# P0.9.3 Full Regression Performance Report

**Test Run**: p093-full-regression-20251229  
**Date**: 2025-12-29 16:38 KST  
**Duration**: TBD  
**Status**: ⏳ IN PROGRESS

---

## 🎯 Test Objective

Validate P0.9.3 Phase 1 (Validation Improvements) on all 4 baseline instances:
1. astropy__astropy-12907 (Perfect baseline - BRS 1.0)
2. sympy__sympy-20590 (Perfect baseline - BRS 1.0)
3. astropy__astropy-14182 (Known validation issues)
4. astropy__astropy-14365 (Known duplicate code issues)

**Goal**: Confirm validation improvements don't regress perfect instances while fixing problem instances.

---

## 📊 Results Summary

### Overall Metrics

| Metric | P0.9.2 Baseline | P0.9.3 Result | Change |
|--------|-----------------|---------------|--------|
| BRS (Bug Resolved Score) | TBD | TBD | TBD |
| Edit Script Success Rate | 16/16 (100%) | TBD | TBD |
| Anchor Validation Errors | 0 | TBD | TBD |
| Auto-fix Success Rate | 16/16 (100%) | TBD | TBD |
| Test Duration | ~22 min | TBD | TBD |

---

## 📈 Instance-by-Instance Results

### 1. astropy__astropy-12907 ✅ (Expected: Perfect)

**Baseline**: BRS 1.0, Overall 0.987

**P0.9.3 Results**:
- Iterations: TBD
- Edit Scripts: TBD
- Validation Errors: TBD
- Auto-fix Triggered: TBD
- Public Tests: TBD
- Result: TBD

**Analysis**: TBD

---

### 2. sympy__sympy-20590 ✅ (Expected: Perfect)

**Baseline**: BRS 1.0, Overall 0.994

**P0.9.3 Results**:
- Iterations: TBD
- Edit Scripts: TBD
- Validation Errors: TBD
- Auto-fix Triggered: TBD
- Public Tests: TBD
- Result: TBD

**Analysis**: TBD

---

### 3. astropy__astropy-14182 ⚠️ (Expected: Improved)

**Baseline**: BRS 1.0, TSS 0.5, Overall 0.825 (validation issues)

**P0.9.3 Results**:
- Iterations: TBD
- Edit Scripts: TBD
- Validation Errors: TBD (Expected: 0, was 3-6)
- Auto-fix Triggered: TBD
- Public Tests: TBD
- Result: TBD

**Analysis**: TBD

---

### 4. astropy__astropy-14365 ⚠️ (Expected: Improved)

**Baseline**: BRS 1.0, Overall 0.994 (duplicate code issues)

**P0.9.3 Results**:
- Iterations: TBD
- Edit Scripts: TBD
- Validation Errors: TBD
- Auto-fix Triggered: TBD (Expected: Yes)
- Auto-fix Success: TBD (Expected: 100%)
- Public Tests: TBD
- Result: TBD

**Analysis**: TBD

---

## 🔍 Detailed Analysis

### Validation Error Breakdown

TBD

### Auto-fix Performance

TBD

### Diff Quality

TBD

---

## ✅ Verification Checklist

- [ ] All 4 instances tested
- [ ] No regression on perfect instances (12907, 20590)
- [ ] Validation errors eliminated
- [ ] Auto-fix working on all instances
- [ ] Edit script success rate maintained
- [ ] Performance acceptable (<30 min total)

---

## 🎯 Success Criteria

### Must Have ✅
- [ ] Zero validation errors (vs 3-6 in P0.9.2)
- [ ] No regression on 12907, 20590
- [ ] Auto-fix 100% success rate

### Should Have 🎯
- [ ] 14182, 14365 improved or maintained
- [ ] Edit script success ≥ 90%
- [ ] Test duration ≤ 30 minutes

### Nice to Have 💫
- [ ] All instances pass public tests
- [ ] BRS maintained at 1.0
- [ ] Overall scores improved

---

## 📋 Next Steps

Based on results:

### If All Success Criteria Met ✅
1. Generate final performance report
2. Commit P0.9.3 Phase 1
3. Tag: v0.9.3-phase1-validation-verified
4. Merge to main
5. Deploy to production

### If Partial Success ⚠️
1. Analyze failures
2. Determine if regression or expected
3. Decide: Deploy anyway / Fix first / Investigate

### If Major Issues ❌
1. Rollback changes
2. Investigate root cause
3. Create fix plan
4. Re-test

---

**Report Status**: Template - Awaiting test completion  
**Next Update**: After test completion (~20-30 min)
