#!/bin/bash
# 실험 상태 확인 스크립트

cd "$(dirname "$0")/.."

echo "═══════════════════════════════════════════════════════════"
echo "  실험 상태 확인"
echo "═══════════════════════════════════════════════════════════"
echo ""

# .experiment_running 파일 확인
if [ -f .experiment_running ]; then
    echo "📌 실행 중인 실험 정보 파일 발견:"
    grep "^RUN_ID=" .experiment_running | sed 's/^/   /'
    echo ""
fi

# PID 파일 확인
if [ -f logs/mvp-005.pid ]; then
    PID=$(cat logs/mvp-005.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ 실험 실행 중"
        echo "   Run ID: mvp-005"
        echo "   PID: $PID"
        echo "   실행 시간: $(ps -p $PID -o etime= | tr -d ' ')"
        echo ""
        echo "📊 최근 로그 (마지막 5줄):"
        tail -5 logs/mvp-005.log 2>/dev/null | sed 's/^/   /'
        echo ""
        echo "📁 결과 파일:"
        find outputs/mvp-005 -name "run.jsonl" 2>/dev/null | wc -l | xargs echo "   처리된 인스턴스:"
    else
        echo "❌ 실험 종료됨 (PID: $PID)"
        echo "   로그 파일: logs/mvp-005.log"
    fi
else
    echo "ℹ️  실행 중인 실험 없음"
    echo "   PID 파일: logs/mvp-005.pid (없음)"
fi

echo ""
echo "=== 다른 실행 중인 실험 확인 ==="
RUNNING=$(ps aux | grep "run_mvp.py" | grep -v grep | wc -l)
if [ "$RUNNING" -gt 0 ]; then
    echo "실행 중인 프로세스: $RUNNING개"
    ps aux | grep "run_mvp.py" | grep -v grep | awk '{print "   PID: "$2" | "$11" "$12" "$13" "$14}'
else
    echo "실행 중인 프로세스 없음"
fi

echo ""
echo "=== 남은 시간 예측 ==="
python3 scripts/predict_remaining_time.py 2>/dev/null || echo "   예측 불가 (로그 파일 확인 필요)"

echo ""
echo "=== 확인 명령어 ==="
echo "   로그 확인: tail -f logs/mvp-005.log"
echo "   프로세스 확인: ps -p \$(cat logs/mvp-005.pid)"
echo "   결과 확인: ls -lh outputs/mvp-005/"
echo "   시간 예측: python3 scripts/predict_remaining_time.py"

