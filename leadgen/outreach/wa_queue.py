"""The WhatsApp Queue tab, worked through from the tablet (the  whatsapp  command, android/whatsapp.sh): the next
message to send, and its result written back to the tab.

Nothing here sends a message. The owner presses Send in WhatsApp Business for each one: WhatsApp's terms forbid
automated and bulk messages and ban numbers that send them, and Meta's own API delivers no marketing messages to
US numbers (leadgen/outreach/whatsapp.py, docs/WHATSAPP.md). The robot fills the queue (a batch a day, more as the
number gets older); its next run reads the results like any typed into the Sheet by hand.
"""
from __future__ import annotations

import re
from urllib.parse import quote, unquote

from ..sheets import _tab_ref, col_letter
from .sheet import TABS
from .whatsapp import RESULTS

COLS = TABS["whatsapp"]
# The price line of messages queued before 15 October 2026 (no prices since then: the product only).
OLD_PRICE_LINE = re.compile(r"It's a one-time price from [₹$][\d,]+, no monthly fees\.")


def without_old_price(link: str, offer: str) -> str:
    """A message queued before the prices came out: the same message with today's line instead of the price."""
    head, sep, query = link.partition("?text=")
    if not sep or not offer:
        return link
    text = unquote(query)
    new = OLD_PRICE_LINE.sub(offer.replace("\\", "\\\\"), text)
    return link if new == text else f"{head}?text={quote(new, safe='')}"


def _row(values: list) -> dict:
    cells = [str(x).strip() for x in values] + [""] * (len(COLS) - len(values))
    return dict(zip(COLS, cells))


def pending(client, tab: str, offer: str = "") -> list[dict]:
    """Queue rows without a Result yet, in queue order: the oldest first, also those of days not sent (offer: the line
    that replaces an old price line in the message)."""
    rows = client.get_values(f"{_tab_ref(tab)}!A2:{col_letter(len(COLS) - 1)}")
    out = []
    for i, values in enumerate(rows):
        r = _row(values)
        if r["Open Chat"].startswith("https://wa.me/") and r["Number"] and not r["Result"]:
            out.append({"row": i + 2, "date": r["Date"], "lead_id": r["Lead ID"], "business": r["Business"],
                        "number": r["Number"], "why": r["Why"], "link": without_old_price(r["Open Chat"], offer),
                        "key": r["Key"]})
    return out


def mark(client, tab: str, row: int, key: str, number: str, result: str) -> int:
    """Write a row's Result. The row is checked by its Key and Number (and found again if rows moved, e.g. sorted by
    hand). Returns the row written, or 0 when that message is no longer in the tab."""
    if result not in RESULTS:
        raise ValueError(f"result must be one of: {', '.join(RESULTS)}")
    rows = client.get_values(f"{_tab_ref(tab)}!A2:{col_letter(len(COLS) - 1)}")
    found = [(i + 2, _row(v)) for i, v in enumerate(rows)]
    same = lambda r: r["Key"] == key and r["Number"] == number  # noqa: E731
    target = next((n for n, r in found if n == row and same(r)), 0) or \
        next((n for n, r in found if same(r) and not r["Result"]), 0)
    if target:
        client.update_values(f"{_tab_ref(tab)}!{col_letter(COLS.index('Result'))}{target}", [[result]])
    return target
