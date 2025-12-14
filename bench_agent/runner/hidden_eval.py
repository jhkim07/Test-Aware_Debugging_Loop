"""
Hidden test evaluation module.
Runs tests with TA_SPLIT=hidden to evaluate overfitting.
"""
from pathlib import Path
from typing import Optional
from .swebench_runner import run_swebench_eval, SwebenchEvalResult
from .report_parser import parse_harness_report, parse_pytest_output


def run_hidden_eval(
    dataset_name: str,
    predictions_path: Path,
    instance_id: str,
    run_id_base: str,
    cache_level: str = "instance",
    clean: bool = False,
) -> Optional[dict]:
    """
    Run hidden test evaluation.
    
    Args:
        dataset_name: SWE-bench dataset name
        predictions_path: Path to predictions.jsonl file
        instance_id: Instance ID to evaluate
        run_id_base: Base run ID (will append "-hidden")
        cache_level: Cache level for harness
        clean: Whether to clean cache
    
    Returns:
        dict with keys:
        - ok: bool indicating if all hidden tests passed
        - pass_rate: pass rate (0.0 to 1.0)
        - passed: number of passed tests
        - failed: number of failed tests
        - total: total number of tests
        - report_dir: Path to report directory
        Or None if evaluation failed to run
    """
    try:
        hidden_run_id = f"{run_id_base}-hidden"
        
        # Set environment variable for hidden split
        import os
        env_hidden = dict(os.environ)
        env_hidden['TA_SPLIT'] = 'hidden'
        
        # Run harness with hidden split
        res = run_swebench_eval(
            dataset_name=dataset_name,
            predictions_path=predictions_path,
            instance_ids=[instance_id],
            run_id=hidden_run_id,
            max_workers=1,
            cache_level=cache_level,
            clean=clean,
            env=env_hidden,
        )
        
        # Parse results - try stdout/stderr first (more reliable)
        stdout_data = parse_pytest_output(res.raw_stdout)
        stderr_data = parse_pytest_output(res.raw_stderr)
        
        # Use the one with more information
        report_data = stdout_data if stdout_data["total"] > 0 else stderr_data
        
        # If stdout/stderr parsing failed, try report files
        if report_data["total"] == 0:
            report_data = parse_harness_report(res.report_dir, instance_id, debug=False)
        
        # Final fallback: use return code
        if report_data["total"] == 0:
            report_data["ok"] = res.ok
            report_data["pass_rate"] = 1.0 if res.ok else 0.0
        
        return {
            "ok": report_data["ok"],
            "pass_rate": report_data["pass_rate"],
            "passed": report_data["passed"],
            "failed": report_data["failed"],
            "total": report_data["total"],
            "report_dir": str(res.report_dir),
            "run_id": hidden_run_id,
        }
        
    except Exception as e:
        # Return None on error (stub behavior for MVP)
        return {
            "ok": False,
            "pass_rate": 0.0,
            "passed": 0,
            "failed": 0,
            "total": 0,
            "error": str(e),
        }
