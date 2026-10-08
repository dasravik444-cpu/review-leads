"""The sales PDF for businesses: two pages, US Letter.

    python marketing/build_pitch.py                      # -> marketing/pitch.pdf (details from marketing/pitch.json)
    python marketing/build_pitch.py --png                # also page images, to check the layout
    python marketing/build_pitch.py --phone "+1 ..."     # override a detail for one build

Drawn as an HTML page with inline SVG pictures (phones, stand, map) and printed to PDF by Chromium
(Playwright). Needs the Inter font installed for the intended look; any sans-serif works.
The brand, name and contact details come from marketing/pitch.json, so the PDF can be rebuilt in seconds
when they change.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from urllib.parse import quote

import segno

HERE = Path(__file__).resolve().parent
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/opt/pw-browsers/chromium")

NAVY, INK, MUTED, LINE, SOFT = "#13294B", "#0F1B2D", "#5B6676", "#E3E8EF", "#F5F7FA"
AMBER, AMBER_INK, GREEN, BLUE = "#F5A623", "#A85F00", "#138A52", "#1A73E8"


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


# ------------------------------------------------------------------ small drawing helpers
def qr_path(data: str, x: float, y: float, size: float, color: str = INK) -> str:
    """A real, scannable QR code drawn as one SVG path."""
    rows = [list(r) for r in segno.make(data, error="m").matrix]
    n = len(rows)
    m = size / n
    d = []
    for j, row in enumerate(rows):
        for i, v in enumerate(row):
            if v:
                d.append(f"M{x + i * m:.2f} {y + j * m:.2f}h{m:.2f}v{m:.2f}h-{m:.2f}z")
    return f'<path d="{"".join(d)}" fill="{color}"/>'


def star(cx: float, cy: float, r: float, fill: str = AMBER, stroke: str = "none") -> str:
    import math

    pts = []
    for k in range(10):
        rad = r if k % 2 == 0 else r * 0.45
        a = -math.pi / 2 + k * math.pi / 5
        pts.append(f"{cx + rad * math.cos(a):.2f},{cy + rad * math.sin(a):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{stroke}" stroke-width="1" stroke-linejoin="round"/>'


def stars(x: float, cy: float, r: float, n_full: float = 5, gap: float = 2, empty: str = "#D5DAE1") -> str:
    out = []
    for k in range(5):
        cx = x + r + k * (2 * r + gap)
        out.append(star(cx, cy, r, AMBER if k < n_full else empty))
    return "".join(out)


_PHONE_ID = [0]


def phone(screen: str, bg: str = "#fff", w: int = 200, h: int = 400, cls: str = "phone", dark_status: bool = True) -> str:
    _PHONE_ID[0] += 1
    cid = f"scr{_PHONE_ID[0]}"
    st = INK if dark_status else "#fff"
    return f"""<svg class="{cls}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img">
<defs><clipPath id="{cid}"><rect x="10" y="10" width="{w - 20}" height="{h - 20}" rx="24"/></clipPath></defs>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="33" fill="{INK}"/>
<rect x="10" y="10" width="{w - 20}" height="{h - 20}" rx="24" fill="{bg}"/>
<g clip-path="url(#{cid})">{screen}
<text x="30" y="31" font-size="9" font-weight="700" fill="{st}">9:41</text>
<rect x="{w - 46}" y="23" width="16" height="8" rx="2" fill="none" stroke="{st}" stroke-width="1"/>
<rect x="{w - 44.5}" y="24.5" width="11" height="5" rx="1" fill="{st}"/></g>
<rect x="{w / 2 - 25}" y="18" width="50" height="14" rx="7" fill="{INK}"/>
</svg>"""


def nfc_icon(x: float, y: float, s: float = 1.0, color: str = INK) -> str:
    return (f'<g transform="translate({x} {y}) scale({s})" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round">'
            '<path d="M0 -4 a5 5 0 0 1 0 8"/><path d="M3.5 -7.5 a9.5 9.5 0 0 1 0 15"/><path d="M7 -11 a14 14 0 0 1 0 22"/></g>')


def stand(x: float, y: float, s: float, business: str, qr_data: str) -> str:
    """An acrylic table stand with the QR card (drawn at 100x150 units, scaled by s)."""
    return f"""<g transform="translate({x} {y}) scale({s})">
<polygon points="6,150 94,150 100,160 0,160" fill="#C9D6E3"/>
<polygon points="14,6 86,6 94,150 6,150" fill="#E8F0F8" stroke="#B9C8D8" stroke-width="1.2"/>
<rect x="17" y="12" width="66" height="132" rx="4" fill="#fff"/>
<text x="50" y="25" text-anchor="middle" font-size="7.2" font-weight="800" fill="{INK}">{esc(business)}</text>
{qr_path(qr_data, 25, 30, 50)}
<g transform="translate(0 0)">{nfc_icon(40, 92, 0.55)}</g>
<text x="56" y="94.5" font-size="5.6" font-weight="700" fill="{INK}">Scan or tap</text>
<rect x="21" y="104" width="58" height="14" rx="7" fill="{NAVY}"/>
{star(29, 111, 3.4)}
<text x="53" y="113" text-anchor="middle" font-size="5.4" font-weight="700" fill="#fff">Google review</text>
<rect x="21" y="122" width="58" height="14" rx="7" fill="#fff" stroke="{NAVY}" stroke-width="0.9"/>
<text x="50" y="131" text-anchor="middle" font-size="5.6" font-weight="700" fill="{NAVY}">Pay the bill</text>
</g>"""


# ------------------------------------------------------------------ the three phones (scan, review, pay)
def phone_scan(business: str, qr_data: str) -> str:
    s = f"""<defs><linearGradient id="cam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3B4658"/>
<stop offset="1" stop-color="#151C29"/></linearGradient>
<linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#A47148"/><stop offset="1" stop-color="#6E4528"/></linearGradient></defs>
<rect x="0" y="0" width="200" height="400" fill="url(#cam)"/>
<polygon points="0,282 200,268 200,400 0,400" fill="url(#wood)"/>
{stand(48, 112, 1.04, business, qr_data)}
<g fill="none" stroke="{AMBER}" stroke-width="3" stroke-linecap="round">
<path d="M66 136 v-12 h12"/><path d="M122 124 h12 v12"/><path d="M134 186 v12 h-12"/><path d="M78 198 h-12 v-12"/></g>
<rect x="22" y="332" width="156" height="34" rx="17" fill="{AMBER}"/>
<text x="94" y="353" text-anchor="middle" font-size="10" font-weight="700" fill="{INK}">Open {esc(business)}</text>
<path d="M150 344 l5 5 -5 5" fill="none" stroke="{INK}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>"""
    return phone(s, bg="#151C29", dark_status=False)


def phone_review(business: str) -> str:
    s = f"""<path d="M27 56 l8 8 M35 56 l-8 8" stroke="{MUTED}" stroke-width="1.6" stroke-linecap="round"/>
<text x="100" y="62" text-anchor="middle" font-size="12" font-weight="800" fill="{INK}">{esc(business)}</text>
<text x="100" y="75" text-anchor="middle" font-size="8" fill="{MUTED}">Google review</text>
<rect x="10" y="86" width="180" height="1" fill="{LINE}"/>
<circle cx="36" cy="110" r="12" fill="#7E57C2"/><text x="36" y="114" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">S</text>
<text x="55" y="107" font-size="9.5" font-weight="700" fill="{INK}">Sarah M.</text>
<text x="55" y="119" font-size="7.5" fill="{MUTED}">Posting publicly</text>
{stars(33, 152, 12.5, gap=2.5)}
<text x="100" y="180" text-anchor="middle" font-size="8" fill="{MUTED}">Tap the stars, add a line if you like</text>
<rect x="22" y="190" width="156" height="78" rx="8" fill="#fff" stroke="#C7CDD4"/>
<text x="31" y="208" font-size="9.5" fill="{INK}">Great tacos and super</text>
<text x="31" y="221" font-size="9.5" fill="{INK}">friendly staff. We'll be</text>
<text x="31" y="234" font-size="9.5" fill="{INK}">back!<tspan fill="{BLUE}" font-weight="700">|</tspan></text>
<g transform="translate(30 286)"><rect x="0" y="-9" width="14" height="11" rx="2" fill="none" stroke="{BLUE}" stroke-width="1.3"/>
<circle cx="7" cy="-3.5" r="2.6" fill="none" stroke="{BLUE}" stroke-width="1.3"/>
<text x="20" y="0" font-size="8.5" font-weight="600" fill="{BLUE}">Add photos (optional)</text></g>
<rect x="112" y="330" width="66" height="30" rx="15" fill="{BLUE}"/>
<text x="145" y="349" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">Post</text>
<text x="40" y="349" font-size="10" font-weight="600" fill="{MUTED}">Cancel</text>"""
    return phone(s, bg="#fff")


def phone_pay(business: str) -> str:
    chips = []
    for k, (lbl, sel) in enumerate((("15%", False), ("18%", True), ("20%", False))):
        cx = 30 + k * 48
        chips.append(f'<rect x="{cx}" y="178" width="42" height="20" rx="10" fill="{NAVY if sel else "#fff"}" '
                     f'stroke="{NAVY}" stroke-width="1"/><text x="{cx + 21}" y="191.5" text-anchor="middle" font-size="9" '
                     f'font-weight="700" fill="{"#fff" if sel else NAVY}">{lbl}</text>')
    s = f"""<text x="100" y="62" text-anchor="middle" font-size="12" font-weight="800" fill="{INK}">{esc(business)}</text>
<text x="100" y="75" text-anchor="middle" font-size="8" fill="{MUTED}">Table 7 · Check #1042</text>
<rect x="22" y="90" width="156" height="120" rx="14" fill="#fff" stroke="{LINE}"/>
<text x="100" y="114" text-anchor="middle" font-size="8.5" fill="{MUTED}">Amount due</text>
<text x="100" y="146" text-anchor="middle" font-size="27" font-weight="800" fill="{INK}">$42.80</text>
<text x="100" y="170" text-anchor="middle" font-size="8" fill="{MUTED}">Add a tip</text>
{"".join(chips)}
<text x="30" y="232" font-size="10" font-weight="700" fill="{INK}">Total</text>
<text x="170" y="232" text-anchor="end" font-size="10" font-weight="700" fill="{INK}">$50.50</text>
<rect x="22" y="250" width="156" height="34" rx="10" fill="#000"/>
<text x="100" y="271" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">Apple Pay</text>
<rect x="22" y="292" width="156" height="34" rx="10" fill="#fff" stroke="#1F1F1F" stroke-width="1"/>
<text x="100" y="313" text-anchor="middle" font-size="11" font-weight="700" fill="#1F1F1F">Google Pay</text>
<text x="100" y="350" text-anchor="middle" font-size="9" font-weight="600" fill="{BLUE}">Pay by card</text>"""
    return phone(s, bg="#F4F6FA")


def arrow_svg() -> str:
    return (f'<svg class="arrow" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg"><circle cx="22" cy="22" r="20" fill="{AMBER}"/>'
            f'<path d="M14 22 h15 M23 15 l7 7 -7 7" fill="none" stroke="{INK}" stroke-width="3.2" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg>')


# ------------------------------------------------------------------ page-1 hero and page-2 pictures
def hero_visual(business: str, qr_data: str) -> str:
    return f"""<svg class="hero-visual" viewBox="0 0 300 280" xmlns="http://www.w3.org/2000/svg" role="img">
<circle cx="150" cy="140" r="128" fill="#FFF4DF"/>
<ellipse cx="150" cy="248" rx="96" ry="10" fill="#E9DCC3"/>
{stand(80, 52, 1.32, business, qr_data)}
<g transform="translate(186 34)"><rect x="0" y="0" width="108" height="50" rx="12" fill="#fff" stroke="{LINE}"/>
<text x="12" y="20" font-size="9" font-weight="800" fill="{INK}">{esc(business)}</text>
<text x="12" y="38" font-size="12" font-weight="800" fill="{INK}">4.8</text>{stars(36, 34, 5.2, gap=1.2)}
<text x="12" y="47" font-size="6.5" fill="{MUTED}">312 Google reviews</text></g>
<g transform="translate(6 168)"><rect x="0" y="0" width="98" height="40" rx="12" fill="{NAVY}"/>
{nfc_icon(16, 20, 0.7, "#fff")}<text x="30" y="17" font-size="8.5" font-weight="700" fill="#fff">No app needed</text>
<text x="30" y="30" font-size="7.5" fill="#C9D3E3">QR + tap (NFC)</text></g>
</svg>"""


def maps_visual() -> str:
    rows = [("Maple Street Café", 4.8, 5, "312", True), ("Bean There", 4.3, 4, "41", False), ("Daily Grind", 4.1, 4, "18", False)]
    out = []
    for k, (name, rating, full, n, me) in enumerate(rows):
        y = 150 + k * 46
        if me:
            out.append(f'<rect x="12" y="{y - 2}" width="256" height="42" rx="8" fill="#FFF4DF"/>'
                       f'<rect x="12" y="{y - 2}" width="4" height="42" rx="2" fill="{AMBER}"/>')
        out.append(f'<text x="26" y="{y + 15}" font-size="11.5" font-weight="800" fill="{INK}">{name}</text>'
                   f'<text x="26" y="{y + 31}" font-size="10" font-weight="700" fill="{INK}">{rating}</text>'
                   f'{stars(46, y + 27.5, 5.2, n_full=full, gap=1)}'
                   f'<text x="110" y="{y + 31}" font-size="9" fill="{MUTED}">({n} reviews)</text>')
        if me:
            out.append(f'<rect x="196" y="{y + 9}" width="62" height="18" rx="9" fill="{NAVY}"/>'
                       f'<text x="227" y="{y + 21.5}" text-anchor="middle" font-size="8" font-weight="700" fill="#fff">Picked first</text>')
    return f"""<svg class="maps" viewBox="0 0 280 292" xmlns="http://www.w3.org/2000/svg" role="img">
<rect x="1" y="1" width="278" height="290" rx="16" fill="#fff" stroke="{LINE}"/>
<rect x="12" y="12" width="256" height="30" rx="15" fill="{SOFT}" stroke="{LINE}"/>
<circle cx="30" cy="26" r="5" fill="none" stroke="{MUTED}" stroke-width="1.6"/><path d="M34 30 l4 4" stroke="{MUTED}" stroke-width="1.6"/>
<text x="44" y="31" font-size="11" fill="{INK}">coffee near me</text>
<rect x="12" y="50" width="256" height="90" rx="10" fill="#E7EFE3"/>
<path d="M12 104 C80 92 120 118 268 96" stroke="#fff" stroke-width="7" fill="none"/>
<path d="M150 50 C140 80 168 110 156 140" stroke="#fff" stroke-width="5" fill="none"/>
<path d="M12 70 H268" stroke="#F6F8F4" stroke-width="3"/>
<rect x="196" y="56" width="62" height="26" rx="5" fill="#CFE3F3"/>
<g transform="translate(118 64)"><path d="M0 18 C-12 6 -9 -8 0 -8 C9 -8 12 6 0 18z" fill="{AMBER}" stroke="{INK}" stroke-width="1"/>
{star(0, -1, 4.2, "#fff")}</g>
<g transform="translate(62 96)"><path d="M0 14 C-9 5 -7 -6 0 -6 C7 -6 9 5 0 14z" fill="#9AA6B5"/></g>
<g transform="translate(212 108)"><path d="M0 14 C-9 5 -7 -6 0 -6 C7 -6 9 5 0 14z" fill="#9AA6B5"/></g>
{"".join(out)}
</svg>"""


def chat_phone(business: str) -> str:
    s = f"""<rect x="0" y="0" width="200" height="86" fill="#0F6E58"/>
<circle cx="40" cy="62" r="13" fill="#fff"/>{star(40, 62, 7)}
<text x="60" y="59" font-size="11" font-weight="700" fill="#fff">{esc(business)}</text>
<text x="60" y="72" font-size="7.5" fill="#CDE8DF">Business account</text>
<rect x="0" y="86" width="200" height="314" fill="#EFE7DC"/>
<rect x="64" y="98" width="72" height="16" rx="8" fill="#DCE7F2"/>
<text x="100" y="109" text-anchor="middle" font-size="7" font-weight="600" fill="{MUTED}">TODAY</text>
<rect x="18" y="122" width="164" height="132" rx="10" fill="#fff"/>
<text font-size="9.2" fill="{INK}"><tspan x="27" y="140">Hi Sarah! Thanks for visiting</tspan>
<tspan x="27" y="153">{esc(business)} tonight.</tspan>
<tspan x="27" y="171">If you have a moment, would you</tspan><tspan x="27" y="184">share your experience on Google?</tspan>
<tspan x="27" y="197">It only takes a few seconds:</tspan></text>
<text x="27" y="214" font-size="9.2" font-weight="700" fill="{BLUE}">g.page/r/joes-diner/review</text>
<text x="27" y="234" font-size="7.5" fill="{MUTED}">Reply STOP to opt out.</text>
<text x="172" y="248" text-anchor="end" font-size="7" fill="{MUTED}">7:52 PM</text>
<rect x="18" y="266" width="164" height="54" rx="10" fill="#fff" opacity=".92"/>
<text font-size="8.6" fill="{MUTED}"><tspan x="27" y="283">Day 2: Hi Sarah, just a friendly</tspan>
<tspan x="27" y="296">reminder in case you missed it.</tspan></text>
<text x="172" y="313" text-anchor="end" font-size="7" fill="{MUTED}">reminder</text>
<rect x="18" y="340" width="164" height="30" rx="15" fill="#fff"/>
<text x="32" y="359" font-size="8.5" fill="#9AA3AE">Message</text>"""
    return phone(s, bg="#EFE7DC", cls="phone chat", dark_status=False)


def customer_list() -> str:
    rows = [("Sarah M.", "+1 (512) •••-0142", "7:40 pm"), ("Daniel K.", "daniel.k@•••.com", "8:05 pm"),
            ("Priya S.", "+1 (512) •••-8810", "8:30 pm"), ("Tom R.", "+1 (737) •••-2291", "9:10 pm")]
    out = []
    for k, (n, c, t) in enumerate(rows):
        y = 64 + k * 30
        out.append(f'<rect x="10" y="{y}" width="200" height="1" fill="{LINE}"/>'
                   f'<text x="16" y="{y + 19}" font-size="9.2" font-weight="700" fill="{INK}">{n}</text>'
                   f'<text x="70" y="{y + 19}" font-size="8.4" fill="{MUTED}">{c}</text>'
                   f'<text x="204" y="{y + 19}" text-anchor="end" font-size="8.2" fill="{MUTED}">{t}</text>')
    return f"""<svg class="list" viewBox="0 0 220 196" xmlns="http://www.w3.org/2000/svg" role="img">
<rect x="1" y="1" width="218" height="194" rx="14" fill="#fff" stroke="{LINE}"/>
<text x="16" y="28" font-size="11.5" font-weight="800" fill="{INK}">Your customer list</text>
<text x="16" y="44" font-size="8.2" fill="{MUTED}">Bookings, loyalty sign-ups, receipts…</text>
<text x="16" y="60" font-size="7.2" font-weight="700" fill="{MUTED}" letter-spacing=".6">NAME        PHONE OR E-MAIL</text>
{"".join(out)}
<rect x="10" y="184" width="200" height="1" fill="{LINE}"/>
</svg>"""


def icon(kind: str) -> str:
    body = {
        "rank": f'<path d="M12 26 l6 -7 5 4 7 -9" fill="none" stroke="{INK}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<path d="M25 14 h5 v5" fill="none" stroke="{INK}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
        "click": star(21, 21, 9.5, INK),
        "easy": f'<path d="M13 21 l5 5 11 -11" fill="none" stroke="{INK}" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>',
    }[kind]
    return f'<svg class="icon" viewBox="0 0 42 42" xmlns="http://www.w3.org/2000/svg"><circle cx="21" cy="21" r="20" fill="#FFE7B8"/>{body}</svg>'


def logo(brand: str, size: int = 34) -> str:
    return (f'<div class="logo"><svg viewBox="0 0 40 40" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="40" height="40" rx="11" fill="{NAVY}"/>'
            f'<path d="M9 12 a4 4 0 0 1 4 -4 h14 a4 4 0 0 1 4 4 v11 a4 4 0 0 1 -4 4 h-8 l-6 5 v-5 a4 4 0 0 1 -4 -4z" fill="#fff"/>'
            f'{star(20, 17.5, 6.2)}</svg><span>{esc(brand)}</span></div>')


# ------------------------------------------------------------------ the page
CSS = f"""
@page {{ size: 8.5in 11in; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: #fff; }}
body {{ font-family: PitchInter, Inter, "Helvetica Neue", Arial, sans-serif; color: {INK}; font-size: 12.5px; line-height: 1.45;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
svg text {{ font-family: PitchInter, Inter, "Helvetica Neue", Arial, sans-serif; }}
.page {{ width: 8.5in; height: 11in; position: relative; overflow: hidden; padding: 30px 44px 0; page-break-after: always; }}
.page:last-child {{ page-break-after: auto; }}
.top {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 14px; border-bottom: 1px solid {LINE}; }}
.logo {{ display: flex; align-items: center; gap: 9px; }}
.logo span {{ font-family: PitchInter, Inter, sans-serif; font-weight: 800; font-size: 21px; letter-spacing: -.02em; color: {NAVY}; }}
.top .tag {{ font-size: 11px; color: {MUTED}; text-align: right; line-height: 1.35; }}
.top .tag b {{ color: {INK}; }}
.hero {{ display: grid; grid-template-columns: 1fr 236px; gap: 16px; align-items: center; padding: 16px 0 6px; }}
.eyebrow {{ display: inline-block; font-size: 9px; font-weight: 800; letter-spacing: .08em; color: {AMBER_INK}; background: #FFF4DF;
           padding: 5px 10px; border-radius: 99px; margin-bottom: 10px; }}
h1 {{ font-family: PitchInter, Inter, sans-serif; font-size: 34px; line-height: 1.06; letter-spacing: -.025em; font-weight: 800; color: {INK}; }}
h1 em {{ font-style: normal; color: {NAVY}; background: linear-gradient(transparent 62%, #FFD98A 62%); }}
.lead {{ font-size: 12.8px; color: #334155; margin-top: 10px; max-width: 480px; }}
.lead b {{ color: {INK}; }}
.hero-visual {{ width: 236px; height: 220px; }}
h2 {{ font-family: PitchInter, Inter, sans-serif; font-size: 21px; letter-spacing: -.015em; font-weight: 800; color: {INK}; }}
.sub {{ color: {MUTED}; font-size: 12px; margin-top: 2px; }}
.how {{ margin-top: 6px; background: {SOFT}; border-radius: 20px; padding: 14px 18px 14px; }}
.how-head {{ display: flex; justify-content: space-between; align-items: baseline; }}
.flow {{ display: grid; grid-template-columns: 1fr 40px 1fr 40px 1fr; align-items: start; margin-top: 10px; }}
.step {{ text-align: center; }}
.phone {{ width: 140px; height: 280px; display: block; margin: 0 auto; filter: drop-shadow(0 8px 14px rgba(15,27,45,.18)); }}
.arrow {{ width: 34px; height: 34px; margin-top: 122px; }}
.num {{ display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%;
       background: {NAVY}; color: #fff; font-weight: 800; font-size: 11.5px; margin-right: 6px; }}
.step h3 {{ font-size: 13.5px; font-weight: 800; margin-top: 9px; display: flex; align-items: center; justify-content: center; }}
.step p {{ font-size: 10.8px; color: #475569; margin: 3px auto 0; max-width: 205px; line-height: 1.38; }}
.fair {{ margin-top: 10px; display: flex; gap: 9px; align-items: center; background: #fff; border: 1px solid {LINE}; border-radius: 12px;
        padding: 7px 12px; font-size: 10.8px; color: #334155; }}
.fair b {{ color: {INK}; }}
.check {{ flex: none; width: 20px; height: 20px; border-radius: 50%; background: {GREEN}; color: #fff; display: flex;
         align-items: center; justify-content: center; font-weight: 900; font-size: 12px; }}
.benefits {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px; }}
.benefit {{ border: 1px solid {LINE}; border-radius: 14px; padding: 10px 13px; }}
.benefit .icon {{ width: 28px; height: 28px; }}
.benefit h4 {{ font-size: 13.2px; font-weight: 800; margin-top: 6px; }}
.benefit p {{ font-size: 10.6px; color: #475569; margin-top: 2px; line-height: 1.38; }}
.foot {{ position: absolute; left: 44px; right: 44px; bottom: 14px; display: flex; justify-content: space-between; gap: 16px; font-size: 8.2px; color: #8A94A3; }}
.foot span:last-child {{ white-space: nowrap; }}
/* page 2 */
.sec {{ margin-top: 12px; }}
.why {{ display: grid; grid-template-columns: 218px 1fr; gap: 16px; margin-top: 8px; align-items: start; }}
.maps {{ width: 218px; height: 227px; }}
.facts {{ display: grid; gap: 8px; }}
.fact {{ border: 1px solid {LINE}; border-radius: 14px; padding: 9px 13px; display: grid; grid-template-columns: 76px 1fr; gap: 8px; align-items: center; }}
.fact .big {{ font-family: PitchInter, Inter, sans-serif; font-weight: 800; font-size: 24px; letter-spacing: -.02em; color: {NAVY}; line-height: 1; }}
.fact p {{ font-size: 10.9px; color: #334155; line-height: 1.38; }}
.fact p b {{ color: {INK}; }}
.fact cite {{ display: block; font-style: normal; font-size: 8.6px; color: #8A94A3; margin-top: 2px; }}
.quote {{ background: {NAVY}; color: #fff; border: 0; grid-template-columns: 1fr; }}
.quote p {{ color: #fff; font-size: 12.4px; font-weight: 700; line-height: 1.34; }}
.quote cite {{ color: #B8C4D6; }}
.guests {{ display: grid; grid-template-columns: 184px 34px 108px 34px 1fr; align-items: center; margin-top: 8px; }}
.list {{ width: 184px; height: 164px; }}
.chat {{ width: 108px; height: 216px; }}
.guests .arrow {{ width: 26px; height: 26px; margin: 0 auto; }}
.timeline {{ list-style: none; position: relative; padding-left: 4px; }}
.timeline li {{ position: relative; padding: 0 0 7px 25px; font-size: 10.4px; color: #475569; line-height: 1.32; }}
.timeline li b {{ display: block; color: {INK}; font-size: 11.4px; }}
.timeline li::before {{ content: ""; position: absolute; left: 3px; top: 3px; width: 12px; height: 12px; border-radius: 50%;
                       background: #fff; border: 3px solid {AMBER}; }}
.timeline li::after {{ content: ""; position: absolute; left: 9px; top: 18px; bottom: -1px; width: 2px; background: #F3D9A6; }}
.timeline li:last-child::after {{ display: none; }}
.timeline li.stop::before {{ border-color: {GREEN}; }}
.nowrap {{ white-space: nowrap; }}
.row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }}
.small-note {{ font-size: 10.2px; color: {MUTED}; margin-top: 5px; }}
.prices {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }}
.price {{ border: 1px solid {LINE}; border-radius: 14px; padding: 9px 12px 10px; position: relative; }}
.price.pop {{ border: 2px solid {AMBER}; background: #FFFCF5; }}
.price .badge {{ position: absolute; top: -10px; right: 12px; background: {AMBER}; color: {INK}; font-size: 8.8px; font-weight: 800;
                letter-spacing: .06em; padding: 3px 8px; border-radius: 99px; }}
.price h4 {{ font-size: 13px; font-weight: 800; }}
.price .amt {{ font-family: PitchInter, Inter, sans-serif; font-size: 24px; font-weight: 800; letter-spacing: -.02em; color: {NAVY}; margin-top: 1px; }}
.price .amt small {{ font-family: PitchInter, Inter, sans-serif; font-size: 10.5px; font-weight: 600; color: {MUTED}; letter-spacing: 0; margin-left: 4px; }}
.price ul {{ list-style: none; margin-top: 3px; }}
.price li {{ font-size: 10.4px; color: #334155; padding-left: 15px; position: relative; line-height: 1.34; margin-top: 2px; }}
.price li::before {{ content: ""; position: absolute; left: 0; top: 2px; width: 11px; height: 11px; background: url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'><path d='M4 10.5 l4 4 8 -9' fill='none' stroke='%23138A52' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/></svg>\") no-repeat center / contain; }}
.cta {{ margin-top: 12px; background: {NAVY}; border-radius: 18px; color: #fff; padding: 14px 20px; display: grid;
       grid-template-columns: 1fr 100px; gap: 18px; align-items: center; }}
.cta h2 {{ color: #fff; font-size: 18.5px; }}
.cta p {{ color: #D5DDEA; font-size: 11.4px; margin-top: 3px; }}
.contact {{ display: flex; flex-wrap: wrap; gap: 4px 18px; margin-top: 9px; font-size: 12px; }}
.contact b {{ color: {AMBER}; font-weight: 800; margin-right: 4px; }}
.contact span {{ color: #fff; }}
.qr {{ background: #fff; border-radius: 12px; padding: 8px; text-align: center; }}
.qr svg {{ width: 84px; height: 84px; display: block; margin: 0 auto; }}
.qr small {{ display: block; color: {INK}; font-size: 8.4px; font-weight: 700; margin-top: 3px; }}
"""


def font_faces() -> str:
    """Inter as embedded web fonts (SIL OFL, marketing/fonts): Chromium writes them into the PDF as real TrueType fonts.
    (Installed OpenType/CFF fonts end up as blurrier Type 3 fonts.)"""
    import base64

    out = []
    for f in sorted((HERE / "fonts").glob("inter-latin-*-normal.woff2")):
        weight = f.name.split("-")[2]
        data = base64.b64encode(f.read_bytes()).decode("ascii")
        out.append(f"@font-face {{ font-family: PitchInter; font-weight: {weight}; font-style: normal; "
                   f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}")
    return "\n".join(out)


def build_html(d: dict) -> str:
    brand, business = d["brand"], d.get("example_business") or "Joe's Diner"
    name, email, phone_no = d.get("name", ""), d.get("email", ""), d.get("phone", "")
    qr_demo = d.get("qr_demo") or "https://example.com/"
    # The code on page 2 opens an e-mail to us (or a WhatsApp chat when a phone number is set).
    wa = "".join(ch for ch in phone_no if ch.isdigit())
    if wa:
        reply_link = f"https://wa.me/{wa}?text={quote('Hi! I would like a free preview of my review page.')}"
        qr_label = "Scan to chat on WhatsApp"
    else:
        reply_link = f"mailto:{email}?subject={quote('Free preview')}"
        qr_label = "Scan to e-mail us"
    contact = [f"<div><b>E-mail</b><span>{esc(email)}</span></div>"] if email else []
    if phone_no:
        contact.append(f"<div><b>WhatsApp / phone</b><span>{esc(phone_no)}</span></div>")
    if d.get("website"):
        contact.append(f"<div><b>Web</b><span>{esc(d['website'])}</span></div>")
    signer = f"{esc(name)} · {esc(brand)}" if name else esc(brand)
    year = d.get("year", "2026")
    disclaimer = (f"Google and Google Maps are trademarks of Google LLC. {esc(brand)} is independent and not affiliated with "
                  "Google. Example business for illustration.")
    top = (f'<div class="top">{logo(brand)}<div class="tag"><b>Google reviews for walk-in businesses</b><br>'
           'restaurants · cafés · bars · salons · gyms · clinics · shops</div></div>')
    page1 = f"""<section class="page">
{top}
<div class="hero"><div>
<span class="eyebrow">MORE GOOGLE REVIEWS · HIGHER ON GOOGLE MAPS · MORE CUSTOMERS</span>
<h1>Turn happy customers into <em>Google reviews</em>, in one tap.</h1>
<p class="lead">Most happy customers never leave a review. Not because they didn't like you: nobody asked at the right
moment, and finding your Google page takes too many steps. <b>{esc(brand)}'s QR + tap stand on your tables and counter
opens your Google review page instantly</b>, right when guests are about to pay.</p>
</div>{hero_visual(business, qr_demo)}</div>

<div class="how">
<div class="how-head"><h2>How it works</h2><div class="sub">Three taps. No app. About 30 seconds.</div></div>
<div class="flow">
<div class="step">{phone_scan(business, qr_demo)}<h3><span class="num">1</span>Scan or tap</h3>
<p>Guests point their camera at the QR code or tap their phone on the stand. Nothing to install.</p></div>
{arrow_svg()}
<div class="step">{phone_review(business)}<h3><span class="num">2</span>Review on Google</h3>
<p>Your Google review page opens instantly. Stars and a one-line review take just seconds.</p></div>
{arrow_svg()}
<div class="step">{phone_pay(business)}<h3><span class="num">3</span>Pay the bill</h3>
<p>One more tap opens your usual payment link (Square, Toast, Stripe, PayPal…). Your money goes straight to you.</p></div>
</div>
<div class="fair"><span class="check"><svg viewBox="0 0 20 20" width="12" height="12"><path d="M4 10.5 l4 4 8 -9" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></span><div><b>Always the guest's choice:</b> they can skip the review and go straight to paying.
Every guest is asked the same way, exactly as Google's review rules require. No fake or paid reviews, ever.</div></div>
</div>

<div class="benefits">
<div class="benefit">{icon("rank")}<h4>Climb Google Maps</h4><p>Google counts how many reviews you have and your rating
when it ranks local results. More reviews help you show up for “near me” searches.</p></div>
<div class="benefit">{icon("click")}<h4>Win the click</h4><p>People pick the place with the better rating and the newest
reviews. A steady flow of fresh reviews keeps that place you.</p></div>
<div class="benefit">{icon("easy")}<h4>Zero work for your staff</h4><p>The stand does the asking at the best moment. Nothing to
install, nothing to train, no awkward conversations.</p></div>
</div>
<div class="foot"><span>{disclaimer}</span><span>1 / 2</span></div>
</section>"""

    page2 = f"""<section class="page">
{top}
<div class="sec"><h2>Why Google reviews bring you customers</h2>
<div class="why">{maps_visual()}
<div class="facts">
<div class="fact quote"><div><p>“Google review count and review score factor into local search ranking. More reviews and positive
ratings can improve your business's local ranking.”</p><cite>Google Business Profile Help: “Tips to improve your local ranking on Google”</cite></div></div>
<div class="fact"><div class="big">5–9%</div><div><p><b>More revenue for each extra star</b> in an independent
restaurant's online (Yelp) rating.</p><cite>Harvard Business School study of restaurant reviews (M. Luca, 2011)</cite></div></div>
<div class="fact"><div class="big">No. 1</div><div><p><b>Google is the review site people use most</b> when they
choose a local business.</p><cite>BrightLocal Local Consumer Review Survey 2025</cite></div></div>
</div></div></div>

<div class="sec"><h2>Already have customers' phone numbers or e-mails? We'll ask for you.</h2>
<div class="sub">Send us the contact list you keep. We message each customer your review link and follow up for you.</div>
<div class="guests">{customer_list()}{arrow_svg()}{chat_phone(business)}{arrow_svg()}
<ol class="timeline">
<li><b>Day 0 · Thank-you + review link</b>A few hours after the visit, while it's fresh.</li>
<li><b>Day 2 · Friendly reminder</b>Short and polite, in case they missed it.</li>
<li><b>Day 5 · Second reminder</b>Same link, one tap to review.</li>
<li><b>Day 9 · Last reminder</b>Then we stop: up to 3 reminders in total.</li>
<li class="stop"><b>Reply STOP, and it stops</b>Only customers who agreed to hear from you.</li>
</ol></div></div>

<div class="sec"><div class="row"><h2>One-time price. No monthly fees.</h2>
<div class="sub nowrap">Typical review platforms charge $75–$599 every month.</div></div>
<div class="prices">
<div class="price"><h4>Digital</h4><div class="amt">$99<small>one-time</small></div><ul>
<li>Your own review + pay page</li><li>Print-ready QR table cards (PDF)</li><li>Your Google review link set up</li></ul></div>
<div class="price"><h4>Stands</h4><div class="amt">$149<small>one-time</small></div><ul>
<li>Everything in Digital</li><li>5 acrylic QR + tap (NFC) stands, delivered</li><li>Link changes without reprinting</li></ul></div>
<div class="price pop"><span class="badge">MOST POPULAR</span><h4>Stands + Guest messages</h4><div class="amt">$199<small>one-time</small></div><ul>
<li>Everything in Stands</li><li>WhatsApp / e-mail review requests with up to 3 reminders</li><li>12 months of updates included</li></ul></div>
</div>
</div>

<div class="cta"><div><h2>See it with your business's name on it, free.</h2>
<p>Reply “yes” to our e-mail or scan the code, and we'll send you a free preview of your own review page.
No cost, no obligation.</p>
<div class="contact"><div><b>{signer}</b></div>{"".join(contact)}</div></div>
<div class="qr"><svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">{qr_path(reply_link, 0, 0, 100)}</svg><small>{qr_label}</small></div></div>
<div class="foot"><span>{disclaimer}</span><span>© {year} {esc(brand)} · 2 / 2</span></div>
</section>"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(brand)}: more Google reviews</title>
<style>{font_faces()}{CSS}</style></head><body>{page1}{page2}</body></html>"""


def render(html_text: str, pdf_path: Path, png: bool = False) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out = []
    with sync_playwright() as p:
        kw = {"executable_path": CHROMIUM} if Path(CHROMIUM).exists() else {}
        browser = p.chromium.launch(**kw)
        page = browser.new_page(viewport={"width": 816, "height": 1056})
        page.set_content(html_text, wait_until="load")
        page.pdf(path=str(pdf_path), width="8.5in", height="11in", print_background=True, prefer_css_page_size=True)
        if png:
            page.set_viewport_size({"width": 816, "height": 1056})
            for k, el in enumerate(page.query_selector_all("section.page"), start=1):
                img = pdf_path.with_name(f"{pdf_path.stem}-page{k}.png")
                el.screenshot(path=str(img))
                out.append(img)
        browser.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--details", default=str(HERE / "pitch.json"))
    ap.add_argument("--out", default=str(HERE / "pitch.pdf"))
    ap.add_argument("--html", default="", help="also write the HTML here")
    ap.add_argument("--png", action="store_true", help="also save page images next to the PDF")
    for k in ("brand", "name", "email", "phone", "website"):
        ap.add_argument(f"--{k}", default=None)
    a = ap.parse_args(argv)
    d = json.loads(Path(a.details).read_text(encoding="utf-8"))
    for k in ("brand", "name", "email", "phone", "website"):
        if getattr(a, k) is not None:
            d[k] = getattr(a, k)
    text = build_html(d)
    if a.html:
        Path(a.html).write_text(text, encoding="utf-8")
    imgs = render(text, Path(a.out), png=a.png)
    print(f"wrote {a.out}" + "".join(f"\nwrote {i}" for i in imgs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
