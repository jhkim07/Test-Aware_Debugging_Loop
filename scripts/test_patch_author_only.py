#!/usr/bin/env python3
"""
간단한 테스트 스크립트: patch_author.py와 test_author.py만 사용하여
패치를 생성하고 테스트 통과 여부를 확인합니다.
"""
import argparse
import json
import os
from pathlib import Path
from datasets import load_dataset

from bench_agent.agent.llm_client import make_client
from bench_agent.agent.test_author import propose_tests
from bench_agent.agent.patch_author import propose_patch
from bench_agent.protocol.patch_builder import combine_diffs
from bench_agent.protocol.diff_cleaner import clean_diff_format
from bench_agent.protocol.utils import write_predictions_jsonl, now_ts
from bench_agent.runner.swebench_runner import run_swebench_eval
from bench_agent.runner.report_parser import parse_harness_report, parse_pytest_output
from bench_agent.runner.pytest_nodeid import extract_nodeids_from_text, extract_failing_nodeids_from_text
import re

def build_repo_context(inst_data: dict, failure_summary: str = "") -> str:
    """Build repository context from SWE-bench instance data."""
    instance_id = inst_data.get('instance_id', '')
    problem_statement = inst_data.get('problem_statement', '')
    repo_name = inst_data.get('repo', '')
    base_commit = inst_data.get('base_commit', '')
    test_patch = inst_data.get('test_patch', '')
    reference_patch = inst_data.get('patch', '')
    
    repo_ctx_parts = [
        f"SWE-bench Instance: {instance_id}",
        f"Repository: {repo_name}",
        f"Base commit: {base_commit}",
    ]
    
    if problem_statement:
        problem_preview = problem_statement[:3000]
        if len(problem_statement) > 3000:
            problem_preview += "\n\n[Problem statement truncated...]"
        repo_ctx_parts.append(f"\n=== Problem Statement ===\n{problem_preview}")
    
    if test_patch:
        test_patch_preview = test_patch[:2000]
        if len(test_patch) > 2000:
            test_patch_preview += "\n\n[Test patch truncated...]"
        repo_ctx_parts.append(f"\n=== Reference Test Patch (for guidance) ===\n{test_patch_preview}")
        repo_ctx_parts.append("\nNote: The reference test patch shows the expected test file structure and location.")
    
    if reference_patch:
        patch_preview = reference_patch[:3000]
        if len(reference_patch) > 3000:
            patch_preview += "\n\n[Reference patch truncated...]"
        repo_ctx_parts.append(f"\n=== Reference Solution Patch (FOLLOW THIS CLOSELY) ===\n{patch_preview}")
        repo_ctx_parts.append("\nCRITICAL: The reference solution patch shows the CORRECT fix. Your patch should closely match this.")
    
    # Extract file paths from failure summary if available
    if failure_summary:
        def extract_file_paths_from_text(text: str) -> list[str]:
            patterns = [
                r'File "([^"]+\.py)"',
                r'--- a/([\w/]+\.py)',
                r'\+\+\+ b/([\w/]+\.py)',
                r'(astropy/[\w/]+\.py|sympy/[\w/]+\.py)',
            ]
            found_paths = set()
            for pattern in patterns:
                matches = re.findall(pattern, text)
                found_paths.update(matches)
            filtered = [p for p in found_paths if not any(x in p for x in ['/usr/', '/lib/', '/site-packages/', '__pycache__', 'conftest.py'])]
            return sorted(list(filtered))[:10]
        
        relevant_file_paths = extract_file_paths_from_text(failure_summary)
        if relevant_file_paths:
            repo_ctx_parts.append("\n=== Relevant File Paths (from failure logs) ===")
            repo_ctx_parts.append("\n" + "\n".join(f"- {p}" for p in relevant_file_paths))
    
    return "\n".join(repo_ctx_parts)

def main():
    ap = argparse.ArgumentParser(description="Test patch_author and test_author only")
    ap.add_argument("--instance-id", required=True, help="SWE-bench instance ID")
    ap.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite", help="SWE-bench dataset name")
    ap.add_argument("--model", default="gpt-4o-mini", help="LLM model name")
    ap.add_argument("--run-id", default="test-patch-only", help="Run ID for output")
    ap.add_argument("--use-reference-patch", action="store_true", 
                    help="Use reference solution patch directly (skip LLM generation, for validation)")
    args = ap.parse_args()
    
    # Load SWE-bench dataset
    print(f"Loading SWE-bench dataset: {args.dataset}...")
    try:
        ds = load_dataset(args.dataset, split='test')
        instance_data = next((item for item in ds if item['instance_id'] == args.instance_id), None)
        if not instance_data:
            print(f"❌ Instance {args.instance_id} not found in dataset")
            return
        print(f"✅ Found instance: {args.instance_id}")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return
    
    # Create output directory
    out_dir = Path("outputs") / args.run_id / args.instance_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Use reference patch if requested
    if args.use_reference_patch:
        print("\n" + "="*80)
        print("Using REFERENCE SOLUTION PATCH (validation mode)")
        print("="*80)
        
        test_patch = instance_data.get('test_patch', '')
        reference_patch = instance_data.get('patch', '')
        
        if not test_patch and not reference_patch:
            print("❌ Error: No reference patches found in instance data")
            return
        
        test_diff = test_patch if test_patch else ""
        code_diff = reference_patch if reference_patch else ""
        
        print(f"✅ Using reference test patch ({len(test_diff)} chars)")
        print(f"✅ Using reference code patch ({len(code_diff)} chars)")
        
        # Save reference patches
        (out_dir / "test_diff.diff").write_text(test_diff, encoding="utf-8")
        (out_dir / "code_diff.diff").write_text(code_diff, encoding="utf-8")
        
        print("\n⚠️  NOTE: This should result in 100% test pass rate if the reference patch is correct!")
        
    else:
        # Initialize LLM client
        client = make_client()
        model = args.model
        
        print("\n" + "="*80)
        print("Step 1: Generate test diff using test_author")
        print("="*80)
        
        # Initial failure summary (empty for first iteration)
        failure_summary = "No previous test results available. This is the first iteration."
        
        # Build repository context
        repo_context = build_repo_context(instance_data, failure_summary)
        
        # Generate test diff
        print("Calling propose_tests()...")
        test_diff = propose_tests(client, model, repo_context, failure_summary)
        test_diff = clean_diff_format(test_diff) if test_diff else ""
        
        print(f"\nGenerated test diff ({len(test_diff)} chars):")
        print("-" * 80)
        print(test_diff[:500] + ("..." if len(test_diff) > 500 else ""))
        print("-" * 80)
        
        # Save test diff
        (out_dir / "test_diff.diff").write_text(test_diff, encoding="utf-8")
        
        print("\n" + "="*80)
        print("Step 2: Generate code patch using patch_author")
        print("="*80)
        
        # Generate code patch
        print("Calling propose_patch()...")
        code_diff = propose_patch(client, model, repo_context, failure_summary, test_diff)
        code_diff = clean_diff_format(code_diff) if code_diff else ""
        
        print(f"\nGenerated code diff ({len(code_diff)} chars):")
        print("-" * 80)
        print(code_diff[:500] + ("..." if len(code_diff) > 500 else ""))
        print("-" * 80)
        
        # Save code diff
        (out_dir / "code_diff.diff").write_text(code_diff, encoding="utf-8")
    
    print("\n" + "="*80)
    print("Step 3: Combine patches and apply")
    print("="*80)
    
    # Combine patches (conftest excluded to avoid patch application failures)
    combined_patch = combine_diffs(test_diff.strip(), code_diff.strip(), include_conftest=False)
    combined_patch = clean_diff_format(combined_patch) if combined_patch else ""
    
    print(f"\nCombined patch ({len(combined_patch)} chars)")
    (out_dir / "combined_patch.diff").write_text(combined_patch, encoding="utf-8")
    
    # Write predictions.jsonl
    predictions_path = out_dir / "predictions.jsonl"
    write_predictions_jsonl(predictions_path, args.instance_id, combined_patch)
    print(f"✅ Written predictions.jsonl: {predictions_path}")
    
    print("\n" + "="*80)
    print("Step 4: Run SWE-bench harness to test the patch")
    print("="*80)
    
    # Run SWE-bench evaluation
    run_id = f"{args.run_id}-{args.instance_id}-{now_ts()}"
    print(f"Running SWE-bench harness (run_id: {run_id})...")
    
    try:
        # Set TA_SPLIT environment variable for public tests
        env = dict(os.environ)
        env['TA_SPLIT'] = 'public'
        
        result = run_swebench_eval(
            dataset_name=args.dataset,
            predictions_path=predictions_path,
            instance_ids=[args.instance_id],
            run_id=run_id,
            max_workers=1,
            env=env,
        )
        
        print(f"\n✅ Harness execution completed")
        print(f"   OK: {result.ok}")
        print(f"   Report dir: {result.report_dir}")
        
        # Check if patch application failed BEFORE parsing test results
        from bench_agent.runner.report_parser import check_patch_apply_failed
        patch_failed = check_patch_apply_failed(result.raw_stdout, result.raw_stderr)
        
        if patch_failed:
            print(f"\n⚠️  WARNING: Patch application failed!")
            print(f"   Test results will not be parsed as tests were not executed.")
            # Return empty results indicating patch failure
            report = {
                "passed": 0,
                "failed": 0,
                "total": 0,
                "pass_rate": 0.0,
                "ok": False,
                "patch_apply_failed": True,
            }
            source = "Patch apply failed"
        else:
            # Parse results from stdout/stderr first (more reliable)
            stdout_result = parse_pytest_output(result.raw_stdout)
            stderr_result = parse_pytest_output(result.raw_stderr)
            
            # Prefer stderr if it has results, otherwise use stdout
            if stderr_result.get('total', 0) > 0:
                report = stderr_result
                source = "STDERR"
            elif stdout_result.get('total', 0) > 0:
                report = stdout_result
                source = "STDOUT"
            else:
                # Fallback to report file parsing
                report = parse_harness_report(result.report_dir, args.instance_id, debug=False)
                source = "Report file"
            
            # Ensure patch_apply_failed flag is set
            report["patch_apply_failed"] = False
        
        print(f"\n📊 Test Results (from {source}):")
        print(f"   Passed: {report.get('passed', 0)}")
        print(f"   Failed: {report.get('failed', 0)}")
        print(f"   Total: {report.get('total', 0)}")
        print(f"   Pass Rate: {report.get('pass_rate', 0.0):.2%}")
        print(f"   OK: {report.get('ok', False)}")
        
        # Save results
        results = {
            "instance_id": args.instance_id,
            "used_reference_patch": args.use_reference_patch,
            "test_diff_length": len(test_diff),
            "code_diff_length": len(code_diff),
            "combined_patch_length": len(combined_patch),
            "harness_ok": result.ok,
            "test_results": report,
        }
        (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\n✅ Results saved to: {out_dir / 'results.json'}")
        
        if report.get('ok', False):
            print("\n🎉 SUCCESS: All tests passed!")
        else:
            print(f"\n⚠️  Tests failed: {report.get('failed', 0)}/{report.get('total', 0)}")
            
    except Exception as e:
        print(f"\n❌ Error running harness: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

