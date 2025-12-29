#!/bin/bash
# P0.9.1 Verification Test Monitor

LOG_FILE="/tmp/p091_verification_test.log"

while true; do
    clear
    echo "=========================================="
    echo "P0.9.1 Phase 1 Verification Test Monitor"
    echo "=========================================="
    echo ""
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Check if process is running
    if ps aux | grep -q "[r]un_mvp.py.*p091_regression_test"; then
        echo "Status: ✓ RUNNING"
    else
        echo "Status: ✗ NOT RUNNING (completed or failed)"
    fi
    echo ""

    # Show current instance
    echo "Current Instance:"
    grep -E "^─+ Instance:" "$LOG_FILE" | tail -1
    echo ""

    # Count iterations
    echo "Progress Summary:"
    echo "  Iterations completed: $(grep -c "Iteration [0-9]" "$LOG_FILE")"
    echo "  Policy violations detected: $(grep -c "Policy violation" "$LOG_FILE")"
    echo "  Patch apply failures: $(grep -c "Patch apply error" "$LOG_FILE")"
    echo ""

    # Show recent activity
    echo "Recent Activity (last 15 lines):"
    tail -15 "$LOG_FILE" | grep -v "^$"
    echo ""
    echo "=========================================="
    echo "Press Ctrl+C to stop monitoring"
    echo "Log file: $LOG_FILE"

    sleep 10
done
