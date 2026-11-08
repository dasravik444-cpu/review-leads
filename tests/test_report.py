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
    r = lr.report_data(14, datetime(2026, 11, 8, 12, tzinfo=IST))
    assert r["days"]["2026-11-06"] == {"first": 4, "followup": 0, "bounced": 2, "positive": 0, "other": 0, "negative": 0}
    assert r["days"]["2026-11-07"] == {"first": 0, "followup": 2, "bounced": 2, "positive": 1, "other": 1, "negative": 0}
    assert [(x["kind"], x["their_email"], x["our_account"], x["business"]) for x in r["replies"]] == [
        ("positive", "owner@leafcafe.in", "one@gmail.com", "Cafe 1"), ("other", "hi@brew.in", "two@gmail.com", "Cafe 2")]
    assert lr.cmd_report(type("A", (), {"days": 14, "all": False})()) == 0
    out = capsys.readouterr().out
    assert "Interested replies (1):" in out and "owner@leafcafe.in" in out and "to one@gmail.com" in out
    assert "In the middle replies (1):" in out and "How much does it cost?" in out
    assert "Out of office" not in out
    assert (tmp_path / "Download" / "aurenflow-replies.csv").read_text().count("\n") == 3
