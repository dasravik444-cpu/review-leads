"""Review requests to a customer's guests: only guests who agreed, everyone asked the same neutral way, nobody
twice, STOP honoured, and the paid API path sends exactly the approved template. Synthetic guests only."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import pytest

from guests import review_requests as rr

BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=BERLIN)
GUESTS = [
    "Anna Schmidt;0151 23456789;08.10.2026 19:30;ja;de",
    "Ben Meyer;0152 34567890;08.10.2026 20:00;;de",                 # did not agree
    "Cara Jones;+44 7911 123456;2026-10-08 18:00;2026-10-08;en",    # agreed (date), English
    "Dora;0151 1;08.10.2026 18:00;ja;de",                           # number not valid
    "Emil;0160 98765432;01.09.2026;ja;de",                          # visit too long ago
    "Finn;0170 1234567;09.10.2026 11:00;ja;de",                     # an hour ago: next run
]


def business(tmp_path: Path, **extra) -> Path:
    d = tmp_path / "businesses"
    d.mkdir(exist_ok=True)
    b = {"id": "test-cafe", "name": "Café Test", "languages": ["de", "en"],
         "review_url": "https://g.page/r/CtestReviewId/review", "payment": None, **extra}
    (d / "test-cafe.json").write_text(json.dumps(b), encoding="utf-8")
    return d


def guest_list(tmp_path: Path, rows, header="Name;Telefon;Besuch;Einwilligung;Sprache") -> Path:
    p = tmp_path / "guests.csv"
    p.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p


def go(tmp_path, rows=GUESTS, now=NOW, **kw):
    if "businesses_dir" not in kw:
        kw["businesses_dir"] = business(tmp_path)
    return rr.run("test-cafe", guest_list(tmp_path, rows), state_dir=tmp_path / "state", out_dir=tmp_path / "out",
                  now=now, **kw)


def test_only_guests_who_agreed_are_asked_and_each_only_once(tmp_path):
    res = go(tmp_path)
    assert res["to_ask"] == 2
    assert res["skipped"] == {"no WhatsApp consent": 1, "phone number not valid": 1, "visit more than 7 days ago": 1,
                              "too early (2 hours after the visit)": 1}
    page = unquote(Path(res["page"]).read_text(encoding="utf-8"))
    assert "https://wa.me/4915123456789?text=Hallo Anna, danke für Ihren Besuch bei Café Test!" in page
    assert "https://wa.me/447911123456?text=Hi Cara, thanks for visiting Café Test!" in page
    assert "https://g.page/r/CtestReviewId/review" in page and "STOP" in page
    assert "4915234567890" not in page                                  # Ben never agreed
    assert "Bewertungsanfragen: 2" in page and "Ben Meyer - keine Einwilligung" in page
    # The next run (Finn's visit is now 2 hours ago) asks only Finn: nobody is asked twice.
    res2 = go(tmp_path, now=NOW.replace(hour=14))
    assert res2["to_ask"] == 1 and res2["skipped"]["already asked"] == 2
    assert "wa.me/491701234567" in Path(res2["page"]).read_text(encoding="utf-8")


def test_stop_list_and_the_latest_visit_win(tmp_path):
    stop = tmp_path / "stop.txt"
    stop.write_text("+49 151 23456789\n", encoding="utf-8")
    rows = ["Anna;0151 23456789;08.10.2026 19:30;ja;de",
            "Cara;+44 7911 123456;05.10.2026 18:00;ja;en",
            "Cara;+44 7911 123456;08.10.2026 18:00;nein;en"]               # her latest booking says no
    res = go(tmp_path, rows, stop_file=stop)
    assert res["to_ask"] == 0
    assert res["skipped"] == {"answered STOP": 1, "same guest listed again": 1, "no WhatsApp consent": 1}
    state = json.loads((tmp_path / "state" / "test-cafe.json").read_text())
    assert state["stop"] == ["+4915123456789"]


def test_english_headers_commas_and_us_dates(tmp_path):
    bdir = business(tmp_path, country="US", timezone="America/Chicago", languages=["en"])
    rows = ["Dana Lee,(512) 555-0147,10/08/2026 19:00,yes", "Eli,512-555-0199,10/08/2026,no"]
    p = tmp_path / "g.csv"
    p.write_text("Guest,Phone,Visit Date,Opt-In\n" + "\n".join(rows) + "\n", encoding="utf-8")
    res = rr.run("test-cafe", p, state_dir=tmp_path / "s", out_dir=tmp_path / "o", businesses_dir=bdir,
                 now=datetime(2026, 10, 9, 12, 0, tzinfo=ZoneInfo("America/Chicago")))
    assert res["to_ask"] == 1
    page = Path(res["page"]).read_text(encoding="utf-8")
    assert "wa.me/15125550147?text=Hi%20Dana" in page
    assert "Review requests: 1" in page and "Row 3: Eli - no WhatsApp consent" in page   # the restaurant's language


def test_texts_that_buy_steer_or_filter_reviews_are_refused(tmp_path):
    for text in ("Hallo{name}, 10 % Rabatt für eine Bewertung: {link}", "Hi{name}, leave us 5 stars: {link}",
                 "Hi{name}, if you enjoyed your meal, review us: {link}", "Hallo{name}, bewerten Sie uns!"):
        with pytest.raises(rr.GuestError):
            go(tmp_path, businesses_dir=business(tmp_path, whatsapp_text={"de": text}))
    own = "Hallo{name}! Wie war es bei {business}? Erzählen Sie es anderen: {link} (STOP = keine Nachrichten mehr)"
    res = go(tmp_path, businesses_dir=business(tmp_path, whatsapp_text={"de": own}))
    assert "Hallo Anna! Wie war es bei Café Test?" in unquote(Path(res["page"]).read_text(encoding="utf-8"))


def test_names_are_shown_as_text(tmp_path):
    res = go(tmp_path, ["<img src=x onerror=alert(1)>;0151 23456789;08.10.2026 19:30;ja;de"])
    page = Path(res["page"]).read_text(encoding="utf-8")
    assert "<img" not in page and "&lt;img src=x onerror=alert(1)&gt;" in page


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self._payload, self.text = status, payload, json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, status=200):
        self.calls, self.status = [], status

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append((url, json, headers))
        return FakeResponse(self.status, {"messages": [{"id": f"wamid.{len(self.calls)}"}]} if self.status == 200
                            else {"error": {"message": "Invalid OAuth access token"}})


ENV = {"WHATSAPP_TOKEN": "t0ken", "WHATSAPP_PHONE_NUMBER_ID": "1234567890"}


def test_api_sends_the_approved_template_to_each_guest(tmp_path):
    session = FakeSession()
    res = go(tmp_path, send=True, session=session, env=ENV, sleep=lambda s: None)
    assert res["sent"] == 2 and res["failed"] == []
    url, body, headers = session.calls[0]
    assert url == "https://graph.facebook.com/v23.0/1234567890/messages" and headers["Authorization"] == "Bearer t0ken"
    assert body["to"] == "4915123456789" and body["template"]["name"] == "review_request"
    assert body["template"]["language"] == {"code": "de"}
    assert [p["text"] for p in body["template"]["components"][0]["parameters"]] == [
        "Anna", "Café Test", "https://g.page/r/CtestReviewId/review"]
    assert session.calls[1][1]["template"]["language"] == {"code": "en"}
    assert go(tmp_path, send=True, session=FakeSession(), env=ENV, sleep=lambda s: None)["sent"] == 0   # not twice


def test_api_stops_on_a_bad_token_and_keeps_quiet_hours(tmp_path):
    session = FakeSession(status=401)
    res = go(tmp_path, send=True, session=session, env=ENV, sleep=lambda s: None)
    assert res["sent"] == 0 and len(session.calls) == 1 and res["failed"][0]["error"].startswith("HTTP 401")
    state = json.loads((tmp_path / "state" / "test-cafe.json").read_text())
    assert state["asked"] == {}                                         # failed guests stay to be asked
    with pytest.raises(rr.GuestError, match="local time"):
        go(tmp_path, now=NOW.replace(hour=21), send=True, session=FakeSession(), env=ENV, sleep=lambda s: None)
    with pytest.raises(rr.GuestError, match="WHATSAPP_TOKEN"):
        go(tmp_path, send=True, session=FakeSession(), env={}, sleep=lambda s: None)


def test_up_to_three_reminders_on_days_2_5_and_9(tmp_path):
    from datetime import timedelta

    anna = ["Anna Schmidt;0151 23456789;08.10.2026 19:30;ja;de", "Cara Jones;+44 7911 123456;2026-10-08 18:00;ja;en"]
    other = ["Ben Meyer;0152 34567890;08.10.2026 20:00;;de"]          # later exports no longer list Anna and Cara
    first = go(tmp_path, anna)
    assert first["to_ask"] == 2 and first["reminders"] == 0
    pages = {}
    for d in range(1, 13):
        res = go(tmp_path, anna if d < 4 else other, now=NOW + timedelta(days=d))
        if res["reminders"]:
            assert res["reminders"] == res["to_ask"] == 2
            pages[d] = unquote(Path(res["page"]).read_text(encoding="utf-8"))
    assert sorted(pages) == [2, 5, 9]                                 # three reminders, then nothing more
    assert "Erinnerung 1" in pages[2] and "Erinnerung 3" in pages[9]
    assert "wa.me/4915123456789?text=Hallo Anna, nur eine kurze Erinnerung" in pages[2]
    assert "wa.me/447911123456?text=Hi Cara, just a friendly reminder" in pages[5]
    assert "https://g.page/r/CtestReviewId/review" in pages[9] and "STOP" in pages[9]
    assert not rr.STEERING.search(rr.REMINDER_TEXTS["en"] + rr.REMINDER_TEXTS["de"])


def test_reminders_end_with_stop_a_review_or_the_business_setting(tmp_path):
    from datetime import timedelta

    rows = ["Anna;0151 23456789;08.10.2026 19:30;ja;de", "Cara;+44 7911 123456;2026-10-08 18:00;ja;en"]
    go(tmp_path, rows)
    stop = tmp_path / "stop.txt"
    stop.write_text("+49 151 23456789\n", encoding="utf-8")
    reviewed = tmp_path / "reviewed.txt"
    reviewed.write_text("+44 7911 123456\n", encoding="utf-8")
    res = go(tmp_path, rows, now=NOW + timedelta(days=2), stop_file=stop, reviewed_file=reviewed)
    assert res["to_ask"] == res["reminders"] == 0
    off = tmp_path / "off"
    off.mkdir()
    bdir = business(off, reminders=0)
    rr.run("test-cafe", guest_list(off, rows), state_dir=off / "state", out_dir=off / "out", now=NOW, businesses_dir=bdir)
    res = rr.run("test-cafe", guest_list(off, rows), state_dir=off / "state", out_dir=off / "out",
                 now=NOW + timedelta(days=2), businesses_dir=bdir)
    assert res["reminders"] == 0 and res["skipped"]["already asked"] == 2
