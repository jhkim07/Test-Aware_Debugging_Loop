#!/usr/bin/env python3
"""
성능 분석 스크립트
run_mvp.py 실행 결과를 분석하여 성능 메트릭을 계산하고 리포트를 생성합니다.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

def load_metrics(run_id: str) -> Dict:
    """모든 인스턴스의 metrics.json을 로드"""
    output_dir = Path("outputs") / run_id
    if not output_dir.exists():
        print(f"❌ 출력 디렉토리가 없습니다: {output_dir}")
        return {}
    
    metrics = {}
    for inst_dir in output_dir.iterdir():
        if inst_dir.is_dir():
            metrics_file = inst_dir / "metrics.json"
            if metrics_file.exists():
                with open(metrics_file) as f:
                    metrics[inst_dir.name] = json.load(f)
    
    return metrics

def analyze_performance(metrics: Dict) -> Dict:
    """성능 메트릭 분석"""
    if not metrics:
        return {}
    
    analysis = {
        "total_instances": len(metrics),
        "completed_instances": 0,
        "successful_instances": 0,
        "aggregate_scores": {
            "hfs": [],
            "tss": [],
            "brs": [],
            "overall": [],
        },
        "public_pass_rates": [],
        "hidden_pass_rates": [],
        "overfit_gaps": [],
        "iterations": [],
        "instance_details": [],
    }
    
    for inst_id, m in metrics.items():
        final = m.get("final_iteration", {})
        scores = m.get("scores", {})
        
        # 완료 여부 확인
        if m.get("iterations", 0) > 0:
            analysis["completed_instances"] += 1
        
        # 성공 여부 (Public Pass Rate > 0%)
        public_pass_rate = final.get("public_pass_rate", 0.0)
        if public_pass_rate > 0:
            analysis["successful_instances"] += 1
        
        # 메트릭 수집
        analysis["aggregate_scores"]["hfs"].append(scores.get("hfs", 0.0))
        analysis["aggregate_scores"]["tss"].append(scores.get("tss", 0.0))
        analysis["aggregate_scores"]["brs"].append(scores.get("brs", 0.0))
        analysis["aggregate_scores"]["overall"].append(scores.get("overall", 0.0))
        
        analysis["public_pass_rates"].append(public_pass_rate)
        analysis["hidden_pass_rates"].append(final.get("hidden_pass_rate", 0.0))
        analysis["overfit_gaps"].append(final.get("overfit_gap", 0.0))
        analysis["iterations"].append(m.get("iterations", 0))
        
        # 인스턴스별 상세 정보
        analysis["instance_details"].append({
            "instance_id": inst_id,
            "public_pass_rate": public_pass_rate,
            "hidden_pass_rate": final.get("hidden_pass_rate", 0.0),
            "overfit_gap": final.get("overfit_gap", 0.0),
            "brs_fail_on_buggy": final.get("brs_fail_on_buggy", False),
            "iterations": m.get("iterations", 0),
            "overall_score": scores.get("overall", 0.0),
        })
    
    # 평균 계산
    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0
    
    analysis["averages"] = {
        "hfs": avg(analysis["aggregate_scores"]["hfs"]),
        "tss": avg(analysis["aggregate_scores"]["tss"]),
        "brs": avg(analysis["aggregate_scores"]["brs"]),
        "overall": avg(analysis["aggregate_scores"]["overall"]),
        "public_pass_rate": avg(analysis["public_pass_rates"]),
        "hidden_pass_rate": avg(analysis["hidden_pass_rates"]),
        "overfit_gap": avg(analysis["overfit_gaps"]),
        "iterations": avg(analysis["iterations"]),
    }
    
    return analysis

def print_report(analysis: Dict, run_id: str):
    """성능 리포트 출력"""
    print("=" * 80)
    print(f"성능 분석 리포트: {run_id}")
    print("=" * 80)
    
    print(f"\n📊 전체 통계:")
    print(f"  총 인스턴스: {analysis['total_instances']}")
    print(f"  완료된 인스턴스: {analysis['completed_instances']}")
    print(f"  성공한 인스턴스 (Public Pass Rate > 0%): {analysis['successful_instances']}")
    print(f"  성공률: {analysis['successful_instances']/analysis['total_instances']*100:.1f}%")
    
    print(f"\n📈 평균 메트릭:")
    avg = analysis["averages"]
    print(f"  Public Pass Rate: {avg['public_pass_rate']:.2%}")
    print(f"  Hidden Pass Rate: {avg['hidden_pass_rate']:.2%}")
    print(f"  Overfit Gap: {avg['overfit_gap']:.2%}")
    print(f"  평균 Iterations: {avg['iterations']:.1f}")
    
    print(f"\n🎯 평균 점수:")
    print(f"  HFS (Hidden Fix Score): {avg['hfs']:.2%}")
    print(f"  TSS (Test Strength Score): {avg['tss']:.2%}")
    print(f"  BRS Score: {avg['brs']:.2%}")
    print(f"  Overall Score: {avg['overall']:.2%}")
    
    print(f"\n📋 인스턴스별 상세:")
    for detail in sorted(analysis["instance_details"], key=lambda x: x["overall_score"], reverse=True):
        inst_id = detail["instance_id"]
        print(f"\n  {inst_id}:")
        print(f"    Public Pass Rate: {detail['public_pass_rate']:.2%}")
        print(f"    Hidden Pass Rate: {detail['hidden_pass_rate']:.2%}")
        print(f"    Overfit Gap: {detail['overfit_gap']:.2%}")
        print(f"    BRS: {'✅' if detail['brs_fail_on_buggy'] else '❌'}")
        print(f"    Iterations: {detail['iterations']}")
        print(f"    Overall Score: {detail['overall_score']:.2%}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_performance.py <run-id>")
        print("Example: python scripts/analyze_performance.py mvp-full-run")
        sys.exit(1)
    
    run_id = sys.argv[1]
    
    print(f"Loading metrics for run: {run_id}...")
    metrics = load_metrics(run_id)
    
    if not metrics:
        print(f"❌ 메트릭을 찾을 수 없습니다. 실행이 완료되었는지 확인하세요.")
        sys.exit(1)
    
    analysis = analyze_performance(metrics)
    print_report(analysis, run_id)
    
    # JSON 리포트 저장
    report_file = Path("outputs") / run_id / "performance_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n✅ 리포트 저장: {report_file}")

if __name__ == "__main__":
    main()


