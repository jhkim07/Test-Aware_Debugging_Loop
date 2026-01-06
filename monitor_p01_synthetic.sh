#!/bin/bash

# P0-1 Phase 2 Synthetic Test Monitor
# Instance: astropy-12907 with max_test_iterations=1

LOG_FILE="logs/p01_phase2_synthetic.log"
OUTPUT_DIR="outputs/p01-phase2-synthetic-20260106"
INSTANCE="astropy__astropy-12907"

echo "=========================================="
echo "P0-1 Phase 2 Synthetic Test Monitor"
echo "Instance: astropy-12907"
echo "Strategy: max_test_iterations=1 (forced)"
echo "=========================================="
echo ""

# Monitor test progress
while true; do
    clear
    echo "=========================================="
    echo "P0-1 Synthetic Test - Live Status"
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""

    # Check if completed
    if [ -f "$OUTPUT_DIR/$INSTANCE/metrics.json" ]; then
        echo "✅ TEST COMPLETED!"
        echo ""
        echo "=========================================="
        echo "📊 Final Results"
        echo "=========================================="
        echo ""

        # Show overall scores
        echo "=== Performance Metrics ==="
        cat "$OUTPUT_DIR/$INSTANCE/metrics.json" | jq '{
            overall: .scores.overall,
            hfs: .scores.hfs,
            tss: .scores.tss,
            brs: .scores.brs
        }'
        echo ""

        # Show P0-1 diagnostic
        echo "=== P0-1 Diagnostic ==="
        cat "$OUTPUT_DIR/$INSTANCE/metrics.json" | jq '.p01_diagnostic'
        echo ""

        # Show iteration counts
        echo "=== Iteration Usage ==="
        cat "$OUTPUT_DIR/$INSTANCE/metrics.json" | jq '{
            test_iterations: .test_iterations_used,
            code_iterations: .code_iterations_used
        }'

        break
    elif [ -d "$OUTPUT_DIR/$INSTANCE" ]; then
        echo "⏳ TEST IN PROGRESS"
        echo ""

        # Count JSONL files to estimate progress
        JSONL_COUNT=$(ls "$OUTPUT_DIR/$INSTANCE"/*.jsonl 2>/dev/null | wc -l)
        echo "📝 JSONL files created: $JSONL_COUNT"
        echo ""

        # Show recent activity
        if [ -f "$LOG_FILE" ]; then
            echo "=== Recent Activity (last 20 lines) ==="
            tail -n 20 "$LOG_FILE" | grep -E "(Processing|Iteration|Test|BRS|P0-1|exhaustion)" || echo "No matching logs..."
        fi
    else
        echo "⏸️  WAITING TO START..."
        echo ""

        # Show initial logs
        if [ -f "$LOG_FILE" ]; then
            echo "=== Initialization Logs ==="
            tail -n 10 "$LOG_FILE"
        fi
    fi

    echo ""
    echo "=========================================="
    echo "Press Ctrl+C to stop monitoring"
    echo "=========================================="

    sleep 10
done

echo ""
echo "=========================================="
echo "Monitor finished"
echo "=========================================="
