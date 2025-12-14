from .llm_client import chat
from .prompts import SYSTEM_PATCH_AUTHOR
from bench_agent.protocol.diff_cleaner import clean_diff_format

def propose_patch(client, model: str, repo_context: str, failure_summary: str, test_diff: str) -> str:
    messages = [{"role":"system","content":SYSTEM_PATCH_AUTHOR}]
    
    # Extract reference solution patch from repo_context if present
    reference_patch_note = ""
    if "Reference Solution Patch" in repo_context:
        reference_patch_note = "\n\nIMPORTANT: The Repository context above includes a 'Reference Solution Patch' section. "
        reference_patch_note += "You MUST closely follow that patch - use the same file, function, and fix approach."
    
    messages.append({"role":"user","content":f"""Repository context (includes Problem Statement and Reference Solution Patch):
{repo_context}

Failure summary:
{failure_summary}

New/updated tests diff:
{test_diff}
{reference_patch_note}

Produce a unified diff for production code only. Your patch should closely match the Reference Solution Patch if provided."""})
    output = chat(client, model, messages).strip()
    # Clean diff format: remove markdown markers, fix hunk headers
    return clean_diff_format(output)
