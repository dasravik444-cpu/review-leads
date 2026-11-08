"""report: e-mails per day and every reply, from all Gmail accounts' memory (synthetic data only)."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from leadgen.outreach.store import OutreachStore

ROOT = Path(__file__).resolve().parent.parent
IST = ZoneInfo("Asia/Kolkata")


def ts(d, h=11):
    return datetime(2026, 11, d, h, tzinfo=IST).timestamp()


def test_report_counts_each_day_and_lists_who_replied(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MARKET", "in")
    spec = importlib.util.spec_from_file_location("local_run", ROOT / "scripts" / "local_run.py")
    lr = importlib.util.module_from_spec(spec)
    sys.modules["local_run"] = lr
    spec.loader.exec_module(lr)
    monkeypatch.setattr(lr, "DATA", tmp_path)
    (tmp_path / "Download").mkdir()
    monkeypatch.setattr(lr, "download_folders", lambda: [tmp_path / "Download"])
    monkeypatch.setattr(lr, "gmail_accounts", lambda: [("one@gmail.com", "x"), ("two@gmail.com", "y")])
    for i, (who, kind) in enumerate([("owner@leafcafe.in", "positive"), ("hi@brew.in", "other")], start=1):
        st = OutreachStore(str(lr.account_db(i)))
        c = st.conn
        for n, (day, step, status) in enumerate([("2026-11-06", 1, "sent"), ("2026-11-06", 1, "invalid"),
                                                ("2026-11-07", 2, "sent"), ("2026-11-07", 1, "bounced")]):
            c.execute("INSERT INTO sends(email,lead_key,step,sent_at,day,status) VALUES(?,?,?,?,?,?)",
                      (f"a{n}@x{i}.in", f"k{n}", step, ts(6), day, status))
        c.execute("INSERT INTO threads(email,lead_key,lead_id,business,stage,updated_at) VALUES(?,?,?,?,?,?)",
                  (who, "k9", f"BLR-0000{i}", f"Cafe {i}", "replied", 0))
        c.execute("INSERT INTO replies(email,lead_key,kind,received_at,snippet) VALUES(?,?,?,?,?)",
                  (who, "k9", kind, ts(7, 15), "Yes please send the preview" if i == 1 else "How much does it cost?"))
        c.execute("INSERT INTO replies(email,lead_key,kind,received_at,snippet) VALUES(?,?,?,?,?)",
                  ("bot@x.in", "k8", "auto", ts(7, 16), "Out of office"))
        c.execute("INSERT INTO replies(email,lead_key,kind,received_at,snippet) VALUES(?,?,?,?,?)",    # stored as
                  ("care@x.in", "k7", "positive", ts(7, 17), "How was your experience? Rate us with one tap."))  # "yes"
    r = lr.report_data(14, datetime(2026, 11, 8, 12, tzinfo=IST))
    assert r["days"]["2026-11-06"] == {"first": 4, "followup": 0, "bounced": 2, "positive": 0, "other": 0, "negative": 0}
    assert r["days"]["2026-11-07"] == {"first": 0, "followup": 2, "bounced": 2, "positive": 1, "other": 1, "negative": 0}
    assert [(x["kind"], x["their_email"], x["our_account"], x["business"]) for x in r["replies"]] == [
        ("positive", "owner@leafcafe.in", "one@gmail.com", "Cafe 1"), ("other", "hi@brew.in", "two@gmail.com", "Cafe 2")]
    import leadgen.outreach.inbox as inbox

    class Gmail:                      # you answered Cafe 1 by e-mail; Cafe 2's question you opened but did not answer
        def __init__(self, addr, pw):
            self.addr = addr

        def answered(self, items):
            return {e: ({"seen": True, "answered": True} if self.addr == "one@gmail.com" else
                        {"seen": True, "answered": False}) for e, _u, _t in items}
    monkeypatch.setattr(inbox, "GmailInbox", Gmail)
    assert lr.cmd_report(type("A", (), {"days": 14, "all": False, "offline": False})()) == 0
    out = capsys.readouterr().out
    assert ("Replies from real people since day one: 2 - 1 answered by you, 1 still waiting for your answer. "
            "Left out: 2 automatic replies (receipts, tickets, surveys).") in out
    assert "Not answered yet - interested (0): none" in out
    assert "Not answered yet - in the middle (1):" in out and "hi@brew.in" in out and "to two@gmail.com, opened" in out
    assert "How much does it cost?" in out and "owner@leafcafe.in" not in out and "Out of office" not in out
    csv_text = (tmp_path / "Download" / "aurenflow-replies.csv").read_text()
    assert csv_text.count("\n") == 3 and "answered,opened" in csv_text
    assert lr.cmd_report(type("A", (), {"days": 14, "all": False, "offline": True})()) == 0     # no Gmail look
    out = capsys.readouterr().out
    assert "2 still waiting" in out and "Gmail not checked" in out and "owner@leafcafe.in" in out


def test_gmail_says_who_you_answered_and_which_replies_you_opened():
    from email.utils import format_datetime

    from leadgen.outreach.inbox import GmailInbox

    reply_at = ts(7, 15)
    sent = {"owner@leafcafe.in": [(501, ts(7, 18))], "hi@brew.in": [(502, ts(6, 9))]}    # Brew: only our 1st e-mail

    class Conn:
        def __init__(self):
            self.box = ""

        def login(self, u, p):
            return "OK", [b""]

        def select(self, box, readonly=False):
            self.box = box
            return "OK", [b"1"]

        def list(self):
            return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

        def uid(self, cmd, *args):
            if cmd == "FETCH" and args[1] == "(FLAGS)":
                flags = "\\Seen" if args[0] == "11" else ""
                return "OK", [f"1 (UID {args[0]} FLAGS ({flags}))".encode()]
            if cmd == "SEARCH":
                addr = args[2].strip('"')
                return "OK", [" ".join(str(u) for u, _ in sent[addr]).encode()]
            if cmd == "FETCH":
                when = next(t for v in sent.values() for u, t in v if str(u) == args[0])
                head = f"Date: {format_datetime(datetime.fromtimestamp(when, IST))}\r\n\r\n".encode()
                return "OK", [(b"1 (UID x BODY[HEADER.FIELDS (DATE)] {40}", head), b")"]
            raise AssertionError(cmd)

        def logout(self):
            pass
    got = GmailInbox("one@gmail.com", "pw", imap_factory=Conn).answered(
        [("owner@leafcafe.in", 11, reply_at), ("hi@brew.in", 12, reply_at)])
    assert got == {"owner@leafcafe.in": {"seen": True, "answered": True},
                   "hi@brew.in": {"seen": False, "answered": False}}
