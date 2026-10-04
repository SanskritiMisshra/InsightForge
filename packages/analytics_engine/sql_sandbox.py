"""
Sandboxed SQL Query Engine
Executes read-only analytical queries against datasets using DuckDB.
Guarded by an AST safety layer via sqlglot that prohibits any data-mutating or administrative statements.
"""

import time
import duckdb
import sqlglot
from sqlglot import exp
import pandas as pd
from typing import List, Dict, Any, Tuple
from .types import SQLQueryResult


DISALLOWED_EXPRESSIONS = (
    exp.Drop,
    exp.Delete,
    exp.Update,
    exp.Insert,
    exp.Alter,
    exp.Create,
    exp.Pragma,
    exp.Command,
)


class SQLSandbox:
    @staticmethod
    def validate_ast_safety(query: str) -> Tuple[bool, str]:
        """
        Parses SQL query AST using sqlglot to guarantee 100% read-only safety.
        Rejects multiple statements, mutations, file exports, or system commands.
        """
        try:
            parsed = sqlglot.parse(query, read="duckdb")
        except Exception as e:
            return False, f"SQL Syntax Error: {str(e)}"

        if len(parsed) == 0:
            return False, "Empty query provided."
        if len(parsed) > 1:
            return False, "Batch / multi-statement SQL execution is prohibited. Provide a single SELECT statement."

        stmt = parsed[0]
        if stmt is None:
            return False, "Invalid SQL statement."

        # Check for disallowed expression types in AST
        for disallowed in DISALLOWED_EXPRESSIONS:
            if stmt.find(disallowed):
                return False, f"Prohibited SQL expression detected: {disallowed.__name__}. Only read-only SELECT is permitted."

        # Root statement must be a Select or Union or With
        if not isinstance(stmt, (exp.Select, exp.Union)):
            return False, f"Statement type '{type(stmt).__name__}' is prohibited. Only SELECT queries are permitted."

        return True, ""

    @classmethod
    def execute_query(cls, df: pd.DataFrame, query: str, table_name: str = "retail_sales") -> SQLQueryResult:
        # 1. AST Validation
        is_safe, error_msg = cls.validate_ast_safety(query)
        if not is_safe:
            raise ValueError(error_msg)

        # 2. Append LIMIT if not present to guard browser memory
        clean_query = query.strip().rstrip(";")
        if "limit" not in clean_query.lower():
            clean_query = f"{clean_query} LIMIT 500"

        # 3. Execute in DuckDB in-memory session
        t_start = time.perf_counter()
        con = duckdb.connect(database=":memory:")
        try:
            # Register dataframe as raw_table
            con.register("raw_table", df)

            # Build aliased view so transactions, retail_sales, and sales work with both schema naming conventions
            extra_cols = []
            if "order_id" in df.columns and "transaction_id" not in df.columns:
                extra_cols.append("order_id AS transaction_id")
            if "order_date" in df.columns and "purchase_date" not in df.columns:
                extra_cols.append("order_date AS purchase_date")
            if "total_amount" in df.columns and "revenue" not in df.columns:
                extra_cols.append("total_amount AS revenue")

            alias_clause = (", " + ", ".join(extra_cols)) if extra_cols else ""
            con.execute(f"CREATE OR REPLACE VIEW transactions AS SELECT * {alias_clause} FROM raw_table;")
            con.execute("CREATE OR REPLACE VIEW retail_sales AS SELECT * FROM transactions;")
            con.execute("CREATE OR REPLACE VIEW sales AS SELECT * FROM transactions;")

            result = con.execute(clean_query)
            description = result.description
            col_names = [d[0] for d in description] if description else []
            col_types = [str(d[1]) for d in description] if description else []

            raw_rows = result.fetchall()
            t_end = time.perf_counter()
            exec_time_ms = round((t_end - t_start) * 1000, 2)

            # Format rows for JSON serialization
            formatted_rows = []
            for r in raw_rows:
                formatted_rows.append([None if v is None else (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)) for v in r])

            return SQLQueryResult(
                query=clean_query,
                columns=col_names,
                column_types=col_types,
                rows=formatted_rows,
                row_count=len(formatted_rows),
                execution_time_ms=exec_time_ms,
                is_read_only=True,
                applied_limit=500,
            )
        finally:
            con.close()
