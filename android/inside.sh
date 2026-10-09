#!/usr/bin/env bash
# The Android commands (made by android/setup.sh) run this inside the Ubuntu in Termux:  inside.sh COMMAND [options]
cd "$(dirname "$0")/.." || exit 1
cmd=$1
shift
PROJECT=review-leads                    # this business's Google Cloud project (its keys are named review-leads-...)

field() { grep -o "\"$1\": *\"[^\"]*\"" "$2" 2>/dev/null | head -n 1 | cut -d'"' -f4; }
google_key() { [ -f "$1" ] && [ "$(field type "$1")" = service_account ]; }
ours() { case "$(field project_id "$1")" in "$PROJECT"*) return 0 ;; *) return 1 ;; esac; }

case "$cmd" in
  getkey)
    # The Google key file you downloaded on the tablet is in its Download folder (any name). Only keys of this
    # business's project are taken: other keys there (Plant Parlour's) stay out of this robot.
    mkdir -p secrets
    for f in secrets/*.json; do         # copies of other projects' keys that an earlier getkey took
      if google_key "$f" && ! ours "$f"; then rm -f "$f"; echo "Removed ${f#secrets/} (not this business's key)"; fi
    done
    found=0
    for f in "${DOWNLOAD_DIR:-/sdcard/Download}"/*.json; do
      if google_key "$f" && ours "$f"; then cp "$f" secrets/ && found=1; fi
    done
    if [ "$found" = 1 ]; then
      echo "Copied. This business's Google keys in the secrets folder (the Sheet must be shared with this address):"
      for f in secrets/*.json; do
        google_key "$f" && echo "  ${f#secrets/}  ($(field client_email "$f"))"
      done
    else
      echo "No key of the Google Cloud project $PROJECT in your Download folder (its name starts with $PROJECT-)."
      echo "Download it again (docs/LOCAL.md, step 3), and check that Termux may use storage: type"
      echo "termux-setup-storage  in Termux and tap ALLOW."
    fi
    ;;
  settings)
    [ -f settings.txt ] || cp settings-example.txt settings.txt
    nano settings.txt
    ;;
  check|leads|hunt|emails|import)
    bash android/dns.sh
    exec bash scripts/run.sh "$cmd" "$@"
    ;;
  robot)                                # the robot's timetable, status, log (scripts/robot.py)
    exec bash scripts/run.sh robot "$@"
    ;;
  update)
    bash android/dns.sh
    git pull --ff-only
    ;;
  *)
    echo "usage: inside.sh getkey|settings|check|leads|hunt|emails|import|robot|update"
    exit 2
    ;;
esac
