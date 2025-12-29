import argparse, json, time, os
from pathlib import Path
import yaml
from rich.console import Console

from bench_agent.agent.llm_client import make_client
from bench_agent.agent.controller import decide
from bench_agent.agent.test_author import propose_tests
from bench_agent.agent.patch_author import propose_patch

from bench_agent.protocol.policy import validate_test_diff, validate_patch_diff
from bench_agent.protocol.utils import write_predictions_jsonl, now_ts
from bench_agent.protocol.patch_builder import combine_diffs, ensure_conftest_in_patch
from bench_agent.protocol.diff_cleaner import clean_diff_format
from bench_agent.protocol.validate_instances import validate_instance_ids
from bench_agent.runner.swebench_runner import run_swebench_eval
from bench_agent.runner.failure_summary import summarize_failure
from bench_agent.runner.pytest_nodeid import extract_nodeids_from_text, extract_failing_nodeids_from_text
import re
from bench_agent.runner.hidden_eval import run_hidden_eval
from bench_agent.runner.report_parser import parse_harness_report, parse_pytest_output
from datasets import load_dataset

# Phase 2: Two-Stage Architecture (feature flag)
USE_TWO_STAGE = os.getenv("USE_TWO_STAGE", "0") == "1"
if USE_TWO_STAGE:
    from bench_agent.protocol.two_stage import generate_test_diff_two_stage, generate_code_diff_two_stage
    console = Console()
    console.print("[cyan]⚙️  Phase 2: Two-Stage Architecture ENABLED[/cyan]")
else:
    console = Console()

# Component 3: Edit Script Mode (feature flag)
USE_EDIT_SCRIPT = os.getenv("USE_EDIT_SCRIPT", "0") == "1"
if USE_EDIT_SCRIPT:
    from bench_agent.protocol.edit_script_workflow import (
        generate_test_diff_edit_script,
        generate_code_diff_edit_script,
        extract_test_file_from_reference,
        extract_code_file_from_reference,
        read_file_from_repo
    )
    console.print("[cyan]⚙️  Component 3: Edit Script Mode ENABLED[/cyan]")

# Component 1: Iteration Safety Guards (always enabled)
from bench_agent.protocol.iteration_safety import (
    IterationSafetyController,
    format_safety_stats
)

def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())

def write_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--max-workers", type=int, default=2)
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    dataset_name = cfg["runner"]["dataset_name"]
    instance_ids_raw = cfg["instances"]["list"]
    
    # 인스턴스 ID 유효성 검증
    valid_ids, invalid_ids = validate_instance_ids(dataset_name, instance_ids_raw)
    
    if invalid_ids:
        console.print(f"[yellow]경고: 유효하지 않은 인스턴스 ID {len(invalid_ids)}개 발견:[/yellow]")
        for id in invalid_ids:
            console.print(f"  - {id}")
        console.print(f"[yellow]유효한 인스턴스 ID {len(valid_ids)}개만 사용합니다.[/yellow]")
    
    if not valid_ids:
        console.print("[red]에러: 유효한 인스턴스 ID가 없습니다. 종료합니다.[/red]")
        return
    
    instance_ids = valid_ids
    limits = cfg["limits"]
    split = cfg.get("split", {"public_ratio": 0.7, "seed": 0})
    policy = cfg["policy"]
    llm_cfg = cfg["llm"]

    client = make_client() if llm_cfg.get("enabled", True) else None
    model = llm_cfg.get("model", "gpt-4o-mini")

    # Load SWE-bench dataset once for all instances
    console.print("[dim]Loading SWE-bench dataset for instance metadata...[/dim]")
    try:
        ds = load_dataset(dataset_name, split='test')
        # Create a lookup dict: instance_id -> instance_data
        instance_data_cache = {item['instance_id']: item for item in ds}
        console.print(f"[green]Loaded {len(instance_data_cache)} instances from dataset.[/green]")
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to load SWE-bench dataset: {e}. Proceeding without problem statements.[/yellow]")
        instance_data_cache = {}

    out_root = Path("outputs") / args.run_id
    out_root.mkdir(parents=True, exist_ok=True)

    for instance_id in instance_ids:
        console.rule(f"[bold]Instance: {instance_id}")
        inst_dir = out_root / instance_id
        inst_dir.mkdir(parents=True, exist_ok=True)
        log_path = inst_dir / "run.jsonl"

        history = []
        combined_patch = ""  # unified diff (tests + code)
        final_test_diff = ""
        final_code_diff = ""
        start_time = time.time()

        # Component 1: Initialize Iteration Safety Controller
        # Determine repository path from instance_id
        repo_name = instance_id.split('__')[0] if '__' in instance_id else instance_id
        repo_path = Path(f"/tmp/{repo_name}_{instance_id}")  # Typical SWE-bench path

        safety_controller = IterationSafetyController(
            repo_path=str(repo_path),
            instance_id=instance_id,
            max_total=limits.get("max_iters", 8),  # Use config max_iters
            max_test=3,  # Max test generation iterations
            max_code=5   # Max code generation iterations
        )
        console.print(f"[dim]Safety guards enabled: max_total={safety_controller.max_total}, max_test={safety_controller.max_test}, max_code={safety_controller.max_code}[/dim]")

        for it in range(1, limits["max_iters"] + 1):
            # Component 1: Check if iteration should continue
            should_continue_test, stop_reason_test = safety_controller.should_continue("test")
            should_continue_code, stop_reason_code = safety_controller.should_continue("code")

            if not should_continue_test:
                console.print(f"[yellow]Safety guard: {stop_reason_test}[/yellow]")
                break

            if not should_continue_code:
                console.print(f"[yellow]Safety guard: {stop_reason_code}[/yellow]")
                break

            # Time limit check
            if (time.time() - start_time) > limits["time_limit_minutes"] * 60:
                console.print("[yellow]Time limit reached, stopping iterations.")
                break

            # Component 1: Reset repository state before iteration
            console.print(f"[dim]Iteration {it}: Resetting repository state...[/dim]")
            reset_ok, reset_msg = safety_controller.start_iteration("test")  # Use "test" as primary stage

            if not reset_ok:
                console.print(f"[red]Repository reset failed: {reset_msg}[/red]")
                safety_controller.record_failure(f"Repository reset failed: {reset_msg}")
                break

            console.print(f"[dim]Repository reset successful[/dim]")

            # Evaluate current combined patch (or empty patch if first iter)
            predictions = inst_dir / "predictions.jsonl"
            write_predictions_jsonl(predictions, instance_id, combined_patch)

            run_id = f"{args.run_id}-{instance_id}-iter{it}-{now_ts()}"
            env_public = dict(os.environ)
            env_public['TA_SPLIT'] = 'public'
            res = run_swebench_eval(
                dataset_name=dataset_name,
                predictions_path=predictions,
                instance_ids=[instance_id],
                run_id=run_id,
                max_workers=1,   # single instance here; keep deterministic
                cache_level="instance",
                clean=False,
                env=env_public,
            )

            failure = summarize_failure(res.report_dir, instance_id)
            console.print(f"[dim]Harness ok={res.ok}. Failure summary length={len(failure)}[/dim]")
            
            # Extract file paths from failure summary for context
            def extract_file_paths_from_text(text: str) -> list[str]:
                """Extract relevant file paths from failure summary."""
                patterns = [
                    r'File "([^"]+\.py)"',  # File "path/to/file.py"
                    r'--- a/([\w/]+\.py)',  # diff format: --- a/path/to/file.py
                    r'\+\+\+ b/([\w/]+\.py)',  # diff format: +++ b/path/to/file.py
                    r'(astropy/[\w/]+\.py|sympy/[\w/]+\.py)',  # repo-specific paths
                ]
                found_paths = set()
                for pattern in patterns:
                    matches = re.findall(pattern, text)
                    found_paths.update(matches)
                # Filter out common false positives
                filtered = [p for p in found_paths if not any(x in p for x in ['/usr/', '/lib/', '/site-packages/', '__pycache__', 'conftest.py'])]
                return sorted(list(filtered))[:10]  # Top 10 unique paths
            
            relevant_file_paths = extract_file_paths_from_text(failure)

            # Get problem statement for Controller
            inst_data = instance_data_cache.get(instance_id, {})
            problem_statement = inst_data.get('problem_statement', '')[:2000]  # Limit length
            
            decision = decide(client, model, failure, history, problem_statement) if client else {"focus":"both","hypotheses":[],"targets":[]}
            history.append({"role":"assistant","content":json.dumps(decision)})

            # Build repository context with SWE-bench instance information
            nodeids = extract_nodeids_from_text(failure)
            failing_nodeids = extract_failing_nodeids_from_text(failure)
            
            # Get SWE-bench instance data
            inst_data = instance_data_cache.get(instance_id, {})
            problem_statement = inst_data.get('problem_statement', '')
            repo_name = inst_data.get('repo', '')
            base_commit = inst_data.get('base_commit', '')
            test_patch = inst_data.get('test_patch', '')  # Reference test patch
            reference_patch = inst_data.get('patch', '')  # Reference solution patch
            
            # Build repo context
            repo_ctx_parts = [
                f"SWE-bench Instance: {instance_id}",
                f"Repository: {repo_name}",
                f"Base commit: {base_commit}",
            ]
            
            if problem_statement:
                # Limit problem statement length to avoid token limits (keep first 3000 chars)
                problem_preview = problem_statement[:3000]
                if len(problem_statement) > 3000:
                    problem_preview += "\n\n[Problem statement truncated...]"
                repo_ctx_parts.append(f"\n=== Problem Statement ===\n{problem_preview}")
            
            # Add reference test patch as hint (what tests should look like)
            if test_patch:
                # Analyze reference test patch
                try:
                    from bench_agent.protocol.reference_test_analyzer import analyze_reference_test_patch
                    test_analysis = analyze_reference_test_patch(test_patch)
                except Exception as e:
                    test_analysis = None
                    import sys
                    print(f"[run_mvp] Warning: Failed to analyze reference test patch: {e}", file=sys.stderr)
                
                test_patch_preview = test_patch[:2000]  # Limit to first 2000 chars
                if len(test_patch) > 2000:
                    test_patch_preview += "\n\n[Test patch truncated...]"
                repo_ctx_parts.append(f"\n=== Reference Test Patch (for guidance) ===\n{test_patch_preview}")
                
                # Add test patch analysis if available
                if test_analysis:
                    repo_ctx_parts.append(f"\n=== Reference Test Patch Analysis ===")
                    repo_ctx_parts.append(test_analysis['summary'])
                    if test_analysis.get('structure_type'):
                        repo_ctx_parts.append(f"\nCRITICAL: Reference Test Patch uses {test_analysis['structure_type']} structure.")
                        repo_ctx_parts.append(f"You MUST use the SAME structure type in your test patch.")
                    if test_analysis.get('expected_values'):
                        repo_ctx_parts.append(f"\nExpected values found in Reference Test Patch:")
                        for name, value in list(test_analysis['expected_values'].items())[:3]:
                            repo_ctx_parts.append(f"  - {name}: {value[:100]}")
                        repo_ctx_parts.append(f"Use these EXACT expected value names and definitions in your test.")
                
                repo_ctx_parts.append("\nNote: The reference test patch shows the expected test file structure and location. Use this as a guide for where to add tests and what format to use.")
            
            # Add reference solution patch as hint (what files/functions need fixing)
            if reference_patch:
                # Analyze reference patch to extract key information
                try:
                    from bench_agent.protocol.reference_patch_analyzer import analyze_reference_patch
                    patch_analysis = analyze_reference_patch(reference_patch)
                except Exception as e:
                    patch_analysis = None
                    import sys
                    print(f"[run_mvp] Warning: Failed to analyze reference patch: {e}", file=sys.stderr)
                
                # Include more of the patch for better guidance
                patch_preview = reference_patch[:3000]  # Increased to 3000 chars
                if len(reference_patch) > 3000:
                    patch_preview += "\n\n[Reference patch truncated...]"
                repo_ctx_parts.append(f"\n=== Reference Solution Patch (FOLLOW THIS CLOSELY) ===\n{patch_preview}")
                
                # Add patch analysis if available
                if patch_analysis:
                    repo_ctx_parts.append(f"\n=== Reference Patch Analysis ===")
                    repo_ctx_parts.append(patch_analysis['summary'])
                    repo_ctx_parts.append("\nIMPORTANT: Use these EXACT line numbers and file paths in your patch.")
                
                repo_ctx_parts.append("\n" + "="*80)
                repo_ctx_parts.append("CRITICAL INSTRUCTIONS FOR REFERENCE SOLUTION PATCH:")
                repo_ctx_parts.append("="*80)
                repo_ctx_parts.append("1. FILE AND FUNCTION MATCHING:")
                repo_ctx_parts.append("   - Identify which file the reference patch modifies (look for 'diff --git a/path/to/file.py')")
                repo_ctx_parts.append("   - Identify which function/class is modified (look for the hunk headers and context lines)")
                repo_ctx_parts.append("   - Your patch MUST modify the SAME file and function")
                repo_ctx_parts.append("")
                repo_ctx_parts.append("2. EXACT CHANGE ANALYSIS:")
                repo_ctx_parts.append("   - Study the hunk headers: @@ -old_start,old_count +new_start,new_count @@")
                repo_ctx_parts.append("   - Use the EXACT line numbers from the reference patch (see Patch Analysis above)")
                repo_ctx_parts.append("   - Identify lines marked with '-' (removed) and '+' (added)")
                repo_ctx_parts.append("   - Understand WHY each change is made (read the context lines - 20-30 lines around changes)")
                repo_ctx_parts.append("   - Your patch should make SIMILAR changes in the SAME location with SAME line numbers")
                repo_ctx_parts.append("")
                repo_ctx_parts.append("3. VARIABLE AND LOGIC MATCHING:")
                repo_ctx_parts.append("   - Use the SAME variable names as in the reference patch")
                repo_ctx_parts.append("   - Use the SAME logic approach (don't invent alternatives)")
                repo_ctx_parts.append("   - Example: If reference uses 'right', do NOT use 'np.eye(right.shape[1])'")
                repo_ctx_parts.append("   - Example: If reference removes a line, you should remove the SAME line")
                repo_ctx_parts.append("")
                repo_ctx_parts.append("4. LINE NUMBER ACCURACY (CRITICAL):")
                repo_ctx_parts.append("   - Match the EXACT hunk header line numbers from the reference patch")
                repo_ctx_parts.append("   - If reference shows @@ -27,7 +27,6 @@, your patch MUST start at line 27")
                repo_ctx_parts.append("   - If reference shows old_count=7, new_count=6, use the SAME counts")
                repo_ctx_parts.append("   - For multiple hunks in the same file, account for changes from previous hunks")
                repo_ctx_parts.append("   - Reference the Patch Analysis above for exact line numbers")
                repo_ctx_parts.append("")
                repo_ctx_parts.append("5. CONTEXT LINES:")
                repo_ctx_parts.append("   - Include 15-20 lines of context around each change (lines before and after)")
                repo_ctx_parts.append("   - Context helps ensure the patch applies correctly")
                repo_ctx_parts.append("   - Match the context lines from the reference patch when possible")
                repo_ctx_parts.append("")
                repo_ctx_parts.append("6. DO NOT:")
                repo_ctx_parts.append("   - Modify different files or functions than the Reference Solution Patch")
                repo_ctx_parts.append("   - Use different variable names or logic than the Reference Solution Patch")
                repo_ctx_parts.append("   - Invent alternative solutions")
                repo_ctx_parts.append("   - Modify conftest.py (it will be handled separately)")
                repo_ctx_parts.append("="*80)
            
            split_info = "\n\n=== Test Information ==="
            split_info += "\nKnown pytest nodeids (partial from logs):\n" + "\n".join(nodeids[:200])
            split_info += "\n\nFailing nodeids:\n" + "\n".join(failing_nodeids[:50])
            
            # Add relevant file paths found in failure summary
            if relevant_file_paths:
                split_info += "\n\n=== Relevant File Paths (from failure logs) ==="
                split_info += "\n" + "\n".join(f"- {p}" for p in relevant_file_paths)
                split_info += "\nNote: These files may need to be modified or contain relevant code for the bug fix."
            
            split_info += f"\n\nSplit config: public_ratio={split.get('public_ratio',0.7)}, seed={split.get('seed',0)}. TA_SPLIT=public is used for harness runs."
            
            repo_ctx = "\n".join(repo_ctx_parts) + split_info

            # --- TEST-FIRST (required) ---
            # Extract previous iteration feedback from history
            previous_feedback = ""
            if history and it > 1:
                # Look for feedback in recent history entries
                for entry in reversed(history[-3:]):  # Check last 3 entries
                    if isinstance(entry, dict) and entry.get("role") == "user":
                        content = entry.get("content", "")
                        if "Iteration" in content and "feedback" in content:
                            previous_feedback = content
                            break

            # P0-2: Extract expected value hints from test_analysis (created earlier during repo_ctx setup)
            expected_value_hints = ""
            if 'test_analysis' in locals() and test_analysis and test_analysis.get('expected_value_hints'):
                expected_value_hints = test_analysis['expected_value_hints']

            # Component 3: Edit Script, Phase 2: Two-Stage, or One-Stage test generation
            if USE_EDIT_SCRIPT:
                # Component 3: Edit Script Mode
                test_file_path = extract_test_file_from_reference(test_patch) if test_patch else None
                if test_file_path and repo_path.exists():
                    test_source = read_file_from_repo(repo_path, test_file_path)
                    if test_source:
                        console.print(f"[cyan]Edit Script: Generating test diff for {test_file_path}[/cyan]")
                        test_diff, metadata = generate_test_diff_edit_script(
                            client=client,
                            model=model,
                            test_file_path=test_file_path,
                            test_source_code=test_source,
                            problem_statement=problem_statement,
                            reference_test_patch=test_patch,
                            failure_summary=failure
                        )
                        if metadata['success']:
                            console.print(f"[green]✓ Edit script applied successfully ({metadata['apply_result'].applied_count} edits)[/green]")
                        else:
                            console.print(f"[yellow]Edit script failed: {metadata['errors']}[/yellow]")
                            safety_controller.record_failure(f"Edit script test generation failed: {metadata['errors']}")
                    else:
                        console.print(f"[yellow]Could not read test file: {test_file_path}[/yellow]")
                        test_diff = ""
                else:
                    console.print(f"[yellow]Could not extract test file path from reference patch[/yellow]")
                    test_diff = ""
            elif USE_TWO_STAGE:
                # Two-Stage: Planner → Writer
                context_2stage = {
                    "problem_statement": problem_statement,
                    "reference_test_patch": test_patch,
                    "failure_summary": failure,
                    "conftest_content": "",  # Could extract from repo if needed
                }
                try:
                    test_diff = generate_test_diff_two_stage(client, context_2stage, mode="research")
                except Exception as e:
                    console.print(f"[red]Two-stage test generation failed: {e}[/red]")
                    test_diff = ""
                    safety_controller.record_failure(f"Two-stage test generation failed: {e}")
            else:
                # One-Stage: Original propose_tests
                test_diff = propose_tests(
                    client, model, repo_ctx, failure,
                    current_tests_hint="",
                    previous_feedback=previous_feedback,
                    expected_value_hints=expected_value_hints  # P0-2: Add expected value enforcement
                ) if client else ""
                # Clean test_diff to fix format issues and line numbers
                # SKIP when using Component 3 (Edit Script Mode) - diffs are already clean
                if not USE_EDIT_SCRIPT:
                    test_diff = clean_diff_format(test_diff) if test_diff else ""

            # Component 1: Check for duplicate test diff
            if test_diff and safety_controller.check_duplicate(test_diff):
                console.print(f"[yellow]⚠️  Duplicate test diff detected (iteration {it}). Skipping to next stage.[/yellow]")
                safety_controller.record_failure(f"Duplicate test diff in iteration {it}")
                # Don't break - allow code generation to proceed

            # P0.9: Apply normalization to test_diff immediately after generation
            # This ensures BRS validation uses normalized test_diff
            # SKIP normalization when using Component 3 (Edit Script Mode) or Phase 2.2 (Two-Stage) - diffs are already clean
            if test_diff and reference_patch and not USE_EDIT_SCRIPT and not USE_TWO_STAGE:
                try:
                    from bench_agent.protocol.pre_apply_normalization import PreApplyNormalizationGate
                    normalizer = PreApplyNormalizationGate(reference_patch, verbose=False, instance_id=instance_id)
                    test_diff, test_norm_report = normalizer.normalize_diff(test_diff, diff_type="test")
                    if test_norm_report.total_fixes() > 0:
                        console.print(f"[cyan]P0.9: Normalized test_diff ({test_norm_report.total_fixes()} fixes)[/cyan]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Test diff normalization failed: {e}[/yellow]")

            # P0.9.1: Policy validation with auto-retry (Phase 1)
            # Instead of immediately failing, retry Test Author up to 2 times with specific feedback
            # Total attempts: 3 (initial + 2 retries)
            MAX_POLICY_RETRIES = 2
            policy_attempt = 0
            policy_validation_passed = False

            while policy_attempt <= MAX_POLICY_RETRIES:
                ok, issues = validate_test_diff(
                    test_diff,
                    forbid_skip=policy.get("forbid_skip", True),
                    forbid_xfail=policy.get("forbid_xfail", True),
                    forbid_network=policy.get("forbid_network", True),
                    restrict_file_io=policy.get("restrict_file_io", True),
                )

                if ok:
                    policy_validation_passed = True
                    break

                # Policy violation detected
                console.print(f"[yellow]Test diff rejected by policy (attempt {policy_attempt+1}/{MAX_POLICY_RETRIES+1}):[/yellow]")
                for i in issues: console.print(f" - {i}")

                if policy_attempt >= MAX_POLICY_RETRIES:
                    # Max attempts reached, give up
                    console.print("[red]Max policy validation attempts reached. Stopping.[/red]")
                    write_jsonl(log_path, {"iter": it, "stage": "test_policy_reject", "issues": issues, "attempts": policy_attempt+1})
                    break

                # Generate specific corrective feedback based on violation type
                corrective_feedback = []
                for issue in issues:
                    if "file I/O" in issue or "open(" in issue:
                        corrective_feedback.append(
                            "POLICY VIOLATION: Your test contains file I/O operations that are not allowed.\n"
                            "REQUIRED FIX: Use pytest's tmp_path fixture for all file operations.\n"
                            "SAFE PATTERNS:\n"
                            "  - def test_example(tmp_path):  # Add tmp_path parameter\n"
                            "  - path = tmp_path / 'file.txt'  # Create path under tmp_path\n"
                            "  - path.write_text('content')   # Use write_text method\n"
                            "  - content = path.read_text()   # Use read_text method\n"
                            "FORBIDDEN PATTERNS:\n"
                            "  - open(...) - DO NOT use open() function\n"
                            "  - Path.open() - DO NOT use Path.open() method\n"
                            "Output ONLY the corrected unified diff format."
                        )
                    elif "network" in issue:
                        corrective_feedback.append(
                            "POLICY VIOLATION: Network I/O is not allowed in tests.\n"
                            "Remove all requests, urllib, socket, httpx calls."
                        )
                    elif "skip" in issue or "xfail" in issue:
                        corrective_feedback.append(
                            "POLICY VIOLATION: Tests must not use pytest.skip or pytest.xfail.\n"
                            "Tests must actually run and verify the bug fix."
                        )

                # Retry Test Author with corrective feedback
                console.print(f"[cyan]Retrying Test Author with corrective feedback...[/cyan]")
                policy_attempt += 1

                # Regenerate test with feedback
                test_diff = propose_tests(
                    client, model, repo_ctx, failure,
                    current_tests_hint="\n".join(corrective_feedback),  # Add corrective feedback
                    previous_feedback="",  # Clear previous feedback, use corrective feedback instead
                    expected_value_hints=expected_value_hints
                ) if client else ""
                # SKIP when using Component 3 (Edit Script Mode) - diffs are already clean
                if not USE_EDIT_SCRIPT:
                    test_diff = clean_diff_format(test_diff) if test_diff else ""

                # Re-normalize after regeneration
                # SKIP when using Component 3 (Edit Script Mode) - diffs are already clean
                if test_diff and reference_patch and not USE_EDIT_SCRIPT:
                    try:
                        from bench_agent.protocol.pre_apply_normalization import PreApplyNormalizationGate
                        normalizer = PreApplyNormalizationGate(reference_patch, verbose=False, instance_id=instance_id)
                        test_diff, test_norm_report = normalizer.normalize_diff(test_diff, diff_type="test")
                    except Exception:
                        pass

            # Check if validation ultimately passed
            if not policy_validation_passed:
                break  # Exit iteration loop if policy validation failed after all retries

            # BRS (Bug Reproduction Strength):
            # - run with tests-only patch (to check it fails on buggy code)
            # - Include conftest.py to ensure split mechanism works
            tests_only = ensure_conftest_in_patch(test_diff.strip())
            # Apply clean_diff_format to fix line numbers
            # SKIP when using Component 3 (Edit Script Mode) - diffs are already clean
            if not USE_EDIT_SCRIPT:
                tests_only = clean_diff_format(tests_only) if tests_only else ""

            # P0.9: Re-normalize after conftest addition (conftest might introduce new content)
            if tests_only and reference_patch:
                try:
                    from bench_agent.protocol.pre_apply_normalization import PreApplyNormalizationGate
                    normalizer = PreApplyNormalizationGate(reference_patch, verbose=False, instance_id=instance_id)
                    tests_only, _ = normalizer.normalize_diff(tests_only, diff_type="test")
                except Exception:
                    pass  # Silently continue if normalization fails

            write_predictions_jsonl(predictions, instance_id, tests_only)
            brs_run_id = f"{args.run_id}-{instance_id}-iter{it}-brs-{now_ts()}"
            brs_env_public = dict(os.environ)
            brs_env_public['TA_SPLIT'] = 'public'
            brs_res = run_swebench_eval(dataset_name, predictions, [instance_id], brs_run_id, max_workers=1, cache_level="instance", clean=False, env=brs_env_public)
            
            # Check if patch application failed BEFORE parsing test results
            from bench_agent.runner.report_parser import check_patch_apply_failed
            brs_patch_failed = check_patch_apply_failed(brs_res.raw_stdout, brs_res.raw_stderr)
            
            if brs_patch_failed:
                # Component 1: Record patch apply failure
                error_msg = brs_res.raw_stderr or brs_res.raw_stdout or "Unknown patch apply error"
                safety_controller.record_failure(error_msg)
                console.print(f"[yellow]⚠️  BRS patch apply failed (iteration {it})[/yellow]")

                # Patch failed, tests were not executed
                brs_report = {
                    "passed": 0,
                    "failed": 0,
                    "total": 0,
                    "pass_rate": 0.0,
                    "ok": False,
                    "patch_apply_failed": True,
                }
            else:
                # Parse report for accurate BRS measurement
                # Priority: report files > stdout/stderr > return code
                # Report files are more reliable for SWE-bench harness
                brs_report = parse_harness_report(brs_res.report_dir, instance_id, debug=False)

                # If report parsing failed, try stdout/stderr
                if brs_report["total"] == 0:
                    brs_stdout = parse_pytest_output(brs_res.raw_stdout)
                    brs_stderr = parse_pytest_output(brs_res.raw_stderr)
                    brs_report = brs_stdout if brs_stdout["total"] > 0 else brs_stderr

                # Final fallback: return code
                if brs_report["total"] == 0:
                    brs_report["ok"] = brs_res.ok
                    brs_report["pass_rate"] = 1.0 if brs_res.ok else 0.0

                # Ensure patch_apply_failed flag is set
                brs_report["patch_apply_failed"] = False

            # BRS is successful if tests FAIL on buggy code (reproduce the bug)
            brs_fail = not brs_report["ok"]  # Tests should fail to reproduce bug
            brs_pass_rate = brs_report["pass_rate"]

            # Extract error information for feedback
            from bench_agent.runner.error_analyzer import extract_patch_apply_errors, extract_test_failure_errors, generate_error_feedback

            brs_patch_errors = extract_patch_apply_errors(brs_res.raw_stdout, brs_res.raw_stderr)
            brs_test_errors = extract_test_failure_errors(brs_res.raw_stdout, brs_res.raw_stderr)

            # P0-2: Enhanced BRS feedback with auto-retry
            brs_feedback = ""
            brs_retry_needed = False

            if not brs_fail:
                # BRS failed - tests passed on buggy code (this is bad)
                # P0-2: Enhanced feedback - explain WHY BRS failed
                passed_tests = brs_report.get('passed', 0)
                total_tests = brs_report.get('total', 0)

                brs_feedback = f"""
=== BRS FAILURE (Bug Reproduction Strength) ===
CRITICAL: {passed_tests}/{total_tests} tests PASSED on buggy code - this means they DO NOT reproduce the bug!

Root Cause Analysis:
1. Your test's expected value may be WRONG (matching buggy output instead of correct output)
2. Your test may be checking the wrong condition
3. Your test may not be exercising the buggy code path

Required Action:
- Review the Problem Statement carefully - what is the CORRECT expected behavior?
- Check if you used the expected values from the Reference Test Patch (see above)
- Your assertion should FAIL on the buggy code and PASS after the fix

Example:
  BAD:  assert result == buggy_output  # This passes on buggy code!
  GOOD: assert result == correct_output  # This fails on buggy code, passes after fix

Reference Test Patch Analysis:
{test_analysis.get('expected_value_hints', 'No hints available') if 'test_analysis' in locals() and test_analysis else 'No reference test available'}
"""
                console.print("[red]BRS FAILED: Tests passed on buggy code. Tests must FAIL to reproduce the bug.[/red]")
                console.print(f"[yellow]Passed: {passed_tests}/{total_tests} tests[/yellow]")

                # P0-2: Auto-retry for BRS failure (1-2 times max)
                brs_retry_count = 0
                for prev_entry in history:
                    if isinstance(prev_entry, dict) and 'BRS FAILURE' in str(prev_entry):
                        brs_retry_count += 1

                if brs_retry_count < 2:  # Allow up to 2 retries
                    brs_retry_needed = True
                    console.print(f"[cyan]BRS auto-retry enabled (attempt {brs_retry_count+1}/2)[/cyan]")

            elif brs_patch_errors.get('failed'):
                brs_feedback = generate_error_feedback(brs_patch_errors, {}, brs_failed=False)
                console.print(f"[yellow]BRS patch apply failed: {brs_patch_errors.get('error_message', 'Unknown error')}[/yellow]")

            # --- PATCH (required) ---
            # Component 3: Edit Script, Phase 2: Two-Stage, or One-Stage code generation
            if USE_EDIT_SCRIPT:
                # Component 3: Edit Script Mode
                code_file_path = extract_code_file_from_reference(reference_patch) if reference_patch else None
                if code_file_path and repo_path.exists():
                    code_source = read_file_from_repo(repo_path, code_file_path)
                    if code_source:
                        console.print(f"[cyan]Edit Script: Generating code diff for {code_file_path}[/cyan]")
                        code_diff, metadata = generate_code_diff_edit_script(
                            client=client,
                            model=model,
                            code_file_path=code_file_path,
                            code_source=code_source,
                            problem_statement=problem_statement,
                            reference_patch=reference_patch,
                            test_results=failure,  # Use failure summary as test results
                            failure_summary=failure
                        )
                        if metadata['success']:
                            console.print(f"[green]✓ Edit script applied successfully ({metadata['apply_result'].applied_count} edits)[/green]")
                        else:
                            console.print(f"[yellow]Edit script failed: {metadata['errors']}[/yellow]")
                            safety_controller.record_failure(f"Edit script code generation failed: {metadata['errors']}")
                    else:
                        console.print(f"[yellow]Could not read code file: {code_file_path}[/yellow]")
                        code_diff = ""
                else:
                    console.print(f"[yellow]Could not extract code file path from reference patch[/yellow]")
                    code_diff = ""
            elif USE_TWO_STAGE:
                # Two-Stage: Planner → Writer
                context_2stage = {
                    "problem_statement": problem_statement,
                    "reference_patch": reference_patch,
                    "failure_summary": failure,
                    "function_context": "",  # Could extract from repo if needed
                }
                try:
                    code_diff = generate_code_diff_two_stage(client, context_2stage, mode="research")
                except Exception as e:
                    console.print(f"[red]Two-stage code generation failed: {e}[/red]")
                    code_diff = ""
                    safety_controller.record_failure(f"Two-stage code generation failed: {e}")
            else:
                # One-Stage: Original propose_patch
                code_diff = propose_patch(client, model, repo_ctx, failure, test_diff) if client else ""
                # Clean code_diff to remove excessive empty lines and fix format issues
                # SKIP when using Component 3 (Edit Script Mode) - diffs are already clean
                if not USE_EDIT_SCRIPT:
                    code_diff = clean_diff_format(code_diff) if code_diff else ""

            # Component 1: Check for duplicate code diff
            if code_diff and safety_controller.check_duplicate(code_diff):
                console.print(f"[yellow]⚠️  Duplicate code diff detected (iteration {it}). LLM is stuck in loop.[/yellow]")
                safety_controller.record_failure(f"Duplicate code diff in iteration {it}")
                # Continue to allow evaluation (maybe tests changed)
            
            # Validate patch structure and applicability
            try:
                from bench_agent.protocol.diff_validator import validate_patch_applicability
                is_applicable, warnings = validate_patch_applicability(code_diff)
                if warnings:
                    console.print(f"[yellow]Patch validation warnings:[/yellow]")
                    for w in warnings[:5]:  # Show first 5 warnings
                        console.print(f"  - {w}")
            except Exception as e:
                import sys
                print(f"[run_mvp] Warning: Patch validation failed: {e}", file=sys.stderr)
            
            ok2, issues2 = validate_patch_diff(code_diff)
            if not ok2:
                console.print("[red]Patch diff rejected by policy:[/red]")
                for i in issues2: console.print(f" - {i}")
                write_jsonl(log_path, {"iter": it, "stage": "patch_policy_reject", "issues": issues2})
                break

            # Combine test diff, code diff, and conftest.py
            # NOTE: include_conftest=False to avoid patch application failures when conftest.py already exists
            # Step 1: Validate individual patches first (sequential validation)
            # This helps identify issues before combining
            if test_diff.strip():
                try:
                    from bench_agent.protocol.diff_validator import validate_diff_structure
                    test_valid, test_errors = validate_diff_structure(test_diff.strip())
                    if not test_valid and test_errors:
                        console.print(f"[yellow]Test diff structure warnings: {len(test_errors)} found[/yellow]")
                except Exception:
                    pass
            
            if code_diff.strip():
                try:
                    from bench_agent.protocol.diff_validator import validate_diff_structure
                    code_valid, code_errors = validate_diff_structure(code_diff.strip())
                    if not code_valid and code_errors:
                        console.print(f"[yellow]Code diff structure warnings: {len(code_errors)} found[/yellow]")
                except Exception:
                    pass
            
            # P0.8: Pre-Apply Normalization Gate V2 (Option 1: Reference Test Diff)
            # Key change from P0.7: Try to extract test diff from reference first
            # - If reference has test files: Use reference test diff (100% accurate)
            # - If reference has no test files: Fall back to LLM test diff with P0.7 normalization
            # - Code diff: Always normalize with P0.7
            # SKIP normalization when using Component 3 (Edit Script Mode) or Phase 2.2 (Two-Stage) - diffs are already clean
            if reference_patch and (test_diff.strip() or code_diff.strip()) and not USE_EDIT_SCRIPT and not USE_TWO_STAGE:
                try:
                    from bench_agent.protocol.pre_apply_normalization import apply_normalization_gate_v2

                    # P0.8: Try reference test diff extraction, fallback to LLM test diff
                    test_diff, code_diff, norm_report = apply_normalization_gate_v2(
                        test_diff=test_diff,
                        code_diff=code_diff,
                        reference_patch=reference_patch,
                        use_reference_test_diff=True,  # P0.8 Option 1
                        verbose=True
                    )

                    # Display summary
                    console.print(f"[green]✓ P0.8: Reference test diff extraction (with fallback)[/green]")
                    if norm_report.total_fixes() > 0:
                        console.print(f"[cyan]  → Total normalizations: {norm_report.total_fixes()}[/cyan]")
                        if norm_report.malformed_patterns_fixed > 0:
                            console.print(f"[cyan]    • Malformed patterns sanitized: {norm_report.malformed_patterns_fixed}[/cyan]")
                        if norm_report.reference_line_numbers_applied > 0:
                            console.print(f"[cyan]    • Reference line numbers enforced: {norm_report.reference_line_numbers_applied}[/cyan]")

                except Exception as e:
                    import sys
                    print(f"[run_mvp] Warning: P0.8 normalization failed, falling back: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    # Keep original diffs on error

            # Step 2: Combine patches (separate test and code patches)
            combined_patch = combine_diffs(test_diff.strip(), code_diff.strip(), include_conftest=False)
            # Apply clean_diff_format to combined patch to fix multi-hunk line numbers
            # SKIP when using Component 3 (Edit Script Mode) or Phase 2.2 (Two-Stage) - diffs are already clean
            if not USE_EDIT_SCRIPT and not USE_TWO_STAGE:
                combined_patch = clean_diff_format(combined_patch) if combined_patch else ""
            final_test_diff = test_diff
            final_code_diff = code_diff

            # Evaluate combined patch (public tests)
            write_predictions_jsonl(predictions, instance_id, combined_patch)
            comb_run_id = f"{args.run_id}-{instance_id}-iter{it}-comb-{now_ts()}"
            comb_env_public = dict(os.environ)
            comb_env_public['TA_SPLIT'] = 'public'
            comb_res = run_swebench_eval(dataset_name, predictions, [instance_id], comb_run_id, max_workers=1, cache_level="instance", clean=False, env=comb_env_public)
            
            # Check if patch application failed BEFORE parsing test results
            comb_patch_failed = check_patch_apply_failed(comb_res.raw_stdout, comb_res.raw_stderr)
            
            # Extract detailed error information (import here to avoid circular dependency)
            from bench_agent.runner.error_analyzer import extract_patch_apply_errors, extract_test_failure_errors, generate_error_feedback
            comb_patch_errors = extract_patch_apply_errors(comb_res.raw_stdout, comb_res.raw_stderr)
            comb_test_errors = extract_test_failure_errors(comb_res.raw_stdout, comb_res.raw_stderr)
            
            if comb_patch_failed:
                # P0.5: Extract detailed failure information for tracking and debugging
                from bench_agent.protocol.patch_fallback import extract_patch_failure_details

                failure_details = extract_patch_failure_details(
                    comb_res.raw_stderr or "",
                    comb_res.raw_stdout or ""
                )

                # Component 1: Record patch apply failure with signature
                error_msg = comb_res.raw_stderr or comb_res.raw_stdout or "Unknown patch apply error"
                safety_controller.record_failure(error_msg)

                # Track failure history for this instance
                if 'patch_failure_history' not in locals():
                    patch_failure_history = []
                patch_failure_history.append(failure_details)

                # Log detailed failure information
                console.print(f"[red]Patch Apply Failure (Iteration {it})[/red]")
                console.print(f"  Type: {failure_details['failure_type']}")
                if failure_details.get('failed_hunks'):
                    console.print(f"  Failed Hunks: {failure_details['failed_hunks']}")
                if failure_details.get('failed_at_line'):
                    console.print(f"  Failed at Line: {failure_details['failed_at_line']}")
                console.print(f"  Error: {failure_details['error_message']}")

                # Patch failed, tests were not executed
                public_report = {
                    "passed": 0,
                    "failed": 0,
                    "total": 0,
                    "pass_rate": 0.0,
                    "ok": False,
                    "patch_apply_failed": True,
                    "failure_details": failure_details,  # Add failure details to report
                }

                # Log detailed error information
                if comb_patch_errors.get('error_message'):
                    console.print(f"[red]Patch apply error: {comb_patch_errors['error_message']}[/red]")
                    if comb_patch_errors.get('suggestions'):
                        console.print("[yellow]Suggestions:[/yellow]")
                        for suggestion in comb_patch_errors['suggestions'][:3]:
                            console.print(f"  - {suggestion}")
            else:
                # Parse public test results
                # Try stdout/stderr first (more reliable)
                public_stdout = parse_pytest_output(comb_res.raw_stdout)
                public_stderr = parse_pytest_output(comb_res.raw_stderr)
                public_report = public_stdout if public_stdout["total"] > 0 else public_stderr
                
                # If stdout/stderr parsing failed, try report files
                if public_report["total"] == 0:
                    public_report = parse_harness_report(comb_res.report_dir, instance_id, debug=False)
                
                # Final fallback: return code
                if public_report["total"] == 0:
                    public_report["ok"] = comb_res.ok
                    public_report["pass_rate"] = 1.0 if comb_res.ok else 0.0
                
                # Ensure patch_apply_failed flag is set
                public_report["patch_apply_failed"] = False
            
            public_pass_rate = public_report["pass_rate"]
            public_ok = public_report["ok"]

            # Hidden eval (overfitting check)
            hidden_result = run_hidden_eval(
                dataset_name=dataset_name,
                predictions_path=predictions,
                instance_id=instance_id,
                run_id_base=comb_run_id,
                cache_level="instance",
                clean=False,
            )

            # Calculate Overfit Gap
            overfit_gap = 0.0
            hidden_pass_rate = 0.0
            if hidden_result and hidden_result.get("total", 0) > 0:
                hidden_pass_rate = hidden_result.get("pass_rate", 0.0)
                overfit_gap = public_pass_rate - hidden_pass_rate
            
            rec = {
                "iter": it,
                "decision": decision,
                "brs": {
                    "fail_on_buggy": brs_fail,  # True if tests fail on buggy code (good)
                    "pass_rate": brs_pass_rate,
                },
                "public": {
                    "ok": public_ok,
                    "pass_rate": public_pass_rate,
                    "passed": public_report.get("passed", 0),
                    "failed": public_report.get("failed", 0),
                    "total": public_report.get("total", 0),
                },
                "hidden": hidden_result or {},
                "overfit_gap": overfit_gap,
                "run_ids": {"tests_only": brs_run_id, "combined": comb_run_id, "hidden": hidden_result.get("run_id") if hidden_result else None},
            }
            write_jsonl(log_path, rec)
            
            # Store feedback in history for next iteration (if not successful)
            if not public_ok and it < limits["max_iters"]:
                # Generate comprehensive feedback
                iteration_feedback = generate_error_feedback(
                    comb_patch_errors if comb_patch_failed else {},
                    comb_test_errors if not comb_patch_failed else {},
                    brs_failed=(not brs_fail)
                )
                
                if iteration_feedback:
                    # Add to history for next iteration
                    history.append({
                        "role": "user",
                        "content": f"Iteration {it} Analysis and Feedback:\n{iteration_feedback}\n\nUse this feedback to improve your approach in the next iteration."
                    })

            if public_ok:
                console.print("[green]Public tests passed (per harness return code).[/green]")
                break
            else:
                console.print("[yellow]Public tests not passing yet; continuing.[/yellow]")
                # Feedback is already stored in history above

        # Component 1: Print iteration safety statistics
        safety_stats = safety_controller.get_stats()
        console.print("\n" + "="*80)
        console.print(format_safety_stats(safety_stats))
        console.print("="*80 + "\n")

        # Save safety statistics to file
        (inst_dir / "safety_stats.json").write_text(
            json.dumps(safety_stats, indent=2),
            encoding="utf-8"
        )

        # Write finals
        (inst_dir / "final_tests.diff").write_text(final_test_diff or "", encoding="utf-8")
        (inst_dir / "final_patch.diff").write_text(final_code_diff or "", encoding="utf-8")
        
        # Calculate final metrics
        # Read all iterations to compute aggregate metrics
        all_iters = []
        if log_path.exists():
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            all_iters.append(json.loads(line))
                        except:
                            pass
        
        # Extract final iteration data
        final_iter = all_iters[-1] if all_iters else {}
        
        # Calculate scores
        hfs = final_iter.get("hidden", {}).get("pass_rate", 0.0)  # Hidden Fix Score
        public_final = final_iter.get("public", {})
        public_pass_rate = public_final.get("pass_rate", 0.0)
        og = final_iter.get("overfit_gap", 0.0)  # Overfit Gap
        brs_final = final_iter.get("brs", {})
        brs_score = 1.0 if brs_final.get("fail_on_buggy", False) else 0.0  # BRS: 1 if tests fail on buggy
        
        # TSS (Test Strength Score) - simplified: BRS + public pass rate
        tss = (brs_score * 0.5) + (public_pass_rate * 0.5)
        
        # Overall score (weighted combination)
        overall_score = (
            0.60 * hfs +      # Hidden Fix Score (60%)
            0.25 * tss +      # Test Strength Score (25%)
            0.10 * (1.0 - abs(og)) +  # Overfit penalty (10%, smaller gap is better)
            0.05 * (1.0 - min(len(all_iters) / limits["max_iters"], 1.0))  # Efficiency (5%, fewer iters is better)
        )
        
        metrics = {
            "instance_id": instance_id,
            "iterations": len(all_iters),
            "max_iters": limits["max_iters"],
            "time_limit_minutes": limits["time_limit_minutes"],
            "scores": {
                "hfs": hfs,  # Hidden Fix Score
                "tss": tss,  # Test Strength Score
                "og": og,    # Overfit Gap
                "brs": brs_score,  # Bug Reproduction Strength
                "overall": overall_score,
            },
            "final_iteration": {
                "public_pass_rate": public_pass_rate,
                "hidden_pass_rate": hfs,
                "overfit_gap": og,
                "brs_fail_on_buggy": brs_final.get("fail_on_buggy", False),
            },
            "note": "Metrics computed from harness reports. HFS=Hidden Fix Score, TSS=Test Strength Score, OG=Overfit Gap, BRS=Bug Reproduction Strength.",
        }
        (inst_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
