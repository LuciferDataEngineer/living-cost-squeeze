import json
from pathlib import Path

from squeeze.reference import BANNED_DASHBOARD_WORDS

DASHBOARD = Path("site/data/dashboard.json")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_dashboard_contract():
    payload = json.loads(DASHBOARD.read_text())
    assert set(payload["pages"]) == {"squeeze", "behind", "where", "next"}
    for name, page in payload["pages"].items():
        assert 3 <= len(page["kpis"]) <= 5, name
        views = page.get("views") or {"": page}
        for view in views.values():
            supporting = view.get("supporting") or page.get("supporting") or []
            assert len(supporting) <= 3, name
            assert view.get("hero") or page.get("hero")
    text = "\n".join(_strings(payload)).lower()
    for word in BANNED_DASHBOARD_WORDS:
        assert word not in text, word
    assert "5.1%" in payload["pages"]["squeeze"]["kpis"][0]["value"]
    assert "Australia/Sydney" not in text
    assert "September" in payload["banner"]["dek"]


def test_page_shell_redraws_on_tab_change():
    script = Path("site/app.js").read_text()
    html = Path("site/index.html").read_text()
    assert "Australia/Sydney" in script
    assert "dateStyle" not in script
    assert "data-tab" in html
    assert "replaceChildren" in script
    assert "spread(" in script
