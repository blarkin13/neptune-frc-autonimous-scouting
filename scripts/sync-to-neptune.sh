#!/bin/sh
# Copy this repo's engine and server code into the main Neptune repo layout.
# Usage: scripts/sync-to-neptune.sh /path/to/neptune-frc-scouting [--check]
#   --check  only report differences, change nothing.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:?path to neptune-frc-scouting}
mode=${2:-}
opts="-a --exclude __pycache__ --exclude .DS_Store"
[ "$mode" = "--check" ] && opts="$opts -n -i --checksum"

# One engine, two install locations: the Mac trainer and the server worker.
rsync $opts --exclude server_run.py --exclude install-server.sh --exclude SERVER_FILES.txt "$here/engine/" "$dest/helper/"
# The server worker ships only the files listed in engine/SERVER_FILES.txt.
rsync $opts --files-from="$here/engine/SERVER_FILES.txt" "$here/engine/" "$dest/neptune_secure/community-learning/"
rsync $opts --exclude community-learning "$here/server/neptune_secure/" "$dest/neptune_secure/"
rsync $opts "$here/server/public_html/" "$dest/public_html/"
rsync $opts "$here/server/sql/" "$dest/sql/"
rsync $opts "$here/tests/server/" "$dest/tests/community-analysis/"
rsync $opts "$here/docs/" "$dest/docs/community-analysis/"
