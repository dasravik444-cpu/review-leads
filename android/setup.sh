#!/data/data/com.termux/files/usr/bin/bash
# One-time setup on an Android tablet or phone, inside the Termux app (docs/LOCAL.md, "Android").
# Paste this into Termux:
#   curl -fsSL https://raw.githubusercontent.com/dasravik444-cpu/review-leads/main/android/setup.sh | bash
# It installs a small Ubuntu Linux inside Termux (its own, named review-leads: a Linux you may already have in
# Termux is left alone), Python and the robot, and adds these commands to Termux:
#   getkey    copy the Google key file (.json) from your Download folder
#   settings  open your settings (settings.txt) to fill in
#   check     test the Google Sheet and Gmail
#   leads     find businesses in the next US cities and their e-mail addresses
#   emails    send today's e-mails (US working hours: about 8 PM - 3 AM India time)
#   import    lead lists from GitHub (leads-<city>.zip) and your PDF, from your Download folder
#   update    get the newest version of the robot
#   robot     on | off | status | log: the robot that finds leads and sends e-mails by itself (android/robot.sh)
# If it stops halfway (a network hiccup), paste the line again: it carries on from where it stopped.
# Other systems in Termux (Plant Parlour) are not touched: when proot-distro already works it is left as it is, the
# robot has its own Ubuntu, and Termux's keep-awake lock is never released here.
set -e
REPO=https://github.com/dasravik444-cpu/review-leads
RAW=https://raw.githubusercontent.com/dasravik444-cpu/review-leads/main
NAME=review-leads                       # the Ubuntu inside Termux
DIR=/root/review-leads                  # the robot's folder in it
UBUNTU=https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release
APT=(apt-get -y -o Acquire::Retries=5 -o Dpkg::Options::=--force-confold)
UBUNTU_PACKAGES="python3 python3-venv git nano ca-certificates"

# pkg downloads from a volunteer mirror picked at random, and on 9 October the one it picked (linux.domainesia.com)
# broke off halfway. Termux's own server (packages-cf.termux.dev, behind Cloudflare) is used instead, written into
# the package lists the way pkg itself writes them.
use_termux_server() {
  local mirror="$PREFIX/etc/termux/mirrors/default" MAIN="" X11="" ROOT="" WEIGHT=""
  [ -f "$mirror" ] || return 0
  . "$mirror"
  point main "$MAIN" "stable main"
  point x11 "$X11" "x11 main"
  point root "$ROOT" "root stable"
}
point() {           # point REPO URL SUITE: one package list at URL, if that list is in use
  local lists="$PREFIX/etc/apt/sources.list.d"
  [ -n "$2" ] || return 0
  if [ -f "$lists/$1.sources" ]; then
    sed -i "s|^URIs:.*|URIs: $2|" "$lists/$1.sources"
  elif [ "$1" = main ]; then
    echo "deb $2 $3" > "$PREFIX/etc/apt/sources.list"
  elif [ -f "$lists/$1.list" ]; then
    echo "deb $2 $3" > "$lists/$1.list"
  fi
}

# Ubuntu 24.04 straight from Ubuntu (about 30 MB), checked against Ubuntu's own checksum list.
install_ubuntu() {
  local arch sums file want tarball
  case "$(dpkg --print-architecture)" in
    aarch64|arm64) arch=arm64 ;;
    arm|armhf) arch=armhf ;;
    x86_64|amd64) arch=amd64 ;;
    *) echo "Sorry, this device ($(dpkg --print-architecture)) is not supported."; exit 1 ;;
  esac
  sums=$(curl -fsSL --retry 5 "$UBUNTU/SHA256SUMS")
  file=$(grep -o "ubuntu-base-[0-9.]*-base-$arch\.tar\.gz" <<<"$sums" | sort -V | tail -n 1)
  want=$(awk -v f="*$file" '$2 == f { print $1 }' <<<"$sums")
  if [ -z "$file" ] || [ -z "$want" ]; then echo "Could not find Ubuntu for this device ($arch)."; exit 1; fi
  tarball="${TMPDIR:-$PREFIX/tmp}/$file"
  if [ "$(sha256sum "$tarball" 2>/dev/null | cut -d' ' -f1)" != "$want" ]; then
    curl -fL --retry 5 -C - -o "$tarball" "$UBUNTU/$file" ||
      { rm -f "$tarball"; curl -fL --retry 5 -o "$tarball" "$UBUNTU/$file"; }
  fi
  if [ "$(sha256sum "$tarball" | cut -d' ' -f1)" != "$want" ]; then
    rm -f "$tarball"
    echo "The Ubuntu download was damaged. Paste the line again."
    exit 1
  fi
  if ! proot-distro install --name "$NAME" "$tarball"; then
    echo "(This proot-distro is too old for that: getting the newest one...)"
    termux_packages
    proot-distro install --name "$NAME" "$tarball"
  fi
  rm -f "$tarball"
}

# proot-distro from Termux's own server, upgrading all of Termux only if it does not start otherwise.
termux_packages() {
  use_termux_server
  dpkg --configure -a || true
  "${APT[@]}" update || echo "(Some package lists could not be loaded. Carrying on.)"
  "${APT[@]}" install proot-distro
  if ! proot-distro list >/dev/null 2>&1; then
    echo "(proot-distro needs newer Termux parts: updating all of Termux, this can take a while...)"
    "${APT[@]}" dist-upgrade
    proot-distro list >/dev/null
  fi
}

ubuntu() { proot-distro login "$NAME" -- "$@"; }

main() {
  echo "== 1/5 Access to your Download folder (tap ALLOW if Android asks)..."
  [ -d "$HOME/storage" ] || termux-setup-storage || true

  echo "== 2/5 Termux: the tool that runs Ubuntu..."
  # Shared with Plant Parlour: when it works it stays exactly as it is. Otherwise only proot-distro and what it
  # needs are installed (upgrading all of Termux can mean hundreds of MB).
  proot-distro list >/dev/null 2>&1 || termux_packages

  echo "== 3/5 Ubuntu inside Termux..."
  proot-distro login "$NAME" -- true >/dev/null 2>&1 || install_ubuntu

  echo "== 4/5 Python and the robot inside Ubuntu (5-10 minutes)..."
  curl -fsSL --retry 5 "$RAW/android/dns.sh" | proot-distro login "$NAME" -- bash -s
  if ! ubuntu dpkg -s $UBUNTU_PACKAGES >/dev/null 2>&1; then
    ubuntu env DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 update
    ubuntu env DEBIAN_FRONTEND=noninteractive apt-get -y -o Acquire::Retries=5 install \
      --no-install-recommends $UBUNTU_PACKAGES
  fi
  if ubuntu test -d "$DIR/.git"; then
    ubuntu git -C "$DIR" pull --ff-only
  else
    ubuntu git clone "$REPO" "$DIR"
  fi

  echo "== 5/5 The short commands..."
  # Each command is a tiny script in Termux that runs the matching step inside Ubuntu.
  for cmd in getkey settings check leads emails import update; do
    {
      echo "#!$PREFIX/bin/bash"
      case "$cmd" in
        leads|emails)
          # Keeps the tablet awake while it works. The lock belongs to all of Termux (Plant Parlour holds it all
          # the time), so it is never released here.
          echo "termux-wake-lock"
          echo "exec proot-distro login $NAME -- bash $DIR/android/inside.sh $cmd \"\$@\"" ;;
        update)                         # everything new: the robot, these commands, what Ubuntu needs
          echo "set -o pipefail"
          echo "curl -fsSL --retry 5 $RAW/android/setup.sh | bash -s update ||"
          echo "  { echo 'The update stopped - check the internet and type  update  again.'; exit 1; }" ;;
        *)
          echo "exec proot-distro login $NAME -- bash $DIR/android/inside.sh $cmd \"\$@\"" ;;
      esac
    } > "$PREFIX/bin/.$cmd.new"
    chmod +x "$PREFIX/bin/.$cmd.new"
    mv -f "$PREFIX/bin/.$cmd.new" "$PREFIX/bin/$cmd"   # a new file: a running "update" keeps reading its old one
  done

  # robot: the switch of the robot that works by itself (android/robot.sh, read from inside Ubuntu's folder, so an
  # update of the robot also updates it).
  rootfs=$(proot-distro login "$NAME" --get-proot-cmd 2>/dev/null | grep -o -- '--rootfs=[^ \\]*' | head -n 1 | cut -d= -f2)
  if [ -n "$rootfs" ] && [ -f "$rootfs$DIR/android/robot.sh" ]; then
    printf '#!%s/bin/bash\nexec bash "%s" "$@"\n' "$PREFIX" "$rootfs$DIR/android/robot.sh" > "$PREFIX/bin/.robot.new"
    chmod +x "$PREFIX/bin/.robot.new"
    mv -f "$PREFIX/bin/.robot.new" "$PREFIX/bin/robot"
  else
    echo "(The robot command could not be set up: Ubuntu's folder was not found. Paste the setup line again.)"
  fi

  echo
  if [ "${1:-}" = update ]; then
    echo "Updated."
  else
    echo "Done. Next: type  getkey  then  settings  then  check   (docs/LOCAL.md)"
  fi
}

# This script arrives through a pipe (curl ... | bash). Everything above is only definitions, so nothing runs
# unless the whole script arrived, and questions are answered on the screen rather than by the rest of the script.
if (exec </dev/tty) 2>/dev/null; then main "$@" </dev/tty; else main "$@" </dev/null; fi
