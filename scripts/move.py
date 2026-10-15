"""Move the robot from one device to another (the tablet to a phone and back), with everything it knows:

    move out     on the device the robot runs on now (after  robot off ): its memory, settings, Google key and your
                 PDF go into ONE file in the Download folder (review-leads-move.zip); this device's robot then
                 stays off until  move in  brings the memory back.
    move in      on the other device (after the one-paste setup): takes that file from its Download folder, puts
                 everything in place and deletes the file (it holds your Gmail app passwords). Then  robot on .

The memory is what makes the robot carry on where it stopped instead of starting again: which businesses got which
e-mail (follow-ups, bounces, the Do Not Contact list), where the sending plan stands, the city campaign's progress,
the WhatsApp queue. Only ONE device may run the robot: two would e-mail the same businesses and go over Gmail's
limit. Standard Python only (no setup needed): it runs on a phone that has nothing else yet.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATUS = DATA / "robot-status.json"
MOVED = DATA / "moved-out.txt"                 # this device's memory went to another device: its robot stays off
NAME = "review-leads-move.zip"
# What a move file may hold (nothing else is taken out of it): the memory, your PDF, the robot's record, settings, key.
ALLOWED = re.compile(r"^(data/[A-Za-z0-9._-]+\.sqlite|data/attachment[A-Za-z0-9-]*\.pdf|data/robot-status\.json|"
                     r"settings\.txt|\.env|secrets/[A-Za-z0-9._ ()-]+\.json)$")


def download_folders() -> list[Path]:
    names = [os.environ.get("DOWNLOAD_DIR", ""), "/sdcard/Download", "/storage/emulated/0/Download",
             str(Path.home() / "Downloads")]
    out: list[Path] = []
    for n in names:
        p = Path(n) if n else None
        if p and p.is_dir() and not any(p.samefile(q) for q in out):
            out.append(p)
    return out


def robot_running(now: float | None = None) -> bool:
    """The robot on this device reported in during the last 3 minutes."""
    try:
        beat = float((json.loads(STATUS.read_text(encoding="utf-8")).get("scheduler") or {}).get("heartbeat") or 0)
    except (OSError, ValueError, AttributeError):
        return False
    return beat > (now or time.time()) - 180


def _google_key(p: Path) -> bool:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(d, dict) and d.get("type") == "service_account"


def pack(target: Path) -> list[str]:
    """Everything the robot needs, into one zip file. Returns what went in."""
    names = []
    tmp = target.with_name(target.name + ".part")
    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for db in sorted(DATA.glob("*.sqlite")):
            copy = Path(td) / db.name                 # a consistent copy, also of a file another program has open
            src, dst = sqlite3.connect(db), sqlite3.connect(copy)
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            zf.write(copy, f"data/{db.name}")
            names.append(f"data/{db.name}")
        extra = [*sorted(DATA.glob("attachment*.pdf")), STATUS, ROOT / "settings.txt", ROOT / ".env",
                 *[p for p in sorted((ROOT / "secrets").glob("*.json")) if _google_key(p)]]
        for p in extra:
            if p.is_file():
                arc = p.relative_to(ROOT).as_posix()
                if ALLOWED.match(arc):
                    zf.write(p, arc)
                    names.append(arc)
    os.replace(tmp, target)
    return names


def unpack(src: Path, now: float | None = None) -> tuple[list[str], Path | None]:
    """Put a move file's contents in place. What this device had before goes into data/before-move-<time>/ first.
    Returns (what was put in place, where the earlier files went or None)."""
    now = now or time.time()
    with zipfile.ZipFile(src) as zf:
        members = [m for m in zf.namelist() if ALLOWED.match(m)]
        if not any(m.endswith(".sqlite") for m in members):
            raise ValueError(f"{src.name} holds no robot memory - is it the file  move out  made?")
        keep = DATA / f"before-move-{datetime.fromtimestamp(now):%Y%m%d-%H%M%S}"
        moved_aside = False
        for old in [*DATA.glob("*.sqlite"), *DATA.glob("attachment*.pdf"), STATUS]:
            if old.is_file():
                keep.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), keep / old.name)
                moved_aside = True
        for m in members:
            dest = ROOT / m
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            with zf.open(m) as fin, open(part, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            os.replace(part, dest)
            if m.startswith("secrets/") or m in ("settings.txt", ".env"):
                os.chmod(dest, 0o600)
    # The other device's robot was running a moment ago: its heartbeat must not make this one wait.
    if STATUS.is_file():
        try:
            st = json.loads(STATUS.read_text(encoding="utf-8"))
            st["scheduler"] = {"heartbeat": 0}
            st["running"] = None
            STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
        except (OSError, ValueError):
            STATUS.unlink(missing_ok=True)
    MOVED.unlink(missing_ok=True)
    return members, (keep if moved_aside else None)


def find_move_file() -> Path | None:
    files = [f for d in download_folders() for f in d.glob("review-leads-move*.zip") if f.is_file()]
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


def move_out() -> int:
    if robot_running():
        print("The robot is still running on this device. Type  robot off  first (it saves its work, up to 3 "
              "minutes), then  move out  again.")
        return 2
    if not any(DATA.glob("*.sqlite")):
        print("Nothing to move: this device has no robot memory (data/*.sqlite).")
        return 1
    folders = download_folders()
    if not folders:
        print("No Download folder found. Type  termux-setup-storage  in Termux, tap ALLOW, and try again.")
        return 1
    target = folders[0] / NAME
    names = pack(target)
    DATA.mkdir(exist_ok=True)
    MOVED.write_text(f"moved out {datetime.now():%Y-%m-%d %H:%M} to {target}\n", encoding="utf-8")
    size = target.stat().st_size / 1e6
    print(f"Packed {len(names)} files ({size:.0f} MB) into {target}")
    print("This device's robot now stays off until you type  move in  here again.")
    print("\nNext: send that file to the other device (Files app -> Download -> long-press the file -> Share ->\n"
          "Quick Share / Nearby Share), then type  move in  there. The file holds your Gmail app passwords:\n"
          "never send it by WhatsApp or e-mail, and delete it here once it has arrived.")
    return 0


def move_in() -> int:
    if robot_running():
        print("The robot is running on this device. Type  robot off  first, then  move in  again.")
        return 2
    src = find_move_file()
    if src is None:
        where = ", ".join(map(str, download_folders())) or "the Download folder"
        print(f"No {NAME} in {where}. Make it on the other device with  move out , send it here (Quick Share), "
              "and check that Termux may use storage (type  termux-setup-storage  and tap ALLOW).")
        return 1
    try:
        names, kept = unpack(src)
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        print(f"Could not use {src.name}: {exc}. Make it again with  move out  and send it once more.")
        return 1
    src.unlink(missing_ok=True)
    print(f"Moved in from {src.name}: {sum(n.endswith('.sqlite') for n in names)} memory files"
          + (", settings" if "settings.txt" in names else "")
          + (", Google key" if any(n.startswith("secrets/") for n in names) else "")
          + (", your PDF" if any("attachment" in n for n in names) else "") + ".")
    if kept:
        print(f"What this device had before is kept in {kept.relative_to(ROOT)}.")
    print(f"The file {src.name} was deleted (it holds your Gmail app passwords): delete it on the other device too.")
    print("\nNext:  check  (Google Sheet and Gmail OK?), then  robot on .")
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["out"]:
        return move_out()
    if args[:1] == ["in"]:
        return move_in()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
