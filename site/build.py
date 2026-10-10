"""Build the QR landing pages: one small static page per customer, plus the preview page for our letters and
the legal pages German law requires. No database, no server code, no cookies, no tracking.

    python site/build.py               build site/public/ (refuses while site.json still has FILL_IN)
    python site/build.py --preview     build anyway (for checking the pages before your details are in)

Each customer is one file in site/businesses/<id>.json. The printed QR code points to <base_url>/r/<id>/, so
the payment link, the review link or the menu can change at any time without reprinting anything.

Why a page in between (and not the Google review form straight from the QR code): Google's review form cannot
send guests back anywhere after they post, and a review must never stand between a guest and paying. So the page
offers both, side by side; a guest who goes to Google comes back to the same page and finds the payment button
waiting (assets/r.js). Payment links are only ever taken from these files, never from the address bar, so nobody
can swap in another payee by editing a link.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
LANGS = ("de", "en")

# Review links Google issues: the Business Profile's "Ask for reviews" link (g.page/r/...), the Place ID form
# (search.google.com/local/writereview?placeid=...) and Maps share links.
REVIEW_HOSTS = {"g.page", "search.google.com", "maps.app.goo.gl", "www.google.com", "google.com"}
# Payment pages of well-known providers. Anything else needs "allow_any_host": true in the business file.
PAYMENT_HOSTS = {"paypal.me", "www.paypal.me", "www.paypal.com", "paypal.com", "buy.stripe.com", "checkout.stripe.com",
                 "pay.sumup.com", "pay.sumup.io", "sumup.link", "square.link", "checkout.square.site", "revolut.me",
                 "monzo.me", "cash.app", "venmo.com", "account.venmo.com", "pay.paddle.com", "checkout.mollie.com",
                 "paymentlink.mollie.com", "pay.vivawallet.com", "link.zettle.com", "pay.zettle.com"}

T = {
    "de": {
        "welcome": "Danke für Ihren Besuch!",
        "home_lead": "Google-Bewertungen, fair und einfach.",
        "home_link": "Vorschau ansehen",
        "lead_pay": "Hier können Sie bezahlen. Und wenn Sie mögen, erzählen Sie anderen Gästen auf Google von Ihrem Besuch.",
        "lead_nopay": "Wenn Sie mögen, erzählen Sie anderen Gästen auf Google von Ihrem Besuch.",
        "pay": "Rechnung bezahlen",
        "review": "Bewertung auf Google schreiben",
        "menu": "Speisekarte ansehen",
        "optional": "Die Bewertung ist freiwillig. Ob kurz oder lang, begeistert oder kritisch: Ihre ehrliche Meinung hilft.",
        "hint_pay": "Danke! Hier geht es weiter zum Bezahlen.",
        "hint_nopay": "Danke für Ihre Zeit!",
        "pay_counter": "Bezahlen Sie bitte wie gewohnt am Tisch oder an der Theke.",
        "thanks_title": "Vielen Dank!",
        "thanks_text": "Schön, dass Sie da waren. Haben Sie eine Minute? Ihre ehrliche Bewertung auf Google hilft uns und anderen Gästen.",
        "imprint": "Impressum", "privacy": "Datenschutz", "other_lang": "English",
        "demo_banner": "Vorschau: So könnte die Seite für {name} aussehen. Die Knöpfe hier sind nur Beispiele.",
        "demo_cta": "Das möchte ich auch",
        "demo_wa": "Hallo, ich habe Ihre Vorschau gesehen und möchte mehr über den Google-Bewertungs-QR-Code für {business} erfahren.",
        "demo_points": ["Ein QR-Code für jeden Tisch und die Theke, fertig zum Drucken",
                        "Ihr Zahlungslink direkt daneben (PayPal, SumUp, Stripe ...)",
                        "Nach Google-Richtlinien: jeder Gast wird gleich gefragt, ohne Rabatte",
                        "Links jederzeit änderbar, ohne neu zu drucken"],
        "your_business": "Ihr Restaurant",
    },
    "en": {
        "welcome": "Thanks for visiting!",
        "home_lead": "Google reviews, fair and simple.",
        "home_link": "See a preview",
        "lead_pay": "You can pay here. And if you like, tell other guests about your visit on Google.",
        "lead_nopay": "If you like, tell other guests about your visit on Google.",
        "pay": "Pay the bill",
        "review": "Write a Google review",
        "menu": "See the menu",
        "optional": "Reviews are optional. Short or long, delighted or critical: your honest opinion helps.",
        "hint_pay": "Thank you! You can pay here now.",
        "hint_nopay": "Thanks for your time!",
        "pay_counter": "Please pay at your table or the counter as usual.",
        "thanks_title": "Thank you!",
        "thanks_text": "Great to have you here. Got a minute? An honest Google review helps us and other guests.",
        "imprint": "Legal notice", "privacy": "Privacy", "other_lang": "Deutsch",
        "demo_banner": "Preview: this is how the page for {name} could look. The buttons here are only examples.",
        "demo_cta": "I'd like this",
        "demo_wa": "Hi, I saw your preview and would like to know more about the Google review QR code for {business}.",
        "demo_points": ["A QR code for every table and the counter, ready to print",
                        "Your payment link right next to it (PayPal, Square, Stripe ...)",
                        "Within Google's rules: every guest asked the same way, no discounts",
                        "Change the links any time without reprinting"],
        "your_business": "Your restaurant",
    },
}

ICON_STAR = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2.8l2.8 5.9 6.4.8-4.7 4.4'
             ' 1.2 6.4L12 17.2l-5.7 3.1 1.2-6.4L2.8 9.5l6.4-.8z"/></svg>')
ICON_CARD = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0'
             ' 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm1 4v8h16V9H4zm0-2h16V7H4z"/></svg>')
ICON_MENU = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4 6h16v2H4zm0 5h16v2H4zm0 5h10v2H4z"/>'
             '</svg>')

HEADERS = """/*
  Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'
  Referrer-Policy: strict-origin-when-cross-origin
  X-Content-Type-Options: nosniff
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
"""


class BuildError(ValueError):
    pass


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def check_url(url: str, what: str, hosts: set[str] | None = None, allow_any: bool = False) -> str:
    url = str(url or "").strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise BuildError(f"{what}: must be an https:// link, got {url!r}")
    if hosts is not None and not allow_any and parts.hostname.lower() not in hosts:
        raise BuildError(f"{what}: {parts.hostname} is not a known {what} address (set allow_any_host if it is right)")
    if what == "review_url" and parts.hostname.lower() in ("www.google.com", "google.com") and not parts.path.startswith("/maps"):
        raise BuildError("review_url: a google.com link must be a Maps link")
    return url


def load_business(path: Path) -> dict:
    b = json.loads(path.read_text(encoding="utf-8"))
    bid = str(b.get("id") or "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", bid):
        raise BuildError(f"{path.name}: id must be lowercase letters, digits and dashes (it is printed in the QR code)")
    if not str(b.get("name") or "").strip():
        raise BuildError(f"{path.name}: name is missing")
    langs = [lang for lang in (b.get("languages") or ["de", "en"]) if lang in LANGS]
    if not langs:
        raise BuildError(f"{path.name}: languages must include de and/or en")
    b["languages"] = langs
    b["review_url"] = check_url(b.get("review_url"), "review_url", REVIEW_HOSTS)
    if b.get("menu_url"):
        b["menu_url"] = check_url(b["menu_url"], "menu_url")
    pay = b.get("payment")
    if pay:
        pay["url"] = check_url(pay.get("url"), "payment", PAYMENT_HOSTS, allow_any=bool(pay.get("allow_any_host")))
    color = str(b.get("brand_color") or "#1f6f50")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise BuildError(f"{path.name}: brand_color must look like #1f6f50")
    b["brand_color"] = color
    return b


def page(lang: str, title: str, body: str, css: list[str], scripts: list[str], footer: str) -> str:
    links = "".join(f'<link rel="stylesheet" href="{esc(h)}">' for h in css)
    js = "".join(f'<script src="{esc(s)}" defer></script>' for s in scripts)
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="noindex"><meta name="referrer" content="strict-origin-when-cross-origin">'
            f'<title>{esc(title)}</title>{links}{js}</head><body>{body}{footer}</body></html>\n')


def footer_html(lang: str, prefix: str) -> str:
    t = T[lang]
    imprint, privacy = ("impressum.html", "datenschutz.html") if lang == "de" else ("legal.html", "privacy.html")
    return f'<footer><a href="{prefix}{imprint}">{t["imprint"]}</a><a href="{prefix}{privacy}">{t["privacy"]}</a></footer>'


def business_page(b: dict, lang: str, other: str | None) -> str:
    t = T[lang]
    pay = b.get("payment")
    parts = [f'<main><div class="card"><h1>{esc(b["name"])}</h1>',
             f'<p class="lead">{esc(t["welcome"])} {esc(t["lead_pay"] if pay else t["lead_nopay"])}</p>',
             f'<p class="hint" role="status">{esc(t["hint_pay"] if pay else t["hint_nopay"])}</p>']
    if pay:
        label = f' ({esc(pay.get("label"))})' if pay.get("label") else ""
        parts.append(f'<a id="pay" class="btn primary" href="{esc(pay["url"])}">{ICON_CARD}{esc(t["pay"])}{label}</a>')
    parts.append(f'<a id="review" class="btn{"" if pay else " primary"}" href="{esc(b["review_url"])}" target="_blank" '
                 f'rel="noopener">{ICON_STAR}{esc(t["review"])}</a>')
    if not pay:
        parts.append(f'<p class="note">{esc(b.get("pay_note") or t["pay_counter"])}</p>')
    if b.get("menu_url"):
        parts.append(f'<a id="menu" class="btn" href="{esc(b["menu_url"])}">{ICON_MENU}{esc(t["menu"])}</a>')
    parts.append(f'<p class="note">{esc(t["optional"])}</p></div>')
    if other:
        parts.append(f'<p class="lang"><a href="{other}.html" hreflang="{other}">{t["other_lang"]}</a></p>')
    parts.append("</main>")
    return page(lang, b["name"], "".join(parts), ["../../assets/r.css", "brand.css"], ["../../assets/r.js"],
                footer_html(lang, "../../"))


def thanks_page(b: dict, lang: str) -> str:
    t = T[lang]
    body = (f'<main><div class="card"><h1>{esc(b["name"])}</h1><p class="thanks">{esc(t["thanks_title"])}</p>'
            f'<p class="lead">{esc(t["thanks_text"])}</p>'
            f'<a id="review" class="btn primary" href="{esc(b["review_url"])}" target="_blank" rel="noopener">'
            f'{ICON_STAR}{esc(t["review"])}</a><p class="note">{esc(t["optional"])}</p></div></main>')
    return page(lang, b["name"], body, ["../../assets/r.css", "brand.css"], [], footer_html(lang, "../../"))


def demo_page(site: dict, lang: str) -> str:
    t = T[lang]
    wa = re.sub(r"\D", "", str(site.get("whatsapp") or ""))
    name = f'<span data-business>{esc(t["your_business"])}</span>'
    points = "".join(f"<li>{esc(p)}</li>" for p in t["demo_points"])
    banner = esc(t["demo_banner"]).replace("{name}", name)
    cta = (f'<a id="whatsapp" class="btn primary" href="https://wa.me/{wa}" data-template="{esc(t["demo_wa"])}" '
           f'target="_blank" rel="noopener">{esc(t["demo_cta"])}</a>' if wa else "")
    body = (f'<main><p class="demo-banner">{banner}</p><div class="card"><h1 data-business>{esc(t["your_business"])}</h1>'
            f'<p class="lead">{esc(t["welcome"])} {esc(t["lead_pay"])}</p>'
            f'<a class="btn primary" href="#" aria-disabled="true">{ICON_CARD}{esc(t["pay"])}</a>'
            f'<a class="btn" href="#" aria-disabled="true">{ICON_STAR}{esc(t["review"])}</a>'
            f'<p class="note">{esc(t["optional"])}</p></div>'
            f'<div class="card"><ul>{points}</ul>{cta}</div></main>')
    return page(lang, f'{t["your_business"]} | {site.get("brand") or ""}', body, ["../assets/r.css"], ["../assets/demo.js"],
                footer_html(lang, "../"))


def legal_pages(site: dict) -> dict[str, str]:
    o = site.get("operator") or {}
    who = (f'<p>{esc(o.get("name"))}<br>{esc(site.get("brand"))}<br>{esc(o.get("street"))}<br>{esc(o.get("city"))}<br>'
           f'{esc(o.get("country"))}</p><p>E-Mail: {esc(o.get("email"))}<br>Telefon: {esc(o.get("phone"))}</p>')
    who_en = who.replace("Telefon:", "Phone:")
    host = esc(site.get("hosting") or "Cloudflare")
    impressum = (f'<main class="legal"><div class="card"><h1>Impressum</h1><p>Angaben gemäß § 5 DDG</p>{who}'
                 '<h2>Hinweis</h2><p>Diese Seiten werden von uns im Auftrag der genannten Gastronomiebetriebe bereitgestellt. '
                 'Zahlungen und Bewertungen laufen ausschließlich über die verlinkten Anbieter (z. B. PayPal, Google).</p></div></main>')
    datenschutz = (
        f'<main class="legal"><div class="card"><h1>Datenschutzerklärung</h1><h2>Verantwortlicher</h2>{who}'
        '<h2>Was wir verarbeiten</h2><p>Diese Seiten setzen keine Cookies, speichern nichts auf Ihrem Gerät und enthalten '
        'keine Analyse- oder Werbedienste. Beim Aufruf verarbeitet unser Hosting-Anbieter '
        f'({host}) technisch notwendige Daten (IP-Adresse, Zeitpunkt, aufgerufene Seite, Browser) in Server-Protokollen, '
        'um die Seiten sicher auszuliefern (Art. 6 Abs. 1 lit. f DSGVO). Diese Protokolle werden nach kurzer Zeit gelöscht.</p>'
        '<h2>Links zu anderen Anbietern</h2><p>Wenn Sie auf „Bewertung auf Google schreiben“ oder „Rechnung bezahlen“ tippen, '
        'verlassen Sie diese Seite. Dort gelten die Datenschutzbestimmungen von Google bzw. des Zahlungsanbieters.</p>'
        '<h2>Ihre Rechte</h2><p>Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, '
        'Widerspruch und Datenübertragbarkeit sowie das Recht, sich bei einer Datenschutz-Aufsichtsbehörde zu beschweren.</p>'
        '<h2>Geschäftskontakte</h2><p>Kontaktdaten von Unternehmen, die wir aus öffentlichen Quellen (Website des Unternehmens, '
        'OpenStreetMap, Overture Maps) erhalten, nutzen wir, um einmal per Brief unser Angebot vorzustellen '
        '(Art. 6 Abs. 1 lit. f DSGVO). Widersprechen Sie jederzeit formlos per E-Mail - wir löschen die Daten dann.</p>'
        '</div></main>')
    legal_en = (f'<main class="legal"><div class="card"><h1>Legal notice</h1>{who_en}'
                '<p>We provide these pages on behalf of the businesses shown. Payments and reviews go directly to the linked '
                'providers (e.g. PayPal, Google).</p></div></main>')
    privacy_en = (
        f'<main class="legal"><div class="card"><h1>Privacy</h1><h2>Who is responsible</h2>{who_en}'
        '<h2>What we process</h2><p>These pages set no cookies, store nothing on your device and contain no analytics or '
        f'advertising. Our hosting provider ({host}) processes technically necessary data (IP address, time, page, browser) '
        'in server logs to deliver the pages securely; the logs are deleted after a short time.</p>'
        '<h2>Links to other providers</h2><p>When you tap "Write a Google review" or "Pay the bill" you leave this page; '
        "Google's or the payment provider's privacy terms apply there.</p>"
        '<h2>Your rights</h2><p>You may ask for access, correction or deletion, object to processing, and complain to a data '
        'protection authority.</p></div></main>')
    out = {}
    for name, lang, body, title in (("impressum.html", "de", impressum, "Impressum"),
                                    ("datenschutz.html", "de", datenschutz, "Datenschutz"),
                                    ("legal.html", "en", legal_en, "Legal notice"),
                                    ("privacy.html", "en", privacy_en, "Privacy")):
        out[name] = page(lang, title, body, ["assets/r.css"], [], footer_html(lang, ""))
    return out


def qr_svg(url: str) -> str | None:
    try:
        import segno
    except ImportError:
        return None
    import io

    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=10, border=2, dark="#111111")
    return buf.getvalue().decode("utf-8")


def build(out: Path, preview: bool = False, site_path: Path | None = None, businesses_dir: Path | None = None) -> dict:
    site = json.loads((site_path or HERE / "site.json").read_text(encoding="utf-8"))
    if not preview:
        missing = [k for k, v in _flat(site) if "FILL_IN" in str(v)]
        if missing:
            raise BuildError("site.json still has FILL_IN in: " + ", ".join(missing) + " (or build with --preview)")
    businesses = [load_business(p) for p in sorted((businesses_dir or HERE / "businesses").glob("*.json"))]
    ids = [b["id"] for b in businesses]
    if len(ids) != len(set(ids)):
        raise BuildError("two business files use the same id")
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    for f in (HERE / "assets").iterdir():
        shutil.copy(f, out / "assets" / f.name)
    base = str(site.get("base_url") or "").rstrip("/")
    for b in businesses:
        d = out / "r" / b["id"]
        d.mkdir(parents=True)
        (d / "brand.css").write_text(f":root {{ --brand: {b['brand_color']}; }}\n", encoding="utf-8")
        langs = b["languages"]
        for i, lang in enumerate(langs):
            other = next((x for x in langs if x != lang), None)
            html_text = business_page(b, lang, other)
            (d / f"{lang}.html").write_text(html_text, encoding="utf-8")
            if i == 0:
                (d / "index.html").write_text(html_text, encoding="utf-8")
                (d / "thanks.html").write_text(thanks_page(b, lang), encoding="utf-8")
            (d / f"thanks-{lang}.html").write_text(thanks_page(b, lang), encoding="utf-8")
        svg = qr_svg(f"{base}/r/{b['id']}/") if base and "FILL_IN" not in base else None
        if svg:
            (d / "qr.svg").write_text(svg, encoding="utf-8")
    (out / "demo").mkdir()
    lang0 = site.get("default_language") if site.get("default_language") in LANGS else "en"
    for lang in LANGS:
        text = demo_page(site, lang)
        (out / "demo" / f"{lang}.html").write_text(text, encoding="utf-8")
        if lang == lang0:
            (out / "demo" / "index.html").write_text(text, encoding="utf-8")
    for name, text in legal_pages(site).items():
        (out / name).write_text(text, encoding="utf-8")
    (out / "index.html").write_text(page(lang0, site.get("brand") or "", '<main><div class="card"><h1>'
                                         f'{esc(site.get("brand"))}</h1><p class="lead">{T[lang0]["home_lead"]} '
                                         f'<a href="demo/">{T[lang0]["home_link"]}</a></p></div></main>', ["assets/r.css"], [],
                                         footer_html(lang0, "")), encoding="utf-8")
    (out / "_headers").write_text(HEADERS, encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /r/\n", encoding="utf-8")
    return {"businesses": ids, "out": str(out), "base_url": base if base and "FILL_IN" not in base else ""}


def _flat(d, prefix=""):
    for k, v in d.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            yield from _flat(v, prefix + k + ".")
        else:
            yield prefix + k, v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(HERE / "public"))
    ap.add_argument("--preview", action="store_true", help="build even while site.json still has FILL_IN values")
    args = ap.parse_args(argv)
    try:
        res = build(Path(args.out), preview=args.preview)
    except (BuildError, json.JSONDecodeError) as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"built {len(res['businesses'])} business pages into {res['out']}: {', '.join(res['businesses'])}")
    if res["base_url"]:
        print("QR codes point to <base_url>/r/<id>/. Where the payment provider can send guests back after paying "
              "(Stripe/Square payment links), use:")
        for bid in res["businesses"]:
            print(f"  {bid}: {res['base_url']}/r/{bid}/thanks.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
