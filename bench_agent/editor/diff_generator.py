"""
Component 3: Diff Generator

Generates unified diffs from before/after code states.
Required since edit scripts modify source directly, but SWE-bench needs diffs.
"""

import difflib
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class DiffResult:
    """Result of diff generation."""
    diff: str
    added_lines: int
    removed_lines: int
    context_lines: int
    hunks: int


# ============================================================================
# UNIFIED DIFF GENERATION
# ============================================================================

def generate_unified_diff(
    original_code: str,
    modified_code: str,
    filepath: str = "file.py",
    context_lines: int = 3
) -> str:
    """
    Generate unified diff from original and modified code.

    Uses Python's difflib to produce standard unified diff format
    compatible with patch(1) and git apply.

    Args:
        original_code: Original source code
        modified_code: Modified source code
        filepath: File path for diff header
        context_lines: Number of context lines (default 3)

    Returns:
        Unified diff string
    """
    # Split into lines WITHOUT line endings
    # difflib.unified_diff will add line terminators based on lineterm parameter
    original_lines = original_code.splitlines()
    modified_lines = modified_code.splitlines()

    # Generate unified diff
    diff_lines = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm='',
        n=context_lines
    )

    # Join into string (diff_lines don't have line endings due to lineterm='')
    diff = '\n'.join(diff_lines)

    return diff


def generate_diff_with_stats(
    original_code: str,
    modified_code: str,
    filepath: str = "file.py",
    context_lines: int = 3
) -> DiffResult:
    """
    Generate unified diff with statistics.

    Args:
        original_code: Original source code
        modified_code: Modified source code
        filepath: File path for diff header
        context_lines: Number of context lines

    Returns:
        DiffResult with diff and statistics
    """
    diff = generate_unified_diff(
        original_code,
        modified_code,
        filepath,
        context_lines
    )

    # Compute statistics
    stats = compute_diff_stats(diff)

    return DiffResult(
        diff=diff,
        added_lines=stats['added_lines'],
        removed_lines=stats['removed_lines'],
        context_lines=stats['context_lines'],
        hunks=stats['hunks']
    )


# ============================================================================
# DIFF STATISTICS
# ============================================================================

def compute_diff_stats(diff: str) -> dict:
    """
    Compute statistics from unified diff.

    Args:
        diff: Unified diff string

    Returns:
        Dict with statistics
    """
    if not diff:
        return {
            'added_lines': 0,
            'removed_lines': 0,
            'context_lines': 0,
            'hunks': 0
        }

    lines = diff.split('\n')

    added = 0
    removed = 0
    context = 0
    hunks = 0

    for line in lines:
        if line.startswith('@@'):
            hunks += 1
        elif line.startswith('+') and not line.startswith('+++'):
            added += 1
        elif line.startswith('-') and not line.startswith('---'):
            removed += 1
        elif line.startswith(' '):
            context += 1

    return {
        'added_lines': added,
        'removed_lines': removed,
        'context_lines': context,
        'hunks': hunks
    }


def is_empty_diff(diff: str) -> bool:
    """
    Check if diff is empty (no changes).

    Args:
        diff: Unified diff string

    Returns:
        True if diff contains no changes
    """
    stats = compute_diff_stats(diff)
    return stats['added_lines'] == 0 and stats['removed_lines'] == 0


# ============================================================================
# DIFF VALIDATION
# ============================================================================

def validate_diff_format(diff: str) -> tuple[bool, Optional[str]]:
    """
    Validate that diff is in correct unified diff format.

    Args:
        diff: Diff string to validate

    Returns:
        (is_valid, error_message)
    """
    if not diff:
        return (False, "Diff is empty")

    lines = diff.split('\n')

    # Check for file headers
    has_from_header = any(line.startswith('---') for line in lines)
    has_to_header = any(line.startswith('+++') for line in lines)

    if not has_from_header:
        return (False, "Missing '---' header (fromfile)")

    if not has_to_header:
        return (False, "Missing '+++' header (tofile)")

    # Check for at least one hunk
    has_hunk = any(line.startswith('@@') for line in lines)

    if not has_hunk:
        # Empty diff is valid (no changes)
        if is_empty_diff(diff):
            return (True, None)
        return (False, "No hunks found")

    # Check hunk format
    for i, line in enumerate(lines):
        if line.startswith('@@'):
            # Hunk header format: @@ -start,count +start,count @@
            if not line.endswith('@@'):
                return (False, f"Malformed hunk header at line {i+1}: {line}")

    return (True, None)


# ============================================================================
# DIFF FORMATTING
# ============================================================================

def format_diff_stats(stats: dict) -> str:
    """
    Format diff statistics for display.

    Args:
        stats: Statistics dict

    Returns:
        Formatted string
    """
    lines = [
        f"Hunks: {stats['hunks']}",
        f"Added lines: +{stats['added_lines']}",
        f"Removed lines: -{stats['removed_lines']}",
        f"Context lines: {stats['context_lines']}"
    ]

    return '\n'.join(lines)


def format_diff_result(result: DiffResult) -> str:
    """
    Format diff result for display.

    Args:
        result: DiffResult

    Returns:
        Formatted string
    """
    lines = [
        "Diff Statistics:",
        f"  Hunks: {result.hunks}",
        f"  Added: +{result.added_lines}",
        f"  Removed: -{result.removed_lines}",
        f"  Context: {result.context_lines}",
        "",
        "Diff:",
        result.diff
    ]

    return '\n'.join(lines)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_patch_from_edits(
    original_code: str,
    modified_code: str,
    filepath: str
) -> str:
    """
    Create patch file content from before/after code.

    This is the main interface for converting edit script results
    into SWE-bench compatible patches.

    Args:
        original_code: Original source code
        modified_code: Modified source code
        filepath: File path (for patch header)

    Returns:
        Patch file content (unified diff format)
    """
    return generate_unified_diff(
        original_code,
        modified_code,
        filepath,
        context_lines=3
    )


def verify_patch_applies(patch: str) -> tuple[bool, Optional[str]]:
    """
    Verify that patch is well-formed.

    Does NOT actually apply the patch, just validates format.

    Args:
        patch: Patch content (unified diff)

    Returns:
        (is_valid, error_message)
    """
    return validate_diff_format(patch)


# ============================================================================
# DIFF COMPARISON
# ============================================================================

def compare_diffs(diff1: str, diff2: str) -> dict:
    """
    Compare two diffs for similarity.

    Useful for verifying that edit script produces expected diff.

    Args:
        diff1: First diff
        diff2: Second diff

    Returns:
        Dict with comparison results
    """
    stats1 = compute_diff_stats(diff1)
    stats2 = compute_diff_stats(diff2)

    # Normalize both diffs (remove headers for comparison)
    def normalize_for_comparison(diff: str) -> str:
        lines = []
        for line in diff.split('\n'):
            # Skip file headers
            if line.startswith('---') or line.startswith('+++'):
                continue
            # Skip hunk headers (may differ in line numbers)
            if line.startswith('@@'):
                continue
            lines.append(line)
        return '\n'.join(lines)

    normalized1 = normalize_for_comparison(diff1)
    normalized2 = normalize_for_comparison(diff2)

    exact_match = normalized1 == normalized2

    return {
        'exact_match': exact_match,
        'stats_match': stats1 == stats2,
        'stats1': stats1,
        'stats2': stats2,
        'diff1_lines': len(diff1.split('\n')),
        'diff2_lines': len(diff2.split('\n'))
    }


# ============================================================================
# MULTI-FILE DIFF SUPPORT
# ============================================================================

def generate_multi_file_diff(
    file_changes: List[tuple[str, str, str]]
) -> str:
    """
    Generate unified diff for multiple files.

    Args:
        file_changes: List of (filepath, original_code, modified_code)

    Returns:
        Combined unified diff for all files
    """
    diffs = []

    for filepath, original, modified in file_changes:
        diff = generate_unified_diff(original, modified, filepath)
        if diff:  # Only include non-empty diffs
            diffs.append(diff)

    return '\n'.join(diffs)


def parse_multi_file_diff(diff: str) -> List[tuple[str, str]]:
    """
    Parse multi-file diff into (filepath, file_diff) pairs.

    Args:
        diff: Combined diff string

    Returns:
        List of (filepath, file_diff) tuples
    """
    files = []
    current_file = None
    current_diff_lines = []

    for line in diff.split('\n'):
        if line.startswith('--- a/'):
            # Start of new file
            if current_file and current_diff_lines:
                files.append((current_file, '\n'.join(current_diff_lines)))

            # Extract filepath
            current_file = line[6:]  # Remove '--- a/'
            current_diff_lines = [line]

        elif current_diff_lines is not None:
            current_diff_lines.append(line)

    # Add last file
    if current_file and current_diff_lines:
        files.append((current_file, '\n'.join(current_diff_lines)))

    return files
