"""Command line for the living-cost pipeline."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess

import duckdb

from squeeze.dashboard import build_dashboard
from squeeze.lakefs_wap import run_write_audit_publish
from squeeze.nowcast import run_nowcast
from squeeze.paths import ROOT, TIMINGS, TRACES, WAREHOUSE
from squeeze.quality import audit_snapshot
from squeeze.tracing import setup_tracing, shutdown_tracing, step


def _plan(environment: str) -> None:
    binary = shutil.which("sqlmesh")
    if binary is None:
        raise SystemExit("sqlmesh is not on PATH. Install requirements.txt first.")
    command = [
        binary,
        "plan",
        environment,
        "--auto-apply",
        "--no-prompts",
        "--skip-tests",
    ]
    if environment != "prod":
        command.append("--include-unmodified")
    subprocess.run(command, cwd=ROOT, check=True)


def _write_timings() -> None:
    steps = []
    if TRACES.exists():
        for line in TRACES.read_text().splitlines():
            if line.strip():
                steps.append(json.loads(line))
    snapshot_bytes = sum(path.stat().st_size for path in (ROOT / "data" / "snapshot").glob("*") if path.is_file())
    warehouse_bytes = WAREHOUSE.stat().st_size if WAREHOUSE.exists() else 0
    payload = {
        "steps": steps,
        "total_ms": round(sum(item["duration_ms"] for item in steps), 2),
        "snapshot_bytes": snapshot_bytes,
        "warehouse_bytes": warehouse_bytes,
        "cost_aud": 0,
    }
    TIMINGS.parent.mkdir(parents=True, exist_ok=True)
    TIMINGS.write_text(json.dumps(payload, indent=2) + "\n")
    for item in steps:
        print(f"{item['name']}: {item['duration_ms']:.0f} ms")
    print(f"total: {payload['total_ms']:.0f} ms, snapshot {snapshot_bytes} bytes, cost $0")


def run_pipeline(fast: bool = False) -> None:
    setup_tracing()
    try:
        with step("quality_gate"):
            issues = audit_snapshot()
            if issues:
                raise SystemExit("Snapshot failed the quality gate:\n" + "\n".join(issues))
        with step("sqlmesh_prod"):
            _plan("prod")
        with step("sqlmesh_dev"):
            _plan("dev")
        with step("nowcast"):
            run_nowcast(fast=fast)
        with step("dashboard"):
            build_dashboard()
    finally:
        shutdown_tracing()
    _write_timings()


def run_step(name: str, fast: bool = False) -> None:
    if name == "audit":
        issues = audit_snapshot()
        if issues:
            raise SystemExit("\n".join(issues))
        print("AUDIT_OK")
    elif name == "transform":
        _plan("prod")
        print("TRANSFORM_OK")
    elif name == "nowcast":
        run_nowcast(fast=fast or os.environ.get("NOWCAST_FAST") == "1")
        print("NOWCAST_OK")
    elif name == "publish":
        connection = duckdb.connect(str(WAREHOUSE), read_only=True)
        value = connection.execute(
            """
            SELECT lci_yoy FROM gold.household_gap
            WHERE household_type = 'P1' AND time_period = '2026-Q3'
            """
        ).fetchone()[0]
        connection.close()
        print(f"EMPLOYEE_LCI_YOY_2026Q3={value}")
    else:
        raise SystemExit(f"unknown step {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Living-cost squeeze pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--fast", action="store_true")
    sub.add_parser("dashboard")
    sub.add_parser("lakefs")
    step_parser = sub.add_parser("step")
    step_parser.add_argument("name", choices=["audit", "transform", "nowcast", "publish"])
    step_parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        run_pipeline(fast=args.fast)
    elif args.command == "dashboard":
        build_dashboard()
    elif args.command == "lakefs":
        result = run_write_audit_publish()
        print(json.dumps({key: result[key] for key in ("merged", "failed_branch_merged", "main_unchanged_after_failure")}))
    elif args.command == "step":
        run_step(args.name, fast=args.fast)


if __name__ == "__main__":
    main()
