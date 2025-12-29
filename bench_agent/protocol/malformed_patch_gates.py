"""
P0.9.3 Phase 2.1: Malformed Patch Gates

Critical gates to prevent malformed patches that cause apply failures.
These gates REJECT bad patches immediately, forcing retry with corrective feedback.
"""

import re
from typing import Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class MalformedPatchError(Exception):
    """Exception raised when patch fails malformed gates."""
    gate_name: str
    reason: str
    corrective_feedback: str

    def __str__(self):
        return f"Gate {self.gate_name}: {self.reason}"


# ============================================================================
# GATE M1: MARKDOWN FENCE BLOCKER
# ============================================================================

def gate_m1_no_markdown_fence(patch: str) -> Tuple[bool, Optional[str]]:
    """
    Gate M1: Block patches containing markdown code fence markers.

    CRITICAL: Markdown fences (```) cause "Malformed patch" errors.
    This is a 100% failure pattern that must be rejected immediately.

    Args:
        patch: Patch content to validate

    Returns:
        (is_valid, error_message)

    Raises:
        MalformedPatchError: If markdown fence detected
    """
    # Check for markdown code fences
    fence_patterns = [
        r'^```',           # Start of line fence
        r'```\s*$',        # End of line fence
        r'```diff',        # Diff fence
        r'```python',      # Python fence
        r'```json',        # JSON fence
    ]

    for pattern in fence_patterns:
        if re.search(pattern, patch, re.MULTILINE):
            match = re.search(pattern, patch, re.MULTILINE)
            line_num = patch[:match.start()].count('\n') + 1

            raise MalformedPatchError(
                gate_name="M1",
                reason=f"Markdown code fence detected at line {line_num}: {match.group()}",
                corrective_feedback=(
                    "CRITICAL ERROR: Your patch contains markdown code fence markers (```).\n"
                    "This causes 'Malformed patch' errors during git apply.\n\n"
                    "REQUIRED FORMAT:\n"
                    "- For edit scripts: Return ONLY valid JSON (no markdown, no code blocks)\n"
                    "- For unified diffs: Start with '--- a/...' (no fence markers)\n\n"
                    "FORBIDDEN:\n"
                    "```diff\n"
                    "--- a/file.py\n"
                    "```\n\n"
                    "CORRECT:\n"
                    "--- a/file.py\n"
                    "+++ b/file.py\n"
                    "@@ -1,1 +1,1 @@\n"
                )
            )

    return (True, None)


# ============================================================================
# GATE M2: EDIT SCRIPT JSON FORMAT ENFORCER
# ============================================================================

def gate_m2_json_only(llm_output: str, expected_type: str = "edit_script") -> Tuple[bool, Optional[str]]:
    """
    Gate M2: Enforce JSON-only output for edit scripts.

    CRITICAL: Edit script mode requires pure JSON. Any text outside JSON
    (markdown, explanations, etc.) causes parsing failures.

    Args:
        llm_output: Raw LLM output
        expected_type: Type of JSON expected ("edit_script" or "other")

    Returns:
        (is_valid, error_message)

    Raises:
        MalformedPatchError: If non-JSON content detected
    """
    import json

    stripped = llm_output.strip()

    # Check for markdown fences around JSON
    if stripped.startswith('```'):
        raise MalformedPatchError(
            gate_name="M2",
            reason="JSON wrapped in markdown code fence",
            corrective_feedback=(
                "CRITICAL ERROR: You wrapped the JSON in markdown code fences.\n\n"
                "FORBIDDEN:\n"
                "```json\n"
                "{ ... }\n"
                "```\n\n"
                "REQUIRED:\n"
                "{ ... }\n\n"
                "Output ONLY the JSON object, with NO markdown, NO explanations, NO fences."
            )
        )

    # Try to parse JSON
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise MalformedPatchError(
            gate_name="M2",
            reason=f"JSON parsing failed: {e}",
            corrective_feedback=(
                f"CRITICAL ERROR: Invalid JSON format.\n"
                f"Error: {e}\n\n"
                "REQUIRED: Output valid JSON only.\n"
                "Check for:\n"
                "- Missing commas\n"
                "- Trailing commas\n"
                "- Unescaped quotes\n"
                "- Missing brackets/braces\n"
            )
        )

    # Check for required fields (if edit_script)
    if expected_type == "edit_script":
        if not isinstance(parsed, dict):
            raise MalformedPatchError(
                gate_name="M2",
                reason="Edit script must be a JSON object (dict), not array or primitive",
                corrective_feedback="Edit script must be a JSON object with 'file' and 'edits' fields."
            )

        if 'file' not in parsed:
            raise MalformedPatchError(
                gate_name="M2",
                reason="Missing required field: 'file'",
                corrective_feedback="Edit script must have 'file' field specifying the file path."
            )

        if 'edits' not in parsed:
            raise MalformedPatchError(
                gate_name="M2",
                reason="Missing required field: 'edits'",
                corrective_feedback="Edit script must have 'edits' field containing list of edit operations."
            )

    return (True, None)


# ============================================================================
# GATE M3: EDIT SCRIPT DIFF SOURCE INVARIANT
# ============================================================================

def gate_m3_diff_source_invariant(
    use_edit_script: bool,
    diff_source: str,
    diff_content: str
) -> Tuple[bool, Optional[str]]:
    """
    Gate M3: Enforce that edit script mode ONLY uses difflib/git-generated diffs.

    CRITICAL INVARIANT: When USE_EDIT_SCRIPT=1, the final patch MUST come from
    difflib.unified_diff() or git diff, NEVER from LLM text output.

    Args:
        use_edit_script: Whether edit script mode is enabled
        diff_source: Source of diff ("difflib", "git_diff", or "llm")
        diff_content: The diff content (for validation)

    Returns:
        (is_valid, error_message)

    Raises:
        MalformedPatchError: If invariant violated
    """
    if not use_edit_script:
        # Invariant doesn't apply
        return (True, None)

    # Check diff source
    if diff_source not in ("difflib", "git_diff"):
        raise MalformedPatchError(
            gate_name="M3",
            reason=f"Invalid diff source in edit script mode: {diff_source}",
            corrective_feedback=(
                f"CRITICAL SYSTEM ERROR: Edit script mode violated diff source invariant.\n"
                f"Expected: difflib or git_diff\n"
                f"Got: {diff_source}\n\n"
                "This is a pipeline bug. LLM-generated diffs must never reach final patch in edit script mode."
            )
        )

    # Additional validation: check that diff looks like unified diff
    if diff_content and not diff_content.strip().startswith('---'):
        # Might be empty diff (no changes), which is OK
        if diff_content.strip():
            raise MalformedPatchError(
                gate_name="M3",
                reason="Diff doesn't start with unified diff header (--- a/...)",
                corrective_feedback=(
                    "Diff validation failed: Doesn't look like a unified diff.\n"
                    "Expected format:\n"
                    "--- a/file.py\n"
                    "+++ b/file.py\n"
                    "@@ ... @@\n"
                )
            )

    return (True, None)


# ============================================================================
# COMBINED GATE RUNNER
# ============================================================================

def run_malformed_patch_gates(
    patch: str,
    use_edit_script: bool = False,
    diff_source: str = "unknown",
    llm_output: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Run all malformed patch gates.

    Args:
        patch: Final patch content
        use_edit_script: Whether edit script mode is enabled
        diff_source: Source of diff generation
        llm_output: Raw LLM output (for JSON validation)

    Returns:
        (all_passed, list_of_errors)

    Note: Raises MalformedPatchError on first failure for immediate rejection
    """
    errors = []

    try:
        # Gate M1: No markdown fences
        gate_m1_no_markdown_fence(patch)

        # Gate M2: JSON-only (if LLM output provided)
        if llm_output:
            gate_m2_json_only(llm_output, expected_type="edit_script")

        # Gate M3: Diff source invariant
        gate_m3_diff_source_invariant(use_edit_script, diff_source, patch)

    except MalformedPatchError as e:
        # Re-raise for immediate handling
        raise

    return (True, [])


# ============================================================================
# CORRECTIVE FEEDBACK GENERATOR
# ============================================================================

def generate_malformed_patch_feedback(error: MalformedPatchError) -> str:
    """
    Generate detailed corrective feedback for LLM retry.

    Args:
        error: The malformed patch error

    Returns:
        Formatted feedback string for LLM prompt
    """
    feedback = f"""
================================================================================
MALFORMED PATCH DETECTED - IMMEDIATE RETRY REQUIRED
================================================================================

Gate Failed: {error.gate_name}
Reason: {error.reason}

{error.corrective_feedback}

================================================================================
CRITICAL REQUIREMENTS FOR RETRY:
================================================================================

1. If generating edit script (JSON):
   - Output ONLY valid JSON
   - NO markdown code fences (```)
   - NO explanations or comments outside JSON
   - Must have 'file' and 'edits' fields

2. If generating unified diff:
   - Start with "--- a/filepath"
   - NO markdown code fences
   - Follow standard unified diff format

3. NEVER mix formats (JSON + diff in same output)

Please retry with these requirements strictly enforced.
================================================================================
"""
    return feedback
