"""Running on your own computer: keys from .env, which cities come next, US working hours for the e-mails."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def local_run():
    spec = importlib.util.spec_from_file_location("local_run", ROOT / "scripts" / "local_run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["local_run"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_settings_are_read_without_overriding_and_the_key_file_is_found(tmp_path, monkeypatch):
    lr = local_run()
    monkeypatch.setattr(lr, "ROOT", tmp_path)
    for k in lr.KEYS + ("OUTREACH_NOTIFY_EMAIL", "PYTHONUTF8", "PYTHONIOENCODING"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OUTREACH_SENDER_PHONE", "+1 512 555 0100")            # already set: wins over the file
    (tmp_path / "settings.txt").write_text('\ufeff# comment\nRQ_SHEET_ID="1AbC"\nOUTREACH_GMAIL_ADDRESS=me@gmail.com\n'
                                           "OUTREACH_SENDER_PHONE=+91 1\nOUTREACH_NOTIFY_EMAIL=\n", encoding="utf-8")
    (tmp_path / ".env").write_text("RQ_SHEET_ID=other\nOUTREACH_POSTAL_ADDRESS=1 Main St\n", encoding="utf-8")
    missing = lr.load_env(tmp_path / "settings.txt", tmp_path / ".env")
    assert os.environ["RQ_SHEET_ID"] == "1AbC" and os.environ["OUTREACH_SENDER_PHONE"] == "+1 512 555 0100"
    assert os.environ["OUTREACH_POSTAL_ADDRESS"] == "1 Main St"              # from the second file
    assert "OUTREACH_NOTIFY_EMAIL" not in os.environ                         # empty values are not set
    assert missing == ["GOOGLE_SERVICE_ACCOUNT_FILE", "OUTREACH_GMAIL_APP_PASSWORD"]
    # the key file is found in the secrets folder whatever its name; other .json files are not taken for it
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "notes.json").write_text('{"a": 1}', encoding="utf-8")
    key = tmp_path / "secrets" / "review-leads-123456-abc.json"
    key.write_text(json.dumps({"type": "service_account", "client_email": "x@y.iam.gserviceaccount.com"}), encoding="utf-8")
    assert "GOOGLE_SERVICE_ACCOUNT_FILE" not in lr.load_env(tmp_path / "settings.txt")
    assert os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"] == str(key)


def test_cities_never_searched_come_first_then_the_oldest(tmp_path, monkeypatch):
    lr = local_run()
    monkeypatch.setattr(lr, "DATA", tmp_path)
    cities = ["austin", "miami", "boston", "denver"]
    for i, c in enumerate(["miami", "austin"]):                              # searched before: miami longest ago
        (tmp_path / f"{c}.sqlite").write_text("x")
        os.utime(tmp_path / f"{c}.sqlite", (1000 + i, 1000 + i))
    assert lr.next_cities(3, cities, done_elsewhere=[]) == ["boston", "denver", "miami"]
    assert lr.next_cities(3, cities, done_elsewhere=["boston"]) == ["denver", "boston", "miami"]
    monkeypatch.setattr(lr, "DATA", tmp_path / "empty")
    first = lr.next_cities(15)                                  # a new computer: cities not yet in the Sheet first
    assert len(first) == 15 and not set(first) & set(lr._fleet_file()["searched_on_github"])


def test_emails_only_in_us_working_hours():
    lr = local_run()
    chi = ZoneInfo("America/Chicago")
    assert lr.us_working_hours(datetime(2026, 10, 12, 10, 0, tzinfo=chi))[0]                  # Monday morning
    assert not lr.us_working_hours(datetime(2026, 10, 12, 7, 0, tzinfo=chi))[0]               # too early
    assert not lr.us_working_hours(datetime(2026, 10, 10, 11, 0, tzinfo=chi))[0]              # Saturday
    ist = ZoneInfo("Asia/Kolkata")
    assert lr.us_working_hours(datetime(2026, 10, 12, 21, 0, tzinfo=ist))[0]                  # 9 PM in India


def test_unknown_city_stops_before_any_work(capsys):
    lr = local_run()
    code = lr.cmd_leads(type("A", (), {"cities": "atlantis", "count": 3, "minutes": 1.0, "hunt_minutes": 0.0})())
    assert code == 2 and "atlantis" in capsys.readouterr().out


def test_with_several_keys_the_one_that_opens_the_sheet_is_used(tmp_path, monkeypatch):
    lr = local_run()
    monkeypatch.setattr(lr, "ROOT", tmp_path)
    for k in lr.KEYS + ("PYTHONUTF8", "PYTHONIOENCODING"):
        monkeypatch.setenv(k, "x")                  # restored afterwards ...
        monkeypatch.delenv(k)                       # ... and absent during the test
    (tmp_path / "secrets").mkdir()
    for name, email in (("a-other-business.json", "robot@other-1.iam.gserviceaccount.com"),
                        ("b-review-leads.json", "sheet-writer@review-leads-1.iam.gserviceaccount.com")):
        (tmp_path / "secrets" / name).write_text(json.dumps({"type": "service_account", "client_email": email}))
    (tmp_path / "settings.txt").write_text("RQ_SHEET_ID=1AbC\n", encoding="utf-8")
    asked = []
    monkeypatch.setattr(lr, "opens_sheet", lambda key, sheet: asked.append((key.name, sheet)) or key.name[0] == "b")
    lr.load_env(tmp_path / "settings.txt")
    assert os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"] == str(tmp_path / "secrets" / "b-review-leads.json")
    assert asked == [("a-other-business.json", "1AbC"), ("b-review-leads.json", "1AbC")]
    assert [k.name for k in lr.key_files()] == ["a-other-business.json", "b-review-leads.json"]
    assert lr.key_email(tmp_path / "settings.txt") == ""


def test_import_takes_lead_lists_and_your_pdf_from_downloads(tmp_path, monkeypatch):
    lr = local_run()
    monkeypatch.setattr(lr, "DATA", tmp_path / "data")
    (tmp_path / "data").mkdir()
    downloads = tmp_path / "Download"
    downloads.mkdir()
    for name in ("leads-austin.zip", "leads-miami.csv", "plant-parlour-automation-1.json", "GuestEcho-overview (1).pdf"):
        (downloads / name).write_bytes(b"x")
    assert lr.attachment().name == "pitch.pdf"                       # until your own PDF is imported
    calls = []
    monkeypatch.setattr(lr, "leadgen", lambda *args: calls.append(args) or 0)
    a = type("A", (), {"folder": [str(downloads)], "dry_run": False})()
    assert lr.cmd_import(a) == 0
    assert lr.attachment() == tmp_path / "data" / "attachment.pdf"
    (cmd,) = calls
    assert cmd[0] == "import-leads" and [Path(f).name for f in cmd[3:]] == ["leads-austin.zip", "leads-miami.csv"]
