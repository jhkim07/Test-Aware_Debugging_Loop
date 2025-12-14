#!/bin/bash
# 실험 실행 및 완료 후 최종 리포트 생성 스크립트

set -e

# 설정 확인
CONFIG="${1:-configs/mvp.yaml}"
RUN_ID="${2:-mvp-$(date +%Y%m%d-%H%M%S)}"
MAX_WORKERS="${3:-1}"

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

echo "=========================================="
echo "실험 실행 및 리포트 생성 스크립트"
echo "=========================================="
echo "Config: $CONFIG"
echo "Run ID: $RUN_ID"
echo "Max Workers: $MAX_WORKERS"
echo ""

# 1. 실험 실행
echo "[1/3] 실험 실행 중..."
bash scripts/run_mvp_nohup.sh "$CONFIG" "$RUN_ID" "$MAX_WORKERS"

# PID 파일 읽기
PID_FILE="logs/${RUN_ID}.pid"
if [ ! -f "$PID_FILE" ]; then
    echo "오류: PID 파일을 찾을 수 없습니다: $PID_FILE"
    exit 1
fi

PID=$(cat "$PID_FILE")
LOG_FILE="logs/${RUN_ID}.log"

echo "실험 PID: $PID"
echo "로그 파일: $LOG_FILE"
echo ""

# 2. 실험 완료 대기
echo "[2/3] 실험 완료 대기 중..."
echo "실험 진행 상황을 확인하려면: tail -f $LOG_FILE"
echo ""

# 프로세스가 종료될 때까지 대기
while ps -p $PID > /dev/null 2>&1; do
    sleep 30  # 30초마다 확인
    # 진행 상황 표시
    if [ -f "$LOG_FILE" ]; then
        # 마지막 몇 줄 출력 (최근 진행 상황)
        echo "[$(date +%H:%M:%S)] 실험 진행 중... (마지막 로그:)"
        tail -n 3 "$LOG_FILE" | sed 's/^/  /'
        echo ""
    fi
done

echo "실험이 완료되었습니다!"
echo ""

# 3. 성능 분석 및 리포트 생성
echo "[3/3] 성능 분석 및 리포트 생성 중..."

# PYTHONPATH 설정
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 성능 분석 실행
python3 scripts/analyze_performance.py --run-id "$RUN_ID" || {
    echo "경고: 성능 분석 스크립트 실행 실패. 수동으로 실행해주세요:"
    echo "  python3 scripts/analyze_performance.py --run-id $RUN_ID"
}

# 최종 리포트 생성
echo ""
echo "최종 리포트 생성 중..."

# 리포트 파일 경로
REPORT_FILE="FINAL_REPORT_${RUN_ID}.md"

cat > "$REPORT_FILE" << EOF
# 최종 실험 리포트

**실행 ID**: ${RUN_ID}  
**실행 시작**: $(date -r "$LOG_FILE" 2>/dev/null || echo "N/A")  
**실행 완료**: $(date)  
**설정 파일**: ${CONFIG}

---

## 실행 요약

EOF

# 성능 리포트가 있으면 포함
if [ -f "performance_report.json" ]; then
    echo "성능 리포트를 포함합니다..."
    python3 << PYTHON_EOF
import json
import sys

try:
    with open('performance_report.json', 'r') as f:
        data = json.load(f)
    
    print("\n## 성능 지표\n")
    print(f"- **총 인스턴스**: {data.get('total_instances', 'N/A')}")
    print(f"- **완료된 인스턴스**: {data.get('completed_instances', 'N/A')}")
    print(f"- **성공한 인스턴스**: {data.get('successful_instances', 'N/A')}")
    print(f"- **성공률**: {data.get('success_rate', 0) * 100:.1f}%")
    
    if 'average_metrics' in data:
        metrics = data['average_metrics']
        print("\n### 평균 지표\n")
        print(f"- **평균 Public Pass Rate**: {metrics.get('public_pass_rate', 0) * 100:.1f}%")
        print(f"- **평균 Hidden Pass Rate**: {metrics.get('hidden_pass_rate', 0) * 100:.1f}%")
        print(f"- **평균 Overfit Gap**: {metrics.get('overfit_gap', 0):.3f}")
        print(f"- **평균 BRS Score**: {metrics.get('brs_score', 0):.3f}")
    
    if 'instance_results' in data:
        print("\n### 인스턴스별 결과\n")
        for inst in data['instance_results']:
            status = "✅ 성공" if inst.get('success', False) else "❌ 실패"
            print(f"- **{inst.get('instance_id', 'N/A')}**: {status}")
            if inst.get('public_pass_rate'):
                print(f"  - Public Pass Rate: {inst['public_pass_rate'] * 100:.1f}%")
except Exception as e:
    print(f"\n성능 리포트 파싱 오류: {e}", file=sys.stderr)
PYTHON_EOF
fi >> "$REPORT_FILE"

# 로그 요약 추가
cat >> "$REPORT_FILE" << EOF

---

## 로그 요약

전체 로그는 \`$LOG_FILE\` 파일을 참조하세요.

### 마지막 50줄

\`\`\`
EOF

tail -n 50 "$LOG_FILE" >> "$REPORT_FILE" 2>/dev/null || echo "(로그 파일을 읽을 수 없습니다)" >> "$REPORT_FILE"

cat >> "$REPORT_FILE" << EOF
\`\`\`

---

## 다음 단계

1. 상세 분석: \`python3 scripts/analyze_performance.py --run-id $RUN_ID\`
2. 로그 확인: \`tail -f $LOG_FILE\`
3. 결과 디렉토리: \`outputs/$RUN_ID/\`

---

*이 리포트는 자동으로 생성되었습니다.*
EOF

echo ""
echo "=========================================="
echo "실험 및 리포트 생성 완료!"
echo "=========================================="
echo "최종 리포트: $REPORT_FILE"
echo "로그 파일: $LOG_FILE"
echo "결과 디렉토리: outputs/$RUN_ID/"
echo ""
echo "리포트 확인: cat $REPORT_FILE"
echo ""


