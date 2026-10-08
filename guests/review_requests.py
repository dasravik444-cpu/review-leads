"""Review requests to a customer's guests by WhatsApp - only to guests who said yes.

    python -m guests.review_requests demo-cafe guests.csv            one-tap page: free, staff press send
    python -m guests.review_requests demo-cafe guests.csv --send     WhatsApp Business Platform (paid per message)

The restaurant sends, from its own WhatsApp Business number, to its own guests; we only prepare the messages
(as its processor under GDPR Art. 28, see docs/COMPLIANCE.md). Rules built in:

- only guests who agreed to a WhatsApp message (the consent column). In Germany a review request is
  advertising (BGH VI ZR 225/17) and needs that consent; elsewhere consent is the safe basis too.
- everyone who agreed is asked the same neutral way: no "were you happy?" filter first and nothing offered in
  return (Google's review policy, FTC 16 CFR 465, CMA, ACCC). Own texts that offer something, ask for five
  stars or only ask happy guests are refused.
- one request per guest in 90 days, then at most 3 short reminders (days 2, 5 and 9 after it; the business setting
  "reminders" = 0-3). Nothing more after STOP, or once the guest has reviewed (--reviewed).
- from 2 hours to 7 days after the visit; through the API only between 10:00 and 20:00 local time.

The guest list is a CSV export (booking system, sign-up form or a sheet). Column names may be German or English:
name/Name, phone/Telefon/Handy, visit/Besuch/Datum, consent/Einwilligung/WhatsApp, language/Sprache.
The page and the state file hold guests' names and numbers: keep them on the restaurant's devices, never in git.
"""
from __future__ import annotations

import argparse
import csv
import html
import importlib.util
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import phonenumbers

ROOT = Path(__file__).resolve().parent.parent
BUSINESSES = ROOT / "site" / "businesses"

MIN_AFTER_VISIT = timedelta(hours=2)
MAX_AFTER_VISIT = timedelta(days=7)
ASK_AGAIN_AFTER = timedelta(days=90)
SEND_HOURS = (10, 20)                       # API sending window, local time of the business
REMINDER_DAYS = (2, 5, 9)                   # days after the first message; at most 3 reminders
MIN_REMINDER_GAP = timedelta(days=2)        # when the tool was not run for a while: reminders stay spaced out
GRAPH = "https://graph.facebook.com"

TEXTS = {
    "de": ("Hallo{name}, danke für Ihren Besuch bei {business}! Wenn Sie mögen, erzählen Sie anderen auf Google "
           "davon: {link} Ob kurz oder lang, Ihre ehrliche Meinung hilft. Keine Nachrichten mehr? Antworten Sie STOP."),
    "en": ("Hi{name}, thanks for visiting {business}! If you like, tell others about it on Google: {link} "
           "Short or long, your honest opinion helps. No more messages? Reply STOP."),
}
REMINDER_TEXTS = {
    "de": ("Hallo{name}, nur eine kurze Erinnerung, falls es untergegangen ist: Wenn Sie mögen, erzählen Sie anderen "
           "auf Google von Ihrem Besuch bei {business}: {link} Keine Nachrichten mehr? Antworten Sie STOP."),
    "en": ("Hi{name}, just a friendly reminder in case you missed it: if you have a moment, you can share your "
           "experience at {business} on Google here: {link} No more messages? Reply STOP."),
}
# Greeting when the guest list has no name (API templates cannot have an empty variable).
NO_NAME = {"de": "zusammen", "en": "there"}

# Texts must not buy, steer or filter reviews.
STEERING = re.compile(
    r"rabatt|gutschein|gratis|geschenk|verlos|gewinnspiel|\d+ ?%|discount|voucher|coupon|gift|giveaway|prize|raffle|"
    r"\b(5|f[üu]nf|five)[ -]?(sterne|stars?)\b|⭐|★|"
    r"wenn sie zufrieden|wenn es ihnen gefallen|if you (were|are) happy|if you enjoyed|if you liked", re.IGNORECASE)

COLUMNS = {
    "name": ("name", "vorname", "gast", "guest", "first name"),
    "phone": ("phone", "telefon", "handy", "mobil", "mobile", "tel", "nummer", "phone number", "whatsapp",
              "whatsapp number", "whatsapp nummer"),
    "visit": ("visit", "besuch", "datum", "date", "visit date", "reservierung", "reservation"),
    "consent": ("consent", "einwilligung", "zustimmung", "whatsapp ok", "whatsapp consent", "whatsapp einwilligung",
                "opt-in", "optin", "opt in"),
    "language": ("language", "sprache", "lang"),
}
YES = {"yes", "ja", "y", "j", "true", "1", "x", "✓", "✔", "ok", "opt-in", "opted in"}


class GuestError(ValueError):
    pass


@dataclass
class Guest:
    row: int
    name: str
    phone: str                 # E.164, "" when not valid
    visit: datetime | None
    consent: bool
    language: str


@dataclass
class Decision:
    guest: Guest
    reason: str = ""           # "" = ask this guest now
    later: bool = False        # not yet (too early): stays for a later run
    reminder: int = 0          # 1-3: a reminder after the first message (0 = the first message)

    @property
    def ok(self) -> bool:
        return not self.reason


# ----------------------------------------------------------------------------------------------- inputs
def load_business(bid: str, businesses_dir: Path | None = None) -> dict:
    """The customer's file from site/businesses/, checked the same way as for its QR page."""
    spec = importlib.util.spec_from_file_location("site_build", ROOT / "site" / "build.py")
    site_build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(site_build)
    path = (businesses_dir or BUSINESSES) / f"{bid}.json"
    if not path.exists():
        raise GuestError(f"no business file {path}")
    b = site_build.load_business(path)
    b.setdefault("country", "DE")
    b.setdefault("timezone", "Europe/Berlin")
    for key in ("whatsapp_text", "whatsapp_reminder_text"):
        for lang, t in (b.get(key) or {}).items():
            check_text(t, f"{key}.{lang}")
    return b


def max_reminders(b: dict) -> int:
    return max(0, min(len(REMINDER_DAYS), int(b.get("reminders", len(REMINDER_DAYS)))))


def check_text(text: str, what: str = "text") -> str:
    if "{link}" not in text:
        raise GuestError(f"{what}: must contain {{link}} (Google's review form)")
    m = STEERING.search(text)
    if m:
        raise GuestError(f"{what}: {m.group(0)!r} - a review request may not offer anything, ask for a rating or only "
                         "ask happy guests (docs/COMPLIANCE.md)")
    return text


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower().replace("_", " ").replace("-", " ")).replace("opt in", "opt-in")


def read_guests(path: Path, region: str, tz: ZoneInfo) -> list[Guest]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
    if not rows:
        return []
    found = {}
    headers = {_norm(h): h for h in rows[0] if h}
    for key, names in COLUMNS.items():
        for n in names:
            if _norm(n) in headers:
                found[key] = headers[_norm(n)]
                break
    for need in ("phone", "visit", "consent"):
        if need not in found:
            raise GuestError(f"{path.name}: no {need} column (accepted names: {', '.join(COLUMNS[need])})")
    out = []
    for i, r in enumerate(rows, start=2):
        cell = {key: (r.get(col) or "").strip() for key, col in found.items()}
        out.append(Guest(row=i, name=cell.get("name", ""), phone=parse_phone(cell["phone"], region),
                         visit=parse_visit(cell["visit"], tz, region), consent=consented(cell["consent"]),
                         language=cell.get("language", "").lower()[:2]))
    return out


def parse_phone(raw: str, region: str) -> str:
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return ""
    if not phonenumbers.is_valid_number(num):
        return ""
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def consented(value: str) -> bool:
    v = (value or "").strip().lower()
    return v in YES or bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}.*|\d{1,2}\.\d{1,2}\.\d{2,4}.*", v))  # a consent date


def parse_visit(value: str, tz: ZoneInfo, region: str = "DE") -> datetime | None:
    v = (value or "").strip().replace("T", " ")
    if not v:
        return None
    slash = "%m/%d/%Y" if region == "US" else "%d/%m/%Y"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d.%m.%y %H:%M", f"{slash} %H:%M"):
        try:
            return datetime.strptime(v[:19] if fmt.endswith("%S") else v, fmt).replace(tzinfo=tz)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", slash):
        try:
            # A date without a time counts as a late visit: the request goes out the next day.
            return datetime.strptime(v, fmt).replace(hour=22, tzinfo=tz)
        except ValueError:
            pass
    return None


# ----------------------------------------------------------------------------------------------- state
def load_state(path: Path) -> dict:
    if path.exists():
        s = json.loads(path.read_text(encoding="utf-8"))
    else:
        s = {}
    s.setdefault("asked", {})          # phone -> time of the first message
    s.setdefault("stop", [])
    s.setdefault("reminders", {})      # phone -> times of the reminders sent
    s.setdefault("guests", {})         # phone -> name and language (for reminders when the guest is not in the new list)
    s.setdefault("reviewed", [])       # phones of guests who reviewed: no more reminders
    return s


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def add_stops(state: dict, lines, region: str) -> int:
    n = 0
    for line in lines:
        e = parse_phone(line.strip(), region)
        if e and e not in state["stop"]:
            state["stop"].append(e)
            n += 1
    return n


# ----------------------------------------------------------------------------------------------- plan
def reminder_due(phone: str, state: dict, now: datetime, maximum: int) -> int:
    """The number of the reminder due now for a guest who got the first message (0 = none)."""
    if phone in state["reviewed"] or phone in state["stop"] or phone not in state["asked"]:
        return 0
    sent = state["reminders"].get(phone, [])
    k = len(sent)
    if k >= min(maximum, len(REMINDER_DAYS)):
        return 0
    if now < datetime.fromisoformat(state["asked"][phone]) + timedelta(days=REMINDER_DAYS[k]):
        return 0
    if sent and now < datetime.fromisoformat(sent[-1]) + MIN_REMINDER_GAP:
        return 0
    return k + 1


def plan(guests: list[Guest], state: dict, now: datetime, reminders: int = len(REMINDER_DAYS)) -> list[Decision]:
    # The same guest listed twice (two visits): only the latest visit counts.
    latest: dict[str, Guest] = {}
    for g in guests:
        if g.phone and g.visit and (g.phone not in latest or g.visit > latest[g.phone].visit):
            latest[g.phone] = g
    out = []
    reminded: set[str] = set()

    def recently_asked(phone: str) -> bool:
        return phone in state["asked"] and now - datetime.fromisoformat(state["asked"][phone]) < ASK_AGAIN_AFTER

    for g in guests:
        if not g.consent:
            out.append(Decision(g, "no WhatsApp consent"))
        elif not g.phone:
            out.append(Decision(g, "phone number not valid"))
        elif g.phone in state["stop"]:
            out.append(Decision(g, "answered STOP"))
        elif recently_asked(g.phone):
            r = 0 if g.phone in reminded else reminder_due(g.phone, state, now, reminders)
            if r:
                reminded.add(g.phone)
                out.append(Decision(g, reminder=r))
            else:
                out.append(Decision(g, f"already asked on {state['asked'][g.phone][:10]}"))
        elif not g.visit:
            out.append(Decision(g, "visit date missing or unreadable"))
        elif latest.get(g.phone) is not g:
            out.append(Decision(g, "same guest listed again"))
        elif now < g.visit + MIN_AFTER_VISIT:
            out.append(Decision(g, "too early (2 hours after the visit)", later=True))
        elif now > g.visit + MAX_AFTER_VISIT:
            out.append(Decision(g, "visit more than 7 days ago"))
        else:
            out.append(Decision(g))
    # Reminders for guests asked earlier who are not in this guest list.
    listed = {g.phone for g in guests if g.phone}
    for phone, info in state["guests"].items():
        if phone not in listed and recently_asked(phone):
            r = reminder_due(phone, state, now, reminders)
            if r:
                g = Guest(row=0, name=info.get("name", ""), phone=phone, visit=None, consent=True,
                          language=info.get("language", ""))
                out.append(Decision(g, reminder=r))
    return out


def language_for(g: Guest, b: dict) -> str:
    return g.language if g.language in b["languages"] else b["languages"][0]


TITLES = {"herr", "frau", "hr", "fr", "dr", "prof", "mr", "mrs", "ms", "miss"}


def first_name(name: str) -> str:
    """'Anna Schmidt' -> 'Anna'; 'Herr Müller' and 'Dr. Weber' keep the title and surname."""
    words = (name or "").split()
    if not words:
        return ""
    if words[0].lower().rstrip(".") in TITLES and len(words) > 1:
        return " ".join(words[:2] if words[1].lower().rstrip(".") not in TITLES else words[:3])[:40]
    return words[0][:40]


def message(b: dict, g: Guest, reminder: int = 0) -> str:
    lang = language_for(g, b)
    if reminder:
        text = (b.get("whatsapp_reminder_text") or {}).get(lang) or REMINDER_TEXTS[lang]
    else:
        text = (b.get("whatsapp_text") or {}).get(lang) or TEXTS[lang]
    name = first_name(g.name)
    return text.replace("{name}", f" {name}" if name else "").replace("{business}", b["name"]).replace("{link}", b["review_url"])


def wa_link(e164: str, text: str) -> str:
    return f"https://wa.me/{e164.lstrip('+')}?text={quote(text, safe='')}"


# ----------------------------------------------------------------------------------------------- outputs
PAGE = {
    "de": {"title": "Bewertungsanfragen", "guest": "Gast", "row": "Zeile", "skipped": "Nicht gefragt", "date": "%d.%m. %H:%M",
           "reminder": "Erinnerung {n}",
           "note": "Stand {now}. Tippen Sie auf „WhatsApp“, prüfen Sie den Text und senden Sie. Bitte alle senden, nicht "
                   "auswählen: Jeder Gast mit Einwilligung wird gleich gefragt (Google-Richtlinien). Wer mit STOP "
                   "antwortet, kommt auf die Stopp-Liste.",
           "reasons": {"no WhatsApp consent": "keine Einwilligung", "phone number not valid": "Nummer ungültig",
                       "answered STOP": "hat STOP geantwortet", "visit date missing or unreadable": "Besuchsdatum fehlt",
                       "same guest listed again": "doppelt (letzter Besuch zählt)",
                       "too early (2 hours after the visit)": "zu früh (2 Stunden nach dem Besuch)",
                       "visit more than 7 days ago": "Besuch länger als 7 Tage her", "already asked": "schon gefragt"}},
    "en": {"title": "Review requests", "guest": "Guest", "row": "Row", "skipped": "Not asked", "date": "%b %d, %H:%M",
           "reminder": "Reminder {n}",
           "note": "As of {now}. Tap “WhatsApp”, check the text and send. Please send them all, don't pick: every guest "
                   "who agreed is asked the same way (Google's rules). Anyone who replies STOP goes on the stop list.",
           "reasons": {}},
}


def one_tap_page(b: dict, decisions: list[Decision], now: datetime) -> str:
    esc = html.escape
    lang = b["languages"][0]
    t = PAGE[lang]
    todo = [d for d in decisions if d.ok]

    def reason(r: str) -> str:
        base = re.sub(r" on (\d{4}-\d{2}-\d{2})$", "", r)
        return t["reasons"].get(base, base) + (f" ({r[-10:]})" if base != r else "")

    def when(d: Decision) -> str:
        if d.reminder:
            return t["reminder"].replace("{n}", str(d.reminder))
        return d.guest.visit.strftime(t["date"]) if d.guest.visit else ""

    cards = "".join(
        f'<li><b>{esc(d.guest.name or t["guest"])}</b> <span>{esc(when(d))}</span>'
        f'<a href="{esc(wa_link(d.guest.phone, message(b, d.guest, d.reminder)))}" target="_blank" rel="noopener">WhatsApp</a></li>'
        for d in todo)
    skipped = "".join(f"<li>{t['row']} {d.guest.row}: {esc(d.guest.name or '-')} - {esc(reason(d.reason))}</li>"
                      for d in decisions if not d.ok)
    stamp = now.strftime("%d.%m.%Y %H:%M") if lang == "de" else now.strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>{t["title"]}: {esc(b["name"])}</title><style>
body{{font:16px/1.4 system-ui,sans-serif;margin:0;padding:16px;max-width:560px}}
ul{{list-style:none;padding:0}} li{{padding:10px 0;border-bottom:1px solid #ddd}}
li span{{color:#666;margin-left:6px}} li a{{float:right;background:#1f6f50;color:#fff;padding:6px 14px;border-radius:8px;text-decoration:none}}
.note{{color:#555;font-size:14px}}</style></head><body>
<h1>{esc(b["name"])}</h1><h2>{t["title"]}: {len(todo)}</h2>
<p class="note">{esc(t["note"].replace("{now}", stamp))}</p>
<ul>{cards}</ul>
<details><summary>{t["skipped"]} ({len(decisions) - len(todo)})</summary><ul>{skipped}</ul></details>
</body></html>
"""


def send_template(session, b: dict, g: Guest, token: str, phone_id: str, version: str, reminder: int = 0) -> tuple[bool, str]:
    """One approved template message through the WhatsApp Business Platform (Cloud API)."""
    lang = language_for(g, b)
    params = [first_name(g.name) or NO_NAME[lang], b["name"], b["review_url"]]
    name = (b.get("whatsapp_reminder_template") or "review_reminder") if reminder else \
        (b.get("whatsapp_template") or "review_request")
    body = {"messaging_product": "whatsapp", "to": g.phone.lstrip("+"), "type": "template",
            "template": {"name": name, "language": {"code": lang},
                         "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]}}
    r = session.post(f"{GRAPH}/{version}/{phone_id}/messages", json=body,
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code == 200:
        msgs = (r.json() or {}).get("messages") or [{}]
        return True, msgs[0].get("id", "")
    return False, f"HTTP {r.status_code}: {r.text[:300]}"


# ----------------------------------------------------------------------------------------------- run
def run(bid: str, guests_csv: Path, *, send: bool = False, state_dir: Path = Path("guests-state"),
        out_dir: Path = Path("guests-out"), stop_file: Path | None = None, reviewed_file: Path | None = None,
        now: datetime | None = None,
        businesses_dir: Path | None = None, session=None, env=os.environ, sleep=time.sleep, max_send: int = 200) -> dict:
    b = load_business(bid, businesses_dir)
    tz = ZoneInfo(b["timezone"])
    now = (now or datetime.now(tz)).astimezone(tz)
    state_path = state_dir / f"{bid}.json"
    state = load_state(state_path)
    if stop_file and stop_file.exists():
        add_stops(state, stop_file.read_text(encoding="utf-8").splitlines(), b["country"])
    if reviewed_file and reviewed_file.exists():
        for line in reviewed_file.read_text(encoding="utf-8").splitlines():
            e = parse_phone(line.strip(), b["country"])
            if e and e not in state["reviewed"]:
                state["reviewed"].append(e)
    decisions = plan(read_guests(guests_csv, b["country"], tz), state, now, max_reminders(b))
    todo = [d for d in decisions if d.ok]
    res = {"business": bid, "guests": len(decisions), "to_ask": len(todo), "reminders": sum(1 for d in todo if d.reminder),
           "sent": 0, "failed": [], "page": "", "skipped": {}}

    def record(d: Decision) -> None:
        if d.reminder:
            state["reminders"].setdefault(d.guest.phone, []).append(now.isoformat())
        else:
            state["asked"][d.guest.phone] = now.isoformat()
            state["guests"][d.guest.phone] = {"name": d.guest.name, "language": d.guest.language}
            state["reminders"].pop(d.guest.phone, None)       # a new first message starts a new schedule
    for d in decisions:
        if not d.ok:
            key = re.sub(r" on \d{4}-\d{2}-\d{2}$", "", d.reason)
            res["skipped"][key] = res["skipped"].get(key, 0) + 1

    if not send:
        out_dir.mkdir(parents=True, exist_ok=True)
        page = out_dir / f"{bid}-{now.strftime('%Y-%m-%d-%H%M')}.html"
        page.write_text(one_tap_page(b, decisions, now), encoding="utf-8")
        res["page"] = str(page)
        for d in todo:                      # prepared = asked: a guest is never asked twice by mistake
            record(d)
        save_state(state_path, state)
        return res

    token, phone_id = env.get("WHATSAPP_TOKEN", ""), env.get("WHATSAPP_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        raise GuestError("set WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID (the restaurant's WhatsApp Business "
                         "Platform number) to send, or leave out --send for the one-tap page")
    if not SEND_HOURS[0] <= now.hour < SEND_HOURS[1]:
        raise GuestError(f"outside {SEND_HOURS[0]}:00-{SEND_HOURS[1]}:00 local time - nothing sent")
    if session is None:
        import requests

        session = requests.Session()
    version = env.get("WHATSAPP_GRAPH_VERSION", "v23.0")
    for d in todo[:max_send]:
        ok, info = send_template(session, b, d.guest, token, phone_id, version, d.reminder)
        if ok:
            res["sent"] += 1
            record(d)
            save_state(state_path, state)
        else:
            res["failed"].append({"row": d.guest.row, "error": info})
            if info.startswith(("HTTP 401", "HTTP 403")):
                break                       # the token or number is wrong: every other message would fail too
        sleep(1.0)
    save_state(state_path, state)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("business", help="the customer's id (site/businesses/<id>.json)")
    ap.add_argument("guests", type=Path, help="CSV export of the guest list")
    ap.add_argument("--send", action="store_true", help="send through the WhatsApp Business Platform (paid per message)")
    ap.add_argument("--stop", type=Path, help="file with numbers that answered STOP (one per line)")
    ap.add_argument("--reviewed", type=Path, help="file with numbers of guests who already reviewed (no more reminders)")
    ap.add_argument("--state", type=Path, default=Path("guests-state"))
    ap.add_argument("--out", type=Path, default=Path("guests-out"))
    args = ap.parse_args(argv)
    try:
        res = run(args.business, args.guests, send=args.send, state_dir=args.state, out_dir=args.out, stop_file=args.stop,
                  reviewed_file=args.reviewed)
    except (GuestError, OSError, json.JSONDecodeError) as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        return 1
    print(f"{res['guests']} guests, {res['to_ask']} to ask now ({res['reminders']} of them reminders)"
          + (f", {res['sent']} sent, {len(res['failed'])} failed" if args.send else f": open {res['page']}"))
    for reason, n in sorted(res["skipped"].items()):
        print(f"  not asked: {n} x {reason}")
    for f in res["failed"]:
        print(f"  row {f['row']}: {f['error']}")
    return 0 if not res["failed"] else 2


if __name__ == "__main__":
    sys.exit(main())
