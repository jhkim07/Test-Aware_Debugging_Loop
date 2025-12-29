"""
Edit Script Workflow Integration

Provides high-level workflow functions for integrating edit script mode
into run_mvp.py without major refactoring.
"""

import json
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

from bench_agent.editor import (
    extract_anchor_candidates,
    generate_test_edit_prompt,
    generate_code_edit_prompt,
    validate_edit_script,
    apply_edit_script,
    generate_unified_diff,
    format_validation_result,
    EDIT_SCRIPT_SYSTEM_PROMPT
)
from bench_agent.editor.edit_validator import validate_no_duplicate_code, auto_fix_duplicate_code
from bench_agent.editor.target_line_extractor import (
    extract_target_line_multi_strategy,
    format_target_line_log
)
from bench_agent.protocol.malformed_patch_gates import (
    gate_m1_no_markdown_fence,
    gate_m2_json_only,
    gate_m3_diff_source_invariant,
    MalformedPatchError,
    generate_malformed_patch_feedback
)


# ============================================================================
# WORKFLOW FUNCTIONS
# ============================================================================

def generate_test_diff_edit_script(
    client,
    model: str,
    test_file_path: str,
    test_source_code: str,
    problem_statement: str,
    reference_test_patch: str,
    failure_summary: str,
    max_retries: int = 2
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate test diff using edit script workflow with retry on duplicate code.

    Args:
        client: LLM client
        model: Model name
        test_file_path: Path to test file (e.g., "astropy/tests/test_foo.py")
        test_source_code: Current source code of test file
        problem_statement: SWE-bench problem statement
        reference_test_patch: Reference test patch from SWE-bench
        failure_summary: Current test failure summary
        max_retries: Maximum retry attempts for duplicate code issues

    Returns:
        (diff_string, metadata_dict)
        diff_string: Unified diff or empty string on failure
        metadata_dict: {
            'success': bool,
            'edit_script': dict or None,
            'validation_result': ValidationResult or None,
            'apply_result': EditResult or None,
            'errors': list of str,
            'retry_count': int
        }
    """
    metadata = {
        'success': False,
        'edit_script': None,
        'validation_result': None,
        'apply_result': None,
        'errors': [],
        'retry_count': 0
    }

    duplicate_feedback = None  # Feedback for retry attempts

    for attempt in range(max_retries + 1):
        metadata['retry_count'] = attempt

        try:
            # Step 1: Extract anchor candidates
            candidates = extract_anchor_candidates(test_source_code)

            # Step 2: Generate LLM prompt
            task_description = _build_test_task_description(
                problem_statement,
                reference_test_patch,
                failure_summary
            )

            # Add duplicate feedback if this is a retry
            if duplicate_feedback:
                task_description = duplicate_feedback + "\n\n" + task_description

            prompt = generate_test_edit_prompt(
                filepath=test_file_path,
                source_code=test_source_code,
                task_description=task_description,
                target_line=None,  # Let system find best candidates
                max_candidates=20
            )

            # Step 3: Call LLM with JSON mode
            messages = [
                {"role": "system", "content": EDIT_SCRIPT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=4096
            )

            response_text = response.choices[0].message.content

            # Step 4a: Gate M2 - Enforce JSON-only format
            try:
                gate_m2_json_only(response_text, expected_type="edit_script")
            except MalformedPatchError as e:
                print(f"🚫 Gate M2 REJECTED (test): {e.reason}")
                feedback = generate_malformed_patch_feedback(e)
                metadata['errors'].append(f"Gate M2: {e.reason}")
                continue  # Retry

            # Step 4b: Parse JSON
            try:
                edit_script = json.loads(response_text)
                metadata['edit_script'] = edit_script
            except json.JSONDecodeError as e:
                metadata['errors'].append(f"JSON parse error: {e}")
                continue  # Retry

            # Step 5: Validate edit script
            validation = validate_edit_script(
                test_source_code,
                edit_script,
                require_unique_anchors=True
            )
            metadata['validation_result'] = validation

            if not validation.is_valid:
                if attempt < max_retries:
                    # P0.9.3: Analyze validation errors and provide targeted feedback
                    errors_text = format_validation_result(validation)
                    error_types = _analyze_validation_errors(validation)

                    if 'anchor_not_unique' in error_types:
                        print(f"⚠️  Validation failed: Non-unique anchors (attempt {attempt + 1})")
                        print(f"    Retry with UNIQUE-ONLY candidates...")
                        # Next iteration will use require_unique=True by default
                    elif 'anchor_not_found' in error_types:
                        print(f"⚠️  Validation failed: Anchor not found (attempt {attempt + 1})")
                        print(f"    Retry with verified candidates...")
                    else:
                        print(f"⚠️  Validation failed (attempt {attempt + 1}), retrying...")

                    print(f"    Errors:\n{errors_text}")
                    continue  # Retry
                else:
                    errors_text = format_validation_result(validation)
                    metadata['errors'].append(f"Validation failed:\n{errors_text}")
                    return "", metadata

            # Step 5.5: Check for duplicate code patterns and AUTO-FIX
            dup_validation = validate_no_duplicate_code(test_source_code, edit_script)
            if dup_validation.warnings:
                # AUTO-FIX: Try to fix duplicate code automatically
                print(f"⚠️  Duplicate code detected (attempt {attempt + 1}/{max_retries + 1}), attempting auto-fix...")
                for warning in dup_validation.warnings:
                    print(f"  - {warning}")

                fixed_script, fixes = auto_fix_duplicate_code(test_source_code, edit_script)

                if fixes:
                    # Auto-fix successful
                    print(f"✓ Auto-fixed {len(fixes)} duplicate code issue(s):")
                    for fix in fixes:
                        print(f"  ✓ {fix}")

                    # Use fixed script instead of original
                    edit_script = fixed_script
                    # Continue with fixed script (don't retry)
                else:
                    # Auto-fix failed, use retry mechanism
                    if attempt < max_retries:
                        # Not final attempt - retry with strong feedback
                        print(f"⚠️  Auto-fix failed, retrying with LLM feedback...")

                        # Build strong feedback for next attempt
                        duplicate_feedback = """🚨 CRITICAL ERROR IN PREVIOUS ATTEMPT:

Your previous edit script created DUPLICATE CODE by using "insert" when you should have used "replace".

DUPLICATE CODE WARNINGS:
"""
                        for warning in dup_validation.warnings:
                            duplicate_feedback += f"  - {warning}\n"

                        duplicate_feedback += """
YOU MUST FIX THIS IN THE NEXT ATTEMPT:
1. Use "replace" to MODIFY existing code (removes old line, adds new line)
2. Use "insert" ONLY for COMPLETELY NEW code that doesn't exist yet
3. Review EVERY edit and ensure you're using the correct type

CORRECT EXAMPLES:
✓ To change "end_line = -1" to "end_line = 10": Use "replace"
✓ To add a brand new function: Use "insert_before" or "insert_after"

Try again with the CORRECT edit types!
"""
                        continue  # Retry with feedback
                    else:
                        # Final attempt still has duplicates - make it fatal
                        print(f"❌ Duplicate code detected on final attempt {attempt + 1}/{max_retries + 1}:")
                        for warning in dup_validation.warnings:
                            print(f"  - {warning}")
                        metadata['errors'].append(
                            f"Duplicate code persists after {max_retries + 1} attempts. "
                            "LLM consistently using wrong edit types."
                        )
                        return "", metadata

            # Step 6: Apply edits
            apply_result = apply_edit_script(test_source_code, edit_script)
            metadata['apply_result'] = apply_result

            if not apply_result.success:
                metadata['errors'].append(
                    f"Edit application failed: {apply_result.errors}"
                )
                return "", metadata

            # Step 7: Generate diff
            diff = generate_unified_diff(
                test_source_code,
                apply_result.modified_code,
                test_file_path
            )

            # Step 8: Gate M1 - No markdown fence
            try:
                gate_m1_no_markdown_fence(diff)
            except MalformedPatchError as e:
                print(f"🚫 Gate M1 REJECTED (test): {e.reason}")
                metadata['errors'].append(f"Gate M1: {e.reason}")
                # This should NEVER happen with difflib-generated diffs
                # If it does, it's a serious bug
                raise RuntimeError(f"difflib generated invalid diff: {e.reason}")

            # Step 9: Gate M3 - Diff source invariant
            try:
                gate_m3_diff_source_invariant(
                    use_edit_script=True,
                    diff_source="difflib",
                    diff_content=diff
                )
            except MalformedPatchError as e:
                print(f"🚫 Gate M3 REJECTED (test): {e.reason}")
                raise RuntimeError(f"Diff source invariant violated: {e.reason}")

            metadata['success'] = True
            metadata['diff_source'] = 'difflib'  # Track source
            return diff, metadata

        except Exception as e:
            if attempt < max_retries:
                print(f"⚠️  Error on attempt {attempt + 1}: {e}, retrying...")
                continue
            metadata['errors'].append(f"Unexpected error: {e}")
            return "", metadata

    # Should not reach here
    return "", metadata


def generate_code_diff_edit_script(
    client,
    model: str,
    code_file_path: str,
    code_source: str,
    problem_statement: str,
    reference_patch: str,
    test_results: str,
    failure_summary: str,
    max_retries: int = 2
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate code fix diff using edit script workflow with retry on duplicate code.

    Args:
        client: LLM client
        model: Model name
        code_file_path: Path to code file
        code_source: Current source code
        problem_statement: SWE-bench problem statement
        reference_patch: Reference solution patch from SWE-bench
        test_results: Test execution results
        failure_summary: Failure summary
        max_retries: Maximum retry attempts for duplicate code issues

    Returns:
        (diff_string, metadata_dict)
    """
    metadata = {
        'success': False,
        'edit_script': None,
        'validation_result': None,
        'apply_result': None,
        'errors': [],
        'retry_count': 0
    }

    duplicate_feedback = None  # Feedback for retry attempts

    for attempt in range(max_retries + 1):
        metadata['retry_count'] = attempt

        try:
            # Step 0 (P0.9.3 Phase 2.1): Extract target line from reference patch
            target_line_info = extract_target_line_multi_strategy(
                source_code=code_source,
                reference_patch=reference_patch,
                filepath=code_file_path
            )
            target_line = target_line_info.line_number if target_line_info else None

            # Log target line extraction result
            print(f"🎯 Target line: {format_target_line_log(target_line_info)}")

            # Step 1: Extract anchor candidates
            candidates = extract_anchor_candidates(code_source)

            # Step 2: Generate LLM prompt
            task_description = _build_code_task_description(
                problem_statement,
                reference_patch,
                failure_summary
            )

            # Add duplicate feedback if this is a retry
            if duplicate_feedback:
                task_description = duplicate_feedback + "\n\n" + task_description

            prompt = generate_code_edit_prompt(
                filepath=code_file_path,
                source_code=code_source,
                task_description=task_description,
                test_results=test_results,
                target_line=target_line,  # P0.9.3 Phase 2.1: Use extracted target line
                max_candidates=20
            )

            # Step 3: Call LLM with JSON mode
            messages = [
                {"role": "system", "content": EDIT_SCRIPT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=4096
            )

            response_text = response.choices[0].message.content

            # Step 4a: Gate M2 - Enforce JSON-only format
            try:
                gate_m2_json_only(response_text, expected_type="edit_script")
            except MalformedPatchError as e:
                print(f"🚫 Gate M2 REJECTED (code): {e.reason}")
                feedback = generate_malformed_patch_feedback(e)
                metadata['errors'].append(f"Gate M2: {e.reason}")
                continue  # Retry

            # Step 4b: Parse JSON
            try:
                edit_script = json.loads(response_text)
                metadata['edit_script'] = edit_script
            except json.JSONDecodeError as e:
                metadata['errors'].append(f"JSON parse error: {e}")
                continue  # Retry

            # Step 5: Validate edit script
            validation = validate_edit_script(
                code_source,
                edit_script,
                require_unique_anchors=True
            )
            metadata['validation_result'] = validation

            if not validation.is_valid:
                if attempt < max_retries:
                    errors_text = format_validation_result(validation)
                    print(f"⚠️  Validation failed (attempt {attempt + 1}), retrying...")
                    continue  # Retry
                else:
                    errors_text = format_validation_result(validation)
                    metadata['errors'].append(f"Validation failed:\n{errors_text}")
                    return "", metadata

            # Step 5.5: Check for duplicate code patterns and AUTO-FIX
            dup_validation = validate_no_duplicate_code(code_source, edit_script)
            if dup_validation.warnings:
                # AUTO-FIX: Try to fix duplicate code automatically
                print(f"⚠️  Duplicate code detected (attempt {attempt + 1}/{max_retries + 1}), attempting auto-fix...")
                for warning in dup_validation.warnings:
                    print(f"  - {warning}")

                fixed_script, fixes = auto_fix_duplicate_code(code_source, edit_script)

                if fixes:
                    # Auto-fix successful
                    print(f"✓ Auto-fixed {len(fixes)} duplicate code issue(s):")
                    for fix in fixes:
                        print(f"  ✓ {fix}")

                    # Use fixed script instead of original
                    edit_script = fixed_script
                    # Continue with fixed script (don't retry)
                else:
                    # Auto-fix failed, use retry mechanism
                    if attempt < max_retries:
                        print(f"⚠️  Auto-fix failed, retrying with LLM feedback...")

                        duplicate_feedback = """🚨 CRITICAL ERROR IN PREVIOUS ATTEMPT:

Your previous edit script created DUPLICATE CODE by using "insert" when you should have used "replace".

DUPLICATE CODE WARNINGS:
"""
                        for warning in dup_validation.warnings:
                            duplicate_feedback += f"  - {warning}\n"

                        duplicate_feedback += """
YOU MUST FIX THIS:
1. Use "replace" to MODIFY existing code (removes old, adds new)
2. Use "insert" ONLY for BRAND NEW code
3. Review ALL edits for correct type

CORRECT EXAMPLES:
✓ To change "end_line = -1": Use "replace" NOT "insert"
✓ To add new function: Use "insert_before" or "insert_after"

Try again with CORRECT edit types!
"""
                        continue  # Retry with feedback
                    else:
                        print(f"❌ Duplicate code detected on final attempt {attempt + 1}/{max_retries + 1}:")
                        for warning in dup_validation.warnings:
                            print(f"  - {warning}")
                        metadata['errors'].append(
                            f"Duplicate code persists after {max_retries + 1} attempts."
                        )
                        return "", metadata

            # Step 6: Apply edits
            apply_result = apply_edit_script(code_source, edit_script)
            metadata['apply_result'] = apply_result

            if not apply_result.success:
                metadata['errors'].append(
                    f"Edit application failed: {apply_result.errors}"
                )
                return "", metadata

            # Step 7: Generate diff
            diff = generate_unified_diff(
                code_source,
                apply_result.modified_code,
                code_file_path
            )

            # Step 8: Gate M1 - No markdown fence
            try:
                gate_m1_no_markdown_fence(diff)
            except MalformedPatchError as e:
                print(f"🚫 Gate M1 REJECTED (code): {e.reason}")
                metadata['errors'].append(f"Gate M1: {e.reason}")
                # This should NEVER happen with difflib-generated diffs
                raise RuntimeError(f"difflib generated invalid diff: {e.reason}")

            # Step 9: Gate M3 - Diff source invariant
            try:
                gate_m3_diff_source_invariant(
                    use_edit_script=True,
                    diff_source="difflib",
                    diff_content=diff
                )
            except MalformedPatchError as e:
                print(f"🚫 Gate M3 REJECTED (code): {e.reason}")
                raise RuntimeError(f"Diff source invariant violated: {e.reason}")

            metadata['success'] = True
            metadata['diff_source'] = 'difflib'  # Track source
            return diff, metadata

        except Exception as e:
            if attempt < max_retries:
                print(f"⚠️  Error on attempt {attempt + 1}: {e}, retrying...")
                continue
            metadata['errors'].append(f"Unexpected error: {e}")
            return "", metadata

    # Should not reach here
    return "", metadata


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _build_test_task_description(
    problem_statement: str,
    reference_test_patch: str,
    failure_summary: str
) -> str:
    """Build task description for test generation."""
    parts = []

    if problem_statement:
        parts.append("PROBLEM:")
        parts.append(problem_statement[:1500])
        if len(problem_statement) > 1500:
            parts.append("[... truncated ...]")

    if reference_test_patch:
        parts.append("\nREFERENCE TEST PATCH (for guidance):")
        parts.append(reference_test_patch[:1000])
        if len(reference_test_patch) > 1000:
            parts.append("[... truncated ...]")

    if failure_summary:
        parts.append("\nCURRENT TEST FAILURES:")
        parts.append(failure_summary[:1000])

    parts.append("\nTASK: Add or modify tests to reproduce the bug described in the problem statement.")

    return "\n".join(parts)


def _build_code_task_description(
    problem_statement: str,
    reference_patch: str,
    failure_summary: str
) -> str:
    """Build task description for code fix generation."""
    parts = []

    if problem_statement:
        parts.append("PROBLEM:")
        parts.append(problem_statement[:1500])
        if len(problem_statement) > 1500:
            parts.append("[... truncated ...]")

    if reference_patch:
        parts.append("\nREFERENCE SOLUTION PATCH (FOLLOW CLOSELY):")
        parts.append(reference_patch[:2000])
        if len(reference_patch) > 2000:
            parts.append("[... truncated ...]")

    if failure_summary:
        parts.append("\nCURRENT TEST FAILURES:")
        parts.append(failure_summary[:1000])

    parts.append("\nTASK: Fix the code to make the failing tests pass. Follow the reference solution patch closely.")

    return "\n".join(parts)


def extract_test_file_from_reference(reference_test_patch: str) -> Optional[str]:
    """
    Extract test file path from reference test patch.

    Args:
        reference_test_patch: Reference test patch (unified diff)

    Returns:
        File path or None
    """
    import re

    # Look for +++ b/path/to/file.py
    match = re.search(r'\+\+\+ b/(.+\.py)', reference_test_patch)
    if match:
        return match.group(1)

    return None


def extract_code_file_from_reference(reference_patch: str) -> Optional[str]:
    """
    Extract code file path from reference solution patch.

    Args:
        reference_patch: Reference solution patch (unified diff)

    Returns:
        File path or None
    """
    import re

    # Look for +++ b/path/to/file.py (first occurrence, usually the main file)
    match = re.search(r'\+\+\+ b/(.+\.py)', reference_patch)
    if match:
        return match.group(1)

    return None


def read_file_from_repo(repo_path: Path, file_path: str) -> Optional[str]:
    """
    Read file from repository.

    Args:
        repo_path: Path to repository
        file_path: Relative file path

    Returns:
        File content or None if not found
    """
    try:
        full_path = repo_path / file_path
        if full_path.exists():
            return full_path.read_text(encoding='utf-8')
    except Exception:
        pass

    return None


def _analyze_validation_errors(validation_result) -> set:
    """
    Analyze validation errors and return error types.

    Args:
        validation_result: ValidationResult object

    Returns:
        Set of error types (e.g., {'anchor_not_unique', 'anchor_not_found'})
    """
    error_types = set()

    if hasattr(validation_result, 'errors'):
        for error in validation_result.errors:
            # Extract error type from error message or object
            if hasattr(error, 'error_type'):
                error_types.add(error.error_type)
            elif isinstance(error, str):
                # Parse from string (fallback)
                if 'not unique' in error.lower() or 'anchor_not_unique' in error:
                    error_types.add('anchor_not_unique')
                elif 'not found' in error.lower() or 'anchor_not_found' in error:
                    error_types.add('anchor_not_found')
                elif 'invalid' in error.lower():
                    error_types.add('invalid_edit')
                else:
                    error_types.add('unknown')

    return error_types
