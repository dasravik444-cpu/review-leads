#!/usr/bin/env bash
# Today's WhatsApp messages on the tablet (the command  whatsapp , made by android/setup.sh):
#   whatsapp          one message after the other: the chat opens in WhatsApp Business with the message already
#                     typed, you press Send there, come back to Termux and say how it went (saved in the Sheet)
#   whatsapp list     only show what is waiting
#   whatsapp --now    also outside office hours (India: 10 AM - 6:30 PM, Monday to Saturday)
# Nothing is sent by a machine: WhatsApp's terms forbid automated and bulk messages and it bans numbers that send
# them. The robot fills the WhatsApp Queue tab with a few messages a day (more as the number gets older), only to
# numbers a business publishes as WhatsApp and to people who said yes; docs/WHATSAPP.md explains it all.
NAME=review-leads                                   # the Ubuntu inside Termux (android/setup.sh)
DIR=/root/review-leads
W4B=com.whatsapp.w4b                                # WhatsApp Business (not the personal WhatsApp)

inside() { proot-distro login "$NAME" -- bash "$DIR/android/inside.sh" "$@" </dev/null; }   # the keyboard stays here

# Open the chat in WhatsApp Business; if Android cannot aim at it, open the link as usual (Android then uses the app
# set for WhatsApp links: make that WhatsApp Business, docs/WHATSAPP.md step 3).
open_chat() {
  local out
  if command -v am >/dev/null 2>&1; then
    out="$(am start -a android.intent.action.VIEW -d "$1" -p "$W4B" 2>&1)"
    case "$out" in *rror*|*xception*|*"not started"*|*"Unable"*) ;; *) return 0 ;; esac
  fi
  echo "   (Opened with Android's app for WhatsApp links: check it is WhatsApp Business, not your personal WhatsApp.)"
  termux-open-url "$1"
}

now=""
case "${1:-}" in
  list)  shift; inside whatsapp list "$@"; exit $? ;;
  --now) now="--now" ;;
  "")    ;;
  *)     echo "usage: whatsapp [list] [--now]"; exit 2 ;;
esac

inside whatsapp list $now
code=$?
[ "$code" = 4 ] && exit 0                           # outside office hours (the list said so)
[ "$code" = 0 ] || exit "$code"

sent=0
while true; do
  # The last line is the message (a first run after an update may print installing notes before it).
  line="$(inside whatsapp next | tail -n 1)"
  IFS=$'\t' read -r row key number lead business link <<< "$line"
  case "$row" in ''|*[!0-9]*) echo; echo "Nothing more to send now ($sent sent). The robot adds new ones each working day."; break ;; esac
  case "$link" in https://wa.me/*) ;; *) echo "Could not read the next message - try  whatsapp  again."; exit 1 ;; esac
  echo
  echo "-> $lead  $business  $number"
  open_chat "$link"
  echo "   WhatsApp Business opens with the message typed: press Send there, then come back here."
  read -r -p "   [Enter] sent   n = not on WhatsApp   s = skip   q = stop for now: " answer || answer=q
  case "$answer" in
    q|Q) echo "Stopped. The rest stays in the list for next time."; break ;;
    n|N) result="Not on WhatsApp" ;;
    s|S) result="Skip" ;;
    *)   result="Sent"; sent=$((sent + 1)) ;;
  esac
  inside whatsapp mark "$row" "$key" "$number" "$result" | tail -n 1
done
