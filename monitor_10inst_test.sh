#!/bin/bash
# Monitor 10-instance test progress

LOG_FILE=$(ls -t logs/nohup/p091-c3-10inst-*.log 2>/dev/null | head -1)

if [ -z "$LOG_FILE" ]; then
    echo "❌ Log file not found"
    exit 1
fi

echo "=== Component 3 - 10 Instance Test Monitor ==="
echo "Log: $LOG_FILE"
echo "Time: $(date)"
echo ""

# Progress
INSTANCES=$(grep -c "Instance:" "$LOG_FILE" || echo "0")
echo "📊 Progress: $INSTANCES/9 instances started"

# Core metrics
DIFF_VAL=$(grep -c "diff_validator" "$LOG_FILE" || echo "0")
MALFORMED=$(grep -c "Type: malformed" "$LOG_FILE" || echo "0")
LINE_MISMATCH=$(grep -c "Type: line_mismatch" "$LOG_FILE" || echo "0")
EDITS=$(grep -c "Edit script applied successfully" "$LOG_FILE" || echo "0")

echo ""
echo "🎯 Core Metrics:"
echo "  diff_validator calls: $DIFF_VAL (target: 0)"
echo "  Malformed: $MALFORMED"
echo "  Line mismatch: $LINE_MISMATCH"
echo "  Edit scripts: $EDITS"

# Last 20 lines
echo ""
echo "=== Latest Activity ==="
tail -20 "$LOG_FILE"

echo ""
echo "=== To continue monitoring ==="
echo "watch -n 30 ./monitor_10inst_test.sh"
