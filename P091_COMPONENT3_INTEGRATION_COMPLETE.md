# Component 3 Integration Complete

**Date**: 2025-12-28 10:40 KST
**Phase**: Component 3 - Edit Script PoC (Phase 3.2: Integration)
**Status**: ✅ **INTEGRATION COMPLETE**

---

## Executive Summary

Component 3 (Edit Script Mode) has been successfully integrated into `run_mvp.py`:

1. ✅ **edit_script_workflow.py** - High-level workflow wrapper (450 lines)
2. ✅ **run_mvp.py modifications** - Feature flag integration (minimal changes)
3. ✅ **Test configuration** - `configs/p091_component3_test.yaml`

**Integration Approach**: Feature flag (`USE_EDIT_SCRIPT`) with minimal code changes
**Total Changes**: ~100 lines modified in run_mvp.py
**Backward Compatibility**: ✅ 100% (defaults to original behavior)

---

## Integration Architecture

### Feature Flag System

```python
# Environment variable controls mode
USE_EDIT_SCRIPT = os.getenv("USE_EDIT_SCRIPT", "0") == "1"

# Priority: Edit Script > Two-Stage > One-Stage
if USE_EDIT_SCRIPT:
    # Component 3: Edit Script Mode
    ...
elif USE_TWO_STAGE:
    # Phase 2: Two-Stage Architecture
    ...
else:
    # Original: One-Stage
    ...
```

**Benefits**:
- No breaking changes
- Easy A/B testing
- Can rollback instantly by changing env var

---

## Files Modified/Created

### 1. NEW: bench_agent/protocol/edit_script_workflow.py (450 lines)

**Purpose**: High-level workflow wrapper for edit script mode

**Key Functions**:

#### generate_test_diff_edit_script()
```python
def generate_test_diff_edit_script(
    client,
    model: str,
    test_file_path: str,
    test_source_code: str,
    problem_statement: str,
    reference_test_patch: str,
    failure_summary: str
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate test diff using edit script workflow.

    Returns:
        (diff_string, metadata_dict)
    """
```

**Workflow**:
1. Extract anchor candidates from test source
2. Generate LLM prompt with candidates
3. Call LLM with JSON mode
4. Parse edit script JSON
5. Validate edit script (anchors exist, unique)
6. Apply edits deterministically
7. Generate unified diff (difflib)

**Return Metadata**:
```python
{
    'success': bool,
    'edit_script': dict or None,
    'validation_result': ValidationResult or None,
    'apply_result': EditResult or None,
    'errors': list of str
}
```

#### generate_code_diff_edit_script()
- Same workflow as test diff
- Uses code-specific prompts
- Includes reference patch analysis

#### Helper Functions
- `extract_test_file_from_reference()` - Extract test file path from diff
- `extract_code_file_from_reference()` - Extract code file path from diff
- `read_file_from_repo()` - Read source file from repository

---

### 2. MODIFIED: scripts/run_mvp.py

**Changes Made**:

#### A. Import Section (Lines 33-43)
```python
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
```

#### B. Test Generation Section (Lines 360-410)
```python
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
    # ... existing code ...
else:
    # ... existing code ...
```

#### C. Code Generation Section (Lines 635-681)
```python
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
                test_results=failure,
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
    # ... existing code ...
else:
    # ... existing code ...
```

**Total Lines Modified**: ~100 lines (in a 960-line file = 10% change)

---

### 3. NEW: configs/p091_component3_test.yaml

**Purpose**: Test configuration for Component 3

```yaml
runner:
  dataset_name: "princeton-nlp/SWE-bench_Lite"

instances:
  list:
    - "astropy__astropy-14182"  # Known failure case from Phase 2

limits:
  max_iters: 3
  time_limit_minutes: 90

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

## Usage

### Run Component 3 Test

```bash
USE_EDIT_SCRIPT=1 PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
python scripts/run_mvp.py \
  --config configs/p091_component3_test.yaml \
  --run-id p091-component3-test-$(date +%Y%m%d-%H%M%S)
```

**Expected Output**:
```
⚙️  Component 3: Edit Script Mode ENABLED
...
Edit Script: Generating test diff for astropy/tests/test_foo.py
✓ Edit script applied successfully (2 edits)
...
Edit Script: Generating code diff for astropy/foo.py
✓ Edit script applied successfully (1 edits)
```

### Fallback to Original Mode

```bash
# Don't set USE_EDIT_SCRIPT (defaults to 0)
PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
python scripts/run_mvp.py \
  --config configs/p091_component3_test.yaml \
  --run-id p091-baseline-test-$(date +%Y%m%d-%H%M%S)
```

---

## Error Handling

### Graceful Degradation

**If Edit Script Fails**:
1. Metadata captures error details
2. Safety controller records failure
3. Empty diff returned (iteration continues)
4. No crash - system keeps running

**Error Types Handled**:
- Test/code file not found → Warning + empty diff
- JSON parse error → Error logged + empty diff
- Validation failed → Errors displayed + empty diff
- Edit application failed → Errors displayed + empty diff
- LLM error → Exception caught + empty diff

**Example Error Output**:
```
[yellow]Edit script failed: ['Validation failed:\n✗ Edit script validation failed\n\nErrors (1):\n[Edit 1] anchor_not_found: Anchor not found in source: def test_basic():...[/yellow]
```

---

## Integration Testing Checklist

### Pre-Test Verification

- [x] All editor modules created (6 files)
- [x] edit_script_workflow.py created
- [x] run_mvp.py modified with feature flag
- [x] Test config created
- [x] Imports resolve correctly
- [ ] SWE-bench environment available
- [ ] astropy repository cloned

### Test Execution

- [ ] Run with `USE_EDIT_SCRIPT=1`
- [ ] Verify "Edit Script Mode ENABLED" message
- [ ] Check anchor extraction succeeds
- [ ] Verify LLM returns valid JSON
- [ ] Validate edit script passes validation
- [ ] Confirm edits apply successfully
- [ ] Verify diff is generated
- [ ] Check no malformed patch errors

### Success Criteria

1. **Zero malformed patches** (vs 92% in Phase 2.2)
2. **Zero hallucinated anchors** (validated against AST)
3. **Edit scripts are well-formed JSON**
4. **At least one successful iteration**

### Failure Analysis (If Test Fails)

Check in order:
1. LLM JSON generation quality
2. Anchor extraction coverage
3. Validation strictness (too strict?)
4. Edit application logic
5. Diff generation

---

## Comparison: Phase 2 vs Component 3

### Phase 2 (Diff Writer)

**Workflow**:
```
LLM generates diff syntax directly
→ 92% malformed patch errors
→ Manual sanitization (incomplete)
→ Still fails
```

**Problems**:
- LLM bad at diff syntax
- Hallucinated line numbers
- Wrong context lines
- Missing hunk headers

### Component 3 (Edit Script)

**Workflow**:
```
System extracts anchors (AST)
→ LLM selects anchors + describes edits (JSON)
→ System validates
→ System applies deterministically
→ difflib generates diff (always correct)
```

**Advantages**:
- LLM never touches diff syntax
- Anchors guaranteed to exist
- Validation rejects hallucinations
- difflib diffs always valid

---

## Expected Results

### Hypothesis

Component 3 should achieve:
- **0% malformed patch errors** (vs 92%)
- **0% hallucinated anchors** (AST validation)
- **Better iteration convergence** (structured feedback)

### Metrics to Track

1. **Malformed Patch Rate**: 0% expected
2. **BRS (Bug Reproduction Strength)**: ≥ Phase 2 baseline
3. **TSS (Test Strength Score)**: ≥ Phase 2 baseline
4. **COMB (Overall Score)**: ≥ Phase 2 baseline
5. **Iteration Count**: Fewer iterations to converge
6. **Validation Errors**: Track anchor errors

### Success Definition

**Minimum Success**:
- Zero malformed patch errors
- At least one instance completes all iterations

**Strong Success**:
- BRS/TSS/COMB ≥ Phase 2 baseline
- Cleaner iteration behavior
- Human-readable edit intents

**Exceptional Success**:
- BRS/TSS/COMB > 0.8 on multiple instances
- Consistent convergence in 2-3 iterations

---

## Rollback Plan

If Component 3 fails catastrophically:

### Option A: Disable via Env Var
```bash
# Just don't set USE_EDIT_SCRIPT
python scripts/run_mvp.py --config configs/p091_component3_test.yaml ...
```

### Option B: Git Rollback
```bash
git checkout HEAD~1 scripts/run_mvp.py
```

**Note**: Core editor modules in `bench_agent/editor/` are independent and don't affect other modes.

---

## Next Steps

### Immediate: Run Test

```bash
USE_EDIT_SCRIPT=1 PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
python scripts/run_mvp.py \
  --config configs/p091_component3_test.yaml \
  --run-id p091-component3-test-$(date +%Y%m%d-%H%M%S)
```

**Estimated Time**: 20-30 minutes for astropy-14182

### After Test: Analysis

1. Review logs for:
   - Malformed patch errors (should be 0)
   - Validation errors
   - Edit script JSON quality
   - Iteration behavior

2. Compare metrics:
   - BRS vs Phase 2 baseline
   - TSS vs Phase 2 baseline
   - COMB vs Phase 2 baseline

3. Debugging (if needed):
   - Check LLM JSON quality
   - Verify anchor extraction
   - Review validation strictness

### If Successful: Expand Testing

```yaml
# configs/p091_component3_full.yaml
instances:
  list:
    - "astropy__astropy-12907"  # Another known case
    - "astropy__astropy-14182"
    - "astropy__astropy-14365"
    - "sympy__sympy-20590"
```

---

## Summary

**Integration Status**: ✅ **COMPLETE**

**Files Created**:
1. `bench_agent/protocol/edit_script_workflow.py` (450 lines)
2. `configs/p091_component3_test.yaml`

**Files Modified**:
1. `scripts/run_mvp.py` (~100 lines changed)

**Backward Compatibility**: ✅ 100% (feature flag)

**Production Readiness**: ✅ Ready for testing

**Next Milestone**: Run Component 3 test on astropy-14182

**Recommendation**: Execute test and analyze results

---

**Report Generated**: 2025-12-28 10:40 KST
**Integration By**: Claude Code - Component 3 Integration Team
