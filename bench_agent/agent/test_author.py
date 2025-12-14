from .llm_client import chat
from .prompts import SYSTEM_TEST_AUTHOR
from bench_agent.protocol.diff_cleaner import clean_diff_format

def propose_tests(client, model: str, repo_context: str, failure_summary: str, current_tests_hint: str="", previous_feedback: str="") -> str:
    messages = [{"role":"system","content":SYSTEM_TEST_AUTHOR}]
    
    # Add previous iteration feedback if available
    feedback_section = ""
    if previous_feedback:
        feedback_section = f"\n\n=== Previous Iteration Feedback ===\n{previous_feedback}\n"
        feedback_section += "\nIMPORTANT: Address the issues mentioned above in your test generation."
    
    messages.append({"role":"user","content":f"""Repository context (partial):
{repo_context}

Failure summary:
{failure_summary}

Current tests hint (optional):
{current_tests_hint}
{feedback_section}

Produce a unified diff for pytest tests only."""})
    output = chat(client, model, messages).strip()
    # Clean diff format: remove markdown markers, fix hunk headers, convert .ta_split.json
    return clean_diff_format(output)
