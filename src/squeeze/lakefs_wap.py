"""Write-audit-publish on lakeFS.

Files land on an ingest branch. They are merged to main only after the
quality gate passes. A second branch is left unmerged on purpose so the
failed audit is visible.
"""

from __future__ import annotations

import csv
import gzip
import io
import os
import uuid

import requests

from squeeze.paths import SNAPSHOT
from squeeze.quality import audit_rows

DEFAULT_HOST = "http://127.0.0.1:8000"
DEFAULT_KEY = "AKIAIOSFOLKFSSAMPLES"
DEFAULT_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


class LakeFS:
    def __init__(self, host: str | None = None, key: str | None = None, secret: str | None = None) -> None:
        self.host = (host or os.environ.get("LAKEFS_HOST", DEFAULT_HOST)).rstrip("/")
        self.auth = (
            key or os.environ.get("LAKEFS_ACCESS_KEY", DEFAULT_KEY),
            secret or os.environ.get("LAKEFS_SECRET_KEY", DEFAULT_SECRET),
        )

    def request(self, method: str, path: str, *, ok: tuple[int, ...] = (200, 201, 204), **kwargs):
        response = requests.request(method, f"{self.host}{path}", auth=self.auth, timeout=90, **kwargs)
        if response.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {response.status_code} {response.text[:400]}")
        return response

    def delete_repo(self, name: str) -> None:
        self.request("DELETE", f"/api/v1/repositories/{name}", ok=(200, 204, 404))

    def create_repo(self, name: str, namespace: str) -> None:
        self.request(
            "POST",
            "/api/v1/repositories",
            json={"name": name, "storage_namespace": namespace, "default_branch": "main"},
        )

    def create_branch(self, repo: str, name: str, source: str) -> None:
        self.request(
            "POST",
            f"/api/v1/repositories/{repo}/branches",
            json={"name": name, "source": source},
        )

    def branch_head(self, repo: str, name: str) -> str:
        response = self.request("GET", f"/api/v1/repositories/{repo}/branches/{name}")
        return response.json()["commit_id"]

    def upload(self, repo: str, branch: str, path: str, payload: bytes) -> None:
        self.request(
            "POST",
            f"/api/v1/repositories/{repo}/branches/{branch}/objects",
            params={"path": path},
            data=payload,
            headers={"Content-Type": "application/octet-stream"},
        )

    def download(self, repo: str, ref: str, path: str) -> bytes:
        response = self.request(
            "GET",
            f"/api/v1/repositories/{repo}/refs/{ref}/objects",
            params={"path": path},
        )
        return response.content

    def commit(self, repo: str, branch: str, message: str) -> str:
        response = self.request(
            "POST",
            f"/api/v1/repositories/{repo}/branches/{branch}/commits",
            json={"message": message, "metadata": {"pattern": "write-audit-publish"}},
        )
        return response.json()["id"]

    def merge(self, repo: str, source: str, destination: str, message: str) -> str:
        response = self.request(
            "POST",
            f"/api/v1/repositories/{repo}/refs/{source}/merge/{destination}",
            json={"message": message},
        )
        return response.json()["reference"]


def _rows_from_gzip(payload: bytes) -> list[dict[str, str]]:
    text = gzip.decompress(payload).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def run_write_audit_publish(client: LakeFS | None = None, repo: str = "squeeze") -> dict[str, object]:
    client = client or LakeFS()
    client.delete_repo(repo)
    namespace = f"s3://lakefs-data/{repo}-{uuid.uuid4().hex[:10]}"
    client.create_repo(repo, namespace)
    main_before = client.branch_head(repo, "main")

    client.create_branch(repo, "ingest", "main")
    for path in sorted(SNAPSHOT.iterdir()):
        if path.is_file():
            client.upload(repo, "ingest", f"raw/{path.name}", path.read_bytes())
    client.commit(repo, "ingest", "Ingest the public snapshot")
    published = _rows_from_gzip(client.download(repo, "ingest", "raw/lci.csv.gz"))
    ingest_issues = audit_rows("lci", published)
    merged = False
    if not ingest_issues:
        client.merge(repo, "ingest", "main", "Publish after the quality gate")
        merged = True
    main_after_pass = client.branch_head(repo, "main")

    client.create_branch(repo, "audit-fail", "main")
    bad = (
        "dataflow,measure,index,houshold_type,region,freq,time_period,obs_value\n"
        "ABS:LCI,1,10001,ZZ,50,Q,2026-Q3,\n"
        "ABS:LCI,3,10001,P1,50,Q,2026-Q3,250\n"
    ).encode()
    client.upload(repo, "audit-fail", "raw/lci.csv.gz", gzip.compress(bad, mtime=0))
    client.commit(repo, "audit-fail", "Load a file that should fail the gate")
    failed_rows = _rows_from_gzip(client.download(repo, "audit-fail", "raw/lci.csv.gz"))
    failures = audit_rows("lci", failed_rows)
    failed_merged = False
    if not failures:
        client.merge(repo, "audit-fail", "main", "This merge should not happen")
        failed_merged = True
    main_after_fail = client.branch_head(repo, "main")

    return {
        "repo": repo,
        "namespace": namespace,
        "merged": merged,
        "ingest_issues": ingest_issues,
        "failed_branch": "audit-fail",
        "failed_branch_merged": failed_merged,
        "failure_reasons": failures,
        "main_before": main_before,
        "main_after_pass": main_after_pass,
        "main_after_fail": main_after_fail,
        "main_unchanged_after_failure": main_after_fail == main_after_pass,
        "publish_moved_main": main_after_pass != main_before,
    }
