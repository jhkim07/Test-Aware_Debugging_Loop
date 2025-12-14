from __future__ import annotations

import re

NODEID_RE = re.compile(r"(^|\s)(?P<nodeid>[\w\-/\.]+::[^\s]+)", re.MULTILINE)

def extract_nodeids_from_text(text: str) -> list[str]:
    out = []
    for m in NODEID_RE.finditer(text):
        nid = m.group("nodeid").strip()
        if "::" in nid:
            out.append(nid)
    return list(dict.fromkeys(out))

def extract_failing_nodeids_from_text(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if line.startswith("FAILED "):
            parts = line.split()
            if len(parts) >= 2 and "::" in parts[1]:
                out.append(parts[1].strip())
    return list(dict.fromkeys(out))
