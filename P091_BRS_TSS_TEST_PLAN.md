# Component 3 - BRS/TSS Measurement Test Plan

**Date**: 2025-12-28 22:00 KST
**Purpose**: Measure BRS/TSS/COMB scores and compare to Phase 0.9.1 baseline
**Test Type**: Performance validation

---

## 🎯 Test Objectives

### Primary Goals:

1. **Measure BRS (Bug Reproduction Score)**
   - Target: ≥80% (12/15 instances)
   - Baseline: Phase 0.9.1 had 100% (4/4)

2. **Measure TSS (Test Success Score)**
   - Target: ≥70% average
   - Baseline: Phase 0.9.1 had ~0.83 average (excluding 14182)

3. **Measure COMB (Combined Score)**
   - Target: ≥0.75 average
   - Baseline: Phase 0.9.1 had 0.950 average

4. **Compare to Phase 0.9.1 baseline**
   - Same 4 instances: Direct comparison
   - New 11 instances: Additional validation

---

## 📊 Test Configuration

### Instances (15 total):

#### Known Baseline (4):
1. **astropy-12907** - Baseline: 0.987 (BRS=1.0, TSS=1.0)
2. **sympy-20590** - Baseline: 0.994 (BRS=1.0, TSS=1.0)
3. **astropy-14182** - Baseline: 0.825 (BRS=1.0, TSS=0.5)
4. **astropy-14365** - Baseline: 0.994 (BRS=1.0, TSS=1.0)

#### Additional Validation (11):
5. astropy-6938
6. astropy-7746
7. sympy-13043
8. sympy-13471
9. sympy-13177
10. sympy-13480
11. astropy-7336
12. sympy-12481
13. sympy-13915
14. astropy-8005
15. sympy-11400

### Settings:
```yaml
max_iters: 8
model: gpt-4o
USE_EDIT_SCRIPT: 1
```

---

## 📈 Success Criteria

### Must Have (Critical):

| Metric | Target | Baseline | Pass/Fail |
|--------|--------|----------|-----------|
| **BRS** | ≥80% | 100% | Must pass |
| **TSS (avg)** | ≥70% | ~83% | Must pass |
| **COMB (avg)** | ≥0.75 | 0.950 | Must pass |
| **diff_validator** | 0 calls | N/A | Must pass |

### Should Have (Important):

| Metric | Target | Rationale |
|--------|--------|-----------|
| **BRS** | ≥90% | Close to Phase 0.9.1 |
| **TSS (avg)** | ≥75% | Good test quality |
| **COMB (avg)** | ≥0.80 | Acceptable performance |

### Nice to Have (Aspirational):

| Metric | Target | Rationale |
|--------|--------|-----------|
| **BRS** | 100% | Match Phase 0.9.1 |
| **COMB (avg)** | ≥0.90 | Very close to baseline |

---

## ⏱️ Timeline Estimate

### Per Instance:
- Average: 15-25 minutes
- Max: 2 hours

### Total:
- **Optimistic**: 4 hours (15 min × 15)
- **Realistic**: 5-6 hours (20-25 min × 15)
- **Pessimistic**: 8 hours (some difficult instances)

**Expected Start**: 22:00 KST (now)
**Expected Completion**: 03:00-04:00 KST (tomorrow)

---

## 📊 Metrics Calculation

### BRS (Bug Reproduction Score):
```
BRS = instances with bug reproduced / total instances
Target: ≥80% (12/15)
```

### TSS (Test Success Score):
```
TSS = average of public_pass_rate across instances
Target: ≥70%
```

### COMB (Combined Score):
```
COMB = (BRS + HFS + TSS) / 3
Target: ≥0.75
```

---

## 🎯 Decision Matrix

### After Test Completion:

```
BRS ≥ 80% AND TSS ≥ 70% AND COMB ≥ 0.75?
  │
  ├─ YES → Success! ✅
  │   │
  │   ├─ COMB ≥ 0.90? → Excellent! Production ready
  │   ├─ COMB 0.80-0.89? → Good! Deploy with monitoring
  │   └─ COMB 0.75-0.79? → Acceptable, deploy cautiously
  │
  └─ NO → Need investigation ⚠️
      │
      ├─ BRS < 80%? → Bug reproduction issues
      ├─ TSS < 70%? → Test quality issues
      └─ COMB < 0.75? → Overall performance low
```

---

## 📊 Comparison Analysis Plan

### For Known Baseline Instances (4):

| Instance | Phase 0.9.1 | Component 3 | Delta | Status |
|----------|-------------|-------------|-------|--------|
| astropy-12907 | 0.987 | ??? | ??? | TBD |
| sympy-20590 | 0.994 | ??? | ??? | TBD |
| astropy-14182 | 0.825 | ??? | ??? | TBD |
| astropy-14365 | 0.994 | ??? | ??? | TBD |

**Target**: Delta within ±10% (acceptable variance)

---

### For New Instances (11):

```
No baseline data
→ Measure Component 3 performance
→ Establish new baseline
→ Contribute to overall statistics
```

---

## 🔍 Analysis Plan

### 1. Overall Performance:

```bash
# Calculate from metrics.json files
- BRS: Count instances with bug_reproduced = true
- TSS: Average public_pass_rate across all instances
- COMB: Average overall_score across all instances
```

### 2. Baseline Comparison:

```bash
# For 4 known instances
- Compare BRS: Should be 100% (4/4)
- Compare TSS: Should be similar
- Compare COMB: Should be within ±10%
```

### 3. Error Analysis:

```bash
# From logs
- Malformed patches: Count and rate
- Line mismatch: Count and rate
- diff_validator calls: Should be 0
- Edit script failures: Count and investigate
```

---

## 📝 Test Execution

### Start Command:

```bash
USE_EDIT_SCRIPT=1 \
PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
python scripts/run_mvp.py \
  --config configs/p091_brs_tss_test.yaml \
  --run-id p091-brs-tss-$(date +%Y%m%d-%H%M%S) \
  > logs/nohup/p091-brs-tss-$(date +%Y%m%d-%H%M%S).log 2>&1 &
```

### Monitoring:

```bash
# Check progress
tail -f logs/nohup/p091-brs-tss-*.log

# Check diff_validator (should be 0)
grep -c "diff_validator" logs/nohup/p091-brs-tss-*.log

# Check instances completed
grep -c "Instance:" logs/nohup/p091-brs-tss-*.log
```

---

## 📊 Expected Results

### Optimistic Scenario:
```
BRS: 90-100% (13-15/15)
TSS: 75-85% average
COMB: 0.85-0.95 average
Malformed: 10-20%
diff_validator: 0 calls ✅
```

**Outcome**: Excellent! Ready for production.

---

### Realistic Scenario:
```
BRS: 80-90% (12-13/15)
TSS: 70-80% average
COMB: 0.75-0.85 average
Malformed: 15-25%
diff_validator: 0 calls ✅
```

**Outcome**: Good! Deploy with monitoring.

---

### Concerning Scenario:
```
BRS: 60-80% (9-12/15)
TSS: 60-70% average
COMB: 0.65-0.75 average
Malformed: 25-35%
diff_validator: 0 calls ✅
```

**Outcome**: Investigate issues before deployment.

---

### Poor Scenario:
```
BRS: <60% (<9/15)
TSS: <60% average
COMB: <0.65 average
Malformed: >35%
diff_validator: >0 calls ❌
```

**Outcome**: Significant issues, need fixes.

---

## 🎯 Post-Test Analysis Tasks

### 1. Metrics Extraction:

```bash
# Extract from each metrics.json
for dir in outputs/p091-brs-tss-*/*/; do
    if [ -f "$dir/metrics.json" ]; then
        cat "$dir/metrics.json"
    fi
done > brs_tss_metrics_summary.json
```

### 2. Calculate Scores:

```python
# Calculate BRS, TSS, COMB
import json
metrics = []
for file in glob("outputs/p091-brs-tss-*/*/metrics.json"):
    with open(file) as f:
        metrics.append(json.load(f))

brs = sum(m.get('bug_reproduced', False) for m in metrics) / len(metrics)
tss = sum(m.get('public_pass_rate', 0) for m in metrics) / len(metrics)
comb = sum(m.get('overall_score', 0) for m in metrics) / len(metrics)
```

### 3. Generate Report:

```markdown
# BRS/TSS Test Results

## Overall Performance:
- BRS: X% (Y/15)
- TSS: X% average
- COMB: X.XXX average

## Comparison to Phase 0.9.1:
- BRS: Baseline=100%, Component3=X%
- TSS: Baseline=83%, Component3=X%
- COMB: Baseline=0.950, Component3=X.XXX

## Decision: [Production Ready / Need Improvement / Not Ready]
```

---

## 📌 Key Questions to Answer

1. ✅ **BRS ≥ 80%?** (Bug reproduction works)
2. ✅ **TSS ≥ 70%?** (Test quality acceptable)
3. ✅ **COMB ≥ 0.75?** (Overall performance good)
4. ✅ **diff_validator = 0?** (Fix still working)
5. ✅ **Baseline match?** (4 known instances similar)
6. ✅ **Malformed rate?** (Should be 10-25%)
7. ✅ **Production ready?** (All criteria met)

---

## 🚀 Next Steps Based on Results

### If Success (COMB ≥ 0.75):

1. **Generate performance report**
2. **Create deployment plan**
3. **Start soft launch** (production deployment)
4. **(Optional) Full 300-instance test** for final validation

---

### If Acceptable (COMB 0.70-0.74):

1. **Analyze performance gaps**
2. **Identify improvement areas**
3. **Deploy with close monitoring**
4. **Iterate and improve**

---

### If Poor (COMB < 0.70):

1. **Detailed failure analysis**
2. **Identify root causes**
3. **Fix Component 3 issues**
4. **Retest before deployment**

---

**Test Plan Created**: 2025-12-28 22:00 KST
**Ready to Execute**: ✅ YES
**Expected Duration**: 5-6 hours
**Expected Completion**: 03:00-04:00 KST

**Let's measure the real performance!** 🚀
