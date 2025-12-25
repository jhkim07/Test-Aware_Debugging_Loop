#!/bin/bash
# P0 Improvements 테스트 스크립트
# 사용법: ./scripts/test_p0_improvements.sh [instance_id]

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}P0 Improvements Test Suite${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}ERROR: OPENAI_API_KEY is not set${NC}"
    echo "Please run: export OPENAI_API_KEY='your-key-here'"
    exit 1
fi

# Get instance ID from argument or use default
INSTANCE_ID=${1:-"sympy__sympy-20590"}
RUN_ID="p0-test-$(date +%Y%m%d-%H%M%S)"

echo -e "${GREEN}Testing Instance: ${INSTANCE_ID}${NC}"
echo -e "${GREEN}Run ID: ${RUN_ID}${NC}"
echo ""

# Test 1: Quick validation - check if modified files are valid Python
echo -e "${CYAN}[Test 1/4] Validating Python syntax of modified files...${NC}"
python3 -m py_compile bench_agent/protocol/diff_validator.py
python3 -m py_compile bench_agent/protocol/patch_fallback.py
python3 -m py_compile bench_agent/runner/report_parser.py
python3 -m py_compile bench_agent/agent/llm_client.py
python3 -m py_compile bench_agent/protocol/reference_test_analyzer.py
python3 -m py_compile bench_agent/agent/test_author.py
echo -e "${GREEN}✅ All Python files are valid${NC}"
echo ""

# Test 2: Check if LLM cache directory is created
echo -e "${CYAN}[Test 2/4] Checking LLM cache setup...${NC}"
python3 -c "from bench_agent.agent.llm_client import CACHE_DIR; print(f'Cache dir: {CACHE_DIR}'); assert CACHE_DIR.exists()"
echo -e "${GREEN}✅ LLM cache directory exists${NC}"
echo ""

# Test 3: Test patch_fallback module import
echo -e "${CYAN}[Test 3/4] Testing patch_fallback module...${NC}"
python3 -c "
from bench_agent.protocol.patch_fallback import extract_patch_failure_details
result = extract_patch_failure_details('Hunk #1 FAILED at 27', '')
assert result['failed'] == True
assert result['failure_type'] == 'line_mismatch'
print('✅ Patch failure detection works')
"
echo -e "${GREEN}✅ Patch fallback module working${NC}"
echo ""

# Test 4: Run actual SWE-bench instance
echo -e "${CYAN}[Test 4/4] Running SWE-bench instance: ${INSTANCE_ID}${NC}"
echo -e "${YELLOW}This will take 10-30 minutes depending on the instance...${NC}"
echo ""

python3 scripts/run_mvp.py \
  --config configs/mvp.yaml \
  --run-id ${RUN_ID} \
  --max-workers 1 \
  --instance-ids ${INSTANCE_ID}

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Test Complete!${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Check results
OUTPUT_DIR="outputs/${RUN_ID}/${INSTANCE_ID}"
if [ -d "$OUTPUT_DIR" ]; then
    echo -e "${GREEN}✅ Output directory created: ${OUTPUT_DIR}${NC}"

    # Check for metrics
    if [ -f "${OUTPUT_DIR}/metrics.json" ]; then
        echo -e "${GREEN}✅ Metrics file created${NC}"
        echo ""
        echo -e "${CYAN}Metrics Summary:${NC}"
        python3 -c "
import json
with open('${OUTPUT_DIR}/metrics.json') as f:
    metrics = json.load(f)
    print(f\"  Overall Score: {metrics.get('overall_score', 'N/A')}%\")
    print(f\"  Hidden Pass Rate: {metrics.get('hidden_pass_rate', 'N/A')}%\")
    print(f\"  BRS: {metrics.get('brs', 'N/A')}\")
    print(f\"  Iterations: {metrics.get('iterations', 'N/A')}\")
"
    fi

    # Check for patch KPI
    PATCH_KPI="${OUTPUT_DIR}/${INSTANCE_ID}_patch_kpi.json"
    if [ -f "$PATCH_KPI" ]; then
        echo -e "${GREEN}✅ Patch KPI tracked${NC}"
        echo ""
        echo -e "${CYAN}Patch Apply KPI:${NC}"
        python3 -c "
import json
with open('${PATCH_KPI}') as f:
    kpi = json.load(f)
    print(f\"  Success Rate: {kpi.get('patch_apply_success_rate', 'N/A')*100:.1f}%\")
    print(f\"  Successful: {kpi.get('successful_iterations', 'N/A')}/{kpi.get('total_iterations', 'N/A')}\")
    if kpi.get('failure_breakdown'):
        print(f\"  Failures: {kpi.get('failure_breakdown')}\")
"
    fi

    # Check LLM cache usage
    CACHE_COUNT=$(ls -1 .llm_cache/ 2>/dev/null | wc -l || echo 0)
    if [ "$CACHE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✅ LLM cache used: ${CACHE_COUNT} cached responses${NC}"
    fi
else
    echo -e "${RED}❌ Output directory not found${NC}"
fi

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Next Steps:${NC}"
echo -e "${CYAN}========================================${NC}"
echo "1. Check detailed logs: tail -f logs/${RUN_ID}.log"
echo "2. View full report: cat outputs/${RUN_ID}/${INSTANCE_ID}/run.jsonl"
echo "3. Analyze performance: python scripts/analyze_performance.py ${RUN_ID}"
echo ""
echo -e "${GREEN}Test script completed successfully!${NC}"
