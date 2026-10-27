#!/bin/bash
# Run on the Neptune server as the last step of every helper release or code deploy (AGENTS.md rule 10).
# Keeps the two newest Mac zips and Windows update zips (plus anything a live feed points at),
# the two newest /root rollback backups, and about 100 MB of journal. Never touches database dumps.
# Usage: prune-release-server.sh [--dry-run]
set -euo pipefail
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
D=/var/www/neptune/public_html/Neptune/community/downloads
KEEP=2

remove() { echo "remove $1"; [ $DRY = 1 ] || rm -rf -- "$1"; }

# $1 folder, $2 glob, $3 feed file that must never lose its referenced file
prune_versions() {
  cd "$1" || return 0
  ls $2 2>/dev/null | sort -V | head -n -$KEEP | while read -r f; do
    if [ -f "$3" ] && grep -qF "$f" "$3"; then echo "keep $f (in $(basename "$3"))"; else remove "$1/$f"; fi
  done
}

prune_versions "$D/mac" 'Neptune-Training-Helper-[0-9]*.zip' "$D/mac/appcast.xml"
prune_versions "$D/windows" 'Neptune-Training-Helper-[0-9]*-update.zip' "$D/windows/latest.json"

ls -dt /root/*-backup-20[0-9][0-9]* 2>/dev/null | grep -v '\.sql$' | tail -n +$((KEEP+1)) | while read -r b; do remove "$b"; done

[ $DRY = 1 ] || journalctl --vacuum-size=100M >/dev/null 2>&1 || true
df -h / | tail -1
