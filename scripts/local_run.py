"""Run the lead search, the e-mail hunt and the outreach on your own computer (free, and within GitHub's terms).

    python scripts/local_run.py check                 are the keys in .env right? (Google Sheet, Gmail)
    python scripts/local_run.py leads                 the next 3 US cities, about an hour each, then their e-mail hunt
    python scripts/local_run.py leads --cities austin,miami --minutes 60 --hunt-minutes 30
    python scripts/local_run.py emails                today's e-mails, replies and follow-ups (US working hours only)
    python scripts/local_run.py emails --dry-run      only prepares them, in the Sheet's "Email Preview" tab

Your keys live in settings.txt in the main folder (the first run makes it from settings-example.txt); the Google
key file (.json) goes into the secrets folder and is found by itself. Each city's memory is a file in data/.
Nothing here needs GitHub: GitHub only stores the code. (docs/LOCAL.md explains it all.)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import tomllib

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
US_TIME = ZoneInfo("America/Chicago")
SEND_HOURS = (8.5, 16.5)            # US Central time, Monday to Friday (the outreach config's own window is 09:30-16:30)
KEYS = ("RQ_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_FILE", "OUTREACH_GMAIL_ADDRESS", "OUTREACH_GMAIL_APP_PASSWORD",
        "OUTREACH_SENDER_PHONE", "OUTREACH_POSTAL_ADDRESS")


def find_key_file() -> str:
    """The Google service-account key: the file named in the settings, else any service-account .json file in the
    secrets folder or the main folder (so it needs no renaming)."""
    named = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    if named:
        p = Path(named) if Path(named).is_absolute() else ROOT / named
        if p.is_file():
            return str(p)
    for folder in (ROOT / "secrets", ROOT):
        for p in sorted(folder.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("type") == "service_account" and data.get("client_email"):
                return str(p)
    return ""


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


def cmd_emails(a) -> int:
    ok, when = us_working_hours()
    if not ok and not a.now:
        print(f"It is {when}: outside US working hours (Monday-Friday 08:30-16:30 there).\n"
              "E-mails that arrive at night look like spam. Run this again then (from India: about 8 PM to 3 AM),\n"
              "or add --now to send anyway.")
        return 0
    args = ["outreach", "--config", "config/us/outreach.toml", "--db", str(DATA / "outreach.sqlite"),
            "--mode", "dry-run" if a.dry_run else "live"]
    # One run sends what today's limit still allows (15 a day at first, rising slowly to 40), a few minutes apart.
    args += ["--max-emails", str(a.max)]
    if a.attach_pdf:
        args += ["--attach", "marketing/pitch.pdf"]
    return leadgen(*args)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="test the keys in .env (Google Sheet and Gmail)")
    le = sub.add_parser("leads", help="find businesses in the next US cities and look for their e-mail addresses")
    le.add_argument("--count", type=int, default=3, help="how many cities this time (default 3)")
    le.add_argument("--cities", default="", help="these cities instead, e.g. austin,miami")
    le.add_argument("--minutes", type=float, default=60.0, help="search time per city (default 60)")
    le.add_argument("--hunt-minutes", type=float, default=30.0, help="e-mail hunt time per city (default 30)")
    em = sub.add_parser("emails", help="send today's e-mails, read replies, send follow-ups")
    em.add_argument("--dry-run", action="store_true", help="only prepare the e-mails (Email Preview tab)")
    em.add_argument("--now", action="store_true", help="also outside US working hours")
    em.add_argument("--max", type=int, default=40, help="at most this many new e-mails in this run (default 40)")
    em.add_argument("--attach-pdf", action="store_true", help="attach marketing/pitch.pdf to first e-mails")
    a = ap.parse_args(argv)
    DATA.mkdir(exist_ok=True)
    missing = load_env(ROOT / "settings.txt", ROOT / ".env")
    if missing:
        names = [("the Google key file (.json) in the secrets folder" if k == "GOOGLE_SERVICE_ACCOUNT_FILE" else k)
                 for k in missing]
        print("Still missing: " + ", ".join(names) + "\nFill them in settings.txt (open it with Notepad), save, and "
              "run this again. Help: docs/LOCAL.md")
        if a.cmd != "leads" or "RQ_SHEET_ID" in missing or "GOOGLE_SERVICE_ACCOUNT_FILE" in missing:
            return 2
    return {"check": cmd_check, "leads": cmd_leads, "emails": cmd_emails}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
