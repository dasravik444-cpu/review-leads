"""Run the lead search, the e-mail hunt and the outreach on your own computer (free, and within GitHub's terms).

    python scripts/local_run.py check                 are the keys in .env right? (Google Sheet, Gmail)
    python scripts/local_run.py leads                 the next 3 US cities, about an hour each, then their e-mail hunt
    python scripts/local_run.py leads --cities austin,miami --minutes 60 --hunt-minutes 30
    python scripts/local_run.py emails                today's e-mails, replies and follow-ups (US working hours only)
    python scripts/local_run.py emails --dry-run      only prepares them, in the Sheet's "Email Preview" tab
    python scripts/local_run.py emails --max 1 --copy-to me@example.com   one e-mail, and a blind copy to you
    python scripts/local_run.py emails --check        only reads replies and bounces (any time of day)
    python scripts/local_run.py import                lead lists (leads-<city>.zip/.csv) and your PDF from Downloads
    python scripts/local_run.py hunt --minutes 60     more e-mail hunting in the cities searched before

Your keys live in settings.txt in the main folder (the first run makes it from settings-example.txt); the Google
key file (.json) goes into the secrets folder and is found by itself. Each city's memory is a file in data/.
Nothing here needs GitHub: GitHub only stores the code. (docs/LOCAL.md explains it all.)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import tomllib

try:
    import fcntl                       # Linux, Mac, Android; on Windows two runs at once are simply not prevented
except ImportError:
    fcntl = None

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUSY = 3                               # exit code: another job (the robot, or one typed by hand) is running
US_TIME = ZoneInfo("America/Chicago")
INDIA = ZoneInfo("Asia/Kolkata")
TITLES = {"leads": "lead search", "hunt": "e-mail hunt", "emails": "e-mail sending", "import": "import"}
SEND_HOURS = (8.5, 16.5)            # US Central time, Monday to Friday (the outreach config's own window is 09:30-16:30)
KEYS = ("RQ_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_FILE", "OUTREACH_GMAIL_ADDRESS", "OUTREACH_GMAIL_APP_PASSWORD",
        "OUTREACH_SENDER_PHONE", "OUTREACH_POSTAL_ADDRESS")


def key_email(path: Path) -> str:
    """The account a Google service-account key file belongs to (empty for any other file)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return ""
    if isinstance(data, dict) and data.get("type") == "service_account":
        return str(data.get("client_email") or "")
    return ""


def key_files() -> list[Path]:
    """The Google service-account key files (.json, any name) in the secrets folder and the main folder."""
    return [p for folder in (ROOT / "secrets", ROOT) for p in sorted(folder.glob("*.json")) if key_email(p)]


def opens_sheet(key: Path, sheet_id: str) -> bool:
    """Whether this key may open the Sheet (one small request to Google)."""
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            str(key), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        r = AuthorizedSession(creds).get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}",
                                         params={"fields": "spreadsheetId"}, timeout=30)
        return r.status_code == 200
    except Exception:  # noqa: BLE001 - no internet, a damaged key: not this one
        return False


def find_key_file() -> str:
    """The Google service-account key: the file named in the settings, else the key file in the secrets folder or
    the main folder (any name). With several (say, the key of another business too), the one that may open the
    Sheet."""
    named = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    if named:
        p = Path(named) if Path(named).is_absolute() else ROOT / named
        if p.is_file():
            return str(p)
    keys = key_files()
    sheet = os.environ.get("RQ_SHEET_ID", "")
    if len(keys) > 1 and sheet:
        for key in keys:
            if opens_sheet(key, sheet):
                return str(key)
    return str(keys[0]) if keys else ""


def load_env(*paths: Path) -> list[str]:
    """KEY=VALUE lines of the settings files into the environment (values already set win; the first file wins over
    later ones). Returns the settings still missing."""
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                os.environ.setdefault(key.strip(), value)
    key_file = find_key_file()
    if key_file:
        os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"] = key_file
    else:
        os.environ.pop("GOOGLE_SERVICE_ACCOUNT_FILE", None)
    os.environ.setdefault("PYTHONUTF8", "1")              # business names in any script, also on Windows
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    return [k for k in KEYS if not os.environ.get(k)]


def _fleet_file() -> dict:
    return tomllib.loads((ROOT / "config" / "us" / "fleet.toml").read_text(encoding="utf-8"))


def fleet() -> list[str]:
    return list(_fleet_file()["cities"])


def next_cities(n: int, cities: list[str] | None = None, done_elsewhere: list[str] | None = None) -> list[str]:
    """Cities never searched first (in the fleet's order; those already searched on GitHub after the others),
    then the city searched longest ago on this computer."""
    cities = cities or fleet()
    elsewhere = set(_fleet_file().get("searched_on_github", []) if done_elsewhere is None else done_elsewhere)

    def last_run(c: str) -> float:
        db = DATA / f"{c}.sqlite"
        return db.stat().st_mtime if db.exists() else (-1.0 if c in elsewhere else -2.0)
    order = {c: i for i, c in enumerate(cities)}
    return sorted(cities, key=lambda c: (last_run(c), order[c]))[:n]


def us_working_hours(now: datetime | None = None) -> tuple[bool, str]:
    now = (now or datetime.now(US_TIME)).astimezone(US_TIME)
    hour = now.hour + now.minute / 60
    ok = now.weekday() < 5 and SEND_HOURS[0] <= hour < SEND_HOURS[1]
    return ok, now.strftime("%A %H:%M") + " in Chicago"


def leadgen(*args: str) -> int:
    cmd = [sys.executable, "-m", "leadgen", *args]
    print("\n>>> " + " ".join(cmd[2:]), flush=True)
    return subprocess.call(cmd, cwd=ROOT, env=os.environ.copy())


def cmd_check(_a) -> int:
    keys = key_files()
    if len(keys) > 1:                           # which one is used, so a wrong key is easy to spot
        used = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
        print("Google keys in the secrets folder:")
        for key in keys:
            print(f"  {key.name} ({key_email(key)})" + ("  <- used" if str(key) == used else ""))
    code = leadgen("doctor", "--config", "config/us/austin.toml", "--db", str(DATA / "austin.sqlite"), "--require-sheet",
                   "--sheet-test")
    print("\nGmail: preparing one e-mail (nothing is sent) to test the login...")
    code2 = leadgen("outreach", "--config", "config/us/outreach.toml", "--db", str(DATA / "outreach.sqlite"),
                    "--mode", "dry-run", "--max-emails", "1")
    return code or code2


def cmd_leads(a) -> int:
    known = fleet()
    wanted = [c.strip() for c in a.cities.split(",") if c.strip()] if a.cities else next_cities(a.count, known)
    unknown = [c for c in wanted if c not in known]
    if unknown:
        print(f"Unknown cities: {', '.join(unknown)}. Choose from: {', '.join(known)}")
        return 2
    print(f"Cities this time: {', '.join(wanted)} ({a.minutes:.0f} min search + {a.hunt_minutes:.0f} min e-mail hunt each)")
    worst = 0
    for city in wanted:
        common = ["--config", f"config/us/{city}.toml", "--db", str(DATA / f"{city}.sqlite")]
        worst = max(worst, leadgen("run", *common, "--budget-minutes", str(a.minutes)))
        if a.hunt_minutes > 0:
            worst = max(worst, leadgen("email-hunt", *common, "--limit", "1500", "--budget-minutes", str(a.hunt_minutes)))
    print("\nDone. The new leads are in your Google Sheet (Leads tab); each city's memory is in the data folder.")
    return worst


class Busy(Exception):
    pass


@contextmanager
def job_lock(what: str, wait: bool = False):
    """One lead search / e-mail run / import at a time (the robot and commands typed by hand share this lock).
    wait: wait until the job holding it has finished (the import), instead of giving up with Busy."""
    DATA.mkdir(exist_ok=True)
    fh = open(DATA / "robot.lock", "a+")
    if fcntl is not None:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.seek(0)
            holder = fh.read().strip() or "another job"
            if not wait:
                fh.close()
                raise Busy(holder)
            print(f"Waiting: {holder} is running. The {TITLES.get(what, what)} starts by itself when it has "
                  "finished - leave Termux open (Ctrl+C cancels).", flush=True)
            try:
                fcntl.flock(fh, fcntl.LOCK_EX)
            except BaseException:
                fh.close()
                raise
    fh.seek(0)
    fh.truncate()
    who = "the robot" if os.environ.get("ROBOT_JOB") else "typed by hand"
    fh.write(f"{TITLES.get(what, what)} ({who}, since {datetime.now(INDIA):%H:%M} India time)")
    fh.flush()
    try:
        yield
    finally:
        fh.seek(0)
        fh.truncate()
        fh.close()                     # also releases the lock


def not_yet_hunted(db: Path) -> int:
    """Businesses of a city with no e-mail yet that the e-mail hunt has not looked at."""
    sys.path.insert(0, str(ROOT))
    from leadgen.hunt import HUNT_VERSION, LEADS

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(f"SELECT COUNT(*) FROM places WHERE {LEADS} AND key NOT IN (SELECT place_key FROM contacts "
                           "WHERE kind='email' AND confidence!='low') AND key NOT IN (SELECT place_key FROM tasks "
                           "WHERE kind='hunt' AND key LIKE ?)", (f"hunt:{HUNT_VERSION}:%",)).fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def cmd_hunt(a) -> int:
    """More e-mail hunting in cities searched before: the city with the most businesses still to look at first."""
    known = set(fleet())
    todo = sorted(((not_yet_hunted(db), db.stem) for db in DATA.glob("*.sqlite") if db.stem in known), reverse=True)
    todo = [(n, city) for n, city in todo if n]
    if not todo:
        print("Every business found so far has been looked at by the e-mail hunt.")
        return 0
    end = time.time() + a.minutes * 60
    worst = 0
    for n, city in todo:
        left = (end - time.time()) / 60
        if left < 5:
            break
        minutes = min(left, max(15.0, a.minutes / 2))
        print(f"\n{city}: {n} businesses without an e-mail not looked at yet ({minutes:.0f} min)")
        worst = max(worst, leadgen("email-hunt", "--config", f"config/us/{city}.toml", "--db", str(DATA / f"{city}.sqlite"),
                                   "--limit", "1500", "--budget-minutes", f"{minutes:.0f}"))
    return worst


def attachment() -> Path:
    """The PDF for first e-mails: your own copy (with your number), once `import` took it from Downloads, else the
    one in the code. Whichever is newer: a new PDF in the code (after  update ) replaces an older copy of yours until
    you import your copy of the new one."""
    own, public = DATA / "attachment.pdf", ROOT / "marketing" / "pitch.pdf"
    if own.is_file() and (not public.is_file() or own.stat().st_mtime >= public.stat().st_mtime):
        return own
    return public


def cmd_emails(a) -> int:
    ok, when = us_working_hours()
    if not ok and not a.now and not a.check:
        print(f"It is {when}: outside US working hours (Monday-Friday 08:30-16:30 there).\n"
              "E-mails that arrive at night look like spam. Run this again then (from India: about 8 PM to 3 AM),\n"
              "or add --now to send anyway.")
        return 0
    args = ["outreach", "--config", "config/us/outreach.toml", "--db", str(DATA / "outreach.sqlite"),
            "--mode", "dry-run" if a.dry_run else "live"]
    # Without --max, each run sends its share of today's limit (15 a day at first, rising slowly to 40), a few
    # minutes apart, spread over the US working day: the robot runs this every hour.
    if a.check:
        args += ["--max-emails", "0"]
    elif a.max is not None:
        args += ["--max-emails", str(a.max)]
    if not a.no_pdf:
        args += ["--attach", str(attachment())]
    if a.copy_to:
        args += ["--bcc", a.copy_to]
    sent = DATA / "last-sent.csv"
    sent.unlink(missing_ok=True)
    os.environ["OUTREACH_SENT_CSV"] = str(sent)
    code = leadgen(*args)
    if sent.is_file():
        with sent.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        print(f"\nE-mails sent this run ({len(rows)}):")
        for r in rows:
            print(f"  {r['Lead ID']}  {r['Business']}  ->  {r['To']}  [{r['Result']}]  \"{r['Subject']}\"")
        if a.copy_to and any(r["Result"] == "sent" for r in rows):
            # Gmail accepted it for both; whether it delivers is up to Gmail - the copy is the proof
            print(f"Gmail also took a blind copy of each for {a.copy_to}: it should be there within minutes "
                  "(Inbox or Spam). If not, docs/LOCAL.md, \"A test e-mail first\", says what to check.")
    return code


def download_folders() -> list[Path]:
    """Where a browser saves downloads: the tablet's Download folder (also inside Ubuntu), else ~/Downloads."""
    names = [os.environ.get("DOWNLOAD_DIR", ""), "/sdcard/Download", "/storage/emulated/0/Download",
             str(Path.home() / "Downloads")]
    out: list[Path] = []
    for n in names:
        p = Path(n) if n else None
        if p and p.is_dir() and not any(p.samefile(q) for q in out):
            out.append(p)
    return out


def cmd_import(a) -> int:
    folders = [Path(f) for f in a.folder] if a.folder else download_folders()
    found = lambda pattern: sorted({f for d in folders for f in d.glob(pattern) if f.is_file()},  # noqa: E731
                                   key=lambda f: f.stat().st_mtime)
    pdfs = sorted(found("Qrated-overview*.pdf") + found("GuestEcho-overview*.pdf"), key=lambda f: f.stat().st_mtime)
    if pdfs:                           # needs no lock: an e-mail run going on now reads the old or the new file whole
        tmp = DATA / "attachment.pdf.new"
        shutil.copyfile(pdfs[-1], tmp)
        os.replace(tmp, DATA / "attachment.pdf")
        print(f"Your PDF {pdfs[-1].name} is attached to first e-mails from now on.")
    lists = [str(f) for f in found("leads-*.zip") + found("leads-*.csv")]
    if not lists:
        print("No lead list (leads-<city>.zip or .csv) in " + ", ".join(map(str, folders)) + ". Download it first "
              "(docs/LOCAL.md, \"Lead lists from GitHub\").")
        return 0 if pdfs else 1
    print("Lead lists: " + ", ".join(Path(f).name for f in lists))
    with job_lock("import", wait=True):  # the Sheet gets one writer at a time: after the robot's job, if one runs
        return leadgen("import-leads", "--config", "config/us/austin.toml", *lists,
                       *(["--dry-run"] if a.dry_run else []))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="test the keys in .env (Google Sheet and Gmail)")
    le = sub.add_parser("leads", help="find businesses in the next US cities and look for their e-mail addresses")
    le.add_argument("--count", type=int, default=3, help="how many cities this time (default 3)")
    le.add_argument("--cities", default="", help="these cities instead, e.g. austin,miami")
    le.add_argument("--minutes", type=float, default=60.0, help="search time per city (default 60)")
    le.add_argument("--hunt-minutes", type=float, default=30.0, help="e-mail hunt time per city (default 30)")
    hu = sub.add_parser("hunt", help="more e-mail hunting in cities searched before")
    hu.add_argument("--minutes", type=float, default=60.0, help="time for all cities together (default 60)")
    em = sub.add_parser("emails", help="send today's e-mails, read replies, send follow-ups")
    em.add_argument("--dry-run", action="store_true", help="only prepare the e-mails (Email Preview tab)")
    em.add_argument("--now", action="store_true", help="also outside US working hours")
    em.add_argument("--max", type=int, default=None, help="this many new e-mails now (default: this hour's share)")
    em.add_argument("--attach-pdf", action="store_true", help=argparse.SUPPRESS)      # the PDF is attached anyway now
    em.add_argument("--no-pdf", action="store_true", help="first e-mails without the PDF")
    em.add_argument("--copy-to", default="", help="a blind copy of each first e-mail to this address (yours)")
    em.add_argument("--check", action="store_true", help="only read replies and bounces, send nothing (any time)")
    im = sub.add_parser("import", help="lead lists from GitHub (leads-<city>.zip) and your PDF (Qrated-overview.pdf) "
                                       "from Downloads")
    im.add_argument("--folder", action="append", default=[], help="look here instead of the Download folder")
    im.add_argument("--dry-run", action="store_true", help="only count what would be added to the Sheet")
    a = ap.parse_args(argv)
    DATA.mkdir(exist_ok=True)
    missing = load_env(ROOT / "settings.txt", ROOT / ".env")
    if missing:
        names = [("the Google key file (.json) in the secrets folder" if k == "GOOGLE_SERVICE_ACCOUNT_FILE" else k)
                 for k in missing]
        print("Still missing: " + ", ".join(names) + "\nFill them in settings.txt (Windows: open it with Notepad; "
              "Android: type  settings ), save, and run this again. Help: docs/LOCAL.md")
        # The lead search, the e-mail hunt and the import need only the Google Sheet; e-mails also need Gmail.
        if a.cmd in ("check", "emails") or "RQ_SHEET_ID" in missing or "GOOGLE_SERVICE_ACCOUNT_FILE" in missing:
            return 2
    run = {"check": cmd_check, "leads": cmd_leads, "hunt": cmd_hunt, "emails": cmd_emails, "import": cmd_import}[a.cmd]
    if a.cmd == "check":
        return run(a)
    if a.cmd == "import":              # takes the lock itself, for the Sheet part only, and waits for it
        try:
            return run(a)
        except KeyboardInterrupt:
            print("\nCancelled - the lead lists were not imported (type  import  again later).")
            return 130
    try:
        with job_lock(a.cmd):
            return run(a)
    except Busy as exc:
        print(f"Busy: {exc} is running. Try again when it has finished (robot status shows it).")
        return BUSY


if __name__ == "__main__":
    sys.exit(main())
