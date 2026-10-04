"""
Storage and Database Layer for InsightForge
Implements SQLite multi-tenant relational persistence matching DATABASE.md.
Stores database on Drive D: d:\\InsightForge\\data\\insightforge.db
"""

import os
import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "insightforge.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 10000;")
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.executescript("""
    -- Organizations
    CREATE TABLE IF NOT EXISTS organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL
    );

    -- Workspaces
    CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        slug TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
    );

    -- Users
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'ANALYST',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
    );

    -- Projects
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        name TEXT NOT NULL,
        domain TEXT NOT NULL DEFAULT 'retail',
        description TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
    );

    -- Datasets
    CREATE TABLE IF NOT EXISTS datasets (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    -- Dataset Versions (Immutable per DATABASE.md §4)
    CREATE TABLE IF NOT EXISTS dataset_versions (
        id TEXT PRIMARY KEY,
        dataset_id TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        version_label TEXT NOT NULL,
        sha256_hash TEXT NOT NULL,
        parent_version_id TEXT,
        row_count INTEGER NOT NULL,
        column_count INTEGER NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        storage_path TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
        FOREIGN KEY (parent_version_id) REFERENCES dataset_versions(id)
    );

    -- Analysis Runs
    CREATE TABLE IF NOT EXISTS analysis_runs (
        id TEXT PRIMARY KEY,
        dataset_version_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'COMPLETED',  -- PENDING, PROCESSING, COMPLETED, FAILED
        stage TEXT NOT NULL DEFAULT 'REPORT_READY',
        progress_pct INTEGER NOT NULL DEFAULT 100,
        error_message TEXT,
        duration_ms INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE CASCADE
    );

    -- Metrics (Append-only per DATABASE.md §6.8)
    CREATE TABLE IF NOT EXISTS metrics (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        dataset_version_id TEXT NOT NULL,
        metric_key TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        category TEXT NOT NULL,
        formatted_value TEXT NOT NULL,
        numeric_value REAL NOT NULL,
        unit TEXT NOT NULL,
        grain TEXT NOT NULL,
        formula TEXT NOT NULL,
        underlying_sql TEXT NOT NULL,
        sha256_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE,
        FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE CASCADE
    );

    -- Quality Profiles
    CREATE TABLE IF NOT EXISTS quality_profiles (
        id TEXT PRIMARY KEY,
        dataset_version_id TEXT NOT NULL,
        overall_score INTEGER NOT NULL,
        completeness_score INTEGER NOT NULL,
        uniqueness_score INTEGER NOT NULL,
        validity_score INTEGER NOT NULL,
        consistency_score INTEGER NOT NULL,
        total_rows INTEGER NOT NULL,
        total_cells INTEGER NOT NULL,
        null_cells INTEGER NOT NULL,
        duplicate_rows INTEGER NOT NULL,
        outlier_count INTEGER NOT NULL,
        issues_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE CASCADE
    );

    -- Cleaning Logs
    CREATE TABLE IF NOT EXISTS cleaning_logs (
        id TEXT PRIMARY KEY,
        dataset_version_id TEXT NOT NULL,
        step_number INTEGER NOT NULL,
        operation TEXT NOT NULL,
        column_affected TEXT NOT NULL,
        rows_modified INTEGER NOT NULL,
        description TEXT NOT NULL,
        justification TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE CASCADE
    );

    -- Audit Events
    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        details_json TEXT NOT NULL,
        ip_address TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
    );
    """)

    # Seed baseline dev tenant if empty
    cur.execute("SELECT COUNT(*) FROM organizations")
    if cur.fetchone()[0] == 0:
        org_id = "org-0192a001-0000-7000-8000-000000000001"
        ws_id = "ws-0192a001-0000-7000-8000-000000000002"
        user_id = "usr-0192a001-0000-7000-8000-000000000003"
        proj_id = "proj-0192a001-0000-7000-8000-000000000004"
        now = datetime.utcnow().isoformat() + "Z"

        cur.execute(
            "INSERT INTO organizations (id, name, slug, created_at) VALUES (?, ?, ?, ?)",
            (org_id, "InsightForge Enterprise", "insightforge-enterprise", now),
        )
        cur.execute(
            "INSERT INTO workspaces (id, organization_id, name, slug, created_at) VALUES (?, ?, ?, ?, ?)",
            (ws_id, org_id, "Retail Analytics Workspace", "retail-analytics", now),
        )
        cur.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, org_id, "analyst@insightforge.ai", "Sanskar", "ANALYST", 1, now),
        )
        cur.execute(
            "INSERT INTO projects (id, workspace_id, name, domain, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (proj_id, ws_id, "Retail Omnichannel Analytics", "retail", "Automated BI pipeline for omnichannel retail transactions", now),
        )
        cur.execute(
            "INSERT INTO projects (id, workspace_id, name, domain, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"proj-{uuid.uuid4()}", ws_id, "E-Commerce Q3 Flash Sale", "ecommerce", "Performance analytics and basket velocity for holiday sales", now),
        )
        cur.execute(
            "INSERT INTO projects (id, workspace_id, name, domain, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"proj-{uuid.uuid4()}", ws_id, "B2B Wholesale & Distribution", "wholesale", "Bulk order fulfillment, customer credit terms and logistics", now),
        )

    conn.commit()
    conn.close()


class DatabaseRepository:
    @staticmethod
    def list_projects() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM projects ORDER BY created_at ASC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_default_project() -> Dict[str, Any]:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM projects LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}

    @staticmethod
    def create_project(name: str, domain: str = "retail", description: str = "") -> Dict[str, Any]:
        conn = get_db_connection()
        cur = conn.cursor()
        # Get default workspace
        cur.execute("SELECT id FROM workspaces LIMIT 1")
        ws_row = cur.fetchone()
        ws_id = ws_row["id"] if ws_row else "ws-default"
        proj_id = f"proj-{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + "Z"
        cur.execute(
            "INSERT INTO projects (id, workspace_id, name, domain, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (proj_id, ws_id, name, domain, description, now),
        )
        conn.commit()
        conn.close()
        return {"id": proj_id, "name": name, "domain": domain, "description": description, "created_at": now}

    @staticmethod
    def get_datasets_for_project(project_id: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM datasets WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_versions_for_dataset(dataset_id: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM dataset_versions WHERE dataset_id = ? ORDER BY version_number ASC", (dataset_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_metrics_for_version(version_id: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM metrics WHERE dataset_version_id = ? ORDER BY category, metric_name", (version_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def record_audit_event(org_id: str, user_id: str, event_type: str, resource_type: str, resource_id: str, details: Dict[str, Any]):
        conn = get_db_connection()
        cur = conn.cursor()
        event_id = f"aud-{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + "Z"
        cur.execute(
            "INSERT INTO audit_events (id, organization_id, user_id, event_type, resource_type, resource_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, org_id, user_id, event_type, resource_type, resource_id, json.dumps(details), now),
        )
        conn.commit()
        conn.close()
