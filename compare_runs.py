#!/usr/bin/env python3
"""
두 실행 결과를 비교하는 스크립트
"""
import json
from pathlib import Path
from typing import Dict, Any

def load_run_data(run_dir: Path) -> Dict[str, Any]:
    """실행 결과 로드"""
    data = {
        "iterations": [],
        "metrics": {},
    }
    
    run_jsonl = run_dir / "run.jsonl"
    if run_jsonl.exists():
        with open(run_jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data["iterations"].append(json.loads(line))
                    except:
                        pass
    
    metrics_file = run_dir / "metrics.json"
    if metrics_file.exists():
        try:
            with open(metrics_file, 'r', encoding='utf-8') as f:
                data["metrics"] = json.load(f)
        except:
            pass
    
    return data

def compare_runs(run1_dir: Path, run2_dir: Path, run1_name: str = "Run 1", run2_name: str = "Run 2"):
    """두 실행 결과 비교"""
    data1 = load_run_data(run1_dir)
    data2 = load_run_data(run2_dir)
    
    print("\n" + "="*100)
    print(f"실행 결과 비교: {run1_name} vs {run2_name}")
    print("="*100)
    
    # 기본 통계 비교
    print(f"\n📊 기본 통계")
    print(f"{'항목':<30} {run1_name:<30} {run2_name:<30} {'개선':<10}")
    print("-" * 100)
    
    iter1 = len(data1["iterations"])
    iter2 = len(data2["iterations"])
    iter_improve = "✓" if iter2 < iter1 else ("✗" if iter2 > iter1 else "=")
    print(f"{'총 Iteration 수':<30} {iter1:<30} {iter2:<30} {iter_improve:<10}")
    
    # 최종 iteration 비교
    if data1["iterations"] and data2["iterations"]:
        final1 = data1["iterations"][-1]
        final2 = data2["iterations"][-1]
        
        # Public pass rate
        pub1 = final1.get("public", {}).get("pass_rate", 0.0) if isinstance(final1.get("public"), dict) else (1.0 if final1.get("public_ok", False) else 0.0)
        pub2 = final2.get("public", {}).get("pass_rate", 0.0) if isinstance(final2.get("public"), dict) else (1.0 if final2.get("public_ok", False) else 0.0)
        pub_improve = "✓" if pub2 > pub1 else ("✗" if pub2 < pub1 else "=")
        print(f"{'Public Pass Rate':<30} {pub1:.2%}<30 {pub2:.2%}<30 {pub_improve:<10}")
        
        # BRS
        brs1 = final1.get("brs", {}).get("fail_on_buggy", False) if isinstance(final1.get("brs"), dict) else final1.get("brs_fail_on_buggy", False)
        brs2 = final2.get("brs", {}).get("fail_on_buggy", False) if isinstance(final2.get("brs"), dict) else final2.get("brs_fail_on_buggy", False)
        brs_improve = "✓" if brs2 else ("✗" if not brs2 and brs1 else "=")
        print(f"{'BRS (Bug Repro)':<30} {'✓' if brs1 else '✗'}<30 {'✓' if brs2 else '✗'}<30 {brs_improve:<10}")
        
        # Hidden pass rate (if available)
        hidden1 = final1.get("hidden", {})
        hidden2 = final2.get("hidden", {})
        if isinstance(hidden1, dict) and "pass_rate" in hidden1:
            h1 = hidden1.get("pass_rate", 0.0)
            h2 = hidden2.get("pass_rate", 0.0) if isinstance(hidden2, dict) else 0.0
            h_improve = "✓" if h2 > h1 else ("✗" if h2 < h1 else "=")
            print(f"{'Hidden Pass Rate':<30} {h1:.2%}<30 {h2:.2%}<30 {h_improve:<10}")
        
        # Overfit Gap
        og1 = final1.get("overfit_gap", 0.0)
        og2 = final2.get("overfit_gap", 0.0)
        og_improve = "✓" if abs(og2) < abs(og1) else ("✗" if abs(og2) > abs(og1) else "=")
        print(f"{'Overfit Gap':<30} {og1:.4f}<30 {og2:.4f}<30 {og_improve:<10}")
    
    # 메트릭 비교
    if data1["metrics"] and data2["metrics"]:
        print(f"\n📈 최종 메트릭 비교")
        print(f"{'메트릭':<30} {run1_name:<30} {run2_name:<30} {'개선':<10}")
        print("-" * 100)
        
        scores1 = data1["metrics"].get("scores", {})
        scores2 = data2["metrics"].get("scores", {})
        
        if scores1 and scores2:
            for key in ["hfs", "tss", "og", "brs", "overall"]:
                val1 = scores1.get(key, 0.0)
                val2 = scores2.get(key, 0.0)
                if key == "og":  # Overfit Gap: 작을수록 좋음
                    improve = "✓" if abs(val2) < abs(val1) else ("✗" if abs(val2) > abs(val1) else "=")
                else:  # 나머지: 클수록 좋음
                    improve = "✓" if val2 > val1 else ("✗" if val2 < val1 else "=")
                
                key_name = {
                    "hfs": "HFS (Hidden Fix Score)",
                    "tss": "TSS (Test Strength)",
                    "og": "OG (Overfit Gap)",
                    "brs": "BRS Score",
                    "overall": "Overall Score",
                }.get(key, key.upper())
                
                print(f"{key_name:<30} {val1:.4f}<30 {val2:.4f}<30 {improve:<10}")
    
    # Iteration별 상세 비교
    print(f"\n📋 Iteration별 상세 비교")
    print(f"{'Iter':<6} {'Metric':<20} {run1_name:<30} {run2_name:<30}")
    print("-" * 100)
    
    max_iters = max(len(data1["iterations"]), len(data2["iterations"]))
    for i in range(max_iters):
        iter_num = i + 1
        it1 = data1["iterations"][i] if i < len(data1["iterations"]) else None
        it2 = data2["iterations"][i] if i < len(data2["iterations"]) else None
        
        if it1 or it2:
            # Public OK
            pub1_val = "✓" if (it1.get("public", {}).get("ok", False) if isinstance(it1.get("public"), dict) else it1.get("public_ok", False)) if it1 else "N/A" else "✗"
            pub2_val = "✓" if (it2.get("public", {}).get("ok", False) if isinstance(it2.get("public"), dict) else it2.get("public_ok", False)) if it2 else "N/A" else "✗"
            print(f"{iter_num:<6} {'Public OK':<20} {pub1_val:<30} {pub2_val:<30}")
            
            # BRS
            brs1_val = "✓" if (it1.get("brs", {}).get("fail_on_buggy", False) if isinstance(it1.get("brs"), dict) else it1.get("brs_fail_on_buggy", False)) if it1 else "N/A" else "✗"
            brs2_val = "✓" if (it2.get("brs", {}).get("fail_on_buggy", False) if isinstance(it2.get("brs"), dict) else it2.get("brs_fail_on_buggy", False)) if it2 else "N/A" else "✗"
            print(f"{'':<6} {'BRS':<20} {brs1_val:<30} {brs2_val:<30}")
            
            # Overfit Gap
            if it1 and "overfit_gap" in it1:
                print(f"{'':<6} {'Overfit Gap':<20} {it1.get('overfit_gap', 0.0):.4f}<30 {it2.get('overfit_gap', 0.0):.4f if it2 else 'N/A':<30}")
    
    print("\n" + "="*100)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python compare_runs.py <run1_dir> <run2_dir> [run1_name] [run2_name]")
        sys.exit(1)
    
    run1_dir = Path(sys.argv[1])
    run2_dir = Path(sys.argv[2])
    run1_name = sys.argv[3] if len(sys.argv) > 3 else "Run 1"
    run2_name = sys.argv[4] if len(sys.argv) > 4 else "Run 2"
    
    if not run1_dir.exists() or not run2_dir.exists():
        print(f"Error: Directory not found")
        sys.exit(1)
    
    compare_runs(run1_dir, run2_dir, run1_name, run2_name)




