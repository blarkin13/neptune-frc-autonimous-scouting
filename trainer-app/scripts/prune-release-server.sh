#!/bin/sh
# Reviewed implementation shared with the Release Center cleanup preview.
# Install release_prune.py to /opt/neptune-release-center/bin/ before this wrapper.
# Keeps current feed targets, two versions per platform and two rollback copies;
# database dumps are preserved. --dry-run previews, --json exports the inventory.
exec /usr/bin/python3 /opt/neptune-release-center/bin/release_prune.py "$@"
