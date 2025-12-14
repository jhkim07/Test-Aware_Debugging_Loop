#!/usr/bin/env python3
"""
실행 결과 분석 스크립트
JSONL 파일을 읽어서 분석 표를 생성합니다.
"""

import json
from pathlib import Path
from datetime import datetime

def analyze_results(output_dir: Path):
    """실행 결과를 분석하고 표를 생성합니다."""
    
    results = []
    instance_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    
    for inst_dir in instance_dirs:
        instance_id = inst_dir.name
        run_jsonl = inst_dir / "run.jsonl"
        
        if not run_jsonl.exists():
            continue
        
        iterations = []
        with open(run_jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        iterations.append(data)
                    except json.JSONDecodeError:
                        continue
        
        # 메트릭 파일 확인
        metrics_file = inst_dir / "metrics.json"
        metrics = {}
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    metrics = json.load(f)
            except:
                pass
        
        results.append({
            'instance_id': instance_id,
            'iterations': iterations,
            'metrics': metrics
        })
    
    return results

def print_summary_table(results):
    """결과를 표 형태로 출력합니다."""
    
    print("\n" + "="*100)
    print("테스트 인식 디버깅 루프 실행 결과 요약")
    print("="*100)
    print()
    
    for result in results:
        instance_id = result['instance_id']
        iterations = result['iterations']
        
        print(f"\n{'─'*100}")
        print(f"인스턴스: {instance_id}")
        print(f"{'─'*100}")
        print(f"총 Iteration 수: {len(iterations)}")
        print()
        
        # Iteration별 상세 표
        if iterations:
            print(f"{'Iteration':<10} {'Focus':<10} {'BRS Pass':<12} {'Public OK':<12} {'Hypotheses':<50}")
            print(f"{'─'*100}")
            
            for it_data in iterations:
                iter_num = it_data.get('iter', 'N/A')
                decision = it_data.get('decision', {})
                focus = decision.get('focus', 'N/A')
                brs_fail = it_data.get('brs_fail_on_buggy', 'N/A')
                brs_pass = '✓' if brs_fail else '✗'  # BRS는 버그 버전에서 실패해야 정상
                public_ok = '✓' if it_data.get('public_ok', False) else '✗'
                hypotheses = decision.get('hypotheses', [])
                hyp_str = hypotheses[0][:47] + '...' if hypotheses and len(hypotheses[0]) > 50 else (hypotheses[0] if hypotheses else 'N/A')
                
                print(f"{iter_num:<10} {focus:<10} {brs_pass:<12} {public_ok:<12} {hyp_str:<50}")
        
        print()
        
        # 전체 통계
        if iterations:
            total_iters = len(iterations)
            public_passed = sum(1 for it in iterations if it.get('public_ok', False))
            brs_passed = sum(1 for it in iterations if it.get('brs_fail_on_buggy', True))
            focus_dist = {}
            for it in iterations:
                focus = it.get('decision', {}).get('focus', 'unknown')
                focus_dist[focus] = focus_dist.get(focus, 0) + 1
            
            print(f"전체 통계:")
            print(f"  - Public 테스트 통과 횟수: {public_passed}/{total_iters}")
            print(f"  - BRS 측정 성공 횟수: {brs_passed}/{total_iters} (버그 버전에서 실패해야 정상)")
            print(f"  - Focus 분포: {dict(focus_dist)}")
            print()
        
        # 메트릭 출력
        metrics = result.get('metrics', {})
        if metrics:
            print(f"메트릭:")
            for key, value in metrics.items():
                print(f"  - {key}: {value}")
            print()

def print_detailed_analysis(results):
    """상세 분석 결과를 출력합니다."""
    
    print("\n" + "="*100)
    print("상세 분석")
    print("="*100)
    print()
    
    for result in results:
        instance_id = result['instance_id']
        iterations = result['iterations']
        
        print(f"\n인스턴스: {instance_id}")
        print(f"{'─'*100}")
        
        for idx, it_data in enumerate(iterations, 1):
            iter_num = it_data.get('iter', idx)
            decision = it_data.get('decision', {})
            
            print(f"\n[Iteration {iter_num}]")
            print(f"  Focus: {decision.get('focus', 'N/A')}")
            print(f"  BRS (Bug Reproduction Strength): {'✓' if it_data.get('brs_fail_on_buggy') else '✗'}")
            print(f"  Public 테스트 통과: {'✓' if it_data.get('public_ok') else '✗'}")
            
            hypotheses = decision.get('hypotheses', [])
            if hypotheses:
                print(f"  가설:")
                for i, hyp in enumerate(hypotheses, 1):
                    print(f"    {i}. {hyp}")
            
            targets = decision.get('targets', [])
            if targets:
                print(f"  목표:")
                for i, target in enumerate(targets, 1):
                    print(f"    {i}. {target}")
            
            run_ids = it_data.get('run_ids', {})
            if run_ids:
                print(f"  Run IDs:")
                print(f"    - Tests only: {run_ids.get('tests_only', 'N/A')}")
                print(f"    - Combined: {run_ids.get('combined', 'N/A')}")

if __name__ == "__main__":
    import sys
    
    output_dir = Path("outputs")
    if len(sys.argv) > 1:
        run_id = sys.argv[1]
        output_dir = output_dir / run_id
    else:
        # 가장 최근 실행 디렉토리 찾기
        if output_dir.exists():
            dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], 
                         key=lambda x: x.stat().st_mtime, reverse=True)
            if dirs:
                output_dir = dirs[0]
                print(f"가장 최근 실행 디렉토리 사용: {output_dir.name}")
    
    if not output_dir.exists():
        print(f"오류: 디렉토리를 찾을 수 없습니다: {output_dir}")
        sys.exit(1)
    
    results = analyze_results(output_dir)
    
    if not results:
        print("분석할 결과가 없습니다.")
        sys.exit(1)
    
    print_summary_table(results)
    print_detailed_analysis(results)




