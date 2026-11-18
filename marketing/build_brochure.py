"""The India brochure (marketing/pitch-in.pdf): two pages, US Letter, in the Aurenflow navy-and-gold style of the
clinic (clinic-growth) and international (worldreach) brochures: a serif headline face (Playfair Display) with a
clean sans body (Inter), deep navy with a muted gold accent, very little text, a drawn illustration per service
(inline SVG made here: no stock images, nothing to license). No prices (15 October 2026). Words: brochure-in.json.

    python marketing/build_brochure.py                    # -> marketing/pitch-in.pdf (no phone in it)
    python marketing/build_brochure.py --png              # also page images, to check the layout
    python marketing/build_brochure.py --phone "+91 ..." --out Aurenflow-India-overview.pdf
                                                          # your own copy: your WhatsApp number and a scan-to-chat code

The edition goes into the PDF's title: the tablet attaches your own copy only when it is the same edition as the PDF
in the code (scripts/local_run.py attachment), never an outdated one.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import sys
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
INK, NAVY, NAVY2 = "#0E1A2B", "#13294B", "#1F3A63"
GOLD, GOLD_L, GOLD_XL = "#B08D57", "#E6D7BC", "#F4ECDD"
IVORY, PANEL = "#FBF9F4", "#F3EEE4"
SKY, SKY_D = "#D3DDEA", "#8EA6C6"
SKIN, HAIR = "#E7B48E", "#3B2A22"
GREY, LINE = "#566070", "#E4DDCF"
GREEN, GREEN_L = "#1F8A5B", "#D7EFE3"                 # WhatsApp's chat colours, in the brochure's muted tone


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def fonts_css() -> str:
    out = []
    for f in sorted(x for x in (HERE / "fonts").glob("*.woff2") if "rupee" not in x.name):   # no prices: no ₹
        family = "Serif" if f.name.startswith("playfair") else "Sans"
        parts = f.stem.split("-")
        weight, style = parts[-2], parts[-1]
        data = base64.b64encode(f.read_bytes()).decode("ascii")
        out.append(f"@font-face {{ font-family: B{family}; font-weight: {weight}; font-style: {style}; "
                   f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------- illustrations
def svg(body: str, w: int = 160, h: int = 120, bg: bool = True) -> str:
    back = (f'<ellipse cx="{w / 2}" cy="{h / 2 + 4}" rx="{w * 0.36}" ry="{h * 0.43}" fill="{PANEL}"/>'
            f'<ellipse cx="{w / 2}" cy="{h - 10}" rx="{w * 0.33}" ry="5" fill="{GOLD_L}" opacity=".55"/>' if bg else "")
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" stroke-linecap="round" '
            f'stroke-linejoin="round">{back}{body}</svg>')


def star(cx: float, cy: float, r: float, fill: str = GOLD) -> str:
    import math

    pts = []
    for k in range(10):
        rad = r if k % 2 == 0 else r * 0.45
        a = -math.pi / 2 + k * math.pi / 5
        pts.append(f"{cx + rad * math.cos(a):.1f},{cy + rad * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


def heart(x: float, y: float, s: float, fill: str) -> str:
    return (f'<path transform="translate({x} {y}) scale({s})" d="M0 -3 C-2 -8 -10 -7 -10 -1 C-10 4 -3 8 0 11 '
            f'C3 8 10 4 10 -1 C10 -7 2 -8 0 -3z" fill="{fill}"/>')


def person(x: float, y: float, coat: str, s: float = 1.0, hair: str = HAIR, walk: bool = False) -> str:
    legs = ('<path d="M-5 24 L-9 40 M5 24 L10 40" stroke="{c}" stroke-width="5"/>' if walk else
            '<path d="M-4 24 L-4 40 M4 24 L4 40" stroke="{c}" stroke-width="5"/>').format(c=INK)
    return (f'<g transform="translate({x} {y}) scale({s})">{legs}'
            f'<path d="M-11 26 C-11 8 11 8 11 26 Z" fill="{coat}"/>'
            f'<rect x="-3" y="2" width="6" height="6" fill="{SKIN}"/>'
            f'<circle cx="0" cy="-4" r="8" fill="{SKIN}"/>'
            f'<path d="M-8 -5 C-8 -14 8 -14 8 -5 C5 -9 -3 -10 -8 -5z" fill="{hair}"/></g>')


ART = {
    "sales": lambda: svg(
        f'<rect x="28" y="54" width="66" height="48" fill="#fff" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<rect x="24" y="40" width="74" height="15" rx="2" fill="{NAVY}"/>'
        + "".join(f'<path d="M{24 + i * 12.33} 55 a6.17 6.17 0 0 0 12.33 0z" fill="{NAVY if i % 2 else GOLD}"/>'
                  for i in range(6))
        + f'<rect x="51" y="70" width="20" height="32" fill="{SKY}" stroke="{NAVY}" stroke-width="2"/>'
          f'<circle cx="66" cy="87" r="1.6" fill="{NAVY}"/>'
          f'<rect x="34" y="66" width="12" height="12" fill="{SKY_D}"/><rect x="76" y="66" width="12" height="12" fill="{SKY_D}"/>'
          f'<rect x="104" y="80" width="9" height="22" rx="1.5" fill="{GOLD_L}"/>'
          f'<rect x="117" y="68" width="9" height="34" rx="1.5" fill="{GOLD_L}"/>'
          f'<rect x="130" y="54" width="9" height="48" rx="1.5" fill="{GOLD}"/>'
          f'<path d="M100 74 L118 58 L126 63 L142 40" fill="none" stroke="{NAVY}" stroke-width="3"/>'
          f'<path d="M134 39 L143 38 L142 47" fill="none" stroke="{NAVY}" stroke-width="3"/>'),
    "reviews": lambda: svg(
        f'<rect x="46" y="16" width="56" height="92" rx="10" fill="{NAVY}"/>'
        f'<rect x="51" y="25" width="46" height="74" rx="4" fill="#fff"/>'
        f'<circle cx="62" cy="37" r="6" fill="{SKY}"/><rect x="71" y="33" width="20" height="3.5" rx="1.7" fill="{SKY_D}"/>'
        f'<rect x="71" y="39" width="13" height="3" rx="1.5" fill="{SKY}"/>'
        + "".join(star(57 + i * 8.6, 55, 3.9) for i in range(5))
        + f'<rect x="56" y="65" width="36" height="3" rx="1.5" fill="{SKY}"/>'
          f'<rect x="56" y="72" width="30" height="3" rx="1.5" fill="{SKY}"/>'
          f'<rect x="56" y="79" width="33" height="3" rx="1.5" fill="{SKY}"/>'
          f'<rect x="96" y="22" width="44" height="30" rx="11" fill="{GOLD}"/>'
          f'<path d="M106 50 L102 60 L114 51z" fill="{GOLD}"/>' + heart(118, 35, 0.95, "#fff")
        + star(30, 86, 11, GOLD) + star(132, 84, 7, GOLD_L)),
    "followup": lambda: svg(
        f'<rect x="32" y="50" width="80" height="52" rx="5" fill="#fff" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<path d="M32 52 L72 80 L112 52" fill="none" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<path d="M32 100 L62 74 M112 100 L82 74" stroke="{SKY_D}" stroke-width="2"/>'
        f'<circle cx="112" cy="52" r="10" fill="{GOLD}"/>'
        f'<text x="112" y="56.5" text-anchor="middle" font-family="BSans" font-weight="700" font-size="12" fill="#fff">1</text>'
        f'<path d="M58 40 C70 22 98 20 112 30" fill="none" stroke="{GOLD}" stroke-width="2" stroke-dasharray="3 5"/>'
        f'<path d="M116 16 L144 10 L130 34 L124 25z" fill="{NAVY}"/><path d="M124 25 L144 10 L120 30z" fill="{NAVY2}"/>'),
    "reminder": lambda: svg(
        f'<rect x="30" y="30" width="72" height="72" rx="7" fill="#fff" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<path d="M30 48 V37 a7 7 0 0 1 7 -7 H95 a7 7 0 0 1 7 7 V48z" fill="{NAVY}"/>'
        f'<rect x="44" y="23" width="5" height="13" rx="2.5" fill="{GOLD}"/><rect x="83" y="23" width="5" height="13" rx="2.5" fill="{GOLD}"/>'
        + "".join(f'<rect x="{39 + c * 14}" y="{56 + r * 13}" width="8" height="7" rx="1.5" fill="{SKY}"/>'
                  for r in range(3) for c in range(4) if (r, c) != (1, 2))
        + f'<circle cx="71" cy="72.5" r="8.5" fill="{GOLD}"/>'
          f'<path d="M67 72.5 l3 3 l5.5 -6" fill="none" stroke="#fff" stroke-width="2.2"/>'
          f'<path d="M118 52 c-9 0 -12 8 -12 16 v8 l-5 6 h34 l-5 -6 v-8 c0 -8 -3 -16 -12 -16z" fill="{GOLD}"/>'
          f'<circle cx="118" cy="86" r="4.5" fill="{GOLD}"/><circle cx="118" cy="49" r="3" fill="{GOLD}"/>'
          f'<path d="M140 56 q6 10 0 20 M96 56 q-6 10 0 20" fill="none" stroke="{GOLD_L}" stroke-width="2.4"/>'),
    "winback": lambda: svg(
        f'<rect x="84" y="28" width="44" height="76" rx="2" fill="{NAVY}"/>'
        f'<rect x="89" y="33" width="34" height="71" fill="{GOLD_XL}"/>'
        f'<path d="M89 33 L111 40 L111 108 L89 104z" fill="#fff" stroke="{NAVY}" stroke-width="2"/>'
        f'<circle cx="106" cy="72" r="1.8" fill="{NAVY}"/>'
        f'<rect x="80" y="104" width="52" height="5" rx="2" fill="{GOLD}"/>'
        + person(54, 58, SKY_D, 1.05, walk=True)
        + f'<path d="M62 72 Q70 70 76 64" fill="none" stroke="{SKY_D}" stroke-width="5"/><circle cx="77" cy="63" r="3" fill="{SKIN}"/>'
        + heart(106, 14, 1.0, GOLD) + heart(72, 30, 0.6, GOLD_L)),
    "payment": lambda: svg(
        f'<rect x="28" y="44" width="84" height="56" rx="8" fill="{NAVY}"/>'
        f'<rect x="28" y="56" width="84" height="10" fill="{INK}"/>'
        f'<rect x="38" y="74" width="15" height="11" rx="2" fill="{GOLD}"/>'
        f'<rect x="60" y="78" width="40" height="3.5" rx="1.7" fill="{SKY_D}"/>'
        f'<rect x="60" y="86" width="26" height="3.5" rx="1.7" fill="{SKY_D}"/>'
        f'<circle cx="114" cy="46" r="17" fill="{GOLD}"/>'
        f'<path d="M106 46 l6 6 l11 -12" fill="none" stroke="#fff" stroke-width="3.6"/>'
        f'<circle cx="40" cy="30" r="7" fill="{GOLD_L}"/><circle cx="52" cy="24" r="5" fill="{GOLD_L}"/>'),
    "website": lambda: svg(
        f'<rect x="20" y="20" width="120" height="84" rx="8" fill="#fff" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<path d="M20 36 V28 a8 8 0 0 1 8 -8 H132 a8 8 0 0 1 8 8 V36z" fill="{NAVY}"/>'
        f'<circle cx="30" cy="28" r="2.6" fill="{GOLD}"/><circle cx="38" cy="28" r="2.6" fill="{GOLD_L}"/>'
        f'<circle cx="46" cy="28" r="2.6" fill="{SKY_D}"/>'
        f'<rect x="30" y="44" width="56" height="32" rx="4" fill="{SKY}"/>'
        f'<path d="M34 72 L50 56 L60 66 L68 59 L82 72z" fill="{SKY_D}"/><circle cx="74" cy="52" r="4" fill="{GOLD}"/>'
        f'<rect x="94" y="46" width="36" height="5" rx="2.5" fill="{NAVY}"/>'
        f'<rect x="94" y="56" width="30" height="3.5" rx="1.7" fill="{SKY}"/>'
        f'<rect x="94" y="63" width="34" height="3.5" rx="1.7" fill="{SKY}"/>'
        f'<rect x="94" y="72" width="26" height="9" rx="4.5" fill="{GOLD}"/>'
        f'<rect x="30" y="84" width="100" height="3.5" rx="1.7" fill="{SKY}"/>'
        f'<rect x="30" y="91" width="70" height="3.5" rx="1.7" fill="{SKY}"/>'),
    "talk": lambda: svg(
        person(62, 66, NAVY, 1.0) + person(114, 66, GOLD, 1.0, hair="#6B4A32")
        + f'<rect x="36" y="16" width="50" height="30" rx="10" fill="#fff" stroke="{NAVY}" stroke-width="2"/>'
          f'<path d="M54 45 L56 54 L64 45z" fill="#fff" stroke="{NAVY}" stroke-width="2"/>'
          f'<path d="M54 44.5 H65" stroke="#fff" stroke-width="3"/>'
          f'<circle cx="49" cy="31" r="3" fill="{SKY_D}"/><circle cx="61" cy="31" r="3" fill="{SKY_D}"/>'
          f'<circle cx="73" cy="31" r="3" fill="{SKY_D}"/>'
          f'<rect x="96" y="20" width="40" height="26" rx="9" fill="{GOLD_L}"/><path d="M116 45 L112 53 L123 45z" fill="{GOLD_L}"/>'
          f'<text x="116" y="39" text-anchor="middle" font-family="BSerif" font-weight="700" font-size="17" fill="{NAVY}">?</text>'),
    "dig": lambda: svg(
        f'<rect x="26" y="24" width="78" height="74" rx="6" fill="#fff" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<rect x="36" y="70" width="10" height="18" rx="1.5" fill="{SKY}"/><rect x="51" y="58" width="10" height="30" rx="1.5" fill="{SKY_D}"/>'
        f'<rect x="66" y="46" width="10" height="42" rx="1.5" fill="{GOLD_L}"/><rect x="81" y="36" width="10" height="52" rx="1.5" fill="{GOLD}"/>'
        f'<circle cx="104" cy="58" r="20" fill="#ffffff" fill-opacity=".55" stroke="{NAVY}" stroke-width="5"/>'
        f'<path d="M118 72 L136 92" stroke="{NAVY}" stroke-width="8"/>'
        f'<path d="M96 58 l6 6 l10 -12" fill="none" stroke="{GOLD}" stroke-width="3"/>'),
    "list": lambda: svg(
        f'<rect x="36" y="26" width="88" height="58" rx="5" fill="{NAVY}"/>'
        f'<rect x="41" y="31" width="78" height="48" rx="2" fill="#fff"/>'
        + "".join(f'<circle cx="50" cy="{40 + i * 11}" r="3.6" fill="{GOLD if i == 1 else SKY}"/>'
                  f'<rect x="58" y="{38 + i * 11}" width="{50 - (i % 2) * 14}" height="4" rx="2" fill="{SKY_D if i == 1 else SKY}"/>'
                  for i in range(4))
        + f'<path d="M26 92 L36 84 H124 L134 92z" fill="{SKY_D}"/><rect x="26" y="92" width="108" height="5" rx="2" fill="{NAVY}"/>'),
    "approve": lambda: svg(
        f'<rect x="42" y="18" width="62" height="86" rx="5" fill="#fff" stroke="{NAVY}" stroke-width="2.4"/>'
        + "".join(f'<rect x="52" y="{32 + i * 9}" width="{42 - (i % 3) * 8}" height="3.5" rx="1.7" fill="{SKY}"/>'
                  for i in range(6))
        + f'<path d="M52 92 q6 -8 12 0 t12 0" fill="none" stroke="{NAVY}" stroke-width="2"/>'
          f'<circle cx="106" cy="88" r="15" fill="{GOLD}"/>'
          f'<path d="M99 88 l5 5 l10 -11" fill="none" stroke="#fff" stroke-width="3.4"/>'
          f'<path d="M122 26 L92 70 L88 80 L96 74 L126 30z" fill="{NAVY2}"/><path d="M122 26 l4 4" stroke="{GOLD}" stroke-width="4"/>'),
    "growth": lambda: svg(
        person(52, 62, NAVY, 0.95) + person(80, 56, GOLD, 1.05, hair="#6B4A32") + person(108, 62, SKY_D, 0.95)
        + f'<path d="M36 34 L64 22 L84 28 L120 10" fill="none" stroke="{GOLD}" stroke-width="3"/>'
          f'<path d="M111 9 L121 9 L119 19" fill="none" stroke="{GOLD}" stroke-width="3"/>'),
}

def qr_block(x: float, y: float, s: float, dark: str = NAVY) -> str:
    """A small QR-code-like square (a picture, not a working code)."""
    out = [f'<rect x="{x}" y="{y}" width="{s * 13}" height="{s * 13}" rx="{s * .6}" fill="#fff"/>']
    finder = lambda fx, fy: (f'<rect x="{fx}" y="{fy}" width="{s * 4}" height="{s * 4}" fill="none" stroke="{dark}" '
                             f'stroke-width="{s * .9}"/><rect x="{fx + s * 1.3}" y="{fy + s * 1.3}" width="{s * 1.4}" '
                             f'height="{s * 1.4}" fill="{dark}"/>')
    out.append(finder(x + s * .8, y + s * .8) + finder(x + s * 8.2, y + s * .8) + finder(x + s * .8, y + s * 8.2))
    for (cx, cy) in ((6, 1), (6, 3), (5.5, 5.5), (8, 6), (10, 6.5), (6.5, 8), (9, 8.5), (11, 9), (8, 10.5),
                     (10.5, 11), (6, 11), (1, 6), (3, 6.5), (4.5, 5.5)):
        out.append(f'<rect x="{x + cx * s}" y="{y + cy * s}" width="{s * 1.2}" height="{s * 1.2}" fill="{dark}"/>')
    return "".join(out)


def phone(x: float, y: float, inner: str, w: float = 50, h: float = 86) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{NAVY}"/>'
            f'<rect x="{x + 4.5}" y="{y + 8}" width="{w - 9}" height="{h - 16}" rx="3.5" fill="#fff"/>{inner}')


ART.update({
    "qr": lambda: svg(
        f'<path d="M50 30 H110 L118 104 H42z" fill="{NAVY}"/>'
        + qr_block(57, 38, 3.5)
        + f'<rect x="56" y="88" width="48" height="4" rx="2" fill="{GOLD}"/>'
          f'<rect x="62" y="95" width="36" height="3" rx="1.5" fill="{SKY_D}"/>'
        + star(30, 40, 9, GOLD) + star(134, 36, 6, GOLD_L) + star(138, 78, 8, GOLD)),
    "payreview": lambda: svg(
        phone(54, 16, f'<rect x="64" y="30" width="30" height="8" rx="4" fill="{GOLD}"/>'
                      f'<text x="79" y="36.5" text-anchor="middle" font-family="BSans" font-weight="700" font-size="6.3" '
                      f'fill="#fff">PAY UPI</text>'
                      + "".join(star(63 + i * 8, 52, 3.4) for i in range(5))
                      + f'<rect x="63" y="62" width="32" height="7" rx="3.5" fill="#fff" stroke="{NAVY}" stroke-width="1.4"/>'
                        f'<rect x="66" y="64.8" width="26" height="1.6" rx=".8" fill="{SKY_D}"/>'
                        f'<rect x="63" y="76" width="22" height="3" rx="1.5" fill="{SKY}"/>'
                        f'<rect x="63" y="82" width="28" height="3" rx="1.5" fill="{SKY}"/>')
        + f'<circle cx="114" cy="40" r="14" fill="{GOLD}"/><path d="M107 40 l5 5 l9 -10" fill="none" stroke="#fff" '
          f'stroke-width="3.2"/>' + qr_block(16, 60, 2.6)),
    "print": lambda: svg(
        f'<path d="M30 98 L52 38 L74 98z" fill="{NAVY}"/><path d="M74 98 L52 38 L60 38 L84 98z" fill="{NAVY2}"/>'
        + qr_block(43, 58, 1.7)
        + f'<rect x="92" y="40" width="44" height="60" rx="4" fill="#fff" stroke="{NAVY}" stroke-width="2.2"/>'
          f'<rect x="99" y="48" width="30" height="4" rx="2" fill="{GOLD}"/>'
        + qr_block(103, 58, 1.7, NAVY)
        + f'<rect x="99" y="88" width="30" height="3" rx="1.5" fill="{SKY_D}"/>'
          f'<circle cx="128" cy="30" r="11" fill="{GOLD_L}"/>' + star(128, 30, 6, GOLD)),
    "whatsapp": lambda: svg(
        phone(30, 14, f'<rect x="34.5" y="22" width="41" height="9" fill="{GREEN}"/>'
                      f'<rect x="39" y="38" width="30" height="12" rx="4" fill="{GREEN_L}"/>'
                      f'<rect x="42" y="42" width="22" height="2.4" rx="1.2" fill="{GREEN}"/>'
                      f'<rect x="44" y="55" width="27" height="10" rx="4" fill="{SKY}"/>'
                      + "".join(star(45 + i * 5, 74, 2.1) for i in range(5))
                      + f'<rect x="39" y="80" width="26" height="2.4" rx="1.2" fill="{SKY_D}"/>')
        + f'<rect x="90" y="22" width="48" height="30" rx="12" fill="{GREEN}"/><path d="M100 50 L96 60 L109 51z" '
          f'fill="{GREEN}"/>' + heart(114, 35, 0.9, "#fff")
        + f'<rect x="96" y="62" width="42" height="24" rx="10" fill="{GOLD_L}"/>'
        + "".join(star(104 + i * 7.5, 74, 2.9) for i in range(4))),
    "report": lambda: svg(
        f'<rect x="28" y="22" width="88" height="80" rx="6" fill="#fff" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<rect x="38" y="32" width="40" height="5" rx="2.5" fill="{NAVY}"/>'
        f'<rect x="40" y="74" width="10" height="18" rx="1.5" fill="{SKY}"/><rect x="55" y="66" width="10" height="26" rx="1.5" fill="{SKY_D}"/>'
        f'<rect x="70" y="56" width="10" height="36" rx="1.5" fill="{GOLD_L}"/><rect x="85" y="46" width="10" height="46" rx="1.5" fill="{GOLD}"/>'
        f'<path d="M40 64 L58 56 L74 50 L100 38" fill="none" stroke="{NAVY}" stroke-width="2.4"/>'
        f'<circle cx="122" cy="40" r="17" fill="{GOLD}"/>'
        f'<text x="122" y="45" text-anchor="middle" font-family="BSerif" font-weight="700" font-size="13" fill="#fff">4.8</text>'
        + star(122, 66, 6, GOLD) + star(134, 92, 5, GOLD_L)),
    "insights": lambda: svg(
        f'<rect x="22" y="30" width="80" height="62" rx="8" fill="{SKY}"/>'
        f'<path d="M22 62 Q50 50 66 64 T102 58" fill="none" stroke="#fff" stroke-width="5"/>'
        f'<path d="M48 30 L56 92" stroke="#fff" stroke-width="4"/>'
        f'<path d="M62 34 c-10 0 -16 7 -16 15 c0 11 16 26 16 26 s16 -15 16 -26 c0 -8 -6 -15 -16 -15z" fill="{GOLD}"/>'
        f'<circle cx="62" cy="49" r="6" fill="#fff"/>'
        f'<circle cx="124" cy="36" r="13" fill="{NAVY}"/>'
        f'<path d="M118 31 q0 9 9 11 l2.4 -2.4 l-3 -2.4 l-1.6 1.6 q-3 -1.5 -4.2 -4.2 l1.6 -1.6 l-2.4 -3z" fill="#fff"/>'
        f'<circle cx="124" cy="68" r="13" fill="{NAVY}"/><path d="M118 72 L124 62 L130 72 L124 69z" fill="#fff"/>'
        f'<circle cx="124" cy="100" r="11" fill="{GOLD_L}"/><path d="M118 100 h12 M124 94 v12" stroke="{NAVY}" stroke-width="2.4"/>'),
    "preview": lambda: svg(
        f'<path d="M34 26 H94 L102 104 H26z" fill="{NAVY}"/>' + qr_block(42, 36, 3.1)
        + f'<rect x="40" y="82" width="48" height="4" rx="2" fill="{GOLD}"/>'
          f'<text x="64" y="96" text-anchor="middle" font-family="BSerif" font-style="italic" font-size="9" fill="#fff">'
          f'Your Cafe</text>'
          f'<rect x="108" y="44" width="38" height="26" rx="10" fill="{GOLD}"/><path d="M118 68 L114 78 L126 69z" fill="{GOLD}"/>'
          f'<text x="127" y="62" text-anchor="middle" font-family="BSans" font-weight="800" font-size="11" fill="#fff">YES</text>'),
    "scan": lambda: svg(
        person(46, 58, SKY_D, 1.0)
        + phone(64, 34, f'<rect x="69" y="42" width="21" height="2" fill="{GOLD}"/>', w=30, h=48)
        + f'<path d="M58 74 Q62 66 66 62" fill="none" stroke="{SKY_D}" stroke-width="5"/>'
          f'<path d="M98 52 L112 46 M98 60 L114 60 M98 68 L112 74" stroke="{GOLD}" stroke-width="2.4" stroke-dasharray="3 3"/>'
        + qr_block(114, 44, 2.6)),
    "remind": lambda: svg(
        phone(56, 16, f'<rect x="65" y="30" width="26" height="10" rx="4" fill="{GREEN_L}"/>'
                      f'<rect x="70" y="46" width="26" height="10" rx="4" fill="{GREEN_L}"/>'
                      f'<rect x="65" y="62" width="26" height="10" rx="4" fill="{GREEN_L}"/>'
                      f'<rect x="80" y="78" width="15" height="7" rx="3" fill="{SKY}"/>')
        + f'<circle cx="122" cy="36" r="12" fill="{GOLD}"/>'
          f'<text x="122" y="41" text-anchor="middle" font-family="BSans" font-weight="800" font-size="13" fill="#fff">3</text>'
          f'<path d="M30 40 q-8 14 0 28 M40 46 q-5 8 0 16" fill="none" stroke="{GOLD_L}" stroke-width="3"/>'),
})

ICONS = {
    "dish": '<path d="M3 16h18M5 16a7 7 0 0 1 14 0M12 9V7M10 7h4M4 19h16"/>',
    "glass": '<path d="M7 3h10l-1 7a4 4 0 0 1-8 0zM12 14v6M8 20h8M7.5 7h9"/>',
    "cake": '<path d="M4 20h16v-6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2zM4 16c2 1.5 4 1.5 5.3 0 1.4 1.5 4 1.5 5.4 0 1.3 1.5 3.3 1.5 5.3 0M12 12V8M12 5.5v.5"/>',
    "bag": '<path d="M5 8h14l-1 12H6zM9 8V6a3 3 0 0 1 6 0v2"/>',

    "gym": '<path d="M5 12h14M3 9v6M21 9v6M6 7v10M18 7v10"/>',
    "yoga": '<circle cx="12" cy="4" r="2"/><path d="M12 7v7M12 9l-6-3M12 9l6-3M4 18c3-3 5-4 8-4s5 1 8 4M6 20h12"/>',
    "karate": '<path d="M2 10.5h7M15 10.5h7M2 13.5h7M15 13.5h7M10.5 14l-3 6M13.5 14l3 6"/><rect x="9" y="9" width="6" height="6" rx="1.2"/>',
    "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.1 8.1 20 20M8.1 15.9 20 4"/>',
    "bed": '<path d="M3 18V7M3 13h18v5M21 13a3 3 0 0 0-3-3h-8v3"/><circle cx="7" cy="10.5" r="1.8"/>',
    "cup": '<path d="M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM17 10h1.5a2.5 2.5 0 0 1 0 5H17M8 3c0 2 2 2 2 4M12 3c0 2 2 2 2 4"/>',
    "paw": '<circle cx="7" cy="9" r="1.8"/><circle cx="11" cy="6" r="1.8"/><circle cx="15" cy="7" r="1.8"/>'
           '<circle cx="18" cy="11" r="1.8"/><path d="M8 17c0-3 2-6 5-6s4 3 4 5-1.5 3-4 2.5S8 20 8 17z"/>',
    "wrench": '<path d="M14.7 6.3a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3l7.7-7.7a4 4 0 0 0-2-2zM14.7 6.3 17 4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 '
             '2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 '
             '0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    "mail": '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M3 6.5l9 6.5 9-6.5"/>',
}


def icon(name: str, size: int = 22, color: str = GOLD, width: float = 1.7) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


# ------------------------------------------------------------------------------------------- the pages
CSS = f"""
@page {{ size: 8.5in 11in; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: BSans, Arial, sans-serif; color: {INK}; font-size: 10.5pt; line-height: 1.45; background: #fff; }}
.page {{ width: 8.5in; height: 11in; padding: 0.55in 0.65in 0.45in; position: relative; overflow: hidden;
         page-break-after: always; display: flex; flex-direction: column; background: #fff; }}
.top {{ display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 10px;
        border-bottom: 1px solid {GOLD}; }}
.mark {{ font-family: BSerif; font-weight: 600; font-size: 13pt; letter-spacing: 3.5px; color: {NAVY}; }}
.tag {{ font-size: 7.8pt; letter-spacing: 2.2px; text-transform: uppercase; color: {GREY}; font-weight: 600; }}
h1 {{ font-family: BSerif; font-weight: 500; font-size: 39pt; line-height: 1.07; letter-spacing: -0.6px;
      color: {INK}; margin-top: 0.34in; max-width: 6.9in; }}
h1 em {{ font-style: italic; font-weight: 400; color: {GOLD}; }}
.sub {{ font-size: 12.2pt; color: {GREY}; margin-top: 14px; max-width: 6.4in; line-height: 1.5; }}
.label {{ display: flex; align-items: center; gap: 12px; margin: 0.34in 0 14px; font-size: 8pt; letter-spacing: 2.6px;
          text-transform: uppercase; color: {GOLD}; font-weight: 700; }}
.label::after {{ content: ""; flex: 1; height: 1px; background: {LINE}; }}
.grid {{ display: grid; grid-template-columns: repeat(3, 1fr); column-gap: 22px; row-gap: 18px; }}
.tile .art {{ background: {IVORY}; border-radius: 16px; height: 1.14in; display: flex; align-items: center;
              justify-content: center; }}
.tile .art svg {{ height: 1.05in; width: auto; }}
.tile b {{ display: block; font-family: BSerif; font-weight: 600; font-size: 14.2pt; line-height: 1.2; color: {NAVY};
           margin-top: 11px; }}
.tile p {{ color: {GREY}; font-size: 10pt; margin-top: 4px; line-height: 1.4; }}
.tile.wide {{ grid-column: 1 / -1; display: grid; grid-template-columns: 2.2in 1fr; gap: 22px; align-items: center;
              background: {NAVY}; border-radius: 16px; padding: 10px 26px 10px 10px; }}
.tile.wide .art {{ height: 1.05in; background: {IVORY}; }}
.tile.wide .art svg {{ height: 0.98in; }}
.tile.wide b {{ color: #fff; margin-top: 0; font-size: 15.5pt; }}
.tile.wide p {{ color: #C9D3E2; font-size: 10.4pt; }}
.strip {{ margin-top: auto; display: flex; justify-content: space-between; align-items: center; gap: 16px;
          border-top: 1px solid {LINE}; padding-top: 13px; }}
.strip .ask {{ font-family: BSerif; font-size: 13.5pt; color: {NAVY}; font-weight: 500; }}
.contact {{ display: flex; gap: 22px; align-items: center; font-weight: 600; font-size: 10.4pt; color: {INK}; }}
.contact span {{ display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }}
.steps {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }}
.step .art {{ background: {IVORY}; border-radius: 16px; height: 1.6in; display: flex; align-items: center;
              justify-content: center; position: relative; }}
.step .art svg {{ height: 1.32in; max-width: 100%; width: auto; margin-top: 10px; }}
.step .n {{ position: absolute; top: 7px; left: 11px; font-family: BSerif; font-style: italic; font-size: 15pt; color: {GOLD}; }}
.step b {{ display: block; font-family: BSerif; font-weight: 600; font-size: 12.6pt; color: {NAVY}; margin-top: 11px; }}
.step p {{ color: {GREY}; font-size: 9.6pt; margin-top: 3px; }}
.inds {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.ind {{ display: flex; align-items: center; gap: 10px; border: 1px solid {LINE}; border-radius: 12px; padding: 14px 12px;
        font-size: 9.8pt; font-weight: 600; color: {NAVY}; }}
.ind .i {{ width: 34px; height: 34px; border-radius: 50%; background: {GOLD_XL}; display: flex; align-items: center;
           justify-content: center; flex: none; }}
.promise {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-bottom: 0.35in; }}
.promise div {{ display: flex; gap: 10px; align-items: flex-start; font-size: 10.6pt; color: {INK}; font-weight: 600;
                line-height: 1.35; }}
.promise svg {{ flex: none; margin-top: 1px; }}
.cta {{ margin-top: auto; margin-bottom: 4px; background: {NAVY}; border-radius: 18px; color: #fff; padding: 28px 30px;
        display: flex; justify-content: space-between; align-items: center; gap: 26px; }}
.cta h2 {{ font-family: BSerif; font-weight: 500; font-size: 25pt; line-height: 1.1; }}
.cta p {{ font-size: 10.6pt; color: #C9D3E2; margin-top: 8px; max-width: 3.7in; }}
.cta .contact {{ flex-direction: column; align-items: flex-start; gap: 10px; color: #fff; font-size: 11.6pt; }}
.facts {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
.fact {{ background: {IVORY}; border-radius: 14px; padding: 14px 16px; }}
.fact .big {{ font-family: BSerif; font-weight: 600; font-size: 25pt; color: {GOLD}; line-height: 1; }}
.fact p {{ font-size: 9.8pt; color: {INK}; margin-top: 7px; line-height: 1.35; font-weight: 600; }}
.fact cite {{ display: block; font-style: normal; font-size: 7.6pt; color: #8A92A0; margin-top: 6px; }}
.cta .scan {{ background: #fff; border-radius: 12px; padding: 8px 8px 5px; text-align: center; flex: none; }}
.cta .scan svg {{ width: 1.05in; height: 1.05in; display: block; }}
.cta .scan small {{ display: block; color: {NAVY}; font-size: 7.6pt; font-weight: 700; margin-top: 3px; }}
.cta .right {{ display: flex; gap: 18px; align-items: center; }}
.foot {{ display: flex; justify-content: space-between; color: #8A92A0; font-size: 7.8pt; letter-spacing: 1px;
         margin-top: 14px; text-transform: uppercase; }}
"""


def contact_html(d: dict, light: bool = False) -> str:
    color = "#fff" if light else GOLD
    items = []
    if d.get("phone"):
        items.append(f'<span>{icon("phone", 17, color)}{esc(d["phone"])}</span>')
    if d.get("email"):
        items.append(f'<span>{icon("mail", 17, color)}{esc(d["email"])}</span>')
    if not items:
        items.append(f'<span>{icon("mail", 17, color)}{esc(d.get("contact_fallback"))}</span>')
    return f'<div class="contact">{"".join(items)}</div>'


def headline(text: str) -> str:
    """The second sentence of the headline in gold italics ("More Google reviews. <em>More customers ...</em>")."""
    first, dot, rest = esc(text).partition(". ")
    if not rest:
        words = first.split(" ")
        cut = max(1, len(words) - 3)
        return " ".join(words[:cut]) + " <em>" + " ".join(words[cut:]) + "</em>"
    return f"{first}.<br><em>{rest}</em>"


def scan_code(d: dict) -> str:
    """The code in the closing box: a WhatsApp chat with you (your own copy), else nothing."""
    digits = "".join(ch for ch in d.get("phone", "") if ch.isdigit())
    if not digits:
        return ""
    import segno

    link = f"https://wa.me/{digits}?text={quote('Hi! I would like a free preview of my review QR.')}"
    code = segno.make(link, error="m")
    path = code.svg_inline(scale=1, border=0, dark=NAVY, omitsize=True)
    return f'<div class="scan">{path}<small>Scan to WhatsApp</small></div>'



def top(d: dict) -> str:
    return f'<div class="top"><span class="mark">{esc(d["brand"]).upper()}</span><span class="tag">{esc(d["tagline"])}</span></div>'


def page_one(d: dict) -> str:
    tiles = "".join(
        (f'<div class="tile wide"><div class="art">{ART[s["art"]]()}</div><div><b>{esc(s["title"])}</b>'
         f'<p>{esc(s["text"])}</p></div></div>') if s.get("wide") else
        (f'<div class="tile"><div class="art">{ART[s["art"]]()}</div><b>{esc(s["title"])}</b>'
         f'<p>{esc(s["text"])}</p></div>') for s in d["services"])
    return f"""<section class="page">{top(d)}
<h1>{headline(d["headline"])}</h1>
<p class="sub">{esc(d["subline"])}</p>
<div class="label">What we do for you</div>
<div class="grid">{tiles}</div>
<div class="strip"><span class="ask">Talk to us</span>{contact_html(d)}</div>
<div class="foot"><span>{esc(d["brand"])}</span><span>1 / 2</span></div>
</section>"""


def page_two(d: dict) -> str:
    steps = "".join(f'<div class="step"><div class="art"><span class="n">0{i}</span>{ART[s["art"]]()}</div>'
                    f'<b>{esc(s["title"])}</b><p>{esc(s["text"])}</p></div>' for i, s in enumerate(d["steps"], start=1))
    inds = "".join(f'<div class="ind"><span class="i">{icon(x["icon"], 19, NAVY, 1.6)}</span>{esc(x["label"])}</div>'
                   for x in d["industries"])
    promise = "".join(f'<div>{icon("check", 20, GOLD, 2.4)}<span>{esc(p)}</span></div>' for p in d["promises"])
    facts = "".join(f'<div class="fact"><div class="big">{esc(f["big"])}</div><p>{esc(f["text"])}</p>'
                    f'<cite>{esc(f["cite"])}</cite></div>' for f in d.get("facts", []))
    return f"""<section class="page">{top(d)}
<div class="label" style="margin-top:0.3in">How it works</div>
<div class="steps">{steps}</div>
<div class="label">Why Google reviews bring customers</div>
<div class="facts">{facts}</div>
<div class="label">Made for</div>
<div class="inds">{inds}</div>
<div class="label">Our promise</div>
<div class="promise">{promise}</div>
<div class="cta"><div><h2>{esc(d["cta_title"])}</h2><p>{esc(d["cta_text"])}</p></div>
<div class="right">{contact_html(d, light=True)}{scan_code(d)}</div></div>
<div class="foot"><span>{esc(d["brand"])} · {esc(d["tagline"])}</span><span>2 / 2</span></div>
</section>"""


# This brochure has one section more than WorldReach's (the facts): a little tighter all round.
TIGHT = """
h1 { margin-top: 0.28in; font-size: 37pt; }
.label { margin: 0.2in 0 10px; }
.step .art { height: 1.18in; } .step .art svg { height: 1.02in; margin-top: 6px; }
.step b { margin-top: 8px; font-size: 12.2pt; } .step p { font-size: 9.3pt; }
.fact { padding: 10px 14px; } .fact .big { font-size: 21pt; } .fact p { font-size: 9.2pt; margin-top: 5px; }
.fact cite { margin-top: 4px; font-size: 7.2pt; }
.ind { padding: 9px 11px; font-size: 9.4pt; } .ind .i { width: 30px; height: 30px; }
.promise { margin-bottom: 0.2in; } .promise div { font-size: 10pt; }
.cta { padding: 20px 22px 20px 26px; gap: 18px; } .cta h2 { font-size: 23pt; }
.cta > div:first-child { flex: 1; min-width: 0; } .cta .right { gap: 16px; flex: none; }
.cta .scan { padding: 7px 7px 4px; } .cta .scan svg { width: 0.95in; height: 0.95in; }
"""


def build_html(d: dict) -> str:
    title = f"{d['brand']}: more Google reviews, edition {d.get('edition', '')}"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title>'
            f"<style>{fonts_css()}\n{CSS}\n{TIGHT}</style></head><body>{page_one(d)}{page_two(d)}</body></html>")




CHROMIUM = "/opt/pw-browsers/chromium"


def render(page_html: str, pdf: Path, png: bool = False) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        kw = {"executable_path": CHROMIUM} if Path(CHROMIUM).exists() else {}
        browser = p.chromium.launch(**kw)
        page = browser.new_page(viewport={"width": 816, "height": 1056}, device_scale_factor=2)
        page.set_content(page_html, wait_until="load")
        page.evaluate("document.fonts.ready")
        over = page.evaluate("""() => [...document.querySelectorAll('section.page')]
            .map((s, i) => [i + 1, s.scrollHeight > s.clientHeight + 1]).filter(x => x[1]).map(x => x[0])""")
        if over:
            browser.close()
            print(f"The text is too long for page {over}: shorten it.")
            return 3
        page.pdf(path=str(pdf), width="8.5in", height="11in", print_background=True)
        if png:
            for k, el in enumerate(page.query_selector_all("section.page"), start=1):
                el.screenshot(path=str(pdf.with_name(f"{pdf.stem}-page{k}.png")))
        browser.close()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(HERE / "pitch-in.pdf"))
    ap.add_argument("--png", action="store_true", help="also page images next to the PDF")
    ap.add_argument("--html", action="store_true", help="only write the HTML (no Chromium needed)")
    ap.add_argument("--phone", default="", help="your WhatsApp number: only for your own copy (never commit it)")
    ap.add_argument("--email", default="")
    a = ap.parse_args(argv)
    d = json.loads((HERE / "brochure-in.json").read_text(encoding="utf-8"))
    d["phone"], d["email"] = a.phone.strip(), a.email.strip()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    page = build_html(d)
    if a.html:
        out.with_suffix(".html").write_text(page, encoding="utf-8")
        print(f"wrote {out.with_suffix('.html')}")
        return 0
    code = render(page, out, a.png)
    if code == 0:
        print(f"wrote {out} (edition {d.get('edition')})")
    return code


if __name__ == "__main__":
    sys.exit(main())
