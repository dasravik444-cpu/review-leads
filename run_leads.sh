#!/usr/bin/env bash
# Mac, Linux and Android (Termux + Ubuntu): in a terminal type  bash run_leads.sh   (docs/LOCAL.md)
cd "$(dirname "$0")"
if [ ! -f settings.txt ]; then
  cp settings-example.txt settings.txt
  echo "Your settings file settings.txt opens now. Fill it in, save it, then run this again."
  if [ "$(uname)" = "Darwin" ]; then open -e settings.txt; else "${EDITOR:-nano}" settings.txt; fi
  exit 0
fi
if [ ! -f .venv/.installed ]; then
  echo "Installing the first time - this takes a few minutes..."
  python3 -m venv .venv || { echo "Could not set up Python (on Ubuntu first run: apt install -y python3-venv)"; exit 1; }
  .venv/bin/python -m pip install --upgrade pip || exit 1
  .venv/bin/python -m pip install -r requirements.txt "duckdb>=1.1" || exit 1
  touch .venv/.installed
fi
mkdir -p data
.venv/bin/python scripts/local_run.py leads "$@"
