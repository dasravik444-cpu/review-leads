#!/usr/bin/env bash
# The Android commands (made by android/setup.sh) run this inside the Ubuntu in Termux:  inside.sh COMMAND [options]
cd "$(dirname "$0")/.." || exit 1
cmd=$1
shift
case "$cmd" in
  getkey)
    # The Google key file you downloaded on the tablet is in its Download folder (any name). Only Google
    # service-account keys are copied; other .json files stay where they are.
    found=0
    for f in "${DOWNLOAD_DIR:-/sdcard/Download}"/*.json; do
      [ -f "$f" ] && grep -q '"type": *"service_account"' "$f" && cp "$f" secrets/ && found=1
    done
    if [ "$found" = 1 ]; then
      echo "Copied. Google keys in the secrets folder now (the Sheet must be shared with the address of one):"
      for f in secrets/*.json; do
        email=$(grep -o '"client_email": *"[^"]*"' "$f" | cut -d'"' -f4)
        [ -n "$email" ] && echo "  ${f#secrets/}  ($email)"
      done
    else
      echo "No .json file in your Download folder. Download the Google key again (docs/LOCAL.md, step 3),"
      echo "and check that Termux may use storage: type  termux-setup-storage  in Termux and tap ALLOW."
    fi
    ;;
  settings)
    [ -f settings.txt ] || cp settings-example.txt settings.txt
    nano settings.txt
    ;;
  check|leads|emails)
    bash android/dns.sh
    exec bash "run_$cmd.sh" "$@"
    ;;
  update)
    bash android/dns.sh
    git pull --ff-only
    ;;
  *)
    echo "usage: inside.sh getkey|settings|check|leads|emails|update"
    exit 2
    ;;
esac
