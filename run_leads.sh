#!/usr/bin/env bash
# Mac / Linux: open Terminal in this folder and type  bash run_leads.sh   (docs/LOCAL.md)
cd "$(dirname "$0")"
if [ ! -f settings.txt ]; then
  cp settings-example.txt settings.txt
  echo 'Fill in settings.txt (it opens now), save it, then run this again.'
  (open -e settings.txt 2>/dev/null || ${EDITOR:-nano} settings.txt)
  exit 0
fi
if [ ! -f data/.installed ]; then
  echo "Installing the first time - this takes a few minutes..."
  python3 -m pip install -r requirements.txt "duckdb>=1.1" && mkdir -p data && echo ok > data/.installed || exit 1
fi
python3 scripts/local_run.py leads "$@"
