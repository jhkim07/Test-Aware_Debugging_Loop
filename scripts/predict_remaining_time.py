#!/usr/bin/env python3
"""
실험 남은 시간 예측 스크립트
"""
import json
import os
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

def load_config(config_path: str) -> dict:
    """설정 파일 로드"""
    with open(config_path) as f:
        return yaml.safe_load(f)

def parse_experiment_status(run_id: str, config: dict) -> Dict:
    """실험 진행 상황 파싱"""
    limits = config.get("limits", {})
    max_iters = limits.get("max_iters", 8)
    time_limit_minutes = limits.get("time_limit_minutes", 30)
    instance_ids = config.get("instances", {}).get("list", [])
    
    outputs_dir = Path("outputs") / run_id
    runs_dir = Path("runs") / run_id
    
    status = {
        "total_instances": len(instance_ids),
        "max_iters": max_iters,
        "time_limit_minutes": time_limit_minutes,
        "completed": [],
        "in_progress": [],
        "pending": [],
        "iteration_times": [],  # 각 iteration의 소요 시간 (분)
    }
    
    # 각 인스턴스별 상태 확인
    for instance_id in instance_ids:
        # outputs 디렉토리에서 확인 (최신 상태)
        inst_dir = outputs_dir / instance_id if outputs_dir.exists() else None
        run_jsonl = inst_dir / "run.jsonl" if inst_dir else None
        
        if run_jsonl and run_jsonl.exists():
            # run.jsonl에서 iteration 수와 타임스탬프 확인
            with open(run_jsonl) as f:
                lines = [l.strip() for l in f if l.strip()]
                
            if not lines:
                status["pending"].append((instance_id, 0))
                continue
                
            # 마지막 iteration 정보
            try:
                last_entry = json.loads(lines[-1])
                iter_num = last_entry.get("iteration", len(lines))
                done = last_entry.get("done", False)
                
                # 타임스탬프 분석하여 iteration 시간 추정
                timestamps = []
                for line in lines:
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp")
                        if ts:
                            timestamps.append(datetime.fromisoformat(ts.replace('Z', '+00:00')))
                    except:
                        pass
                
                # iteration 간 시간 차이 계산
                if len(timestamps) >= 2:
                    for i in range(1, len(timestamps)):
                        delta = (timestamps[i] - timestamps[i-1]).total_seconds() / 60
                        if delta > 0 and delta < 60:  # 합리적인 범위 (1분 ~ 60분)
                            status["iteration_times"].append(delta)
                
                if done:
                    status["completed"].append(instance_id)
                else:
                    elapsed_time = None
                    if inst_dir:
                        # 파일 수정 시간으로 경과 시간 추정
                        mtime = run_jsonl.stat().st_mtime
                        start_time = mtime - sum(status["iteration_times"][-iter_num:]) * 60 if status["iteration_times"] else mtime
                        elapsed_time = (datetime.now().timestamp() - start_time) / 60
                    
                    status["in_progress"].append({
                        "instance_id": instance_id,
                        "current_iter": iter_num,
                        "remaining_iters": max_iters - iter_num,
                        "elapsed_minutes": elapsed_time,
                    })
            except Exception as e:
                # 파싱 실패 시 대기 중으로 처리
                status["pending"].append((instance_id, 0))
        else:
            status["pending"].append((instance_id, 0))
    
    return status

def predict_remaining_time(status: Dict) -> Dict:
    """남은 시간 예측"""
    max_iters = status["max_iters"]
    time_limit = status["time_limit_minutes"]
    
    # iteration 평균 시간 계산
    iter_times = status["iteration_times"]
    if iter_times:
        avg_iter_time = sum(iter_times) / len(iter_times)
        # 최대값과 최소값 제거하여 이상치 제거
        sorted_times = sorted(iter_times)
        if len(sorted_times) > 4:
            trimmed_times = sorted_times[1:-1]
            avg_iter_time = sum(trimmed_times) / len(trimmed_times)
    else:
        # 기본 추정값: iteration당 5분 (테스트 실행 + LLM 호출 고려)
        avg_iter_time = 5.0
    
    # 진행 중인 인스턴스들의 남은 시간
    in_progress_remaining = 0.0
    for item in status["in_progress"]:
        remaining_iters = item["remaining_iters"]
        elapsed = item.get("elapsed_minutes", 0) or 0
        
        # 현재 iteration의 남은 시간 추정
        if elapsed > 0 and elapsed < avg_iter_time:
            current_iter_remaining = avg_iter_time - elapsed
        else:
            current_iter_remaining = 0
        
        # 남은 iteration들의 예상 시간
        future_iters_time = remaining_iters * avg_iter_time
        
        # 시간 제한 고려
        instance_remaining = min(
            current_iter_remaining + future_iters_time,
            time_limit - elapsed if elapsed else time_limit
        )
        in_progress_remaining += max(0, instance_remaining)
    
    # 대기 중인 인스턴스들의 예상 시간
    pending_instances = len(status["pending"])
    pending_time = pending_instances * min(avg_iter_time * max_iters, time_limit)
    
    # 총 예상 남은 시간
    total_remaining = in_progress_remaining + pending_time
    
    return {
        "avg_iter_time_minutes": avg_iter_time,
        "in_progress_remaining_minutes": in_progress_remaining,
        "pending_time_minutes": pending_time,
        "total_remaining_minutes": total_remaining,
        "total_remaining_hours": total_remaining / 60,
        "estimated_completion": datetime.now() + timedelta(minutes=total_remaining),
    }

def format_time(minutes: float) -> str:
    """시간을 읽기 쉬운 형식으로 포맷"""
    if minutes < 60:
        return f"{int(minutes)}분"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}시간 {mins}분"

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", help="Run ID (기본: .experiment_running에서 읽기)")
    ap.add_argument("--config", default="configs/mvp.yaml", help="설정 파일 경로")
    args = ap.parse_args()
    
    # Run ID 확인
    run_id = args.run_id
    if not run_id:
        exp_file = Path(".experiment_running")
        if exp_file.exists():
            with open(exp_file) as f:
                for line in f:
                    if line.startswith("RUN_ID="):
                        run_id = line.split("=", 1)[1].strip()
                        break
    
    if not run_id:
        print("❌ Run ID를 찾을 수 없습니다.")
        print("   --run-id 옵션을 사용하거나 .experiment_running 파일을 확인하세요.")
        return
    
    print(f"📊 실험 진행 상황 분석: {run_id}")
    print("=" * 60)
    
    # 설정 로드
    config = load_config(args.config)
    
    # 상태 분석
    status = parse_experiment_status(run_id, config)
    
    # 결과 출력
    print(f"\n📋 전체 현황:")
    print(f"   총 인스턴스: {status['total_instances']}개")
    print(f"   완료: {len(status['completed'])}개")
    print(f"   진행 중: {len(status['in_progress'])}개")
    print(f"   대기: {len(status['pending'])}개")
    
    if status['completed']:
        print(f"\n✅ 완료된 인스턴스:")
        for inst_id in status['completed']:
            print(f"   - {inst_id}")
    
    if status['in_progress']:
        print(f"\n🔄 진행 중인 인스턴스:")
        for item in status['in_progress']:
            inst_id = item['instance_id']
            curr_iter = item['current_iter']
            remaining_iters = item['remaining_iters']
            elapsed = item.get('elapsed_minutes')
            elapsed_str = f"{int(elapsed)}분" if elapsed else "알 수 없음"
            print(f"   - {inst_id}:")
            print(f"     현재: iteration {curr_iter}/{status['max_iters']}")
            print(f"     남은 iteration: {remaining_iters}개")
            print(f"     경과 시간: {elapsed_str}")
    
    if status['pending']:
        print(f"\n⏳ 대기 중인 인스턴스:")
        for inst_id, _ in status['pending']:
            print(f"   - {inst_id}")
    
    # 시간 예측
    prediction = predict_remaining_time(status)
    
    print(f"\n⏱️  시간 예측:")
    print(f"   평균 iteration 시간: {prediction['avg_iter_time_minutes']:.1f}분")
    print(f"   진행 중인 인스턴스 남은 시간: {format_time(prediction['in_progress_remaining_minutes'])}")
    print(f"   대기 중인 인스턴스 예상 시간: {format_time(prediction['pending_time_minutes'])}")
    print(f"   총 예상 남은 시간: {format_time(prediction['total_remaining_minutes'])} ({prediction['total_remaining_hours']:.1f}시간)")
    print(f"   예상 완료 시각: {prediction['estimated_completion'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 경고
    if prediction['total_remaining_minutes'] > config['limits']['time_limit_minutes'] * status['total_instances']:
        print(f"\n⚠️  주의: 예상 시간이 최대 시간 제한을 초과할 수 있습니다.")
        max_time = config['limits']['time_limit_minutes'] * status['total_instances']
        print(f"   최대 시간 제한: {format_time(max_time)}")
    
    print()

if __name__ == "__main__":
    main()



