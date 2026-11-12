"""Browser checks that chart labels stay inside the plot and clear of each other."""

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1] / "site"
DESKTOP = 1280
PHONE = 390

INSPECT = r"""
() => {
  const problems = [];
  const watched = [
    "Mortgage interest has climbed much faster than the rest of the basket",
    "The gap has been building since 2021",
  ];
  for (const title of watched) {
    const svg = document.querySelector(`svg[aria-label="${title}"]`);
    if (!svg) continue;
    const labels = [...svg.querySelectorAll("text.x-axis")].map((node) => node.textContent);
    if (!labels.includes("Sep 2026")) {
      problems.push(`${title}: latest quarter Sep 2026 is missing from the x-axis`);
    }
  }
  for (const svg of document.querySelectorAll("svg")) {
    const svgBox = svg.getBoundingClientRect();
    const title = svg.getAttribute("aria-label") || "chart";
    if (svgBox.width < 20 || svgBox.height < 20) {
      problems.push(`${title}: chart did not lay out`);
      continue;
    }
    const texts = [...svg.querySelectorAll("text")].flatMap((node) => {
      const box = node.getBoundingClientRect();
      if (box.width < 0.5 || box.height < 0.5) return [];
      return [{ text: (node.textContent || "").trim(), box }];
    });
    if (!texts.length) problems.push(`${title}: chart has no labels`);
    for (const item of texts) {
      const box = item.box;
      const overflow = [
        ["left", svgBox.left - box.left],
        ["right", box.right - svgBox.right],
        ["top", svgBox.top - box.top],
        ["bottom", box.bottom - svgBox.bottom],
      ].filter(([, value]) => value > 1);
      if (overflow.length) {
        const detail = overflow.map(([side, value]) => `${side} ${value.toFixed(1)}px`).join(", ");
        problems.push(`${title}: "${item.text}" is clipped (${detail})`);
      }
    }
    for (let i = 0; i < texts.length; i += 1) {
      for (let j = i + 1; j < texts.length; j += 1) {
        const a = texts[i].box;
        const b = texts[j].box;
        const overlapX = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (overlapX > 1 && overlapY > 1) {
          problems.push(
            `${title}: "${texts[i].text}" overlaps "${texts[j].text}" by ${overlapX.toFixed(1)}×${overlapY.toFixed(1)}px`,
          );
        }
      }
    }
  }
  return problems;
}
"""


class _QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def log_message(self, *_args):
        return


def _playwright():
    return pytest.importorskip("playwright.sync_api")


def _launch(playwright):
    errors = []
    for kwargs in ({}, {"channel": "chrome"}):
        try:
            return playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"], **kwargs)
        except Exception as exc:  # noqa: BLE001 — try bundled Chromium, then system Chrome
            label = kwargs.get("channel", "bundled chromium")
            errors.append(f"{label}: {exc}")
    raise RuntimeError("No Chromium or Chrome browser available\n" + "\n".join(errors))


@pytest.fixture(scope="module")
def site_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with _playwright().sync_playwright() as playwright:
        launched = _launch(playwright)
        yield launched
        launched.close()


def _expect_clean(page, width, tab_name, view_name):
    problems = page.evaluate(INSPECT)
    assert not problems, f"{width}px, {tab_name} / {view_name}:\n" + "\n".join(problems)


@pytest.mark.parametrize("viewport_width", [DESKTOP, PHONE])
def test_chart_labels_do_not_overlap_or_clip(site_server, browser, viewport_width):
    page = browser.new_page(viewport={"width": viewport_width, "height": 900})
    page.set_default_timeout(20_000)
    try:
        page.goto(site_server, wait_until="domcontentloaded")
        page.wait_for_selector(".kpi")
        tabs = page.locator("[data-tab]")
        assert tabs.count() >= 4
        for tab_index in range(tabs.count()):
            tab = tabs.nth(tab_index)
            tab_name = tab.inner_text()
            tab.click()
            page.wait_for_selector("svg text")
            _expect_clean(page, viewport_width, tab_name, "default")
            pills = page.locator(".pills button")
            for pill_index in range(pills.count()):
                pill = pills.nth(pill_index)
                view_name = pill.inner_text()
                pill.click()
                _expect_clean(page, viewport_width, tab_name, view_name)
    finally:
        page.close()
