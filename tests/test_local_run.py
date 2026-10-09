"""Running on your own computer: keys from .env, which cities come next, US working hours for the e-mails."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
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


def test_import_waits_for_the_robots_job_and_takes_the_pdf_at_once(tmp_path, monkeypatch, capsys):
    import threading

    lr = local_run()
    monkeypatch.setattr(lr, "DATA", tmp_path / "data")
    (tmp_path / "data").mkdir()
    downloads = tmp_path / "Download"
    downloads.mkdir()
    (downloads / "leads-austin.zip").write_bytes(b"x")
    (downloads / "GuestEcho-overview.pdf").write_bytes(b"%PDF new")
    calls = []
    monkeypatch.setattr(lr, "leadgen", lambda *args: calls.append(args) or 0)
    a = type("A", (), {"folder": [str(downloads)], "dry_run": False})()
    done = []
    monkeypatch.setenv("ROBOT_JOB", "1")
    with lr.job_lock("emails"):                             # the robot is sending e-mails
        monkeypatch.delenv("ROBOT_JOB")
        t = threading.Thread(target=lambda: done.append(lr.cmd_import(a)))
        t.start()
        for _ in range(100):
            if "Waiting: e-mail sending (the robot, since" in capsys.readouterr().out:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("the import did not say it waits")
        assert (tmp_path / "data" / "attachment.pdf").read_bytes() == b"%PDF new"   # the PDF did not wait
        assert not calls and t.is_alive()                                         # the Sheet part does
    t.join(10)
    assert done == [0] and calls and calls[0][0] == "import-leads"


def test_one_job_at_a_time_and_emails_paced_by_default(tmp_path, monkeypatch):
    import pytest

    lr = local_run()
    monkeypatch.setattr(lr, "DATA", tmp_path)
    monkeypatch.setenv("ROBOT_JOB", "1")
    with lr.job_lock("leads"):
        with pytest.raises(lr.Busy) as exc:                 # the robot's lead search holds it: a second job waits
            with lr.job_lock("emails"):
                pass
        assert str(exc.value).startswith("lead search (the robot, since ") and str(exc.value).endswith(" India time)")
    monkeypatch.delenv("ROBOT_JOB")
    with lr.job_lock("emails"):                             # free again afterwards
        assert "e-mail sending (typed by hand, since" in (tmp_path / "robot.lock").read_text()
    calls = []
    monkeypatch.setattr(lr, "leadgen", lambda *a: calls.append(a) or 0)
    monkeypatch.setattr(lr, "us_working_hours", lambda: (True, "Monday 10:00 in Chicago"))
    args = {"dry_run": False, "now": False, "check": False, "max": None, "no_pdf": False, "copy_to": ""}
    run = lambda **k: lr.cmd_emails(type("A", (), {**args, **k})())  # noqa: E731
    run()
    assert "--max-emails" not in calls[-1] and "--attach" in calls[-1]          # this hour's share, PDF attached
    run(check=True)
    assert calls[-1][calls[-1].index("--max-emails") + 1] == "0"
    run(max=1, copy_to="me@example.com")
    assert calls[-1][calls[-1].index("--max-emails") + 1] == "1" and calls[-1][-1] == "me@example.com"


def test_hunt_starts_with_the_city_that_has_most_businesses_to_look_at(tmp_path, monkeypatch):
    from leadgen.db import DB

    lr = local_run()
    monkeypatch.setattr(lr, "DATA", tmp_path)
    now = 1.0
    for city, n in (("austin", 2), ("miami", 5), ("boston", 0)):
        db = DB(str(tmp_path / f"{city}.sqlite"))
        for i in range(n):
            db.conn.execute("INSERT INTO places(key,name,norm_name,provider,first_seen,updated_at,found_date,qualified) "
                            "VALUES(?,?,?,?,?,?,?,1)", (f"k{i}", f"B{i}", f"b{i}", "overture", now, now, "2026-10-10"))
        db.conn.commit()
        db.close()
    assert lr.not_yet_hunted(tmp_path / "miami.sqlite") == 5
    calls = []
    monkeypatch.setattr(lr, "leadgen", lambda *a: calls.append(a) or 0)
    assert lr.cmd_hunt(type("A", (), {"minutes": 60.0})()) == 0
    assert [c[2] for c in calls] == ["config/us/miami.toml", "config/us/austin.toml"]     # boston: nothing to do
    assert calls[0][-1] == "30"                                                            # half the time each


def test_a_test_email_lists_what_was_sent_and_claims_no_more_than_gmail_said(tmp_path, monkeypatch, capsys):
    lr = local_run()
    monkeypatch.setattr(lr, "DATA", tmp_path)
    monkeypatch.setattr(lr, "us_working_hours", lambda: (True, "Friday 11:38 in Chicago"))

    def fake_leadgen(*args, result="sent"):
        with open(os.environ["OUTREACH_SENT_CSV"], "w", encoding="utf-8") as fh:
            fh.write("Lead ID,Business,To,Result,Subject\n")
            fh.write(f"HOU-00008,Houston Tea & Beverage,tea@example.com,{result},Google reviews for Houston Tea\n")
        return 0
    monkeypatch.setattr(lr, "leadgen", fake_leadgen)
    args = {"dry_run": False, "now": False, "check": False, "max": 1, "no_pdf": False, "copy_to": "me@example.com"}
    assert lr.cmd_emails(type("A", (), args)()) == 0
    out = capsys.readouterr().out
    assert "HOU-00008  Houston Tea & Beverage  ->  tea@example.com  [sent]" in out
    assert "Gmail also took a blind copy of each for me@example.com" in out and "went to" not in out
    monkeypatch.setattr(lr, "leadgen", lambda *a: fake_leadgen(*a, result="invalid"))
    lr.cmd_emails(type("A", (), args)())
    assert "blind copy" not in capsys.readouterr().out                    # nothing went out: no copy either
