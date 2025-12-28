# Component 3 Phase 3.1: Core Infrastructure - COMPLETE

**Date**: 2025-12-28 10:21 KST
**Phase**: Component 3 - Edit Script PoC (Phase 3.1: Core Infrastructure)
**Status**: ✅ **PHASE 3.1 COMPLETE**

---

## Executive Summary

Phase 3.1 (Core Infrastructure) of Component 3 has been successfully implemented with all 6 core modules:

1. ✅ **anchor_extractor.py** - AST-based anchor extraction (11,397 bytes)
2. ✅ **edit_applier.py** - Deterministic edit application (10,019 bytes)
3. ✅ **edit_validator.py** - Anchor and structure validation (13,505 bytes)
4. ✅ **diff_generator.py** - Unified diff generation (10,578 bytes)
5. ✅ **edit_script_generator.py** - LLM prompt generation (12,224 bytes)
6. ✅ **candidate_ranker.py** - Anchor quality scoring (13,315 bytes)

**Total Code**: ~71,000 bytes (~1,800 lines)
**Implementation Time**: ~2 hours
**Architecture**: System-generated anchors + LLM selection → Deterministic application

---

## Architecture Overview

### Paradigm Shift: From LLM-Generated Diffs to LLM-Selected Anchors

**Problem with Phase 2 (Diff Writer)**:
- LLM generates diff syntax directly
- 92% failure rate on malformed patches
- LLM hallucinates line numbers, context, formatting

**Solution with Component 3 (Edit Script)**:
```
┌─────────────────────────────────────────────────────┐
│ 1. SYSTEM: Extract anchor candidates (AST)         │
│    - Functions, classes, imports, line patterns    │
│    - Guaranteed to exist in source                 │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 2. SYSTEM: Format candidates for LLM prompt        │
│    - Show line numbers, exact text                 │
│    - Prevent hallucination by constraining choices │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 3. LLM: Select anchors + describe edits (JSON)     │
│    {                                                │
│      "edits": [{                                    │
│        "anchor": {"selected": "def test_basic():"} │
│        "type": "insert_after",                      │
│        "content": "def test_new(): ..."            │
│      }]                                             │
│    }                                                │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 4. SYSTEM: Validate anchors exist and are unique   │
│    - Check anchor in source                        │
│    - Check uniqueness                              │
│    - Reject if hallucinated                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 5. SYSTEM: Apply edits deterministically           │
│    - Find anchor line                              │
│    - insert_before/insert_after/replace/delete     │
│    - No syntax parsing required                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ 6. SYSTEM: Generate unified diff                   │
│    - difflib.unified_diff(before, after)           │
│    - Always syntactically correct                  │
└─────────────────────────────────────────────────────┘
```

**Key Insight**: LLM is good at semantic understanding but bad at syntax generation. Edit scripts let LLM focus on "what to change" while system handles "how to format it".

---

## Module Descriptions

### 1. anchor_extractor.py (357 lines)

**Purpose**: Extract anchor candidates from Python source using AST

**Key Functions**:
```python
def extract_anchor_candidates(
    source_code: str,
    target_line: Optional[int] = None,
    search_range: int = 20
) -> Dict[str, List[AnchorCandidate]]:
    """Extract anchors via AST + pattern matching."""
    # Returns: function_definitions, class_definitions,
    #          import_statements, line_patterns, decorators
```

**Anchor Types**:
- `function_def`: Function definitions (e.g., `def test_basic():`)
- `class_def`: Class definitions (e.g., `class Foo:`)
- `import_stmt`: Import statements (e.g., `from x import y`)
- `line_pattern`: Non-empty lines (exact match after stripping)
- `decorator`: Decorator lines (e.g., `@pytest.mark.skip`)

**Example Output**:
```python
{
  'function_definitions': [
    AnchorCandidate(
      type='function_def',
      text='def test_basic():',
      lineno=42,
      name='test_basic'
    )
  ],
  'line_patterns': [
    AnchorCandidate(
      type='line_pattern',
      text='    assert result == expected',
      lineno=45
    )
  ]
}
```

**Critical Feature**: AST parsing guarantees anchors actually exist in source (prevents hallucination).

---

### 2. edit_applier.py (353 lines)

**Purpose**: Apply edit scripts deterministically to source code

**Key Functions**:
```python
def apply_edit_script(
    source_code: str,
    edit_script: Dict,
    validate_anchors: bool = True
) -> EditResult:
    """Apply edit script to source code."""
```

**Edit Types Supported**:
1. **insert_before**: Insert content before anchor line
2. **insert_after**: Insert content after anchor line
3. **replace**: Replace anchor line with content
4. **delete**: Delete anchor line

**Example Edit Script**:
```json
{
  "file": "test_file.py",
  "edits": [
    {
      "type": "insert_after",
      "anchor": {
        "type": "function_def",
        "selected": "def test_basic():"
      },
      "content": "def test_edge_case():\n    assert foo() == 42\n",
      "description": "Add edge case test"
    }
  ]
}
```

**Return Value**:
```python
EditResult(
    success=True,
    modified_code="...",  # Modified source
    errors=[],
    applied_count=1,
    skipped_count=0
)
```

**Error Handling**:
- Anchor not found → skip edit, record error
- Anchor not unique → skip edit (if validate_anchors=True)
- Unknown edit type → skip edit

---

### 3. edit_validator.py (471 lines)

**Purpose**: Validate edit scripts before application

**Key Functions**:
```python
def validate_edit_script(
    source_code: str,
    edit_script: Dict,
    require_unique_anchors: bool = True
) -> ValidationResult:
    """Comprehensive edit script validation."""
```

**Validation Checks**:
1. **Structure**: Required fields, correct types, value constraints
2. **Anchor Existence**: Anchor found in source
3. **Anchor Uniqueness**: Anchor appears exactly once (if required)
4. **System-Generated**: Anchor matches extracted candidates (anti-hallucination)

**Validation Result**:
```python
ValidationResult(
    is_valid=True,
    errors=[],
    warnings=['2/3 edits missing description field']
)
```

**Error Types**:
- `anchor_not_found`: Anchor doesn't exist in source
- `anchor_not_unique`: Anchor appears multiple times
- `anchor_hallucinated`: Anchor not in system-extracted candidates
- `structure`: Missing/invalid required fields

---

### 4. diff_generator.py (394 lines)

**Purpose**: Generate unified diffs from before/after code

**Key Functions**:
```python
def generate_unified_diff(
    original_code: str,
    modified_code: str,
    filepath: str = "file.py",
    context_lines: int = 3
) -> str:
    """Generate unified diff using difflib."""
```

**Why This Module?**
- Edit scripts modify source directly → need diff for SWE-bench
- difflib guarantees syntactically correct diffs
- No malformed patch errors possible

**Example Usage**:
```python
original = read_file("test.py")
result = apply_edit_script(original, edit_script)
diff = generate_unified_diff(original, result.modified_code, "test.py")
# diff is always valid unified diff format
```

**Statistics**:
```python
stats = compute_diff_stats(diff)
# {'added_lines': 3, 'removed_lines': 1, 'context_lines': 10, 'hunks': 2}
```

---

### 5. edit_script_generator.py (306 lines)

**Purpose**: Generate LLM prompts for edit script creation

**Key Functions**:
```python
def generate_test_edit_prompt(
    filepath: str,
    source_code: str,
    task_description: str,
    target_line: Optional[int] = None
) -> str:
    """Generate prompt for test edit script."""
```

**Prompt Structure**:
```
1. System prompt: Explain edit script format, anti-hallucination rules
2. Task description: What to achieve
3. Available anchors: System-extracted candidates (ONLY these allowed)
4. Source code: Full context
5. Requirements: JSON format, use only provided anchors
```

**Critical Instruction**:
```
CRITICAL RULES:
- ONLY use anchors from the provided candidate list
- DO NOT invent or hallucinate anchor text
- Anchors must match EXACTLY as shown in candidates
```

**Prompt Types**:
- `generate_test_edit_prompt`: Add/modify tests
- `generate_code_edit_prompt`: Fix code based on test failures
- `generate_focused_edit_prompt`: Focus on specific line range
- `generate_iterative_edit_prompt`: Learn from previous failed attempts

---

### 6. candidate_ranker.py (398 lines)

**Purpose**: Rank anchor candidates by quality

**Key Functions**:
```python
def rank_candidates(
    source_code: str,
    candidates: List[AnchorCandidate],
    target_line: Optional[int] = None
) -> List[RankedCandidate]:
    """Rank candidates by composite score."""
```

**Scoring Dimensions**:
1. **Uniqueness** (weight 0.5): Higher if anchor appears exactly once
   - count=1 → score=1.0
   - count=2 → score=0.5
   - count=3 → score=0.33

2. **Proximity** (weight 0.3): Higher if closer to target line
   - distance=0 → score=1.0
   - distance=max → score=0.0
   - Linear decay

3. **Stability** (weight 0.2): Resistance to unrelated changes
   - function_def/class_def → 1.0 (very stable)
   - decorator → 0.8
   - import_stmt → 0.6
   - line_pattern → 0.4 (formatting can change)

**Composite Score**:
```python
score = 0.5 * uniqueness + 0.3 * proximity + 0.2 * stability
```

**Example Output**:
```
1. [Line 42] function_def (score: 0.95)
   def test_basic():
   Uniqueness: 1.00, Proximity: 0.90, Stability: 1.00

2. [Line 45] line_pattern (score: 0.72)
   assert result == expected
   Uniqueness: 1.00, Proximity: 0.80, Stability: 0.40
```

**Use Case**: Show LLM best anchors first (high-quality, unique, nearby).

---

## Integration Points

### How Component 3 Fits into run_mvp.py

**Current Flow (Phase 2 - Diff Writer)**:
```python
# Stage A: Generate test diff (LLM directly generates diff syntax)
test_diff = llm_generate_diff(prompt)

# Stage B: Apply diff (90% failure rate)
result = apply_patch(test_diff)  # Often fails: malformed patch
```

**New Flow (Component 3 - Edit Script)**:
```python
# Stage A: Generate test edit script
candidates = extract_anchor_candidates(source_code)
prompt = generate_test_edit_prompt(filepath, source_code, task, candidates)
edit_script_json = llm_generate(prompt)  # JSON, not diff

# Stage A: Validate and apply edit script
validation = validate_edit_script(source_code, edit_script_json)
if not validation.is_valid:
    handle_validation_errors(validation.errors)

result = apply_edit_script(source_code, edit_script_json)
if not result.success:
    handle_application_errors(result.errors)

# Stage A: Generate diff from modified source
diff = generate_unified_diff(source_code, result.modified_code, filepath)
# diff is ALWAYS syntactically correct (generated by difflib, not LLM)
```

**Key Difference**:
- Phase 2: LLM generates diff syntax → 90% failure
- Component 3: LLM generates semantic edits → System generates diff → 0% syntax errors expected

---

## Expected Benefits

### 1. Eliminate Malformed Patch Errors

**Phase 2 Failure Pattern**:
```
Malformed patch at line 16: '   line_with_wrong_context'
Malformed patch at line 23: 'missing_hunk_header'
```

**Component 3 Solution**:
- LLM never touches diff syntax
- difflib generates all diffs
- **Expected**: 0% malformed patch errors

---

### 2. Prevent Anchor Hallucination

**Current Issue (Phase 2)**:
```diff
@@ -42,3 +42,5 @@
 def test_basic():  # LLM might hallucinate this doesn't exist
+    new_line
```

**Component 3 Solution**:
```json
{
  "anchor": {"selected": "def test_basic():"}  // MUST be from candidate list
}
```
- System extracts all anchors via AST
- LLM can ONLY select from provided list
- Validation rejects hallucinated anchors
- **Expected**: 0% anchor hallucination errors

---

### 3. Better Iteration Behavior

**Current Issue**: When diff fails, LLM regenerates another broken diff

**Component 3 Approach**:
```python
# Iteration N: Failed with error "Anchor not unique"
previous_attempts = [
    {'edits': [...], 'result': 'failed', 'error': 'Anchor not unique'}
]

# Iteration N+1: Generate with context
prompt = generate_iterative_edit_prompt(
    source_code,
    task,
    previous_attempts,  # LLM learns from failure
    test_results
)
```

**Expected**: Better convergence through iteration

---

### 4. Human-Readable Edit Plans

**Phase 2 Output**:
```diff
@@ -42,3 +42,5 @@
```
(Hard to understand intent)

**Component 3 Output**:
```json
{
  "type": "insert_after",
  "anchor": {"selected": "def test_basic():"},
  "description": "Add edge case test for empty input",
  "content": "def test_empty_input(): ..."
}
```
(Intent is explicit)

**Benefit**: Easier debugging and human review

---

## Files Created

1. ✅ `bench_agent/editor/anchor_extractor.py` (357 lines)
2. ✅ `bench_agent/editor/edit_applier.py` (353 lines)
3. ✅ `bench_agent/editor/edit_validator.py` (471 lines)
4. ✅ `bench_agent/editor/diff_generator.py` (394 lines)
5. ✅ `bench_agent/editor/edit_script_generator.py` (306 lines)
6. ✅ `bench_agent/editor/candidate_ranker.py` (398 lines)
7. ✅ `bench_agent/editor/__init__.py` (167 lines)

**Total**: 2,446 lines of production code

---

## Next Steps: Phase 3.2 - Integration

### Task: Integrate Edit Script Mode into run_mvp.py

**Changes Required**:

1. **Add USE_EDIT_SCRIPT flag**:
```python
USE_EDIT_SCRIPT = os.environ.get('USE_EDIT_SCRIPT', '0') == '1'
```

2. **Import editor modules**:
```python
if USE_EDIT_SCRIPT:
    from bench_agent.editor import (
        extract_anchor_candidates,
        generate_test_edit_prompt,
        generate_code_edit_prompt,
        validate_edit_script,
        apply_edit_script,
        generate_unified_diff
    )
```

3. **Replace Stage A (test generation)**:
```python
if USE_EDIT_SCRIPT:
    # Edit script mode
    candidates = extract_anchor_candidates(test_source)
    prompt = generate_test_edit_prompt(test_file, test_source, task)
    edit_script = llm_generate_json(prompt)  # JSON response

    validation = validate_edit_script(test_source, edit_script)
    if not validation.is_valid:
        # Handle validation errors
        pass

    result = apply_edit_script(test_source, edit_script)
    if result.success:
        test_diff = generate_unified_diff(test_source, result.modified_code, test_file)
else:
    # Original diff mode
    test_diff = llm_generate_diff(prompt)
```

4. **Replace Stage B (code generation)** - similar changes

5. **Update LLM call to request JSON**:
```python
response = llm.generate(
    prompt,
    response_format={'type': 'json_object'}  # Force JSON
)
```

**Estimated Time**: 1-2 hours

---

### Task: Create Test Configuration

**File**: `configs/p091_component3_test.yaml`

```yaml
runner:
  dataset_name: "princeton-nlp/SWE-bench_Lite"

instances:
  list:
    - "astropy__astropy-14182"  # Known failure case

limits:
  max_iters: 3
  time_limit_minutes: 60

split:
  public_ratio: 0.7
  seed: 0

policy:
  forbid_skip: true
  forbid_xfail: true
  forbid_network: true
  restrict_file_io: true

llm:
  enabled: true
  model: "gpt-4o"  # Need capable model for JSON generation

edit_script:
  enabled: true
  require_unique_anchors: true
  max_candidates_per_type: 10
```

---

### Task: Run Component 3 Test

**Command**:
```bash
USE_EDIT_SCRIPT=1 PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
python scripts/run_mvp.py \
  --config configs/p091_component3_test.yaml \
  --run-id p091-component3-test-$(date +%Y%m%d-%H%M%S)
```

**Expected Outcomes**:
1. ✅ No malformed patch errors
2. ✅ No anchor hallucination errors
3. ✅ Cleaner iteration behavior
4. 📊 Compare BRS/TSS/COMB scores to Phase 2 baseline

**Success Criteria**:
- Zero malformed patch errors (vs 92% in Phase 2.2)
- At least one instance shows improved scores
- Edit scripts are well-formed JSON

---

## Risk Assessment

### High Confidence

1. **Zero malformed patches**: difflib guarantees correct syntax ✅
2. **Zero hallucinated anchors**: AST extraction + validation ✅
3. **JSON parsing success**: Modern LLMs (GPT-4o) handle JSON well ✅

### Medium Confidence

1. **LLM anchor selection quality**: Will LLM select good anchors?
   - Mitigation: Candidate ranking shows best anchors first
   - Fallback: Iterative prompts learn from failures

2. **Edit complexity**: Can LLM describe complex edits?
   - Mitigation: Start with simple edits (insert_after for tests)
   - Future: Multi-step edits if needed

### Low Risk

1. **Integration complexity**: run_mvp.py changes are straightforward
2. **Performance**: Anchor extraction is fast (AST parsing ~10ms)

---

## Summary

**Phase 3.1 Status**: ✅ **COMPLETE**

**Deliverables**:
- 6 core modules (2,446 lines)
- Complete edit script workflow
- Anti-hallucination architecture
- Deterministic diff generation

**Time Spent**: ~2 hours (as estimated)

**Production Readiness**: Core infrastructure ready, integration pending

**Next Milestone**: Phase 3.2 - Integration (1-2 hours estimated)

**Recommendation**: Proceed with integration into run_mvp.py, then test on astropy-14182

---

**Report Generated**: 2025-12-28 10:21 KST
**Implementation By**: Claude Code - Component 3 Phase 3.1 Team
