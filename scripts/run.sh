#!/usr/bin/env bash
# What run_check.sh, run_leads.sh and run_emails.sh do (Mac, Linux, Android):  bash scripts/run.sh COMMAND [options]
# COMMAND: check, leads, hunt, emails or import (scripts/local_run.py), or robot ... (scripts/robot.py).
# The first time it makes settings.txt and installs what is needed.
cd "$(dirname "$0")/.." || exit 1
if [ ! -f settings.txt ]; then
  cp settings-example.txt settings.txt
  echo "Your settings file settings.txt opens now. Fill it in, save it, then run this again."
  if [ "$(uname)" = "Darwin" ]; then open -e settings.txt; else "${EDITOR:-nano}" settings.txt; fi
  exit 0
fi
# Installs what it needs the first time, and again after an update that needs something new.
if ! cmp -s requirements.txt .venv/.installed; then
  echo "Installing what it needs - this takes a few minutes..."
  python3 -m venv .venv || { echo "Could not set up Python (on Ubuntu first run: apt install -y python3-venv)"; exit 1; }
  .venv/bin/python -m pip install --upgrade pip || exit 1
  .venv/bin/python -m pip install -r requirements.txt "duckdb>=1.1" || exit 1
  cp requirements.txt .venv/.installed
fi
mkdir -p data
if [ "$1" = robot ]; then
  shift
  exec .venv/bin/python scripts/robot.py "$@"           # the robot's timetable (scripts/robot.py)
fi
exec .venv/bin/python scripts/local_run.py "$@"
