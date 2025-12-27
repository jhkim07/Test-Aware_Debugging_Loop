"""
Phase 2: Stage A - Planner

Generates high-level planning JSON from problem context.
Separates "what to fix" from "how to format".
"""

import json
from typing import Dict, Optional

from .llm_client import chat


# ============================================================================
# PLANNER SYSTEM PROMPT
# ============================================================================

PLANNER_SYSTEM_PROMPT = """You are a code analysis assistant specializing in bug fix planning.

Your task: Analyze the bug report and reference materials, then output a MINIMAL JSON plan.

Output ONLY valid JSON (no markdown, no explanation, no ```json markers).

Focus on:
1. Which file(s) to modify
2. Which function/class to target
3. What change to make (one sentence)
4. Test approach (if applicable)

Be concise. The plan will be used by another system to generate the actual diff."""


# ============================================================================
# PLANNER USER PROMPTS
# ============================================================================

def build_planner_prompt_test(context: Dict) -> str:
    """Build prompt for test diff planning."""

    reference_section = ""
    if context.get('reference_test_patch'):
        ref_preview = context['reference_test_patch'][:1500]
        reference_section = f"""
Reference Test Patch (use for guidance):
{ref_preview}
...

IMPORTANT: Follow the reference structure closely.
"""

    return f"""Plan a test diff for this bug.

Problem:
{context.get('problem_statement', 'N/A')[:800]}

{reference_section}

Failure Context:
{context.get('failure_summary', 'N/A')[:500]}

Output JSON schema:
{{
  "test_file": "path/to/test_file.py",
  "approach": "dictionary_append" | "new_function" | "extend_existing",
  "description": "one sentence what test does"
}}

Output ONLY the JSON above."""


def build_planner_prompt_code(context: Dict) -> str:
    """Build prompt for code diff planning."""

    reference_section = ""
    if context.get('reference_patch'):
        ref_preview = context['reference_patch'][:2000]
        reference_section = f"""
Reference Solution Patch (FOLLOW THIS CLOSELY):
{ref_preview}
...

CRITICAL: Extract the file, function, and change from the reference above.
"""

    return f"""Plan a code fix for this bug.

Problem:
{context.get('problem_statement', 'N/A')[:800]}

{reference_section}

Failure Context:
{context.get('failure_summary', 'N/A')[:500]}

Output JSON schema:
{{
  "files": [
    {{
      "path": "exact/path/from/reference",
      "function": "function_or_class_name",
      "change": "one sentence description"
    }}
  ]
}}

Output ONLY the JSON above."""


# ============================================================================
# PLANNER MAIN FUNCTION
# ============================================================================

def generate_plan(
    role: str,
    client,
    model: str,
    context: Dict,
    mode: str = "research"
) -> Dict:
    """
    Stage A: Generate planning JSON.

    Args:
        role: "test" or "code"
        client: LLM client
        model: Model name (e.g., "gpt-4o-mini")
        context: Dict with problem_statement, reference_patch, etc.
        mode: "research" or "official" (for future use)

    Returns:
        Plan dict (JSON)

    Raises:
        ValueError: If JSON parsing fails
        RuntimeError: If plan validation fails
    """

    # Build prompt based on role
    if role == "test":
        user_prompt = build_planner_prompt_test(context)
    elif role == "code":
        user_prompt = build_planner_prompt_code(context)
    else:
        raise ValueError(f"Invalid role: {role}. Must be 'test' or 'code'.")

    # Call LLM
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = chat(client, model, messages).strip()

    # Remove markdown if present
    if response.startswith("```"):
        lines = response.split("\n")
        # Remove first and last lines (```json and ```)
        response = "\n".join([l for l in lines if not l.strip().startswith("```")])

    # Parse JSON
    try:
        plan = json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner output is not valid JSON: {e}\nResponse: {response[:500]}")

    # Basic validation
    if role == "test":
        if "test_file" not in plan or "approach" not in plan:
            raise RuntimeError(f"Invalid test plan schema: {plan}")
    elif role == "code":
        if "files" not in plan or len(plan["files"]) == 0:
            raise RuntimeError(f"Invalid code plan schema: {plan}")
        if "path" not in plan["files"][0] or "function" not in plan["files"][0]:
            raise RuntimeError(f"Invalid code plan file schema: {plan['files'][0]}")

    return plan


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def validate_plan_schema(plan: Dict, role: str) -> tuple[bool, str]:
    """
    Validate plan against expected schema.

    Returns:
        (is_valid, error_message)
    """

    if role == "test":
        required_keys = ["test_file", "approach"]
        for key in required_keys:
            if key not in plan:
                return False, f"Missing required key: {key}"

        valid_approaches = ["dictionary_append", "new_function", "extend_existing"]
        if plan["approach"] not in valid_approaches:
            return False, f"Invalid approach: {plan['approach']}"

    elif role == "code":
        if "files" not in plan:
            return False, "Missing 'files' key"

        if not isinstance(plan["files"], list) or len(plan["files"]) == 0:
            return False, "'files' must be non-empty list"

        for i, file_plan in enumerate(plan["files"]):
            required_keys = ["path", "function", "change"]
            for key in required_keys:
                if key not in file_plan:
                    return False, f"File {i}: Missing required key '{key}'"

    return True, "OK"
