#!/usr/bin/env bash
# Helpers for the Android commands (android/setup.sh). They run inside Ubuntu, in the robot's folder.
cd "$(dirname "$0")/.."
case "$1" in
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
  *)
    echo "usage: inside.sh getkey|settings"
    ;;
esac
