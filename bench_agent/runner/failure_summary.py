from pathlib import Path
import re
import json

def summarize_failure(report_dir: Path, instance_id: str) -> str:
    """
    Best-effort summary: looks for instance-specific logs/reports under report_dir.
    SWE-bench output formats can vary across versions; this function is intentionally defensive.
    """
    texts = []
    # include harness stdout/stderr dumps if present
    for pat in ["**/*log*", "**/*report*.json", "**/*results*.json", "**/*.txt"]:
        for fp in report_dir.glob(pat):
            if fp.is_file() and fp.stat().st_size < 2_000_000:
                try:
                    content = fp.read_text(errors="ignore")
                except Exception:
                    continue
                if instance_id in content or "FAIL" in content or "Traceback" in content:
                    texts.append(f"--- {fp} ---\n{content[-5000:]}")
    if not texts:
        return "No detailed report files found; check runs output manually."
    # crude trimming
    joined = "\n\n".join(texts)
    return joined[-12000:]
