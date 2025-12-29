#!/bin/bash
# Component 3 Regression Test - Independent Execution
# This script runs independently even if the terminal is closed

cd /home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop

# Activate conda environment and run test
source ~/anaconda3/bin/activate testing

# Set environment variables
export USE_EDIT_SCRIPT=1
export PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH

# Create log directory
mkdir -p logs/nohup

# Run test with nohup (continues even if terminal closes)
RUN_ID="p091-c3-regression-$(date +%Y%m%d-%H%M%S)"
LOG_FILE="logs/nohup/${RUN_ID}.log"

echo "Starting Component 3 Regression Test"
echo "Run ID: $RUN_ID"
echo "Log file: $LOG_FILE"
echo "Start time: $(date)"
echo ""

nohup python scripts/run_mvp.py \
    --config configs/p091_component3_regression.yaml \
    --run-id "$RUN_ID" \
    > "$LOG_FILE" 2>&1 &

PID=$!
echo "Process ID: $PID"
echo "$PID" > logs/nohup/c3_regression.pid
echo ""
echo "✅ Test started successfully!"
echo ""
echo "Monitor with:"
echo "  tail -f $LOG_FILE"
echo ""
echo "Check status:"
echo "  ps -p $PID"
echo ""
echo "Kill if needed:"
echo "  kill $PID"
