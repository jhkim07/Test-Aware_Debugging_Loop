#!/usr/bin/env python3
"""
문제 진단 스크립트
리포트 파싱 실패의 근본 원인을 찾습니다.
"""
import json
import subprocess
from pathlib import Path

print("="*80)
print("SWE-bench Harness 리포트 파싱 문제 진단")
print("="*80)

# 1. 인스턴스 ID 유효성 확인
print("\n[1] 인스턴스 ID 유효성 확인")
print("-" * 80)

try:
    from datasets import load_dataset
    
    print("Loading SWE-bench Lite dataset...")
    ds = load_dataset('princeton-nlp/SWE-bench_Lite', split='test')
    instance_ids = [item['instance_id'] for item in ds]
    
    print(f"Total instances in Lite dataset: {len(instance_ids)}")
    
    # Config의 인스턴스 ID 확인
    config_file = Path("configs/mvp.yaml")
    if config_file.exists():
        import yaml
        config = yaml.safe_load(config_file.read_text())
        config_ids = config.get("instances", {}).get("list", [])
        
        print(f"\nConfig에 설정된 인스턴스 ID ({len(config_ids)}개):")
        for id in config_ids:
            if id in instance_ids:
                print(f"  ✓ {id} - 유효함")
            else:
                print(f"  ✗ {id} - 유효하지 않음!")
        
        if len(config_ids) < 10:
            print(f"\n⚠️  경고: 인스턴스 ID가 {len(config_ids)}개로 매우 적습니다.")
            print("   SWE-bench Lite는 수백 개의 인스턴스를 가지고 있습니다.")
            print("   더 많은 인스턴스를 추가하는 것을 권장합니다.")
    
except Exception as e:
    print(f"에러: {e}")
    print("datasets 라이브러리가 설치되어 있지 않거나 데이터셋 로드 실패")

# 2. Docker 환경 확인
print("\n[2] Docker 환경 확인")
print("-" * 80)

try:
    result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print(f"✓ Docker 설치됨: {result.stdout.strip()}")
        
        # Docker 데몬 실행 확인
        result2 = subprocess.run(['docker', 'ps'], capture_output=True, text=True, timeout=5)
        if result2.returncode == 0:
            print("✓ Docker 데몬 실행 중")
        else:
            print("✗ Docker 데몬이 실행되지 않음")
            print(f"  Error: {result2.stderr}")
    else:
        print("✗ Docker가 설치되지 않음")
except FileNotFoundError:
    print("✗ Docker가 설치되지 않음")
except Exception as e:
    print(f"✗ Docker 확인 중 에러: {e}")

# 3. 실제 리포트 디렉토리 확인
print("\n[3] 리포트 디렉토리 확인")
print("-" * 80)

runs_dir = Path("runs")
if runs_dir.exists():
    subdirs = [d for d in runs_dir.iterdir() if d.is_dir()]
    print(f"runs 디렉토리 존재: {len(subdirs)}개 하위 디렉토리")
    
    if subdirs:
        print("\n최근 실행 디렉토리 (최대 5개):")
        for d in sorted(subdirs, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            files = list(d.rglob("*"))
            file_count = len([f for f in files if f.is_file()])
            print(f"  - {d.name}: {file_count}개 파일")
            
            # JSON 파일 찾기
            json_files = [f for f in files if f.suffix == '.json']
            if json_files:
                print(f"    JSON 파일: {len(json_files)}개")
                for jf in json_files[:3]:
                    print(f"      - {jf.relative_to(d)}")
else:
    print("✗ runs 디렉토리가 존재하지 않음")
    print("  → SWE-bench harness가 리포트를 생성하지 않았을 가능성")

# 4. SWE-bench harness 실행 확인
print("\n[4] SWE-bench Harness 실행 가능 여부 확인")
print("-" * 80)

try:
    result = subprocess.run(
        ['python', '-m', 'swebench.harness.run_evaluation', '--help'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print("✓ swebench.harness.run_evaluation 실행 가능")
        if result.stdout:
            # Help 메시지에서 중요한 정보 추출
            if '--predictions_path' in result.stdout:
                print("  ✓ --predictions_path 옵션 확인됨")
            if '--instance_ids' in result.stdout:
                print("  ✓ --instance_ids 옵션 확인됨")
    else:
        print("✗ swebench.harness.run_evaluation 실행 실패")
        print(f"  Return code: {result.returncode}")
        if result.stderr:
            print(f"  Error: {result.stderr[:500]}")
except FileNotFoundError:
    print("✗ swebench 모듈을 찾을 수 없음")
except Exception as e:
    print(f"✗ 확인 중 에러: {e}")

# 5. 실제 실행 로그 확인
print("\n[5] 실제 실행 로그 확인")
print("-" * 80)

run_jsonl = Path("outputs/mvp-003/astropy__astropy-14539/run.jsonl")
if run_jsonl.exists():
    with open(run_jsonl) as f:
        lines = f.readlines()
        if lines:
            first = json.loads(lines[0])
            run_ids = first.get("run_ids", {})
            
            print(f"첫 번째 iteration의 run_id:")
            for key, value in run_ids.items():
                if value:
                    print(f"  {key}: {value}")
                    
                    # 해당 디렉토리 확인
                    if key == "combined":
                        report_dir = Path("runs") / value
                        if report_dir.exists():
                            print(f"    ✓ 리포트 디렉토리 존재: {report_dir}")
                        else:
                            print(f"    ✗ 리포트 디렉토리 없음: {report_dir}")

# 6. Predictions 파일 확인
print("\n[6] Predictions 파일 확인")
print("-" * 80)

pred_file = Path("outputs/mvp-003/astropy__astropy-14539/predictions.jsonl")
if pred_file.exists():
    with open(pred_file) as f:
        for line in f:
            data = json.loads(line)
            patch = data.get('model_patch', '')
            
            print(f"✓ predictions.jsonl 존재")
            print(f"  Patch 길이: {len(patch)} 문자")
            print(f"  conftest.py 포함: {'conftest.py' in patch}")
            print(f"  .ta_split.json 포함: {'.ta_split.json' in patch}")
            break
else:
    print("✗ predictions.jsonl이 없음")

print("\n" + "="*80)
print("진단 완료")
print("="*80)




