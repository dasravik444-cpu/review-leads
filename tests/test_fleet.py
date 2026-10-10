"""The US fleet: one campaign per city sharing one Google Sheet, only leads we can write to in the sheet, the
fleet's city plan, and the other English-speaking markets. Synthetic data only."""
from __future__ import annotations

import glob
import importlib.util
import itertools
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import tomllib
from conftest import make_config
from helpers import FakeHttp, FakeSheetsSession, _Resp
from test_open_data import GREEN_HOME, od_config, row, store
from test_outreach import SENDER, Clock, SmtpWorld, lead, runner, sheet_with

from leadgen import country
from leadgen.config import load_config
from leadgen.db import DB
from leadgen.enrich.emails import normalize_email
from leadgen.geo import haversine_km
from leadgen.outreach.store import OutreachStore
from leadgen.quality import is_chain
from leadgen.runner import Runner
from leadgen.sheets import LEAD_COLUMNS, REPORT_COLUMNS, SheetsClient, SheetsSync

ROOT = Path(__file__).resolve().parent.parent
US_CATEGORIES = {"restaurant", "cafe", "bar", "bakery", "salon", "gym", "hotel", "dental", "auto", "health", "pets",
                 "tattoo", "entertainment", "retail", "laundry"}


def fleet_matrix():
    spec = importlib.util.spec_from_file_location("fleet_matrix", ROOT / "scripts" / "ci" / "fleet_matrix.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fleet_matrix"] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ the city files
def test_us_city_files_share_one_sheet_and_never_overlap():
    files = [f for f in sorted(glob.glob(str(ROOT / "config" / "us" / "*.toml")))
             if not Path(f).name.startswith("_") and Path(f).stem not in ("fleet", "outreach")]
    assert len(files) >= 20
    cfgs = [load_config(f) for f in files]
    for cfg in cfgs:
        assert cfg["campaign"]["country"] == "US" and country.active().code == "US"
        assert {c["key"] for c in cfg.categories} == US_CATEGORIES       # shared list + the US switches merged
        assert next(c for c in cfg.categories if c["key"] == "dental")["overture"]
        sh = cfg["sheets"]
        assert (sh["leads_tab"], sh["plan_tab"], sh["report_tab"]) == ("Leads", "", "Daily Report")
        assert sh["require_any"] == ["email", "whatsapp", "phone"]      # every business we can reach somehow
    assert len({c["campaign"]["id"] for c in cfgs}) == len(cfgs)
    assert len({c["campaign"]["lead_id_prefix"] for c in cfgs}) == len(cfgs)
    for a, b in itertools.combinations(cfgs, 2):        # a business never belongs to two cities
        d = haversine_km(*a["area"]["center"], *b["area"]["center"])
        assert d >= a["area"]["radius_km"] + b["area"]["radius_km"], (a["campaign"]["id"], b["campaign"]["id"])
    fleet = tomllib.loads((ROOT / "config" / "us" / "fleet.toml").read_text())["cities"]
    assert sorted(fleet) == sorted(Path(f).stem for f in files)
    outreach = load_config(str(ROOT / "config" / "us" / "outreach.toml"))
    assert outreach["campaign"]["id"] == "us-outreach" and outreach["sheets"]["leads_tab"] == "Leads"


def test_fleet_runs_every_city_when_public_and_one_a_day_when_private():
    fm = fleet_matrix()
    fleet = tomllib.loads((ROOT / "config" / "us" / "fleet.toml").read_text())["cities"]
    pub = fm.plan("", private=False, budget="")
    assert pub["matrix"] == fleet and pub["parallel"] == min(15, len(fleet)) and pub["budget"] == 120
    day1, day2 = (fm.plan("", private=True, budget="", today=date(2026, 10, d)) for d in (8, 9))
    assert len(day1["matrix"]) == 1 and day1["matrix"] != day2["matrix"]           # cities take turns
    assert day1["parallel"] == 1 and day1["budget"] == 25
    named = fm.plan("austin, miami", private=True, budget="40")
    assert named == {"matrix": ["austin", "miami"], "parallel": 1, "budget": 40}
    try:
        fm.plan("atlantis", private=False, budget="")
        raise AssertionError("an unknown city must stop the run")
    except SystemExit as exc:
        assert "atlantis" in str(exc)


# ------------------------------------------------------------------ one sheet for many cities
def test_shared_sheet_has_no_plan_tab_and_a_campaign_column():
    sess = FakeSheetsSession()
    sync = SheetsSync(SheetsClient("sheet", session=sess), "Leads", "", "Daily Report")
    sync.ensure_tabs()
    assert "Plan" not in sess.tabs and {"Leads", "Daily Report"} <= set(sess.tabs)
    assert REPORT_COLUMNS[0] == "Campaign" and sess.tabs["Daily Report"]["rows"][0] == REPORT_COLUMNS
    sync.write_plan([[1, "Downtown"]])                                               # nothing to write to
    sync.append_report(["us-austin", "2026-10-08"])
    sync.append_report(["us-miami", "2026-10-08"])
    assert [r[0] for r in sess.tabs["Daily Report"]["rows"][1:]] == ["us-austin", "us-miami"]


class RacingSheets(FakeSheetsSession):
    """Another city's run creates the Leads tab between our look at the sheet and our 'add tab' request."""

    def request(self, method, url, timeout=None, params=None, json=None):
        path = urlsplit(url).path
        if method == "GET" and path.endswith("sheet") and "Leads" not in self.tabs:
            resp = super().request(method, url, timeout, params, json)
            self.tabs["Leads"] = {"id": 77, "rows": [list(LEAD_COLUMNS)]}
            return resp
        if method == "POST" and path.endswith(":batchUpdate"):
            for req in json["requests"]:
                title = req.get("addSheet", {}).get("properties", {}).get("title")
                if title and title in self.tabs:
                    self.raced = getattr(self, "raced", 0) + 1
                    return _Resp(400, {"error": {"message": f'Invalid requests[0].addSheet: A sheet with the name "{title}" '
                                                            "already exists. Please enter another name."}})
        return super().request(method, url, timeout, params, json)


def test_tab_created_by_another_city_at_the_same_moment_is_fine():
    sess = RacingSheets()
    sync = SheetsSync(SheetsClient("sheet", session=sess), "Leads", "", "Daily Report")
    sync.ensure_tabs()
    assert sess.raced == 1                                      # the other run won the race...
    assert sess.tabs["Leads"]["rows"][0] == LEAD_COLUMNS and "Daily Report" in sess.tabs   # ...and nothing broke


def test_sheet_gets_only_businesses_with_an_email_or_whatsapp(tmp_path):
    cfg = od_config(sheets={"require_any": ["email", "whatsapp"]})
    db = DB(str(tmp_path / "s.sqlite"))

    def world(method, url, params, data):
        host = urlsplit(url).hostname or ""
        if urlsplit(url).path == "/robots.txt":
            return (404, "", "text/html")
        if host == "www.greenleafcafe.in":
            return (200, GREEN_HOME, "text/html")
        return (404, "not found", "text/html")
    sess = FakeSheetsSession()
    factory = lambda: SheetsSync(SheetsClient("sheet", session=sess))
    code, s = Runner(cfg, db, http=FakeHttp(world), sheets_factory=factory, overture=store(db, cfg)).run()
    assert code == 0, s
    rows = [dict(zip(LEAD_COLUMNS, r)) for r in sess.tabs["Leads"]["rows"][1:] if any(str(x) for x in r)]
    assert rows and all(r["Emails"] or r["WhatsApp"] for r in rows)
    phone_only = db.scalar("SELECT COUNT(*) FROM places WHERE qualified=1 AND excluded IS NULL AND key NOT IN "
                           "(SELECT place_key FROM contacts WHERE kind IN ('email','whatsapp') AND confidence!='low')")
    assert phone_only > 0                                   # found and kept, but not in the sheet
    assert "Green Leaf Cafe" in {r["Business Name"] for r in rows}
    # a phone-only business that later shows an e-mail joins the sheet on the next sync
    key = db.one("SELECT key FROM places WHERE qualified=1 AND excluded IS NULL AND key NOT IN "
                 "(SELECT place_key FROM contacts WHERE kind='email')")["key"]
    db.add_contact(key, "email", "owner@example-bistro.com", source="website", source_url="https://example-bistro.com/",
                   confidence="high", evidence="test")
    Runner(cfg, db, http=FakeHttp(world), sheets_factory=factory, overture=store(db, cfg), discovery=False).run()
    keys = {r[LEAD_COLUMNS.index("Key")] for r in sess.tabs["Leads"]["rows"][1:] if any(str(x) for x in r)}
    assert key in keys


# ------------------------------------------------------------------ more English-speaking markets
def test_more_english_speaking_markets():
    rules = {c: country.use_country(c, "X").rules for c in ("CA", "IE", "NZ", "AE", "SG", "US")}
    assert rules["CA"].cold_email == "published_role" and rules["CA"].postal_address_required
    assert rules["IE"].cold_email == "companies_only" and rules["IE"].letters
    assert rules["NZ"].cold_email == "published_role"
    assert rules["AE"].cold_email == "allowed" and rules["AE"].cold_whatsapp == "manual_queue"
    assert rules["SG"].subject_prefix == "<ADV> "
    assert rules["US"].cold_whatsapp == "manual_queue"              # numbers a US business publishes as WhatsApp
    country.use_country("CA", "Toronto")
    assert country.postcodes("100 Queen St W, Toronto, ON M5H 2N2") == {"M5H2N2"}
    country.use_country("IE", "Dublin")
    assert country.postcodes("12 Grafton Street, Dublin 2, D02 X285") == {"D02X285"}
    country.use_country("AE", "Dubai")
    assert country.postcodes("Shop 4, Jumeirah Beach Road, Dubai 12345") == set()   # no postcodes in the UAE


def test_singapore_subjects_carry_the_adv_label(tmp_path):
    cfg = make_config(campaign={"country": "SG", "timezone": "Asia/Singapore", "language": "en", "region": "sg",
                                "lead_id_prefix": "SG"},
                      area={"name": "Singapore", "center": [1.2903, 103.8519], "radius_km": 3},
                      outreach={"sender": SENDER, "email": {"start_per_day": 5, "step": 0, "max_per_day": 40, "max_per_run": 8},
                                "whatsapp": {"start_per_day": 0, "step": 0, "max_per_day": 0, "include_mobiles": False}})
    _sess, client = sheet_with([lead(1, "Kopi Corner", email="hello@kopicorner.sg")])
    smtp = SmtpWorld()
    clock = Clock(datetime(2026, 10, 14, 11, 0, tzinfo=ZoneInfo("Asia/Singapore")).timestamp())
    code, s = runner(cfg, OutreachStore(str(tmp_path / "o.sqlite")), client, clock, smtp).run()
    assert code == 0, s
    assert [m["Subject"].startswith("<ADV> ") for m in smtp.sent] == [True]


# ------------------------------------------------------------------ mistakes found in the first Austin run
def test_mistakes_from_the_austin_sample_are_caught(tmp_path):
    cfg = load_config(str(ROOT / "config" / "us" / "austin.toml"))
    chains = cfg["filters"]["exclude_chains"]
    assert is_chain("Domino's Pizza", chains) == "domino" and is_chain("Dominos", chains) == "domino"
    assert is_chain("GO Car Wash", chains) == "go car wash"
    assert is_chain("Dominic's Pizzeria", chains) is None and is_chain("Gourmet Car Wash", chains) is None
    assert normalize_email("templates@wavesdesign.io") is None                      # the web designer's, in the footer
    assert normalize_email("trey@radiocoffeeandbeer.com") == "trey@radiocoffeeandbeer.com"
    st = store(DB(str(tmp_path / "s.sqlite")), cfg, rows=[row(1, "Vert-Align", "dentist")])
    assert st.category_for("dentist", "dentist", "Vert-Align", "vertalignchiropractic@gmail.com") == "health"
    assert st.category_for("dentist", "dentist", "Smile Studio", "hello@smilestudio.com") == "dental"
    assert st.category_for("dentist", "dentist", "Bright Dental & Chiropractic") == "dental"   # both: the code decides
    assert st.category_for("cafe", "cafe", "The Laundromat Cafe") == "cafe"                    # only between specialists


# ------------------------------------------------------------------ the sales PDF and the manual test send
def test_first_email_carries_the_pdf_and_a_manual_test_goes_out_after_hours(tmp_path):
    from leadgen.outreach.mailer import body_text

    pdf = tmp_path / "pitch.pdf"
    pdf.write_bytes(b"%PDF-1.4 two pages")
    sender = {**SENDER, "city": "", "postal_address": "1 Main St, Austin, TX 78701"}       # no city needed
    cfg = make_config(campaign={"country": "US", "timezone": "America/Chicago", "language": "en", "region": "us",
                                "lead_id_prefix": "US"},
                      area={"name": "Austin", "center": [30.27, -97.74], "radius_km": 3},
                      outreach={"sender": sender, "email": {"start_per_day": 5, "step": 0, "max_per_day": 40, "max_per_run": 8,
                                                            "window_start": "09:30", "window_end": "16:30"},
                                "whatsapp": {"start_per_day": 0, "step": 0, "max_per_day": 0, "include_mobiles": False}})
    _sess, client = sheet_with([lead(1, "Taco Town", email="hola@tacotown.com"), lead(2, "Brew Lab", email="hi@brewlab.com")])
    smtp = SmtpWorld()
    tz = ZoneInfo("America/Chicago")
    evening = Clock(datetime(2026, 10, 8, 19, 30, tzinfo=tz).timestamp())          # a Thursday, after sending hours
    db = str(tmp_path / "o.sqlite")
    code, s = runner(cfg, OutreachStore(db), client, evening, smtp, attach=str(pdf)).run()
    assert code == 0, s
    assert smtp.sent == []                                       # the timetable waits for business hours...
    code, s = runner(cfg, OutreachStore(db), client, evening, smtp, max_emails=1, attach=str(pdf)).run()
    assert code == 0, s
    [first] = smtp.sent                                          # ...a manual test run goes out right away
    assert [(a.get_filename(), a.get_content_type(), a.get_content()) for a in first.iter_attachments()] == \
        [("Green-Supply-Co-overview.pdf", "application/pdf", b"%PDF-1.4 two pages")]   # named after the sender's brand
    text = body_text(first)
    assert "attached a two-page overview (PDF)" in text and "$100" in text and "Ravi" in text
    assert "stand" not in text and "tap" not in text.replace("taps", "")         # a QR code only: nothing is shipped
    # three days later: the follow-up carries no attachment, a new first e-mail does
    later = Clock(datetime(2026, 10, 12, 16, 0, tzinfo=tz).timestamp())           # last run of the day: all due go out
    code, s = runner(cfg, OutreachStore(db), client, later, smtp, attach=str(pdf)).run()
    assert code == 0, s
    by_to = {m["To"]: m for m in smtp.sent[1:]}
    assert set(by_to) == {"hola@tacotown.com", "hi@brewlab.com"}
    assert by_to["hola@tacotown.com"]["Subject"].startswith("Re:") and not list(by_to["hola@tacotown.com"].iter_attachments())
    assert [a.get_filename() for a in by_to["hi@brewlab.com"].iter_attachments()] == ["Green-Supply-Co-overview.pdf"]
