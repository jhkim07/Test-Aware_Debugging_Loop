#!/bin/bash
# 실행 완료 대기 및 성능 분석 자동 실행 스크립트

RUN_ID="mvp-full-run"
EXPECTED_INSTANCES=4
CHECK_INTERVAL=60  # 60초마다 확인

echo "=========================================="
echo "실행 완료 대기 및 성능 분석"
echo "=========================================="
echo "Run ID: $RUN_ID"
echo "예상 인스턴스 수: $EXPECTED_INSTANCES"
echo "확인 간격: ${CHECK_INTERVAL}초"
echo ""

cd "$(dirname "$0")/.."

while true; do
    # 완료된 인스턴스 수 확인
    COMPLETED=$(python3 << EOF
from pathlib import Path
import json

run_id = "$RUN_ID"
output_dir = Path("outputs") / run_id

if not output_dir.exists():
    print(0)
    exit(0)

completed = 0
for inst_dir in output_dir.iterdir():
    if inst_dir.is_dir():
        metrics_file = inst_dir / "metrics.json"
        if metrics_file.exists():
            completed += 1

print(completed)
EOF
)
    
    echo "[$(date '+%H:%M:%S')] 완료: $COMPLETED/$EXPECTED_INSTANCES"
    
    if [ "$COMPLETED" -eq "$EXPECTED_INSTANCES" ]; then
        echo ""
        echo "✅ 모든 인스턴스 완료!"
        echo ""
        echo "성능 분석 시작..."
        
        # 성능 분석 실행
        python3 scripts/analyze_performance.py "$RUN_ID"
        
        # 리포트 생성
        python3 << 'PYEOF'
import json
from pathlib import Path
from datetime import datetime

run_id = "mvp-full-run"
report_file = Path("outputs") / run_id / "performance_report.json"

if report_file.exists():
    with open(report_file) as f:
        analysis = json.load(f)
    
    report_md = f"""# MVP 성능 분석 리포트

**실행 ID**: {run_id}  
**분석 날짜**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**설정 파일**: configs/mvp.yaml

---

## 실행 요약

### 설정
- **인스턴스 수**: {analysis['total_instances']}개
- **Max Iterations**: 8
- **Time Limit**: 30 minutes per instance
- **LLM Model**: gpt-4o-mini
- **Public Ratio**: 0.7

### 인스턴스 목록
1. `astropy__astropy-12907`
2. `astropy__astropy-14182`
3. `astropy__astropy-14365`
4. `sympy__sympy-20590`

---

## 전체 통계

- **총 인스턴스**: {analysis['total_instances']}개
- **완료된 인스턴스**: {analysis['completed_instances']}개
- **성공한 인스턴스** (Public Pass Rate > 0%): {analysis['successful_instances']}개
- **성공률**: {analysis['successful_instances']/analysis['total_instances']*100:.1f}%

---

## 평균 메트릭

### 테스트 통과율
- **Public Pass Rate**: {analysis['averages']['public_pass_rate']:.2%}
- **Hidden Pass Rate**: {analysis['averages']['hidden_pass_rate']:.2%}
- **Overfit Gap**: {analysis['averages']['overfit_gap']:.2%}

### 반복 횟수
- **평균 Iterations**: {analysis['averages']['iterations']:.1f}

---

## 평균 점수

- **HFS (Hidden Fix Score)**: {analysis['averages']['hfs']:.2%}
- **TSS (Test Strength Score)**: {analysis['averages']['tss']:.2%}
- **BRS Score**: {analysis['averages']['brs']:.2%}
- **Overall Score**: {analysis['averages']['overall']:.2%}

---

## 인스턴스별 상세 결과

"""

    for detail in sorted(analysis['instance_details'], key=lambda x: x['overall_score'], reverse=True):
        inst_id = detail['instance_id']
        report_md += f"""
### {inst_id}

- **Public Pass Rate**: {detail['public_pass_rate']:.2%}
- **Hidden Pass Rate**: {detail['hidden_pass_rate']:.2%}
- **Overfit Gap**: {detail['overfit_gap']:.2%}
- **BRS (Bug Reproduction)**: {'✅ Tests fail on buggy code' if detail['brs_fail_on_buggy'] else '❌ Tests pass on buggy code'}
- **Iterations**: {detail['iterations']}
- **Overall Score**: {detail['overall_score']:.2%}

"""

    report_md += """
---

## 결론 및 인사이트

"""

    success_rate = analysis['successful_instances'] / analysis['total_instances']
    if success_rate >= 0.75:
        report_md += "✅ **우수한 성능**: 대부분의 인스턴스에서 성공적으로 패치를 생성하고 테스트를 통과했습니다.\n\n"
    elif success_rate >= 0.5:
        report_md += "⚠️ **양호한 성능**: 절반 이상의 인스턴스에서 성공했습니다. 개선 여지가 있습니다.\n\n"
    else:
        report_md += "❌ **개선 필요**: 성공률이 낮습니다. 프롬프트나 로직 개선이 필요할 수 있습니다.\n\n"

    avg_overfit = analysis['averages']['overfit_gap']
    if abs(avg_overfit) < 0.1:
        report_md += f"✅ **Overfitting 없음**: Overfit Gap이 {avg_overfit:.2%}로 매우 낮아 편법 패치 없이 올바른 수정을 수행했습니다.\n\n"
    elif abs(avg_overfit) < 0.3:
        report_md += f"⚠️ **약간의 Overfitting**: Overfit Gap이 {avg_overfit:.2%}입니다. 일부 편법 패치 가능성이 있습니다.\n\n"
    else:
        report_md += f"❌ **심각한 Overfitting**: Overfit Gap이 {avg_overfit:.2%}로 높습니다. 편법 패치가 많을 수 있습니다.\n\n"

    avg_brs = analysis['averages']['brs']
    if avg_brs >= 0.75:
        report_md += f"✅ **우수한 BRS**: 평균 BRS가 {avg_brs:.2%}로 높아 테스트가 버그를 잘 재현합니다.\n\n"
    else:
        report_md += f"⚠️ **BRS 개선 필요**: 평균 BRS가 {avg_brs:.2%}입니다. 테스트 강화가 필요할 수 있습니다.\n\n"

    report_path = Path("PERFORMANCE_REPORT.md")
    report_path.write_text(report_md, encoding='utf-8')
    print(f"✅ 리포트 생성 완료: {report_path}")

PYEOF
        
        echo ""
        echo "✅ 성능 분석 및 리포트 생성 완료!"
        echo "   - JSON 리포트: outputs/$RUN_ID/performance_report.json"
        echo "   - 마크다운 리포트: PERFORMANCE_REPORT.md"
        break
    fi
    
    sleep $CHECK_INTERVAL
done


