#!/bin/sh
# Open the room on macOS or Linux.
cd "$(dirname "$0")" && exec python3 server.py "$@"
