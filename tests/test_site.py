"""The QR landing pages (site/): links are validated, text is escaped, and in a real browser the review opens
beside the page and the guest comes back to the payment button. Browser tests skip where Chromium is missing."""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))

import build as site_build

CHROMIUM = os.environ.get("CHROMIUM_PATH", "/opt/pw-browsers/chromium")


def write_business(d: Path, **b):
    d.mkdir(parents=True, exist_ok=True)
    data = {"id": "test-cafe", "name": "Test Cafe", "languages": ["de", "en"],
            "review_url": "https://g.page/r/CtestReviewId/review", "payment": {"url": "https://paypal.me/testcafe", "label": "PayPal"},
            **b}
    (d / f"{data['id']}.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_strict_build_refuses_placeholders_and_preview_builds(tmp_path):
    with pytest.raises(site_build.BuildError, match="FILL_IN"):
        site_build.build(tmp_path / "out")
    res = site_build.build(tmp_path / "out", preview=True)
    assert "demo-cafe" in res["businesses"]
    out = tmp_path / "out"
    for f in ("r/demo-cafe/index.html", "r/demo-cafe/en.html", "r/demo-cafe/thanks.html", "demo/index.html",
              "impressum.html", "datenschutz.html", "privacy.html", "_headers", "assets/r.js"):
        assert (out / f).exists(), f
    assert "script-src 'self'" in (out / "_headers").read_text()
    html = (out / "r" / "demo-cafe" / "index.html").read_text()
    assert 'href="https://paypal.me/demo-cafe-luise"' in html and 'target="_blank"' in html
    assert "<script>" not in html and "style=" not in html          # nothing inline: the CSP stays strict
    assert "freiwillig" in html                                     # reviews are explicitly optional
    assert '<a href="en.html" hreflang="en">English</a>' in html    # the German page offers the English one


def test_links_are_checked_and_names_escaped(tmp_path):
    bdir = tmp_path / "b"
    write_business(bdir, name='Bar <script>alert(1)</script> & Grill')
    site_build.build(tmp_path / "out", preview=True, businesses_dir=bdir)
    html = (tmp_path / "out" / "r" / "test-cafe" / "index.html").read_text()
    assert "<script>alert(1)" not in html and "Bar &lt;script&gt;alert(1)&lt;/script&gt; &amp; Grill" in html
    for bad, match in (({"payment": {"url": "https://evil.example/pay"}}, "not a known payment"),
                       ({"payment": {"url": "http://paypal.me/x"}}, "https://"),
                       ({"review_url": "https://evil.example/review"}, "not a known review_url"),
                       ({"id": "Bad Id"}, "id must be")):
        shutil.rmtree(bdir)
        write_business(bdir, **bad)
        with pytest.raises(site_build.BuildError, match=match):
            site_build.build(tmp_path / "out2", preview=True, businesses_dir=bdir)


def test_restaurant_without_payment_link_gets_a_review_page(tmp_path):
    bdir = tmp_path / "b"
    write_business(bdir, payment=None, menu_url="https://example.com/menu.pdf")
    site_build.build(tmp_path / "out", preview=True, businesses_dir=bdir)
    html = (tmp_path / "out" / "r" / "test-cafe" / "index.html").read_text()
    assert 'id="pay"' not in html and "am Tisch oder an der Theke" in html and 'id="menu"' in html
    assert 'id="review" class="btn primary"' in html                # the review is the main button then



def test_qr_code_is_made_once_the_address_is_known(tmp_path):
    pytest.importorskip("segno")
    site = json.loads((ROOT / "site" / "site.json").read_text(encoding="utf-8"))
    site["base_url"] = "https://reviews.example.org/"
    sp = tmp_path / "site.json"
    sp.write_text(json.dumps(site), encoding="utf-8")
    res = site_build.build(tmp_path / "out", preview=True, site_path=sp)
    assert res["base_url"] == "https://reviews.example.org"
    svg = (tmp_path / "out" / "r" / "demo-cafe" / "qr.svg").read_text()
    assert svg.lstrip().startswith("<?xml") or "<svg" in svg


# ----------------------------------------------------------------------------------------- real browser
def _browser():
    pw = pytest.importorskip("playwright.sync_api")
    if not Path(CHROMIUM).exists():
        pytest.skip("Chromium not installed")
    return pw


@pytest.fixture
def served(tmp_path):
    site_build.build(tmp_path / "public", preview=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path / "public"))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_guest_reviews_then_comes_back_to_pay(served):
    pw = _browser()
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        ctx.route("https://g.page/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<p>Google review form</p>"))
        ctx.route("https://paypal.me/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<p>PayPal</p>"))
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(served + "/r/demo-cafe/")
        assert page.locator("h1").inner_text() == "Café Luise (Demo)"
        assert page.locator("#pay").is_visible() and page.locator("#review").is_visible()
        assert not page.locator(".hint").is_visible()
        with ctx.expect_page() as review_tab:
            page.locator("#review").click()
        tab = review_tab.value
        tab.wait_for_load_state()
        assert tab.url == "https://g.page/r/CdemoExampleReviewId/review"      # Google's own review form, untouched
        tab.close()
        page.bring_to_front()
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_selector("html.returned")
        assert page.locator(".hint").is_visible()                            # "Thank you! You can pay here now."
        assert page.evaluate("document.activeElement.id") == "pay"
        page.locator("#pay").click()
        page.wait_for_url("https://paypal.me/demo-cafe-luise")               # exactly the configured payment link
        assert errors == []
        browser.close()


def test_preview_page_shows_the_name_as_text_only(served):
    pw = _browser()
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page()
        dialogs = []
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        page.goto(served + "/demo/?n=" + "%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E%20Caf%C3%A9")
        page.wait_for_timeout(300)
        assert page.locator("h1").inner_text() == "<img src=x onerror=alert(1)> Café"
        assert page.locator("main img").count() == 0 and dialogs == []
        href = page.locator("#whatsapp").get_attribute("href")
        assert href.startswith("https://wa.me/") and "text=" in href and "Caf%C3%A9" in href
        page.goto(served + "/demo/?n=Joe%27s%20Diner&lang=en")              # the link in an English e-mail
        page.wait_for_timeout(300)
        assert page.url.endswith("/demo/?n=Joe%27s%20Diner&lang=en")        # the default page is English: stays
        assert page.locator("h1").inner_text() == "Joe's Diner" and "Preview" in page.locator(".demo-banner").inner_text()
        page.goto(served + "/demo/?n=Caf%C3%A9&lang=de")                    # a German letter's link
        page.wait_for_url("**/demo/de.html?n=Caf%C3%A9&lang=de")
        assert page.locator("h1").inner_text() == "Café" and "Vorschau" in page.locator(".demo-banner").inner_text()
        browser.close()
