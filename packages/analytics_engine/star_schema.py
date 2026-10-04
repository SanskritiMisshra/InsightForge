"""
Stage 9: Star Schema & DAX Measures Generator
Deconstructs flat e-commerce transactions into a Kimball-style dimensional star schema:
- 1 central Fact table (fact_sales)
- 4 Conformed Dimension tables (dim_dates, dim_customers, dim_products, dim_payment_methods)
- 10 Production-grade DAX measures with explicit business rationales
"""

from typing import List, Dict, Any
from .types import StarSchemaModel, StarSchemaTable, DAXMeasure


class StarSchemaGenerator:
    @classmethod
    def generate(cls) -> StarSchemaModel:
        tables = [
            StarSchemaTable(
                name="fact_sales",
                type="fact",
                columns=[
                    {"name": "sales_key", "type": "BIGINT", "role": "SURROGATE_KEY"},
                    {"name": "order_id", "type": "VARCHAR(64)", "role": "DEGENERATE_DIMENSION"},
                    {"name": "date_key", "type": "INTEGER", "role": "FOREIGN_KEY"},
                    {"name": "customer_key", "type": "INTEGER", "role": "FOREIGN_KEY"},
                    {"name": "product_key", "type": "INTEGER", "role": "FOREIGN_KEY"},
                    {"name": "payment_key", "type": "INTEGER", "role": "FOREIGN_KEY"},
                    {"name": "quantity", "type": "INTEGER", "role": "ADDITIVE_MEASURE"},
                    {"name": "unit_price", "type": "DECIMAL(12,2)", "role": "NON_ADDITIVE_PRICE"},
                    {"name": "discount_pct", "type": "DECIMAL(5,4)", "role": "RATE"},
                    {"name": "total_amount", "type": "DECIMAL(14,2)", "role": "ADDITIVE_REVENUE"},
                ],
                primary_key="sales_key",
                foreign_keys=[
                    {"column": "date_key", "references": "dim_dates.date_key"},
                    {"column": "customer_key", "references": "dim_customers.customer_key"},
                    {"column": "product_key", "references": "dim_products.product_key"},
                    {"column": "payment_key", "references": "dim_payment_methods.payment_key"},
                ],
            ),
            StarSchemaTable(
                name="dim_dates",
                type="dimension",
                columns=[
                    {"name": "date_key", "type": "INTEGER", "role": "PRIMARY_KEY"},
                    {"name": "full_date", "type": "DATE", "role": "DATE_ATTRIBUTE"},
                    {"name": "year", "type": "INTEGER", "role": "HIERARCHY_LEVEL_1"},
                    {"name": "quarter", "type": "VARCHAR(2)", "role": "HIERARCHY_LEVEL_2"},
                    {"name": "month_num", "type": "INTEGER", "role": "SORT_ORDER"},
                    {"name": "month_name", "type": "VARCHAR(16)", "role": "HIERARCHY_LEVEL_3"},
                    {"name": "day_of_month", "type": "INTEGER", "role": "ATTRIBUTE"},
                    {"name": "day_name", "type": "VARCHAR(12)", "role": "ATTRIBUTE"},
                ],
                primary_key="date_key",
            ),
            StarSchemaTable(
                name="dim_customers",
                type="dimension",
                columns=[
                    {"name": "customer_key", "type": "INTEGER", "role": "PRIMARY_KEY"},
                    {"name": "customer_id", "type": "VARCHAR(64)", "role": "BUSINESS_KEY"},
                    {"name": "city", "type": "VARCHAR(64)", "role": "GEOGRAPHY"},
                    {"name": "region", "type": "VARCHAR(32)", "role": "GEOGRAPHY_HIERARCHY"},
                    {"name": "rfm_segment", "type": "VARCHAR(32)", "role": "ANALYTICAL_SEGMENT"},
                ],
                primary_key="customer_key",
            ),
            StarSchemaTable(
                name="dim_products",
                type="dimension",
                columns=[
                    {"name": "product_key", "type": "INTEGER", "role": "PRIMARY_KEY"},
                    {"name": "product_id", "type": "VARCHAR(64)", "role": "BUSINESS_KEY"},
                    {"name": "product_name", "type": "VARCHAR(128)", "role": "ATTRIBUTE"},
                    {"name": "category", "type": "VARCHAR(64)", "role": "HIERARCHY_LEVEL_1"},
                    {"name": "is_pareto_core", "type": "BOOLEAN", "role": "FLAG"},
                ],
                primary_key="product_key",
            ),
            StarSchemaTable(
                name="dim_payment_methods",
                type="dimension",
                columns=[
                    {"name": "payment_key", "type": "INTEGER", "role": "PRIMARY_KEY"},
                    {"name": "payment_method", "type": "VARCHAR(32)", "role": "ATTRIBUTE"},
                    {"name": "is_digital_rail", "type": "BOOLEAN", "role": "FLAG"},
                ],
                primary_key="payment_key",
            ),
        ]

        relationships = [
            {"from": "fact_sales.date_key", "to": "dim_dates.date_key", "cardinality": "many_to_one", "cross_filter": "single"},
            {"from": "fact_sales.customer_key", "to": "dim_customers.customer_key", "cardinality": "many_to_one", "cross_filter": "single"},
            {"from": "fact_sales.product_key", "to": "dim_products.product_key", "cardinality": "many_to_one", "cross_filter": "single"},
            {"from": "fact_sales.payment_key", "to": "dim_payment_methods.payment_key", "cardinality": "many_to_one", "cross_filter": "single"},
        ]

        dax_measures = [
            DAXMeasure(
                name="Total Revenue",
                formula="SUM(fact_sales[total_amount])",
                format_string="$#,##0.00",
                description="Deterministic gross sales revenue after item-level discounts.",
                category="Revenue",
            ),
            DAXMeasure(
                name="Total Orders",
                formula="DISTINCTCOUNT(fact_sales[order_id])",
                format_string="#,##0",
                description="Distinct count of unique transaction invoices completed.",
                category="Volume",
            ),
            DAXMeasure(
                name="Total Units Sold",
                formula="SUM(fact_sales[quantity])",
                format_string="#,##0",
                description="Cumulative physical units shipped across all product lines.",
                category="Volume",
            ),
            DAXMeasure(
                name="Active Customers",
                formula="DISTINCTCOUNT(fact_sales[customer_key])",
                format_string="#,##0",
                description="Number of unique customer keys with at least one recorded sale.",
                category="Customer",
            ),
            DAXMeasure(
                name="Average Order Value",
                formula="DIVIDE([Total Revenue], [Total Orders], 0)",
                format_string="$#,##0.00",
                description="Average monetary value captured per distinct transaction invoice.",
                category="Efficiency",
            ),
            DAXMeasure(
                name="Revenue YoY %",
                formula="""VAR CurrentRev = [Total Revenue]
VAR PriorRev = CALCULATE([Total Revenue], SAMEPERIODLASTYEAR(dim_dates[full_date]))
RETURN DIVIDE(CurrentRev - PriorRev, PriorRev, 0)""",
                format_string="0.0%",
                description="Year-over-Year revenue growth rate comparing identical calendar periods.",
                category="Growth",
            ),
            DAXMeasure(
                name="Customer Lifetime Value",
                formula="DIVIDE([Total Revenue], [Active Customers], 0)",
                format_string="$#,##0.00",
                description="Average cumulative gross spend across all transacting buyers.",
                category="Customer",
            ),
            DAXMeasure(
                name="Repeat Purchase Rate",
                formula="""VAR MultiBuyers = COUNTROWS(FILTER(dim_customers, [Customer Order Count] > 1))
RETURN DIVIDE(MultiBuyers, [Active Customers], 0)""",
                format_string="0.0%",
                description="Proportion of transacting customers who made 2 or more orders.",
                category="Retention",
            ),
            DAXMeasure(
                name="Discount Dollar Drag",
                formula="SUMX(fact_sales, (fact_sales[quantity] * fact_sales[unit_price]) - fact_sales[total_amount])",
                format_string="$#,##0.00",
                description="Total gross margin conceded through promotional discounts.",
                category="Profitability",
            ),
            DAXMeasure(
                name="Digital Payment Ratio",
                formula="""VAR DigitalRev = CALCULATE([Total Revenue], dim_payment_methods[is_digital_rail] = TRUE())
RETURN DIVIDE(DigitalRev, [Total Revenue], 0)""",
                format_string="0.0%",
                description="Percentage of sales settled through prepaid digital rails (UPI, Card, Net Banking).",
                category="Payment",
            ),
        ]

        return StarSchemaModel(
            tables=tables,
            relationships=relationships,
            dax_measures=dax_measures,
        )
