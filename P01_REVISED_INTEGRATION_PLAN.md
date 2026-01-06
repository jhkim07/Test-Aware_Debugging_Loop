# P0-1 Revised Integration Plan (Critical Corrections)

**Date**: 2026-01-05
**Status**: 🔴 CRITICAL REVISIONS based on detailed review
**Previous**: P01_MINIMAL_INTEGRATION_PLAN.md (flawed predicate logic)

---

## 🚨 Critical Corrections Summary

### Issue 1: `brs_satisfied=brs_fail` Variable Confusion ⚠️
**Problem**: Naming confusion between "BRS satisfied" and "brs_fail" variable
**Impact**: If implemented as-is, scoring would be inverted (BRS +20 applied backwards)
**Fix**:
```python
# WRONG (current document)
brs_satisfied=brs_fail

# CORRECT
reproduces_bug=brs_fail  # Clear: True = tests fail on buggy = good
# OR
brs_ok=brs_fail  # Clear: True = BRS requirement met
```

### Issue 2: `score > 0` is Wrong Predicate for Valid Candidate
**Problem**: "Valid for fallthrough" ≠ "positive score"
- Example: BRS(+20) + policy(-20) = 0 → Rejected as "invalid"
- But this candidate is **diagnostically valuable** (shows policy block)

**Fix**: Separate concerns
- **Score**: For ranking/sorting candidates
- **Valid predicate**: For execution safety (logical conditions)

### Issue 3: Phase 1 Success Criteria Too Vague
**Problem**: "3-4 instances with has_valid=true" is imprecise
**Fix**: Define two predicates explicitly

### Issue 4: Missing Diagnostic Fields for Root Cause
**Problem**: Can't distinguish "stuck pattern" vs "improving but not enough"
**Fix**: Add 3 lightweight fields

### Issue 5: Phase 2 Goal Misaligned
**Problem**: "2-3/4 perfect conversion" is too optimistic for 1st goal
**Fix**: Primary goal = "reach Code phase + diagnose blocker location"

---

## ✅ Corrected Two-Phase Strategy

### Phase 1: Record + Validate Predicates (2-3 instances sample)

**NOT** "record all Cohort 2" (overkill)
**YES** "record 2-3 instances, validate predicate logic"

**Why sample sufficient**:
- Scoring sanity check needs 2-3 data points
- Cohort 2 is policy-risk heavy → may skew distribution
- Can activate Phase 2 for remaining instances if validated

---

## 🎯 Corrected Predicate Definitions

### Predicate 1: Valid-for-Fallthrough (Execution Safety)

**Purpose**: Can we safely use this candidate to proceed to Code phase?

```python
def is_valid_for_fallthrough(candidate: TestCandidate) -> bool:
    """
    Candidate must be EXECUTABLE and REPRODUCE BUG.

    This is NOT about score - it's about safety.
    """
    # Must execute without crashes
    if not candidate.runs_ok:
        return False

    # Must reproduce bug (BRS requirement)
    if not candidate.brs_satisfied:
        return False

    # Must not violate policy (dealbreaker)
    if candidate.policy_violation:
        return False

    # Must be collectable (can't proceed if collection fails)
    if candidate.collection_error:
        return False

    # Import errors are borderline - allow if runs_ok is True
    # (sometimes tests can run despite import warnings)

    return True
```

**Key insight**: This predicate ensures fallthrough won't make things WORSE

---

### Predicate 2: Valid-for-Diagnosis (Analytical Value)

**Purpose**: Can this candidate tell us WHERE the blocker is?

```python
def is_valid_for_diagnosis(candidate: TestCandidate) -> bool:
    """
    Candidate has diagnostic value even if not executable.

    Example: BRS=1 + policy_violation = tells us "policy is blocker"
    """
    # At minimum, must have attempted BRS check
    if candidate.brs_satisfied:
        return True  # Any BRS=1 candidate is diagnostically valuable

    # Or if it ran but failed for interesting reasons
    if candidate.runs_ok and (candidate.public_pass_count > 0 or candidate.public_fail_count > 0):
        return True  # Execution happened, data is useful

    return False
```

**Key insight**: Even "bad" candidates can reveal root cause

---

## 📊 Corrected TestCandidate Class Enhancement

Add 3 diagnostic fields for root cause analysis:

```python
class TestCandidate:
    # ... existing 12 fields ...

    # NEW: Essential diagnostic fields
    fail_signature: str = ""        # error_type + top_frame hash
    diff_fingerprint: str = ""      # test_diff hash (detect duplicates)
    failure_stage: str = ""         # COLLECTION / EXECUTION / ASSERTION / POLICY

    def __init__(self, ...):
        # ... existing init ...

        # Auto-compute signatures
        self.fail_signature = self._compute_fail_signature(error_message)
        self.diff_fingerprint = hashlib.md5(test_diff.encode()).hexdigest()[:8]
        self.failure_stage = self._classify_failure_stage()

    def _compute_fail_signature(self, error_msg: str) -> str:
        """Extract error type + first meaningful line"""
        if not error_msg:
            return "NO_ERROR"

        lines = error_msg.split('\n')
        for line in lines:
            if 'Error:' in line or 'Exception:' in line:
                # Take error type + first 50 chars
                return line[:60].strip()

        return error_msg[:60].strip()

    def _classify_failure_stage(self) -> str:
        """Classify where failure occurred"""
        if self.policy_violation:
            return "POLICY"
        if self.collection_error:
            return "COLLECTION"
        if self.import_error:
            return "IMPORT"
        if self.syntax_error:
            return "SYNTAX"
        if not self.runs_ok:
            return "EXECUTION"
        if not self.brs_satisfied and self.runs_ok:
            return "ASSERTION"  # Tests ran but didn't reproduce bug
        if self.brs_satisfied:
            return "BRS_OK"

        return "UNKNOWN"
```

**Benefit**: Can detect "stuck" (same signature 3 times) automatically

---

## 🔄 Corrected TestCandidateTracker Enhancement

```python
class TestCandidateTracker:
    # ... existing methods ...

    def has_valid_for_fallthrough(self) -> bool:
        """Check if ANY candidate is safe to use for fallthrough"""
        for candidate in self.candidates:
            if is_valid_for_fallthrough(candidate):
                return True
        return False

    def get_best_executable_candidate(self) -> Optional[TestCandidate]:
        """
        Get best candidate that is SAFE to execute.

        CRITICAL: This is NOT just "highest score" - it's
        "highest score AMONG executable candidates"
        """
        executable = [c for c in self.candidates if is_valid_for_fallthrough(c)]

        if not executable:
            return None

        # Now sort by score
        sorted_exec = sorted(executable, key=lambda c: c.compute_score(), reverse=True)
        return sorted_exec[0]

    def get_diagnostic_summary(self) -> dict:
        """Analyze failure patterns"""
        if not self.candidates:
            return {}

        # Count failure stages
        stage_counts = {}
        for c in self.candidates:
            stage = c.failure_stage
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        # Check for stuck pattern (same signature repeated)
        signatures = [c.fail_signature for c in self.candidates]
        is_stuck = len(signatures) >= 2 and signatures[-1] == signatures[-2]

        # Check diff evolution
        fingerprints = [c.diff_fingerprint for c in self.candidates]
        diff_stable = len(set(fingerprints)) == 1  # All same

        return {
            'total_candidates': len(self.candidates),
            'valid_for_fallthrough': sum(1 for c in self.candidates if is_valid_for_fallthrough(c)),
            'valid_for_diagnosis': sum(1 for c in self.candidates if is_valid_for_diagnosis(c)),
            'stage_distribution': stage_counts,
            'is_stuck': is_stuck,
            'diff_stable': diff_stable,
            'best_executable_score': self.get_best_executable_candidate().compute_score() if self.get_best_executable_candidate() else None
        }
```

---

## 🎯 Corrected Phase 1 Implementation

### Change 1: After BRS validation

```python
# BRS is successful if tests FAIL on buggy code
brs_fail = not brs_report["ok"]
brs_pass_rate = brs_report["pass_rate"]

# P0-1 Phase 1: Record test candidate with diagnostic fields
error_stderr = str(brs_res.raw_stderr) if brs_res.raw_stderr else ""
error_stdout = str(brs_res.raw_stdout) if brs_res.raw_stdout else ""
combined_error = error_stderr + " " + error_stdout

safety_controller.add_test_candidate(
    iteration=it,
    test_diff=test_diff,
    brs_satisfied=brs_fail,  # CRITICAL: True = tests fail on buggy = good = reproduces bug
    public_pass_count=brs_report.get('passed', 0),
    public_fail_count=brs_report.get('failed', 0),
    runs_ok=brs_report.get('ok', False),
    patch_apply_ok=not brs_report.get('patch_apply_failed', False),
    policy_violation=not policy_validation_passed,
    syntax_error='SyntaxError' in combined_error,
    import_error=('ImportError' in combined_error or 'ModuleNotFoundError' in combined_error),
    collection_error=('collection error' in combined_error.lower() or 'cannot collect' in combined_error.lower()),
    error_message=error_stderr[:500] if error_stderr else ""
)

# NOTE: brs_satisfied naming is confusing - consider renaming to reproduces_bug
```

### Change 2: At test exhaustion (diagnostic logging)

```python
if not should_continue_test:
    console.print(f"[yellow]Safety guard: {stop_reason_test}[/yellow]")

    # P0-1 Phase 1: Diagnostic analysis (not activation)
    diagnostic = safety_controller.test_candidate_tracker.get_diagnostic_summary()

    console.print(f"[dim]╔═══ P0-1 DIAGNOSTIC ═══════════════════════╗[/dim]")
    console.print(f"[dim]║ Candidates: {diagnostic.get('total_candidates', 0)}                              ║[/dim]")
    console.print(f"[dim]║ Executable: {diagnostic.get('valid_for_fallthrough', 0)}                              ║[/dim]")
    console.print(f"[dim]║ Best score: {diagnostic.get('best_executable_score', 'N/A')}                           ║[/dim]")
    console.print(f"[dim]║ Stuck: {diagnostic.get('is_stuck', False)}                                    ║[/dim]")
    console.print(f"[dim]║ Stages: {diagnostic.get('stage_distribution', {})}        ║[/dim]")
    console.print(f"[dim]╚════════════════════════════════════════════╝[/dim]")

    write_jsonl(log_path, {
        "stage": "test_exhaustion_reached",
        "iteration": it,
        "diagnostic": diagnostic
    })

    break  # Phase 1: No fallthrough yet
```

### Change 3: Final metrics

```python
metrics = {
    "instance_id": instance_id,
    "overall_score": overall,
    # ... existing fields ...

    # P0-1 Phase 1: Full diagnostic data
    "p01_diagnostic": safety_controller.test_candidate_tracker.get_diagnostic_summary(),
    "test_iterations_used": safety_controller.test_iterations,
    "code_iterations_used": safety_controller.code_iterations,
}
```

---

## 🎯 Corrected Phase 1 Success Criteria

### Must Have
1. ✅ 2-3 instances record candidates successfully
2. ✅ No BRS/HFS/Overall regression
3. ✅ `p01_diagnostic` in metrics.json
4. ✅ No crashes

### Target (Corrected)
1. 🎯 At least 1 instance shows `valid_for_fallthrough > 0`
2. 🎯 `stage_distribution` reveals failure pattern (not uniform)
3. 🎯 `is_stuck=true` correlates with `diff_stable=true`
4. 🎯 Best executable candidate has score > 10 (meaningful)

### Abort Conditions
1. ❌ All candidates have `valid_for_fallthrough = 0` (predicate too strict)
2. ❌ Crashes or errors in P0-1 code
3. ❌ BRS/HFS regression

---

## 🎯 Corrected Phase 2 Implementation

### Activation Logic (Corrected)

```python
# At test exhaustion
if not should_continue_test and not fallthrough_active:
    console.print(f"[yellow]Safety guard: {stop_reason_test}[/yellow]")

    # P0-1 Phase 2: Check for safe fallthrough
    best = safety_controller.get_best_executable_candidate()  # NOT just best

    if best:  # has_valid_for_fallthrough implicit
        console.print(f"[cyan]╔═══ P0-1 FALLTHROUGH ACTIVATED ═══════════════╗[/cyan]")
        console.print(f"[cyan]║ Best executable candidate                      ║[/cyan]")
        console.print(f"[cyan]║ • Score: {best.compute_score():.1f}                                   ║[/cyan]")
        console.print(f"[cyan]║ • Iteration: {best.iteration}                                ║[/cyan]")
        console.print(f"[cyan]║ • Stage: {best.failure_stage:15s}                   ║[/cyan]")
        console.print(f"[cyan]║ • BRS satisfied: {best.brs_satisfied}                         ║[/cyan]")
        console.print(f"[cyan]╚═══════════════════════════════════════════════╝[/cyan]")

        fallthrough_active = True
        best_test_diff = best.test_diff

        write_jsonl(log_path, {
            "stage": "test_exhaustion_fallthrough_activated",
            "iteration": it,
            "best_candidate": best.to_dict(),
            "diagnostic": safety_controller.test_candidate_tracker.get_diagnostic_summary()
        })

        console.print("[cyan]→ Proceeding to Code phase for blocker diagnosis[/cyan]")
    else:
        console.print("[red]✗ No executable candidate for fallthrough[/red]")
        diagnostic = safety_controller.test_candidate_tracker.get_diagnostic_summary()
        console.print(f"[yellow]  Candidates: {diagnostic['total_candidates']}, Executable: {diagnostic['valid_for_fallthrough']}[/yellow]")

        write_jsonl(log_path, {
            "stage": "test_exhaustion_no_executable_candidate",
            "iteration": it,
            "diagnostic": diagnostic
        })
        break
```

---

## 🎯 Corrected Phase 2 Success Criteria

### Primary Goal (1st Priority)
1. ✅ **Code iterations > 0** for fallthrough instances
2. ✅ **Failure mode diagnosed**: TEST_EXHAUSTED → PATCH_FAIL / APPLY_FAIL / etc.
3. ✅ **Blocker location clear** in logs and metrics

### Secondary Goal (2nd Priority)
1. 🎯 **1+ partial → perfect** conversion (any improvement is good)
2. 🎯 **Hard ratio improves** (0.40 → 0.30-0.35)

### Must Have (Safety)
1. ✅ No infinite loops (fallthrough_active flag ensures once only)
2. ✅ No crashes in fallthrough path
3. ✅ Clear logging of activation

### Abort Conditions
1. ❌ Fallthrough makes results WORSE (more failures than before)
2. ❌ Infinite loops detected
3. ❌ Crashes in Code phase with fallthrough

---

## 📊 Corrected Analysis Queries (After Phase 1)

```bash
# 1. How many had executable candidates?
jq '.p01_diagnostic.valid_for_fallthrough' outputs/*/metrics.json

# 2. What stages blocked progression?
jq '.p01_diagnostic.stage_distribution' outputs/*/metrics.json

# 3. Were patterns stuck?
jq 'select(.p01_diagnostic.is_stuck == true) | .instance_id' outputs/*/metrics.json

# 4. Best executable scores
jq '{instance: .instance_id, best_score: .p01_diagnostic.best_executable_score}' \
   outputs/*/metrics.json

# 5. Would fallthrough help? (comprehensive)
jq 'select(.overall_score < 0.98 and .p01_diagnostic.valid_for_fallthrough > 0) |
    {instance: .instance_id,
     executable: .p01_diagnostic.valid_for_fallthrough,
     best_score: .p01_diagnostic.best_executable_score,
     stage: .p01_diagnostic.stage_distribution}' \
   outputs/*/metrics.json
```

---

## ⚠️ Risk Reassessment (Corrected)

### Phase 1: MINIMAL (Unchanged)
- Zero behavioral change
- 2-3 instances only
- Diagnostic data collection

### Phase 2: MODERATE → HIGH (Conditional)

**IF** predicates enforced (`is_valid_for_fallthrough`):
- 🟡 **MODERATE risk**

**IF** only score checked (`score > 0`):
- 🔴 **HIGH risk** (can pick unexecutable candidate)

**Current plan**: Predicates enforced → **MODERATE**

---

## 📋 Final Adjusted Timeline

### Phase 1 (Sample Mode)
- **Implementation**: 20-25 minutes (3 changes + 3 fields)
- **Test**: 10 minutes (1 Cohort 1 instance)
- **Deploy**: 2-3 instances from Cohort 2 (~30-40 minutes runtime)
- **Analysis**: 10 minutes
- **Total**: ~1.5 hours

### Phase 1 Decision Point
- **Review**: 10 minutes
- **Go/No-go**: 5 minutes

### Phase 2 (If approved)
- **Activate**: 5 minutes (change break to continue)
- **Deploy**: Remaining Cohort 2 instances (~2 hours runtime)
- **Analysis**: 20 minutes
- **Total**: ~2.5 hours

**Overall**: ~4 hours (vs original 6-7 hours)

---

## 🎯 Final Recommendation

**Proceed with corrected Phase 1**:
1. ✅ Fix `brs_satisfied` naming clarity
2. ✅ Add 3 diagnostic fields (signature, fingerprint, stage)
3. ✅ Implement predicate-based validation (not score threshold)
4. ✅ Sample 2-3 Cohort 2 instances (not all 10)
5. ✅ Primary goal = "reach Code phase + diagnose blocker"

**Key Changes from Original**:
- ❌ Remove "score > 0" as validity check
- ✅ Add execution predicate (`is_valid_for_fallthrough`)
- ✅ Add diagnostic predicate (`is_valid_for_diagnosis`)
- ✅ Sample deployment (2-3) instead of full (10)
- ✅ Add 3 diagnostic fields for root cause
- ✅ Phase 2 goal = diagnosis first, perfect conversion second

---

**Status**: ✅ Ready to implement with corrections
**Next**: Implement corrected Phase 1 code
**Date**: 2026-01-05
