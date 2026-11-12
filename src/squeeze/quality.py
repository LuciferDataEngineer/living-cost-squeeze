"""Checks for the committed snapshot and for a lakeFS branch."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

from squeeze.paths import ROOT
from squeeze.reference import HOUSEHOLDS, STATES

HOUSEHOLD_CODES = set(HOUSEHOLDS)
STATE_CODES = set(STATES) | {"AUS", "50"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def _number(value: str) -> float | None:
    text = (value or "").strip()
    if text == "":
        return None
    return float(text)


def audit_rows(kind: str, rows: list[dict[str, str]]) -> list[str]:
    """Return human-readable problems. An empty list means the extract can be published."""
    issues: list[str] = []
    if not rows:
        return [f"{kind}: no rows"]

    if kind == "lci":
        if len(rows) < 1000:
            issues.append(f"{kind}: only {len(rows)} rows")
        for index, row in enumerate(rows, start=1):
            household = row.get("houshold_type") or row.get("household_type")
            measure = row.get("measure")
            value = _number(row.get("obs_value", ""))
            if household not in HOUSEHOLD_CODES:
                issues.append(f"{kind} row {index}: unknown household {household}")
            if measure not in {"1", "2", "3", "4", "5"}:
                issues.append(f"{kind} row {index}: unknown measure {measure}")
            if value is None:
                issues.append(f"{kind} row {index}: missing value")
                continue
            if measure == "1" and not 10 <= value <= 400:
                issues.append(f"{kind} row {index}: index {value} outside 10 to 400")
            if measure == "3" and not -40 <= value <= 100:
                issues.append(f"{kind} row {index}: annual change {value} outside -40 to 100")
            if len(issues) > 12:
                issues.append(f"{kind}: further problems omitted")
                break
    elif kind == "cpi":
        if len(rows) < 100:
            issues.append(f"{kind}: only {len(rows)} rows")
        for index, row in enumerate(rows, start=1):
            value = _number(row.get("obs_value", ""))
            if value is None or not 20 <= value <= 250:
                issues.append(f"{kind} row {index}: index {row.get('obs_value')}")
            if len(issues) > 12:
                break
    elif kind == "wpi":
        if len(rows) < 1000:
            issues.append(f"{kind}: only {len(rows)} rows")
        for index, row in enumerate(rows, start=1):
            value = _number(row.get("obs_value", ""))
            region = row.get("region")
            if region not in STATE_CODES:
                issues.append(f"{kind} row {index}: unknown region {region}")
            if value is None or not -20 <= value <= 300:
                issues.append(f"{kind} row {index}: value {row.get('obs_value')}")
            if len(issues) > 12:
                break
    elif kind == "unemployment":
        for index, row in enumerate(rows, start=1):
            value = _number(row.get("obs_value", ""))
            if value is None or not 0 <= value <= 25:
                issues.append(f"{kind} row {index}: rate {row.get('obs_value')}")
    elif kind == "cash_rate":
        for index, row in enumerate(rows, start=1):
            value = _number(row.get("cash_rate_target", ""))
            if value is None or not 0 <= value <= 20:
                issues.append(f"{kind} row {index}: target {row.get('cash_rate_target')}")
            if row.get("series") not in {"decision", "month_average"}:
                issues.append(f"{kind} row {index}: series {row.get('series')}")
    else:
        issues.append(f"unknown extract {kind}")
    return issues


def audit_snapshot(root: Path | None = None) -> list[str]:
    root = root or ROOT
    manifest_path = root / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    issues: list[str] = []
    kind_by_path = {
        "data/snapshot/lci.csv.gz": "lci",
        "data/snapshot/cpi.csv.gz": "cpi",
        "data/snapshot/wpi_total.csv.gz": "wpi",
        "data/snapshot/wpi_industry.csv.gz": "wpi",
        "data/snapshot/unemployment.csv.gz": "unemployment",
        "data/snapshot/rba_cash_rate.csv.gz": "cash_rate",
    }
    for item in manifest["files"]:
        path = root / str(item["path"])
        if not path.exists():
            issues.append(f"missing {item['path']}")
            continue
        digest = _sha256(path)
        if digest != item["sha256"]:
            issues.append(f"checksum mismatch for {item['path']}")
        rows = _read_csv(path) if path.suffix in {".gz", ".csv"} else []
        if "rows" in item and rows and len(rows) != item["rows"]:
            # Raw RBA files are not a single tidy table, so only compare tidy extracts.
            if str(item["path"]).endswith(".gz"):
                issues.append(f"row count {len(rows)} != {item['rows']} for {item['path']}")
        kind = kind_by_path.get(str(item["path"]))
        if kind:
            issues.extend(audit_rows(kind, rows))
    return issues
