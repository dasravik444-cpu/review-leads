"""The WhatsApp Queue from the tablet (leadgen/outreach/wa_queue.py, scripts/local_run.py whatsapp, android/whatsapp.sh):
the owner sends each message in WhatsApp Business; the tablet opens the chat and saves the result in the Sheet."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import FakeSheetsSession

from leadgen.outreach import wa_queue
from leadgen.outreach.sheet import TABS
from leadgen.sheets import SheetsClient

ROOT = Path(__file__).resolve().parent.parent
TAB = "WhatsApp Queue"


def queue_sheet(rows, tab=TAB):
    sess = FakeSheetsSession()
    sess.tabs[tab] = {"id": 7, "rows": [list(TABS["whatsapp"])] + [list(r) for r in rows]}
    return sess, SheetsClient("sheet", session=sess)


def qrow(lead_id, business, number, result="", key="", why="Publishes this number as WhatsApp"):
    digits = "".join(ch for ch in number if ch.isdigit())
    return ["2026-10-12", lead_id, business, "Cafe", "Austin", number, why, "Hi team", f"https://wa.me/{digits}?text=Hi",
            result, key or f"k-{lead_id}"]


def results(sess, tab=TAB):
    col = TABS["whatsapp"].index("Result")
    return [r[col] if len(r) > col else "" for r in sess.tabs[tab]["rows"][1:]]


def test_the_queue_gives_the_messages_still_to_send_and_saves_each_result():
    sess, client = queue_sheet([qrow("AUS-00001", "Done Cafe", "+1 512-555-0100", "Sent"),
                                qrow("AUS-00002", "Taco Town", "+1 512-555-0101"),
                                qrow("AUS-00003", "Brew Lab", "+1 512-555-0102", key="k-brew"),
                                qrow("AUS-00003", "Brew Lab", "+1 512-555-0199", key="k-brew")])   # its next number
    todo = wa_queue.pending(client, TAB)
    assert [(t["row"], t["business"], t["number"]) for t in todo] == [
        (3, "Taco Town", "+1 512-555-0101"), (4, "Brew Lab", "+1 512-555-0102"), (5, "Brew Lab", "+1 512-555-0199")]
    assert todo[0]["link"].startswith("https://wa.me/15125550101") and todo[0]["key"] == "k-AUS-00002"
    assert wa_queue.mark(client, TAB, 3, "k-AUS-00002", "+1 512-555-0101", "Sent") == 3
    assert wa_queue.mark(client, TAB, 4, "k-brew", "+1 512-555-0102", "Not on WhatsApp") == 4
    assert results(sess) == ["Sent", "Sent", "Not on WhatsApp", ""]
    # someone sorted the tab by hand: the message is found again by its lead and number
    rows = sess.tabs[TAB]["rows"]
    rows[1:] = rows[1:][::-1]
    assert wa_queue.mark(client, TAB, 5, "k-brew", "+1 512-555-0199", "Skip") == 2
    assert wa_queue.mark(client, TAB, 3, "k-gone", "+1 000", "Sent") == 0            # not in the tab: nothing written
    with pytest.raises(ValueError):
        wa_queue.mark(client, TAB, 3, "k-brew", "+1 512-555-0199", "Delivered")
    assert wa_queue.pending(client, TAB) == []


def local_run():
    spec = importlib.util.spec_from_file_location("local_run", ROOT / "scripts" / "local_run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["local_run"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("market,tab", [("us", "WhatsApp Queue"), ("in", "India WhatsApp Queue")])
def test_the_command_prints_the_next_message_as_one_line_and_waits_for_office_hours(market, tab, monkeypatch, capsys):
    sess, client = queue_sheet([qrow("", "Taco\tTown", "+1 512-555-0101")], tab)          # no Lead ID, a tab in a name
    import leadgen.sheets

    monkeypatch.setenv("MARKET", market)                     # each market has its own queue tab
    monkeypatch.setattr(leadgen.sheets, "SheetsClient", lambda *a, **k: client)
    monkeypatch.setenv("RQ_SHEET_ID", "sheet")
    lr = local_run()
    real, seen = lr.cmd_whatsapp, []
    monkeypatch.setattr(lr, "load_env", lambda *a: [])
    monkeypatch.setattr(lr, "cmd_whatsapp", lambda a: seen.append(a) or 0)

    def run(*argv):                       # the tablet's exact command line, parsed by main, then the real command
        lr.main(["whatsapp", *argv])
        return real(seen.pop())

    assert run("next") == 0
    fields = capsys.readouterr().out.rstrip("\n").split("\t")
    assert fields == ["2", "k-", "+1 512-555-0101", "-", "Taco Town", "https://wa.me/15125550101?text=Hi"]
    monkeypatch.setattr(lr, "working_hours", lambda: (False, "Monday 02:00"))
    out = (run("list"), capsys.readouterr().out)
    hours = "10 AM - 6:30 PM, Monday to Saturday" if market == "in" else "about 8 PM - 2 AM India time"
    assert out[0] == 4 and "outside office hours in" in out[1] and hours in out[1]
    assert run("list", "--now") == 0
    monkeypatch.setattr(lr, "working_hours", lambda: (True, "Monday 11:00"))
    assert run("list") == 0 and "1 message to send" in capsys.readouterr().out
    assert run("mark", "2", "k-", "+1 512-555-0101", "Sent") == 0 and results(sess, tab) == ["Sent"]
    assert run("mark", "2", "k-", "+1 512-555-0101", "Interested") == 0 and results(sess, tab) == ["Interested"]


TABLET_STUBS = {
    # "inside whatsapp ..." in Ubuntu: two messages, then none; every result is logged
    "proot-distro": '''case "$*" in
  *"whatsapp list"*) echo "WhatsApp Queue: 2 messages to send."; exit "${LIST_CODE:-0}" ;;
  *"whatsapp next"*) n=$(cat "$STATE/n" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$STATE/n"
                     echo "Installing what it needs - this takes a few minutes..."
                     case $n in
                       1) printf '3\\tk-1\\t+1 512-555-0101\\tAUS-00002\\tTaco Town\\thttps://wa.me/15125550101?text=Hi\\n' ;;
                       2) printf '4\\tk-2\\t+1 512-555-0102\\t-\\tBrew Lab\\thttps://wa.me/15125550102?text=Hi\\n' ;;
                     esac ;;
  *"whatsapp mark"*) shift 6; echo "$*" >> "$STATE/log"; echo "Saved: ${@: -1}" ;;
esac''',
    "am": 'echo "am $*" >> "$STATE/log"; echo "Starting: Intent { act=android.intent.action.VIEW }"',
    "termux-open-url": 'echo "open-url $*" >> "$STATE/log"',
}


@pytest.mark.skipif(not shutil.which("bash"), reason="needs bash")
def test_the_tablet_opens_each_chat_in_whatsapp_business_and_saves_what_you_answer(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in TABLET_STUBS.items():
        (stubs / name).write_text("#!/bin/bash\n" + body + "\n")
        (stubs / name).chmod(0o755)
    env = {**os.environ, "STATE": str(tmp_path), "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"}
    run = lambda keys, **extra: subprocess.run(["bash", str(ROOT / "android" / "whatsapp.sh")], input=keys,  # noqa: E731
                                               env={**env, **extra}, capture_output=True, text=True, timeout=60)
    out = run("\nn\n")                                        # the first one sent, the second not on WhatsApp
    assert out.returncode == 0, out.stderr
    assert "-> AUS-00002  Taco Town  +1 512-555-0101" in out.stdout and "Nothing more to send now (1 sent)" in out.stdout
    log = (tmp_path / "log").read_text().splitlines()
    assert "am start -a android.intent.action.VIEW -d https://wa.me/15125550101?text=Hi -p com.whatsapp.w4b" in log
    assert "mark 3 k-1 +1 512-555-0101 Sent" in log and "mark 4 k-2 +1 512-555-0102 Not on WhatsApp" in log
    (tmp_path / "n").unlink()
    (tmp_path / "log").unlink()
    out = run("", LIST_CODE="4")                               # outside office hours: nothing is opened
    assert out.returncode == 0 and not (tmp_path / "log").exists()
    out = run("q\n")                                           # stop after looking at the first one
    assert "Stopped" in out.stdout and "mark" not in (tmp_path / "log").read_text()
