# Phase 2: Plan-then-Diff 2-Stage Architecture

**Branch**: `phase2-plan-then-diff`
**Base Version**: v0.9.1-phase1-verified (ba7fcb3)
**Status**: 🚧 Design Phase
**Rollback Point**: `git checkout main` or `git checkout v0.9.1-phase1-verified`

---

## Executive Summary

Phase 2 implements a **2-stage LLM architecture** that separates:
- **Stage A (Planner)**: High-level planning (what/where/how to fix) → JSON output
- **Stage B (Diff Writer)**: Precise diff rendering (JSON → unified diff) → stable format

**Goal**: Improve astropy-14182 TSS from 0.5 to 0.75+ while maintaining other instances' perfect scores.

**Strategy**: Failure mode separation (semantic vs format) enables targeted retry.

---

## Problem Statement

### Current P0.9.1 Phase 1 Limitation

**astropy-14182 Performance**:
- BRS: 1.0 ✅ (bug reproduction works)
- HFS: 1.0 ✅ (hidden tests pass)
- TSS: 0.5 ⚠️ (public_pass_rate = 0.0)
- Overall: 0.825

**Root Cause**:
- Single-stage LLM mixes "creative planning" with "precise diff formatting"
- LLM generates different malformed patterns each iteration
- Pattern-based cleaning (P0.9.1 Phase 2 attempt) failed → regression

**Phase 2 Failed Approach** (rolled back):
- Post-processing malformed patch cleaning
- Too aggressive → removed valid code
- Result: 0.825 → 0.225 (severe regression)

---

## Phase 2 Solution: Plan-then-Diff

### Core Insight

**Separate concerns by LLM role**:

| Concern | Current (1-stage) | Phase 2 (2-stage) |
|---------|-------------------|-------------------|
| **What to fix** | Single LLM call | Stage A: Planner |
| **How to format** | Same LLM call | Stage B: Diff Writer |
| **Retry on format error** | Full regeneration | Writer only (cheaper) |
| **Retry on logic error** | Full regeneration | Planner only (targeted) |

**Key Benefit**: When LLM makes formatting mistake (malformed diff), we only retry the "rendering" stage, keeping the "thinking" stage results.

---

## Architecture Design

### Stage A: Planner

**Model**: gpt-4o (creative, high-quality planning)
**Input**:
- problem_statement
- reference_patch (if research mode)
- reference_test_patch (if research mode)
- failure_summary
- repo_context

**Output**: JSON plan (strict schema)
```json
{
  "task_type": "test" | "code" | "both",
  "files": [
    {
      "path": "astropy/modeling/separable.py",
      "edit_type": "modify",
      "target_symbol": "_cstack",
      "change_summary": "Replace constant with right matrix",
      "reference_alignment": {
        "hunk_start": 242,
        "old_lines": 7,
        "new_lines": 7,
        "key_changes": ["Remove constant", "Add right multiplication"]
      }
    }
  ],
  "test_strategy": {
    "approach": "dictionary_append",
    "expected_values": ["cm_4d_expected"],
    "io_policy": "use_tmp_path_only"
  },
  "constraints": {
    "no_file_io": true,
    "no_network": true,
    "follow_reference_exactly": true
  }
}
```

**Forbidden**:
- Diff output
- Code blocks
- Markdown formatting
- Explanatory text

---

### Stage B: Diff Writer

**Model**: gpt-4o-mini (precise, stable formatting)
**Input**:
- Plan JSON from Stage A
- Minimal source context (only relevant functions/lines)
- Reference patch hints (optional, for line number accuracy)

**Output**: Unified diff only
```diff
diff --git a/astropy/modeling/separable.py b/astropy/modeling/separable.py
--- a/astropy/modeling/separable.py
+++ b/astropy/modeling/separable.py
@@ -242,7 +242,7 @@ def _cstack(left, right):
     # ... context lines ...
-    constant = 1
+    result = right @ matrix
     # ... context lines ...
```

**Forbidden**:
- JSON output
- Explanatory text
- Multiple diff formats
- Policy violations (enforced by prompt)

---

### Gate: Validation & Retry Controller

**Validation Pipeline**:
1. **JSON Schema Validation** (Stage A output)
2. **Diff Structure Validation** (Stage B output)
3. **Policy Validation** (file I/O, network, skip/xfail)
4. **Reference Alignment Check** (research mode)
5. **Dry-run Patch Apply**

**Retry Logic**:

```python
# Error Classification
ERROR_TYPES = {
    "MALFORMED_DIFF": "B",      # Stage B retry
    "POLICY_VIOLATION": "B",    # Stage B retry
    "HUNK_MISMATCH": "B",       # Stage B retry
    "WRONG_FILE": "A",          # Stage A retry
    "WRONG_LOGIC": "A",         # Stage A retry
    "PLAN_INCOMPLETE": "A",     # Stage A retry
}

# Retry Strategy
if error_type in ["MALFORMED_DIFF", "POLICY_VIOLATION", "HUNK_MISMATCH"]:
    # Retry Stage B only (keep Plan)
    for attempt in range(MAX_WRITER_RETRIES):
        diff = stage_b_render(plan, corrective_feedback)
        if validate(diff): break
else:
    # Retry Stage A (replan)
    plan = stage_a_replan(updated_context)
    diff = stage_b_render(plan)
```

---

## Implementation Plan

### Phase 2.1: Scaffolding (Week 1) - No Performance Change

**Goal**: Add 2-stage infrastructure with feature flag, maintain current performance.

**Tasks**:
- [ ] Create `bench_agent/agent/planner.py`
  - `generate_plan(role, context) -> dict`
  - JSON schema validation
- [ ] Create `bench_agent/agent/diff_writer.py`
  - `render_diff(role, plan, context) -> str`
  - Plan-to-diff conversion
- [ ] Create `bench_agent/protocol/two_stage.py`
  - `generate_patch_two_stage(...)` wrapper
  - Combines planner + writer
- [ ] Add feature flag to `run_mvp.py`
  - `USE_TWO_STAGE = os.getenv("USE_TWO_STAGE", "0") == "1"`
  - Default: OFF (use current 1-stage)
- [ ] Write unit tests
  - Test JSON schema validation
  - Test plan-to-diff conversion

**Success Criteria**:
- Regression test with `USE_TWO_STAGE=0`: All 4 instances maintain scores
- Code review: Clean separation of concerns

---

### Phase 2.2: Gate-Aware Retry (Week 2) - Performance Improvement

**Goal**: Implement smart retry logic, target astropy-14182 improvement.

**Tasks**:
- [ ] Standardize error types in `bench_agent/protocol/diff_validator.py`
  - Return `ErrorType` enum instead of string messages
- [ ] Implement retry router in `two_stage.py`
  - Error → A/B routing table
  - Retry counters (A: 1 retry, B: 2 retries)
- [ ] Add failure logging
  - Track "Stage A failure" vs "Stage B failure"
  - Log for ablation study
- [ ] Enable `USE_TWO_STAGE=1` for testing
  - Test on astropy-14182 only (focused test)
  - Run 10 iterations to measure stability

**Success Criteria**:
- astropy-14182 TSS improves from 0.5 to 0.65+ (intermediate goal)
- No regression on other 3 instances
- Retry logic reduces full regenerations by 30%+

---

### Phase 2.3: Optimization & Tuning (Week 3) - Production Ready

**Goal**: Optimize for best performance, full regression test.

**Tasks**:
- [ ] Tune prompt templates
  - Minimize Planner verbosity
  - Enforce Diff Writer strictness
- [ ] Add conditional sanitizers (code-based, not prompt)
  - astropy-14182 specific: test diff table separator cleanup
  - Triggered only when needed (if-else in Gate)
- [ ] Full regression test
  - Run with `USE_TWO_STAGE=1` on all 4 instances
  - 5 runs per instance to measure variance
- [ ] Performance comparison
  - P0.9.1 Phase 1 (baseline)
  - + 2-stage only
  - + 2-stage + smart retry
  - + 2-stage + smart retry + sanitizers

**Success Criteria**:
- Average Overall ≥ 0.96 (target: +1% from 0.95)
- astropy-14182 TSS ≥ 0.75
- BRS maintains 100%
- No regression on perfect scores

---

## Technical Specifications

### File Structure

```
bench_agent/
├── agent/
│   ├── planner.py              # NEW: Stage A
│   ├── diff_writer.py          # NEW: Stage B
│   ├── llm_client.py           # (existing)
│   ├── test_author.py          # (modify to use 2-stage)
│   └── patch_author.py         # (modify to use 2-stage)
├── protocol/
│   ├── two_stage.py            # NEW: Wrapper & retry logic
│   ├── plan_schema.py          # NEW: JSON schema definition
│   ├── error_types.py          # NEW: Error classification
│   ├── diff_validator.py       # (modify: return ErrorType)
│   └── policy.py               # (existing)
└── runner/
    └── ...                      # (no changes)

scripts/
└── run_mvp.py                   # (modify: add USE_TWO_STAGE flag)

tests/
├── test_planner.py              # NEW: Unit tests
├── test_diff_writer.py          # NEW: Unit tests
└── test_two_stage.py            # NEW: Integration tests
```

---

### JSON Schema (Planner Output)

```python
# bench_agent/protocol/plan_schema.py

PLAN_SCHEMA = {
    "type": "object",
    "required": ["task_type", "files"],
    "properties": {
        "task_type": {
            "type": "string",
            "enum": ["test", "code", "both"]
        },
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "edit_type", "target_symbol"],
                "properties": {
                    "path": {"type": "string"},
                    "edit_type": {"type": "string", "enum": ["modify", "create", "delete"]},
                    "target_symbol": {"type": "string"},
                    "change_summary": {"type": "string"},
                    "reference_alignment": {
                        "type": "object",
                        "properties": {
                            "hunk_start": {"type": "integer"},
                            "old_lines": {"type": "integer"},
                            "new_lines": {"type": "integer"},
                            "key_changes": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            }
        },
        "test_strategy": {
            "type": "object",
            "properties": {
                "approach": {"type": "string", "enum": ["dictionary_append", "new_function", "parametrize_extend"]},
                "expected_values": {"type": "array", "items": {"type": "string"}},
                "io_policy": {"type": "string", "enum": ["use_tmp_path_only", "no_io"]}
            }
        },
        "constraints": {
            "type": "object",
            "properties": {
                "no_file_io": {"type": "boolean"},
                "no_network": {"type": "boolean"},
                "follow_reference_exactly": {"type": "boolean"}
            }
        }
    }
}
```

---

### Error Type Enum

```python
# bench_agent/protocol/error_types.py

from enum import Enum

class ErrorType(Enum):
    # Stage B errors (retry Writer only)
    MALFORMED_DIFF = "malformed_diff"
    POLICY_VIOLATION = "policy_violation"
    HUNK_MISMATCH = "hunk_mismatch"
    LINE_MISMATCH = "line_mismatch"

    # Stage A errors (retry Planner)
    WRONG_FILE = "wrong_file"
    WRONG_LOGIC = "wrong_logic"
    PLAN_INCOMPLETE = "plan_incomplete"
    MISSING_REFERENCE_ALIGNMENT = "missing_reference_alignment"

    # Both stages need retry
    UNKNOWN_ERROR = "unknown_error"

def should_retry_writer(error_type: ErrorType) -> bool:
    """Determine if error should trigger Writer-only retry."""
    return error_type in [
        ErrorType.MALFORMED_DIFF,
        ErrorType.POLICY_VIOLATION,
        ErrorType.HUNK_MISMATCH,
        ErrorType.LINE_MISMATCH,
    ]

def should_retry_planner(error_type: ErrorType) -> bool:
    """Determine if error should trigger Planner retry."""
    return error_type in [
        ErrorType.WRONG_FILE,
        ErrorType.WRONG_LOGIC,
        ErrorType.PLAN_INCOMPLETE,
        ErrorType.MISSING_REFERENCE_ALIGNMENT,
    ]
```

---

## Risk Mitigation

### Risk 1: JSON Bloat (Planner over-explains)

**Mitigation**:
- Strict schema validation (reject extra fields)
- Token limit on Planner response
- Example-driven prompts (show minimal valid JSON)

### Risk 2: Plan-Diff Mismatch (Writer ignores Plan)

**Mitigation**:
- Gate validates plan.files[] vs diff files
- Gate validates plan.target_symbol appears in diff hunks
- Immediate reject + Writer retry if mismatch

### Risk 3: Regression on Perfect Instances

**Mitigation**:
- Feature flag OFF by default
- Incremental testing (14182 first, then full regression)
- Automated rollback if BRS drops below 100%

### Risk 4: Cost Increase (2 LLM calls per iteration)

**Mitigation**:
- Writer uses gpt-4o-mini (10x cheaper)
- Smart retry saves cost vs full regeneration
- Expected cost neutral or lower due to retry efficiency

---

## Success Metrics

### Primary Goals
- [ ] astropy-14182 TSS: 0.5 → 0.75+ (50% improvement)
- [ ] Average Overall: 0.950 → 0.960+ (1% improvement)
- [ ] BRS: Maintain 100% (4/4)

### Secondary Goals
- [ ] Retry efficiency: Reduce full regenerations by 30%+
- [ ] Iteration count: Reduce average from 3 to 2.5
- [ ] No regression: Other 3 instances maintain ≥0.987

### Ablation Study (for paper)
- [ ] Baseline (P0.9.1 Phase 1)
- [ ] + 2-stage architecture
- [ ] + Smart retry
- [ ] + Instance-specific sanitizers
- [ ] Measure contribution of each component

---

## Rollback Plan

If Phase 2 causes regressions:

```bash
# Quick rollback to verified version
git checkout main
# or
git checkout v0.9.1-phase1-verified

# Test verified version
PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
  ~/anaconda3/envs/testing/bin/python scripts/run_mvp.py \
  --config configs/p091_regression_test.yaml \
  --run-id rollback-verify-$(date +%Y%m%d-%H%M%S)
```

See [ROLLBACK_INSTRUCTIONS.md](ROLLBACK_INSTRUCTIONS.md) for details.

---

## Timeline

| Week | Phase | Deliverable | Success Gate |
|------|-------|-------------|--------------|
| 1 | 2.1 Scaffolding | 2-stage infrastructure | No regression with flag OFF |
| 2 | 2.2 Smart Retry | Error routing + retry | 14182 TSS ≥ 0.65 |
| 3 | 2.3 Optimization | Full regression test | Overall ≥ 0.96, BRS 100% |

---

## Next Steps

1. **Immediate**: Start Phase 2.1 implementation
   - Create `planner.py` with JSON schema
   - Create `diff_writer.py` with plan parsing
   - Add feature flag to `run_mvp.py`

2. **This Week**: Complete scaffolding
   - Unit tests for planner/writer
   - Integration test with flag OFF (equivalence check)

3. **Next Week**: Enable smart retry
   - Test on astropy-14182
   - Measure improvement

---

**Branch**: `phase2-plan-then-diff`
**Base**: v0.9.1-phase1-verified (ba7fcb3)
**Safe Rollback**: `git checkout main`
**Status**: 🚧 Design Complete - Ready for Implementation
