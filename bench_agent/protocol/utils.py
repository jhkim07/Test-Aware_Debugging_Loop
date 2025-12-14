import subprocess, tempfile, os, textwrap, json
from pathlib import Path

def write_predictions_jsonl(path: Path, instance_id: str, patch: str) -> None:
    # swebench harness expects JSONL with {"instance_id": ..., "model_patch": "..."} at minimum
    # See harness docs/CLI. citeturn0search5
    # SWE-bench harness requires model_name_or_path field
    rec = {
        "instance_id": instance_id, 
        "model_patch": patch,
        "model_name_or_path": "test-aware-debugging",  # Required by SWE-bench harness
    }
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")

def now_ts() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
