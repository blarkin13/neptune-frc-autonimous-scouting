#!/bin/sh
# Copy this repo's engine and server code into the main Neptune repo layout.
# Usage: scripts/sync-to-neptune.sh /path/to/neptune-frc-scouting [--check]
#   --check  only report differences, change nothing.
# Refuses to overwrite a file someone changed in the main repo since the last sync
# (hashes recorded in .sync-manifest); bring that change in here first.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:?path to neptune-frc-scouting}
mode=${2:-}
exec python3 -I "$here/scripts/sync.py" "$here" "$dest" $mode
