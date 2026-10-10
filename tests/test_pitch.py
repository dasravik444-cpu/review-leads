"""The sales PDF's content (marketing/build_pitch.py): what it promises must be deliverable from India - a QR code the
business prints itself, review tracking, review requests to its own customers - and its facts must carry a source."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("segno")


def pitch():
    spec = importlib.util.spec_from_file_location("build_pitch", ROOT / "marketing" / "build_pitch.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_pitch"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_pdf_sells_a_qr_code_in_two_plans_and_highlights_ranking_and_trust():
    d = json.loads((ROOT / "marketing" / "pitch.json").read_text(encoding="utf-8"))
    html = pitch().build_html(d)
    text = html.replace("&#x27;", "'")
    assert d["brand"] == "Aurenflow" and "Auren<i>flow</i>" in text
    for promise in ("Starter", "$100", "Pro", "$200", "Your QR code", "Review tracking", "WhatsApp and e-mail review requests"):
        assert promise in text, promise
    for gone in ("acrylic", "NFC", "Pay the bill", "$99", "$149", "$199", "Apple Pay", "delivered", "GuestEcho", "Qrated",
                 "$75", "$599"):
        assert gone not in text, gone                                        # nothing is shipped, no payment step
    assert "More reviews, higher on Google" in text and "More reviews, more trust" in text
    assert "“Google review count and review score factor into local search ranking.”" in text
    assert "won't use a business with fewer than 20 reviews" in text and text.count("Review Survey 2026") >= 2
    assert "Leading review platforms start at $299–$399 a month." in text     # Birdeye $299, Podium $399 (CostBench)


def test_the_owners_copy_carries_a_whatsapp_code_and_the_public_one_an_e_mail_code():
    p = pitch()
    d = json.loads((ROOT / "marketing" / "pitch.json").read_text(encoding="utf-8"))
    page = lambda details: p.build_html(details).split("</style>", 1)[1]   # noqa: E731 - the page, not the font data
    assert "Scan to e-mail us" in page(d) and "+91" not in page(d)
    mine = page({**d, "phone": "+91 62908 43509"})
    assert "Scan to chat on WhatsApp" in mine and "+91 62908 43509" in mine
