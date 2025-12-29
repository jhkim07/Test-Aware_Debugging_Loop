# Phase 2.2 Design: Enhanced Diff Writer

**Date**: 2025-12-28
**Objective**: Fix Diff Writer formatting issues identified in Phase 2.1 test
**Target**: TSS 0.5 → 0.60+ on astropy-14182

---

## Problem Statement

Phase 2.1 test showed that the 2-stage architecture executes correctly, but the Diff Writer (Stage B) generates malformed diffs:

1. **Triple-quoted string remnants** in test diffs (line 16 error)
2. **Incomplete hunk headers** in code diffs (`@@ -57,10` instead of `@@ -57,10 +XX,YY @@`)
3. **No iteration-to-iteration learning** (same errors repeated 3 times)

Result: TSS = 0.5 (no improvement over baseline)

---

## Solution Design

### Component 1: Syntax Validation Layer

**Purpose**: Catch malformed diffs before they're returned

**Implementation**: Create `bench_agent/agent/diff_syntax_validator.py`

```python
def validate_diff_syntax(diff: str) -> tuple[bool, list[str]]:
    """
    Validate diff syntax and return (is_valid, list_of_errors).

    Checks:
    1. All hunks have complete headers: @@ -X,Y +A,B @@
    2. No stray triple-quotes outside context
    3. No markdown markers (```)
    4. Valid line prefixes (+, -, space)
    5. Proper file headers (diff --git, ---, +++)
    """
    errors = []

    # Check 1: Hunk header completeness
    hunk_pattern = r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@'
    incomplete_hunks = re.findall(r'@@ -\d+,\d+(?!\s*\+)', diff)
    if incomplete_hunks:
        errors.append(f"Incomplete hunk headers: {incomplete_hunks}")

    # Check 2: Stray triple-quotes
    lines = diff.split('\n')
    for i, line in enumerate(lines):
        if '"""' in line or "'''" in line:
            # Only allow in context (lines starting with space, +, or -)
            if not line.startswith((' ', '+', '-')):
                errors.append(f"Stray triple-quote at line {i+1}: {line[:50]}")

    # Check 3: Markdown markers
    if '```' in diff:
        errors.append("Markdown code block markers found")

    # Check 4: File headers
    if not diff.startswith('diff --git'):
        errors.append("Missing 'diff --git' header")

    return (len(errors) == 0, errors)
```

**Integration Point**: In `diff_writer.py`, call validator before returning:

```python
def render_diff(...) -> str:
    response = chat(client, model, messages).strip()

    # Remove markdown if present
    if response.startswith("```"):
        response = clean_markdown(response)

    # NEW: Syntax validation
    is_valid, errors = validate_diff_syntax(response)
    if not is_valid:
        raise ValueError(f"Diff syntax errors: {errors}")

    return response
```

---

### Component 2: Multi-Line String Sanitizer

**Purpose**: Clean up triple-quoted strings in diff context

**Implementation**: Add to `diff_syntax_validator.py`

```python
def sanitize_multiline_strings(diff: str) -> str:
    """
    Remove stray triple-quoted string remnants from diff.

    Strategy:
    1. Identify lines with """ or ''' that are NOT valid context
    2. Remove them if they appear outside proper diff syntax
    3. Preserve valid multi-line strings in context
    """
    lines = diff.split('\n')
    cleaned_lines = []
    in_hunk = False

    for line in lines:
        # Track if we're in a hunk (after @@ header)
        if line.startswith('@@'):
            in_hunk = True
            cleaned_lines.append(line)
            continue

        # If in hunk, check for stray quotes
        if in_hunk:
            # Valid context line: starts with space, +, or -
            if line.startswith((' ', '+', '-')):
                cleaned_lines.append(line)
            else:
                # Invalid line with quotes - likely stray
                if '"""' in line or "'''" in line:
                    # Skip this line (it's malformed)
                    continue
                else:
                    cleaned_lines.append(line)
        else:
            # Outside hunk (file header, etc.)
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)
```

**Integration**: Call in `render_diff` after LLM response:

```python
response = chat(client, model, messages).strip()
response = clean_markdown(response)
response = sanitize_multiline_strings(response)  # NEW
is_valid, errors = validate_diff_syntax(response)
```

---

### Component 3: Hunk Header Completion

**Purpose**: Fix incomplete hunk headers automatically

**Implementation**: Add to `diff_syntax_validator.py`

```python
def complete_hunk_headers(diff: str) -> str:
    """
    Fix incomplete hunk headers by calculating missing line counts.

    Incomplete: @@ -57,10
    Complete:   @@ -57,10 +67,15 @@

    Strategy:
    1. Find incomplete headers (missing + side)
    2. Count lines in hunk to calculate new_count
    3. Calculate new_start from old_start and context
    4. Replace with complete header
    """
    import re

    lines = diff.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for incomplete hunk header
        match = re.match(r'(@@ -(\d+),(\d+))(\s|$)', line)
        if match and '+' not in line:
            # Incomplete header found
            old_start = int(match.group(2))
            old_count = int(match.group(3))

            # Count hunk lines to calculate new side
            j = i + 1
            added = 0
            removed = 0
            while j < len(lines) and not lines[j].startswith('@@'):
                if lines[j].startswith('+'):
                    added += 1
                elif lines[j].startswith('-'):
                    removed += 1
                j += 1

            # Calculate new side
            new_start = old_start
            new_count = old_count - removed + added

            # Replace with complete header
            complete_header = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
            result.append(complete_header)
        else:
            result.append(line)

        i += 1

    return '\n'.join(result)
```

**Integration**: Call before validation:

```python
response = clean_markdown(response)
response = sanitize_multiline_strings(response)
response = complete_hunk_headers(response)  # NEW
is_valid, errors = validate_diff_syntax(response)
```

---

### Component 4: Iteration Feedback

**Purpose**: Learn from previous iteration errors

**Implementation**: Modify `two_stage.py` to pass feedback to Writer

```python
def generate_diff_two_stage(
    role: str,
    client,
    context: Dict,
    mode: str = "research",
    max_retries: int = 2,
    previous_errors: list[str] = None  # NEW
) -> str:
    """
    Generate diff with iteration feedback.

    Args:
        previous_errors: List of errors from previous iterations
    """

    # Stage A: Planner (unchanged)
    plan = generate_plan(role, client, planner_model, context, mode)

    # Stage B: Diff Writer with feedback
    for attempt in range(max_retries + 1):
        try:
            # NEW: Add previous errors to context
            writer_context = context.copy()
            if previous_errors:
                writer_context['previous_errors'] = previous_errors

            diff = render_diff(role, plan, client, writer_model, writer_context)

            # Apply sanitizers
            diff = sanitize_multiline_strings(diff)
            diff = complete_hunk_headers(diff)

            # Validate
            is_valid, errors = validate_diff_syntax(diff)
            if not is_valid:
                previous_errors = errors  # Feed errors to next attempt
                continue

            return diff
        except Exception as e:
            if attempt < max_retries:
                continue

    raise RuntimeError(f"Writer failed after {max_retries + 1} attempts")
```

**Diff Writer Prompt Enhancement** (`diff_writer.py`):

```python
def build_writer_prompt_test(plan: Dict, context: Dict) -> str:
    """Build prompt with previous error feedback."""

    # ... existing code ...

    error_feedback = ""
    if context.get('previous_errors'):
        error_list = '\n'.join(f"  - {err}" for err in context['previous_errors'])
        error_feedback = f"""
CRITICAL - Previous attempt had these errors:
{error_list}

You MUST avoid these errors in this attempt.
"""

    return f"""Generate unified diff for test changes.

Plan:
{json.dumps(plan, indent=2)}

{error_feedback}

{reference_hint}

Requirements:
- File to modify: {plan.get('test_file', 'N/A')}
- Approach: {plan.get('approach', 'N/A')}
- NO stray triple-quotes outside context lines
- ALL hunk headers MUST be complete: @@ -X,Y +A,B @@

Output unified diff ONLY. Start with: diff --git a/..."""
```

---

## Implementation Plan

### Step 1: Create Syntax Validator Module
**File**: `bench_agent/agent/diff_syntax_validator.py`
**Functions**:
- `validate_diff_syntax(diff) -> (bool, list[str])`
- `sanitize_multiline_strings(diff) -> str`
- `complete_hunk_headers(diff) -> str`

### Step 2: Enhance Diff Writer
**File**: `bench_agent/agent/diff_writer.py`
**Changes**:
- Import validator functions
- Add sanitization pipeline before validation
- Enhance prompts with error feedback
- Add previous_errors parameter

### Step 3: Update Two-Stage Wrapper
**File**: `bench_agent/protocol/two_stage.py`
**Changes**:
- Add previous_errors tracking
- Pass errors to Writer on retries
- Apply sanitization pipeline
- Track and return validation results

### Step 4: Integration with run_mvp.py
**File**: `scripts/run_mvp.py`
**Changes**:
- Pass previous iteration errors to two_stage calls
- Track patch apply errors across iterations
- Feed malformed patch errors back to next iteration

---

## Success Criteria

### Immediate (Phase 2.2 Test)
- ✅ No malformed patch errors (eliminate "Malformed patch at line 16")
- ✅ All hunk headers complete (`@@ -X,Y +A,B @@`)
- ✅ No triple-quoted string remnants in invalid positions
- ✅ TSS ≥ 0.60 (improvement over 0.5 baseline)

### Stretch Goals
- TSS ≥ 0.65 (original Phase 2 target)
- Patch applies successfully on first iteration
- BRS = 1.0 (maintain baseline)

---

## Testing Strategy

### Test 1: Syntax Validator Unit Tests
Create `tests/test_diff_syntax_validator.py`:
```python
def test_incomplete_hunk_header():
    diff = """diff --git a/file.py b/file.py
@@ -10,5
+new line
"""
    is_valid, errors = validate_diff_syntax(diff)
    assert not is_valid
    assert "Incomplete hunk" in errors[0]

def test_complete_hunk_headers():
    diff = """@@ -10,5
+new line
-old line
"""
    completed = complete_hunk_headers(diff)
    assert "@@ -10,5 +10,5 @@" in completed
```

### Test 2: End-to-End Test
Run on astropy-14182 with Phase 2.2:
```bash
USE_TWO_STAGE=1 PYTHONPATH=... python scripts/run_mvp.py \
  --config configs/p091_phase2_test.yaml \
  --run-id p091-phase2.2-test-$(date +%Y%m%d-%H%M%S)
```

Expected:
- No malformed patch errors in log
- TSS ≥ 0.60
- At least 1 iteration with successful patch apply

---

## Rollback Plan

If Phase 2.2 test shows **TSS < 0.60** (less than 20% improvement):

1. **Document failure** in P091_PHASE2.2_FAILURE_REPORT.md
2. **Rollback to baseline**:
   ```bash
   git checkout main
   git branch -D phase2-plan-then-diff
   ```
3. **Tag and close Phase 2**:
   - Update documentation to mark Phase 2 as "explored but not viable"
   - Focus on alternative improvements (e.g., better test analysis, reference patch extraction)

---

## Timeline

- **Implementation**: 4-6 hours (syntax validator + integration)
- **Testing**: 1-2 hours (unit tests + end-to-end)
- **Analysis**: 1 hour (results evaluation)
- **Total**: 6-9 hours (~1 day)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Sanitizers break valid diffs | Medium | High | Unit tests with valid diffs |
| Hunk calculation incorrect | Medium | High | Test with reference patches |
| No improvement over 2.1 | Medium | Medium | Have rollback plan ready |
| Regression on other instances | Low | High | Run regression test after |

---

## Next Steps

1. ✅ Review and approve Phase 2.2 design
2. Create `diff_syntax_validator.py` module
3. Enhance `diff_writer.py` with sanitization
4. Update `two_stage.py` with feedback loop
5. Test on astropy-14182
6. Evaluate results (TSS ≥ 0.60 → continue, else rollback)

---

**Design Status**: Ready for implementation
**Approval Required**: User confirmation to proceed
**Estimated Completion**: 2025-12-28 EOD
