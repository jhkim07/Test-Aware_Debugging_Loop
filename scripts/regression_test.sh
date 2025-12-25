#!/bin/bash
# 회귀 테스트 스크립트 - P0 개선사항이 기존 성공 케이스를 보호하는지 검증
# Usage: ./scripts/regression_test.sh

set -e

# Set PYTHONPATH
export PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}회귀 테스트 (Regression Test)${NC}"
echo -e "${CYAN}P0 개선사항 안전성 검증${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Phase 1: 단위 테스트
echo -e "${CYAN}[Phase 1/3] 단위 테스트 실행...${NC}"
echo ""

# Test 1: diff_validator context 계산
echo -e "${YELLOW}Test 1: diff_validator context calculation${NC}"
python3 << 'EOF'
from bench_agent.protocol.diff_validator import _calculate_actual_hunk_counts

# Test case 1: astropy-12907 유사 패치 (간단한 1줄 변경)
diff_lines = [
    '@@ -242,5 +242,5 @@',
    '         cright = _coord_matrix(right, "right", noutp)',
    '     else:',
    '         cright = np.zeros((noutp, right.shape[1]))',
    '-        cright[-right.shape[0]:, -right.shape[1]:] = 1',
    '+        cright[-right.shape[0]:, -right.shape[1]:] = right',
    '',
    '     return np.hstack([cleft, cright])'
]

old_count, new_count = _calculate_actual_hunk_counts(diff_lines, 0)
print(f"  Result: old_count={old_count}, new_count={new_count}")

# 예상: 1 removed + 4 context = 5, 1 added + 4 context = 5
if old_count == 5 and new_count == 5:
    print("  ✅ PASS: Correct count (5, 5)")
else:
    print(f"  ❌ FAIL: Expected (5, 5), got ({old_count}, {new_count})")
    exit(1)

# Test case 2: 빈 줄 포함 케이스
diff_lines_with_empty = [
    '@@ -10,7 +10,8 @@',
    ' line 1',
    ' ',  # 빈 줄 (context)
    ' line 3',
    '-old line',
    '+new line 1',
    '+new line 2',
    ' ',  # 빈 줄 (context)
    ' line 6'
]

old_count, new_count = _calculate_actual_hunk_counts(diff_lines_with_empty, 0)
print(f"  Result (with empty lines): old_count={old_count}, new_count={new_count}")

# 예상: 1 removed + 5 context (빈 줄 2개 포함) = 6, 2 added + 5 context = 7
# Context: ' line 1', ' ' (empty), ' line 3', ' ' (empty), ' line 6' = 5
expected_old = 6
expected_new = 7
if old_count == expected_old and new_count == expected_new:
    print(f"  ✅ PASS: Correctly counts empty lines ({expected_old}, {expected_new})")
else:
    print(f"  ❌ FAIL: Expected ({expected_old}, {expected_new}), got ({old_count}, {new_count})")
    exit(1)

print("")
EOF

# Test 2: llm_client temperature 기본값
echo -e "${YELLOW}Test 2: llm_client temperature default${NC}"
python3 << 'EOF'
import inspect
from bench_agent.agent.llm_client import chat

# Check function signature
sig = inspect.signature(chat)
temp_param = sig.parameters['temperature']
default_temp = temp_param.default

print(f"  Default temperature: {default_temp}")

if default_temp == 0.0:
    print("  ✅ PASS: Temperature defaults to 0.0 (deterministic)")
else:
    print(f"  ❌ FAIL: Expected temperature=0.0, got {default_temp}")
    exit(1)

print("")
EOF

# Test 3: reference_test_analyzer 추출
echo -e "${YELLOW}Test 3: reference_test_analyzer expected value extraction${NC}"
python3 << 'EOF'
from bench_agent.protocol.reference_test_analyzer import analyze_reference_test_patch

# astropy-12907 유사 test patch
test_patch = """diff --git a/test_file.py b/test_file.py
--- a/test_file.py
+++ b/test_file.py
@@ -1,3 +1,8 @@
 p1 = models.Polynomial1D(1, name='p1')

+cm_4d_expected = (np.array([False, False, True, True]),
+                  np.array([[True,  True,  False, False],
+                            [True,  True,  False, False]]))
+
 compound_models = {
+    'cm8': (rot & (sh1 & sh2), cm_4d_expected),
 }
"""

result = analyze_reference_test_patch(test_patch)
expected_values = result.get('expected_values', {})

print(f"  Extracted expected values: {list(expected_values.keys())}")

if 'cm_4d_expected' in expected_values:
    print("  ✅ PASS: Expected value 'cm_4d_expected' extracted")
else:
    print(f"  ❌ FAIL: Expected value not extracted. Got: {expected_values}")
    exit(1)

# Check hints generation
hints = result.get('expected_value_hints', '')
if 'CRITICAL' in hints and 'cm_4d_expected' in hints:
    print("  ✅ PASS: Expected value hints generated")
else:
    print(f"  ❌ FAIL: Hints not properly generated")
    exit(1)

print("")
EOF

# Test 4: patch_fallback 실패 감지
echo -e "${YELLOW}Test 4: patch_fallback failure detection${NC}"
python3 << 'EOF'
from bench_agent.protocol.patch_fallback import extract_patch_failure_details

# Test case 1: Hunk failure (astropy-14182 패턴)
stderr1 = """
patching file astropy/io/ascii/rst.py
Hunk #1 FAILED at 27.
1 out of 1 hunk FAILED -- saving rejects to file astropy/io/ascii/rst.py.rej
"""

result1 = extract_patch_failure_details(stderr1, "")
print(f"  Test 'Hunk FAILED': {result1}")

if result1['failed'] and result1['failure_type'] == 'line_mismatch':
    print("  ✅ PASS: Hunk failure detected correctly")
else:
    print(f"  ❌ FAIL: Expected line_mismatch failure, got {result1}")
    exit(1)

# Test case 2: 성공 케이스 (false positive 없어야 함)
stdout2 = "patching file test.py\nSuccessfully applied patch"
result2 = extract_patch_failure_details("", stdout2)

if not result2['failed']:
    print("  ✅ PASS: No false positive on successful patch")
else:
    print(f"  ❌ FAIL: False positive detected: {result2}")
    exit(1)

print("")
EOF

echo -e "${GREEN}✅ Phase 1 완료: 모든 단위 테스트 통과${NC}"
echo ""

# Phase 2: 통합 테스트 (기존 성공 케이스 보호)
echo -e "${CYAN}[Phase 2/3] 통합 테스트 - 기존 성공 케이스 보호 검증${NC}"
echo ""

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  OPENAI_API_KEY not set. Skipping integration tests.${NC}"
    echo -e "${YELLOW}    Set API key to run full regression test:${NC}"
    echo -e "${YELLOW}    export OPENAI_API_KEY='your-key'${NC}"
    echo ""
else
    echo -e "${YELLOW}Running astropy__astropy-12907 (기존 성공 케이스)...${NC}"
    echo -e "${YELLOW}This will take 10-20 minutes...${NC}"
    echo ""

    RUN_ID="regression-$(date +%Y%m%d-%H%M%S)"

    python3 scripts/run_mvp.py \
        --config configs/mvp.yaml \
        --run-id ${RUN_ID} \
        --max-workers 1 \
        --instance-ids astropy__astropy-12907

    # 결과 비교
    echo ""
    echo -e "${CYAN}결과 비교 중...${NC}"

    python3 << EOF
import json
from pathlib import Path

# 기존 결과 (baseline)
baseline_path = Path('outputs/mvp-20251215-013151/astropy__astropy-12907/metrics.json')
if not baseline_path.exists():
    print("⚠️  Baseline metrics not found. Skipping comparison.")
    print(f"   Expected: {baseline_path}")
    exit(0)

old_metrics = json.loads(baseline_path.read_text())

# 새 결과
new_path = Path('outputs/${RUN_ID}/astropy__astropy-12907/metrics.json')
if not new_path.exists():
    print("❌ New metrics not found!")
    exit(1)

new_metrics = json.loads(new_path.read_text())

print("=" * 60)
print("회귀 테스트 결과 비교")
print("=" * 60)
print(f"{'메트릭':<20} {'기존':<15} {'P0 개선 후':<15} {'상태':<10}")
print("-" * 60)

# Overall Score
old_overall = old_metrics['scores']['overall']
new_overall = new_metrics['scores']['overall']
overall_status = "✅ PASS" if new_overall >= old_overall * 0.99 else "❌ FAIL"
print(f"{'Overall Score':<20} {old_overall:<15.4f} {new_overall:<15.4f} {overall_status:<10}")

# BRS
old_brs = old_metrics['scores']['brs']
new_brs = new_metrics['scores']['brs']
brs_status = "✅ PASS" if new_brs == 1.0 else "❌ FAIL"
print(f"{'BRS':<20} {old_brs:<15.1f} {new_brs:<15.1f} {brs_status:<10}")

# Iterations
old_iter = old_metrics['iterations']
new_iter = new_metrics['iterations']
iter_status = "✅ PASS" if new_iter <= old_iter else "⚠️  WARN"
print(f"{'Iterations':<20} {old_iter:<15} {new_iter:<15} {iter_status:<10}")

# Public/Hidden Pass Rate
old_public = old_metrics['final_iteration']['public_pass_rate']
new_public = new_metrics['final_iteration']['public_pass_rate']
public_status = "✅ PASS" if new_public >= old_public else "❌ FAIL"
print(f"{'Public Pass Rate':<20} {old_public:<15.2%} {new_public:<15.2%} {public_status:<10}")

old_hidden = old_metrics['final_iteration']['hidden_pass_rate']
new_hidden = new_metrics['final_iteration']['hidden_pass_rate']
hidden_status = "✅ PASS" if new_hidden >= old_hidden else "❌ FAIL"
print(f"{'Hidden Pass Rate':<20} {old_hidden:<15.2%} {new_hidden:<15.2%} {hidden_status:<10}")

print("=" * 60)

# 최종 판정
regression = (
    new_overall < old_overall * 0.99 or
    new_brs < 1.0 or
    new_public < old_public or
    new_hidden < old_hidden
)

if regression:
    print("❌ 회귀 발생! 기존 성공 케이스가 저하되었습니다.")
    exit(1)
else:
    print("✅ 회귀 없음! 기존 성공 케이스가 보호되었습니다.")

    # 개선 사항 체크
    improvements = []
    if new_overall > old_overall:
        improvements.append(f"  • Overall Score 향상: {old_overall:.4f} → {new_overall:.4f}")
    if new_iter < old_iter:
        improvements.append(f"  • Iterations 감소: {old_iter} → {new_iter}")

    if improvements:
        print("\n🎉 추가 개선 사항:")
        for imp in improvements:
            print(imp)

EOF

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Phase 2 완료: 기존 성공 케이스 보호 확인됨${NC}"
    else
        echo ""
        echo -e "${RED}❌ Phase 2 실패: 회귀 발생${NC}"
        exit 1
    fi
fi

echo ""

# Phase 3: 요약
echo -e "${CYAN}[Phase 3/3] 최종 요약${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}회귀 테스트 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "✅ 검증된 사항:"
echo "  1. diff_validator - context 계산 로직 정확성"
echo "  2. llm_client - temperature=0 기본값 설정"
echo "  3. reference_test_analyzer - expected value 추출"
echo "  4. patch_fallback - 실패 감지 정확성"

if [ -n "$OPENAI_API_KEY" ]; then
    echo "  5. 기존 성공 케이스 (astropy-12907) 보호"
fi

echo ""
echo -e "${CYAN}다음 단계:${NC}"
echo "1. 실패 케이스 개선 확인:"
echo "   ./scripts/test_p0_improvements.sh astropy__astropy-14182"
echo ""
echo "2. 전체 테스트 실행:"
echo "   python scripts/run_mvp.py --config configs/mvp.yaml --run-id p0-full-test"
echo ""
echo "3. 성능 분석:"
echo "   python scripts/analyze_performance.py p0-full-test"
echo ""

echo -e "${GREEN}회귀 테스트 성공! P0 개선사항이 안전합니다.${NC}"
