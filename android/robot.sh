#!/usr/bin/env bash
# The robot's switch in Termux (the command  robot , made by android/setup.sh):
#   robot on              start it: from now on it finds leads every day and sends the e-mails in office hours
#   robot off             stop it (the job it is on finishes its step and saves first; stays off until  robot on )
#   robot status          what it does and did, and the leads found so far
#   robot log [LINES]     the end of today's log
#   robot run JOB         one job now: leads, hunt, emails, update or backup
# It keeps itself running: after a restart of the tablet (Termux:Boot app) and, every 15 minutes, if Android closed it
# (Termux:API app). Plant Parlour is never touched: its own Ubuntu, folder (~/.plant-parlour), job number (4711) and
# start-up script. Termux's keep-awake lock is shared with it, so it is taken here but never released.
NAME=review-leads                                   # the Ubuntu inside Termux (android/setup.sh)
DIR=/root/review-leads                              # the robot's folder in it
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
HOST_DIR="$(dirname "$(dirname "$SELF")")"          # the same folder, seen from Termux
HOME_DIR="$HOME/.review-leads"
PIDFILE="$HOME_DIR/robot.pid"                       # the one supervisor (robot.sh supervise) that keeps the robot going
STOPFLAG="$HOME_DIR/stopped"                        # robot off: stays off, also after a restart of the tablet
LOGF="$HOME_DIR/service.log"
STATUS="$HOST_DIR/data/robot-status.json"           # the robot's own record (scripts/robot.py): its heartbeat
JOB_ID=7711                                         # Android job number of the 15-minute check (Plant Parlour: 4711)
WAIT=${ROBOT_WAIT_SECONDS:-60}                      # seconds between looks while an earlier robot still runs

inside() { proot-distro login "$NAME" -- bash "$DIR/android/inside.sh" "$@"; }
stamp() { date '+%F %T'; }

# That number is a live supervisor of this robot (not a number left over from before a restart of the tablet).
supervisor() {
  [ -n "$1" ] && kill -0 "$1" 2>/dev/null || return 1
  [ -r "/proc/$1/cmdline" ] || return 0
  tr '\0' ' ' < "/proc/$1/cmdline" | grep -q 'robot\.sh supervise'
}
running() { supervisor "$(cat "$PIDFILE" 2>/dev/null)"; }

# The robot itself (inside Ubuntu) reported in during the last 3 minutes.
robot_alive() {
  local beat
  beat="$(grep -o '"heartbeat": *[0-9]*' "$STATUS" 2>/dev/null | head -n 1 | grep -o '[0-9]*$')"
  [ -n "$beat" ] && [ "$beat" -gt $(( $(date +%s) - 180 )) ]
}

# One supervisor at a time. Two can start at the same moment (robot on and the 15-minute check): both write their
# number, the last one keeps it and the other leaves.
mine() {
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null)"
  [ "$pid" = "$$" ] && return 0
  supervisor "$pid" && return 1
  echo $$ > "$PIDFILE"
  sleep 1
  [ "$(cat "$PIDFILE" 2>/dev/null)" = "$$" ]
}

supervise() {
  mkdir -p "$HOME_DIR"
  mine || exit 0                                    # another supervisor keeps it going already
  command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
  child=""
  trap 'touch "$STOPFLAG"; touch "$HOST_DIR/data/robot.stop" 2>/dev/null' TERM INT
  fails=0
  while [ ! -f "$STOPFLAG" ] && mine; do
    if robot_alive; then                            # a robot started earlier still runs: this one takes over after it
      sleep "$WAIT"
      continue
    fi
    started=$(date +%s)
    echo "$(stamp) robot starting" >> "$LOGF"
    inside robot serve >> "$LOGF" 2>&1 &
    child=$!
    wait "$child"
    code=$?
    while kill -0 "$child" 2>/dev/null; do          # a signal ended the wait early: let the robot finish its step
      wait "$child"
      code=$?
    done
    echo "$(stamp) robot stopped (exit code $code)" >> "$LOGF"
    [ -f "$STOPFLAG" ] && break
    if [ "$code" = 75 ]; then fails=0; sleep "$WAIT"; continue; fi  # another copy of the robot runs: look again later
    if [ "$code" = 10 ]; then fails=0; sleep 2; continue; fi        # updated itself: start the new version now
    if [ $(( $(date +%s) - started )) -lt 120 ]; then fails=$((fails + 1)); else fails=0; fi
    if [ "$fails" -ge 5 ]; then
      echo "$(stamp) it keeps stopping - next try in 10 minutes (robot log shows why)" >> "$LOGF"
      sleep 600
    else
      sleep 20
    fi
  done
  if [ "$(cat "$PIDFILE" 2>/dev/null)" = "$$" ]; then
    rm -f "$PIDFILE"
    echo "$(stamp) robot off" >> "$LOGF"
  fi
}

start() {
  mkdir -p "$HOME_DIR"
  rm -f "$STOPFLAG" "$HOST_DIR/data/robot.stop"
  if running; then
    echo "The robot is already on."
    return 0
  fi
  if command -v setsid >/dev/null 2>&1; then
    setsid nohup bash "$SELF" supervise > /dev/null 2>&1 < /dev/null &
  else
    nohup bash "$SELF" supervise > /dev/null 2>&1 < /dev/null &
  fi
  for _ in $(seq 1 15); do running && break; sleep 1; done
  if running; then echo "The robot is on. It works by itself from now on (robot status shows what it does)."
  else echo "Could not start the robot - see $LOGF"; return 1; fi
}

autostart() {
  # After a restart of the tablet (Termux:Boot) and every 15 minutes (Termux:API): start it again if Android closed it.
  mkdir -p "$HOME/.termux/boot" "$HOME_DIR"
  printf '#!%s/bin/bash\ntermux-wake-lock\nexec bash "%s" watchdog\n' "$PREFIX" "$SELF" > "$HOME/.termux/boot/review-leads"
  chmod 700 "$HOME/.termux/boot/review-leads"
  printf '#!%s/bin/bash\nexec bash "%s" watchdog\n' "$PREFIX" "$SELF" > "$HOME_DIR/watchdog-job.sh"
  chmod 700 "$HOME_DIR/watchdog-job.sh"
  if command -v termux-job-scheduler >/dev/null 2>&1 &&
     timeout 30 termux-job-scheduler --job-id "$JOB_ID" --period-ms 900000 --persisted true --battery-not-low false \
       --script "$HOME_DIR/watchdog-job.sh" >/dev/null 2>&1; then
    echo "Restarts by itself: after a tablet restart and, if Android closes it, within 15 minutes."
  else
    echo "Restarts by itself after a tablet restart (with the Termux:Boot app). The 15-minute check needs the"
    echo "Termux:API app and package (pkg install termux-api) - not set now."
  fi
}

stop() {
  mkdir -p "$HOME_DIR"
  touch "$STOPFLAG" "$HOST_DIR/data/robot.stop"
  if command -v termux-job-scheduler >/dev/null 2>&1; then
    timeout 30 termux-job-scheduler --cancel --job-id "$JOB_ID" >/dev/null 2>&1 || true
  fi
  if running || robot_alive; then
    echo "Stopping - the job it is on saves its work first (up to 3 minutes)..."
    for _ in $(seq 1 100); do running || robot_alive || break; sleep 2; done
    if running; then
      kill -TERM "$(cat "$PIDFILE")" 2>/dev/null
      sleep 3
    fi
  fi
  running || rm -f "$PIDFILE"
  echo "The robot is off. It stays off (also after a restart of the tablet) until:  robot on"
}

switch_line() {
  if [ -f "$STOPFLAG" ]; then
    if robot_alive; then echo "Switch: OFF - the robot finishes the step it is on, then stops"
    else echo "Switch: OFF (robot on starts it)"; fi
  elif robot_alive; then echo "Switch: ON"
  elif running; then echo "Switch: ON - the robot is starting (if this stays, robot log shows why)"
  else echo "Switch: not running (robot on starts it)"; fi
}

case "${1:-status}" in
  on|start)   autostart; start ;;
  off|stop)   stop ;;
  status)     switch_line; inside robot status ;;
  log|logs)   shift; inside robot log "$@" ;;
  run)        shift; inside robot run "$@" ;;
  supervise)  supervise ;;
  watchdog)   [ -f "$STOPFLAG" ] || running || { echo "$(stamp) watchdog: not running - starting" >> "$LOGF"; start; } ;;
  *)          echo "usage: robot on|off|status|log [LINES]|run JOB"; exit 2 ;;
esac
