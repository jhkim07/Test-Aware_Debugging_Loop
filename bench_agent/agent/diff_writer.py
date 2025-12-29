"""
Phase 2: Stage B - Diff Writer

Converts planning JSON into unified diff format.
Focuses on precise formatting, not semantic decisions.

Phase 2.2: Enhanced with syntax validation and sanitization.
"""

import json
from typing import Dict, List

from .llm_client import chat
from .diff_syntax_validator import sanitize_diff, validate_diff_syntax


# ============================================================================
# DIFF WRITER SYSTEM PROMPT
# ============================================================================

DIFF_WRITER_SYSTEM_PROMPT = """You are a precise diff generator.

Your task: Convert the JSON plan into a unified diff format.

CRITICAL RULES:
1. Output ONLY unified diff format
2. NO markdown (no ```diff markers)
3. NO explanations or comments
4. Follow the plan EXACTLY
5. Use proper diff headers: diff --git, ---, +++, @@
6. Include 10-15 lines of context around changes

Start your output with: diff --git a/..."""


# ============================================================================
# DIFF WRITER USER PROMPTS
# ============================================================================

def build_writer_prompt_test(plan: Dict, context: Dict) -> str:
    """Build prompt for test diff generation with error feedback."""

    # Phase 2.2: Add previous error feedback
    error_feedback = ""
    if context.get('previous_errors'):
        error_list = '\n'.join(f"  - {err}" for err in context['previous_errors'])
        error_feedback = f"""
⚠️ CRITICAL - Previous attempt had these errors:
{error_list}

You MUST avoid these errors in this attempt.
"""

    reference_hint = ""
    if context.get('reference_test_patch'):
        ref_preview = context['reference_test_patch'][:1000]
        reference_hint = f"""
Reference Test Patch (for structure guidance only):
{ref_preview}
...
"""

    conftest_hint = ""
    if context.get('conftest_content'):
        conftest_preview = context['conftest_content'][:500]
        conftest_hint = f"""
Current conftest.py content (if dictionary_append):
{conftest_preview}
...
"""

    return f"""Generate unified diff for test changes.

Plan:
{json.dumps(plan, indent=2)}

{error_feedback}

{reference_hint}

{conftest_hint}

Requirements:
- File to modify: {plan.get('test_file', 'N/A')}
- Approach: {plan.get('approach', 'N/A')}
- Description: {plan.get('description', 'N/A')}

CRITICAL FORMATTING RULES:
- NO stray triple-quotes outside context lines
- ALL hunk headers MUST be complete: @@ -X,Y +A,B @@
- Context lines MUST start with space, + for additions, - for removals
- NO partial lines or broken syntax

Output unified diff ONLY. Start with: diff --git a/..."""


def build_writer_prompt_code(plan: Dict, context: Dict) -> str:
    """Build prompt for code diff generation with error feedback."""

    file_plan = plan["files"][0]  # Assume single file for now

    # Phase 2.2: Add previous error feedback
    error_feedback = ""
    if context.get('previous_errors'):
        error_list = '\n'.join(f"  - {err}" for err in context['previous_errors'])
        error_feedback = f"""
⚠️ CRITICAL - Previous attempt had these errors:
{error_list}

You MUST avoid these errors in this attempt.
"""

    reference_hint = ""
    if context.get('reference_patch'):
        ref_preview = context['reference_patch'][:1500]
        reference_hint = f"""
Reference Solution Patch (FOLLOW CLOSELY for line numbers and structure):
{ref_preview}
...

CRITICAL: Match the line numbers and context from the reference above.
"""

    function_hint = ""
    if context.get('function_context'):
        func_preview = context['function_context'][:800]
        function_hint = f"""
Target Function Context:
{func_preview}
...
"""

    return f"""Generate unified diff for code changes.

Plan:
{json.dumps(file_plan, indent=2)}

{error_feedback}

{reference_hint}

{function_hint}

Requirements:
- File: {file_plan.get('path', 'N/A')}
- Function: {file_plan.get('function', 'N/A')}
- Change: {file_plan.get('change', 'N/A')}

CRITICAL FORMATTING RULES:
- NO stray triple-quotes outside context lines
- ALL hunk headers MUST be complete: @@ -X,Y +A,B @@
- Context lines MUST start with space, + for additions, - for removals
- NO partial lines or broken syntax

Output unified diff ONLY. Start with: diff --git a/..."""


# ============================================================================
# DIFF WRITER MAIN FUNCTION
# ============================================================================

def render_diff(
    role: str,
    plan: Dict,
    client,
    model: str,
    context: Dict
) -> str:
    """
    Stage B: Generate unified diff from plan.

    Phase 2.2: Enhanced with sanitization and validation.

    Args:
        role: "test" or "code"
        plan: Planning JSON from Stage A
        client: LLM client
        model: Model name (e.g., "gpt-4o-mini")
        context: Dict with reference patches, source code, etc.

    Returns:
        Unified diff string (sanitized and validated)

    Raises:
        ValueError: If diff generation or validation fails
    """

    # Build prompt based on role
    if role == "test":
        user_prompt = build_writer_prompt_test(plan, context)
    elif role == "code":
        user_prompt = build_writer_prompt_code(plan, context)
    else:
        raise ValueError(f"Invalid role: {role}. Must be 'test' or 'code'.")

    # Call LLM
    messages = [
        {"role": "system", "content": DIFF_WRITER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = chat(client, model, messages).strip()

    # DEBUG: Save full diff to file for analysis
    import sys, os
    debug_dir = "/tmp/phase22_debug"
    os.makedirs(debug_dir, exist_ok=True)
    debug_file = f"{debug_dir}/{role}_original.diff"
    with open(debug_file, 'w') as f:
        f.write(response)
    print(f"[DEBUG] Saved original {role} diff to {debug_file}", file=sys.stderr)

    # Check for invalid lines
    invalid_found = False
    for i, line in enumerate(response.split('\n'), 1):
        if line.strip() and not line.startswith(('diff ', '--- ', '+++ ', 'index ', '@@', ' ', '+', '-')):
            if not invalid_found:
                print(f"[DEBUG] Invalid lines found in {role} diff:", file=sys.stderr)
                invalid_found = True
            print(f"  Line {i}: {repr(line[:80])}", file=sys.stderr)
    if not invalid_found:
        print(f"[DEBUG] No invalid lines in original {role} diff", file=sys.stderr)

    # Phase 2.2: Apply sanitization pipeline
    sanitized_diff, warnings = sanitize_diff(response)

    # DEBUG: Also save sanitized diff
    sanitized_file = f"{debug_dir}/{role}_sanitized.diff"
    with open(sanitized_file, 'w') as f:
        f.write(sanitized_diff)
    print(f"[DEBUG] Saved sanitized {role} diff to {sanitized_file}", file=sys.stderr)

    # Log warnings if any
    if warnings:
        import sys
        print(f"[diff_writer] Sanitization warnings for {role} diff:", file=sys.stderr)
        for warning in warnings:
            print(f"  - {warning}", file=sys.stderr)

    # Final validation
    is_valid, errors = validate_diff_syntax(sanitized_diff)
    if not is_valid:
        error_msg = '\n'.join(errors)
        raise ValueError(f"Diff syntax validation failed:\n{error_msg}")

    # Basic sanity check (should pass after sanitization)
    if not sanitized_diff.startswith("diff --git"):
        raise ValueError(f"Sanitized diff doesn't start with 'diff --git'. Got: {sanitized_diff[:100]}")

    return sanitized_diff


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_plan_files(plan: Dict, role: str) -> list[str]:
    """Extract file paths from plan for validation."""

    if role == "test":
        return [plan.get("test_file", "")]
    elif role == "code":
        return [f.get("path", "") for f in plan.get("files", [])]
    else:
        return []


def validate_diff_matches_plan(diff: str, plan: Dict, role: str) -> tuple[bool, str]:
    """
    Check if diff files match plan files.

    Returns:
        (matches, error_message)
    """

    plan_files = extract_plan_files(plan, role)

    for plan_file in plan_files:
        if plan_file and plan_file not in diff:
            return False, f"Plan file '{plan_file}' not found in diff"

    return True, "OK"
