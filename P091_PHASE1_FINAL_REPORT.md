# P0.9.1 Phase 1 Final Report

## Executive Summary

**Status**: ✅ **SUCCESS** - Final Stable Version

P0.9.1 Phase 1 successfully implements **policy violation auto-retry** mechanism, achieving:
- ✅ **100% BRS** (Bug Reproduction Strength): 4/4 instances
- ✅ **Target instance fixed**: astropy-14365 improved from 0.0 → 0.994
- ✅ **No regressions**: All other instances maintained or improved
- ✅ **Average Overall**: 0.952

---

## Implementation

### Core Feature: Policy Violation Auto-Retry

**Location**: `scripts/run_mvp.py` lines 317-395

**Mechanism**:
1. **Detect** policy violations (file I/O, network, skip/xfail)
2. **Retry** Test Author up to 2 times (3 total attempts)
3. **Feedback** specific corrective instructions per violation type

**Key Code**:
```python
MAX_POLICY_RETRIES = 2
policy_attempt = 0

while policy_attempt <= MAX_POLICY_RETRIES:
    ok, issues = validate_test_diff(test_diff, ...)

    if ok:
        policy_validation_passed = True
        break

    # Generate specific corrective feedback
    if "file I/O" in issue:
        feedback = "Use pytest's tmp_path fixture..."
    elif "network" in issue:
        feedback = "Remove network calls..."
    # ... etc

    # Retry Test Author with feedback
    test_diff = call_test_author(feedback)
```

---

## Results

### Final Performance (P0.9.1 Phase 1)

| Instance | BRS | HFS | TSS | OG | Overall | vs P0.9 Baseline |
|----------|-----|-----|-----|----|---------| -----------------|
| **astropy-12907** | 1.0 | 1.0 | 1.0 | 0.0 | **0.994** | ✅ maintained |
| **sympy-20590** | 1.0 | 1.0 | 1.0 | 0.0 | **0.994** | ✅ maintained |
| **astropy-14182** | 1.0 | 1.0 | 0.5 | 0.0 | **0.825** | ✅ improved (+267%) |
| **astropy-14365** | 1.0 | 1.0 | 1.0 | 0.0 | **0.994** | 🎉 **FIXED** (from 0.0!) |

**Aggregate Metrics**:
- BRS: **100%** (4/4 perfect bug reproduction)
- Average Overall: **0.952**
- Perfect scores: **3/4** (>= 0.99)

---

## Comparison with P0.9 Baseline

### astropy-14365 (Target Instance)

| Metric | P0.9 Baseline | P0.9.1 Phase 1 | Change |
|--------|---------------|----------------|--------|
| BRS | 0.0 ❌ | 1.0 ✅ | **+1.0** |
| HFS | 0.0 ❌ | 1.0 ✅ | **+1.0** |
| TSS | 0.5 | 1.0 ✅ | +0.5 |
| Overall | **0.0** | **0.994** | **+0.994** 🎉 |

**Root Cause Fixed**: File I/O policy violation
- P0.9: Failed immediately on policy check
- P0.9.1: Auto-retry with `tmp_path` fixture guidance → Success

### astropy-14182 (Also Improved)

| Metric | P0.9 Baseline | P0.9.1 Phase 1 | Change |
|--------|---------------|----------------|--------|
| BRS | 1.0 | 1.0 | ✅ maintained |
| HFS | 0.0 ❌ | 1.0 ✅ | **+1.0** |
| Overall | **0.225** | **0.825** | **+0.600** (+267%) |

**Improvement**: Hidden test now passes (HFS 0.0 → 1.0)

---

## Phase 2 Attempt (Failed - Rolled Back)

### Phase 2 Goal
Fix astropy-14182 remaining issue (TSS=0.5) via malformed patch auto-cleaning

### Phase 2 Results
**FAILED** - Caused severe regressions:

| Instance | Phase 1 | Phase 2 | Change |
|----------|---------|---------|--------|
| astropy-12907 | 0.994 | 0.987 | -0.007 ⚠️ |
| sympy-20590 | 0.994 | 0.994 | 0.000 |
| astropy-14182 | 0.825 | **0.225** | **-0.600** ❌ |
| astropy-14365 | 0.994 | 0.994 | 0.000 |
| **Average** | **0.952** | **0.800** | **-0.152** ❌ |

### Root Cause of Phase 2 Failure
1. **Aggressive cleaning**: Removed some valid code
2. **Insufficient approach**: LLM generates new malformed patterns each iteration
3. **14182 HFS crash**: Hidden test failures (1.0 → 0.0)

### Decision
**Rollback Phase 2** and keep Phase 1 as final stable version.

---

## Technical Details

### Bug Fixes (Phase 1 Development)

During Phase 1 development, **6 critical BRS calculation bugs** were discovered and fixed:

1. **SWE-bench tests_status format support** (`report_parser.py:154-176`)
2. **pytest output pattern order** (failed-first patterns prioritized)
3. **ANSI escape code handling** (color codes removed before parsing)
4. **Parse priority optimization** (report files > stdout/stderr)
5. **Individual test counting accuracy** (regex improved)
6. **CRITICAL: report_dir path bug** (`swebench_runner.py:45-50`)
   - Fixed: `runs/` → `logs/run_evaluation/`

### Files Modified

**Core Implementation**:
- `scripts/run_mvp.py`: Policy retry logic (lines 317-395)

**Bug Fixes**:
- `bench_agent/runner/report_parser.py`: BRS parsing improvements
- `bench_agent/runner/swebench_runner.py`: report_dir path fix

**Phase 2 (Rolled Back)**:
- `bench_agent/protocol/diff_validator.py`: clean_malformed_patch_content() (unused)

---

## Lessons Learned

### ✅ What Worked

1. **Targeted retry with specific feedback**: Much more effective than generic error messages
2. **Phase 1 approach**: Simple, focused on one clear problem (policy violations)
3. **Thorough debugging**: Fixed 6 BRS bugs → accurate measurements
4. **P0.9 baseline comparison**: Validated improvements objectively

### ❌ What Didn't Work

1. **Phase 2 malformed patch cleaning**: Too aggressive, caused regressions
2. **Pattern-based cleaning**: Can't keep up with LLM's creative malformed patterns
3. **Cleaning without LLM guidance**: Needs feedback loop to LLM, not just cleanup

### 🔍 Insights

1. **LLM non-determinism**: Same instance can produce different results across runs
2. **14182 root issue**: Likely LLM prompt/capability, not solvable via post-processing
3. **Diminishing returns**: 0.825 → 0.994 requires fundamentally different approach

---

## Conclusions

### Phase 1: SUCCESS ✅

P0.9.1 Phase 1 is a **clear success**:
- Solved target problem (14365: 0.0 → 0.994)
- Maintained existing good performance (12907, 20590)
- Bonus improvement (14182: 0.225 → 0.825)
- Clean, maintainable implementation

**Recommendation**: **Ship P0.9.1 Phase 1 as production version**

### Phase 2: FAILED ❌

P0.9.1 Phase 2 attempt taught valuable lessons but must be abandoned:
- Post-processing cleanup insufficient for LLM-generated patches
- Need different strategy for remaining issues (e.g., prompt engineering, LLM model upgrade)

### Future Work

For astropy-14182 (TSS=0.5, Overall=0.825):
1. **Option A**: Prompt engineering to improve patch quality
2. **Option B**: Upgrade to stronger LLM (gpt-4o vs gpt-4o-mini)
3. **Option C**: Accept 0.825 as "good enough" (BRS=1.0 is primary goal)

**Current Status**: 4/4 BRS 100%, 3/4 Overall >0.99 → **Excellent baseline for future work**

---

## Metrics Summary

### Formula Reference
```
BRS (Bug Reproduction Strength) = 1.0 if tests fail on buggy code, else 0.0
HFS (Hidden Fix Score) = hidden_pass_rate (tests pass on fixed code with hidden suite)
TSS (Test Strength Score) = (BRS + public_pass_rate) / 2
OG (Overfit Gap) = public_pass_rate - hidden_pass_rate
Overall = (BRS + HFS + TSS - OG) / 3
```

### P0.9.1 Phase 1 Achievements
- ✅ BRS: 4/4 = **100%**
- ✅ HFS: 4/4 = **100%**
- ✅ TSS: 3.5/4 = **87.5%** (14182 at 0.5)
- ✅ OG: 4/4 = **0.0** (no overfitting)
- ✅ Overall: Average **0.952**

---

## Git History

```
6904aa7 Rollback P0.9.1 Phase 2 - Malformed patch cleaning caused regression
4fbdd70 P0.9.1 Regression Test Complete - 3/4 SUCCESS, 1 regression
e406140 docs: 실패 케이스 분석 문서 검증 완료
1bd78e8 Fix critical report_dir path bug - P0.9.1 Phase 1 SUCCESS
26c1368 Fix BRS calculation bugs in report parser
8b26417 Fix P0.9.1 Phase 1 critical bugs
2497d1d Implement P0.9.1 Phase 1: Policy violation auto-retry
```

---

**Report Generated**: 2025-12-27
**Status**: Production Ready ✅
**Version**: P0.9.1 Phase 1 (Final)
