"""The Queue page as the demo API serves it (S7.7). Skips where the demo API is not running.

No browser here: this checks what can be checked without one -- the page and every asset it
references load, every response carries the CSP, and nothing comes from another host.
"""

import re
import urllib.error
import urllib.request

import pytest

BASE = "http://127.0.0.1:8130"


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return r.status, dict(r.headers), r.read().decode("utf-8", "replace")


def _up():
    try:
        return _get("/api/health")[0] == 200
    except (urllib.error.URLError, OSError):
        return False


pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not _up(), reason="demo API not running here")]  # fmt: skip


@pytest.mark.parametrize("page", ["/", "/case/", "/about/"])
def test_each_page_and_every_asset_it_references_loads_with_the_csp(page):
    status, headers, html = _get(page)
    assert status == 200 and "script-src 'self'" in headers["content-security-policy"]
    assets = re.findall(r'(?:src|href)="(/_next/[^"]+)"', html)
    assert assets, "no Next.js assets referenced"
    for a in assets:
        s, h, _ = _get(a)
        assert s == 200 and "content-security-policy" in h, a
    # nothing LOADED from another host (a plain <a href> link is navigation, allowed)
    assert not re.search(r'src="(?:https?:)?//|<link\b[^>]*href="(?:https?:)?//', html)


def test_the_queue_page_carries_the_synthetic_data_banner():
    _, _, html = _get("/")
    assert "Synthetic data." in html and "People check only the riskiest." in html


def test_the_about_page_is_prerendered_with_its_numbers():
    _, _, html = _get("/about/")
    for text in ("What this is", "The leakage contract", "0.28155", "542 of 1,083", "SR 26-2"):
        assert text in html, text
