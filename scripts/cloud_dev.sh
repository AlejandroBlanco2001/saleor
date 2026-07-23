#!/bin/sh
# Thin wrapper -- see scripts/cloud_dev.py for the actual logic and full
# usage docs. Requires python3.
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
exec python3 "$SCRIPT_DIR/cloud_dev.py" "$@"
