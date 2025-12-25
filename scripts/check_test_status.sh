#!/bin/bash
# 테스트 실행 상태 확인 스크립트

RUN_ID="test-verify-full-20251223-101204"

echo "=== 테스트 실행 상태 확인: $RUN_ID ==="
echo ""

# 프로세스 확인
if ps aux | grep -q "run_mvp.py.*$RUN_ID"; then
    echo "✅ 프로세스 실행 중"
    ps aux | grep "run_mvp.py.*$RUN_ID" | grep -v grep
else
    echo "❌ 프로세스가 실행되지 않음 (완료되었거나 오류 발생)"
fi

echo ""
echo "=== 최근 로그 (마지막 30줄) ==="
if [ -f "logs/${RUN_ID}.log" ]; then
    tail -30 "logs/${RUN_ID}.log"
else
    echo "로그 파일을 찾을 수 없습니다: logs/${RUN_ID}.log"
fi

echo ""
echo "=== 완료된 인스턴스 확인 ==="
if [ -d "outputs/${RUN_ID}" ]; then
    for inst_dir in outputs/${RUN_ID}/*/; do
        if [ -d "$inst_dir" ]; then
            inst_name=$(basename "$inst_dir")
            if [ -f "$inst_dir/metrics.json" ]; then
                echo "✅ $inst_name: 완료"
            else
                echo "⏳ $inst_name: 진행 중"
            fi
        fi
    done
else
    echo "출력 디렉토리가 아직 생성되지 않았습니다."
fi

echo ""
echo "=== 전체 로그 확인: tail -f logs/${RUN_ID}.log ==="





