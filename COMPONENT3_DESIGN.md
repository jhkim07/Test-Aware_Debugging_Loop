# Component 3: Edit Script PoC - Design Document

**Date**: 2025-12-28 02:50 KST
**Phase**: Plan A - Component 3 (High Priority)
**Estimated Time**: 2.5-3 days
**Success Probability**: 70-80% (with corrections)

---

## Executive Summary

**Paradigm Shift**: From "LLM generates diff syntax" → "LLM generates edit instructions, system applies them"

**Key Innovation**: System generates anchor candidates, LLM only selects (prevents hallucination)

**Expected Impact**: 70-80% success rate (vs current 60-70%)

---

## Problem Analysis

### Current Approach (Diff Generation)
```
LLM → Raw diff string → Sanitization → Validation → patch apply
```

**Failure Points**:
1. LLM generates malformed diff syntax (hunk headers, line numbers)
2. LLM hallucinates context lines that don't exist
3. LLM miscalculates line numbers after edits
4. Sanitization can't fix all LLM errors

**Example Failure** (Phase 2.2):
```diff
@@ -57,10        ← Incomplete hunk header
 ==== ========= ==== ====
 """,           ← Stray triple-quote (context line starts with space but invalid)
     )
```

---

## Proposed Approach (Edit Script)

### Architecture

```
1. System: Extract anchor candidates from source (AST/regex)
2. LLM: Generate edit plan (JSON) with anchor selection
3. System: Validate anchors exist and are unique
4. System: Apply edits deterministically
5. System: Generate diff from before/after
```

### Key Principle

**LLM should NEVER generate**:
- Diff syntax (@@ headers, line numbers)
- Context lines (risk of hallucination)
- Exact code (risk of syntax errors)

**LLM should ONLY**:
- Select from system-provided anchor candidates
- Describe what to add/remove/replace (high-level)
- Provide new code snippets (validated by system)

---

## Edit Script Format

### JSON Schema

```json
{
  "file": "path/to/file.py",
  "edits": [
    {
      "type": "insert_after",
      "anchor": {
        "type": "function_definition",
        "name": "test_basic_case",
        "candidates": ["def test_basic_case():", "class TestBasic:", ...],
        "selected": "def test_basic_case():"
      },
      "content": "def test_new_case():\n    assert True\n",
      "description": "Add new test case after existing test"
    },
    {
      "type": "replace",
      "anchor": {
        "type": "line_pattern",
        "pattern": "right = np.eye(right)",
        "candidates": ["    right = np.eye(right)", "    # Use identity matrix"],
        "selected": "    right = np.eye(right)"
      },
      "content": "    right = np.eye(right.shape[1])",
      "description": "Fix identity matrix dimension"
    }
  ]
}
```

### Edit Types

1. **insert_before**: Add content before anchor
2. **insert_after**: Add content after anchor
3. **replace**: Replace anchor with content
4. **delete**: Remove anchor

### Anchor Types

1. **function_definition**: `def function_name(...):`
2. **class_definition**: `class ClassName:`
3. **line_pattern**: Exact line match
4. **import_statement**: `import X` or `from X import Y`
5. **decorator**: `@decorator_name`

---

## System Anchor Generation

### Strategy: AST-Based Extraction

```python
import ast

def extract_anchor_candidates(source_code: str, edit_context: dict) -> dict:
    """
    Extract anchor candidates using AST.

    Args:
        source_code: File content
        edit_context: Dict with target_line, search_range, etc.

    Returns:
        {
            'function_definitions': [...],
            'class_definitions': [...],
            'line_patterns': [...],
            'import_statements': [...]
        }
    """
    tree = ast.parse(source_code)

    candidates = {
        'function_definitions': [],
        'class_definitions': [],
        'line_patterns': [],
        'import_statements': []
    }

    # Visit all nodes
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Extract function signature
            lineno = node.lineno
            line = source_code.split('\n')[lineno - 1]
            candidates['function_definitions'].append({
                'name': node.name,
                'line': line.strip(),
                'lineno': lineno,
                'end_lineno': node.end_lineno
            })

        elif isinstance(node, ast.ClassDef):
            lineno = node.lineno
            line = source_code.split('\n')[lineno - 1]
            candidates['class_definitions'].append({
                'name': node.name,
                'line': line.strip(),
                'lineno': lineno,
                'end_lineno': node.end_lineno
            })

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            lineno = node.lineno
            line = source_code.split('\n')[lineno - 1]
            candidates['import_statements'].append({
                'line': line.strip(),
                'lineno': lineno
            })

    # Add line patterns near target
    if 'target_line' in edit_context:
        target = edit_context['target_line']
        lines = source_code.split('\n')
        search_range = edit_context.get('search_range', 10)

        for offset in range(-search_range, search_range + 1):
            idx = target + offset - 1  # 0-indexed
            if 0 <= idx < len(lines):
                line = lines[idx]
                if line.strip():  # Non-empty
                    candidates['line_patterns'].append({
                        'line': line,
                        'lineno': idx + 1
                    })

    return candidates
```

### Candidate Ranking

```python
def rank_candidates(candidates: list, context: dict) -> list:
    """
    Rank candidates by uniqueness and proximity to target.

    Scoring:
    - Uniqueness: Higher if appears only once
    - Proximity: Higher if close to target line
    - Complexity: Higher if contains distinctive tokens
    """
    scores = []

    for candidate in candidates:
        score = 0

        # Uniqueness (0-10)
        if candidate['count'] == 1:
            score += 10
        elif candidate['count'] == 2:
            score += 5

        # Proximity (0-10)
        if 'target_line' in context:
            distance = abs(candidate['lineno'] - context['target_line'])
            proximity = max(0, 10 - distance)
            score += proximity

        # Complexity (0-5)
        tokens = len(candidate['line'].split())
        if tokens > 5:
            score += 5
        elif tokens > 3:
            score += 3

        scores.append((score, candidate))

    # Sort by score (descending)
    scores.sort(key=lambda x: x[0], reverse=True)

    return [c for (s, c) in scores]
```

---

## LLM Prompt Design

### System Prompt

```
You are an expert code editor assistant.

Your task: Generate structured edit instructions (JSON) to modify source code.

CRITICAL RULES:
1. You MUST select anchors from the provided candidates list
2. You CANNOT create new anchor text (risk of hallucination)
3. Each edit must have a clear, unique anchor
4. Edits are applied in order (consider side effects)

Output format: Valid JSON matching the schema below.
```

### User Prompt Template

```python
def build_edit_prompt(
    file_path: str,
    source_code: str,
    anchor_candidates: dict,
    problem_statement: str,
    reference_patch: str
) -> str:
    """Build LLM prompt for edit script generation."""

    # Show anchor candidates
    candidates_str = format_candidates(anchor_candidates)

    # Show reference patch (for guidance)
    reference_preview = reference_patch[:2000] if reference_patch else "N/A"

    return f"""Generate edit instructions to fix the bug.

File: {file_path}

Problem:
{problem_statement[:500]}

Reference Patch (for guidance):
{reference_preview}

Available Anchor Candidates:
{candidates_str}

Task:
1. Identify which lines need to be modified
2. Select appropriate anchors from candidates above
3. Generate edit instructions in JSON format

Output Schema:
{{
  "file": "{file_path}",
  "edits": [
    {{
      "type": "insert_after" | "replace" | "delete",
      "anchor": {{
        "type": "function_definition" | "line_pattern",
        "selected": "<exact text from candidates>"
      }},
      "content": "<new code>",
      "description": "<why this edit>"
    }}
  ]
}}

CRITICAL:
- anchor.selected MUST be exact match from candidates above
- Do NOT invent anchor text
- Edits are applied in order

Output JSON only:"""
```

---

## Edit Application Engine

### Core Algorithm

```python
def apply_edit_script(
    source_code: str,
    edit_script: dict,
    validate: bool = True
) -> tuple[str, list[str]]:
    """
    Apply edit script to source code.

    Args:
        source_code: Original file content
        edit_script: Parsed JSON edit instructions
        validate: Whether to validate anchors

    Returns:
        (modified_code, list_of_errors)
    """
    lines = source_code.split('\n')
    errors = []

    # Apply edits in order
    for i, edit in enumerate(edit_script['edits']):
        edit_type = edit['type']
        anchor = edit['anchor']
        content = edit.get('content', '')

        # Find anchor line
        anchor_line, anchor_idx = find_anchor(lines, anchor)

        if anchor_line is None:
            errors.append(f"Edit {i+1}: Anchor not found: {anchor['selected']}")
            continue

        # Validate uniqueness
        if validate:
            count = count_anchor_occurrences(lines, anchor)
            if count > 1:
                errors.append(f"Edit {i+1}: Anchor not unique ({count} occurrences)")
                continue

        # Apply edit
        try:
            lines = apply_single_edit(lines, edit_type, anchor_idx, content)
        except Exception as e:
            errors.append(f"Edit {i+1}: Application failed: {e}")

    modified_code = '\n'.join(lines)
    return (modified_code, errors)


def apply_single_edit(
    lines: list[str],
    edit_type: str,
    anchor_idx: int,
    content: str
) -> list[str]:
    """Apply a single edit operation."""

    if edit_type == 'insert_after':
        # Insert content after anchor
        new_lines = lines[:anchor_idx+1]
        new_lines.extend(content.split('\n'))
        new_lines.extend(lines[anchor_idx+1:])
        return new_lines

    elif edit_type == 'insert_before':
        # Insert content before anchor
        new_lines = lines[:anchor_idx]
        new_lines.extend(content.split('\n'))
        new_lines.extend(lines[anchor_idx:])
        return new_lines

    elif edit_type == 'replace':
        # Replace anchor with content
        new_lines = lines[:anchor_idx]
        new_lines.extend(content.split('\n'))
        new_lines.extend(lines[anchor_idx+1:])
        return new_lines

    elif edit_type == 'delete':
        # Remove anchor line
        new_lines = lines[:anchor_idx] + lines[anchor_idx+1:]
        return new_lines

    else:
        raise ValueError(f"Unknown edit type: {edit_type}")
```

### Anchor Finding

```python
def find_anchor(lines: list[str], anchor: dict) -> tuple[str, int]:
    """
    Find anchor line in source code.

    Returns:
        (anchor_line_text, line_index) or (None, None) if not found
    """
    anchor_type = anchor['type']
    selected = anchor['selected']

    if anchor_type == 'line_pattern':
        # Exact match
        for i, line in enumerate(lines):
            if line.strip() == selected.strip():
                return (line, i)

    elif anchor_type == 'function_definition':
        # Match function def
        for i, line in enumerate(lines):
            if line.strip().startswith('def ') and selected in line:
                return (line, i)

    elif anchor_type == 'class_definition':
        # Match class def
        for i, line in enumerate(lines):
            if line.strip().startswith('class ') and selected in line:
                return (line, i)

    return (None, None)


def count_anchor_occurrences(lines: list[str], anchor: dict) -> int:
    """Count how many times anchor appears."""
    count = 0
    selected = anchor['selected']

    for line in lines:
        if selected.strip() in line.strip():
            count += 1

    return count
```

---

## Failure Modes and Handling

### F1: Anchor Not Found

**Cause**: LLM selected anchor that doesn't exist (hallucination)

**Detection**: `find_anchor()` returns None

**Handling**:
```python
if anchor_line is None:
    errors.append(f"Anchor not found: {anchor['selected']}")
    # Skip this edit, continue with next
    continue
```

**Prevention**: Only show LLM actual anchor candidates from source

---

### F2: Anchor Not Unique

**Cause**: Selected anchor appears multiple times

**Detection**: `count_anchor_occurrences() > 1`

**Handling**:
```python
if count > 1:
    errors.append(f"Anchor not unique: {count} occurrences")
    # Try to use additional context (line number hint)
    # Or skip edit
    continue
```

**Prevention**: Rank candidates by uniqueness, prefer unique anchors

---

### F3: Edit Applied But Tests Fail

**Cause**: Logical error in edit (correct syntax, wrong logic)

**Detection**: Tests fail after patch apply

**Handling**:
- This is expected (iteration continues)
- Failure feedback given to LLM for next iteration
- Same as current system

---

## Implementation Plan

### Phase 3.1: Core Infrastructure (Day 1, 6-8 hours)

**Files to Create**:
1. `bench_agent/editor/anchor_extractor.py` - AST-based anchor extraction
2. `bench_agent/editor/edit_applier.py` - Edit application engine
3. `bench_agent/editor/edit_validator.py` - Anchor validation
4. `bench_agent/editor/diff_generator.py` - Generate diff from before/after

**Files to Modify**:
1. `bench_agent/agent/patch_author.py` - Add edit script mode
2. `scripts/run_mvp.py` - Add USE_EDIT_SCRIPT flag

---

### Phase 3.2: LLM Integration (Day 1-2, 6-8 hours)

**Files to Create**:
1. `bench_agent/agent/edit_script_generator.py` - LLM prompts for edit generation
2. `bench_agent/editor/candidate_ranker.py` - Rank anchor candidates

**Integration Points**:
- Modify `propose_patch()` to use edit script when flag enabled
- Add fallback to diff mode if edit script fails

---

### Phase 3.3: Testing & Iteration (Day 2-3, 8-12 hours)

**Test Cases**:
1. Simple function replacement
2. Line insertion after anchor
3. Multiple edits in sequence
4. Ambiguous anchor (should fail gracefully)

**Test Instance**: astropy-14182

**Success Criteria**:
- Edit script generates and applies without errors
- TSS ≥ 0.65 (improvement over 0.5-0.6 baseline)
- BRS = 1.0 (maintain baseline)

---

## Expected Outcomes

### Best Case (70-80% probability)
- Edit script applies successfully
- TSS improves to 0.65-0.75
- Fewer malformed patch errors
- **Decision**: Adopt edit script as primary mode

### Medium Case (15-20% probability)
- Edit script works but no significant improvement
- TSS ~0.55-0.60 (marginal)
- **Decision**: Keep as experimental feature, need more iteration

### Worst Case (5-10% probability)
- Edit script fails to apply
- Anchor finding errors
- **Decision**: Rollback, investigate issues, consider redesign

---

## Success Metrics

### Primary Metrics
1. **TSS (Test Strength Score)**: Target ≥ 0.65 (vs 0.5 baseline on 14182)
2. **Patch Apply Success**: ≥ 80% (first iteration)
3. **Anchor Finding Accuracy**: ≥ 90%

### Secondary Metrics
1. **Edit Generation Time**: ≤ 30s (comparable to diff gen)
2. **Error Recovery**: Graceful fallback to diff mode
3. **Code Quality**: Passes syntax validation

---

## Risk Mitigation

### Risk 1: Anchor Extraction Fails
**Probability**: Medium
**Impact**: High
**Mitigation**: Comprehensive AST parsing + regex fallback

### Risk 2: LLM Ignores Candidate List
**Probability**: Low-Medium
**Impact**: High
**Mitigation**: Strong prompt engineering + validation

### Risk 3: Edit Order Dependencies
**Probability**: Medium
**Impact**: Medium
**Mitigation**: Clear documentation + examples in prompt

---

## Rollback Plan

If Component 3 fails after 3 days:

1. ✅ Document findings in COMPONENT3_FAILURE_REPORT.md
2. ✅ Preserve code in feature branch (edit-script-poc)
3. ✅ Return to P0.9.1 baseline
4. ✅ Consider alternative improvements

---

## Next Steps

1. **User Approval**: Confirm Component 3 design
2. **Phase 3.1**: Implement core infrastructure (6-8 hours)
3. **Phase 3.2**: LLM integration (6-8 hours)
4. **Phase 3.3**: Testing & iteration (8-12 hours)

**Total Estimated Time**: 2.5-3 days

---

**Design Status**: Ready for implementation
**Approval Required**: User confirmation to proceed
**Estimated Completion**: 2025-12-30 EOD

---

**Design Document By**: Claude Code - Component 3 Architecture Team
**Date**: 2025-12-28 02:50 KST
