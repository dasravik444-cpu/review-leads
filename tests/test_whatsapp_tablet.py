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
    hours = "7 AM - 9 PM, every day" if market == "in" else "about 8 PM - 2 AM India time"
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
    env = {**os.environ, "STATE": str(tmp_path), "HOME": str(tmp_path), "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"}
    run = lambda keys, **extra: subprocess.run(["bash", str(ROOT / "android" / "whatsapp.sh")], input=keys,  # noqa: E731
                                               env={**env, **extra}, capture_output=True, text=True, timeout=60)
    out = run("\nn\n")                                        # the first one sent, the second not on WhatsApp
    assert out.returncode == 0, out.stderr
    assert "-> AUS-00002  Taco Town  +1 512-555-0101" in out.stdout and "Nothing more to send now (1 sent" in out.stdout
    log = (tmp_path / "log").read_text().splitlines()
    assert "am start -a android.intent.action.VIEW -d https://wa.me/15125550101?text=Hi -p com.whatsapp.w4b" in log
    assert "mark 3 k-1 +1 512-555-0101 Sent" in log and "mark 4 k-2 +1 512-555-0102 Not on WhatsApp" in log
    (tmp_path / "n").unlink()
    (tmp_path / "log").unlink()
    out = run("", LIST_CODE="4")                               # outside office hours: nothing is opened
    assert out.returncode == 0 and not (tmp_path / "log").exists()
    out = run("q\n")                                           # stop after looking at the first one
    assert "Stopped" in out.stdout and "mark" not in (tmp_path / "log").read_text()


def test_a_test_message_skipped_numbers_and_a_sheet_that_does_not_answer(monkeypatch, capsys):
    sess, client = queue_sheet([qrow("BLR-00001", "Olive Bistro", "+91 98450 11111"),
                                qrow("BLR-00002", "Saffron Lounge", "+91 80 4123 4567")], "India WhatsApp Queue")
    import leadgen.sheets

    monkeypatch.setattr(leadgen.sheets, "SheetsClient", lambda *a, **k: client)
    monkeypatch.setenv("MARKET", "in")
    lr = local_run()
    args = lambda action, **k: type("A", (), {"action": action, "now": True, "skip": [], **k})()  # noqa: E731
    # a test message to a number typed the Indian way: the Sheet is read, the chat link is made
    assert lr.cmd_whatsapp(args("test", number="987-654-3210")) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0] == "Google Sheet: connected, 2 messages in the India WhatsApp Queue tab."
    fields = out[-1].split("\t")
    assert fields[2] == "+919876543210" and fields[5].startswith("https://wa.me/919876543210?text=Test%20message")
    assert "running%20and%20synced" in fields[5]
    assert lr.cmd_whatsapp(args("test", number="12345")) == 2 and "not a phone number" in capsys.readouterr().out
    # numbers already dealt with this time are passed over, even before the Sheet has their result
    assert lr.cmd_whatsapp(args("next", skip=["+91 98450 11111"])) == 0
    assert capsys.readouterr().out.split("\t")[4] == "Saffron Lounge"
    # the Sheet does not answer: a clear message and exit code 5, no crash
    from leadgen.outreach import wa_queue

    monkeypatch.setattr(wa_queue, "pending", lambda *a: (_ for _ in ()).throw(ConnectionError("no internet")))
    assert lr.cmd_whatsapp(args("next")) == 5 and "Nothing is lost" in capsys.readouterr().out


ROBUST_STUBS = {
    "proot-distro": '''echo "$*" | sed 's/.*inside.sh //' >> "$STATE/calls"
case "$*" in
  *"whatsapp list"*) echo "WhatsApp Queue: 2 messages to send." ;;
  *"whatsapp next"*) [ -n "$NEXT_FAIL" ] && { echo "The Google Sheet did not answer"; exit 5; }
                     n=$(cat "$STATE/n" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$STATE/n"
                     case $n in
                       1) printf '3\\tk-1\\t+91 98450 11111\\tBLR-00001\\tOlive Bistro\\thttps://wa.me/919845011111?text=Hi\\n' ;;
                       2) printf '4\\tk-2\\t+91 80 4123 4567\\tBLR-00002\\tSaffron Lounge\\thttps://wa.me/918041234567?text=Hi\\n' ;;
                     esac ;;
  *"whatsapp mark"*) [ -n "$MARK_FAIL_ROW" ] && [[ "$*" == *"whatsapp mark $MARK_FAIL_ROW "* ]] && exit 5
                     echo "Saved" ;;
  *"whatsapp pdf"*)  printf 'marketing/pitch-in.pdf\tAurenflow-overview.pdf\n' ;;
  *"whatsapp test"*) echo "Google Sheet: connected, 2 messages in the India WhatsApp Queue tab."
                     printf '0\\t-\\t+919876543210\\t-\\tTest message\\thttps://wa.me/919876543210?text=Test\\n' ;;
esac''',
    "am": 'echo "am $*" >> "$STATE/calls"; echo "Starting: Intent { act=android.intent.action.VIEW }"',
    "termux-open-url": 'echo "open-url $*" >> "$STATE/calls"',
    "termux-share": 'echo "share $*" >> "$STATE/calls"',
}


@pytest.mark.skipif(not shutil.which("bash"), reason="needs bash")
def test_the_tablet_keeps_going_when_the_sheet_or_a_key_press_goes_wrong(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in ROBUST_STUBS.items():
        (stubs / name).write_text("#!/bin/bash\n" + body + "\n")
        (stubs / name).chmod(0o755)
    env = {**os.environ, "STATE": str(tmp_path), "HOME": str(tmp_path), "WHATSAPP_RETRY_SECONDS": "0",
           "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"}

    def run(*argv, keys="", **extra):
        (tmp_path / "calls").unlink(missing_ok=True)
        (tmp_path / "n").unlink(missing_ok=True)
        out = subprocess.run(["bash", str(ROOT / "android" / "whatsapp.sh"), *argv], input=keys, env={**env, **extra},
                             capture_output=True, text=True, timeout=60)
        calls = (tmp_path / "calls").read_text().splitlines() if (tmp_path / "calls").exists() else []
        return out, calls

    unsaved = tmp_path / ".review-leads" / "whatsapp-unsaved.tsv"
    # the Sheet does not take the first result: it is kept on the tablet, the next message still comes, and that
    # first number is not opened again; a wrong key just asks again. After the message, the PDF goes into the chat.
    out, calls = run(keys="\n\nx\nn\n", MARK_FAIL_ROW="3")
    assert out.returncode == 0, out.stderr
    assert "Kept on the tablet" in out.stdout and "Press Enter (sent), n (WhatsApp said" in out.stdout
    assert "whatsapp next --skip +91 98450 11111" in calls
    assert "whatsapp mark 4 k-2 +91 80 4123 4567 Not on WhatsApp" in calls
    assert unsaved.read_text() == "3\tk-1\t+91 98450 11111\tSent\n"            # tried again at the end, still kept
    assert "Nothing more to send now (1 sent, 1 with the PDF)" in out.stdout
    assert "1 earlier result(s) still waiting" in out.stdout
    pdf = tmp_path / ".review-leads" / "share" / "Aurenflow-overview.pdf"
    assert pdf.read_bytes() == (ROOT / "marketing" / "pitch-in.pdf").read_bytes()      # the e-mails' PDF, a good name
    uri = f"content://com.termux.files{pdf}"
    # the PDF's address as the intent's data too: only then may WhatsApp read it
    assert (f"am start -a android.intent.action.SEND -t application/pdf -d {uri} --grant-read-uri-permission --eu "
            f"android.intent.extra.STREAM {uri} --es jid 919845011111@s.whatsapp.net -p com.whatsapp.w4b") in calls
    method = tmp_path / ".review-leads" / "whatsapp-pdf-method"
    log = tmp_path / ".review-leads" / "whatsapp.log"
    assert method.read_text().strip() == "direct" and "PDF sent (direct) to +91 98450 11111" in log.read_text()
    assert sum(c.startswith("am start -a android.intent.action.SEND") for c in calls) == 1     # not after "n"
    props = (tmp_path / ".termux" / "termux.properties").read_text()
    assert props.count("allow-external-apps = true") == 1          # WhatsApp may read the shared PDF
    # next time it is saved first, before anything else; the Termux setting is not added twice
    out, calls = run(keys="q\n")
    assert calls[0] == "whatsapp mark 3 k-1 +91 98450 11111 Sent" and unsaved.read_text() == ""
    assert (tmp_path / ".termux" / "termux.properties").read_text() == props
    # the PDF did not show up ("n"): the share menu next, and that way is remembered for the next time
    out, calls = run(keys="\nn\n\nq\n")
    assert f"share -a send -c application/pdf {pdf}" in calls and "through the share menu" in out.stdout
    assert method.read_text().strip() == "menu" and "PDF did not show up (direct)" in log.read_text()
    out, calls = run(keys="\n\nq\n")
    assert not any("action.SEND" in c for c in calls) and f"share -a send -c application/pdf {pdf}" in calls
    # neither showed up: by hand, with the PDF copied where WhatsApp's paperclip finds it; still nothing: say so
    out, calls = run(keys="\nn\nn\nn\nq\n")
    assert "Now the PDF, by hand: in this chat tap the paperclip -> Document ->" in out.stdout
    assert "No way worked for this one. Show me the end of" in out.stdout and "1 sent, 0 with the PDF" not in out.stdout
    # only the PDF, to a number that already got the message (10 digits: an Indian number)
    method.write_text("direct\n")
    out, calls = run("pdf", "93217", "07545", keys="\n")
    assert out.returncode == 0 and "-> the PDF to +919321707545" in out.stdout
    assert any("--es jid 919321707545@s.whatsapp.net" in c for c in calls) and "whatsapp next" not in calls
    out, calls = run("--no-pdf", keys="\nq\n")
    assert not any("SEND" in c for c in calls) and "whatsapp pdf" not in calls
    # the Sheet does not answer at all: three tries, then a clear message - no crash
    out, calls = run(NEXT_FAIL="1")
    assert out.returncode == 0 and calls.count("whatsapp next") == 3
    assert "The WhatsApp Queue could not be read (0 sent so far)" in out.stdout
    # the test message: opened in WhatsApp Business, and what happened is said plainly
    out, calls = run("test", "987-654-3210", keys="\n\n")
    assert out.returncode == 0 and "Google Sheet: connected, 2 messages" in out.stdout
    assert "whatsapp test 987-654-3210" in calls
    assert "am start -a android.intent.action.VIEW -d https://wa.me/919876543210?text=Test -p com.whatsapp.w4b" in calls
    assert any("--es jid 919876543210@s.whatsapp.net" in c for c in calls)
    assert "Test sent: Termux, the Google Sheet and WhatsApp Business work together, the PDF too." in out.stdout
    out, _ = run("test", "987-654-3210", keys="n\n")
    assert "is not on WhatsApp: check the number" in out.stdout


def test_next_gives_yes_replies_first_then_the_oldest_days_messages(monkeypatch, capsys):
    def dated(day, *a, **k):
        r = qrow(*a, **k)
        r[0] = day
        return r
    sess, client = queue_sheet([dated("2026-10-16", "IN-3", "Day Three", "+91 98300 00003"),      # sorted by hand
                                dated("2026-10-14", "IN-1", "Day One", "+91 98300 00001"),
                                dated("2026-10-16", "IN-9", "Said Yes", "+91 98300 00009",
                                      why="Replied 'yes' to our e-mail - send the free preview"),
                                dated("2026-10-15", "IN-2", "Day Two", "+91 98300 00002")], "India WhatsApp Queue")
    import leadgen.sheets

    monkeypatch.setenv("MARKET", "in")
    monkeypatch.setattr(leadgen.sheets, "SheetsClient", lambda *a, **k: client)
    monkeypatch.setenv("RQ_SHEET_ID", "sheet")
    lr = local_run()
    order, skip = [], []
    for _ in range(5):
        args = type("A", (), {"action": "next", "skip": list(skip), "now": True})()
        lr._whatsapp(args)
        out = capsys.readouterr().out.strip()
        if not out:
            break
        fields = out.split("\t")
        order.append(fields[4])
        skip.append(fields[2])
    assert order == ["Said Yes", "Day One", "Day Two", "Day Three"]
