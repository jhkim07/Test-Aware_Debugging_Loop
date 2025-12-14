import re

FORBIDDEN_TEST_PATTERNS = [
    r"\bpytest\.skip\b",
    r"\bpytest\.xfail\b",
    r"\b@pytest\.mark\.skip\b",
    r"\b@pytest\.mark\.xfail\b",
]

FORBIDDEN_NETWORK_PATTERNS = [
    r"\brequests\.",
    r"\burllib\.",
    r"\bsocket\.",
    r"\bhttpx\.",
]

FORBIDDEN_FILEIO_PATTERNS = [
    r"\bopen\(",
    r"\bPath\(",
    r"\.write_text\(",
    r"\.read_text\(",
]

def _matches_any(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for p in patterns:
        if re.search(p, text):
            hits.append(p)
    return hits

def validate_test_diff(diff: str, forbid_skip=True, forbid_xfail=True, forbid_network=True, restrict_file_io=True) -> tuple[bool, list[str]]:
    issues = []
    if forbid_skip or forbid_xfail:
        hits = _matches_any(diff, FORBIDDEN_TEST_PATTERNS)
        if hits:
            issues.append(f"skip/xfail patterns found: {hits}")
    if forbid_network:
        hits = _matches_any(diff, FORBIDDEN_NETWORK_PATTERNS)
        if hits:
            issues.append(f"network patterns found: {hits}")
    if restrict_file_io:
        hits = _matches_any(diff, FORBIDDEN_FILEIO_PATTERNS)
        if hits:
            issues.append(f"file I/O patterns found: {hits} (consider removing or using tmp_path carefully)")
    return (len(issues)==0, issues)

def validate_patch_diff(diff: str) -> tuple[bool, list[str]]:
    # Minimal guardrails (extend as needed)
    issues = []
    if re.search(r"\bexcept\s*:\s*pass\b", diff):
        issues.append("broad 'except: pass' found")
    return (len(issues)==0, issues)
