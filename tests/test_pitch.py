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


# No price, fee or charge anywhere (15 October 2026): neither ours nor other platforms'. The PDF talks about the product.
PRICE_WORDS = ("₹", "$", "rupee", "price", "one-time", "fee", "fees", "charge", "charges", "subscription", "a month.",
               "3,000", "8,000", "10,000")


def has_word(text: str, word: str) -> bool:
    import re

    if not word[0].isalnum():                    # a currency sign: anywhere ("₹3,000", "$100")
        return word in text
    return re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) is not None     # a word ("fee", not "coffee")


def visible(html: str) -> str:
    """The page's words as a reader sees them (no styles, no markup)."""
    import re

    page = html.split("</style>", 1)[1]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)).replace("&#x27;", "'").replace("&amp;", "&")


def test_the_pdf_sells_a_qr_code_in_two_plans_and_highlights_ranking_and_trust():
    d = json.loads((ROOT / "marketing" / "pitch.json").read_text(encoding="utf-8"))
    html = pitch().build_html(d)
    text = html.replace("&#x27;", "'")
    assert d["brand"] == "Aurenflow" and "Auren<i>flow</i>" in text
    for promise in ("What you get", "Starter", "Pro", "Your QR code", "Review tracking", "WhatsApp and e-mail review requests"):
        assert promise in text, promise
    for gone in ("acrylic", "NFC", "Pay the bill", "$99", "$149", "$199", "Apple Pay", "delivered", "GuestEcho", "Qrated",
                 "$75", "$599"):
        assert gone not in text, gone                                        # nothing is shipped, no payment step
    assert "More reviews, higher on Google" in text and "More reviews, more trust" in text
    assert "“Google review count and review score factor into local search ranking.”" in text
    assert "won't use a business with fewer than 20 reviews" in text and text.count("Review Survey 2026") >= 2
    words = visible(html).lower()
    for price in PRICE_WORDS:
        assert not has_word(words, price), price                                     # no prices: only the product


def test_the_owners_copy_carries_a_whatsapp_code_and_the_public_one_an_e_mail_code():
    p = pitch()
    d = json.loads((ROOT / "marketing" / "pitch.json").read_text(encoding="utf-8"))
    page = lambda details: p.build_html(details).split("</style>", 1)[1]   # noqa: E731 - the page, not the font data
    assert "Scan to e-mail us" in page(d) and "+91" not in page(d)
    mine = page({**d, "phone": "+91 90000 00000"})
    assert "Scan to chat on WhatsApp" in mine and "+91 90000 00000" in mine


def test_the_india_version_has_no_prices_and_has_the_monthly_review_report():
    p = pitch()
    d = json.loads((ROOT / "marketing" / "pitch.json").read_text(encoding="utf-8"))
    html = p.build_html({**d, **d["markets"]["in"]})
    page = html.split("</style>", 1)[1].replace("&#x27;", "'")
    words = visible(html).lower()
    for price in PRICE_WORDS:
        assert not has_word(words, price), price
    assert "We track your Google reviews, every month" in page
    for item in ("How many new reviews", "Your star rating", "What it brings you", "add us as a manager"):
        assert item in page, item
    assert "Reply “yes” to our message" in page
    assert "edition IN-" in html.split("<title>")[1].split("</title>")[0]      # the tablet never sends an old copy
    us = p.build_html(d).split("</style>", 1)[1]
    assert "We track your Google reviews, every month" not in us and "Reply “yes” to our e-mail" in us
    assert (ROOT / "marketing" / "pitch-in.pdf").is_file()       # the one e-mails attach until you import your copy
