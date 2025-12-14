#!/bin/bash
# Cursor 창을 닫아도 실험이 계속 실행되도록 nohup으로 실행하는 스크립트

set -e

# 설정 확인
CONFIG="${1:-configs/mvp.yaml}"
RUN_ID="${2:-mvp-$(date +%Y%m%d-%H%M%S)}"
MAX_WORKERS="${3:-1}"

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

# 로그 디렉토리 생성
mkdir -p logs

# nohup으로 실행 (터미널 세션과 독립적으로 실행)
nohup bash -c "
export PYTHONPATH=$PROJECT_ROOT:\$PYTHONPATH
cd $PROJECT_ROOT
timeout 7200 python scripts/run_mvp.py \
  --config $CONFIG \
  --run-id $RUN_ID \
  --max-workers $MAX_WORKERS \
  > logs/${RUN_ID}.log 2>&1
" &

# 프로세스 ID 저장
PID=$!
echo "실험이 백그라운드에서 실행 중입니다."
echo "PID: $PID"
echo "로그 파일: logs/${RUN_ID}.log"
echo ""
echo "프로세스 상태 확인: ps -p $PID"
echo "로그 확인: tail -f logs/${RUN_ID}.log"
echo "프로세스 종료: kill $PID"

# PID를 파일에 저장
echo $PID > logs/${RUN_ID}.pid

# 실행 중인 실험 정보 파일 생성 (다음 Cursor 세션에서 확인용)
cat > ../.experiment_running << EOF
# 현재 실행 중인 실험 정보
# 이 파일이 존재하면 실험이 실행 중일 수 있습니다
# 확인: ./scripts/check_experiment.sh

RUN_ID=${RUN_ID}
PID_FILE=logs/${RUN_ID}.pid
LOG_FILE=logs/${RUN_ID}.log
STARTED_AT=$(date)
EOF

