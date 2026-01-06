# Test-Aware Debugging Loop - Scale-up Plan (n ≥ 100, target 300)

**작성일**: 2025-12-30
**현재 상태**: P0.9.3 Phase 2 (4개 인스턴스 검증 완료)
**목표**: SWE-bench Lite 100개 → 300개 전체 확장

---

## Executive Summary

### Current Baseline (4 instances)
- **Overall**: 0.944 (94.4%)
- **BRS**: 100% (4/4)
- **HFS**: 100%
- **TSS**: 0.875 (avg)
- **Overfit Gap**: 0.00

### Scale-up Objectives
1. **Phase 1 (10 instances)**: Infrastructure validation, 2-3 days
2. **Phase 2 (50 instances)**: Mid-scale performance analysis, 1 week
3. **Phase 3 (100 instances)**: Full-scale test, statistical significance, 2 weeks
4. **Phase 4 (300 instances)**: Complete SWE-bench Lite coverage, 1 month

### Expected Outcomes (Conservative Estimates)

**100-instance scale predictions**:
```
Overall:      0.65-0.75  (현재 0.944에서 하락 예상)
BRS:          75-85%     (현재 100%에서 하락 예상)
HFS:          60-70%     (현재 100%에서 하락 예상)
TSS:          0.55-0.65  (현재 0.875에서 하락 예상)
Overfit Gap:  0.00-0.10  (현재 0.00 유지 목표)
```

**300-instance scale predictions**:
```
Overall:      0.55-0.65  (더 다양한 난이도 분포)
BRS:          65-75%     (복잡한 버그 증가)
HFS:          50-60%     (실제 fix 어려움 증가)
TSS:          0.45-0.55  (테스트 생성 난이도 증가)
Overfit Gap:  0.00-0.15  (overfitting 위험 관리)
```

### Critical Success Factors
1. ✅ **Zero regression** on baseline 4 instances
2. ✅ **Overfit Gap < 0.15** across all scales
3. ✅ **BRS ≥ 65%** at 300-instance scale
4. ✅ **Statistical significance** (p < 0.05)
5. ✅ **Cost efficiency** (< $5 per instance)

---

## Phase 1: 10-Instance Pilot (Days 1-3)

### Objectives
- **Validate infrastructure** for parallel execution
- **Identify bottlenecks** in pipeline
- **Establish baseline metrics** for comparison
- **Test monitoring systems**

### Instance Selection Strategy

**Diversity-based sampling** (10개 선택):

```python
# Criteria:
# 1. Repository diversity (astropy, sympy, django, matplotlib, sklearn)
# 2. Difficulty spread (easy, medium, hard)
# 3. Code size variety (small, medium, large patches)
# 4. Test count distribution (few, many tests)

selected_instances = [
    # Easy (baseline 포함)
    "astropy__astropy-12907",  # baseline ✅
    "sympy__sympy-20590",      # baseline ✅

    # Medium
    "astropy__astropy-14182",  # baseline (TSS=0.5) ✅
    "django__django-12453",    # new
    "matplotlib__matplotlib-23476", # new

    # Hard
    "astropy__astropy-14365",  # baseline (critical) ✅
    "sklearn__scikit-learn-13142", # new
    "sympy__sympy-18057",      # new

    # Very Hard
    "django__django-13658",    # new
    "matplotlib__matplotlib-25332", # new
]
```

### Expected Metrics Distribution

**Phase 1 Predictions (10 instances)**:

| Metric | Min | Q1 | Median | Q3 | Max | Mean | Std |
|--------|-----|----|----|----|----|------|-----|
| Overall | 0.50 | 0.70 | 0.80 | 0.90 | 0.99 | 0.78 | 0.15 |
| BRS | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.85 | 0.35 |
| HFS | 0.00 | 0.50 | 0.80 | 1.00 | 1.00 | 0.72 | 0.30 |
| TSS | 0.00 | 0.50 | 0.75 | 1.00 | 1.00 | 0.68 | 0.32 |
| Overfit Gap | -0.05 | 0.00 | 0.02 | 0.08 | 0.20 | 0.05 | 0.08 |

**Success Criteria**:
- ✅ Mean Overall ≥ 0.70
- ✅ Mean BRS ≥ 0.80
- ✅ Mean Overfit Gap ≤ 0.10
- ✅ Zero crashes or infrastructure failures
- ✅ All 4 baseline instances maintain performance

### Infrastructure Setup

**Parallel Execution**:
```yaml
# configs/p10_phase1_test.yaml
instances_file: configs/instances/phase1_10instances.txt
max_iterations: 8
parallel_workers: 4  # 동시 4개 실행
timeout_per_instance: 3600  # 1시간
use_edit_script: true
enable_gates: true
```

**Monitoring**:
```bash
# Real-time monitoring script
./monitor_phase1_test.sh

# Metrics collection
- Per-instance metrics.json
- Aggregate statistics
- Cost tracking
- Time tracking
- Error logs
```

### Execution Plan

**Day 1**: Setup and validation
```bash
# 1. Create instance list
cat > configs/instances/phase1_10instances.txt <<EOF
astropy__astropy-12907
sympy__sympy-20590
astropy__astropy-14182
astropy__astropy-14365
django__django-12453
matplotlib__matplotlib-23476
sklearn__scikit-learn-13142
sympy__sympy-18057
django__django-13658
matplotlib__matplotlib-25332
EOF

# 2. Verify environment
./setup_swebench_env.sh

# 3. Run single instance test (dry run)
USE_EDIT_SCRIPT=1 python run_evaluation.py \
  --config configs/p10_phase1_test.yaml \
  --instances astropy__astropy-12907
```

**Day 2**: Full execution
```bash
# Run all 10 instances
nohup ./run_phase1_test.sh > logs/nohup/phase1.log 2>&1 &

# Monitor progress
./monitor_phase1_test.sh
```

**Day 3**: Analysis and reporting
```bash
# Generate report
python scripts/analyze_phase1_results.py

# Create distribution plots
python scripts/plot_metric_distributions.py
```

---

## Phase 2: 50-Instance Mid-Scale (Days 4-10)

### Objectives
- **Statistical power**: Sufficient sample size for meaningful analysis
- **Pattern identification**: Discover common failure modes
- **Cost optimization**: Identify expensive instances
- **Strategy tuning**: Adjust parameters based on Phase 1 learnings

### Instance Selection Strategy

**Stratified sampling** (50개 선택):

```python
# Stratification criteria:
# 1. Repository (10 repos × 5 instances each)
# 2. Difficulty tiers (Easy:Medium:Hard = 2:3:5 비율)
# 3. Test complexity (Public test count: 1-5, 6-10, 11+)
# 4. Code complexity (Patch size: <500B, 500-2KB, >2KB)

repositories = {
    'astropy': 8,
    'django': 8,
    'matplotlib': 7,
    'sympy': 7,
    'scikit-learn': 6,
    'requests': 4,
    'pandas': 4,
    'flask': 3,
    'pytest': 2,
    'sphinx': 1
}

difficulty_distribution = {
    'easy': 10,      # Overall > 0.8 expected
    'medium': 15,    # Overall 0.5-0.8
    'hard': 15,      # Overall 0.3-0.5
    'very_hard': 10  # Overall < 0.3
}
```

### Expected Metrics Distribution

**Phase 2 Predictions (50 instances)**:

| Metric | Min | Q1 | Median | Q3 | Max | Mean | Std |
|--------|-----|----|----|----|----|------|-----|
| Overall | 0.20 | 0.60 | 0.72 | 0.85 | 0.99 | 0.70 | 0.20 |
| BRS | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.82 | 0.37 |
| HFS | 0.00 | 0.40 | 0.67 | 0.90 | 1.00 | 0.65 | 0.28 |
| TSS | 0.00 | 0.50 | 0.67 | 0.88 | 1.00 | 0.63 | 0.30 |
| Overfit Gap | -0.10 | 0.00 | 0.03 | 0.10 | 0.30 | 0.06 | 0.10 |

**Distribution Analysis**:

```
Overall Score Distribution (예상):
  [0.0-0.2):  ████░░░░░░░░░░░░░░░░  5 instances (10%)
  [0.2-0.4):  ████████░░░░░░░░░░░░  8 instances (16%)
  [0.4-0.6):  ████████████░░░░░░░░ 12 instances (24%)
  [0.6-0.8):  ████████████████░░░░ 15 instances (30%)
  [0.8-1.0]:  ██████████░░░░░░░░░░ 10 instances (20%)

BRS Distribution (예상):
  BRS = 0:  █████░░░░░░░░░░░░░░░  9 instances (18%)  <- 버그 재현 실패
  BRS = 1:  █████████████████████ 41 instances (82%)  <- 성공

Overfit Gap Distribution (예상):
  Gap < 0.05:  ███████████████░░░░  30 instances (60%)  <- Excellent
  0.05-0.10:   ██████░░░░░░░░░░░░░  12 instances (24%)  <- Good
  0.10-0.15:   ████░░░░░░░░░░░░░░░   6 instances (12%)  <- Acceptable
  Gap > 0.15:  ██░░░░░░░░░░░░░░░░░   2 instances (4%)   <- Concerning
```

### Success Criteria

**Quantitative Targets**:
- ✅ Mean Overall ≥ 0.65
- ✅ Median Overall ≥ 0.70
- ✅ BRS ≥ 80%
- ✅ Mean Overfit Gap ≤ 0.10
- ✅ % instances with Gap > 0.15 < 10%

**Qualitative Targets**:
- ✅ Zero infrastructure crashes
- ✅ Clear failure mode categorization
- ✅ Cost < $5 per instance
- ✅ Execution time < 1 hour per instance (median)

### Execution Plan

**Days 4-5**: Preparation
```bash
# 1. Stratified sampling
python scripts/select_instances.py \
  --strategy stratified \
  --n 50 \
  --output configs/instances/phase2_50instances.txt

# 2. Verify diversity
python scripts/analyze_instance_diversity.py \
  --instances configs/instances/phase2_50instances.txt

# 3. Setup parallel execution
# 8 workers (2× Phase 1)
```

**Days 6-8**: Execution
```bash
# Parallel execution with 8 workers
nohup ./run_phase2_test.sh > logs/nohup/phase2.log 2>&1 &

# Expected time: 50 instances × 45 min / 8 workers ≈ 5 hours

# Monitor:
watch -n 60 ./monitor_phase2_test.sh
```

**Days 9-10**: Analysis
```bash
# Generate comprehensive report
python scripts/generate_phase2_report.py \
  --output PHASE2_RESULTS.md

# Statistical analysis
python scripts/statistical_analysis.py \
  --baseline phase1 \
  --current phase2 \
  --test mann-whitney  # Non-parametric test

# Failure mode analysis
python scripts/analyze_failure_modes.py
```

---

## Phase 3: 100-Instance Full Scale (Days 11-24)

### Objectives
- **Statistical significance**: Robust evaluation with n=100
- **Comprehensive coverage**: Major repositories and bug types
- **Performance characterization**: Detailed distribution analysis
- **Production readiness**: Validate scalability and reliability

### Instance Selection Strategy

**Representative sampling** (100개):

```python
# Full SWE-bench Lite diversity
# Target: Representative of all 300 instances

selection_criteria = {
    'repository_coverage': {
        # Top 15 repositories
        'django': 15,
        'scikit-learn': 12,
        'matplotlib': 12,
        'pytest': 10,
        'sympy': 10,
        'astropy': 8,
        'requests': 6,
        'flask': 5,
        'pandas': 5,
        'sphinx': 5,
        'seaborn': 4,
        'pylint': 3,
        'httpie': 3,
        'marshmallow': 1,
        'pydicom': 1,
    },

    'difficulty_tiers': {
        'easy': 15,          # Overall > 0.8 expected
        'medium': 30,        # Overall 0.5-0.8
        'hard': 35,          # Overall 0.3-0.5
        'very_hard': 20,     # Overall < 0.3
    },

    'bug_categories': {
        'logic_error': 25,
        'type_error': 20,
        'api_change': 15,
        'performance': 10,
        'edge_case': 15,
        'regression': 10,
        'documentation': 5,
    },

    'code_complexity': {
        'single_file': 60,
        'multi_file': 30,
        'cross_module': 10,
    },
}
```

### Expected Metrics Distribution

**Phase 3 Predictions (100 instances)**:

| Metric | Min | Q1 | Median | Q3 | Max | Mean | Std | CV |
|--------|-----|----|--------|----|----|------|-----|-----|
| Overall | 0.10 | 0.55 | 0.70 | 0.82 | 0.99 | 0.68 | 0.22 | 0.32 |
| BRS | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.80 | 0.39 | 0.49 |
| HFS | 0.00 | 0.35 | 0.63 | 0.85 | 1.00 | 0.62 | 0.30 | 0.48 |
| TSS | 0.00 | 0.45 | 0.67 | 0.87 | 1.00 | 0.61 | 0.32 | 0.52 |
| Overfit Gap | -0.15 | 0.00 | 0.04 | 0.12 | 0.35 | 0.07 | 0.11 | 1.57 |
| Patch Size | 200B | 650B | 1.1KB | 2.3KB | 8KB | 1.5KB | 1.2KB | 0.80 |
| Iterations | 1 | 2 | 3 | 5 | 8 | 3.5 | 2.1 | 0.60 |
| Time (min) | 5 | 25 | 42 | 68 | 120 | 48 | 28 | 0.58 |

**Detailed Distributions**:

```
Overall Score Distribution (100 instances 예상):
  [0.0-0.1):  ███░░░░░░░░░░░░░░░░░  3 instances (3%)
  [0.1-0.2):  ████░░░░░░░░░░░░░░░░  4 instances (4%)
  [0.2-0.3):  ██████░░░░░░░░░░░░░░  6 instances (6%)
  [0.3-0.4):  ████████░░░░░░░░░░░░  8 instances (8%)
  [0.4-0.5):  ███████████░░░░░░░░░ 11 instances (11%)
  [0.5-0.6):  ████████████████░░░░ 16 instances (16%)
  [0.6-0.7):  ███████████████████░ 19 instances (19%)
  [0.7-0.8):  ████████████████░░░░ 16 instances (16%)
  [0.8-0.9):  ██████████░░░░░░░░░░ 10 instances (10%)
  [0.9-1.0]:  ███████░░░░░░░░░░░░░  7 instances (7%)

BRS Distribution (100 instances 예상):
  BRS = 0:  ████░░░░░░░░░░░░░░░░ 20 instances (20%)  <- 버그 재현 실패
  BRS = 1:  ████████████████████ 80 instances (80%)  <- 성공

HFS Distribution (100 instances 예상):
  HFS = 0.0:       ██████░░░░░░░░░░░░░░ 12 instances (12%)  <- 완전 실패
  (0.0-0.33):      ████████░░░░░░░░░░░░ 16 instances (16%)  <- Low
  [0.33-0.67):     ████████████░░░░░░░░ 24 instances (24%)  <- Medium
  [0.67-1.0):      ██████████████░░░░░░ 28 instances (28%)  <- High
  HFS = 1.0:       ████████████░░░░░░░░ 20 instances (20%)  <- Perfect

TSS Distribution (100 instances 예상):
  TSS = 0.0:       ████████░░░░░░░░░░░░ 18 instances (18%)  <- 테스트 생성 실패
  (0.0-0.5):       ██████████░░░░░░░░░░ 22 instances (22%)  <- Weak tests
  [0.5-0.75):      ██████████████░░░░░░ 26 instances (26%)  <- Moderate
  [0.75-1.0):      ████████░░░░░░░░░░░░ 14 instances (14%)  <- Strong
  TSS = 1.0:       ████████████░░░░░░░░ 20 instances (20%)  <- Perfect

Overfit Gap Distribution (100 instances 예상):
  Gap < 0.00:      ██████░░░░░░░░░░░░░░ 12 instances (12%)  <- 과소적합
  [0.00-0.05):     ████████████████████ 40 instances (40%)  <- Excellent
  [0.05-0.10):     ████████████░░░░░░░░ 24 instances (24%)  <- Good
  [0.10-0.15):     ██████░░░░░░░░░░░░░░ 12 instances (12%)  <- Acceptable
  [0.15-0.20):     ████░░░░░░░░░░░░░░░░  8 instances (8%)   <- Warning
  Gap ≥ 0.20:      ██░░░░░░░░░░░░░░░░░░  4 instances (4%)   <- Critical
```

### Success Criteria

**Primary Metrics**:
- ✅ **Mean Overall ≥ 0.65** (Target: 0.68)
- ✅ **Median Overall ≥ 0.70** (Robust central tendency)
- ✅ **BRS ≥ 75%** (At least 75 instances reproduce bug)
- ✅ **Mean HFS ≥ 0.60** (60% hidden test success)
- ✅ **Mean Overfit Gap ≤ 0.10** (Overfitting controlled)

**Distribution Requirements**:
- ✅ **% Overall > 0.8**: ≥ 15% (at least 15 "excellent" instances)
- ✅ **% Overall < 0.3**: ≤ 20% (at most 20 "failed" instances)
- ✅ **% Gap > 0.15**: ≤ 15% (overfitting under control)
- ✅ **% BRS = 1**: ≥ 75% (bug reproduction success)

**Statistical Significance**:
- ✅ **95% CI for mean Overall**: [0.64, 0.72] (narrow CI)
- ✅ **vs. Baseline (4 instances)**: p < 0.05 (if different)
- ✅ **vs. Phase 2 (50 instances)**: consistency check

**Operational Metrics**:
- ✅ **Mean time per instance**: ≤ 50 minutes
- ✅ **Mean cost per instance**: ≤ $5
- ✅ **Infrastructure reliability**: ≥ 99% (≤ 1 crash)
- ✅ **Zero regression** on 4 baseline instances

### Execution Plan

**Days 11-12**: Preparation
```bash
# 1. Representative sampling
python scripts/select_instances.py \
  --strategy representative \
  --n 100 \
  --output configs/instances/phase3_100instances.txt \
  --ensure_baseline  # 4개 baseline 포함

# 2. Verify coverage
python scripts/verify_coverage.py \
  --instances configs/instances/phase3_100instances.txt \
  --reference data/swebench_lite_all.json

# 3. Infrastructure scaling
# 16 workers (optimal for 100 instances)
# Expected total time: 100 × 45 min / 16 ≈ 5 hours
```

**Days 13-17**: Execution (5 days buffer)
```bash
# Day 13: First batch (50 instances)
nohup ./run_phase3_batch1.sh > logs/nohup/phase3_batch1.log 2>&1 &

# Day 15: Second batch (50 instances)
nohup ./run_phase3_batch2.sh > logs/nohup/phase3_batch2.log 2>&1 &

# Monitor continuously
./monitor_phase3_test.sh

# Checkpointing every 10 instances
python scripts/checkpoint_results.py --interval 10
```

**Days 18-20**: Analysis
```bash
# Comprehensive statistical analysis
python scripts/analyze_100instance_results.py \
  --output PHASE3_FULL_RESULTS.md

# Distribution plots
python scripts/plot_distributions.py \
  --metrics Overall HFS TSS BRS OverfitGap \
  --output plots/phase3/

# Correlation analysis
python scripts/correlation_analysis.py \
  --features patch_size iterations test_count code_complexity \
  --target Overall

# Failure mode taxonomy
python scripts/categorize_failures.py \
  --threshold 0.5 \
  --output PHASE3_FAILURE_ANALYSIS.md
```

**Days 21-24**: Reporting and refinement
```bash
# Generate final report
python scripts/generate_comprehensive_report.py \
  --phases 1 2 3 \
  --output PHASE3_COMPREHENSIVE_REPORT.md

# Create visualizations
python scripts/create_visualizations.py \
  --type heatmap boxplot violin scatter \
  --output plots/phase3/

# Identify improvement opportunities
python scripts/identify_improvements.py \
  --focus low_performers overfit_cases \
  --output PHASE3_IMPROVEMENT_PLAN.md
```

---

## Phase 4: 300-Instance Complete Coverage (Days 25-55)

### Objectives
- **Complete SWE-bench Lite**: All 300 instances
- **Production validation**: Real-world performance characterization
- **Benchmark establishment**: Definitive baseline for future work
- **Publication readiness**: Comprehensive evaluation for paper

### Instance Selection

**All 300 SWE-bench Lite instances** (complete coverage)

```python
# Repository breakdown (estimated):
repositories = {
    'django': 114,
    'scikit-learn': 45,
    'matplotlib': 40,
    'pytest': 28,
    'sympy': 23,
    'astropy': 15,
    'requests': 10,
    'flask': 7,
    'pandas': 6,
    'sphinx': 6,
    'others': 6,
}

# Difficulty distribution (estimated from literature):
difficulty = {
    'easy': 30,          # ~10%
    'medium': 90,        # ~30%
    'hard': 120,         # ~40%
    'very_hard': 60,     # ~20%
}
```

### Expected Metrics Distribution

**Phase 4 Predictions (300 instances)**:

| Metric | Min | Q1 | Median | Q3 | Max | Mean | Std | CV | IQR |
|--------|-----|----|--------|----|----|------|-----|-----|-----|
| Overall | 0.00 | 0.50 | 0.65 | 0.78 | 0.99 | 0.62 | 0.25 | 0.40 | 0.28 |
| BRS | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.75 | 0.42 | 0.56 | 0.00 |
| HFS | 0.00 | 0.30 | 0.58 | 0.80 | 1.00 | 0.56 | 0.32 | 0.57 | 0.50 |
| TSS | 0.00 | 0.40 | 0.63 | 0.83 | 1.00 | 0.58 | 0.34 | 0.59 | 0.43 |
| Overfit Gap | -0.20 | 0.00 | 0.05 | 0.14 | 0.40 | 0.08 | 0.13 | 1.63 | 0.14 |
| Patch Size | 100B | 550B | 1.0KB | 2.1KB | 12KB | 1.6KB | 1.5KB | 0.94 | 1.6KB |
| Iterations | 1 | 2 | 3 | 5 | 8 | 3.8 | 2.2 | 0.58 | 3 |
| Time (min) | 3 | 22 | 40 | 72 | 150 | 52 | 32 | 0.62 | 50 |
| Cost ($) | 0.5 | 2.5 | 4.2 | 6.8 | 15.0 | 5.1 | 3.2 | 0.63 | 4.3 |

### Detailed Distribution Analysis (300 instances)

```
Overall Score Distribution (300 instances 예상):
  [0.0-0.1):  ████████░░░░░░░░░░░░  18 instances (6%)   <- Complete failure
  [0.1-0.2):  ████████░░░░░░░░░░░░  18 instances (6%)   <- Critical issues
  [0.2-0.3):  ██████████░░░░░░░░░░  24 instances (8%)   <- Major problems
  [0.3-0.4):  ████████████░░░░░░░░  30 instances (10%)  <- Moderate issues
  [0.4-0.5):  ██████████████░░░░░░  36 instances (12%)  <- Below average
  [0.5-0.6):  ████████████████░░░░  42 instances (14%)  <- Average
  [0.6-0.7):  ████████████████░░░░  48 instances (16%)  <- Good
  [0.7-0.8):  ██████████████░░░░░░  39 instances (13%)  <- Very good
  [0.8-0.9):  ██████████░░░░░░░░░░  27 instances (9%)   <- Excellent
  [0.9-1.0]:  ████████░░░░░░░░░░░░  18 instances (6%)   <- Perfect

Performance Categories:
  Failed (Overall < 0.3):     60 instances (20%)  <- Need improvement
  Partial (0.3 ≤ Overall < 0.6): 108 instances (36%)  <- Moderate success
  Good (0.6 ≤ Overall < 0.8):  87 instances (29%)  <- Strong performance
  Excellent (Overall ≥ 0.8):  45 instances (15%)  <- Outstanding

BRS Distribution (300 instances 예상):
  BRS = 0:  ███████░░░░░░░░░░░░░  75 instances (25%)  <- 버그 재현 실패
  BRS = 1:  █████████████████████ 225 instances (75%)  <- 성공

  Bug Reproduction Failure Analysis (75 instances):
    - Complex multi-step bugs: 25 (33%)
    - Insufficient context: 20 (27%)
    - Ambiguous requirements: 15 (20%)
    - Test generation limits: 15 (20%)

HFS Distribution (300 instances 예상):
  HFS = 0.0:       ████████████░░░░░░░░  48 instances (16%)  <- No fix
  (0.0-0.25):      ██████████░░░░░░░░░░  36 instances (12%)  <- Poor fix
  [0.25-0.50):     ████████████░░░░░░░░  48 instances (16%)  <- Partial fix
  [0.50-0.75):     ██████████████░░░░░░  72 instances (24%)  <- Good fix
  [0.75-1.0):      ████████████░░░░░░░░  54 instances (18%)  <- Excellent fix
  HFS = 1.0:       ████████░░░░░░░░░░░░  42 instances (14%)  <- Perfect fix

TSS Distribution (300 instances 예상):
  TSS = 0.0:       ████████████░░░░░░░░  60 instances (20%)  <- No test
  (0.0-0.33):      ████████░░░░░░░░░░░░  42 instances (14%)  <- Weak test
  [0.33-0.67):     ██████████████░░░░░░  72 instances (24%)  <- Moderate test
  [0.67-1.0):      ████████████░░░░░░░░  66 instances (22%)  <- Strong test
  TSS = 1.0:       ████████████░░░░░░░░  60 instances (20%)  <- Perfect test

Overfit Gap Distribution (300 instances 예상):
  Gap < -0.10:     ████░░░░░░░░░░░░░░░░  15 instances (5%)   <- 과소적합 (Hidden > Public)
  [-0.10-0.00):    ██████░░░░░░░░░░░░░░  30 instances (10%)  <- Slight underfit
  [0.00-0.05):     ████████████████████  90 instances (30%)  <- Excellent (no overfit)
  [0.05-0.10):     ██████████████░░░░░░  75 instances (25%)  <- Good (minimal overfit)
  [0.10-0.15):     ████████░░░░░░░░░░░░  45 instances (15%)  <- Acceptable
  [0.15-0.20):     ████░░░░░░░░░░░░░░░░  27 instances (9%)   <- Warning
  Gap ≥ 0.20:      ██░░░░░░░░░░░░░░░░░░  18 instances (6%)   <- Critical overfit

Overfit Risk Assessment:
  Excellent (Gap < 0.05):    120 instances (40%)  <- No concern
  Good (0.05 ≤ Gap < 0.10):   75 instances (25%)  <- Monitor
  Acceptable (0.10 ≤ Gap < 0.15): 45 instances (15%)  <- Watch closely
  Concerning (Gap ≥ 0.15):    60 instances (20%)  <- Needs investigation
```

### Repository-Specific Performance (예상)

```
Mean Overall by Repository (Top 10):
  django (n=114):          0.58 ± 0.24  ████████████░░░░░░░░
  scikit-learn (n=45):     0.65 ± 0.22  ██████████████░░░░░░
  matplotlib (n=40):       0.62 ± 0.26  █████████████░░░░░░░
  pytest (n=28):           0.68 ± 0.20  ███████████████░░░░░
  sympy (n=23):            0.70 ± 0.18  ████████████████░░░░
  astropy (n=15):          0.72 ± 0.19  █████████████████░░░
  requests (n=10):         0.55 ± 0.28  ███████████░░░░░░░░░
  flask (n=7):             0.60 ± 0.25  ████████████░░░░░░░░
  pandas (n=6):            0.52 ± 0.30  ██████████░░░░░░░░░░
  sphinx (n=6):            0.58 ± 0.27  ████████████░░░░░░░░

Insights:
  - Astropy/Sympy: Better performance (scientific computing, well-structured)
  - Django: Lower performance (complex web framework, many edge cases)
  - Pandas: Challenging (complex data structures, type handling)
```

### Difficulty-Stratified Analysis (예상)

```
Mean Overall by Difficulty Tier:
  Easy (n=30):       0.85 ± 0.12  █████████████████████
  Medium (n=90):     0.72 ± 0.15  ████████████████░░░░░
  Hard (n=120):      0.58 ± 0.22  ████████████░░░░░░░░░
  Very Hard (n=60):  0.38 ± 0.25  ████████░░░░░░░░░░░░░

BRS by Difficulty:
  Easy:       90% (27/30)   ████████████████████░
  Medium:     82% (74/90)   █████████████████░░░░
  Hard:       72% (86/120)  ███████████████░░░░░░
  Very Hard:  63% (38/60)   █████████████░░░░░░░░

Overfit Gap by Difficulty:
  Easy:       0.02 ± 0.04  (minimal overfitting)
  Medium:     0.05 ± 0.08  (controlled)
  Hard:       0.09 ± 0.12  (moderate risk)
  Very Hard:  0.15 ± 0.18  (higher risk, but acceptable)
```

### Success Criteria

**Primary Metrics** (Conservative targets):
- ✅ **Mean Overall ≥ 0.60** (Target: 0.62)
- ✅ **Median Overall ≥ 0.65** (Robust performance)
- ✅ **BRS ≥ 70%** (At least 210 instances)
- ✅ **Mean HFS ≥ 0.55** (Actual bug fixing)
- ✅ **Mean Overfit Gap ≤ 0.10** (Controlled overfitting)

**Distribution Requirements**:
- ✅ **% Overall ≥ 0.8**: ≥ 12% (at least 36 excellent instances)
- ✅ **% Overall < 0.3**: ≤ 25% (at most 75 failed instances)
- ✅ **% Gap > 0.15**: ≤ 20% (60 instances with overfit concern)
- ✅ **% Gap < 0.05**: ≥ 35% (105 instances with no overfit)

**Statistical Robustness**:
- ✅ **95% CI for mean Overall**: Width < 0.05 (narrow CI with n=300)
- ✅ **Consistency across repositories**: No repo with mean < 0.40
- ✅ **Consistency across difficulty**: Clear stratification observable
- ✅ **Correlation analysis**: Identify key success factors

**Operational Excellence**:
- ✅ **Mean time per instance**: ≤ 55 minutes
- ✅ **Mean cost per instance**: ≤ $5.50
- ✅ **Total cost**: ≤ $1,650
- ✅ **Infrastructure reliability**: ≥ 99.5% (≤ 2 crashes)
- ✅ **Zero regression** on all 100 Phase 3 instances

### Execution Plan

**Days 25-27**: Preparation
```bash
# 1. Get all 300 instances
python scripts/get_all_swebench_lite.py \
  --output configs/instances/phase4_300instances.txt

# 2. Verify completeness
python scripts/verify_completeness.py \
  --instances configs/instances/phase4_300instances.txt

# 3. Infrastructure scaling
# 32 workers (maximum parallelism)
# Expected time: 300 × 45 min / 32 ≈ 7 hours

# 4. Cost estimation
python scripts/estimate_cost.py \
  --instances 300 \
  --model gpt-4o \
  --avg_iterations 3.8
```

**Days 28-42**: Execution (15 days, 20 instances/day)
```bash
# Batch strategy: 6 batches × 50 instances
# 2.5 days per batch × 6 = 15 days

# Batch 1: Days 28-30 (instances 1-50)
nohup ./run_phase4_batch1.sh > logs/nohup/phase4_batch1.log 2>&1 &

# Batch 2: Days 31-33 (instances 51-100)
nohup ./run_phase4_batch2.sh > logs/nohup/phase4_batch2.log 2>&1 &

# ... (similar for batches 3-6)

# Continuous monitoring
./monitor_phase4_test.sh

# Hourly checkpointing
cron: 0 * * * * python scripts/checkpoint_phase4.py

# Daily interim reports
cron: 0 0 * * * python scripts/daily_report.py
```

**Days 43-50**: Comprehensive Analysis
```bash
# Statistical analysis
python scripts/analyze_300instance_results.py \
  --output PHASE4_COMPLETE_RESULTS.md

# Distribution analysis
python scripts/distribution_analysis.py \
  --metrics Overall HFS TSS BRS OverfitGap \
  --stratify repository difficulty bug_type \
  --output plots/phase4/distributions/

# Correlation and feature importance
python scripts/feature_analysis.py \
  --features patch_size iterations test_count code_complexity \
    repository difficulty bug_category num_files \
  --target Overall \
  --methods pearson spearman random_forest \
  --output PHASE4_FEATURE_ANALYSIS.md

# Failure taxonomy
python scripts/failure_taxonomy.py \
  --threshold 0.5 \
  --categories bug_type error_type failure_stage \
  --output PHASE4_FAILURE_TAXONOMY.md

# Success pattern analysis
python scripts/success_patterns.py \
  --threshold 0.8 \
  --output PHASE4_SUCCESS_PATTERNS.md

# Overfit deep dive
python scripts/overfit_analysis.py \
  --threshold 0.15 \
  --output PHASE4_OVERFIT_ANALYSIS.md
```

**Days 51-55**: Final Reporting
```bash
# Comprehensive final report
python scripts/generate_final_report.py \
  --phases 1 2 3 4 \
  --output PHASE4_FINAL_COMPREHENSIVE_REPORT.md

# Publication-ready visualizations
python scripts/create_publication_plots.py \
  --types distribution boxplot violin heatmap scatter \
  --quality publication \
  --output plots/publication/

# Comparison with baselines
python scripts/compare_with_baselines.py \
  --baselines swe-agent auto-code-rover \
  --output BASELINE_COMPARISON.md

# Executive summary
python scripts/executive_summary.py \
  --output EXECUTIVE_SUMMARY_300.md
```

---

## Key Metrics Summary (All Phases)

### Expected Performance Progression

| Phase | n | Overall | BRS | HFS | TSS | Overfit Gap | Time | Cost |
|-------|---|---------|-----|-----|-----|-------------|------|------|
| Baseline | 4 | 0.944 | 100% | 100% | 0.875 | 0.00 | - | - |
| Phase 1 | 10 | 0.78 | 85% | 72% | 0.68 | 0.05 | 6h | $50 |
| Phase 2 | 50 | 0.70 | 82% | 65% | 0.63 | 0.06 | 30h | $250 |
| Phase 3 | 100 | 0.68 | 80% | 62% | 0.61 | 0.07 | 80h | $500 |
| Phase 4 | 300 | 0.62 | 75% | 56% | 0.58 | 0.08 | 260h | $1,650 |

### Critical Insights

**Performance Degradation** (expected):
```
Baseline → Phase 4:
  Overall:     0.944 → 0.62  (-34% relative, expected)
  BRS:         100% → 75%     (-25%, natural difficulty increase)
  Overfit Gap: 0.00 → 0.08    (+0.08, still controlled)

Reasons:
  1. Baseline 선택 편향 (easy instances)
  2. Scale-up에서 난이도 다양성 증가
  3. 복잡한 버그 비율 증가
  4. Multi-file, cross-module 버그 증가
```

**Overfit Control** (maintained):
```
All Phases: Overfit Gap < 0.10 (Target achieved)
  - Public/Hidden split 전략 효과적
  - Test-aware iteration 작동
  - No systematic overfitting
```

**Cost Efficiency**:
```
Phase 4: $1,650 / 300 = $5.50 per instance
  - Acceptable for research
  - Optimization 가능 (model selection, caching)
```

---

## Infrastructure Requirements

### Computational Resources

**Phase 1 (10 instances)**:
- Workers: 4
- Memory: 32GB
- Storage: 50GB
- GPU: Not required

**Phase 2 (50 instances)**:
- Workers: 8
- Memory: 64GB
- Storage: 100GB
- GPU: Not required

**Phase 3 (100 instances)**:
- Workers: 16
- Memory: 128GB
- Storage: 200GB
- GPU: Optional (for faster LLM inference)

**Phase 4 (300 instances)**:
- Workers: 32
- Memory: 256GB
- Storage: 500GB
- GPU: Recommended (A100 or equivalent)
- Network: High bandwidth for LLM API calls

### Docker and Environment

```yaml
# docker-compose.yml
version: '3.8'
services:
  swebench-runner:
    image: swebench-runner:latest
    deploy:
      replicas: 32  # Phase 4
    resources:
      limits:
        cpus: '2'
        memory: 8G
    volumes:
      - ./data:/data
      - ./outputs:/outputs
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - USE_EDIT_SCRIPT=1
```

### Monitoring and Logging

```bash
# Real-time monitoring dashboard
./monitor_dashboard.sh

# Metrics:
# - Completed instances
# - Success rate (Overall > 0.5)
# - Average metrics
# - Cost accumulation
# - ETA
# - Error rate

# Logging:
# - Per-instance logs: logs/instances/{instance_id}/
# - Aggregate logs: logs/aggregate/
# - Error logs: logs/errors/
# - Cost logs: logs/costs/
```

---

## Risk Mitigation

### Risk 1: Infrastructure Failures

**Mitigation**:
- Checkpointing every 10 instances
- Graceful restart mechanism
- Docker container isolation
- Resource monitoring and auto-scaling

### Risk 2: Cost Overruns

**Mitigation**:
- Cost estimation before each phase
- Real-time cost tracking
- Budget alerts (80%, 90%, 100%)
- Model downgrade option (gpt-4o → gpt-4o-mini)

### Risk 3: Performance Regression

**Mitigation**:
- Continuous baseline validation
- Statistical process control (SPC) charts
- Automated regression detection
- Rollback mechanism

### Risk 4: Overfit Emergence

**Mitigation**:
- Per-instance overfit gap monitoring
- Threshold alerts (Gap > 0.15)
- Root cause analysis for high-gap instances
- Strategy adjustment if systematic overfitting detected

---

## Timeline Summary

```
Day 1-3:    Phase 1 (10 instances)    ████░░░░░░░░░░░░░░░░
Day 4-10:   Phase 2 (50 instances)    ███████░░░░░░░░░░░░░
Day 11-24:  Phase 3 (100 instances)   ██████████████░░░░░░
Day 25-55:  Phase 4 (300 instances)   ████████████████████

Total: ~8 weeks (55 days)
```

---

## Deliverables

### Phase 1 Deliverables
- [ ] PHASE1_RESULTS.md
- [ ] plots/phase1/distributions.png
- [ ] Lessons learned document

### Phase 2 Deliverables
- [ ] PHASE2_RESULTS.md
- [ ] PHASE2_FAILURE_ANALYSIS.md
- [ ] plots/phase2/comprehensive/

### Phase 3 Deliverables
- [ ] PHASE3_FULL_RESULTS.md
- [ ] PHASE3_STATISTICAL_ANALYSIS.md
- [ ] PHASE3_IMPROVEMENT_PLAN.md
- [ ] plots/phase3/publication_quality/

### Phase 4 Deliverables
- [ ] PHASE4_COMPLETE_RESULTS.md
- [ ] PHASE4_FAILURE_TAXONOMY.md
- [ ] PHASE4_SUCCESS_PATTERNS.md
- [ ] PHASE4_OVERFIT_ANALYSIS.md
- [ ] BASELINE_COMPARISON.md
- [ ] EXECUTIVE_SUMMARY_300.md
- [ ] plots/publication/ (all figures)
- [ ] Paper draft (optional)

---

## Success Definition

### Quantitative Success
- ✅ Mean Overall ≥ 0.60 at 300-instance scale
- ✅ BRS ≥ 70% (at least 210/300 instances)
- ✅ Mean Overfit Gap ≤ 0.10 (controlled overfitting)
- ✅ Statistical significance (p < 0.05)
- ✅ Cost ≤ $6 per instance

### Qualitative Success
- ✅ Clear understanding of failure modes
- ✅ Reproducible evaluation framework
- ✅ Scalable infrastructure
- ✅ Publication-ready analysis
- ✅ Actionable improvement insights

### Comparison Success
- ✅ Competitive with or better than existing SWE-bench baselines
- ✅ Novel contributions clearly demonstrated
- ✅ Overfitting control superior to baselines

---

## Next Steps

### Immediate (Week 1)
1. Review and approve this plan
2. Setup infrastructure for Phase 1
3. Create monitoring scripts
4. Prepare instance selection scripts

### Short-term (Weeks 2-4)
1. Execute Phase 1 and 2
2. Analyze initial results
3. Refine strategies based on learnings
4. Prepare for Phase 3

### Medium-term (Weeks 5-8)
1. Execute Phase 3 and 4
2. Comprehensive analysis
3. Publication preparation
4. Future work planning

---

**Plan Owner**: Claude Code
**Review Date**: 2025-12-30
**Next Review**: After Phase 1 completion
**Status**: Ready for Approval
