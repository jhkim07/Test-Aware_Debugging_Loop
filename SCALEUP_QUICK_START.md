# Scale-up Quick Start Guide

**목표**: 4개 인스턴스 → 100개 → 300개 (SWE-bench Lite 전체)

---

## TL;DR - Expected Results at Each Scale

### Current Baseline (4 instances)
```
Overall: 0.944  BRS: 100%  HFS: 100%  TSS: 0.875  Overfit Gap: 0.00
Cost: $20      Time: 2h
```

### Phase 1: 10 instances (3 days)
```
Overall: 0.78   BRS: 85%   HFS: 72%   TSS: 0.68   Overfit Gap: 0.05
Cost: $50      Time: 6h
```

### Phase 2: 50 instances (7 days)
```
Overall: 0.70   BRS: 82%   HFS: 65%   TSS: 0.63   Overfit Gap: 0.06
Cost: $250     Time: 30h
```

### Phase 3: 100 instances (14 days)
```
Overall: 0.68   BRS: 80%   HFS: 62%   TSS: 0.61   Overfit Gap: 0.07
Cost: $500     Time: 80h
```

### Phase 4: 300 instances (30 days)
```
Overall: 0.62   BRS: 75%   HFS: 56%   TSS: 0.58   Overfit Gap: 0.08
Cost: $1,650   Time: 260h
```

---

## Metric Distribution Expectations (300 instances)

### Overall Score Distribution
```
[0.0-0.2): ██░░░░░░░░░░░░░░░░░░  36 (12%)  <- Failed
[0.2-0.4): ████░░░░░░░░░░░░░░░░  54 (18%)  <- Poor
[0.4-0.6): ██████████░░░░░░░░░░  78 (26%)  <- Moderate
[0.6-0.8): ████████████░░░░░░░░  87 (29%)  <- Good
[0.8-1.0]: ██████░░░░░░░░░░░░░░  45 (15%)  <- Excellent

Success (≥ 0.5): 210/300 (70%)
```

### BRS Distribution
```
BRS = 0: ███████░░░░░░░░░░░░░  75 (25%)  <- Failed bug reproduction
BRS = 1: █████████████████████ 225 (75%)  <- Success
```

### Overfit Gap Distribution
```
Gap < 0.05:  ████████████████████ 120 (40%)  <- Excellent
0.05-0.10:   ████████████░░░░░░░░  75 (25%)  <- Good
0.10-0.15:   ██████░░░░░░░░░░░░░░  45 (15%)  <- Acceptable
Gap ≥ 0.15:  ████░░░░░░░░░░░░░░░░  60 (20%)  <- Concerning

Overfit controlled: 240/300 (80%)
```

### HFS (Hidden Fix Score) Distribution
```
HFS = 0.0:    ██████░░░░░░░░░░░░░░  48 (16%)  <- No fix
(0.0-0.5):    ████████████░░░░░░░░  84 (28%)  <- Partial
[0.5-1.0):    ████████████████░░░░ 126 (42%)  <- Good
HFS = 1.0:    ██████░░░░░░░░░░░░░░  42 (14%)  <- Perfect

Hidden tests passed: 210/300 (70%)
```

---

## Quick Start Commands

### Phase 1: 10 instances (Pilot)

```bash
# 1. Select instances
python scripts/select_instances.py \
  --strategy stratified \
  --n 10 \
  --output configs/instances/phase1_10instances.txt \
  --ensure_baseline

# 2. Create config
cat > configs/p10_phase1_test.yaml <<EOF
instances_file: configs/instances/phase1_10instances.txt
max_iterations: 8
use_edit_script: true
enable_gates: true
model: gpt-4o
EOF

# 3. Run test
USE_EDIT_SCRIPT=1 python run_evaluation.py \
  --config configs/p10_phase1_test.yaml \
  --run_id p10-phase1-$(date +%Y%m%d-%H%M%S)

# 4. Analyze results
python scripts/analyze_phase_results.py \
  --output_dir outputs/p10-phase1-* \
  --report PHASE1_RESULTS.md \
  --json PHASE1_RESULTS.json
```

**Expected time**: 6 hours
**Expected cost**: $50
**Expected success rate**: 70-80%

### Phase 2: 50 instances (Mid-scale)

```bash
# 1. Select instances
python scripts/select_instances.py \
  --strategy stratified \
  --n 50 \
  --output configs/instances/phase2_50instances.txt \
  --ensure_baseline

# 2. Run with 8 workers
# (Edit config to increase parallelism)

# 3. Monitor progress
watch -n 60 'ls outputs/p50-phase2-*/*/metrics.json | wc -l'

# 4. Generate report
python scripts/analyze_phase_results.py \
  --output_dir outputs/p50-phase2-* \
  --report PHASE2_RESULTS.md
```

**Expected time**: 30 hours (5 hours with 8 workers)
**Expected cost**: $250
**Expected success rate**: 65-75%

### Phase 3: 100 instances (Full-scale)

```bash
# 1. Select instances
python scripts/select_instances.py \
  --strategy representative \
  --n 100 \
  --output configs/instances/phase3_100instances.txt \
  --ensure_baseline

# 2. Run in batches
./run_phase3_batch.sh

# 3. Comprehensive analysis
python scripts/analyze_phase_results.py \
  --output_dir outputs/p100-phase3-* \
  --report PHASE3_COMPREHENSIVE_RESULTS.md \
  --json PHASE3_ANALYSIS.json

# 4. Generate plots
python scripts/plot_distributions.py \
  --json PHASE3_ANALYSIS.json \
  --output plots/phase3/
```

**Expected time**: 80 hours (5 hours with 16 workers)
**Expected cost**: $500
**Expected success rate**: 60-70%

### Phase 4: 300 instances (Complete)

```bash
# 1. Get all SWE-bench Lite instances
python scripts/get_all_swebench_lite.py \
  --output configs/instances/phase4_300instances.txt

# 2. Run in 6 batches (50 each)
for batch in {1..6}; do
  ./run_phase4_batch${batch}.sh
done

# 3. Final comprehensive analysis
python scripts/generate_final_report.py \
  --phases 1 2 3 4 \
  --output FINAL_COMPREHENSIVE_REPORT.md

# 4. Publication-ready visualizations
python scripts/create_publication_plots.py \
  --quality publication \
  --output plots/publication/
```

**Expected time**: 260 hours (8 hours with 32 workers)
**Expected cost**: $1,650
**Expected success rate**: 55-65%

---

## Key Success Criteria by Phase

### Phase 1 (10 instances)
- ✅ Mean Overall ≥ 0.70
- ✅ BRS ≥ 80%
- ✅ Overfit Gap ≤ 0.10
- ✅ Zero infrastructure failures
- ✅ Baseline 4 instances maintain performance

### Phase 2 (50 instances)
- ✅ Mean Overall ≥ 0.65
- ✅ Median Overall ≥ 0.70
- ✅ BRS ≥ 80%
- ✅ Mean Overfit Gap ≤ 0.10
- ✅ % instances with Gap > 0.15 < 10%

### Phase 3 (100 instances)
- ✅ Mean Overall ≥ 0.65
- ✅ Median Overall ≥ 0.70
- ✅ BRS ≥ 75%
- ✅ Mean HFS ≥ 0.60
- ✅ 95% CI width < 0.05

### Phase 4 (300 instances)
- ✅ Mean Overall ≥ 0.60
- ✅ Median Overall ≥ 0.65
- ✅ BRS ≥ 70%
- ✅ Mean HFS ≥ 0.55
- ✅ % Overfit Gap > 0.15 ≤ 20%

---

## Expected Performance Degradation

### Why Performance Decreases with Scale

```
Baseline (4) → Phase 4 (300):
  Overall: 0.944 → 0.62  (-34%)

Reasons:
1. Selection bias in baseline (easier instances)
2. Difficulty diversity increases
3. Complex multi-file bugs increase
4. Edge cases and ambiguous requirements
5. Natural variance in large-scale testing
```

### This is EXPECTED and NORMAL

- ✅ **Baseline selected for proof-of-concept** (not representative)
- ✅ **300 instances cover full difficulty spectrum**
- ✅ **0.62 overall at 300-scale is competitive** with SOTA
- ✅ **Overfit Gap < 0.10 maintained** (key innovation working)

---

## Critical Checkpoints

### After Phase 1 (10 instances)
**Decision point**: Proceed to Phase 2?

✅ **Proceed if**:
- Mean Overall ≥ 0.70
- Overfit Gap ≤ 0.10
- No infrastructure issues

❌ **Stop and investigate if**:
- Mean Overall < 0.60
- Overfit Gap > 0.15 for >20% instances
- Frequent crashes or errors

### After Phase 2 (50 instances)
**Decision point**: Proceed to Phase 3?

✅ **Proceed if**:
- Mean Overall ≥ 0.65
- BRS ≥ 75%
- Clear failure mode patterns identified
- Cost/instance < $6

❌ **Optimize first if**:
- Mean Overall < 0.55
- BRS < 70%
- Cost/instance > $8

### After Phase 3 (100 instances)
**Decision point**: Proceed to Phase 4?

✅ **Proceed if**:
- Mean Overall ≥ 0.63
- Statistical significance achieved
- Infrastructure stable
- Clear path to improvements

❌ **Refine approach if**:
- Mean Overall < 0.55
- High variance (std > 0.25)
- Systematic overfitting emerging

---

## Monitoring Dashboard (Real-time)

### Key Metrics to Watch

```bash
# Real-time progress
./monitor_phase.sh

Output:
  Progress: 45/100 instances (45%)
  Success rate: 32/45 (71%)
  Mean Overall: 0.68
  Mean BRS: 78%
  Mean Overfit Gap: 0.06
  ETA: 3.5 hours
  Cost so far: $225
```

### Alert Thresholds

```yaml
alerts:
  overfit_gap_high:
    threshold: 0.15
    action: "Investigate instance for overfitting"

  success_rate_low:
    threshold: 0.50
    action: "Check for systematic issues"

  cost_overrun:
    threshold: $7 per instance
    action: "Consider model downgrade"

  infrastructure_failure:
    threshold: 2 crashes
    action: "Pause and debug"
```

---

## Common Issues and Solutions

### Issue 1: Lower success rate than expected

**Diagnosis**:
```bash
python scripts/analyze_failures.py \
  --output_dir outputs/p*-phase*-* \
  --threshold 0.5
```

**Common causes**:
- Difficult instances selected
- Gates too strict
- LLM model selection

**Solutions**:
- Verify instance difficulty distribution
- Adjust gate thresholds if needed
- Try GPT-4o vs GPT-4o-mini comparison

### Issue 2: High overfit gap (> 0.15)

**Diagnosis**:
```bash
python scripts/analyze_overfit.py \
  --instances <high_gap_instances> \
  --output OVERFIT_ANALYSIS.md
```

**Common causes**:
- Public/Hidden split too skewed
- Test generation targeting public only
- Insufficient hidden test coverage

**Solutions**:
- Verify split ratio (should be ~70/30)
- Check test generation prompts
- Increase hidden test weight

### Issue 3: Infrastructure failures

**Diagnosis**:
```bash
grep -r "ERROR" logs/
python scripts/diagnose_failures.py
```

**Common causes**:
- Docker memory issues
- Network timeouts
- Concurrent resource conflicts

**Solutions**:
- Increase Docker memory limits
- Implement retry logic
- Reduce parallel workers

---

## Cost Optimization Strategies

### Strategy 1: Model Selection

```yaml
# High quality (expensive)
model: gpt-4o
cost_per_instance: $5-6

# Balanced (recommended)
model: gpt-4o-mini for easy instances
model: gpt-4o for hard instances
cost_per_instance: $3-4

# Budget (faster, lower quality)
model: gpt-4o-mini
cost_per_instance: $2-3
```

### Strategy 2: Caching

```python
# Enable LLM response caching
use_cache: true
cache_dir: .llm_cache/

# Estimated savings: 20-30% on retries
```

### Strategy 3: Early Termination

```yaml
# Stop iteration if no improvement
early_stop:
  enabled: true
  patience: 2  # Stop if no improvement for 2 iterations
  min_iterations: 2

# Estimated savings: 15-25% on difficult instances
```

---

## Timeline and Resource Requirements

### Phase 1: 10 instances
- **Duration**: 3 days
- **Compute**: 4 workers, 32GB RAM
- **Storage**: 50GB
- **Cost**: $50

### Phase 2: 50 instances
- **Duration**: 7 days
- **Compute**: 8 workers, 64GB RAM
- **Storage**: 100GB
- **Cost**: $250

### Phase 3: 100 instances
- **Duration**: 14 days
- **Compute**: 16 workers, 128GB RAM
- **Storage**: 200GB
- **Cost**: $500

### Phase 4: 300 instances
- **Duration**: 30 days
- **Compute**: 32 workers, 256GB RAM
- **Storage**: 500GB
- **Cost**: $1,650

### Total: ~8 weeks, ~$2,500

---

## Success Metrics Summary Table

| Metric | Baseline (4) | P1 (10) | P2 (50) | P3 (100) | P4 (300) |
|--------|--------------|---------|---------|----------|----------|
| **Overall** | 0.944 | 0.78 | 0.70 | 0.68 | 0.62 |
| **BRS** | 100% | 85% | 82% | 80% | 75% |
| **HFS** | 100% | 72% | 65% | 62% | 56% |
| **TSS** | 0.875 | 0.68 | 0.63 | 0.61 | 0.58 |
| **Overfit Gap** | 0.00 | 0.05 | 0.06 | 0.07 | 0.08 |
| **Success Rate** | 100% | 80% | 72% | 68% | 62% |
| **Cost/instance** | $5 | $5 | $5 | $5 | $5.50 |
| **Time/instance** | 30min | 36min | 40min | 45min | 50min |

---

## Final Deliverables

### Phase 1
- ✅ PHASE1_RESULTS.md
- ✅ Instance selection strategy validation
- ✅ Infrastructure verification

### Phase 2
- ✅ PHASE2_RESULTS.md
- ✅ Failure mode categorization
- ✅ Cost optimization insights

### Phase 3
- ✅ PHASE3_COMPREHENSIVE_RESULTS.md
- ✅ Statistical significance analysis
- ✅ Publication-quality plots
- ✅ Improvement recommendations

### Phase 4
- ✅ PHASE4_FINAL_COMPREHENSIVE_REPORT.md
- ✅ Complete metric distributions
- ✅ Repository-specific analysis
- ✅ Difficulty-stratified results
- ✅ Baseline comparisons
- ✅ Paper-ready visualizations

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Setup infrastructure** for Phase 1
3. **Run Phase 1 pilot** (3 days)
4. **Analyze results** and adjust strategy
5. **Proceed to Phase 2** if criteria met
6. **Iterate through phases** with continuous improvement
7. **Generate final report** for publication

---

**Plan Status**: Ready for Execution
**Estimated Completion**: ~8 weeks from start
**Total Budget**: ~$2,500
**Expected Final Overall Score**: 0.60-0.65 (300 instances)
**Key Innovation Maintained**: Overfit Gap < 0.10

---

**Contact**: Claude Code
**Version**: 1.0
**Date**: 2025-12-30
