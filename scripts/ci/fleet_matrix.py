"""Which cities the fleet runs now, how many at a time and for how long (written to $GITHUB_OUTPUT format).

    python scripts/ci/fleet_matrix.py "<cities or empty>" <private: true|false> "<budget or empty>"

Public repository: every city in config/us/fleet.toml, 15 at a time, 150 minutes each (GitHub's minutes are free).
Private repository (2,000 minutes a month): one city per day, in turn, 25 minutes - unless cities are named.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]


def plan(requested: str, private: bool, budget: str, today: dt.date | None = None) -> dict:
    fleet = tomllib.loads((ROOT / "config" / "us" / "fleet.toml").read_text(encoding="utf-8"))["cities"]
    known = {p.stem for p in (ROOT / "config" / "us").glob("*.toml") if not p.stem.startswith("_")}
    missing = [c for c in fleet if c not in known]
    if missing:
        raise SystemExit(f"config/us/fleet.toml names cities without a file: {missing}")
    if requested.strip():
        cities = [c.strip() for c in requested.split(",") if c.strip()]
        unknown = [c for c in cities if c not in known]
        if unknown:
            raise SystemExit(f"unknown cities {unknown}; choose from {sorted(known)}")
    elif private:
        day = (today or dt.datetime.now(dt.timezone.utc).date()).toordinal()
        cities = [fleet[day % len(fleet)]]          # one city a day, in turn
    else:
        cities = list(fleet)
    minutes = int(budget) if budget.strip() else (25 if private else 150)
    return {"matrix": cities, "parallel": 1 if private else min(15, len(cities)), "budget": minutes}


if __name__ == "__main__":
    p = plan(sys.argv[1] if len(sys.argv) > 1 else "", (sys.argv[2] if len(sys.argv) > 2 else "true") == "true",
             sys.argv[3] if len(sys.argv) > 3 else "")
    print(f"matrix={json.dumps(p['matrix'])}")
    print(f"parallel={p['parallel']}")
    print(f"budget={p['budget']}")
