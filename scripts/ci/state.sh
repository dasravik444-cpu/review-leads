#!/usr/bin/env bash
# Persist the state database between GitHub Actions runs as an ENCRYPTED artifact.
#   state.sh restore   download + decrypt the newest "rq-state" artifact of this branch
#   state.sh pack      checkpoint + compress + encrypt state/leadgen.sqlite into state-out/rq-state.enc
#   state.sh prune     delete older saved states of this branch, keeping the newest KEEP (default 3)
# The database (lead contacts) is never stored unencrypted, even in a private repository:
# AES-256-CBC with PBKDF2 (200k iterations) keyed by the RQ_STATE_KEY secret.
# ART_NAME is per campaign (rq-state-<campaign id>), so switching campaigns never mixes their memories.
# Private repositories have 500 MB of free artifact storage: prune keeps only the newest few.
set -euo pipefail

STATE_DIR="${STATE_DIR:-state}"
OUT_DIR="${OUT_DIR:-state-out}"
DB_NAME="${DB_NAME:-leadgen.sqlite}"      # outreach.sqlite for the outreach workflow
DB="$STATE_DIR/$DB_NAME"
ART_NAME="${ART_NAME:-rq-state}"

enc() { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -salt -pass env:RQ_STATE_KEY "$@"; }

need_key() {
  if [ -z "${RQ_STATE_KEY:-}" ]; then
    echo "::error::The RQ_STATE_KEY secret is not set. Add it under Settings > Secrets and variables > Actions (see docs/SETUP.md)."
    exit 1
  fi
}

case "${1:-}" in
  restore)
    need_key
    mkdir -p "$STATE_DIR"
    tmp=$(mktemp -d)
    # Read every page: there can be more than 100 saved states and the API does
    # not promise an order. A listing error stops the run rather than silently
    # starting a fresh campaign (which would then be saved as the newest state).
    api="${GITHUB_API_URL:-https://api.github.com}/repos/${GITHUB_REPOSITORY}/actions/artifacts?name=${ART_NAME}&per_page=100"
    : > "$tmp/all.jsonl"
    for page in $(seq 1 50); do
      curl -fsSL --retry 4 --retry-delay 5 --retry-all-errors \
        -H "Authorization: Bearer ${GH_TOKEN}" -H "Accept: application/vnd.github+json" \
        "$api&page=$page" > "$tmp/page.json"
      jq -c '.artifacts[]' "$tmp/page.json" >> "$tmp/all.jsonl"
      [ "$(jq '.artifacts | length' "$tmp/page.json")" -lt 100 ] && break
    done
    url=$(jq -rs --arg br "${GITHUB_REF_NAME}" \
      '[.[] | select(.expired == false and .workflow_run.head_branch == $br)] | sort_by(.created_at) | last | .archive_download_url // empty' \
      "$tmp/all.jsonl")
    if [ -z "$url" ]; then
      echo "No saved state for branch ${GITHUB_REF_NAME} - starting a fresh campaign state."
      exit 0
    fi
    curl -fsSL --retry 4 --retry-delay 5 --retry-all-errors \
      -H "Authorization: Bearer ${GH_TOKEN}" -o "$tmp/state.zip" "$url"
    unzip -q -o "$tmp/state.zip" -d "$tmp"
    if ! enc -d -in "$tmp/rq-state.enc" -out "$tmp/db.gz" 2>/dev/null; then
      echo "::error::Saved state could not be decrypted. Was RQ_STATE_KEY changed? Restore the old key, or delete the rq-state artifacts to start fresh."
      exit 1
    fi
    gunzip -c "$tmp/db.gz" > "$tmp/restored.sqlite"
    python - "$tmp/restored.sqlite" <<'PY'
import sqlite3, sys
ok = sqlite3.connect(sys.argv[1]).execute("PRAGMA integrity_check").fetchone()[0] == "ok"
print("state database integrity:", "ok" if ok else "FAILED")
sys.exit(0 if ok else 1)
PY
    mv "$tmp/restored.sqlite" "$DB"
    echo "Restored state ($(du -h "$DB" | cut -f1))."
    ;;
  pack)
    if [ ! -f "$DB" ]; then
      echo "No state database to save."
      exit 0
    fi
    need_key
    mkdir -p "$OUT_DIR"
    # Plain intermediates stay in a temp dir (the runner is discarded after the
    # job); only the encrypted file goes to OUT_DIR, which is uploaded.
    work=$(mktemp -d)
    if [ "$DB_NAME" = "leadgen.sqlite" ]; then
      python -m leadgen backup --db "$DB" --out "$work/leadgen.sqlite"
      if [ "${STATE_SLIM:-}" = "1" ]; then
        # The open-data extract is downloaded again next run (seconds): leaving it out keeps the saved copy small.
        python - "$work/leadgen.sqlite" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
con.execute("DELETE FROM open_places")
con.execute("DELETE FROM meta WHERE key LIKE 'overture_%'")
con.commit()
con.execute("VACUUM")
con.close()
print("open-data extract left out of the saved copy")
PY
      fi
    else
      python - "$DB" "$work/leadgen.sqlite" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    sys.exit("database integrity check FAILED - not saving")
con.execute("VACUUM INTO ?", (sys.argv[2],))
print("backup written")
PY
    fi
    gzip -9 -c "$work/leadgen.sqlite" > "$work/db.gz"
    enc -in "$work/db.gz" -out "$OUT_DIR/rq-state.enc"
    echo "Encrypted state ready ($(du -h "$OUT_DIR/rq-state.enc" | cut -f1))."
    ;;
  prune)
    keep="${KEEP:-3}"
    tmp=$(mktemp -d)
    api="${GITHUB_API_URL:-https://api.github.com}/repos/${GITHUB_REPOSITORY}/actions/artifacts?name=${ART_NAME}&per_page=100"
    : > "$tmp/all.jsonl"
    for page in $(seq 1 50); do
      curl -fsSL --retry 4 --retry-delay 5 --retry-all-errors \
        -H "Authorization: Bearer ${GH_TOKEN}" -H "Accept: application/vnd.github+json" \
        "$api&page=$page" > "$tmp/page.json" || { echo "::warning::could not list saved states - nothing pruned"; exit 0; }
      jq -c '.artifacts[]' "$tmp/page.json" >> "$tmp/all.jsonl"
      [ "$(jq '.artifacts | length' "$tmp/page.json")" -lt 100 ] && break
    done
    ids=$(jq -rs --arg br "${GITHUB_REF_NAME}" --argjson keep "$keep" \
      '[.[] | select(.expired == false and .workflow_run.head_branch == $br)] | sort_by(.created_at) | reverse | .[$keep:] | .[].id' \
      "$tmp/all.jsonl")
    n=0
    for id in $ids; do
      curl -fsSL -X DELETE -H "Authorization: Bearer ${GH_TOKEN}" -H "Accept: application/vnd.github+json" \
        "${GITHUB_API_URL:-https://api.github.com}/repos/${GITHUB_REPOSITORY}/actions/artifacts/$id" && n=$((n + 1)) || true
    done
    echo "Pruned $n older saved states (kept the newest $keep)."
    ;;
  *)
    echo "usage: $0 restore|pack|prune" >&2
    exit 2
    ;;
esac
