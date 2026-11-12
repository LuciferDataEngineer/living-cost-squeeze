"""Repository paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data" / "snapshot"
MANIFEST = ROOT / "data" / "manifest.json"
WAREHOUSE = ROOT / "warehouse" / "squeeze.duckdb"
TRACES = ROOT / "data" / "traces" / "pipeline.jsonl"
TIMINGS = ROOT / "data" / "perf" / "timings.json"
DASHBOARD = ROOT / "site" / "data" / "dashboard.json"
INSIGHTS = ROOT / "data" / "perf" / "insights.json"
