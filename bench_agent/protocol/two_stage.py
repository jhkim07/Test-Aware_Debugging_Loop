"""
Phase 2: Two-Stage Wrapper

Unified interface for 2-stage Plan-then-Diff architecture.
Combines Planner (Stage A) and Diff Writer (Stage B).
"""

import os
from typing import Dict, Optional

from bench_agent.agent.planner import generate_plan, validate_plan_schema
from bench_agent.agent.diff_writer import render_diff, validate_diff_matches_plan
from bench_agent.protocol.diff_cleaner import clean_diff_format


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_planner_model(mode: str = "research") -> str:
    """
    Select Planner model based on mode.

    Research mode (reference available): gpt-4o-mini (4x cheaper)
    Official mode (no reference): gpt-4o (more creative)
    """
    # For Phase 2.1, always use mini (we're in research mode)
    return os.getenv("PLANNER_MODEL", "gpt-4o-mini")


def get_writer_model() -> str:
    """
    Select Writer model.

    Always use gpt-4o-mini for stable diff formatting.
    """
    return os.getenv("WRITER_MODEL", "gpt-4o-mini")


# ============================================================================
# MAIN TWO-STAGE FUNCTION
# ============================================================================

def generate_diff_two_stage(
    role: str,
    client,
    context: Dict,
    mode: str = "research",
    max_retries: int = 2
) -> str:
    """
    Unified 2-stage generation for both test and code diffs.

    Args:
        role: "test" or "code"
        client: LLM client
        context: Dict with problem_statement, reference_patch, etc.
        mode: "research" or "official"
        max_retries: Max retries for Writer (Stage B)

    Returns:
        Unified diff string

    Raises:
        RuntimeError: If generation fails after retries
    """

    planner_model = get_planner_model(mode)
    writer_model = get_writer_model()

    # ========================================================================
    # STAGE A: PLANNER
    # ========================================================================

    try:
        plan = generate_plan(role, client, planner_model, context, mode)
    except Exception as e:
        raise RuntimeError(f"[Stage A] Planner failed: {e}")

    # Validate plan schema
    ok, msg = validate_plan_schema(plan, role)
    if not ok:
        raise RuntimeError(f"[Stage A] Plan validation failed: {msg}")

    print(f"[Stage A] Plan generated and validated")

    # ========================================================================
    # STAGE B: DIFF WRITER (with retry)
    # ========================================================================

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            diff = render_diff(role, plan, client, writer_model, context)

            # Validate diff matches plan
            ok, msg = validate_diff_matches_plan(diff, plan, role)
            if not ok:
                raise ValueError(f"Plan-Diff mismatch: {msg}")

            # Clean diff format (remove any remaining markdown, etc.)
            diff = clean_diff_format(diff)

            print(f"[Stage B] Diff generated and validated (attempt {attempt + 1})")
            return diff

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"[Stage B] Attempt {attempt + 1} failed: {e}. Retrying...")
            else:
                print(f"[Stage B] All {max_retries + 1} attempts failed")

    # All retries exhausted
    raise RuntimeError(f"[Stage B] Writer failed after {max_retries + 1} attempts. Last error: {last_error}")


# ============================================================================
# CONVENIENCE WRAPPERS
# ============================================================================

def generate_test_diff_two_stage(client, context: Dict, mode: str = "research") -> str:
    """Generate test diff using 2-stage architecture."""
    return generate_diff_two_stage("test", client, context, mode)


def generate_code_diff_two_stage(client, context: Dict, mode: str = "research") -> str:
    """Generate code diff using 2-stage architecture."""
    return generate_diff_two_stage("code", client, context, mode)
