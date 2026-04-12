#!/bin/bash
# FyersGap — start the gap strategy in the background
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"

if [ -f .fyersgap.pid ]; then
    PID=$(cat .fyersgap.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "FyersGap already running (PID $PID). Stop it first with ./stop_gap.sh"
        exit 1
    fi
fi

nohup python main.py run >> "$LOG_DIR/startup.log" 2>&1 &
echo $! > .fyersgap.pid
echo "FyersGap started (PID $!). Logs: $LOG_DIR/gap_strategy.log"
