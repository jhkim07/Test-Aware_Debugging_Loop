#!/usr/bin/env python3
"""
Harness 실행 시 실제 stderr 확인
"""
import subprocess
from pathlib import Path
import json

# 실제로 harness가 실행될 때의 stderr 확인
# 간단한 테스트 실행

print("="*80)
print("Harness 실행 테스트 (stderr 확인)")
print("="*80)

# predictions.jsonl 확인
pred_file = Path("outputs/mvp-003/astropy__astropy-14539/predictions.jsonl")
if not pred_file.exists():
    print("predictions.jsonl이 없습니다.")
    exit(1)

# 실제 harness 실행 시도 (짧은 타임아웃)
print("\n[테스트] 유효한 인스턴스 ID로 harness 실행 테스트...")
print("인스턴스 ID: sympy__sympy-20590 (유효함)")

cmd = [
    "python", "-m", "swebench.harness.run_evaluation",
    "--dataset_name", "princeton-nlp/SWE-bench_Lite",
    "--predictions_path", str(pred_file),
    "--instance_ids", "sympy__sympy-20590",
    "--run_id", "test-debug-run",
    "--max_workers", "1",
    "--cache_level", "instance",
    "--clean", "False",
    "--timeout", "60",  # 짧은 타임아웃
]

print(f"\n실행 명령: {' '.join(cmd)}")
print("\n실행 중... (타임아웃 30초)")

try:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        env=None
    )
    
    print(f"\nReturn code: {result.returncode}")
    print(f"\nSTDOUT (first 1000 chars):")
    print(result.stdout[:1000])
    print(f"\nSTDERR (first 1000 chars):")
    print(result.stderr[:1000])
    
    # 리포트 디렉토리 확인
    report_dir = Path("runs/test-debug-run")
    if report_dir.exists():
        print(f"\n✓ 리포트 디렉토리 생성됨: {report_dir}")
        files = list(report_dir.rglob("*"))
        print(f"  파일 수: {len([f for f in files if f.is_file()])}")
    else:
        print(f"\n✗ 리포트 디렉토리 없음: {report_dir}")
        
except subprocess.TimeoutExpired:
    print("\n⏱️  타임아웃 (정상 - harness 실행이 오래 걸릴 수 있음)")
except Exception as e:
    print(f"\n에러: {e}")




