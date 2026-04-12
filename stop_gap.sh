#!/bin/bash
# FyersGap — graceful stop (writes stop flag, waits for the strategy to exit)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python main.py stop

if [ -f .fyersgap.pid ]; then
    PID=$(cat .fyersgap.pid)
    echo "Waiting for process $PID to exit…"
    TIMEOUT=60
    ELAPSED=0
    while kill -0 "$PID" 2>/dev/null && [ $ELAPSED -lt $TIMEOUT ]; do
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done
    if kill -0 "$PID" 2>/dev/null; then
        echo "Process did not exit after ${TIMEOUT}s — sending SIGTERM"
        kill "$PID" 2>/dev/null || true
    fi
    rm -f .fyersgap.pid
fi
echo "FyersGap stopped."
