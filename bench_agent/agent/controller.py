import json
from .llm_client import chat
from .prompts import SYSTEM_CONTROLLER

def decide(client, model: str, failure_summary: str, history: list[dict], problem_statement: str = "") -> dict:
    messages = [{"role":"system","content":SYSTEM_CONTROLLER}]
    for h in history[-8:]:
        messages.append(h)
    
    user_content = ""
    if problem_statement:
        user_content += f"Problem Statement:\n{problem_statement[:2000]}\n\n"
    user_content += f"Failure summary:\n{failure_summary}\n\nReturn JSON decision."
    
    messages.append({"role":"user","content":user_content})
    out = chat(client, model, messages)
    # best-effort parse
    try:
        return json.loads(out)
    except Exception:
        return {"focus":"both","hypotheses":[out[:500]],"targets":[]}
