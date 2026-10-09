#!/data/data/com.termux/files/usr/bin/bash
# One-time setup on an Android tablet or phone, inside the Termux app (docs/LOCAL.md, "Android").
# Paste this into Termux:
#   curl -fsSL https://raw.githubusercontent.com/dasravik444-cpu/review-leads/main/android/setup.sh | bash
# It installs a small Ubuntu Linux inside Termux, Python and the robot, and adds these commands to Termux:
#   getkey    copy the Google key file (.json) from your Download folder
#   settings  open your settings (settings.txt) to fill in
#   check     test the Google Sheet and Gmail
#   leads     find businesses in the next US cities and their e-mail addresses
#   emails    send today's e-mails (US working hours: about 8 PM - 3 AM India time)
#   update    get the newest version of the robot
set -e
REPO=https://github.com/dasravik444-cpu/review-leads
DIR=/root/review-leads

echo "== 1/4 Updating Termux (just wait)..."
apt-get update -y
apt-get -y -o Dpkg::Options::=--force-confold upgrade
apt-get -y -o Dpkg::Options::=--force-confold install proot-distro

echo "== 2/4 Asking for access to your Download folder (tap ALLOW if Android asks)..."
termux-setup-storage || true
sleep 3

echo "== 3/4 Installing Ubuntu inside Termux (a few hundred MB, 5-10 minutes)..."
if [ ! -d "$PREFIX/var/lib/proot-distro/installed-rootfs/ubuntu" ]; then
  proot-distro install ubuntu
fi
proot-distro login ubuntu -- env DEBIAN_FRONTEND=noninteractive apt-get update -y
proot-distro login ubuntu -- env DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv git nano ca-certificates
if proot-distro login ubuntu -- test -d "$DIR/.git"; then
  proot-distro login ubuntu -- git -C "$DIR" pull --ff-only
else
  proot-distro login ubuntu -- git clone "$REPO" "$DIR"
fi

echo "== 4/4 Adding the short commands..."
# Each command is a tiny script in Termux that runs the matching step inside Ubuntu.
for name in getkey settings check leads emails update; do
  {
    echo "#!$PREFIX/bin/bash"
    case "$name" in
      getkey)   echo "proot-distro login ubuntu -- bash $DIR/android/inside.sh getkey" ;;
      settings) echo "proot-distro login ubuntu -- bash $DIR/android/inside.sh settings" ;;
      check)    echo "proot-distro login ubuntu -- bash $DIR/run_check.sh \"\$@\"" ;;
      leads)    echo "termux-wake-lock; proot-distro login ubuntu -- bash $DIR/run_leads.sh \"\$@\"; termux-wake-unlock" ;;
      emails)   echo "termux-wake-lock; proot-distro login ubuntu -- bash $DIR/run_emails.sh \"\$@\"; termux-wake-unlock" ;;
      update)   echo "proot-distro login ubuntu -- git -C $DIR pull --ff-only" ;;
    esac
  } > "$PREFIX/bin/$name"
  chmod +x "$PREFIX/bin/$name"
done

echo
echo "Done. Next: type  getkey  then  settings  then  check   (docs/LOCAL.md)"
