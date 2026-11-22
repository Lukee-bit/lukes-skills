#!/usr/bin/env bash
# Installs every Luke's skills tool on the harnesses found on this machine.
# Pass other arguments to change that, for example: ./Install.command ask --harness cursor
cd "$(dirname "$0")" || exit 1
[ $# -eq 0 ] && set -- all
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    "$py" install.py "$@"
    exit $?
  fi
done
echo "Python 3.8 or newer was not found. Install it from https://www.python.org/downloads/ and run this again."
exit 1
