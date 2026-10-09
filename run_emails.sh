#!/usr/bin/env bash
# Mac, Linux and Android (Termux + Ubuntu): in a terminal type  bash run_emails.sh   (docs/LOCAL.md)
exec bash "$(dirname "$0")/scripts/run.sh" emails "$@"
