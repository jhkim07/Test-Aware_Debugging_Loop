import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class SwebenchEvalResult:
    ok: bool
    report_dir: Path
    raw_stdout: str
    raw_stderr: str

def run_swebench_eval(
    dataset_name: str,
    predictions_path: Path,
    instance_ids: list[str],
    run_id: str,
    max_workers: int = 1,
    cache_level: str = "instance",
    clean: bool = False,
    env: Optional[dict] = None,
) -> SwebenchEvalResult:
    """
    Runs SWE-bench harness evaluation for given instance IDs.

    Uses:
      python -m swebench.harness.run_evaluation --dataset_name ... --predictions_path ... --instance_ids ... --run_id ...
    citeturn0search1turn0search5
    """
    cmd = [
        "python", "-m", "swebench.harness.run_evaluation",
        "--dataset_name", dataset_name,
        "--predictions_path", str(predictions_path),
        "--instance_ids", *instance_ids,
        "--max_workers", str(max_workers),
        "--run_id", run_id,
        "--cache_level", cache_level,
        "--clean", str(clean),
    ]
    # Create intermediate files directory if it doesn't exist
    intermediate_dir = Path("tmp/intermediate_files")
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=Path.cwd())
    # Harness writes reports under ./runs/<run_id>/ by default (see swebench docs; adjust if needed)
    report_dir = Path("runs") / run_id
    ok = (p.returncode == 0)
    
    # Move test-aware-debugging.* files to intermediate_files directory
    import glob
    import shutil
    for json_file in glob.glob("test-aware-debugging.*.json"):
        try:
            src = Path(json_file)
            if src.exists():
                dst = intermediate_dir / src.name
                shutil.move(str(src), str(dst))
        except Exception:
            pass  # Ignore errors during file move
    
    # 에러 로깅 강화 (제안된 방식 적용)
    if not ok:
        # console이 있으면 사용, 없으면 sys.stderr 사용
        try:
            from rich.console import Console
            console = Console(stderr=True)
            console.print(f"[red]Harness failed with return code {p.returncode}[/red]")
            if p.stderr:
                stderr_preview = p.stderr[-1000:] if len(p.stderr) > 1000 else p.stderr
                console.print(f"[yellow]STDERR: {stderr_preview}[/yellow]")
            if p.stdout:
                stdout_preview = p.stdout[-1000:] if len(p.stdout) > 1000 else p.stdout
                # stdout에 에러 관련 메시지가 있을 때만 출력
                if any(keyword in stdout_preview for keyword in ["Warning", "Error", "Failed", "Missing"]):
                    console.print(f"[yellow]STDOUT: {stdout_preview}[/yellow]")
        except ImportError:
            # rich가 없으면 기본 출력
            import sys
            if p.stderr:
                stderr_preview = p.stderr[-1000:] if len(p.stderr) > 1000 else p.stderr
                print(f"[WARNING] Harness failed (return code: {p.returncode})", file=sys.stderr)
                print(f"[WARNING] STDERR: {stderr_preview}", file=sys.stderr)
            if p.stdout:
                stdout_preview = p.stdout[-1000:] if len(p.stdout) > 1000 else p.stdout
                if any(keyword in stdout_preview for keyword in ["Warning", "Error", "Failed", "Missing"]):
                    print(f"[WARNING] STDOUT: {stdout_preview}", file=sys.stderr)
    
    return SwebenchEvalResult(ok=ok, report_dir=report_dir, raw_stdout=p.stdout, raw_stderr=p.stderr)
