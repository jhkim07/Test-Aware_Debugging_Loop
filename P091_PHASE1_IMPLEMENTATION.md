# P0.9.1 Phase 1 Implementation Summary

**Date**: 2025-12-26
**Version**: P0.9 → P0.9.1
**Strategy**: Policy Violation Auto-Retry (Phase 1 of 3)

---

## 🎯 Goal

Solve **astropy-14365 (File I/O policy violation)** without:
- ❌ Prompt bloat (P0.10's 87-line mistake)
- ❌ Policy loosening (security risk)
- ❌ Multiple simultaneous changes (debug complexity)

**Target**: 75% → 100% success rate, zero regression on existing perfect scores.

---

## 📊 Problem Analysis

### Current State (P0.9)
```
Success Rate: 75% (3/4)
Failed Instance: astropy-14365

Failure Log:
{"iter": 1, "stage": "test_policy_reject",
 "issues": ["file I/O patterns found: ['\\bopen\\(']"]}
```

**Root Cause**: LLM generates `open()` → Policy immediately rejects → 0% score

### Why NOT Policy Loosening?
From CURRENT_STATUS_AND_PRIORITIES.md:
```
P0.10 tried policy.py changes:
- Result: astropy-14365 solved (0% → 99.38%)
- But: BRS regression on 2 other instances (unclear causality)
- Lesson: Policy changes are risky
```

### Why NOT Prompt Bloat?
From CURRENT_STATUS_AND_PRIORITIES.md:
```
P0.10 added 87 lines to prompts.py:
- Result: BRS 100% → 0% (2 cases regressed)
- Cause: Attention dilution (BRS focus 25% → 17%)
- Lesson: Keep prompts minimal
```

---

## ✅ Phase 1 Solution: Auto-Retry with Corrective Feedback

### Principle
> "Don't change what works (prompts, policy). Just add a safety net (retry loop)."

### Implementation

**File**: `scripts/run_mvp.py` (lines 317-399)

**Core Logic**:
```python
# OLD (P0.9): Immediate rejection
if not validate_test_diff(test_diff):
    print("Policy rejected")
    break  # Game over

# NEW (P0.9.1): Retry with feedback
MAX_RETRIES = 2
for retry in range(MAX_RETRIES + 1):
    if validate_test_diff(test_diff):
        break  # Success

    if retry >= MAX_RETRIES:
        break  # Give up

    # Generate specific feedback
    feedback = generate_corrective_feedback(violations)

    # Regenerate test with feedback
    test_diff = create_tests(..., hint=feedback)
```

### Corrective Feedback Templates

**File I/O Violation** (most common):
```
POLICY VIOLATION: Your test contains file I/O operations that are not allowed.
REQUIRED FIX: Use pytest's tmp_path fixture for all file operations.
SAFE PATTERNS:
  - def test_example(tmp_path):  # Add tmp_path parameter
  - path = tmp_path / 'file.txt'  # Create path under tmp_path
  - path.write_text('content')   # Use write_text method
  - content = path.read_text()   # Use read_text method
FORBIDDEN PATTERNS:
  - open(...) - DO NOT use open() function
  - Path.open() - DO NOT use Path.open() method
Output ONLY the corrected unified diff format.
```

**Network I/O Violation**:
```
POLICY VIOLATION: Network I/O is not allowed in tests.
Remove all requests, urllib, socket, httpx calls.
```

**Skip/XFail Violation**:
```
POLICY VIOLATION: Tests must not use pytest.skip or pytest.xfail.
Tests must actually run and verify the bug fix.
```

---

## 🔍 Why This Works

### Evidence from LLM_INPUT_OUTPUT_EXAMPLE.md

**gpt-4o-mini's strength**: Precise copying/following of instructions
```
gpt-4o-mini (P0.9 success):
  "정답을 보고 그대로 베껴라" → ✅ 정확히 베낌

When given specific corrective feedback:
  "Do X, not Y" → ✅ Follows exactly
```

**Hypothesis**: gpt-4o-mini + concrete feedback → high success rate on retry

### Comparison to P0.10

| Aspect | P0.10 (Failed) | P0.9.1 Phase 1 (Expected) |
|--------|---------------|---------------------------|
| **Prompt Changes** | +87 lines | 0 lines |
| **System Prompt** | Modified | Untouched |
| **Policy Changes** | Loosened | Unchanged |
| **Feedback Type** | Generic rules | Specific violations |
| **Regression Risk** | High | Minimal |

---

## 📈 Expected Outcomes

### Scenario A: Phase 1 Succeeds
```
astropy-14365:
  Attempt 1: open() → Rejected
  Attempt 2: tmp_path.write_text() → Accepted
  Result: BRS=1.0, Overall=0.99

Full Results:
  Success Rate: 100% (4/4) ← Up from 75%
  Average BRS: 1.0 (maintained)
  Average Overall: ~0.99 ← Up from 0.7453
```

### Scenario B: Phase 1 Partially Succeeds
```
astropy-14365: Still fails after 2 retries
Other 3: Maintain perfect scores (no regression)

Result: 75% (3/4) - same as P0.9
Next Step: Activate Phase 2 (User message injection)
```

### Scenario C: Regression Detected
```
Any of 12907/20590/14182 drops from BRS=1.0

Action: Immediate rollback
Investigation: Why retry loop affected other instances?
```

---

## 🧪 Testing Plan

### Step 1: Single Instance Test
```bash
python scripts/run_mvp.py --config configs/p091_phase1_test.yaml
```

**Expected**:
- 1-2 retries triggered for astropy-14365
- Final test uses `tmp_path` instead of `open()`
- BRS=1.0, Overall>0.99

### Step 2: Full Regression Test
```bash
python scripts/run_mvp.py --config configs/p091_regression_test.yaml
```

**Acceptance Criteria**:
- ✅ PASS: All 4 instances with BRS=1.0
- ⚠️ PARTIAL: 3/4 succeed (14365 fails, but no regression)
- ❌ FAIL: Any of 12907/20590/14182 regress

---

## 🔄 Rollback Plan

If regression detected:

```bash
# 1. Revert to P0.9
git revert HEAD

# 2. Verify rollback
python scripts/run_mvp.py --config configs/p09_rollback_verify.yaml

# 3. Analyze failure
- Check which instance regressed
- Review retry loop logs
- Identify unexpected LLM behavior
```

---

## 🚀 Next Steps (If Phase 1 Insufficient)

### Phase 2: User Message Injection (instance-specific)
```python
# Only for astropy-14365
if instance_id == "astropy__astropy-14365":
    user_message += "\nIMPORTANT: Use tmp_path fixture for file ops"
```

**Pros**: Instance-isolated, no global impact
**Cons**: Requires hardcoding per instance

### Phase 3: Pre-Apply Gate (blocking + retry)
```python
# In pre_apply_gate.py
if detect_open_pattern(diff):
    return reject_and_regenerate()
```

**Pros**: Guaranteed enforcement
**Cons**: More complex logic, harder to debug

---

## 📝 Key Design Decisions

### Why Max 2 Retries?
- Balance between success probability and cost
- Most violations should be fixed in 1-2 attempts
- Prevents infinite loops on persistent issues

### Why Not Auto-Transform open() → tmp_path?
- Risk of breaking test semantics
- Complex regex transformations error-prone
- Prefer "reject + regenerate" over "auto-fix"

### Why Keep Policy Unchanged?
- Security: File I/O restrictions protect evaluation integrity
- Stability: Policy has been stable across P0.7-P0.9
- Clarity: Validation rules should be strict and clear

---

## 📚 Related Documents

- [CURRENT_STATUS_AND_PRIORITIES.md](CURRENT_STATUS_AND_PRIORITIES.md): P0.10 failure analysis
- [LLM_INPUT_OUTPUT_EXAMPLE.md](LLM_INPUT_OUTPUT_EXAMPLE.md): gpt-4o-mini behavior evidence
- [VALIDATION_STRICTNESS_ANALYSIS.md](VALIDATION_STRICTNESS_ANALYSIS.md): Policy comparison with SWE-bench

---

## ✅ Implementation Checklist

- [x] Implement retry loop in run_mvp.py
- [x] Add corrective feedback templates
- [x] Create Phase 1 test config (p091_phase1_test.yaml)
- [x] Create regression test config (p091_regression_test.yaml)
- [x] Document implementation (this file)
- [x] Commit changes with clear message
- [ ] Run Phase 1 single-instance test
- [ ] Run full regression test
- [ ] Analyze results and decide next phase

---

## 🎓 Lessons Applied from P0.10

1. ✅ **Minimal Changes**: Only run_mvp.py modified (retry loop)
2. ✅ **No Prompt Bloat**: System prompts untouched
3. ✅ **One Change at a Time**: Phase 1 only, test before Phase 2
4. ✅ **Clear Causality**: Retry loop isolated, easy to debug
5. ✅ **Instance Isolation**: Retry only triggers on violations (not all instances)

---

## 🎯 Success Metrics

**Primary**:
- Success rate: 75% → 100%
- BRS maintained: 1.0 on all 4 instances

**Secondary**:
- Average retries per instance: <1.5
- No increase in overall runtime: <10% overhead
- Clean logs: Clear indication of retry reasons

**Failure Criteria**:
- Any regression: BRS drops on 12907/20590/14182
- Cost explosion: >5 retries per instance average
- Unclear behavior: Logs don't show why retries triggered
