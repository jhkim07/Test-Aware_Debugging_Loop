# Phase 0.9.2: Comprehensive Fix Plan

**Date**: 2025-12-29 15:40 KST
**Status**: Ready to Execute

---

## 🎯 Two Separate Problems Identified

### Problem 1: Auto-fix Bug (Priority 1 - CRITICAL)
**Impact**: 3 failures
**Cause**: `'dict' object has no attribute 'strip'`
**Fix Effort**: 15 minutes
**Success Rate**: 99%

### Problem 2: Component 3 Validation (Priority 2 - IMPROVEMENT)
**Impact**: 3 failures
**Cause**: anchor_not_unique, anchor_not_found
**Fix Effort**: 30-60 minutes
**Success Rate**: 70%

---

## 📋 Fix Plan Overview

### Phase 1: Fix Auto-fix Bug (15 min)
1. Fix `auto_fix_duplicate_code()` function
2. Fix unit test format
3. Quick integration test

### Phase 2: Fix Component 3 Validation (45 min)
4. Add better anchor candidate ranking
5. Add anchor fallback mechanism
6. Test on problematic instance

### Phase 3: Full Validation (90 min)
7. Run complete regression test
8. Generate final report

**Total Estimated Time**: 150 minutes (~2.5 hours)

---

# PHASE 1: Fix Auto-fix Bug

## 1.1 Code Fix

### File: `bench_agent/editor/edit_validator.py`

**Current Code (Lines 597, 619, 624):**
```python
# Line 597 - BUG: anchor is dict, not string
anchor = edit.get('anchor', '')

# Line 619 - CRASH
old_anchor_line = anchor.strip()

# Line 624 - CRASH
if anchor.strip() in src_line:
```

**Fixed Code:**
```python
# Line 597 - FIX: Extract string from dict
anchor_dict = edit.get('anchor', {})
if isinstance(anchor_dict, dict):
    anchor_text = anchor_dict.get('selected', '')
else:
    anchor_text = str(anchor_dict)

# Line 619 - FIXED
old_anchor_line = anchor_text.strip()

# Line 624 - FIXED
if anchor_text.strip() in src_line:
```

**Additional Changes Needed:**
- Update all references from `anchor` to `anchor_text` in the function
- Add type safety check

## 1.2 Unit Test Fix

### File: `test_duplicate_autofix.py`

**Current Format (WRONG):**
```python
edit_script = {
    "edits": [{
        "type": "insert_before",
        "anchor": "return x + y",  # ❌ Wrong: string
        "content": "    x = 10\n    y = 20"
    }]
}
```

**Correct Format:**
```python
edit_script = {
    "file": "test.py",
    "edits": [{
        "type": "insert_before",
        "anchor": {  # ✅ Correct: dict
            "selected": "return x + y",
            "type": "line_pattern"
        },
        "content": "    x = 10\n    y = 20",
        "description": "Add variable initialization"
    }]
}
```

## 1.3 Integration Test

**Test Instance**: astropy__astropy-14365 (known duplicate code issue)

**Command**:
```bash
# Single instance quick test
USE_EDIT_SCRIPT=1 PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
  python scripts/run_mvp.py \
  --config configs/p091_component3_single.yaml \
  --run-id p092-autofix-integration-test
```

**Expected Result**:
- Duplicate code detected: Yes
- Auto-fix triggered: Yes
- Auto-fix successful: Yes (no crash)
- Edit script applied: Yes

**Pass Criteria**: No TypeError crashes

---

# PHASE 2: Fix Component 3 Validation Issues

## Problem Analysis

### Issue 1: anchor_not_unique

**Example from logs**:
```
[Edit 2] anchor_not_unique: Anchor appears 3 times (must be unique):
  ==== ========= ==== ====
```

**Root Cause**:
- LLM selects generic anchor like table separators
- These appear multiple times in file
- Validation rejects non-unique anchors

### Issue 2: anchor_not_found

**Example from logs**:
```
[Edit 1] anchor_not_found: Anchor not found in source:
  from io import StringIO
```

**Root Cause**:
- LLM hallucinates anchor text
- Anchor exists in reference patch but not current file
- File structure changed between iterations

## Solution 1: Improved Anchor Ranking

### File: `bench_agent/editor/anchor_extractor.py`

**Current**: Basic ranking by type (function > class > assignment)

**Improved**: Add uniqueness score
```python
def rank_candidates_by_quality(
    source_code: str,
    candidates: List[AnchorCandidate]
) -> List[AnchorCandidate]:
    """
    Rank candidates by quality:
    1. Uniqueness (count occurrences)
    2. Type priority (function > class > assignment)
    3. Context richness (longer is better)
    """
    ranked = []
    lines = source_code.split('\n')

    for candidate in candidates:
        # Count occurrences
        occurrence_count = sum(
            1 for line in lines
            if candidate.text.strip() in line
        )

        # Calculate uniqueness score (lower is better)
        uniqueness_score = occurrence_count

        # Combine with type priority
        type_priority = {
            'function_def': 1,
            'class_def': 2,
            'assignment': 3,
            'line_pattern': 4
        }.get(candidate.type, 5)

        # Final score (lower is better)
        candidate.quality_score = (uniqueness_score * 100) + type_priority
        ranked.append(candidate)

    # Sort by quality score
    return sorted(ranked, key=lambda c: c.quality_score)
```

**Impact**: Prioritize unique anchors → reduce anchor_not_unique errors

## Solution 2: Anchor Fallback Mechanism

### File: `bench_agent/protocol/edit_script_workflow.py`

**Add retry with different candidates**:
```python
# After validation fails with anchor_not_unique
if validation.errors:
    for error in validation.errors:
        if error.error_type == 'anchor_not_unique':
            # Retry with better anchor candidates
            # Filter out non-unique candidates
            unique_candidates = [
                c for c in candidates
                if count_occurrences(source_code, c.text) == 1
            ]

            # Regenerate prompt with unique-only candidates
            prompt = generate_edit_prompt(
                ...,
                anchor_candidates=unique_candidates
            )

            # Retry LLM call
            ...
```

**Impact**: Second chance with better candidates → reduce failures

## Solution 3: Anchor Verification Before LLM Call

### File: `bench_agent/editor/prompt_generator.py`

**Add pre-filtering**:
```python
def filter_valid_anchor_candidates(
    source_code: str,
    candidates: List[AnchorCandidate],
    require_unique: bool = True
) -> List[AnchorCandidate]:
    """
    Filter candidates to only include valid ones.
    """
    lines = source_code.split('\n')
    valid = []

    for candidate in candidates:
        # Check existence
        exists = any(candidate.text.strip() in line for line in lines)
        if not exists:
            continue

        # Check uniqueness if required
        if require_unique:
            count = sum(1 for line in lines if candidate.text.strip() in line)
            if count != 1:
                continue

        valid.append(candidate)

    return valid
```

**Impact**: Only present valid anchors to LLM → prevent hallucination

---

# PHASE 3: Testing & Validation

## 3.1 Quick Integration Test (10 min)

**After Phase 1 fixes**:
```bash
# Test auto-fix on single problem instance
./test_autofix_single.sh
```

**Success Criteria**:
- ✅ No TypeError crashes
- ✅ Auto-fix detects duplicates
- ✅ Auto-fix applies fixes
- ✅ Edit script succeeds

## 3.2 Component 3 Validation Test (20 min)

**After Phase 2 fixes**:
```bash
# Test on astropy-14182 (validation issues)
./test_validation_fix.sh
```

**Success Criteria**:
- ✅ Fewer anchor_not_unique errors
- ✅ No anchor_not_found errors
- ✅ Edit script success rate >80%

## 3.3 Full Regression Test (85 min)

**After both fixes**:
```bash
# Run all 4 instances
./run_p092_final_test.sh
```

**Success Criteria**:
- ✅ Auto-fix success rate >90%
- ✅ Edit script failures <3 (down from 6)
- ✅ Malformed patches <3 (down from 6)
- ✅ Overall improvement vs baseline

---

# Expected Results

## After Phase 1 Only (Auto-fix fixed)

| Metric | Baseline | After P1 | Change |
|--------|----------|----------|--------|
| Edit Script Failures | 6 | 3 | -50% ✅ |
| - Auto-fix crashes | 0 | 0 | Fixed ✅ |
| - Duplicate code | 3 | 0 | Fixed ✅ |
| - Validation errors | 3 | 3 | No change |
| Malformed Patches | 6 | 3-6 | Maybe better |

**ROI**: 50% error reduction for 15 min work = Excellent

## After Phase 1 + 2 (Both fixed)

| Metric | Baseline | After P1+P2 | Change |
|--------|----------|-------------|--------|
| Edit Script Failures | 6 | 0-1 | -83-100% ✅ |
| - Auto-fix crashes | 0 | 0 | Fixed ✅ |
| - Duplicate code | 3 | 0 | Fixed ✅ |
| - Validation errors | 3 | 0-1 | Fixed ✅ |
| Malformed Patches | 6 | 0-2 | -67-100% ✅ |

**ROI**: 83-100% error reduction for 60 min work = Excellent

---

# Implementation Order

## Option A: Sequential (Safer)

```
Phase 1 (15 min) → Test (10 min) →
Phase 2 (45 min) → Test (20 min) →
Full Test (85 min)

Total: 175 min
Risk: Low
Confidence: High
```

**Pros**:
- Validate each fix before proceeding
- Easy to identify which fix causes issues
- Can stop after Phase 1 if satisfied

**Cons**:
- Longer total time (2 test runs)
- More manual intervention

## Option B: Parallel (Faster)

```
Phase 1 + Phase 2 together (60 min) →
Quick Test (15 min) →
Full Test (85 min)

Total: 160 min
Risk: Medium
Confidence: Medium
```

**Pros**:
- Faster (saves 15 min)
- One comprehensive test run

**Cons**:
- If full test fails, harder to debug
- Can't evaluate Phase 1 impact separately

## Option C: Phase 1 Only (Pragmatic)

```
Phase 1 (15 min) →
Quick Test (10 min) →
Full Test (85 min)

Total: 110 min
Risk: Low
Confidence: High
```

**Pros**:
- Fastest path to 50% improvement
- Low risk (simple fix)
- Can evaluate Phase 2 separately later

**Cons**:
- Only fixes duplicate code, not validation
- Leaves 3 validation errors unfixed

---

# Recommendation

## 🎯 Start with Option C (Phase 1 Only)

**Rationale**:
1. **Quick win**: 50% error reduction in 110 min
2. **Low risk**: Simple, well-understood fix
3. **High ROI**: Maximum benefit per time invested
4. **Validatable**: Can measure exact impact
5. **Flexible**: Can add Phase 2 later if needed

**Execution Plan**:
```
1. Fix auto_fix_duplicate_code() (10 min)
2. Fix unit test format (5 min)
3. Run unit test (2 min)
4. Quick integration test on astropy-14365 (10 min)
5. If successful → Full regression test (85 min)
6. Generate results report (15 min)
7. Decide if Phase 2 needed based on results

Total: ~127 min
```

**Decision Point After Phase 1**:
- If results excellent (0-1 errors) → Done! 🎉
- If results good (2-3 errors) → Consider Phase 2
- If results poor (4+ errors) → Investigate before Phase 2

---

# Risk Assessment

## Phase 1 Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Fix doesn't work | Low (5%) | High | Unit test + integration test first |
| Breaks other code | Very Low (2%) | Medium | Isolated function, good test coverage |
| New edge case | Low (10%) | Low | Comprehensive error handling |

**Overall Risk**: **Low**

## Phase 2 Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Anchor ranking ineffective | Medium (30%) | Medium | Test on known failures first |
| LLM ignores better candidates | Medium (25%) | Medium | May need prompt engineering |
| Creates new issues | Low (15%) | High | Thorough testing required |

**Overall Risk**: **Medium**

---

# Success Metrics

## Must Have (Phase 1)
- ✅ Auto-fix crashes: 3 → 0
- ✅ Unit test passes with real format
- ✅ Integration test shows auto-fix working

## Should Have (Phase 1)
- ✅ Duplicate code errors: 3 → 0
- ✅ Edit script failures: 6 → 3
- ✅ No regressions on working instances

## Nice to Have (Phase 1 + 2)
- ✅ Validation errors: 3 → 0-1
- ✅ Edit script failures: 6 → 0-1
- ✅ Malformed patches: 6 → 0-2
- ✅ 100% BRS on all instances

---

# Next Steps

## Immediate Action Required

**Decision needed**: Which option to proceed with?

1. **Option A**: Sequential (safest, 175 min)
2. **Option B**: Parallel (faster, 160 min)
3. **Option C**: Phase 1 Only (pragmatic, 110 min) ⭐ **RECOMMENDED**

**Ready to execute once decision made.**

---

**Document Version**: 1.0
**Created**: 2025-12-29 15:40 KST
**Status**: Awaiting approval to proceed
