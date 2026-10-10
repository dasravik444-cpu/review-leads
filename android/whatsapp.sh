#!/usr/bin/env bash
# Today's WhatsApp messages on the tablet (the command  whatsapp , made by android/setup.sh):
#   whatsapp              one message after the other: the chat opens in WhatsApp Business with the message already
#                         typed, you press Send there, come back to Termux and say how it went (saved in the Sheet)
#   whatsapp list         only show what is waiting
#   whatsapp --now        also outside office hours (India: 10 AM - 6:30 PM, every day)
#   whatsapp test NUMBER  a test message to one number (e.g. your own): checks the Sheet, Termux and WhatsApp Business
# Nothing is sent by a machine: WhatsApp's terms forbid automated and bulk messages and it bans numbers that send
# them. The robot fills the WhatsApp Queue tab with a few messages a day (more as the number gets older); every
# phone number of a business is tried, one at a time. docs/WHATSAPP.md explains it all.
#
# Made not to fall over: a number that is not on WhatsApp is marked and the next message comes; no internet or a
# Google Sheet that does not answer means a few tries, then a clear message; a result the Sheet could not take is kept
# on the tablet and saved later (it is never lost, and that chat is never opened twice).
NAME=review-leads                                   # the Ubuntu inside Termux (android/setup.sh)
DIR=/root/review-leads
W4B=com.whatsapp.w4b                                # WhatsApp Business (not the personal WhatsApp)
KEEP="$HOME/.review-leads"
UNSAVED="$KEEP/whatsapp-unsaved.tsv"                # results the Sheet did not take yet: row, key, number, result
TEMPORARY=5                                         # local_run's exit code: the Sheet or the internet, try again later
RETRY="${WHATSAPP_RETRY_SECONDS:-15}"               # wait between tries when the Sheet does not answer

inside() { proot-distro login "$NAME" -- bash "$DIR/android/inside.sh" "$@" </dev/null; }   # the keyboard stays here

# Open the chat in WhatsApp Business; if Android cannot aim at it, open the link as usual (Android then uses the app
# set for WhatsApp links: make that WhatsApp Business, docs/WHATSAPP.md step 3). Fails only if neither works.
open_chat() {
  local out
  if command -v am >/dev/null 2>&1; then
    out="$(am start -a android.intent.action.VIEW -d "$1" -p "$W4B" 2>&1)"
    case "$out" in *rror*|*xception*|*"not started"*|*"Unable"*) ;; *) return 0 ;; esac
  fi
  echo "   (Opened with Android's app for WhatsApp links: check it is WhatsApp Business, not your personal WhatsApp.)"
  termux-open-url "$1" 2>/dev/null
}

# Save one result in the Sheet; when the Sheet cannot be reached it is kept on the tablet for the next time.
save() {
  local out code
  out="$(inside whatsapp mark "$@" 2>&1)"; code=$?
  if [ "$code" = 0 ] || [ "$code" = 1 ]; then          # 1: that row is no longer in the tab - nothing to keep
    printf '%s\n' "$out" | tail -n 1
    return 0
  fi
  mkdir -p "$KEEP"
  printf '%s\t%s\t%s\t%s\n' "$@" >> "$UNSAVED"
  echo "   Kept on the tablet (the Sheet did not answer): it is saved by itself next time."
}

# Results kept on the tablet earlier: save them now (those the Sheet still does not take stay kept).
save_unsaved() {
  [ -s "$UNSAVED" ] || return 0
  local left="$UNSAVED.left" row key number result code
  : > "$left"
  while IFS=$'\t' read -r row key number result; do
    [ -n "$row" ] || continue
    inside whatsapp mark "$row" "$key" "$number" "$result" >/dev/null 2>&1; code=$?
    if [ "$code" != 0 ] && [ "$code" != 1 ]; then
      printf '%s\t%s\t%s\t%s\n' "$row" "$key" "$number" "$result" >> "$left"
    fi
  done < "$UNSAVED"
  mv "$left" "$UNSAVED"
  [ -s "$UNSAVED" ] && echo "($(wc -l < "$UNSAVED") earlier result(s) still waiting for the Sheet - saved next time.)"
  return 0
}

# Ask until the answer is one of the keys.
ask() {
  local answer
  while true; do
    read -r -p "   [Enter] sent   n = not on WhatsApp   s = skip   q = stop for now: " answer || answer=q
    case "$answer" in
      "")  result="Sent" ;;
      n|N) result="Not on WhatsApp" ;;
      s|S) result="Skip" ;;
      q|Q) result="" ;;
      *)   echo "   Press Enter (sent), n (WhatsApp said the number is not on WhatsApp), s (skip) or q (stop)."; continue ;;
    esac
    return 0
  done
}

stopped() { echo; echo "Stopped. The rest stays in the list for next time."; save_unsaved; exit 0; }
trap stopped INT

now=""
case "${1:-}" in
  list) shift; inside whatsapp list "$@"; exit $? ;;
  test)
    shift
    [ -n "${1:-}" ] || { echo "usage: whatsapp test NUMBER   (for example: whatsapp test 98765 43210)"; exit 2; }
    out="$(inside whatsapp test "$*")"; code=$?
    line="$(printf '%s\n' "$out" | tail -n 1)"
    IFS=$'\t' read -r _ _ number _ _ link <<< "$line"
    case "$link" in
      https://wa.me/*) ;;
      *) printf '%s\n' "$out" | tail -n 3; exit "$([ "$code" = 0 ] && echo 1 || echo "$code")" ;;
    esac
    printf '%s\n' "$out" | sed '$d' | tail -n 2         # what it says about the Sheet
    echo "-> test message to $number"
    open_chat "$link" || { echo "Could not open WhatsApp Business: is it installed on this tablet?"; exit 1; }
    echo "   WhatsApp Business opens with the test message typed: press Send there, then come back here."
    ask
    case "$result" in
      Sent) echo "Test sent: Termux, the Google Sheet and WhatsApp Business work together." ;;
      "Not on WhatsApp") echo "WhatsApp says $number is not on WhatsApp: check the number and try again." ;;
      *) echo "No test sent." ;;
    esac
    exit 0 ;;
  --now) now="--now" ;;
  "")    ;;
  *)     echo "usage: whatsapp [list | test NUMBER] [--now]"; exit 2 ;;
esac

save_unsaved
inside whatsapp list $now
code=$?
[ "$code" = 4 ] && exit 0                           # outside office hours (the list said so)
if [ "$code" != 0 ]; then
  echo "The WhatsApp Queue could not be read just now (no internet, or Google did not answer). Try  whatsapp  again in a minute."
  exit 0
fi

sent=0
handled=()                                          # numbers dealt with this time: never opened twice
while true; do
  skip=()
  for n in "${handled[@]}"; do skip+=(--skip "$n"); done
  line=""
  for try in 1 2 3; do
    out="$(inside whatsapp next "${skip[@]}")"; code=$?
    [ "$code" = 0 ] && { line="$(printf '%s\n' "$out" | tail -n 1)"; break; }   # the last line is the message
    [ "$try" = 3 ] || { echo "   (The Sheet did not answer - trying again in $RETRY seconds.)"; sleep "$RETRY"; }
  done
  if [ "$code" != 0 ]; then
    echo; echo "The WhatsApp Queue could not be read ($sent sent so far). Check the internet and type  whatsapp  again."
    break
  fi
  IFS=$'\t' read -r row key number lead business link <<< "$line"
  case "$row" in ''|*[!0-9]*) echo; echo "Nothing more to send now ($sent sent). The robot adds new ones every day."; break ;; esac
  handled+=("$number")
  case "$link" in https://wa.me/*) ;; *) echo "   (That message has no chat link - skipped.)"; continue ;; esac
  echo
  echo "-> $lead  $business  $number"
  if ! open_chat "$link"; then
    echo "   Could not open WhatsApp Business for this one - left in the list for next time."
    continue
  fi
  echo "   WhatsApp Business opens with the message typed: press Send there, then come back here."
  echo "   If WhatsApp says the number is not on WhatsApp, press n: the business's next number comes later."
  ask
  [ -n "$result" ] || stopped
  [ "$result" = "Sent" ] && sent=$((sent + 1))
  save "$row" "$key" "$number" "$result"
done
save_unsaved
exit 0
