#!/usr/bin/env bash
# Today's WhatsApp messages on the tablet (the command  whatsapp , made by android/setup.sh):
#   whatsapp              one message after the other: the chat opens in WhatsApp Business with the message already
#                         typed, you press Send there, come back to Termux and say how it went (saved in the Sheet);
#                         then the same chat opens with the PDF ready, and you press Send again
#   whatsapp list         only show what is waiting
#   whatsapp --now        also outside office hours (India: 7 AM - 6:30 PM, every day)
#   whatsapp --no-pdf     the messages without the PDF
#   whatsapp pdf NUMBER   only the PDF, to one number (e.g. a business that got the message without it)
#   whatsapp test NUMBER  a test message and the PDF to one number (e.g. your own): checks the Sheet, Termux and
#                         WhatsApp Business
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
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
HOST_DIR="$(dirname "$(dirname "$SELF")")"          # the robot's folder, seen from Termux
SHARE="$KEEP/share"                                 # the PDF, under the name the businesses see
PDF=""
HAND=""
LOG="$KEEP/whatsapp.log"                            # what the tablet tried, for when something does not work
METHOD_FILE="$KEEP/whatsapp-pdf-method"             # the way of attaching the PDF that worked last

inside() { proot-distro login "$NAME" -- bash "$DIR/android/inside.sh" "$@" </dev/null; }   # the keyboard stays here
note() { mkdir -p "$KEEP"; printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }

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

# The PDF for the chats: the same one the e-mails carry (your own copy once  import  took it), copied under the
# name the business sees.
prepare_pdf() {
  local out rel name
  out="$(inside whatsapp pdf 2>&1 | tail -n 1)"
  IFS=$'\t' read -r rel name <<< "$out"
  if [ -z "$name" ] || [ ! -f "$HOST_DIR/$rel" ]; then
    echo "(No PDF this time${out:+: $out})"
    return 0
  fi
  mkdir -p "$SHARE" && cp "$HOST_DIR/$rel" "$SHARE/$name" && PDF="$SHARE/$name"
  allow_sharing
}

# WhatsApp reads the PDF through Termux's file sharing, which Termux allows only with allow-external-apps in
# ~/.termux/termux.properties (shared with Plant Parlour: this one line is added once, nothing else is changed).
allow_sharing() {
  local props="$HOME/.termux/termux.properties"
  grep -Eq '^[[:space:]]*allow-external-apps[[:space:]]*=[[:space:]]*true' "$props" 2>/dev/null && return 0
  mkdir -p "$HOME/.termux"
  printf '\n# review-leads: WhatsApp Business may read the PDF the  whatsapp  command shares\nallow-external-apps = true\n' >> "$props"
  command -v termux-reload-settings >/dev/null 2>&1 && termux-reload-settings >/dev/null 2>&1
  return 0
}

# How the PDF gets into the chat. Android phones differ, so there are three ways, tried in this order (the way that
# worked last on this tablet first, remembered in $METHOD_FILE):
#   direct  WhatsApp Business opens this business's chat with the PDF ready (one tap: Send)
#   menu    Android's share menu: WhatsApp Business, then the business at the top of the list (it was just written to)
#   hand    the paperclip in the chat -> Document -> the PDF in the Download folder
# Everything the tablet tries is written to $LOG, so a problem can be looked at later.
pdf_direct() {
  local digits="${1//[!0-9]/}" uri="content://com.termux.files$PDF" out
  # The PDF's address goes in twice: as the intent's data (only then does Android let WhatsApp read it) and as the
  # attachment WhatsApp takes; jid picks the chat.
  out="$(am start -a android.intent.action.SEND -t application/pdf -d "$uri" --grant-read-uri-permission \
           --eu android.intent.extra.STREAM "$uri" --es jid "$digits@s.whatsapp.net" -p "$W4B" 2>&1)"
  note "direct $digits: $out"
  case "$out" in *rror*|*xception*|*"Unable"*) return 1 ;; esac
  return 0
}

pdf_menu() {
  local out code
  if command -v termux-share >/dev/null 2>&1; then
    out="$(termux-share -a send -c application/pdf "$PDF" 2>&1)"; code=$?
    note "menu (termux-share) $code: $out"
    [ "$code" = 0 ] && return 0
  fi
  out="$(termux-open --send --chooser --content-type application/pdf "$PDF" 2>&1)"; code=$?
  note "menu (termux-open) $code: $out"
  return "$code"
}

# The PDF also in the Download folder (its own subfolder, so  import  never takes it for your copy): for the
# paperclip way.
copy_for_hand() {
  local dir
  for dir in /sdcard/Download "$HOME/storage/downloads"; do
    if [ -d "$dir" ] && mkdir -p "$dir/Aurenflow" 2>/dev/null && cp "$PDF" "$dir/Aurenflow/" 2>/dev/null; then
      HAND="Download -> Aurenflow -> $(basename "$PDF")"
      return 0
    fi
  done
  HAND="the PDF ($(basename "$PDF")) in your Download folder"
}

# After a message went out: the PDF into the same chat. "n" = it did not show up: the next way is tried.
pdf_step() {
  [ -n "$PDF" ] || return 0
  local first order=() m answer
  first="$(cat "$METHOD_FILE" 2>/dev/null)"
  for m in "$first" direct menu hand; do
    case " ${order[*]} " in *" $m "*) ;; *) [ -n "$m" ] && order+=("$m") ;; esac
  done
  for m in "${order[@]}"; do
    case "$m" in
      direct)
        echo "   Now the PDF: WhatsApp Business opens this chat with the PDF ready - press Send, then come back here."
        pdf_direct "$1" || { echo "   (Android did not open it - trying the next way.)"; continue; } ;;
      menu)
        echo "   Now the PDF, through the share menu: choose WhatsApp Business, then this business at the top, then Send."
        pdf_menu || { echo "   (The share menu did not open - trying the next way.)"; continue; } ;;
      hand)
        [ -n "$HAND" ] || copy_for_hand
        echo "   Now the PDF, by hand: in this chat tap the paperclip -> Document -> $HAND -> Send." ;;
      *) continue ;;
    esac
    while true; do
      read -r -p "   [Enter] PDF sent   n = it did not show up (try another way)   s = no PDF this time: " answer || answer=s
      case "$answer" in
        "")  pdfs=$((pdfs + 1)); mkdir -p "$KEEP"; echo "$m" > "$METHOD_FILE"; note "PDF sent ($m) to $1"; return 0 ;;
        n|N) note "PDF did not show up ($m) for $1"; break ;;
        s|S) note "PDF skipped for $1"; return 0 ;;
        *)   echo "   Press Enter (PDF sent), n (it did not show up: another way) or s (no PDF for this one)." ;;
      esac
    done
  done
  echo "   No way worked for this one. Show me the end of $LOG (command: tail -n 30 $LOG)."
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
pdfs=0
with_pdf=1
args=()
for a in "$@"; do
  case "$a" in --no-pdf) with_pdf="" ;; *) args+=("$a") ;; esac
done
set -- "${args[@]}"
case "${1:-}" in
  list) shift; inside whatsapp list "$@"; exit $? ;;
  pdf)
    shift
    digits="$*"; digits="${digits//[!0-9]/}"
    [ "${#digits}" = 10 ] && digits="91$digits"                 # 10 digits: an Indian number
    [ "${#digits}" -ge 11 ] || { echo "usage: whatsapp pdf NUMBER   (for example: whatsapp pdf 93217 07545)"; exit 2; }
    prepare_pdf
    [ -n "$PDF" ] || exit 1
    echo "-> the PDF to +$digits (the chat must exist: a message was sent to this number before)"
    pdf_step "$digits"
    exit 0 ;;
  test)
    shift
    [ -n "${1:-}" ] || { echo "usage: whatsapp test NUMBER   (for example: whatsapp test 98765 43210)"; exit 2; }
    [ -n "$with_pdf" ] && prepare_pdf
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
    [ "$result" = "Sent" ] && pdf_step "$number"
    case "$result" in
      Sent) echo "Test sent: Termux, the Google Sheet and WhatsApp Business work together$([ "$pdfs" = 1 ] && echo ", the PDF too")." ;;
      "Not on WhatsApp") echo "WhatsApp says $number is not on WhatsApp: check the number and try again." ;;
      *) echo "No test sent." ;;
    esac
    exit 0 ;;
  --now) now="--now" ;;
  "")    ;;
  *)     echo "usage: whatsapp [list | test NUMBER | pdf NUMBER] [--now] [--no-pdf]"; exit 2 ;;
esac

save_unsaved
inside whatsapp list $now
code=$?
[ "$code" = 4 ] && exit 0                           # outside office hours (the list said so)
if [ "$code" != 0 ]; then
  echo "The WhatsApp Queue could not be read just now (no internet, or Google did not answer). Try  whatsapp  again in a minute."
  exit 0
fi
[ -n "$with_pdf" ] && prepare_pdf

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
  case "$row" in ''|*[!0-9]*) echo; echo "Nothing more to send now ($sent sent, $pdfs with the PDF). The robot adds new ones every day."; break ;; esac
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
  save "$row" "$key" "$number" "$result"
  [ "$result" = "Sent" ] && { sent=$((sent + 1)); pdf_step "$number"; }
done
save_unsaved
exit 0
