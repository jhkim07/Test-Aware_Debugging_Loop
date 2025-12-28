# Component 3 - 10 Instance Test Plan

**Date**: 2025-12-28 17:20 KST
**Purpose**: Validate Component 3 performance before full deployment
**Test Type**: Extended validation (4 → 10 instances)

---

## 🎯 Test Objectives

### Primary Goals:

1. **Verify 33% malformed rate is representative**
   - 4개 샘플이 너무 작았을 수 있음
   - 10개로 더 정확한 추정

2. **Estimate BRS/TSS/COMB scores**
   - Phase 0.9.1 baseline과 비교
   - Production 배포 여부 결정

3. **Confirm diff_validator bypass works across diverse instances**
   - 다양한 프로젝트 (Django, Matplotlib, Pytest, etc.)
   - 다양한 코드 패턴

---

## 📊 Test Configuration

### Instances (10 total):

#### Phase 0.9.1 Verified (4):
1. **astropy-12907** - Baseline: 0.987 ✅
2. **sympy-20590** - Baseline: 0.994 ✅
3. **astropy-14182** - Baseline: 0.825 (TSS=0.5) ⚠️
4. **astropy-14365** - Baseline: 0.994 ✅

#### New Instances (6):
5. **django-11815** - Web framework
6. **matplotlib-23314** - Visualization
7. **pytest-5692** - Testing framework
8. **scikit-learn-13779** - Machine learning
9. **sphinx-8474** - Documentation
10. **requests-2148** - HTTP library

### Settings:
```yaml
max_iters: 8
model: gpt-4o
USE_EDIT_SCRIPT: 1 (Component 3 enabled)
```

---

## ⏱️ Timeline Estimate

### Per Instance:
- Average: 15-20 minutes
- Max: 2 hours (time limit)

### Total:
- **Optimistic**: 2.5 hours (15 min × 10)
- **Realistic**: 3-4 hours (20 min × 10)
- **Pessimistic**: 6 hours (if many iterations needed)

**Expected Completion**: ~20:30 KST (3.5 hours from now)

---

## 📈 Success Criteria

### Must Have (Critical):

| Metric | Target | Rationale |
|--------|--------|-----------|
| **diff_validator calls** | 0 | Verify complete fix works across all instances |
| **Edit success rate** | ≥95% | Core Component 3 functionality |
| **No crashes** | 0 | Stability verification |

### Should Have (Important):

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Malformed rate** | ≤40% | Better than or similar to 4-instance test (33%) |
| **BRS** | ≥80% | Bug reproduction should work |
| **Average Overall** | ≥0.70 | Reasonable performance floor |

### Nice to Have (Aspirational):

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Malformed rate** | ≤20% | Improvement over 33% |
| **BRS** | ≥90% | Excellent bug reproduction |
| **Average Overall** | ≥0.85 | Close to Phase 0.9.1 (0.950) |

---

## 🔍 What We'll Learn

### Question 1: Is 33% malformed representative?

**If malformed ≤30%**:
- ✅ 4-instance sample was accurate
- → Proceed with current approach

**If malformed ≥40%**:
- ⚠️ 4-instance sample was lucky
- → Investigate malformed causes before full deployment

---

### Question 2: How does Component 3 compare to Phase 0.9.1?

**Expected scenarios**:

| Scenario | Avg Overall | Interpretation | Next Step |
|----------|-------------|----------------|-----------|
| **Best** | ≥0.90 | Component 3 matches baseline | → Full deployment |
| **Good** | 0.75-0.89 | Slightly lower but acceptable | → Deploy with monitoring |
| **Concerning** | 0.60-0.74 | Significantly lower | → Investigate before deployment |
| **Poor** | <0.60 | Major regression | → Fix issues first |

---

### Question 3: Are there patterns in malformed instances?

**Look for**:
- Specific projects (astropy vs others)
- File types (test files vs source files)
- Edit complexity (single vs multi-edit)
- LLM patterns (specific prompts failing)

---

## 📊 Comparison Matrix

### vs Phase 2 (Baseline):

| Metric | Phase 2 | Component 3 (Expected) |
|--------|---------|----------------------|
| Malformed rate | 92% | 30-40% |
| diff_validator calls | Many | 0 |
| Edit application | N/A | 95%+ |

### vs Phase 0.9.1 (Target):

| Metric | Phase 0.9.1 | Component 3 (Target) |
|--------|-------------|---------------------|
| Avg Overall | 0.950 | ≥0.75 (acceptable) |
| BRS | 100% | ≥80% (minimum) |
| Perfect scores | 75% | 50%+ (aspirational) |

---

## 🚦 Decision Tree

### After Test Completion:

```
Results Ready
  │
  ├─ diff_validator > 0?
  │   └─ YES → Debug fix, retest
  │   └─ NO → Continue ✅
  │
  ├─ Malformed ≤40%?
  │   └─ YES → Continue ✅
  │   └─ NO → Analyze causes
  │
  ├─ Avg Overall ≥0.75?
  │   └─ YES → Proceed to deployment decision
  │   └─ NO → Investigate regressions
  │
  └─ Deployment Decision:
      │
      ├─ Avg ≥0.90 → Full deployment ✅
      ├─ Avg 0.75-0.89 → Deploy with monitoring ⚠️
      └─ Avg <0.75 → More investigation needed ❌
```

---

## 📝 Test Execution

### Command:

```bash
USE_EDIT_SCRIPT=1 \
PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
python scripts/run_mvp.py \
  --config configs/p091_component3_10instances.yaml \
  --run-id p091-c3-10inst-$(date +%Y%m%d-%H%M%S) \
  > logs/nohup/p091-c3-10inst-$(date +%Y%m%d-%H%M%S).log 2>&1 &
```

### Monitoring:

```bash
# Check progress
tail -f logs/nohup/p091-c3-10inst-*.log

# Check diff_validator calls (should be 0)
grep -c "diff_validator" logs/nohup/p091-c3-10inst-*.log

# Check malformed rate
grep "Type: malformed" logs/nohup/p091-c3-10inst-*.log | wc -l
```

---

## 📊 Expected Output

### Metrics to Track:

1. **diff_validator calls**: 0 (critical)
2. **Malformed patches**: ~10-15 (30-40% of ~30-40 total errors)
3. **Line mismatch**: ~20-25 (60-70% of errors)
4. **Edit scripts applied**: ~40-50 (95%+ success)
5. **BRS**: 8-10 instances (80-100%)
6. **Average Overall**: 0.70-0.90

---

## 🎯 Post-Test Analysis

### Reports to Generate:

1. **Performance Summary**
   - BRS/TSS/COMB vs Phase 0.9.1
   - Malformed rate analysis
   - diff_validator verification

2. **Instance Analysis**
   - Which instances succeeded
   - Which instances struggled
   - Pattern identification

3. **Deployment Recommendation**
   - Go/No-Go decision
   - Risk assessment
   - Rollback plan

---

## 🚀 Next Steps After Test

### If Successful (Avg ≥0.75):

1. ✅ Generate performance report
2. ✅ Create deployment plan
3. ✅ (Optional) Run full 300-instance test
4. ✅ Deploy to production

### If Concerning (Avg 0.60-0.74):

1. ⚠️ Analyze failure patterns
2. ⚠️ Identify specific issues
3. ⚠️ Fix critical bugs
4. ⚠️ Retest before deployment

### If Poor (Avg <0.60):

1. ❌ Deep dive into failures
2. ❌ Fix Component 3 issues
3. ❌ Consider reverting to Phase 0.9.1
4. ❌ Extensive retesting needed

---

## 📌 Key Questions to Answer

1. ✅ **Is diff_validator bypass working?** (Must be 0 calls)
2. ✅ **What's the real malformed rate?** (4-instance was 33%)
3. ✅ **How's overall performance?** (Compare to 0.950 baseline)
4. ✅ **Are there failure patterns?** (Projects, file types, etc.)
5. ✅ **Is Component 3 production-ready?** (Go/No-Go decision)

---

**Test Plan Created**: 2025-12-28 17:20 KST
**Ready to Execute**: ✅ YES
**Expected Duration**: 3-4 hours
**Expected Completion**: ~20:30 KST

---

## 🎊 Let's Go!

All preparations complete. Ready to launch 10-instance extended validation test.

**Run command when ready!**
