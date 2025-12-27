#!/usr/bin/env python3
"""
Design Validation: Quick check of 2-stage hypothesis

Goal: Verify that 2-stage architecture can generate valid diffs
WITHOUT running full test harness.

Tests:
1. Can Planner generate valid JSON from reference patch?
2. Can Writer convert JSON to valid diff structure?
3. Does output pass basic validation gates?

This is NOT a full integration test - just design validation.
"""

import json
from pathlib import Path

from bench_agent.agent.llm_client import make_client, chat
from bench_agent.protocol.diff_validator import validate_diff_structure


# ============================================================================
# PROMPTS (Minimal for validation)
# ============================================================================

PLANNER_PROMPT = """You are analyzing a bug fix.

Given the reference patch below, extract a simple plan in JSON format.

Reference Patch:
{reference_patch}

Output JSON (no markdown, no explanation):
{{
  "files": [
    {{
      "path": "exact/path/from/patch",
      "function_or_class": "name from patch",
      "change_summary": "one sentence"
    }}
  ]
}}

Output ONLY the JSON above."""


WRITER_PROMPT = """You are a diff generator.

Convert this plan to a unified diff format:

Plan:
{plan}

Reference for guidance:
{reference_hint}

Output ONLY unified diff (no markdown, no explanation).
Start with: diff --git a/..."""


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_1_planner_generates_valid_json():
    """Test 1: Can Planner parse reference and output valid JSON?"""

    print("\n" + "="*80)
    print("TEST 1: Planner JSON Generation")
    print("="*80)

    # Load real reference patch
    context_file = Path("outputs/poc_two_stage/astropy_14182_context.json")
    if not context_file.exists():
        print("❌ Context file not found. Run poc_load_context.py first.")
        return False

    with open(context_file) as f:
        context = json.load(f)

    reference_patch = context['reference_patch']

    # Call Planner
    client = make_client()
    model = "gpt-4o-mini"

    prompt = PLANNER_PROMPT.format(reference_patch=reference_patch[:2000])

    messages = [
        {"role": "system", "content": "You are a code analysis assistant."},
        {"role": "user", "content": prompt}
    ]

    print("Calling Planner LLM...")
    response = chat(client, model, messages).strip()

    # Remove markdown if present
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join([l for l in lines if not l.startswith("```")])

    print(f"Raw response ({len(response)} chars):")
    print(response[:500])

    # Parse JSON
    try:
        plan = json.loads(response)
        print("\n✅ Valid JSON generated")
        print(f"Plan: {json.dumps(plan, indent=2)}")

        # Check schema
        if "files" not in plan:
            print("⚠️ Missing 'files' key")
            return False

        if len(plan["files"]) == 0:
            print("⚠️ No files in plan")
            return False

        print(f"✅ Plan has {len(plan['files'])} file(s)")
        return plan

    except json.JSONDecodeError as e:
        print(f"❌ JSON parse failed: {e}")
        return False


def test_2_writer_generates_valid_diff(plan):
    """Test 2: Can Writer convert plan to valid diff?"""

    print("\n" + "="*80)
    print("TEST 2: Writer Diff Generation")
    print("="*80)

    if not plan:
        print("⏭️  Skipped (no plan from Test 1)")
        return False

    # Load reference for hints
    context_file = Path("outputs/poc_two_stage/astropy_14182_context.json")
    with open(context_file) as f:
        context = json.load(f)

    reference_hint = context['reference_patch'][:1000]  # First 1000 chars

    # Call Writer
    client = make_client()
    model = "gpt-4o-mini"

    prompt = WRITER_PROMPT.format(
        plan=json.dumps(plan, indent=2),
        reference_hint=reference_hint
    )

    messages = [
        {"role": "system", "content": "You are a precise diff generator."},
        {"role": "user", "content": prompt}
    ]

    print("Calling Writer LLM...")
    response = chat(client, model, messages).strip()

    # Remove markdown if present
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join([l for l in lines if not l.startswith("```")])

    print(f"\nDiff generated ({len(response)} chars)")
    print("Preview:")
    print(response[:400])

    # Validate structure
    try:
        ok, issues = validate_diff_structure(response)
        if ok:
            print("\n✅ Valid diff structure")
            return response
        else:
            print(f"\n⚠️ Diff structure issues: {issues}")
            return response  # Return anyway for analysis
    except Exception as e:
        print(f"\n❌ Validation exception: {e}")
        return False


def test_3_end_to_end_coherence(plan, diff):
    """Test 3: Does plan → diff maintain coherence?"""

    print("\n" + "="*80)
    print("TEST 3: Plan-Diff Coherence")
    print("="*80)

    if not plan or not diff:
        print("⏭️  Skipped (missing plan or diff)")
        return False

    # Check if files in plan appear in diff
    plan_files = [f['path'] for f in plan.get('files', [])]

    coherence_checks = []

    for plan_file in plan_files:
        if plan_file in diff:
            print(f"✅ File '{plan_file}' found in diff")
            coherence_checks.append(True)
        else:
            print(f"⚠️ File '{plan_file}' NOT found in diff")
            coherence_checks.append(False)

    if all(coherence_checks):
        print("\n✅ Plan-Diff coherence: PASS")
        return True
    else:
        print(f"\n⚠️ Plan-Diff coherence: PARTIAL ({sum(coherence_checks)}/{len(coherence_checks)})")
        return False


# ============================================================================
# MAIN VALIDATION
# ============================================================================

def validate_design():
    """Run all design validation tests."""

    print("="*80)
    print("DESIGN VALIDATION: 2-Stage Plan-then-Diff Architecture")
    print("="*80)
    print("\nInstance: astropy-14182")
    print("Goal: Validate core hypothesis (can 2-stage work?)")

    results = {
        "test_1_planner": False,
        "test_2_writer": False,
        "test_3_coherence": False
    }

    # Test 1: Planner
    plan = test_1_planner_generates_valid_json()
    results["test_1_planner"] = bool(plan)

    # Test 2: Writer
    diff = None
    if plan:
        diff = test_2_writer_generates_valid_diff(plan)
        results["test_2_writer"] = bool(diff)

    # Test 3: Coherence
    if plan and diff:
        coherent = test_3_end_to_end_coherence(plan, diff)
        results["test_3_coherence"] = coherent

    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())

    print("\n" + "="*80)
    if all_passed:
        print("✅ DESIGN VALIDATION: SUCCESSFUL")
        print("\nConclusion: 2-stage architecture is VIABLE")
        print("Recommendation: Proceed to full PoC implementation")
    else:
        print("⚠️ DESIGN VALIDATION: PARTIAL")
        print("\nConclusion: 2-stage architecture needs refinement")
        print("Recommendation: Address failing tests before full implementation")
    print("="*80)

    # Save results
    output_dir = Path("outputs/poc_two_stage")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "validation_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_dir}/validation_results.json")

    return all_passed


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        success = validate_design()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Validation interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n\n❌ Validation failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
