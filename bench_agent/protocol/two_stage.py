"""
Phase 2: Two-Stage Wrapper

Unified interface for 2-stage Plan-then-Diff architecture.
Combines Planner (Stage A) and Diff Writer (Stage B).

Phase 2.2: Enhanced with iteration feedback and error tracking.
"""

import os
from typing import Dict, Optional, List

from bench_agent.agent.planner import generate_plan, validate_plan_schema
from bench_agent.agent.diff_writer import render_diff, validate_diff_matches_plan
from bench_agent.agent.diff_syntax_validator import (
    validate_diff_syntax,
    sanitize_diff,
    complete_hunk_headers,
    sanitize_multiline_strings
)
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
    max_retries: int = 2,
    previous_errors: Optional[List[str]] = None
) -> str:
    """
    Unified 2-stage generation for both test and code diffs.

    Phase 2.2: Enhanced with iteration feedback.

    Args:
        role: "test" or "code"
        client: LLM client
        context: Dict with problem_statement, reference_patch, etc.
        mode: "research" or "official"
        max_retries: Max retries for Writer (Stage B)
        previous_errors: List of errors from previous iterations (Phase 2.2)

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
    # STAGE B: DIFF WRITER (with retry and iteration feedback)
    # ========================================================================

    last_error = None
    error_accumulator = previous_errors.copy() if previous_errors else []

    for attempt in range(max_retries + 1):
        try:
            # Phase 2.2: Pass previous errors to Writer
            writer_context = context.copy()
            if error_accumulator:
                writer_context['previous_errors'] = error_accumulator

            diff = render_diff(role, plan, client, writer_model, writer_context)

            # Validate diff matches plan
            ok, msg = validate_diff_matches_plan(diff, plan, role)
            if not ok:
                error_accumulator.append(f"Plan-Diff mismatch: {msg}")
                raise ValueError(f"Plan-Diff mismatch: {msg}")

            # Phase 2.2: Full sanitization pipeline
            # Step 1: Apply sanitization (removes stray quotes, completes headers)
            original_diff = diff
            diff, sanitization_warnings = sanitize_diff(diff)

            # Filter out informational warnings (changes that were successfully applied)
            # Only keep actual validation errors
            error_warnings = [w for w in sanitization_warnings if w.startswith("Validation:")]
            info_warnings = [w for w in sanitization_warnings if not w.startswith("Validation:")]

            if info_warnings:
                print(f"[Stage B] Sanitization applied: {len(info_warnings)} fixes")
                for warning in info_warnings:
                    print(f"  ✓ {warning}")

            # Step 2: Syntax validation (after sanitization)
            # Only fail if there are actual validation errors AFTER sanitization
            if error_warnings:
                print(f"[Stage B] Validation errors after sanitization:")
                for warning in error_warnings:
                    print(f"  ✗ {warning}")
                error_accumulator.extend(error_warnings)
                raise ValueError(f"Diff syntax validation failed:\n{'; '.join(error_warnings)}")

            # Step 3: Clean diff format - SKIP for Phase 2.2 (already sanitized)
            # diff = clean_diff_format(diff)  # Disabled - sanitization handles this

            print(f"[Stage B] Diff generated and validated (attempt {attempt + 1})")
            return diff

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"[Stage B] Attempt {attempt + 1} failed: {e}. Retrying with feedback...")
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
