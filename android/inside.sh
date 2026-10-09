#!/usr/bin/env bash
# The Android commands (made by android/setup.sh) run this inside the Ubuntu in Termux:  inside.sh COMMAND [options]
cd "$(dirname "$0")/.." || exit 1
cmd=$1
shift
case "$cmd" in
  getkey)
    # The Google key file you downloaded on the tablet is in its Download folder (any name; only the
    # service-account key is used, other .json files are ignored).
    found=0
    for f in "${DOWNLOAD_DIR:-/sdcard/Download}"/*.json; do
      [ -f "$f" ] && cp "$f" secrets/ && found=1
    done
    if [ "$found" = 1 ]; then
      echo "Copied. In the secrets folder now:"; ls secrets
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
