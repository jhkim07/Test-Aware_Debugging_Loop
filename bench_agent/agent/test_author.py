from .llm_client import chat
from .prompts import SYSTEM_TEST_AUTHOR
from bench_agent.protocol.diff_cleaner import clean_diff_format

def propose_tests(
    client,
    model: str,
    repo_context: str,
    failure_summary: str,
    current_tests_hint: str = "",
    previous_feedback: str = "",
    expected_value_hints: str = ""  # P0-2: Add expected value enforcement
) -> str:
    """
    Propose test diff using LLM.

    P0-2 Enhancement: Add expected_value_hints parameter to enforce
    reference test expected values for BRS stability.
    """
    messages = [{"role": "system", "content": SYSTEM_TEST_AUTHOR}]

    # Add previous iteration feedback if available
    feedback_section = ""
    if previous_feedback:
        feedback_section = f"\n\n=== Previous Iteration Feedback ===\n{previous_feedback}\n"
        feedback_section += "\nIMPORTANT: Address the issues mentioned above in your test generation."

    # P0-2: Add expected value enforcement section
    expected_value_section = ""
    if expected_value_hints:
        expected_value_section = f"\n\n=== CRITICAL: Expected Values from Reference Test ===\n{expected_value_hints}\n"
        expected_value_section += "\n⚠️ WARNING: If you use different expected values, the test may pass on buggy code (BRS failure)!"

    messages.append({"role": "user", "content": f"""Repository context (partial):
{repo_context}

Failure summary:
{failure_summary}

Current tests hint (optional):
{current_tests_hint}
{expected_value_section}
{feedback_section}

Produce a unified diff for pytest tests only."""})
    output = chat(client, model, messages).strip()
    # Clean diff format: remove markdown markers, fix hunk headers, convert .ta_split.json
    return clean_diff_format(output)
