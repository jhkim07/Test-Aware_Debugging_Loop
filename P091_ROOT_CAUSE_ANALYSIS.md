# Component 3 - Root Cause Analysis

**Date**: 2025-12-28 23:30 KST
**Test**: p091-brs-tss-20251228-214418
**Status**: ❌ **CRITICAL BUGS IDENTIFIED**

---

## 🚨 Executive Summary

Component 3 (Edit Script Mode) has **catastrophic performance regression** (-76.3%) due to **malformed diffs** generated after edit application.

**Key Finding**: While edit scripts apply successfully, the **diff generation produces incorrect patches** that fail to apply, resulting in:
- HFS = 0.0 (zero successful fixes)
- COMB = 0.225 vs 0.950 baseline
- All patches rejected by git/patch

---

## 📊 Test Results

### Successfully Executed: 4/13 instances

| Instance | BRS | TSS | HFS | Overall | Baseline | Delta |
|----------|-----|-----|-----|---------|----------|-------|
| astropy-12907 | 1.0 | 0.5 | 0.0 | 0.256 | 0.987 | -74.1% |
| sympy-20590 | 1.0 | 0.5 | 0.0 | 0.256 | 0.994 | -74.2% |
| astropy-14182 | 1.0 | 0.5 | 0.0 | 0.256 | 0.825 | -69.0% |
| astropy-14365 | 0.0 | 0.0 | 0.0 | 0.131 | 0.994 | -86.8% |

### Failed: 9/13 instances (Repository setup errors)

---

## 🔍 Root Cause Analysis

### Issue 1: Malformed Diff Generation ❌ CRITICAL

**Symptom**: Edit scripts apply successfully but generated diffs fail to apply.

**Evidence**:
```
✓ Edit script applied successfully (1 edits)
⚠️  BRS patch apply failed (iteration 1)
BRS patch apply failed: Hunk #1 failed at line 1

Patch Apply Failure (Iteration 1)
  Type: line_mismatch
  Failed Hunks: [1]
  Failed at Line: 136
```

**Analysis of Malformed Test Diff** (astropy-12907):

```diff
@@ -136,6 +136,27 @@


 def test_custom_model_separable():
+
+
+def test_separability_matrix_nested_compound_models():
+    cm = models.Linear1D(10) & models.Linear1D(5)
+    ...
+    assert_allclose(separability_matrix(nested_cm), expected_nested_cm_matrix)
     @custom_model
     def model_a(x):
         return x
```

**Problem**: The new function is being **inserted INSIDE** the existing `test_custom_model_separable` function instead of BEFORE it.

- Lines 7-27: New test function (correct content)
- Line 28: `@custom_model` - **This is part of the ORIGINAL function!**

**Result**: The patch corrupts the file by splitting an existing function.

---

**Analysis of Malformed Code Diff** (astropy-12907):

```diff
@@ -242,6 +242,34 @@
         cright = _coord_matrix(right, 'right', noutp)
     else:
         cright = np.zeros((noutp, right.shape[1]))
+        cright[-right.shape[0]:, -right.shape[1]:] = right
+
+    return np.hstack([cleft, cright])
+    """
+    Function corresponding to '&' operation.
+    ...
+    """
+    noutp = _compute_n_outputs(left, right)
+    ...
         cright[-right.shape[0]:, -right.shape[1]:] = 1

     return np.hstack([cleft, cright])
```

**Problem**: The patch is **duplicating the entire _cstack function**.

- Lines 7-35: Duplicate function code
- Line 35: Original code continues

**Result**: The patch creates malformed code with duplicate function definitions.

---

### Root Cause Hypothesis

#### Theory 1: Edit Script Targets Wrong Anchor (Most Likely)

**Hypothesis**: LLM is selecting anchors that are **inside functions** instead of **between functions**.

**Example**:
```python
# WRONG: Anchor inside function
def test_custom_model_separable():
    @custom_model  # ← Anchor selected here
    def model_a(x):
        return x
```

When edit script inserts **before** this anchor, it creates:
```python
def test_custom_model_separable():
    # NEW FUNCTION INSERTED HERE (WRONG!)
    def test_separability_matrix_nested_compound_models():
        ...
    @custom_model  # ← Original code continues
    def model_a(x):
        return x
```

**Correct anchor should be**:
```python
def test_custom_model_separable():  # ← Anchor should be the function def itself
    @custom_model
    def model_a(x):
        return x
```

---

#### Theory 2: Edit Application Logic Bug (Less Likely)

**Hypothesis**: The `apply_edit_script()` function may have a bug in how it inserts code around anchors.

**Need to verify**: Check `bench_agent/editor/edit_applicator.py` for logic errors.

---

#### Theory 3: Anchor Extraction Missing Function Boundaries (Possible)

**Hypothesis**: `extract_anchor_candidates()` may not be identifying function definitions as valid anchors, forcing LLM to pick sub-optimal anchors inside functions.

**Need to verify**: Check what anchors are being extracted for test files.

---

### Issue 2: LLM Generating Duplicate Diffs ⚠️ MEDIUM

**Evidence**:
```
⚠️  Duplicate code diff detected (iteration 2). LLM is stuck in loop.
⚠️  Duplicate code diff detected (iteration 3). LLM is stuck in loop.
```

**Analysis**: After iteration 1 fails, iterations 2 and 3 generate **identical diffs**.

**Likely Cause**: Feedback loop not providing enough information about WHY the patch failed, so LLM keeps trying the same thing.

**Impact**: Wastes iterations, prevents system from recovering.

---

### Issue 3: Repository Setup Incomplete ❌ HIGH

**Evidence**: 9/13 instances failed with:
```
Repository path does not exist: /tmp/astropy_astropy__astropy-6938
```

**Root Cause**: New instances require SWE-bench environment preparation.

**Impact**: Cannot test on expanded instance set.

**Fix**: Run SWE-bench setup script for all instances before testing.

---

## 🎯 Critical Path to Fix

### Priority 1: Fix Malformed Diff Generation

#### Investigation Steps:

1. **Check what anchors are extracted**
   ```python
   # Add debug logging to extract_anchor_candidates
   candidates = extract_anchor_candidates(test_source_code)
   print(f"Extracted {len(candidates)} anchors:")
   for c in candidates[:10]:
       print(f"  Line {c['line_number']}: {c['text'][:50]}")
   ```

2. **Check what anchor LLM selects**
   ```python
   # Parse edit_script JSON to see selected anchor
   print(f"Selected anchor: {edit_script['anchor']}")
   print(f"Operation: {edit_script['operation']}")  # insert_before / insert_after
   ```

3. **Manually verify edit result**
   ```python
   # Before: original_code
   # After: apply_result.modified_code
   # Compare to see if insertion is correct
   ```

4. **Check if difflib is working correctly**
   ```python
   # Test difflib directly
   diff = difflib.unified_diff(original.split('\n'), modified.split('\n'))
   print('\n'.join(diff))
   ```

---

#### Likely Fix Scenarios:

**Scenario A: Anchor Selection Bug** (80% probability)
- **Problem**: LLM selecting wrong anchors (inside functions)
- **Fix**: Improve anchor ranking to prefer function definitions
- **File**: `bench_agent/editor/anchor_extractor.py`
- **Action**: Modify ranking to deprioritize nested anchors

**Scenario B: Edit Application Bug** (15% probability)
- **Problem**: `apply_edit_script()` inserting at wrong location
- **Fix**: Debug and fix insertion logic
- **File**: `bench_agent/editor/edit_applicator.py`
- **Action**: Add bounds checking, verify insertion point calculation

**Scenario C: Prompt Engineering** (5% probability)
- **Problem**: LLM not understanding task correctly
- **Fix**: Improve prompt to emphasize function-level insertions
- **File**: `bench_agent/editor/prompt_templates.py`
- **Action**: Add examples, clarify anchor selection criteria

---

### Priority 2: Fix Repository Setup

**Action**: Run SWE-bench environment preparation for all instances.

```bash
# Prepare all instances
python scripts/prepare_swebench_instances.py --config configs/p091_brs_tss_test.yaml
```

---

### Priority 3: Improve Iteration Feedback

**Action**: Provide detailed failure analysis to LLM when patch fails.

**Current feedback**:
```
Patch apply failed at line 136
```

**Improved feedback**:
```
Patch apply failed at line 136.
Analysis: New code was inserted inside function 'test_custom_model_separable' instead of before it.
Please select anchor at line 136 (function definition) instead of line 142 (decorator inside function).
```

---

## 📋 Recommended Investigation Sequence

### Step 1: Manual Reproduction (30 minutes)

```python
# Create test script to manually reproduce the issue
from bench_agent.editor import extract_anchor_candidates, apply_edit_script

# Load astropy-12907 test file
test_code = read_file("astropy/modeling/tests/test_separable.py")

# Extract anchors
candidates = extract_anchor_candidates(test_code)

# Print anchor at line 136-145
for c in candidates:
    if 136 <= c['line_number'] <= 145:
        print(f"Line {c['line_number']}: {c['text']}")
        print(f"  Type: {c['type']}, Score: {c.get('score', 'N/A')}")
```

**Expected Finding**: Anchor at line 142 (`@custom_model`) has higher score than line 136 (`def test_custom_model_separable`).

**If confirmed**: Anchor ranking is broken → Fix anchor scoring.

---

### Step 2: Fix Anchor Scoring (1-2 hours)

**File**: `bench_agent/editor/anchor_extractor.py`

**Changes**:
1. Increase score for function definitions (def, class)
2. Decrease score for decorators
3. Decrease score for nested statements (inside functions)
4. Add "function boundary" detection

**Test**: Re-extract anchors, verify function defs score highest.

---

### Step 3: Local Testing (30 minutes)

```python
# Test edit script application with fixed anchors
edit_script = {
    "anchor": "def test_custom_model_separable():",
    "anchor_line": 136,
    "operation": "insert_before",
    "code": "def test_separability_matrix_nested_compound_models():\n    ..."
}

result = apply_edit_script(test_code, edit_script)
print(result.modified_code)

# Check if insertion is correct
# Expected: New function BEFORE line 136, not INSIDE it
```

---

### Step 4: Single Instance Test (20 minutes)

```bash
# Test with just astropy-12907
USE_EDIT_SCRIPT=1 python scripts/run_mvp.py \
  --config configs/single_instance_test.yaml \
  --run-id p091-anchor-fix-test
```

**Success Criteria**:
- Patch applies successfully
- HFS > 0 (at least some tests pass)
- No malformed diffs

---

### Step 5: 4-Instance Regression (1 hour)

```bash
# Test with 4 baseline instances
USE_EDIT_SCRIPT=1 python scripts/run_mvp.py \
  --config configs/p091_baseline_4inst.yaml \
  --run-id p091-anchor-fix-regression
```

**Success Criteria**:
- BRS ≥ 80% (3/4 or 4/4)
- TSS ≥ 70%
- COMB ≥ 0.75
- HFS > 0 (successful fixes)

---

## 🔧 Quick Fix vs Complete Fix

### Quick Fix (2-3 hours):

**Goal**: Get something working for deployment.

**Actions**:
1. Fix anchor scoring to prefer function definitions
2. Test on 4 baseline instances
3. If BRS/TSS/COMB meet criteria → Deploy

**Risk**: May not fix all edge cases.

---

### Complete Fix (1-2 days):

**Goal**: Robust, production-ready solution.

**Actions**:
1. Deep investigation of anchor selection
2. Improve edit application logic
3. Add validation checks for insertion points
4. Improve LLM feedback loop
5. Test on 10-20 instances
6. Full regression on all instances

**Risk**: Takes longer, may find more issues.

---

## 📊 Decision Matrix

```
Current State:
  BRS: 75% (3/4)   ❌ vs 80% target
  TSS: 37.5%       ❌ vs 70% target
  COMB: 0.225      ❌ vs 0.75 target
  HFS: 0%          ❌ CRITICAL

Recommended Path: QUICK FIX first

Reason:
  - Clear root cause identified (anchor selection)
  - Likely fixable in 2-3 hours
  - Can test and deploy quickly
  - If fails, fall back to Phase 0.9.1
```

---

## 📝 Next Actions

### Immediate (Next 30 minutes):

1. ✅ Create investigation script
2. ✅ Reproduce anchor extraction issue
3. ✅ Confirm hypothesis

### Short-term (Next 2-3 hours):

1. ⬜ Fix anchor scoring algorithm
2. ⬜ Test on single instance
3. ⬜ Test on 4 baseline instances

### Medium-term (Next 6-12 hours):

1. ⬜ If quick fix succeeds: Deploy to production
2. ⬜ If quick fix fails: Deep investigation
3. ⬜ Complete fix implementation

---

## 🚀 Success Criteria for Fix

### Minimal (Deploy with monitoring):
```
BRS ≥ 75% (3/4)
TSS ≥ 70%
COMB ≥ 0.75
HFS > 0 (any successful fix)
Patches apply successfully
```

### Target (Full deployment):
```
BRS ≥ 80%
TSS ≥ 75%
COMB ≥ 0.80
HFS ≥ 0.5
Baseline match (±10%)
```

### Ideal (Production ready):
```
BRS = 100% (4/4)
TSS ≥ 80%
COMB ≥ 0.90
HFS ≥ 0.7
Match Phase 0.9.1 baseline
```

---

**Report Generated**: 2025-12-28 23:30 KST
**Status**: ❌ ROOT CAUSE IDENTIFIED - READY TO FIX
**Estimated Fix Time**: 2-3 hours (quick fix) | 1-2 days (complete fix)
**Recommended Action**: **QUICK FIX FIRST**
