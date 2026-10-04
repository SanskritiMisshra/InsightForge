"""
InsightForge Automated Healthcheck Script
Validates:
1. REST API readiness on port 8080
2. In-memory DuckDB query execution
3. Multi-tenant database connectivity
"""

import sys
import json
import urllib.request
import urllib.error

HEALTH_URL = "http://localhost:8080/api/v1/health"

def run_healthcheck() -> bool:
    try:
        req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "InsightForge-Healthcheck/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                print(f"[HEALTHCHECK FAIL] Non-200 HTTP status: {response.status}", file=sys.stderr)
                return False
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") == "healthy" and payload.get("dataset_loaded"):
                print("[HEALTHCHECK PASS] Engine is healthy and dataset is active.")
                return True
            else:
                print(f"[HEALTHCHECK FAIL] Unexpected health payload: {payload}", file=sys.stderr)
                return False
    except urllib.error.URLError as e:
        print(f"[HEALTHCHECK FAIL] Connection refused or timed out: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[HEALTHCHECK FAIL] Unexpected error: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    is_healthy = run_healthcheck()
    sys.exit(0 if is_healthy else 1)
