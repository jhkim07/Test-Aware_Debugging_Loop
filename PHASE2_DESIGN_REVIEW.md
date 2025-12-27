# Phase 2 Design Review & Analysis

**Date**: 2025-12-27
**Reviewer**: Design Review Session
**Status**: Critical Analysis Before Implementation

---

## 1. Overall Architecture Assessment

### ✅ Strengths

**A. Clear Separation of Concerns**
- Planner (semantic) vs Writer (syntactic) separation is sound
- Matches observed failure modes: astropy-14182 shows format issues, not logic issues
- Allows targeted retry → cost efficiency

**B. Incremental Rollout Strategy**
- Feature flag approach is safe (default OFF)
- Phase 2.1 → 2.2 → 2.3 progression minimizes risk
- Each phase has clear success criteria

**C. Well-Defined Rollback**
- v0.9.1-phase1-verified tag provides safe fallback
- Branch isolation prevents main contamination

---

## 2. Critical Design Questions

### 🤔 Question 1: JSON Schema Complexity

**Current Design**:
```json
{
  "task_type": "test",
  "files": [{
    "path": "...",
    "edit_type": "modify",
    "target_symbol": "_cstack",
    "change_summary": "...",
    "reference_alignment": {
      "hunk_start": 242,
      "old_lines": 7,
      "new_lines": 7,
      "key_changes": ["..."]
    }
  }],
  "test_strategy": {...},
  "constraints": {...}
}
```

**Concern**: Too detailed? Might trigger LLM verbosity.

**Analysis**:
- ✅ **Keep**: `task_type`, `files[].path`, `files[].target_symbol`
- ⚠️ **Reconsider**: `reference_alignment.key_changes` (might be redundant)
- ⚠️ **Reconsider**: `constraints` object (already in context, duplicative?)

**Recommendation**: Start with **minimal schema** in Phase 2.1, add fields only when needed.

**Minimal Schema v1**:
```json
{
  "files": [{
    "path": "astropy/modeling/separable.py",
    "function": "_cstack",
    "change": "Replace constant with right matrix"
  }],
  "test_approach": "dictionary_append"
}
```

---

### 🤔 Question 2: Stage B Input - How Much Context?

**Current Design**: "Minimal source context (only relevant functions/lines)"

**Problem**: What is "minimal"?
- Too little → Writer can't generate accurate diff
- Too much → Writer gets distracted, creative (defeats purpose)

**Proposed Specification**:

For **test diff**:
```python
context = {
    "plan": plan_json,
    "conftest_current": "...",  # If dictionary append
    "test_file_template": "...", # Expected structure
    "max_lines": 100
}
```

For **code diff**:
```python
context = {
    "plan": plan_json,
    "target_function_source": extract_function(plan.files[0].function),
    "surrounding_context_lines": 20,  # Before/after function
    "reference_hunk_hint": "line 242, 7→7 lines"  # From reference
}
```

**Recommendation**: Define **exact context extraction rules** before Phase 2.1.

---

### 🤔 Question 3: Error Classification Accuracy

**Current Design**: Gate classifies errors into A/B retry types.

**Concern**: What if classification is wrong?

Example:
```
Error: "Hunk #1 failed at line 242"

Could be:
- Stage B error: Wrong line numbers in hunk header → retry Writer
- Stage A error: Wrong function targeted → retry Planner
```

**Proposed Solution**: Multi-signal classification

```python
def classify_error(error_msg, plan, diff, reference_patch):
    signals = []

    # Signal 1: Error type keyword
    if "malformed" in error_msg.lower():
        signals.append("B")
    elif "hunk failed" in error_msg.lower():
        # Need deeper check
        if plan.files[0].path in diff:
            signals.append("B")  # Right file, wrong format
        else:
            signals.append("A")  # Wrong file

    # Signal 2: Plan-Diff consistency
    if plan.files[0].path not in diff:
        signals.append("A")  # Plan says X, diff has Y

    # Signal 3: Reference alignment
    if reference_patch:
        ref_files = extract_files(reference_patch)
        if plan.files[0].path not in ref_files:
            signals.append("A")  # Plan diverged from reference

    # Vote
    return "A" if signals.count("A") > signals.count("B") else "B"
```

**Recommendation**: Implement **conservative classification** (prefer "A" when uncertain).

---

### 🤔 Question 4: Model Selection - Is gpt-4o for Planner Necessary?

**Current Design**:
- Planner: gpt-4o (expensive, creative)
- Writer: gpt-4o-mini (cheap, stable)

**Question**: Can we use gpt-4o-mini for Planner too?

**Analysis**:

| Planner Task | Requires Creativity? | Mini Sufficient? |
|--------------|---------------------|------------------|
| Parse reference patch | No | ✅ Yes |
| Identify target file/function | No (it's in reference) | ✅ Yes |
| Extract key changes | Minimal | ⚠️ Maybe |
| Generate test strategy | Yes (for non-reference cases) | ❌ No |

**Research Mode** (reference available):
- Most planning is "copying reference structure" → **mini sufficient**

**Official Mode** (no reference):
- Requires creative problem-solving → **gpt-4o needed**

**Recommendation**:
```python
planner_model = "gpt-4o" if mode == "official" else "gpt-4o-mini"
```

**Cost Savings**: ~80% of test cases are research mode → 4x cost reduction on Planner.

---

### 🤔 Question 5: Integration Point with Existing Code

**Current Code Structure**:
```python
# run_mvp.py (line 296)
test_diff = propose_tests(client, model, repo_ctx, failure, ...)

# run_mvp.py (line 540)
code_diff = propose_patch(client, model, repo_ctx, failure, test_diff)
```

**Phase 2 Needs**:
```python
if USE_TWO_STAGE:
    plan = planner.generate_plan(...)
    test_diff = diff_writer.render_diff(plan, ...)
else:
    test_diff = propose_tests(...)  # Current 1-stage
```

**Problem**: Two separate call sites (test, code) → DRY violation?

**Proposed Refactoring**:

```python
# bench_agent/protocol/two_stage.py
def generate_diff_two_stage(
    role: str,  # "test" or "code"
    client,
    model_planner: str,
    model_writer: str,
    context: dict,
    mode: str = "research"
) -> str:
    """Unified 2-stage generation for both test and code diffs."""
    plan = planner.generate_plan(role, context, model_planner)
    diff = diff_writer.render_diff(role, plan, context, model_writer)
    return diff

# run_mvp.py
if USE_TWO_STAGE:
    test_diff = generate_diff_two_stage("test", client, ...)
    code_diff = generate_diff_two_stage("code", client, ...)
else:
    test_diff = propose_tests(...)
    code_diff = propose_patch(...)
```

**Recommendation**: Create **single unified wrapper** to avoid duplication.

---

## 3. Risk Re-Assessment

### Risk 1: Planner "Overthinks" Simple Cases

**Scenario**: For simple bugs, Planner generates overly complex plan.

**Example**:
- Bug: Typo `colum` → `column`
- Expected Plan: `{"path": "file.py", "change": "Fix typo"}`
- Actual Plan: 5-field nested JSON with unnecessary analysis

**Mitigation**:
- Add `complexity: "simple" | "complex"` hint in context
- If `complexity == "simple"`, use minimal schema
- Prompt: "For simple fixes, use minimal plan"

---

### Risk 2: Writer "Hallucinates" When Plan is Vague

**Scenario**: Plan says "Fix the bug" without specifics.

**Example**:
```json
{"change": "Fix the indexing issue"}
```
→ Writer has no concrete guidance, generates random diff

**Mitigation**:
- **Planner validation**: Reject plan if `change` field is too generic
- Require: Specific variable/line/operation mentioned
- Good: "Change `arr[i]` to `arr[i-1]` in line 42"
- Bad: "Fix indexing"

---

### Risk 3: Research Mode Over-Reliance on Reference

**Scenario**: Plan becomes "copy reference exactly" → no learning.

**Question**: If we're just copying reference, why use LLM at all?

**Counter-argument**: Reference patch ≠ test patch in many cases
- Reference shows fix location
- Test must be generated independently
- Alignment needed but not blind copying

**Recommendation**: Monitor "plan creativity" metric
- Track: How often plan deviates from reference
- If always 100% match → might be over-fitting

---

## 4. Alternative Designs Considered

### Alternative 1: Chain-of-Thought in Single Stage

**Idea**: Force LLM to output `<thought>...</thought>` before diff.

**Pros**:
- Simpler than 2-stage
- No JSON parsing overhead

**Cons**:
- Can't selectively retry "thought" vs "diff"
- LLM often ignores format instructions (our exact problem!)

**Verdict**: ❌ Doesn't solve core issue (format stability)

---

### Alternative 2: 3-Stage (Plan → Code → Diff)

**Idea**:
- Stage 1: Plan (JSON)
- Stage 2: Generate code change (Python)
- Stage 3: Convert to diff

**Pros**:
- Even more precise control

**Cons**:
- 3x LLM calls → high cost
- Code→Diff conversion can be deterministic (no LLM needed)

**Verdict**: ⚠️ Over-engineering for Phase 2, consider for Phase 3

---

### Alternative 3: Retrieval-Augmented Generation

**Idea**: Use vector DB of successful patches to guide generation.

**Pros**:
- Learn from past successes

**Cons**:
- Requires large dataset
- Out of scope for current phase

**Verdict**: 📝 Future work (Phase 4?)

---

## 5. Implementation Priority Re-Ordering

**Current Plan**:
1. Phase 2.1: Scaffolding
2. Phase 2.2: Smart Retry
3. Phase 2.3: Optimization

**Concern**: Phase 2.1 has no observable benefit (flag OFF).

**Alternative: Spike-First Approach**

**Week 1**: Proof-of-Concept (Spike)
- Hardcode 2-stage for **astropy-14182 only**
- Skip feature flag, skip test/code split
- Single script: `poc_two_stage.py`
- Goal: Validate core hypothesis (TSS 0.5 → 0.65+)

**Week 2**: Generalize (if spike succeeds)
- Refactor spike into proper architecture
- Add feature flag
- Extend to all 4 instances

**Week 3**: Optimization
- Same as current plan

**Pros**:
- Fail fast if 2-stage doesn't work
- Faster validation of core idea

**Cons**:
- Spike code might be thrown away

**Recommendation**: Discuss with team - **spike vs scaffolding** trade-off.

---

## 6. Metrics & Observability Gaps

**Current Design**: Track "Stage A failure" vs "Stage B failure"

**Missing Metrics**:

1. **Plan Quality**:
   - Plan-Reference alignment score
   - Plan verbosity (JSON token count)
   - Plan rejection rate (schema validation)

2. **Writer Efficiency**:
   - Writer retry rate
   - Writer-Plan divergence (how often diff doesn't match plan)

3. **Cost Analysis**:
   - Cost per iteration (Planner + Writer)
   - Cost savings from selective retry

4. **Iteration Patterns**:
   - How often does "B retry → B retry → A retry" happen?
   - Optimal retry limits (current: A=1, B=2)

**Recommendation**: Add **structured logging** in Phase 2.1.

```python
log_entry = {
    "instance_id": "astropy-14182",
    "iteration": 3,
    "stage": "planner",
    "plan_tokens": 245,
    "plan_alignment_score": 0.85,
    "plan_valid": True,
    "retry_reason": None
}
```

---

## 7. Prompt Engineering Considerations

**Current Design**: Relies on system prompts for Planner/Writer.

**Missing**: Prompt examples in design doc.

**Critical Prompts Needed**:

### Planner Prompt (Draft)
```
You are a code analysis assistant. Given a bug report and reference patch,
output a JSON plan (and ONLY JSON) specifying:
1. Which file to modify
2. Which function/class to target
3. What change to make (in one sentence)

Schema: {...}

Example Input:
Problem: Function _cstack returns wrong matrix
Reference: Changes line 242 in separable.py

Example Output:
{
  "files": [{
    "path": "astropy/modeling/separable.py",
    "function": "_cstack",
    "change": "Replace constant with right matrix multiplication"
  }]
}

CRITICAL: Output ONLY valid JSON. No explanations. No markdown.
```

### Writer Prompt (Draft)
```
You are a diff renderer. Given a JSON plan, output ONLY a unified diff.

Input Plan:
{...}

Source Context:
def _cstack(left, right):
    # ... 20 lines ...

Output Requirements:
- Unified diff format ONLY
- No markdown (no ```diff)
- No explanations
- Match plan exactly

Example Output:
diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -242,7 +242,7 @@
...
```

**Recommendation**: Finalize prompts **before** Phase 2.1 coding.

---

## 8. Testing Strategy Gaps

**Current Plan**: "Unit tests for planner/writer"

**Missing**:

1. **Golden Dataset**:
   - Need 5-10 known-good (plan, diff) pairs
   - Use for regression testing

2. **Adversarial Tests**:
   - Malformed JSON from Planner → Writer should reject
   - Vague plan → Writer should request clarification (or fail gracefully)

3. **Integration Tests**:
   - Full 2-stage pipeline on synthetic bugs
   - Before testing on real instances

**Recommendation**: Create `tests/fixtures/golden_plans.json` before Phase 2.2.

---

## 9. Comparison with Related Work

### OpenAI's "Codex" Multi-Step Approach
- Similar: Separates "understanding" from "generation"
- Different: Uses intermediate natural language, not JSON

### GitHub Copilot Workspaces
- Similar: Plan-based code generation
- Different: Interactive user approval of plan

### Facebook's SapFix
- Similar: Template-based fix generation
- Different: Uses heuristics, not LLM

**Takeaway**: Plan-then-Diff is established pattern, not novel. Good sign.

---

## 10. Final Recommendations

### ✅ Approved Design Elements

1. **2-stage architecture**: Sound for failure mode separation
2. **Feature flag approach**: Safe rollout strategy
3. **Error classification**: Core innovation, needs refinement
4. **Rollback plan**: Well-defined

### ⚠️ Needs Refinement Before Implementation

1. **JSON Schema**: Start minimal, grow as needed
2. **Context Extraction**: Define exact rules for "minimal context"
3. **Error Classification**: Use multi-signal voting
4. **Model Selection**: gpt-4o-mini for research mode Planner
5. **Prompts**: Finalize before coding
6. **Metrics**: Add structured logging from day 1

### 🔴 Critical Risks to Address

1. **Plan-Diff Mismatch**: Needs strong validation gate
2. **Planner Verbosity**: Monitor token count, cap if needed
3. **Cost**: Track closely, ensure 2-stage ≤ 1-stage cost

### 🎯 Recommended Next Steps

**Option A: Scaffolding-First (Current Plan)**
- Safer, more structured
- Slower to validate core hypothesis

**Option B: Spike-First (Alternative)**
- Faster validation
- Risk of wasted spike code

**Recommendation**: **Hybrid Approach**
1. **Week 1 Day 1-2**: Quick spike on astropy-14182 (validate hypothesis)
2. **Week 1 Day 3-5**: If spike succeeds, refactor into proper architecture
3. **Week 2**: Smart retry + full regression
4. **Week 3**: Optimization

---

## 11. Design Approval Checklist

Before proceeding to implementation:

- [ ] Finalize minimal JSON schema
- [ ] Write Planner/Writer prompt templates
- [ ] Define context extraction rules
- [ ] Implement error classification logic (on paper)
- [ ] Create golden dataset (5 examples)
- [ ] Decide: Spike-first or Scaffolding-first?
- [ ] Set up structured logging schema
- [ ] Define success metrics for Phase 2.1

---

## 12. Open Questions for Discussion

1. **Q**: Should we support "Official Mode" (no reference) in Phase 2, or focus only on Research Mode?
   - **Impact**: Research-only → simpler, faster
   - **Trade-off**: Less generalizable

2. **Q**: Maximum plan JSON size? (token limit)
   - **Proposal**: 500 tokens max
   - **Rationale**: Force conciseness

3. **Q**: Should Writer have access to reference patch, or only plan?
   - **Pro (access)**: Better line number accuracy
   - **Con (access)**: Might bypass plan, copy reference

4. **Q**: Retry limits - current A=1, B=2. Optimal?
   - **Alternative**: A=2, B=3 (more tolerant)
   - **Alternative**: Adaptive (increase if close to success)

5. **Q**: Should we add "plan confidence score" to JSON?
   - **Idea**: Planner outputs `"confidence": 0.85`
   - **Use**: Skip Writer if confidence < 0.5, replan immediately

---

**Review Status**: ✅ Design is sound with refinements
**Recommendation**: Proceed to implementation **after** addressing "Needs Refinement" items
**Risk Level**: Medium (manageable with proposed mitigations)

---

**Reviewed By**: Claude Code
**Date**: 2025-12-27
**Next**: Refine schema & prompts → Implement Phase 2.1 (or Spike)
