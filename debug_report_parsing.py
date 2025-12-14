#!/usr/bin/env python3
"""
리포트 파싱 디버깅 스크립트
실제 stdout/stderr과 리포트 파일을 확인합니다.
"""
import json
from pathlib import Path
from bench_agent.runner.report_parser import parse_harness_report, parse_pytest_output

# 가장 최근 실행 결과 확인
run_jsonl = Path("outputs/mvp-003/astropy__astropy-14539/run.jsonl")
if not run_jsonl.exists():
    print(f"File not found: {run_jsonl}")
    exit(1)

# 첫 번째 iteration의 run_id 가져오기
with open(run_jsonl) as f:
    first_line = f.readline()
    if first_line:
        data = json.loads(first_line)
        combined_run_id = data.get("run_ids", {}).get("combined")
        if combined_run_id:
            print(f"Checking run_id: {combined_run_id}")
            
            # 리포트 디렉토리 찾기
            report_dir = Path("runs") / combined_run_id
            print(f"\nReport directory: {report_dir}")
            print(f"Exists: {report_dir.exists()}")
            
            if report_dir.exists():
                print(f"\nFiles in report dir:")
                for f in report_dir.rglob("*"):
                    if f.is_file():
                        print(f"  - {f.relative_to(report_dir)} ({f.stat().st_size} bytes)")
                
                # 리포트 파싱 시도
                print(f"\n=== Parsing report ===")
                result = parse_harness_report(report_dir, "astropy__astropy-14539", debug=True)
                print(f"Result: {result}")
            else:
                print(f"\nReport directory does not exist!")
                print(f"Looking for similar directories...")
                runs_dir = Path("runs")
                if runs_dir.exists():
                    similar = [d for d in runs_dir.iterdir() if combined_run_id.split("-")[-1] in d.name]
                    for d in similar[:5]:
                        print(f"  - {d}")




