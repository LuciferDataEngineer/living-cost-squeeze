"""Download the free ABS and RBA extracts and write a checksummed snapshot.

The ABS Data API needs no key. Responses are stored gzipped with a fixed
gzip timestamp so the checksum tracks the file contents. RBA tables are kept
as the exact bytes that were downloaded, plus a small tidy cash-rate file
derived from them.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "snapshot"
MANIFEST = ROOT / "data" / "manifest.json"
ABS = "https://data.api.abs.gov.au/rest/data"
USER_AGENT = "living-cost-squeeze/0.1 (public-data research; CC-BY)"

LCI_INDEXES = (
    "10001+20001+20002+20003+20004+20005+20006+30016+115486+115488+"
    "115489+115493+115522+126670+130427+131278"
)
HOUSEHOLDS = "PBLCI+P1+P2+P3+P4"
INDUSTRIES = "B+C+D+E+F+G+H+I+J+K+L+M+N+O+P+Q+R+S"


def fetch(url: str, accept: str = "text/csv") -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return exc.code, body


def gzip_bytes(payload: bytes) -> bytes:
    return gzip.compress(payload, mtime=0)


def lowercase_header(payload: bytes) -> bytes:
    """Keep the published values and make the header easy to query."""
    text = payload.decode("utf-8-sig")
    lines = text.splitlines()
    if not lines:
        return payload
    lines[0] = lines[0].lower()
    return ("\n".join(lines) + "\n").encode()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def csv_rows(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def coverage(rows: list[dict[str, str]], column: str = "time_period") -> str:
    if rows and column not in rows[0] and "TIME_PERIOD" in rows[0]:
        column = "TIME_PERIOD"
    values = sorted({row[column] for row in rows if row.get(column)})
    if not values:
        return "none"
    return f"{values[0]} to {values[-1]}"


def write_gz(name: str, payload: bytes) -> dict[str, object]:
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT / name
    payload = lowercase_header(payload)
    compressed = gzip_bytes(payload)
    path.write_bytes(compressed)
    rows = csv_rows(payload)
    return {
        "path": f"data/snapshot/{name}",
        "sha256": sha256(compressed),
        "bytes": len(compressed),
        "rows": len(rows),
        "coverage": coverage(rows) if rows and ("time_period" in rows[0] or "TIME_PERIOD" in rows[0]) else "",
    }


def write_raw(name: str, payload: bytes) -> dict[str, object]:
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT / name
    path.write_bytes(payload)
    return {
        "path": f"data/snapshot/{name}",
        "sha256": sha256(payload),
        "bytes": len(payload),
        "rows": max(payload.count(b"\n") - 1, 0),
    }


def require_csv(name: str, url: str) -> tuple[bytes, dict[str, object]]:
    status, payload = fetch(url)
    if status != 200 or not payload.startswith(b"DATAFLOW"):
        raise SystemExit(f"{name} download failed: HTTP {status} from {url}")
    meta = write_gz(name, payload)
    meta["source_url"] = url
    return payload, meta


def parse_number(value: str) -> float | None:
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    if "to" in text:
        text = text.split("to")[-1].strip()
    text = text.replace("+", "")
    try:
        return float(text)
    except ValueError:
        return None


def tidy_cash_rate(a2: bytes, f1: bytes) -> bytes:
    a2_text = a2.decode("utf-8-sig").splitlines()
    f1_text = f1.decode("utf-8-sig").splitlines()

    def rows_after_series(lines: list[str]) -> list[list[str]]:
        start = next(i for i, line in enumerate(lines) if line.startswith("Series ID"))
        parsed: list[list[str]] = []
        for line in lines[start + 1 :]:
            if not line.strip():
                continue
            parsed.append(next(csv.reader([line])))
        return parsed

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["series", "observed_on", "cash_rate_target", "change_text"])
    for cols in rows_after_series(a2_text):
        if len(cols) < 3:
            continue
        target = parse_number(cols[2])
        if target is None:
            continue
        observed = datetime.strptime(cols[0], "%d-%b-%Y").date().isoformat()
        writer.writerow(["decision", observed, f"{target:.2f}", cols[1]])
    for cols in rows_after_series(f1_text):
        if len(cols) < 2:
            continue
        target = parse_number(cols[1])
        if target is None:
            continue
        observed = datetime.strptime(cols[0], "%d/%m/%Y").date().isoformat()
        writer.writerow(["month_average", observed, f"{target:.2f}", ""])
    return out.getvalue().encode()


def main() -> None:
    unavailable: list[dict[str, str]] = []
    files: list[dict[str, object]] = []

    lci_url = (
        f"{ABS}/LCI/1+2+3+4.{LCI_INDEXES}.{HOUSEHOLDS}.50.Q"
        "?startPeriod=2004-Q1&dimensionAtObservation=AllDimensions"
    )
    _, lci_meta = require_csv("lci.csv.gz", lci_url)
    lci_meta.update(
        {
            "publisher": "Australian Bureau of Statistics",
            "series": "Selected Living Cost Indexes",
            "licence": "CC BY 4.0",
            "notes": (
                "Quarterly index, quarterly change, annual change, and points "
                "contribution for household types and the main groups. National only."
            ),
        }
    )
    files.append(lci_meta)

    contrib_url = (
        f"{ABS}/LCI/5.10001+20001+20003+20005+115486+130427+131278.{HOUSEHOLDS}.50.Q"
        "?startPeriod=2018-Q1&dimensionAtObservation=AllDimensions"
    )
    _, contrib_meta = require_csv("lci_contribution.csv.gz", contrib_url)
    contrib_meta.update(
        {
            "publisher": "Australian Bureau of Statistics",
            "series": "Selected Living Cost Indexes, change in contribution",
            "licence": "CC BY 4.0",
            "notes": "Measure 5, change in points contribution. Sparse before the latest years.",
        }
    )
    files.append(contrib_meta)

    weight_url = (
        f"{ABS}/LCI_WEIGHTS/1.{LCI_INDEXES}.{HOUSEHOLDS}.50.Q"
        "?startPeriod=2010-Q1&dimensionAtObservation=AllDimensions"
    )
    _, weight_meta = require_csv("lci_weights.csv.gz", weight_url)
    weight_meta.update(
        {
            "publisher": "Australian Bureau of Statistics",
            "series": "Selected Living Cost Indexes weights",
            "licence": "CC BY 4.0",
            "notes": (
                "Budget weights at the updates the API returns. Mortgage interest "
                "as its own weight (item 131278) is not in this extract; interest "
                "charges (130427) are."
            ),
        }
    )
    files.append(weight_meta)

    wpi_url = (
        f"{ABS}/WPI/1+3.THRPEB+OHRPEB.7+1+2.TOT.10+20.AUS+1+2+3+4+5+6+7+8.Q"
        "?startPeriod=2004-Q1&dimensionAtObservation=AllDimensions"
    )
    _, wpi_meta = require_csv("wpi_total.csv.gz", wpi_url)
    wpi_meta.update(
        {
            "publisher": "Australian Bureau of Statistics",
            "series": "Wage Price Index, total hourly and ordinary-time rates",
            "licence": "CC BY 4.0",
            "notes": (
                "All industries. Seasonally adjusted figures are national. "
                "State figures in this extract are original."
            ),
        }
    )
    files.append(wpi_meta)

    industry_url = (
        f"{ABS}/WPI/1+3.THRPEB.7+1.{INDUSTRIES}.10.AUS.Q"
        "?startPeriod=2012-Q1&dimensionAtObservation=AllDimensions"
    )
    _, industry_meta = require_csv("wpi_industry.csv.gz", industry_url)
    industry_meta.update(
        {
            "publisher": "Australian Bureau of Statistics",
            "series": "Wage Price Index by industry division",
            "licence": "CC BY 4.0",
            "notes": (
                "Original total hourly rates excluding bonuses, all-sectors and "
                "private. Agriculture (ANZSIC A) and seasonally adjusted industry "
                "keys return HTTP 404."
            ),
        }
    )
    files.append(industry_meta)

    cpi_url = (
        f"{ABS}/CPI/1.10001.10.50+1+2+3+4+5+6+7+8.Q"
        "?startPeriod=2004-Q1&dimensionAtObservation=AllDimensions"
    )
    _, cpi_meta = require_csv("cpi.csv.gz", cpi_url)
    cpi_meta.update(
        {
            "publisher": "Australian Bureau of Statistics",
            "series": "Consumer Price Index, all groups, original",
            "licence": "CC BY 4.0",
            "notes": (
                "Index numbers for the weighted average of eight capital cities "
                "and each capital. Annual change is calculated in the silver layer "
                "because the percentage-change key returns HTTP 404."
            ),
        }
    )
    files.append(cpi_meta)

    lf_url = (
        f"{ABS}/LF/M13.3.1599.20.AUS+1+2+3+4+5+6+7+8.M"
        "?startPeriod=2015-01&dimensionAtObservation=AllDimensions"
    )
    lf_status, lf_payload = fetch(lf_url)
    if lf_status != 200 or not lf_payload.startswith(b"DATAFLOW"):
        raise SystemExit(f"labour force download failed: HTTP {lf_status}")
    lf_rows = csv_rows(lf_payload)
    regions = sorted({row["REGION"] for row in lf_rows})
    lf_meta = write_gz("unemployment.csv.gz", lf_payload)
    lf_meta.update(
        {
            "source_url": lf_url,
            "publisher": "Australian Bureau of Statistics",
            "series": "Labour force unemployment rate, seasonally adjusted",
            "licence": "CC BY 4.0",
            "notes": (
                "Persons, all ages, seasonally adjusted. Regions returned: "
                + ", ".join(regions)
                + ". Northern Territory and the ACT are absent from this key when "
                "the API does not publish a seasonally adjusted rate for them."
            ),
        }
    )
    files.append(lf_meta)
    if "7" not in regions or "8" not in regions:
        unavailable.append(
            {
                "series": "Seasonally adjusted unemployment, Northern Territory and ACT",
                "attempted_url": lf_url,
                "result": f"HTTP 200 but regions present were {', '.join(regions)}",
                "adaptation": "The state page shows the jobless rate only where this extract has it.",
            }
        )

    probes = [
        (
            "Trimmed-mean CPI",
            f"{ABS}/CPI/1+3.999902.10.50.Q?startPeriod=2018-Q1&dimensionAtObservation=AllDimensions",
            "Headline CPI is calculated from the all-groups index. The trimmed mean is not shown.",
        ),
        (
            "CPI annual percentage change",
            f"{ABS}/CPI/3.10001.10.50.Q?startPeriod=2024-Q1&dimensionAtObservation=AllDimensions",
            "Annual price change is index(t) / index(t-4) - 1, from the published index.",
        ),
        (
            "Wage Price Index, agriculture and seasonally adjusted industries",
            f"{ABS}/WPI/3.THRPEB.7.A+C.20.AUS.Q?startPeriod=2024-Q1&dimensionAtObservation=AllDimensions",
            "Industry wages use the original series for divisions B to S. Agriculture is omitted.",
        ),
    ]
    for series, url, adaptation in probes:
        status, _payload = fetch(url)
        if status != 200:
            unavailable.append(
                {
                    "series": series,
                    "attempted_url": url,
                    "result": f"HTTP {status} on the access date",
                    "adaptation": adaptation,
                }
            )

    unavailable.append(
        {
            "series": "ANZ-Roy Morgan consumer confidence",
            "attempted_url": "",
            "result": "No open, key-free bulk file. The survey is proprietary.",
            "adaptation": "Confidence is not in the snapshot or the dashboard.",
        }
    )
    unavailable.append(
        {
            "series": "Wage Price Index, September quarter 2026",
            "attempted_url": wpi_url,
            "result": "Not in the API extract. The ABS release is scheduled for 18 November 2026.",
            "adaptation": "The next-quarter page estimates the September wage result from the published history.",
        }
    )
    unavailable.append(
        {
            "series": "Selected living cost indexes by state",
            "attempted_url": lci_url,
            "result": "The selected living cost indexes are published for Australia, not by state.",
            "adaptation": "The state page pairs each state's wages with its capital-city price index.",
        }
    )

    a2_url = "https://www.rba.gov.au/statistics/tables/csv/a2-data.csv"
    f1_url = "https://www.rba.gov.au/statistics/tables/csv/f1.1-data.csv"
    a2_status, a2 = fetch(a2_url, accept="text/csv")
    f1_status, f1 = fetch(f1_url, accept="text/csv")
    if a2_status != 200 or not (a2.startswith(b"\xef\xbb\xbfA2") or a2.startswith(b"A2")):
        raise SystemExit(f"RBA A2 download failed: HTTP {a2_status}")
    if f1_status != 200 or b"F1.1" not in f1[:80]:
        raise SystemExit(f"RBA F1.1 download failed: HTTP {f1_status}")
    a2_meta = write_raw("rba_a2.csv", a2)
    a2_meta.update(
        {
            "source_url": a2_url,
            "publisher": "Reserve Bank of Australia",
            "series": "A2 changes in monetary policy",
            "licence": "Free to reuse with attribution (RBA copyright)",
            "coverage": "decision dates",
            "notes": "Exact response bytes, including the preamble.",
        }
    )
    files.append(a2_meta)
    f1_meta = write_raw("rba_f1.csv", f1)
    f1_meta.update(
        {
            "source_url": f1_url,
            "publisher": "Reserve Bank of Australia",
            "series": "F1.1 interest rates and yields, money market",
            "licence": "Free to reuse with attribution (RBA copyright)",
            "coverage": "monthly",
            "notes": "Exact response bytes. The cash-rate target is the second column.",
        }
    )
    files.append(f1_meta)

    tidy = tidy_cash_rate(a2, f1)
    tidy_meta = write_gz("rba_cash_rate.csv.gz", tidy)
    tidy_rows = csv_rows(tidy)
    decisions = [row for row in tidy_rows if row["series"] == "decision"]
    months = [row for row in tidy_rows if row["series"] == "month_average"]
    tidy_meta.update(
        {
            "source_url": a2_url,
            "publisher": "Reserve Bank of Australia",
            "series": "Cash-rate target, tidy extract of A2 and F1.1",
            "licence": "Free to reuse with attribution (RBA copyright)",
            "rows": len(tidy_rows),
            "coverage": f"decisions {decisions[0]['observed_on']} to {decisions[-1]['observed_on']}; months to {months[-1]['observed_on']}",
            "notes": "Derived from the raw A2 and F1.1 files in this snapshot. Not a separate download.",
        }
    )
    files.append(tidy_meta)

    manifest = {
        "project": "living-cost-squeeze",
        "access_date": datetime.now(timezone.utc).date().isoformat(),
        "access_note": "Downloaded by scripts/refresh_snapshot.py. ABS and tidy cash-rate files keep the published values with a lower-case header. Dates in the dashboard are shown in Australian Eastern time.",
        "files": files,
        "unavailable": unavailable,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {MANIFEST} ({len(files)} files)")
    for item in files:
        print(f"  {item['path']}: {item['rows']} rows, {item['coverage']}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        print(f"network error: {exc}", file=sys.stderr)
        sys.exit(1)
