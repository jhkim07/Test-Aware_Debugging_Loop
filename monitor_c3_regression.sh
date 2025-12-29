#!/bin/bash
# Monitor Component 3 Regression Test Progress

echo "=== Component 3 Regression Test Monitor ==="
echo "Started: $(date)"
echo ""

while true; do
    clear
    echo "=== Component 3 Regression Test Progress ==="
    echo "Time: $(date)"
    echo ""

    # Show current output
    if [ -f /tmp/claude/-home-jin-prj-ws-agenticAI-Test-Aware_Debugging_Loop/tasks/becb7c1.output ]; then
        echo "=== Last 30 lines ==="
        tail -30 /tmp/claude/-home-jin-prj-ws-agenticAI-Test-Aware_Debugging_Loop/tasks/becb7c1.output
        echo ""
    fi

    # Count completed instances
    COMPLETED=$(grep -c "Instance.*complete" /tmp/claude/-home-jin-prj-ws-agenticAI-Test-Aware_Debugging_Loop/tasks/becb7c1.output 2>/dev/null || echo "0")
    echo "=== Status ==="
    echo "Instances completed: $COMPLETED / 4"

    # Check for errors
    MALFORMED=$(grep -c "Malformed patch" /tmp/claude/-home-jin-prj-ws-agenticAI-Test-Aware_Debugging_Loop/tasks/becb7c1.output 2>/dev/null || echo "0")
    EDITS=$(grep -c "Edit script applied successfully" /tmp/claude/-home-jin-prj-ws-agenticAI-Test-Aware_Debugging_Loop/tasks/becb7c1.output 2>/dev/null || echo "0")

    echo "Edit scripts applied: $EDITS"
    echo "Malformed patches: $MALFORMED"
    echo ""
    echo "Press Ctrl+C to exit monitoring"

    sleep 10
done
