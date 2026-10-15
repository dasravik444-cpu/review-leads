"""Moving the robot to another device and back (scripts/move.py): everything it knows goes along in one file, only
one device runs it, and the file never carries anything but the robot's own files. Synthetic data only."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def mover(root: Path, download: Path, monkeypatch):
    spec = importlib.util.spec_from_file_location("move", ROOT / "scripts" / "move.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["move"] = mod
    spec.loader.exec_module(mod)
    for name, value in (("ROOT", root), ("DATA", root / "data"), ("STATUS", root / "data" / "robot-status.json"),
                        ("MOVED", root / "data" / "moved-out.txt")):
        monkeypatch.setattr(mod, name, value)
    monkeypatch.setattr(mod, "download_folders", lambda: [download])
    return mod


def device(tmp_path, name):
    root = tmp_path / name
    (root / "data").mkdir(parents=True)
    (root / "secrets").mkdir()
    return root


def test_move_out_and_in_carries_the_memory_settings_key_and_pdf_and_keeps_one_robot(tmp_path, monkeypatch, capsys):
    tablet, phone, download = device(tmp_path, "tablet"), device(tmp_path, "phone"), tmp_path / "Download"
    download.mkdir()
    con = sqlite3.connect(tablet / "data" / "outreach-in.sqlite")
    con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES('plan_started', '1760000000')")
    con.commit()                                       # left open: the copy must still be complete
    (tablet / "data" / "bengaluru.sqlite").write_bytes(b"")
    sqlite3.connect(tablet / "data" / "bengaluru.sqlite").close()
    (tablet / "data" / "attachment-in.pdf").write_bytes(b"%PDF mine")
    (tablet / "settings.txt").write_text("OUTREACH_GMAIL_APP_PASSWORD=abcd efgh ijkl mnop\n")
    (tablet / "secrets" / "review-leads-1.json").write_text(json.dumps({"type": "service_account", "client_email": "a@b"}))
    (tablet / "secrets" / "notes.json").write_text('{"a": 1}')              # not a Google key: stays
    (tablet / "review-leads-2.json").write_text("\ufeff" + json.dumps({"type": "service_account"}))  # main folder
    status = tablet / "data" / "robot-status.json"
    status.write_text(json.dumps({"scheduler": {"heartbeat": time.time()}, "jobs": {"leads": {"result": "ok"}}}))

    m = mover(tablet, download, monkeypatch)
    assert m.move_out() == 2 and "robot off" in capsys.readouterr().out     # still running here: not moved
    status.write_text(json.dumps({"scheduler": {"heartbeat": time.time() - 600}, "jobs": {"leads": {"result": "ok"}}}))
    assert m.move_out() == 0
    zf = zipfile.ZipFile(download / "review-leads-move.zip")
    assert sorted(zf.namelist()) == ["data/attachment-in.pdf", "data/bengaluru.sqlite", "data/outreach-in.sqlite",
                                     "data/robot-status.json", "secrets/review-leads-1.json",
                                     "secrets/review-leads-2.json", "settings.txt"]
    assert (tablet / "data" / "moved-out.txt").is_file()                   # the tablet's robot stays off now
    con.close()

    (phone / "data" / "outreach-in.sqlite").write_text("an old memory of the phone")
    m = mover(phone, download, monkeypatch)
    assert m.move_in() == 0
    out = capsys.readouterr().out
    assert "2 memory files, settings, Google key, your PDF" in out and "robot on" in out
    got = sqlite3.connect(phone / "data" / "outreach-in.sqlite").execute("SELECT value FROM meta").fetchone()
    assert got == ("1760000000",)
    assert (phone / "settings.txt").read_text().startswith("OUTREACH_GMAIL_APP_PASSWORD=")
    assert (phone / "settings.txt").stat().st_mode & 0o077 == 0
    assert json.loads((phone / "data" / "robot-status.json").read_text())["scheduler"]["heartbeat"] == 0
    assert json.loads((phone / "data" / "robot-status.json").read_text())["jobs"]["leads"]["result"] == "ok"
    assert not (download / "review-leads-move.zip").exists()                # it holds the app passwords: deleted
    kept = list((phone / "data").glob("before-move-*/outreach-in.sqlite"))
    assert len(kept) == 1 and kept[0].read_text() == "an old memory of the phone"
    assert m.move_in() == 1 and "No review-leads-move.zip" in capsys.readouterr().out


def test_a_move_file_with_anything_else_in_it_puts_only_the_robots_files_in_place(tmp_path, monkeypatch):
    phone, download = device(tmp_path, "phone"), tmp_path / "Download"
    download.mkdir()
    with zipfile.ZipFile(download / "review-leads-move (1).zip", "w") as zf:      # Quick Share's renamed copy
        zf.writestr("data/outreach-in.sqlite", b"")
        zf.writestr("../evil.sh", b"rm -rf /")
        zf.writestr("data/../../evil.txt", b"x")
        zf.writestr("scripts/robot.py", b"replaced")
    m = mover(phone, download, monkeypatch)
    assert m.move_in() == 0
    assert (phone / "data" / "outreach-in.sqlite").is_file()
    assert not (tmp_path / "evil.sh").exists() and not (tmp_path / "evil.txt").exists()
    assert not (phone / "scripts").exists()
    with zipfile.ZipFile(download / "review-leads-move.zip", "w") as zf:
        zf.writestr("settings.txt", b"x")                                          # no memory in it: refused
    assert m.move_in() == 1 and not (phone / "settings.txt").exists()


def test_the_robot_does_not_run_on_a_device_whose_memory_moved_out(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("robot", ROOT / "scripts" / "robot.py")
    r = importlib.util.module_from_spec(spec)
    sys.modules["robot"] = r
    spec.loader.exec_module(r)
    monkeypatch.setattr(r, "DATA", tmp_path / "data")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "moved-out.txt").write_text("moved out 2026-10-16 02:00\n")
    assert r.serve() == r.ALREADY_RUNNING and "move in" in capsys.readouterr().out
    text = (ROOT / "android" / "robot.sh").read_text()
    assert 'if [ -f "$HOST_DIR/data/moved-out.txt" ]; then' in text           # robot on refuses there too


@pytest.mark.parametrize("cmd", ["move"])
def test_the_tablet_commands_include_move_and_it_needs_no_settings(cmd):
    assert f" {cmd}; do" in (ROOT / "android" / "setup.sh").read_text()
    assert f"  {cmd})" in (ROOT / "android" / "inside.sh").read_text()
    run = (ROOT / "scripts" / "run.sh").read_text()
    assert run.index('if [ "$1" = move ]') < run.index("if [ ! -f settings.txt ]")
