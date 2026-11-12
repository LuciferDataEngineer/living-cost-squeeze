import pytest

from squeeze.lakefs_wap import run_write_audit_publish


@pytest.mark.lakefs
def test_failed_audit_branch_is_not_merged():
    result = run_write_audit_publish(repo="squeeze")
    assert result["ingest_issues"] == []
    assert result["merged"] is True
    assert result["publish_moved_main"] is True
    assert result["failed_branch"] == "audit-fail"
    assert result["failure_reasons"]
    assert result["failed_branch_merged"] is False
    assert result["main_unchanged_after_failure"] is True
