#!/bin/bash
# Component 3 Full Integration and Regression Test
# Tests Edit Script Mode on all instances

set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="p091-component3-full-${TIMESTAMP}"

echo "================================================================================"
echo "COMPONENT 3 FULL TEST"
echo "================================================================================"
echo ""
echo "Run ID: ${RUN_ID}"
echo "Timestamp: ${TIMESTAMP}"
echo "Config: configs/p091_component3_regression.yaml"
echo ""
echo "Test Plan:"
echo "  1. Run all 4 instances with Edit Script Mode (USE_EDIT_SCRIPT=1)"
echo "  2. Compare metrics against Phase 0.9.1 baseline"
echo "  3. Verify zero malformed patch errors"
echo "  4. Analyze iteration behavior"
echo ""
echo "Expected Duration: ~8 hours (2 hours per instance)"
echo ""
echo "================================================================================"
echo ""

# Check if running in correct conda environment
if ! conda env list | grep -q "testing.*\*"; then
    echo "WARNING: Not in 'testing' conda environment"
    echo "Please activate: conda activate testing"
    exit 1
fi

# Set environment variables
export USE_EDIT_SCRIPT=1
export PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH

echo "Environment:"
echo "  USE_EDIT_SCRIPT=${USE_EDIT_SCRIPT}"
echo "  PYTHONPATH=${PYTHONPATH}"
echo ""

# Create logs directory
LOGS_DIR="logs/component3_full_test_${TIMESTAMP}"
mkdir -p "${LOGS_DIR}"

echo "Logs will be saved to: ${LOGS_DIR}"
echo ""

# Run test
echo "Starting test at: $(date)"
echo ""

python scripts/run_mvp.py \
  --config configs/p091_component3_regression.yaml \
  --run-id "${RUN_ID}" \
  2>&1 | tee "${LOGS_DIR}/run.log"

EXIT_CODE=$?

echo ""
echo "Test completed at: $(date)"
echo "Exit code: ${EXIT_CODE}"
echo ""

# Generate summary
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "================================================================================"
    echo "TEST COMPLETED SUCCESSFULLY"
    echo "================================================================================"
    echo ""
    echo "Results saved to: outputs/${RUN_ID}/"
    echo "Logs saved to: ${LOGS_DIR}/"
    echo ""
    echo "Next steps:"
    echo "  1. Review results: ls outputs/${RUN_ID}/*/"
    echo "  2. Check for malformed patches: grep -r 'Malformed patch' outputs/${RUN_ID}/"
    echo "  3. Analyze metrics: python scripts/analyze_results.py outputs/${RUN_ID}/"
    echo ""
else
    echo "================================================================================"
    echo "TEST FAILED"
    echo "================================================================================"
    echo ""
    echo "Exit code: ${EXIT_CODE}"
    echo "Check logs: ${LOGS_DIR}/run.log"
    echo ""
fi

exit ${EXIT_CODE}
