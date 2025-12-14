"""
Patch builder utilities for combining test diffs, code diffs, and conftest.py injection.
"""
from pathlib import Path
from bench_agent.runner.conftest_injector import CONFTEXT


def create_conftest_diff(repo_root: str = ".", force_update: bool = False) -> str:
    """
    Create a unified diff for conftest.py injection.
    
    Uses /dev/null format. If conftest.py already exists, the patch will fail,
    but SWE-bench harness may handle this gracefully or we can skip conftest
    injection in the patch and use a different mechanism.
    
    For now, we use /dev/null format and rely on the fact that most repositories
    don't have a root-level conftest.py.
    """
    conftest_content = CONFTEXT.strip() + "\n"
    
    # Split into lines for diff format
    lines = conftest_content.splitlines(keepends=False)  # Remove trailing newlines
    
    # Create unified diff format
    num_lines = len(lines)
    
    # Use /dev/null format - works when file doesn't exist
    # If file exists, patch will fail, but we'll handle that separately if needed
    diff_lines = [
        "--- /dev/null",
        "+++ b/conftest.py",
        f"@@ -0,0 +1,{num_lines} @@",
    ]
    
    # Add each line with + prefix
    for line in lines:
        diff_lines.append("+" + line)
    
    # Ensure diff ends with newline for proper separation when combining
    return "\n".join(diff_lines) + "\n"


def ensure_conftest_in_patch(patch: str) -> str:
    """
    Ensure conftest.py is included in the patch.
    If conftest.py diff is already present, return as-is.
    Otherwise, prepend conftest.py diff.
    """
    if "conftest.py" in patch and ("--- a/conftest.py" in patch or "--- /dev/null" in patch and "+++ b/conftest.py" in patch):
        # Already has conftest.py
        return patch
    
    # Prepend conftest diff
    conftest_diff = create_conftest_diff()
    return conftest_diff + "\n" + patch.strip() + "\n"


def combine_diffs(test_diff: str, code_diff: str, include_conftest: bool = False) -> str:
    """
    Combine test diff, code diff, and optionally conftest.py diff.
    
    NOTE: include_conftest is now False by default because conftest.py
    injection via patch causes issues when the file already exists.
    Conftest should be injected via a different mechanism (e.g., before
    running the harness).
    
    Args:
        test_diff: Test file changes (unified diff)
        code_diff: Production code changes (unified diff)
        include_conftest: Whether to include conftest.py injection (default: False)
    
    Returns:
        Combined unified diff
    """
    parts = []
    
    # NOTE: Conftest injection disabled by default to avoid patch application failures
    # when conftest.py already exists. Use inject_conftest() function instead.
    if include_conftest:
        conftest_diff = create_conftest_diff()
        parts.append(conftest_diff)
    
    if test_diff.strip():
        # Clean test_diff to remove excessive empty lines
        from bench_agent.protocol.diff_cleaner import remove_excessive_empty_lines
        cleaned_test = remove_excessive_empty_lines(test_diff.strip())
        parts.append(cleaned_test)
    
    if code_diff.strip():
        # Clean code_diff to remove excessive empty lines
        from bench_agent.protocol.diff_cleaner import remove_excessive_empty_lines
        cleaned_code = remove_excessive_empty_lines(code_diff.strip())
        parts.append(cleaned_code)
    
    # Strip each part to remove trailing newlines, then join with double newline
    # This ensures exactly one blank line between diff sections
    stripped_parts = [p.rstrip() for p in parts if p.strip()]
    result = "\n\n".join(stripped_parts)
    return result + "\n" if result else ""

