"""The robot's timetable (India time for the lead jobs, Chicago time for e-mails), its records, status and update."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
IST, CHI = ZoneInfo("Asia/Kolkata"), ZoneInfo("America/Chicago")


def robot(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("robot", ROOT / "scripts" / "robot.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["robot"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "DATA", tmp_path / "data")
    monkeypatch.setattr(mod, "LOGS", tmp_path / "data" / "logs")
    monkeypatch.setattr(mod, "STATUS", tmp_path / "data" / "robot-status.json")
    monkeypatch.setattr(mod, "STOP", tmp_path / "data" / "robot.stop")
    return mod


def at(tz, *args) -> float:
    return datetime(*args, tzinfo=tz).timestamp()


def test_timetable_india_for_leads_chicago_for_emails(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    # Saturday 10 Oct 2026, 13:05 in India: the lead search is due; no e-mails on a US Friday night/Saturday
    now = at(IST, 2026, 10, 10, 13, 5)
    assert r.pick_due(now, {}, {}).name == "update"                            # an update first, then the others
    assert r.pick_due(now, {"jobs": {"update": {"last_started": at(IST, 2026, 10, 10, 11, 0)}}}, {}).name == "leads"
    st = {"jobs": {"update": {"last_started": at(IST, 2026, 10, 10, 11, 0)},
                   "leads": {"last_started": at(IST, 2026, 10, 10, 13, 0, 30)},
                   "backup": {"last_started": at(IST, 2026, 10, 10, 0, 30)}}}
    assert r.pick_due(now, st, {}) is None                                      # done today
    assert r.pick_due(at(IST, 2026, 10, 10, 17, 31), st, {}).name == "hunt"
    # Monday 12 Oct 2026: 09:35 in Chicago (20:05 in India) the first e-mail run; 08:00 there nothing
    st["jobs"].update(hunt={"last_started": at(IST, 2026, 10, 12, 17, 30)}, leads={"last_started": at(IST, 2026, 10, 12, 13, 0)},
                      update={"last_started": at(IST, 2026, 10, 12, 11, 0)}, backup={"last_started": at(IST, 2026, 10, 12, 0, 30)})
    assert r.pick_due(at(CHI, 2026, 10, 12, 8, 0), st, {}) is None
    assert r.pick_due(at(CHI, 2026, 10, 12, 9, 36), st, {}).name == "emails"
    assert r.pick_due(at(CHI, 2026, 10, 10, 10, 0), {"jobs": {}}, {}).name != "emails"           # a US Saturday
    assert r.next_slot(r.JOBS["emails"], at(CHI, 2026, 10, 9, 16, 0)) == datetime(2026, 10, 12, 9, 35, tzinfo=CHI)
    # switched off in settings.txt, and a job that found the lock taken waits 5 minutes
    assert r.pick_due(now, {}, {"ROBOT_LEADS": "no", "ROBOT_AUTO_UPDATE": "no"}).name == "backup"
    assert r.pick_due(now, {"jobs": {"leads": {"retry_at": now + 60}}}, {"ROBOT_AUTO_UPDATE": "no"}).name == "backup"
    assert r.command(r.JOBS["leads"], {"ROBOT_CITIES_PER_DAY": "2"}) == (
        ["bash", "scripts/run.sh", "leads", "--count", "2", "--minutes", "60", "--hunt-minutes", "30"], 220)
    assert r.command(r.JOBS["emails"], {})[0] == ["bash", "scripts/run.sh", "emails"]   # paced: this hour's share


def test_a_job_is_recorded_and_a_busy_lock_means_try_again_soon(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    monkeypatch.setattr(r, "ROOT", tmp_path)
    monkeypatch.setattr(r, "command", lambda job, s: ([sys.executable, "-c", "print('working'); raise SystemExit(0)"], 1))
    r.run_job(r.JOBS["hunt"], {})
    rec = json.loads(r.STATUS.read_text())["jobs"]["hunt"]
    assert rec["result"] == "ok" and rec["last_started"] <= time.time() and json.loads(r.STATUS.read_text())["running"] is None
    assert "working" in r.log_path().read_text()
    monkeypatch.setattr(r, "command", lambda job, s: ([sys.executable, "-c", "raise SystemExit(3)"], 1))
    r.run_job(r.JOBS["leads"], {})
    rec = json.loads(r.STATUS.read_text())["jobs"]["leads"]
    assert "last_started" not in rec and rec["retry_at"] > time.time() + 200
    monkeypatch.setattr(r, "command", lambda job, s: ([sys.executable, "-c", "raise SystemExit(2)"], 1))
    r.run_job(r.JOBS["emails"], {})
    assert json.loads(r.STATUS.read_text())["jobs"]["emails"]["result"].startswith("failed (exit code 2)")
    code = "import os; print('robot job:', os.environ.get('ROBOT_JOB'))"
    monkeypatch.setattr(r, "command", lambda job, s: ([sys.executable, "-c", code], 1))
    r.run_job(r.JOBS["hunt"], {})
    assert "robot job: 1" in r.log_path().read_text()           # its Busy text says "the robot" (local_run)


def test_a_job_stopped_by_robot_off_runs_again_when_it_is_back_on(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    monkeypatch.setattr(r, "command", lambda job, s: (["true"], 1))
    monkeypatch.setattr(r, "run_command", lambda *a, **k: 143)
    at = datetime(2026, 10, 9, 14, 0, tzinfo=IST).timestamp()   # an hour after the 13:00 lead search began
    r.save_status({"jobs": {"leads": {"last_started": at - 86400, "result": "ok"}}})
    r.run_job(r.JOBS["leads"], {})
    rec = json.loads(r.STATUS.read_text())["jobs"]["leads"]
    assert rec["last_started"] == at - 86400 and rec["result"] == "stopped (robot off) - runs again when on"
    switches = {"ROBOT_AUTO_UPDATE": "no", "ROBOT_EMAILS": "no"}
    assert r.pick_due(at, r.load_status(), switches).name == "leads"      # today's slot is still due


def test_status_shows_jobs_and_the_leads_per_city(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    from leadgen.db import DB
    from leadgen.outreach.store import OutreachStore

    (tmp_path / "data").mkdir()
    db = DB(str(tmp_path / "data" / "austin.sqlite"))
    now = time.time()
    for i in range(4):
        db.conn.execute("INSERT INTO places(key,name,norm_name,provider,first_seen,updated_at,found_date,qualified) "
                        "VALUES(?,?,?,?,?,?,?,1)", (f"k{i}", f"B{i}", f"b{i}", "overture", now, now, "2026-10-10"))
    for i, kind, value in [(0, "email", "a@b.com"), (1, "email", "c@d.com"), (0, "phone", "+15125550100"),
                           (1, "phone", "+15125550101"), (2, "phone", "+15125550102"), (3, "email", "x@y.com")]:
        conf = "low" if i == 3 else "high"                          # an unverified address does not count
        db.conn.execute("INSERT INTO contacts(place_key,kind,value,source,confidence,found_at) VALUES(?,?,?,?,?,?)",
                        (f"k{i}", kind, value, "website", conf, now))
    db.conn.commit()
    store = OutreachStore(str(tmp_path / "data" / "outreach.sqlite"))
    today = datetime.now(CHI).date().isoformat()
    store.conn.execute("INSERT INTO sends(email,lead_key,step,sent_at,day,status) VALUES('a@b.com','k0',1,?,?,'sent')", (now, today))
    store.conn.execute("INSERT INTO replies(email,kind,received_at) VALUES('a@b.com','positive',?)", (now,))
    store.conn.commit()
    r.save_status({"scheduler": {"heartbeat": now, "started": now, "version": "abc1234"},
                   "jobs": {"leads": {"last_started": now - 3600, "result": "ok"}}})
    text = r.status_text(now)
    assert "Robot: RUNNING" in text and "abc1234" in text
    row = next(line for line in text.splitlines() if line.startswith("austin"))
    assert row.split()[:6] == ["austin", "4", "2", "50%", "3", "75%"]
    assert "1 sent today" in text and "interested 1" in text
    r.save_status({"scheduler": {"heartbeat": now - 600}})
    assert "NOT RUNNING" in r.status_text(now)


def test_backup_keeps_the_last_seven(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    (tmp_path / "data").mkdir()
    import sqlite3
    sqlite3.connect(tmp_path / "data" / "austin.sqlite").execute("CREATE TABLE t(x)").connection.commit()
    (tmp_path / "a-file").write_text("x")                                # cannot hold a folder: the next one is used
    monkeypatch.setattr(r, "BACKUP_DIRS", [tmp_path / "a-file" / "backups", tmp_path / "backups"])
    for day in range(1, 10):
        assert r.do_backup(at(IST, 2026, 10, day, 0, 30)).startswith("ok")
    zips = sorted(p.name for p in (tmp_path / "backups").glob("*.zip"))
    assert zips == [f"review-leads-2026-10-0{d}.zip" for d in range(3, 10)]
    assert zipfile.ZipFile(tmp_path / "backups" / zips[-1]).namelist() == ["austin.sqlite"]


def test_update_keeps_a_new_version_only_when_it_starts(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    origin, work = tmp_path / "origin", tmp_path / "work"
    git = lambda cwd, *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd,  # noqa: E731
                                         check=True, capture_output=True, text=True).stdout.strip()
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    (origin / "a.txt").write_text("1")
    git(origin, "add", ".")
    git(origin, "commit", "-q", "-m", "one")
    git(tmp_path, "clone", "-q", str(origin), str(work))
    monkeypatch.setattr(r, "ROOT", work)
    assert r.do_update() == ("ok: already the newest version", False)
    (origin / "a.txt").write_text("2")
    git(origin, "commit", "-q", "-am", "two")
    monkeypatch.setattr(r, "smoke_test", lambda: False)                  # the new version does not start
    result, updated = r.do_update()
    assert result.startswith("failed") and not updated and (work / "a.txt").read_text() == "1"
    monkeypatch.setattr(r, "smoke_test", lambda: True)
    git(work, "reset", "-q", "--hard", "HEAD")
    result, updated = r.do_update()
    assert updated and result.startswith("ok: updated") and (work / "a.txt").read_text() == "2"


def test_status_says_when_a_job_whose_time_has_passed_runs(tmp_path, monkeypatch):
    # switched on at 22:09 India time: the update ran, the e-mails run now, today's lead search and hunt follow
    r = robot(tmp_path, monkeypatch)
    monkeypatch.setattr(r, "email_settings", lambda: {"enabled": True})
    now = datetime(2026, 10, 9, 22, 16, tzinfo=IST).timestamp()
    r.save_status({"scheduler": {"heartbeat": now, "started": now - 420, "version": "abc1234"},
                   "running": {"job": "emails", "since": now - 420},
                   "jobs": {"update": {"last_started": now - 420, "result": "ok: already the newest version"},
                            "backup": {"last_started": now - 600, "result": "ok"}}})
    rows = {line[:13].strip(): line[81:] for line in r.status_text(now).splitlines()[5:10]}
    assert rows == {"Update": "Sat 10 Oct 11:00", "E-mails": "now (working on it)",
                    "Lead search": "next (today's time has passed)",
                    "E-mail hunt": "after that (today's time has passed)", "Backup": "Sat 10 Oct 00:30"}
    r.save_status({"scheduler": {"heartbeat": now}, "jobs": {"update": {"last_started": now - 420},
                                                           "emails": {"last_started": now - 60},
                                                           "leads": {"retry_at": now + 240}}})
    rows = {line[:13].strip(): line[81:] for line in r.status_text(now).splitlines()[4:9]}
    assert rows["Lead search"] == "Fri 09 Oct 22:20 (another job was running)"
    assert rows["E-mail hunt"] == "now (today's time has passed)"


def test_status_says_when_sending_is_paused_in_the_config(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    now = datetime(2026, 10, 10, 11, 25, tzinfo=IST).timestamp()
    r.save_status({"scheduler": {"heartbeat": now}})
    e = {"enabled": False, "start_per_day": 15, "step": 5, "step_every_days": 3, "max_per_day": 40}
    monkeypatch.setattr(r, "email_settings", lambda: e)
    text = r.status_text(now)
    row = next(line for line in text.splitlines() if line.startswith("E-mails "))
    assert row.endswith("Mon 12 Oct 20:05 (09:35 Chicago) - sending PAUSED, reads replies only")
    assert "E-mails (sending PAUSED in config/us/_base.toml): none sent yet" in text
    e["enabled"] = True
    assert "PAUSED" not in r.status_text(now)
    assert r.email_settings is not None and r.daily_limit(7, e) == 25           # 15, +5 every 3 sending days


def test_status_says_why_a_job_failed_from_that_days_log(tmp_path, monkeypatch):
    r = robot(tmp_path, monkeypatch)
    monkeypatch.setattr(r, "email_settings", lambda: {"enabled": True})
    started = datetime(2026, 10, 10, 2, 5, tzinfo=IST).timestamp()
    r.log_path(started).write_text("\n".join([
        "01:06:10 [robot] E-mails: ok (1 min)",
        "02:05:01 [robot] E-mails: started",
        ">>> leadgen outreach --config config/us/outreach.toml --mode live",
        "{", ' "status": "ok",', ' "new": 0,', ' "notes": [',
        '  "could not read the Gmail inbox: error: b\'[AUTHENTICATIONFAILED] Invalid credentials\'",',
        '  "no e-mails this run: outside the sending window"', " ]", "}",
        "02:06:40 [robot] E-mails: failed (exit code 2) - see the log (2 min)",
        "11:00:02 [robot] Update: started"]) + "\n")
    r.save_status({"scheduler": {"heartbeat": started}, "jobs": {"emails": {
        "last_started": started, "result": "failed (exit code 2) - see the log"}}})
    text = r.status_text(started + 600)
    assert ("Why it failed (robot log shows more):\n  E-mails (Sat 10 Oct 02:05): could not read the Gmail inbox: "
            "error: b'[AUTHENTICATIONFAILED] Invalid credentials'") in text
    lines = ["Traceback (most recent call last):", '  File "x.py", line 1', "OSError: [Errno 28] No space left on device",
             "Done. The new leads are in your Google Sheet"]
    assert r.why_failed(['"notes": []', *lines]) == "OSError: [Errno 28] No space left on device"
    assert r.why_failed(["all fine"]) == ""
