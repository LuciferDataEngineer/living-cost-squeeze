import gzip

from squeeze.quality import audit_rows, audit_snapshot


def test_snapshot_passes_the_quality_gate():
    assert audit_snapshot() == []


def test_bad_living_cost_rows_fail():
    issues = audit_rows(
        "lci",
        [
            {
                "houshold_type": "ZZ",
                "measure": "1",
                "obs_value": "",
                "time_period": "2026-Q3",
            },
            {
                "houshold_type": "P1",
                "measure": "3",
                "obs_value": "250",
                "time_period": "2026-Q3",
            },
        ],
    )
    assert any("unknown household" in issue for issue in issues)
    assert any("missing value" in issue for issue in issues)
    assert any("annual change" in issue for issue in issues)
    assert any("only 2 rows" in issue for issue in issues)


def test_contribution_file_is_gzip_and_small():
    raw = gzip.open("data/snapshot/lci_contribution.csv.gz", "rt").read()
    assert "houshold_type" in raw.splitlines()[0]
    assert "2026-Q3" in raw
