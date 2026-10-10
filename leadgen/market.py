"""The market the tablet works on: India (the default since 10 October 2026) or the US.

Set in settings.txt as  MARKET=in  or  MARKET=us . A market has its own campaign files (config/<code>/: cities,
categories, the outreach texts), its own tabs in the Google Sheet (set in those files) and its own memory of
e-mails sent (data/<outreach_db>), so the two never mix. It also decides when e-mails and WhatsApp messages go out:
in the businesses' own office hours.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT = "in"


@dataclass(frozen=True)
class Market:
    code: str                      # "in" | "us": the folder config/<code>/ and the MARKET setting
    name: str                      # for messages: "India", "the US"
    tz: ZoneInfo                   # the businesses' local time
    place: str                     # how that time is named on screen: "India", "Chicago"
    days: tuple[int, ...]          # working days, 0 = Monday
    hours: tuple[float, float]     # office hours for e-mails and WhatsApp (local time, hours as decimals)
    email_slots: tuple[str, ...]   # the robot's e-mail runs (local time)
    outreach_db: str               # the outreach memory file in data/
    pdf_suffix: str                # marketing/pitch<suffix>.pdf, data/attachment<suffix>.pdf
    own_pdfs: tuple[str, ...]      # the owner's copy of the PDF in Downloads (newest wins), for  import
    india_time: str                # the same hours in India time, for messages on the tablet

    def is_working_time(self, now: datetime | None = None) -> tuple[bool, str]:
        """(within office hours?, "Monday 10:00 in Chicago")."""
        now = (now or datetime.now(self.tz)).astimezone(self.tz)
        hour = now.hour + now.minute / 60
        ok = now.weekday() in self.days and self.hours[0] <= hour < self.hours[1]
        return ok, now.strftime("%A %H:%M") + f" in {self.place}"


MARKETS = {
    "in": Market(code="in", name="India", tz=ZoneInfo("Asia/Kolkata"), place="India", days=(0, 1, 2, 3, 4, 5),
                 hours=(10.0, 18.5), email_slots=tuple(f"{h:02d}:35" for h in range(10, 18)),
                 outreach_db="outreach-in.sqlite", pdf_suffix="-in", own_pdfs=("Aurenflow-India-overview*.pdf",),
                 india_time="10 AM - 6:30 PM, Monday to Saturday"),
    "us": Market(code="us", name="the US", tz=ZoneInfo("America/Chicago"), place="Chicago", days=(0, 1, 2, 3, 4),
                 hours=(8.5, 16.5), email_slots=tuple(f"{h:02d}:35" for h in range(9, 16)),
                 outreach_db="outreach.sqlite", pdf_suffix="",
                 own_pdfs=("Aurenflow-overview*.pdf", "Qrated-overview*.pdf", "GuestEcho-overview*.pdf"),
                 india_time="about 8 PM - 2 AM India time on US working days"),
}


def current(settings: dict | None = None) -> Market:
    """The market from the settings (settings.txt, or the environment the runner filled from it); India if unset."""
    code = str((settings or {}).get("MARKET") or os.environ.get("MARKET") or DEFAULT).strip().lower()
    return MARKETS.get(code, MARKETS[DEFAULT])
