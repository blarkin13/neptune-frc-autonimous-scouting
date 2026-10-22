#!/bin/sh
# Opens the robot labeler on this Mac only (127.0.0.1). Close this window to stop it.
cd "$(dirname "$0")"
python3 -u server.py "$@" | while IFS= read -r line; do
  echo "$line"
  case "$line" in *http://127.0.0.1:*) open "$(echo "$line" | grep -o 'http://[^ ]*')";; esac
done
