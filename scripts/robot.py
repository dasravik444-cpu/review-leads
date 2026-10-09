"""The review robot: finds leads every day and sends the e-mails in US office hours by itself (docs/LOCAL.md).

    python scripts/robot.py serve          the timetable, for good (on the tablet:  robot on  starts it)
    python scripts/robot.py status         what it does and did, and the leads found so far
    python scripts/robot.py run JOB        one job now: leads, hunt, emails, update or backup
    python scripts/robot.py log [LINES]    the end of today's log

Timetable. Lead jobs in India time; e-mails in US Central time, when US businesses are open:
    11:00              update   the newest version (kept only when it starts cleanly, else the old one stays)
    13:00              leads    the next US city: an hour of search, then 30 minutes of e-mail hunt
    17:30              hunt     an hour of e-mail hunt for businesses of earlier cities that still have no e-mail
    00:30              backup   the robot's memory into the tablet's Documents folder (the last 7 kept)
    09:35 ... 15:35    emails   Monday to Friday, every hour, Chicago time (about 8 PM to 2 AM India time)
One job at a time; a slot missed while the tablet was off runs as soon as the robot is back the same day.
Settings (settings.txt, all optional): ROBOT_CITIES_PER_DAY (1), ROBOT_LEADS, ROBOT_EMAILS, ROBOT_AUTO_UPDATE (yes/no).
Plant Parlour has its own robot with its own times; nothing here touches it.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
LOGS = DATA / "logs"
STATUS = DATA / "robot-status.json"
STOP = DATA / "robot.stop"                 # written by  robot off : finish the current job's step, then stop
INDIA = ZoneInfo("Asia/Kolkata")
CHICAGO = ZoneInfo("America/Chicago")
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


JOBS = {j.name: j for j in [
    Job("update", "Update", ("11:00",), INDIA, timeout_min=20, switch="ROBOT_AUTO_UPDATE"),
    Job("emails", "E-mails", tuple(f"{h:02d}:35" for h in range(9, 16)), CHICAGO, weekdays=(0, 1, 2, 3, 4),
        timeout_min=55, switch="ROBOT_EMAILS"),
    Job("leads", "Lead search", ("13:00",), INDIA, timeout_min=0, switch="ROBOT_LEADS"),   # timeout: per city
    Job("hunt", "E-mail hunt", ("17:30",), INDIA, timeout_min=80, switch="ROBOT_LEADS"),
    Job("backup", "Backup", ("00:30",), INDIA, timeout_min=20),
]}
PRIORITY = ["update", "emails", "leads", "hunt", "backup"]   # when several are due: an update first, e-mails on time


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
    jobs = status.get("jobs", {})
    for name in PRIORITY:
        job = JOBS[name]
        st = jobs.get(name) or {}
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


def command(job: Job, settings: dict) -> tuple[list[str], float]:
    """What a job runs (through scripts/run.sh, which also installs a new requirement after an update) and its time
    limit in minutes."""
    run = ["bash", "scripts/run.sh"]
    if job.name == "leads":
        n = cities_per_day(settings)
        return run + ["leads", "--count", str(n), "--minutes", "60", "--hunt-minutes", "30"], n * 100 + 20
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
        if job.name == "update":
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
        else:
            rec.update(last_started=now, last_finished=time.time(), result=result, retry_at=0)
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
def lead_counts() -> list[tuple[str, int, int, int, int]]:
    """Per city: businesses (leads), with e-mail, with phone, with WhatsApp - from the robot's memory files."""
    sql = ("SELECT COUNT(*), "
           "SUM(EXISTS(SELECT 1 FROM contacts c WHERE c.place_key=p.key AND c.kind='email' AND c.confidence!='low')), "
           "SUM(EXISTS(SELECT 1 FROM contacts c WHERE c.place_key=p.key AND c.kind='phone' AND c.confidence!='low')), "
           "SUM(EXISTS(SELECT 1 FROM contacts c WHERE c.place_key=p.key AND c.kind='whatsapp' AND c.confidence!='low')) "
           "FROM places p WHERE p.qualified=1 AND p.excluded IS NULL AND p.merged_into IS NULL")
    out = []
    for db in sorted(DATA.glob("*.sqlite")):
        if db.stem == "outreach":
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


def email_counts(now: float) -> dict:
    db = DATA / "outreach.sqlite"
    if not db.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        today = datetime.fromtimestamp(now, CHICAGO).date().isoformat()
        one = lambda sql, *a: con.execute(sql, a).fetchone()[0] or 0  # noqa: E731
        out = {"today": one("SELECT COUNT(*) FROM sends WHERE day=? AND status='sent'", today),
               "all": one("SELECT COUNT(*) FROM sends WHERE status='sent'"),
               "first": one("SELECT COUNT(*) FROM sends WHERE status='sent' AND step=1"),
               "bounced": one("SELECT COUNT(*) FROM sends WHERE status IN ('bounced','invalid')"),
               "days": one("SELECT COUNT(DISTINCT day) FROM sends WHERE status='sent' AND day < ?", today),
               "replies": dict(con.execute("SELECT kind, COUNT(*) FROM replies GROUP BY kind").fetchall())}
        con.close()
        return out
    except sqlite3.Error:
        return {}


def daily_limit(days_sent: int) -> int:
    """Today's e-mail limit, the way the outreach engine works it out (config/us/_base.toml [outreach.email])."""
    try:
        from leadgen.config import load_config

        e = load_config(str(ROOT / "config" / "us" / "outreach.toml"))["outreach"]["email"]
        return min(e["max_per_day"], e["start_per_day"] + e["step"] * (days_sent // e["step_every_days"]))
    except Exception:  # noqa: BLE001 - only for the status line
        return 0


def fmt(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, INDIA).strftime("%a %d %b %H:%M") if ts else "-"


def pct(part: int, whole: int) -> str:
    return f"{part:>6,} {round(100 * part / whole) if whole else 0:>3}%"


def status_text(now: float | None = None) -> str:
    now = now or time.time()
    st, settings = load_status(), read_settings()
    sch = st.get("scheduler") or {}
    alive = sch.get("heartbeat", 0) > now - 180
    lines = [f"Robot: {'RUNNING' if alive else 'NOT RUNNING'}"
             + (f" since {fmt(sch.get('started'))} (version {sch.get('version', '?')})" if alive else ""),
             f"Now {datetime.fromtimestamp(now, INDIA):%a %H:%M} in India = "
             f"{datetime.fromtimestamp(now, CHICAGO):%a %H:%M} in Chicago"]
    running = st.get("running") if alive else None
    if running:
        lines.append(f"Working on: {JOBS[running['job']].title} (since {fmt(running['since'])})")
    lines += ["", f"{'Job':<13}{'Last run (India time)':<24}{'Result':<44}Next run (India time)"]
    queued = 0                         # jobs whose time today has passed (e.g. the robot was off): one after the other
    for name in PRIORITY:
        job, rec = JOBS[name], (st.get("jobs") or {}).get(name) or {}
        nxt = next_slot(job, now)
        nxt_text = "switched off in settings.txt" if not switched_on(job, settings) else fmt(nxt.timestamp()) if nxt else "-"
        if nxt and job.tz is CHICAGO and switched_on(job, settings):
            nxt_text += f" ({nxt:%H:%M} Chicago)"
        if alive and switched_on(job, settings) and due_slot(job, now, rec.get("last_started")):
            if running and running["job"] == name:
                nxt_text = "now (working on it)"
            elif rec.get("retry_at", 0) > now:
                nxt_text = f"{fmt(rec['retry_at'])} (another job was running)"
            else:
                nxt_text = ("now" if not running and not queued else "next" if not queued else "after that") + \
                    " (today's time has passed)"
                queued += 1
        lines.append(f"{job.title:<13}{fmt(rec.get('last_started')):<24}{(rec.get('result') or '-')[:42]:<44}{nxt_text}")
    counts = lead_counts()
    if counts:
        lines += ["", "Leads found on this tablet (businesses, and how many have each contact):",
                  f"{'City':<16}{'Businesses':>11}{'E-mail':>13}{'Phone':>13}{'WhatsApp':>10}"]
        tot = [0, 0, 0, 0]
        for city, n, e, p, w in counts:
            lines.append(f"{city:<16}{n:>11,}{pct(e, n):>13}{pct(p, n):>13}{w:>10,}")
            tot = [a + b for a, b in zip(tot, (n, e, p, w))]
        if len(counts) > 1:
            lines.append(f"{'All cities':<16}{tot[0]:>11,}{pct(tot[1], tot[0]):>13}{pct(tot[2], tot[0]):>13}{tot[3]:>10,}")
    em = email_counts(now)
    if em:
        cap = daily_limit(em["days"])
        r = em["replies"]
        lines += ["", f"E-mails: {em['today']} sent today (today's limit {cap}, rising slowly to 40), {em['all']} in all "
                      f"({em['first']} first e-mails); bounced {em['bounced']}; replies: interested {r.get('positive', 0)}, "
                      f"not interested {r.get('negative', 0)}, other {r.get('other', 0)}"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="the timetable, for good")
    sub.add_parser("status", help="what it does and did, the leads so far")
    r = sub.add_parser("run", help="one job now")
    r.add_argument("job", choices=sorted(JOBS))
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
    run_job(JOBS[a.job], read_settings())
    return 0


if __name__ == "__main__":
    sys.exit(main())
