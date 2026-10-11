"""A sending plan in time blocks ([outreach.email] plan / plan_then): how many e-mails one Gmail account may have sent
so far, counted from the plan's start.

    plan = [[6, 50], [6, 75], [6, 100], [6, 100], [12, 100], [12, 120], [12, 125], [12, 150]]
    plan_then = [12, 200]

means 50 e-mails in the first 6 hours, 75 in the next 6, ... and after the last block 200 every 12 hours. Within a
block the e-mails are spread evenly, so an hourly run sends about one hour's share, and a run that was missed (the
night's lead search keeps the robot busy) is made up by the next runs.
"""
from __future__ import annotations


def blocks(plan: list, then: list | None, hours: float) -> list[tuple[float, float, int]]:
    """(start hour, length in hours, e-mails) of each block up to `hours` after the start."""
    out, t = [], 0.0
    for length, count in plan:
        out.append((t, float(length), int(count)))
        t += float(length)
    if then:
        length, count = then
        while t <= hours:
            out.append((t, float(length), int(count)))
            t += float(length)
    return out


def allowed(plan: list, then: list | None, hours: float) -> float:
    """E-mails the plan allows from its start until `hours` after it (pro rata within a block)."""
    total = 0.0
    for start, length, count in blocks(plan, then, hours):
        if hours <= start:
            break
        total += count * min(1.0, (hours - start) / length)
    return total


def current(plan: list, then: list | None, hours: float) -> tuple[int, float, int] | None:
    """(block number from 1, its length in hours, its e-mails) at `hours` after the start; None after a plan with no
    plan_then."""
    for i, (start, length, count) in enumerate(blocks(plan, then, hours), start=1):
        if start <= hours < start + length:
            return i, length, count
    return None
