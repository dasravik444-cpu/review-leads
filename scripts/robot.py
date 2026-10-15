"""The review robot: finds leads every day and sends the e-mails in office hours by itself (docs/LOCAL.md).

    python scripts/robot.py serve          the timetable, for good (on the tablet:  robot on  starts it)
    python scripts/robot.py status         what it does and did, and the leads found so far
    python scripts/robot.py run JOB        one job now: leads, hunt, emails, update or backup
    python scripts/robot.py log [LINES]    the end of today's log

Timetable, India time. E-mails go out when the businesses of the market are open (MARKET in settings.txt, India
unless it says MARKET=us; leadgen/market.py), so the lead jobs move out of their way:
                       India market                         US market
    update             06:30                                11:00      the newest version (kept only when it starts
                                                                       cleanly, else the old one stays)
    emails             every hour, 00:05 ... 23:05          09:35 ... 15:35 Chicago time, Monday to Friday
                                                                       (about 8 PM to 2 AM India time)
    leads              01:00 (up to 3 hours)                13:00      the city whose campaign is under way (else the
                                                                       next one), then 30 minutes of e-mail hunt
    hunt               04:30                                17:30      an hour of e-mail hunt for businesses of
                                                                       earlier cities that still have no e-mail
    backup             00:30                                00:30      the robot's memory into the tablet's
                                                                       Documents folder (the last 7 kept)
One job at a time; a slot missed while the tablet was off runs as soon as the robot is back the same day.
The lead search stays on a city until its campaign is finished (Bengaluru: 7 days), for up to ROBOT_LEAD_MINUTES a
day (India 180, US 60; it stops sooner when the day's share of the city is done).
Settings (settings.txt, all optional): MARKET (in), ROBOT_CITIES_PER_DAY (1), ROBOT_LEAD_MINUTES, ROBOT_LEADS,
ROBOT_EMAILS, ROBOT_AUTO_UPDATE (yes/no).
Plant Parlour has its own robot with its own times; nothing here touches it.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from leadgen import market as markets  # noqa: E402 - India or the US (settings.txt MARKET)

DATA = ROOT / "data"
LOGS = DATA / "logs"
STATUS = DATA / "robot-status.json"
STOP = DATA / "robot.stop"                 # written by  robot off : finish the current job's step, then stop
INDIA = ZoneInfo("Asia/Kolkata")
UPDATED = 10                               # serve's exit code after an update: start the new version at once
ALREADY_RUNNING = 75
BUSY = 3                                   # local_run's exit code when another job holds the lock
BACKUP_DIRS = [Path("/sdcard/Documents/review-leads-backup"), DATA / "backups"]
KEEP_BACKUPS = 7


@dataclass(frozen=True)
class Job:
    name: str
    title: str
    times: tuple[str, ...]
    tz: ZoneInfo
    weekdays: tuple[int, ...] | None = None          # 0 = Monday; None = every day
    timeout_min: float = 60
    switch: str = ""                                 # a settings key; "no" there switches the job off


# Lead search time per city and day (minutes), unless ROBOT_LEAD_MINUTES says otherwise: India aims at about 1,000
# businesses a day (the run stops sooner once the day's share is done).
LEAD_MINUTES = {"in": 180, "us": 60}
# A job that fails (the internet gone for a while, Google not answering) runs again 10 minutes later, 3 times, before
# it waits for its next time; before each job the robot waits up to 10 minutes for a lost internet connection.
RETRY_JOBS, RETRIES, RETRY_MINUTES = ("leads", "hunt", "emails", "update"), 3, 10
NETWORK_WAIT_MINUTES = 10
# The lead jobs' times (India time), out of the way of the market's e-mail hours.
# India: the lead search at night (01:00, up to about 3 hours, then the e-mail hunt), so new leads are in the Sheet
# before the first e-mails at 07:05.
LEAD_TIMES = {"in": {"update": "06:30", "leads": "01:00", "hunt": "04:30", "backup": "00:30"},
              "us": {"update": "11:00", "leads": "13:00", "hunt": "17:30", "backup": "00:30"}}


def make_jobs(m: markets.Market) -> dict[str, Job]:
    t = LEAD_TIMES[m.code]
    return {j.name: j for j in [
        Job("update", "Update", (t["update"],), INDIA, timeout_min=20, switch="ROBOT_AUTO_UPDATE"),
        Job("emails", "E-mails", m.email_slots, m.tz, weekdays=m.days, timeout_min=58, switch="ROBOT_EMAILS"),
        Job("leads", "Lead search", (t["leads"],), INDIA, timeout_min=0, switch="ROBOT_LEADS"),   # timeout: per city
        Job("hunt", "E-mail hunt", (t["hunt"],), INDIA, timeout_min=80, switch="ROBOT_LEADS"),
        Job("backup", "Backup", (t["backup"],), INDIA, timeout_min=20),
    ]}


JOBS_BY_MARKET = {code: make_jobs(m) for code, m in markets.MARKETS.items()}
PRIORITY = ["update", "emails", "leads", "hunt", "backup"]   # when several are due: an update first, e-mails on time


def market(settings: dict) -> markets.Market:
    return markets.current(settings)


def jobs(settings: dict) -> dict[str, Job]:
    """The timetable of the market in the settings."""
    return JOBS_BY_MARKET[market(settings).code]


def slots(job: Job, day: date) -> list[datetime]:
    if job.weekdays is not None and day.weekday() not in job.weekdays:
        return []
    out = []
    for t in job.times:
        h, m = (int(x) for x in t.split(":"))
        out.append(datetime(day.year, day.month, day.day, h, m, tzinfo=job.tz))
    return out


def due_slot(job: Job, now: float, last_started: float | None) -> datetime | None:
    """Today's latest slot (in the job's own time zone) that has passed and that the job has not started since."""
    today = datetime.fromtimestamp(now, job.tz).date()
    passed = [s for s in slots(job, today) if s.timestamp() <= now]
    if not passed:
        return None
    latest = passed[-1]
    return latest if not last_started or last_started < latest.timestamp() else None


def next_slot(job: Job, now: float) -> datetime | None:
    today = datetime.fromtimestamp(now, job.tz).date()
    for d in range(8):
        for s in slots(job, today + timedelta(days=d)):
            if s.timestamp() > now:
                return s
    return None


def switched_on(job: Job, settings: dict) -> bool:
    return not job.switch or str(settings.get(job.switch, "yes")).strip().lower() not in ("no", "off", "false", "0")


def pick_due(now: float, status: dict, settings: dict) -> Job | None:
    records, timetable = status.get("jobs", {}), jobs(settings)
    for name in PRIORITY:
        job = timetable[name]
        st = records.get(name) or {}
        if not switched_on(job, settings) or st.get("retry_at", 0) > now:
            continue
        if due_slot(job, now, st.get("last_started")):
            return job
    return None


def cities_per_day(settings: dict) -> int:
    try:
        return max(1, min(5, int(str(settings.get("ROBOT_CITIES_PER_DAY", "1")).strip())))
    except ValueError:
        return 1


def lead_minutes(settings: dict) -> int:
    try:
        return max(15, min(600, int(str(settings.get("ROBOT_LEAD_MINUTES", "")).strip())))
    except ValueError:
        return LEAD_MINUTES[market(settings).code]


def command(job: Job, settings: dict) -> tuple[list[str], float]:
    """What a job runs (through scripts/run.sh, which also installs a new requirement after an update) and its time
    limit in minutes."""
    run = ["bash", "scripts/run.sh"]
    if job.name == "leads":
        n, minutes = cities_per_day(settings), lead_minutes(settings)
        return (run + ["leads", "--count", str(n), "--minutes", str(minutes), "--hunt-minutes", "30"],
                n * (minutes + 40) + 20)
    if job.name == "hunt":
        return run + ["hunt", "--minutes", "60"], job.timeout_min
    if job.name == "emails":
        return run + ["emails"], job.timeout_min
    raise ValueError(job.name)


# ------------------------------------------------------------------ state, settings, log
def load_status() -> dict:
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_status(st: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_name(STATUS.name + ".tmp")
    tmp.write_text(json.dumps(st, indent=1), encoding="utf-8")
    os.replace(tmp, STATUS)


def update_status(change) -> dict:
    """Read, change and write the status file under a lock (the scheduler and a job run by hand both write it)."""
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "robot-status.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        st = load_status()
        change(st)
        save_status(st)
        return st


def read_settings() -> dict:
    """settings.txt as a dict (the ROBOT_ switches; the keys themselves are read by the jobs)."""
    out = {}
    path = ROOT / "settings.txt"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                out[key.strip()] = value.strip().strip("\"'")
    return out


def log_path(now: float | None = None) -> Path:
    LOGS.mkdir(parents=True, exist_ok=True)
    return LOGS / f"{datetime.fromtimestamp(now or time.time(), INDIA):%Y-%m-%d}.log"


def log(msg: str) -> None:
    line = f"{datetime.now(INDIA):%H:%M:%S} [robot] {msg}"
    with open(log_path(), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def prune_logs(keep_days: int = 30) -> None:
    for p in sorted(LOGS.glob("*.log"))[:-keep_days]:
        p.unlink(missing_ok=True)


# ------------------------------------------------------------------ running jobs
def run_command(args: list[str], timeout_min: float, should_stop=lambda: False, heartbeat=lambda: None) -> int:
    """Run one command, its output added to today's log. 124 = took too long, 143 = stopped (robot off)."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "ROBOT_JOB": "1"}      # ROBOT_JOB: "the robot" in a Busy message
    with open(log_path(), "a", encoding="utf-8") as out:
        proc = subprocess.Popen(args, cwd=str(ROOT), env=env, stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        end = time.time() + timeout_min * 60
        while True:
            try:
                return proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                heartbeat()
                late = time.time() > end
                if late or should_stop():
                    stop_group(proc)
                    return 124 if late else 143


def stop_group(proc: subprocess.Popen, grace: float = 120) -> None:
    """SIGTERM first: the lead search finishes its step and saves; after the grace time, SIGKILL."""
    for sig, wait_s in ((signal.SIGTERM, grace), (signal.SIGKILL, 10)):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=wait_s)
            return
        except subprocess.TimeoutExpired:
            continue


def git(*args: str, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)


def smoke_test() -> bool:
    """The new version starts: its settings/requirements step, the lead engine, the robot."""
    checks = [["bash", "scripts/run.sh", "--help"], [str(ROOT / ".venv/bin/python"), "-m", "leadgen", "--help"],
              [str(ROOT / ".venv/bin/python"), "scripts/robot.py", "--help"]]
    for args in checks:
        try:
            r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=900)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if r.returncode != 0:
            return False
    return True


def do_update() -> tuple[str, bool]:
    """git pull; the new version is kept only if it starts cleanly. Returns (result, updated)."""
    old = git("rev-parse", "--short", "HEAD").stdout.strip()
    pull = git("pull", "--ff-only")
    if pull.returncode != 0:
        return f"failed: git pull: {(pull.stderr or pull.stdout).strip()[-200:]}", False
    new = git("rev-parse", "--short", "HEAD").stdout.strip()
    if new == old:
        return "ok: already the newest version", False
    if smoke_test():
        return f"ok: updated {old} -> {new}", True
    git("reset", "--hard", old)
    smoke_test()                                # back to the old version's requirements
    return f"failed: version {new} did not start cleanly - kept {old}", False


def do_backup(now: float) -> str:
    """A consistent copy of every memory file, zipped into the tablet's Documents folder (or data/backups)."""
    dbs = sorted(DATA.glob("*.sqlite"))
    if not dbs:
        return "ok: nothing to back up yet"
    for folder in BACKUP_DIRS:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".write-test"
            probe.write_text("x")
            probe.unlink()
            break
        except OSError:
            continue
    else:
        return "failed: no folder to write the backup to"
    target = folder / f"review-leads-{datetime.fromtimestamp(now, INDIA):%Y-%m-%d}.zip"
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for db in dbs:
            copy = Path(tmp) / db.name
            src, dst = sqlite3.connect(db), sqlite3.connect(copy)
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            zf.write(copy, db.name)
    for old in sorted(folder.glob("review-leads-*.zip"))[:-KEEP_BACKUPS]:
        old.unlink(missing_ok=True)
    return f"ok: {target} ({len(dbs)} memory files)"


def internet_ok() -> bool:
    """Our own internet connection works: well-known names resolve (the same check as the lead engine's)."""
    for host in ("www.google.com", "www.cloudflare.com", "github.com"):
        try:
            socket.getaddrinfo(host, 443)
            return True
        except OSError:
            continue
    return False


def wait_for_internet(max_seconds: float, should_stop=lambda: False, heartbeat=lambda: None, every: float = 30,
                      check=None, sleep=time.sleep) -> bool:
    """A short drop (Wi-Fi switching, a router restarting): wait for the connection, up to max_seconds, still reporting
    in (heartbeat) and stopping at once on  robot off . True when it works."""
    check = check or internet_ok
    end = time.monotonic() + max_seconds
    told = False
    while not check():
        if should_stop() or time.monotonic() >= end:
            return False
        if not told:
            log(f"no internet connection - waiting up to {max_seconds / 60:.0f} minutes for it to come back")
            told = True
        heartbeat()
        sleep(every)
    if told:
        log("internet connection back")
    return True


def beat(st: dict) -> None:
    st.setdefault("scheduler", {})["heartbeat"] = time.time()


def run_job(job: Job, settings: dict, should_stop=lambda: False, serving: bool = False) -> bool:
    """Run one job and record it. Returns True when the robot updated itself (start the new version)."""
    now = time.time()
    update_status(lambda st: st.update(running={"job": job.name, "since": now}))
    log(f"{job.title}: started")
    if os.environ.get("PD_CONTAINER") and job.name != "backup":
        try:                                     # the tablet may have moved to another network (android/dns.sh)
            subprocess.run(["bash", "android/dns.sh"], cwd=str(ROOT), timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            pass
    updated = False
    try:
        if job.name != "backup" and not wait_for_internet(NETWORK_WAIT_MINUTES * 60, should_stop,
                                                          (lambda: update_status(beat)) if serving else (lambda: None)):
            result = "failed: no internet connection" if not should_stop() else "stopped (robot off)"
        elif job.name == "update":
            result, updated = do_update()
        elif job.name == "backup":
            result = do_backup(now)
        else:
            args, limit = command(job, settings)
            code = run_command(args, limit, should_stop, (lambda: update_status(beat)) if serving else (lambda: None))
            result = {0: "ok", 124: f"stopped: took longer than {limit:.0f} minutes", 143: "stopped (robot off)",
                      BUSY: "busy: another job was running"}.get(code, f"failed (exit code {code}) - see the log")
    except Exception as exc:  # noqa: BLE001 - one job's problem must not stop the robot
        result = f"failed: {type(exc).__name__}: {exc}"[:200]

    def record(st: dict) -> None:
        st["running"] = None
        rec = st.setdefault("jobs", {}).setdefault(job.name, {})
        if result.startswith("busy"):
            rec["retry_at"] = time.time() + 300   # a job started by hand holds the lock: again in 5 minutes
        elif result.startswith("stopped (robot off)"):
            rec.update(result="stopped (robot off) - runs again when on", retry_at=0)   # the slot stays due
        elif job.name in RETRY_JOBS and result.startswith("failed") and rec.get("fails", 0) < RETRIES and \
                (job.name != "update" or "git pull" in result or "internet" in result):
            # Not a whole day lost to a short outage: the slot stays due and the job runs again in 10 minutes
            again = time.time() + RETRY_MINUTES * 60
            rec.update(result=f"{result[:60]} - again at {fmt(again)[-5:]}", retry_at=again, fails=rec.get("fails", 0) + 1)
        else:
            rec.update(last_started=now, last_finished=time.time(), result=result, retry_at=0, fails=0)
    update_status(record)
    log(f"{job.title}: {result} ({(time.time() - now) / 60:.0f} min)")
    return updated


# ------------------------------------------------------------------ the scheduler
def serve() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    lock = open(DATA / "robot-serve.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("The robot is already running.")
        return ALREADY_RUNNING
    STOP.unlink(missing_ok=True)
    stopping = []
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.append(1))
    should_stop = lambda: bool(stopping) or STOP.exists()  # noqa: E731
    version = git("rev-parse", "--short", "HEAD").stdout.strip()
    update_status(lambda st: st.update(scheduler={"pid": os.getpid(), "started": time.time(), "heartbeat": time.time(),
                                                  "version": version}, running=None))
    log(f"robot started (version {version})")
    prune_logs()
    try:
        while not should_stop():
            st = update_status(beat)
            settings = read_settings()
            job = pick_due(time.time(), st, settings)
            if job is not None and run_job(job, settings, should_stop, serving=True):
                log("starting the new version")
                return UPDATED
            if job is None and git("rev-parse", "--short", "HEAD").stdout.strip() not in ("", version):
                log("new version on disk (update) - starting it")          # e.g. after the  update  command
                return UPDATED
            for _ in range(6):                       # look again in 30 seconds
                if should_stop():
                    break
                time.sleep(5)
    finally:
        STOP.unlink(missing_ok=True)
        update_status(lambda st: st.setdefault("scheduler", {}).update(heartbeat=0))
    log("robot stopped")
    return 0


# ------------------------------------------------------------------ status
def market_cities(m: markets.Market) -> list[str]:
    try:
        return list(tomllib.loads((ROOT / "config" / m.code / "fleet.toml").read_text(encoding="utf-8"))["cities"])
    except (OSError, ValueError, KeyError):
        return []


def lead_counts(m: markets.Market | None = None) -> list[tuple[str, int, int, int, int]]:
    """Per city of the market: businesses (leads), with e-mail, with phone, with WhatsApp - from the robot's memory
    files."""
    cities = market_cities(m) if m else None
    sql = ("SELECT COUNT(*), "
           "SUM(EXISTS(SELECT 1 FROM contacts c WHERE c.place_key=p.key AND c.kind='email' AND c.confidence!='low')), "
           "SUM(EXISTS(SELECT 1 FROM contacts c WHERE c.place_key=p.key AND c.kind='phone' AND c.confidence!='low')), "
           "SUM(EXISTS(SELECT 1 FROM contacts c WHERE c.place_key=p.key AND c.kind='whatsapp' AND c.confidence!='low')) "
           "FROM places p WHERE p.qualified=1 AND p.excluded IS NULL AND p.merged_into IS NULL")
    out = []
    for db in sorted(DATA.glob("*.sqlite")):
        if db.stem.startswith("outreach") or db.stem == "check" or (cities is not None and db.stem not in cities):
            continue
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            n, e, p, w = con.execute(sql).fetchone()
            con.close()
        except sqlite3.Error:
            continue
        if n:
            out.append((db.stem, n, e or 0, p or 0, w or 0))
    return out


def campaign_lines(m: markets.Market, now: float) -> list[str]:
    """The cities whose campaign is under way: which day, how much of the city is searched, how many businesses."""
    from leadgen.progress import city_progress

    today = datetime.fromtimestamp(now, INDIA).date()
    out = []
    for city in market_cities(m):
        state = city_progress(DATA / f"{city}.sqlite", today)
        if state and state["unfinished"]:
            out.append(f"  {city}: day {state['day']} of {state['days']}, {state['searched_pct']}% of the city searched, "
                       f"{state['mapped']:,} businesses of these kinds on the map (open data)")
    return ["", "Lead campaign under way (the robot stays on it every evening until it is finished):"] + out if out else []


def outreach_dbs(m: markets.Market) -> list[Path]:
    """The e-mail memory of each Gmail account (scripts/local_run.py account_db): outreach-in.sqlite, -2, -3."""
    base = DATA / m.outreach_db
    return [p for p in [base] + [base.with_name(f"{base.stem}-{i}{base.suffix}") for i in (2, 3)] if p.exists()]


def email_counts(now: float, m: markets.Market | None = None) -> dict:
    """The e-mails of all Gmail accounts together (and per account: sent today, in the last 24 hours)."""
    m = m or markets.MARKETS["us"]
    dbs = outreach_dbs(m)
    if not dbs:
        return {}
    today = datetime.fromtimestamp(now, m.tz).date().isoformat()
    out = {"today": 0, "all": 0, "first": 0, "bounced": 0, "days": 0, "last24": 0, "replies": {}, "accounts": [],
           "plan_started": 0.0, "paused": [], "recent_bounces": []}
    for i, db in enumerate(dbs, start=1):
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            one = lambda sql, *a: con.execute(sql, a).fetchone()[0] or 0  # noqa: E731
            today_n, last24 = (one("SELECT COUNT(*) FROM sends WHERE day=? AND status='sent'", today),
                               one("SELECT COUNT(*) FROM sends WHERE sent_at>=? AND status='sent'", now - 86400))
            out["today"] += today_n
            out["last24"] += last24
            out["all"] += one("SELECT COUNT(*) FROM sends WHERE status='sent'")
            out["first"] += one("SELECT COUNT(*) FROM sends WHERE status='sent' AND step=1")
            out["bounced"] += one("SELECT COUNT(*) FROM sends WHERE status IN ('bounced','invalid')")
            out["days"] = max(out["days"], one("SELECT COUNT(DISTINCT day) FROM sends WHERE status='sent' AND day < ?", today))
            for kind, n in con.execute("SELECT kind, COUNT(*) FROM replies GROUP BY kind").fetchall():
                out["replies"][kind] = out["replies"].get(kind, 0) + n
            meta = dict(con.execute("SELECT key, value FROM meta WHERE key IN "
                                    "('plan_started','paused_until','pause_reason')").fetchall())
            if i == 1:
                out["plan_started"] = float(json.loads(meta["plan_started"])) if "plan_started" in meta else 0.0
            until = float(json.loads(meta["paused_until"])) if meta.get("paused_until") else 0.0
            if until > now:
                out["paused"].append((i, until, str(json.loads(meta.get("pause_reason") or '""'))))
            for email, err, at in con.execute("SELECT email, error, sent_at FROM sends WHERE status IN ('invalid','bounced') "
                                              "ORDER BY sent_at DESC LIMIT 5").fetchall():
                out["recent_bounces"].append((at or 0, i, email, " ".join(str(err or "").split())[:70]))
            out["accounts"].append((i, today_n, last24))
            con.close()
        except (sqlite3.Error, ValueError, TypeError):
            continue
    return out


def plan_text(e: dict, started: float, now: float) -> str:
    """Where the sending plan stands, for each Gmail account (leadgen/outreach/plan.py)."""
    from leadgen.outreach import plan as sending_plan

    if not started:
        return "Sending plan: starts with the next e-mail run"
    hours = (now - started) / 3600
    then = e.get("plan_then") or None
    cur = sending_plan.current(e["plan"], then, hours)
    if cur is None:
        return f"Sending plan: finished ({hours:.0f} hours since it started)"
    block, length, count = cur
    nxt = round(sending_plan.allowed(e["plan"], then, hours + 24) - sending_plan.allowed(e["plan"], then, hours))
    return (f"Sending plan: hour {hours:.0f}, block {block} ({count} e-mails in {length:g} hours); about {nxt} in the "
            f"next 24 hours, per Gmail account (never more than {e.get('max_per_24h', 450)} in 24 hours)")


def email_settings(m: markets.Market | None = None) -> dict:
    """The e-mail part of the market's outreach config (config/<market>/_base.toml [outreach.email]); {} if it cannot
    be read."""
    try:
        from leadgen.config import load_config

        m = m or market(read_settings())
        return load_config(str(ROOT / "config" / m.code / "outreach.toml"))["outreach"]["email"]
    except Exception:  # noqa: BLE001 - only for the status
        return {}


def daily_limit(days_sent: int, e: dict | None = None) -> int:
    """Today's e-mail limit, the way the outreach engine works it out."""
    e = email_settings() if e is None else e
    try:
        return min(e["max_per_day"], e["start_per_day"] + e["step"] * (days_sent // e["step_every_days"]))
    except (KeyError, TypeError, ZeroDivisionError):
        return 0


ERRORISH = re.compile(r"error|fail|refused|could not|cannot|can't|denied|traceback|exception|timed out|paused",
                      re.IGNORECASE)


def why_failed(lines: list[str]) -> str:
    """One line on why a job failed, from its output: the e-mail run's notes first, else the last error line."""
    notes = []
    for i, line in enumerate(lines):
        if line.strip() == '"notes": [':
            for item in lines[i + 1:]:
                item = item.strip()
                if item.startswith("]"):
                    break
                try:
                    notes.append(str(json.loads(item.rstrip(","))))
                except ValueError:
                    notes.append(item.rstrip(",").strip('"'))
    for note in notes:
        if ERRORISH.search(note):
            return note[:200]
    if notes:
        return notes[0][:200]
    for line in reversed(lines):
        if ERRORISH.search(line) and "[robot]" not in line:
            return line.strip()[:200]
    return ""


def failure_reason(job: Job, rec: dict) -> str:
    """Why a job's last run failed, read from that day's log (between its "started" and "failed" lines)."""
    if not rec.get("last_started"):
        return ""
    try:
        lines = log_path(rec["last_started"]).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    ends = [i for i, line in enumerate(lines) if f"[robot] {job.title}: failed" in line]
    if not ends:
        return ""
    starts = [i for i, line in enumerate(lines[:ends[-1]]) if f"[robot] {job.title}: started" in line]
    return why_failed(lines[(starts[-1] if starts else 0):ends[-1]])


def fmt(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, INDIA).strftime("%a %d %b %H:%M") if ts else "-"


def pct(part: int, whole: int) -> str:
    return f"{part:>6,} {round(100 * part / whole) if whole else 0:>3}%"


def status_text(now: float | None = None) -> str:
    now = now or time.time()
    st, settings = load_status(), read_settings()
    m, timetable = market(settings), jobs(settings)
    sch = st.get("scheduler") or {}
    alive = sch.get("heartbeat", 0) > now - 180
    local = "" if m.tz.key == INDIA.key else f" = {datetime.fromtimestamp(now, m.tz):%a %H:%M} in {m.place}"
    lines = [f"Robot: {'RUNNING' if alive else 'NOT RUNNING'}"
             + (f" since {fmt(sch.get('started'))} (version {sch.get('version', '?')})" if alive else ""),
             f"Market: {m.name} (MARKET in settings.txt)",
             f"Now {datetime.fromtimestamp(now, INDIA):%a %H:%M} in India{local}"]
    running = st.get("running") if alive else None
    if running:
        lines.append(f"Working on: {timetable[running['job']].title} (since {fmt(running['since'])})")
    lines += ["", f"{'Job':<13}{'Last run (India time)':<24}{'Result':<44}Next run (India time)"]
    queued = 0                         # jobs whose time today has passed (e.g. the robot was off): one after the other
    problems = []
    e_cfg = email_settings(m)
    paused = e_cfg.get("enabled") is False           # sending paused in the config: the job only reads replies
    for name in PRIORITY:
        job, rec = timetable[name], (st.get("jobs") or {}).get(name) or {}
        nxt = next_slot(job, now)
        nxt_text = "switched off in settings.txt" if not switched_on(job, settings) else fmt(nxt.timestamp()) if nxt else "-"
        if nxt and job.tz.key != INDIA.key and switched_on(job, settings):
            nxt_text += f" ({nxt:%H:%M} {m.place})"
        if alive and switched_on(job, settings) and due_slot(job, now, rec.get("last_started")):
            if running and running["job"] == name:
                nxt_text = "now (working on it)"
            elif rec.get("retry_at", 0) > now:
                nxt_text = f"{fmt(rec['retry_at'])} (another job was running)"
            else:
                nxt_text = ("now" if not running and not queued else "next" if not queued else "after that") + \
                    " (today's time has passed)"
                queued += 1
        if name == "emails" and paused and switched_on(job, settings):
            nxt_text += " - sending PAUSED, reads replies only"
        lines.append(f"{job.title:<13}{fmt(rec.get('last_started')):<24}{(rec.get('result') or '-')[:42]:<44}{nxt_text}")
        if (rec.get("result") or "").startswith("failed"):
            why = failure_reason(job, rec)
            if why:
                problems.append(f"  {job.title} ({fmt(rec.get('last_started'))}): {why}")
    if problems:
        lines += ["", "Why it failed (robot log shows more):"] + problems
    lines += campaign_lines(m, now)
    counts = lead_counts(m)
    if counts:
        lines += ["", f"Leads found on this tablet in {m.name} (businesses, and how many have each contact):",
                  f"{'City':<16}{'Businesses':>11}{'E-mail':>13}{'Phone':>13}{'WhatsApp':>10}"]
        tot = [0, 0, 0, 0]
        for city, n, e, p, w in counts:
            lines.append(f"{city:<16}{n:>11,}{pct(e, n):>13}{pct(p, n):>13}{w:>10,}")
            tot = [a + b for a, b in zip(tot, (n, e, p, w))]
        if len(counts) > 1:
            lines.append(f"{'All cities':<16}{tot[0]:>11,}{pct(tot[1], tot[0]):>13}{pct(tot[2], tot[0]):>13}{tot[3]:>10,}")
    em = email_counts(now, m)
    head = f"E-mails (sending PAUSED in config/{m.code}/_base.toml)" if paused else "E-mails"
    if em:
        r = em["replies"]
        if e_cfg.get("plan"):
            lines += ["", f"{head}: {em['today']} sent today, {em['last24']} in the last 24 hours, {em['all']} in all "
                          f"({em['first']} first e-mails); bounced {em['bounced']}; replies: interested "
                          f"{r.get('positive', 0)}, not interested {r.get('negative', 0)}, other {r.get('other', 0)}",
                      "  " + plan_text(e_cfg, em["plan_started"], now)]
            if len(em["accounts"]) > 1:
                lines += [f"  Gmail account {i}: {t} sent today, {d} in the last 24 hours" for i, t, d in em["accounts"]]
        else:
            cap = daily_limit(em["days"], e_cfg)
            top = e_cfg.get("max_per_day", 40)
            lines += ["", f"{head}: {em['today']} sent today (today's limit {cap}, rising slowly to {top}), {em['all']} "
                          f"in all ({em['first']} first e-mails); bounced {em['bounced']}; replies: interested "
                          f"{r.get('positive', 0)}, not interested {r.get('negative', 0)}, other {r.get('other', 0)}"]
        for i, until, why in em["paused"]:
            lines.append(f"  Gmail account {i}: sending PAUSED until {fmt(until)} - {why}")
        if em["recent_bounces"]:
            lines.append("  Bounced lately (never e-mailed again): " + "; ".join(
                f"{email}" + (f" ({err})" if err else "") for _, _, email, err in sorted(em["recent_bounces"], reverse=True)[:5]))
    elif paused:
        lines += ["", f"{head}: none sent yet"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="the timetable, for good")
    sub.add_parser("status", help="what it does and did, the leads so far")
    r = sub.add_parser("run", help="one job now")
    r.add_argument("job", choices=sorted(PRIORITY))
    lg = sub.add_parser("log", help="the end of today's log")
    lg.add_argument("lines", nargs="?", type=int, default=60)
    a = ap.parse_args(argv)
    if a.cmd == "serve":
        return serve()
    if a.cmd == "status":
        print(status_text())
        return 0
    if a.cmd == "log":
        path = log_path()
        text = path.read_text(encoding="utf-8").splitlines() if path.exists() else ["(nothing logged today yet)"]
        print("\n".join(text[-a.lines:]))
        return 0
    settings = read_settings()
    run_job(jobs(settings)[a.job], settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
