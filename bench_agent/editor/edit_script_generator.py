"""
Component 3: Edit Script Generator

Generates LLM prompts for edit script creation.
System extracts anchors, LLM selects and describes edits.
"""

from typing import Dict, List, Optional
from .anchor_extractor import (
    extract_anchor_candidates,
    filter_top_level_only,
    format_candidates_for_prompt,
    get_candidates_near_line
)


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

EDIT_SCRIPT_SYSTEM_PROMPT = """You are a code editing assistant that generates structured edit instructions.

Your task is to generate edit scripts in JSON format. Edit scripts specify:
1. Which anchor points to use (from system-provided candidates)
2. What type of edit to perform (insert_before, insert_after, replace, delete)
3. What content to insert/replace

CRITICAL RULES:
- ONLY use anchors from the provided candidate list
- DO NOT invent or hallucinate anchor text
- Anchors must match EXACTLY as shown in candidates
- Be precise and minimal - only change what's necessary

Edit script format:
{
  "file": "path/to/file.py",
  "edits": [
    {
      "type": "insert_after",  // or: insert_before, replace, delete
      "anchor": {
        "type": "function_def",  // type from candidates
        "selected": "def test_basic():"  // EXACT text from candidates
      },
      "content": "def test_new():\\n    assert True\\n",
      "description": "Add new test case"
    }
  ]
}

Available edit types:

1. "replace" - MODIFY existing code (most common)
   Use when: Changing existing lines, updating values, fixing bugs
   Example: Change "end_line = -1" to "end_line = 10"
   ✓ Correct: {"type": "replace", "anchor": {"selected": "end_line = -1"}, "content": "end_line = 10"}
   ✗ WRONG:  {"type": "insert_before", ...} ← Creates DUPLICATE code!

   CRITICAL: "replace" REMOVES the anchor line and adds new content
   Result: Old code GONE, new code IN PLACE

2. "insert_after" - ADD new code after anchor
   Use when: Adding NEW functions/methods that didn't exist before
   Example: Add a new test function after existing test
   ✓ Correct: {"type": "insert_after", "anchor": {"selected": "def test_old():"}, "content": "def test_new():\\n    pass"}

   WARNING: insert_after on a function adds code INSIDE that function!
   For adding new functions, use "insert_before" on the NEXT function instead.

3. "insert_before" - ADD new code before anchor
   Use when: Adding imports, adding new functions before an anchor
   Example: Add new function before existing function
   ✓ Correct: {"type": "insert_before", "anchor": {"selected": "def existing():"}, "content": "def new():\\n    pass\\n"}

4. "delete" - REMOVE code
   Use when: Removing unnecessary code
   Example: {"type": "delete", "anchor": {"selected": "old_line = 1"}}
   No "content" field needed.

DECISION FLOWCHART:
- Changing existing code? → Use "replace"
- Adding brand new code? → Use "insert_before" or "insert_after"
- Removing code? → Use "delete"
"""


TEST_EDIT_SCRIPT_PROMPT_TEMPLATE = """Generate edit script to add/modify tests.

FILE: {filepath}

TASK: {task_description}

AVAILABLE ANCHORS (select from these only):
{anchor_candidates}

SOURCE CODE:
```python
{source_code}
```

REQUIREMENTS:
1. Add tests to cover the issue described in the task
2. ONLY use anchors from the "Available Anchors" list above
3. To add new test functions: Use insert_before on the NEXT function definition (not insert_after on previous function)
4. CRITICAL: insert_after on a function definition inserts INSIDE that function (wrong!). Always use insert_before on the next function.
5. Preserve existing test structure and style
6. Return valid JSON edit script

Generate the edit script now:"""


CODE_EDIT_SCRIPT_PROMPT_TEMPLATE = """Generate edit script to fix code.

FILE: {filepath}

TASK: {task_description}

TEST RESULTS (what needs to be fixed):
{test_results}

AVAILABLE ANCHORS (select from these only):
{anchor_candidates}

SOURCE CODE:
```python
{source_code}
```

REQUIREMENTS:
1. Fix the code to pass the failing tests
2. ONLY use anchors from the "Available Anchors" list above
3. Choose correct edit type:
   - MODIFYING existing code? → Use "replace" (removes old, adds new)
   - ADDING completely new code? → Use "insert_before" or "insert_after"
   - Example: To fix "end_line = -1", use "replace" NOT "insert"
4. Preserve existing code structure
5. Return valid JSON edit script

CRITICAL: Using "insert" when you should use "replace" creates DUPLICATE code!

Generate the edit script now:"""


# ============================================================================
# PROMPT GENERATION
# ============================================================================

def generate_test_edit_prompt(
    filepath: str,
    source_code: str,
    task_description: str,
    target_line: Optional[int] = None,
    max_candidates: int = 20
) -> str:
    """
    Generate LLM prompt for test edit script creation.

    Args:
        filepath: Path to file being edited
        source_code: Source code content
        task_description: What tests to add
        target_line: Optional line number to focus anchor search
        max_candidates: Maximum anchor candidates to show

    Returns:
        Formatted prompt string
    """
    # Extract anchor candidates
    candidates = extract_anchor_candidates(
        source_code,
        target_line=target_line,
        search_range=30
    )

    # Filter to top-level only (prevents malformed diffs from nested anchors)
    filtered_candidates = filter_top_level_only(candidates, allow_single_indent=False)

    # Format candidates for prompt
    candidates_text = format_candidates_for_prompt(
        filtered_candidates,
        max_per_type=max_candidates
    )

    # Fill template
    prompt = TEST_EDIT_SCRIPT_PROMPT_TEMPLATE.format(
        filepath=filepath,
        task_description=task_description,
        anchor_candidates=candidates_text,
        source_code=source_code
    )

    return prompt


def generate_code_edit_prompt(
    filepath: str,
    source_code: str,
    task_description: str,
    test_results: str,
    target_line: Optional[int] = None,
    max_candidates: int = 20
) -> str:
    """
    Generate LLM prompt for code edit script creation.

    Args:
        filepath: Path to file being edited
        source_code: Source code content
        task_description: What to fix
        test_results: Test failure information
        target_line: Optional line number to focus anchor search
        max_candidates: Maximum anchor candidates to show

    Returns:
        Formatted prompt string
    """
    # Extract anchor candidates
    candidates = extract_anchor_candidates(
        source_code,
        target_line=target_line,
        search_range=30
    )

    # Filter to top-level only (prevents malformed diffs from nested anchors)
    filtered_candidates = filter_top_level_only(candidates, allow_single_indent=False)

    # Format candidates for prompt
    candidates_text = format_candidates_for_prompt(
        filtered_candidates,
        max_per_type=max_candidates
    )

    # Fill template
    prompt = CODE_EDIT_SCRIPT_PROMPT_TEMPLATE.format(
        filepath=filepath,
        task_description=task_description,
        test_results=test_results,
        anchor_candidates=candidates_text,
        source_code=source_code
    )

    return prompt


# ============================================================================
# FOCUSED PROMPT GENERATION
# ============================================================================

def generate_focused_edit_prompt(
    filepath: str,
    source_code: str,
    task_description: str,
    focus_area: Dict,
    edit_type: str = "code"
) -> str:
    """
    Generate focused prompt with anchor candidates near specific area.

    Args:
        filepath: Path to file
        source_code: Source code
        task_description: What to do
        focus_area: Dict with 'start_line', 'end_line', or 'target_line'
        edit_type: "test" or "code"

    Returns:
        Focused prompt string
    """
    target_line = focus_area.get('target_line')

    if target_line is None:
        # Compute from start/end
        start = focus_area.get('start_line', 1)
        end = focus_area.get('end_line', 1)
        target_line = (start + end) // 2

    # Extract ALL candidates first
    all_candidates = extract_anchor_candidates(source_code)

    # Get candidates near target
    nearby = get_candidates_near_line(
        all_candidates,
        target_line,
        max_distance=20
    )

    # Convert back to dict format for formatting
    focused_candidates = {
        'function_definitions': [c for c in nearby if c.type == 'function_def'],
        'class_definitions': [c for c in nearby if c.type == 'class_def'],
        'line_patterns': [c for c in nearby if c.type == 'line_pattern'],
        'import_statements': [c for c in nearby if c.type == 'import_stmt'],
        'decorators': [c for c in nearby if c.type == 'decorator'],
    }

    # Format
    candidates_text = format_candidates_for_prompt(
        focused_candidates,
        max_per_type=10
    )

    # Use appropriate template
    if edit_type == "test":
        template = TEST_EDIT_SCRIPT_PROMPT_TEMPLATE
        prompt = template.format(
            filepath=filepath,
            task_description=task_description,
            anchor_candidates=candidates_text,
            source_code=source_code
        )
    else:
        # For code edits, need test_results
        test_results = focus_area.get('test_results', 'No test results provided')
        template = CODE_EDIT_SCRIPT_PROMPT_TEMPLATE
        prompt = template.format(
            filepath=filepath,
            task_description=task_description,
            test_results=test_results,
            anchor_candidates=candidates_text,
            source_code=source_code
        )

    return prompt


# ============================================================================
# MULTI-STEP EDIT PROMPTS
# ============================================================================

def generate_iterative_edit_prompt(
    filepath: str,
    source_code: str,
    task_description: str,
    previous_attempts: List[Dict],
    test_results: str
) -> str:
    """
    Generate prompt for iterative editing (after previous attempt failed).

    Args:
        filepath: Path to file
        source_code: Current source code
        task_description: What to fix
        previous_attempts: List of previous edit scripts and their results
        test_results: Latest test results

    Returns:
        Prompt with context from previous attempts
    """
    # Extract candidates
    candidates = extract_anchor_candidates(source_code)
    candidates_text = format_candidates_for_prompt(candidates)

    # Format previous attempts
    attempts_text = _format_previous_attempts(previous_attempts)

    # Build prompt
    prompt = f"""Generate edit script to fix code (iteration {len(previous_attempts) + 1}).

FILE: {filepath}

TASK: {task_description}

PREVIOUS ATTEMPTS:
{attempts_text}

LATEST TEST RESULTS:
{test_results}

AVAILABLE ANCHORS (select from these only):
{candidates_text}

CURRENT SOURCE CODE:
```python
{source_code}
```

REQUIREMENTS:
1. Learn from previous failed attempts
2. Try a different approach
3. ONLY use anchors from the "Available Anchors" list
4. Return valid JSON edit script

Generate the edit script now:"""

    return prompt


def _format_previous_attempts(attempts: List[Dict]) -> str:
    """Format previous attempts for prompt."""
    if not attempts:
        return "None (first attempt)"

    lines = []
    for i, attempt in enumerate(attempts, 1):
        lines.append(f"\nAttempt {i}:")
        lines.append(f"  Edits: {len(attempt.get('edits', []))}")
        lines.append(f"  Result: {attempt.get('result', 'Unknown')}")

        # Show error if available
        error = attempt.get('error')
        if error:
            lines.append(f"  Error: {error}")

    return '\n'.join(lines)


# ============================================================================
# PROMPT VALIDATION
# ============================================================================

def validate_prompt_length(prompt: str, max_tokens: int = 8000) -> tuple[bool, str]:
    """
    Validate prompt is not too long.

    Args:
        prompt: Prompt string
        max_tokens: Maximum allowed tokens (rough estimate: 1 token ≈ 4 chars)

    Returns:
        (is_valid, message)
    """
    # Rough token estimate
    estimated_tokens = len(prompt) // 4

    if estimated_tokens > max_tokens:
        return (
            False,
            f"Prompt too long: ~{estimated_tokens} tokens (max {max_tokens})"
        )

    return (True, "Prompt length OK")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_edit_prompt(
    stage: str,
    filepath: str,
    source_code: str,
    task_description: str,
    test_results: Optional[str] = None,
    target_line: Optional[int] = None
) -> str:
    """
    Create edit prompt for given stage.

    Convenience function that routes to appropriate prompt generator.

    Args:
        stage: "test" or "code"
        filepath: Path to file
        source_code: Source code
        task_description: Task description
        test_results: Test results (required for code stage)
        target_line: Optional focus line

    Returns:
        Formatted prompt
    """
    if stage == "test":
        return generate_test_edit_prompt(
            filepath=filepath,
            source_code=source_code,
            task_description=task_description,
            target_line=target_line
        )
    elif stage == "code":
        if test_results is None:
            test_results = "No test results available"

        return generate_code_edit_prompt(
            filepath=filepath,
            source_code=source_code,
            task_description=task_description,
            test_results=test_results,
            target_line=target_line
        )
    else:
        raise ValueError(f"Unknown stage: {stage}")
