"""
Phase 2: Stage B - Diff Writer

Converts planning JSON into unified diff format.
Focuses on precise formatting, not semantic decisions.
"""

import json
from typing import Dict

from .llm_client import chat


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
    """Build prompt for test diff generation."""

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

{reference_hint}

{conftest_hint}

Requirements:
- File to modify: {plan.get('test_file', 'N/A')}
- Approach: {plan.get('approach', 'N/A')}
- Description: {plan.get('description', 'N/A')}

Output unified diff ONLY. Start with: diff --git a/..."""


def build_writer_prompt_code(plan: Dict, context: Dict) -> str:
    """Build prompt for code diff generation."""

    file_plan = plan["files"][0]  # Assume single file for now

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

{reference_hint}

{function_hint}

Requirements:
- File: {file_plan.get('path', 'N/A')}
- Function: {file_plan.get('function', 'N/A')}
- Change: {file_plan.get('change', 'N/A')}

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

    Args:
        role: "test" or "code"
        plan: Planning JSON from Stage A
        client: LLM client
        model: Model name (e.g., "gpt-4o-mini")
        context: Dict with reference patches, source code, etc.

    Returns:
        Unified diff string

    Raises:
        ValueError: If diff generation fails
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

    # Remove markdown if present
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join([l for l in lines if not l.strip().startswith("```")])

    # Basic sanity check
    if not response.startswith("diff --git"):
        raise ValueError(f"Writer output doesn't start with 'diff --git'. Got: {response[:100]}")

    return response


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
