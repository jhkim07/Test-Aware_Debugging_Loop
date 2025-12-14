#!/bin/bash
# OpenAI API 사용량 확인 스크립트

cd "$(dirname "$0")/.."

echo "═══════════════════════════════════════════════════════════"
echo "  OpenAI API 사용량 확인"
echo "═══════════════════════════════════════════════════════════"
echo ""

# API 키 확인
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
    echo ""
    echo "설정 방법:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    exit 1
fi

echo "✅ API 키 확인됨"
echo "   키 앞 7자리: ${OPENAI_API_KEY:0:7}..."
echo ""

echo "📊 사용량 확인 방법:"
echo ""
echo "1. 🌐 웹 대시보드 (권장 - 가장 정확함):"
echo "   → https://platform.openai.com/usage"
echo "   - 로그인 필요"
echo "   - 실시간 사용량 및 비용 확인"
echo "   - 일별/월별 사용량 그래프"
echo "   - 모델별 사용량 상세 정보"
echo ""

echo "2. 🔑 API를 통한 확인:"
echo "   python3 -c \""
echo "import requests, os"
echo "headers = {'Authorization': f'Bearer {os.environ.get(\"OPENAI_API_KEY\")}'}"
echo "r = requests.get('https://api.openai.com/v1/usage', headers=headers)"
echo "print(r.json() if r.status_code == 200 else r.text)"
echo "   \""
echo ""

echo "3. 📝 프로젝트 로그에서 호출 횟수 확인:"
LOG_COUNT=$(find logs -name "*.log" -type f 2>/dev/null | wc -l)
if [ "$LOG_COUNT" -gt 0 ]; then
    echo "   로그 파일 수: $LOG_COUNT개"
    echo "   최근 로그:"
    ls -lt logs/*.log 2>/dev/null | head -3 | awk '{print "     - " $9}'
else
    echo "   로그 파일 없음"
fi
echo ""

echo "💡 OpenAI 대시보드 링크:"
echo "   - Usage: https://platform.openai.com/usage"
echo "   - Billing: https://platform.openai.com/account/billing"
echo "   - API Keys: https://platform.openai.com/api-keys"
echo ""




