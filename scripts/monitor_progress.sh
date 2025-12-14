#!/bin/bash
# 15분마다 진행 상황을 확인하고 리포트하는 스크립트

RUN_ID="mvp-full-run"
EXPECTED_INSTANCES=4
CHECK_INTERVAL=900  # 15분 = 900초
REPORT_DIR="outputs/$RUN_ID"

echo "=========================================="
echo "진행 상황 모니터링 시작"
echo "=========================================="
echo "Run ID: $RUN_ID"
echo "예상 인스턴스 수: $EXPECTED_INSTANCES"
echo "보고 간격: 15분"
echo ""

cd "$(dirname "$0")/.."

REPORT_COUNT=0

while true; do
    REPORT_COUNT=$((REPORT_COUNT + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo ""
    echo "=========================================="
    echo "[보고 #$REPORT_COUNT] $TIMESTAMP"
    echo "=========================================="
    
    # 진행 상황 확인 및 리포트 생성
    python3 << PYEOF
from pathlib import Path
import json
from datetime import datetime

run_id = "$RUN_ID"
output_dir = Path("outputs") / run_id

if not output_dir.exists():
    print("❌ 출력 디렉토리가 아직 생성되지 않았습니다.")
    print("   실행이 시작 중입니다...")
    exit(0)

instances = sorted([d.name for d in output_dir.iterdir() if d.is_dir()])
completed_instances = []
in_progress_instances = []

for inst_id in instances:
    inst_dir = output_dir / inst_id
    metrics_file = inst_dir / "metrics.json"
    log_file = inst_dir / "run.jsonl"
    
    if metrics_file.exists():
        with open(metrics_file) as f:
            m = json.load(f)
        final = m.get("final_iteration", {})
        scores = m.get("scores", {})
        completed_instances.append({
            "instance_id": inst_id,
            "public_pass_rate": final.get("public_pass_rate", 0.0),
            "hidden_pass_rate": final.get("hidden_pass_rate", 0.0),
            "overfit_gap": final.get("overfit_gap", 0.0),
            "overall_score": scores.get("overall", 0.0),
            "iterations": m.get("iterations", 0),
            "max_iters": m.get("max_iters", 8),
            "brs_fail_on_buggy": final.get("brs_fail_on_buggy", False),
        })
    elif log_file.exists():
        with open(log_file) as f:
            lines = [l for l in f if l.strip()]
        if lines:
            try:
                last_log = json.loads(lines[-1])
                iter_num = last_log.get("iter", 0)
                public_info = last_log.get("public", {})
                in_progress_instances.append({
                    "instance_id": inst_id,
                    "current_iter": iter_num,
                    "public_passed": public_info.get("passed", 0),
                    "public_total": public_info.get("total", 0),
                })
            except:
                in_progress_instances.append({"instance_id": inst_id, "status": "로그 기록 중"})
    else:
        in_progress_instances.append({"instance_id": inst_id, "status": "시작 대기 중"})

print(f"\n📊 전체 진행 상황:")
print(f"   완료: {len(completed_instances)}/{len(instances)}")
print(f"   진행 중: {len(in_progress_instances)}/{len(instances)}")
print(f"   진행률: {len(completed_instances)/len(instances)*100:.1f}%")

if completed_instances:
    print(f"\n✅ 완료된 인스턴스:")
    for item in completed_instances:
        inst_id = item["instance_id"]
        print(f"\n   {inst_id}:")
        print(f"      Public Pass Rate: {item['public_pass_rate']:.2%}")
        print(f"      Hidden Pass Rate: {item['hidden_pass_rate']:.2%}")
        print(f"      Overfit Gap: {item['overfit_gap']:.2%}")
        print(f"      Overall Score: {item['overall_score']:.2%}")
        print(f"      Iterations: {item['iterations']}/{item['max_iters']}")
        print(f"      BRS: {'✅' if item['brs_fail_on_buggy'] else '❌'}")

if in_progress_instances:
    print(f"\n⏳ 진행 중인 인스턴스:")
    for item in in_progress_instances:
        inst_id = item["instance_id"]
        if "current_iter" in item:
            print(f"   {inst_id}: Iteration {item['current_iter']} 실행 중")
            if item.get("public_total", 0) > 0:
                print(f"      Public: {item['public_passed']}/{item['public_total']} passed")
        else:
            print(f"   {inst_id}: {item.get('status', '진행 중')}")

# 성공률 계산
if completed_instances:
    successful = sum(1 for item in completed_instances if item['public_pass_rate'] > 0)
    success_rate = successful / len(completed_instances) * 100
    print(f"\n🎯 성공률: {successful}/{len(completed_instances)} ({success_rate:.1f}%)")

# 모든 인스턴스가 완료되었는지 확인
if len(completed_instances) == len(instances) and len(instances) > 0:
    print(f"\n✅ 모든 인스턴스 완료!")
    print(f"\n📈 성능 분석 실행 중...")
    
    # 성능 분석 실행
    import subprocess
    result = subprocess.run(
        ["python3", "scripts/analyze_performance.py", run_id],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(result.stdout)
        
        # 리포트 생성
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
            print(f"\n✅ 최종 리포트 생성 완료: {report_path}")
            print(f"   - JSON 리포트: outputs/{run_id}/performance_report.json")
            print(f"   - 마크다운 리포트: PERFORMANCE_REPORT.md")
    else:
        print(f"⚠️ 성능 분석 실행 실패: {result.stderr}")
    
    print(f"\n✅ 모니터링 완료. 종료합니다.")
    exit(0)

PYEOF
    
    # 다음 확인까지 대기
    echo ""
    echo "다음 보고까지 대기 중... (15분)"
    sleep $CHECK_INTERVAL
done


