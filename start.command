#!/bin/bash
# Double-click this file to start the ReelStreak server.
# First time: macOS may block it — right-click > Open, then confirm once.

cd "$(dirname "$0")"

echo "Starting ReelStreak server..."
echo "Leave this window open while you use the app."
echo ""

python3 -m uvicorn app.main:app --reload

# Keep the window open if the server exits or crashes, so you can read the error
echo ""
echo "Server stopped. Press any key to close this window."
read -n 1
