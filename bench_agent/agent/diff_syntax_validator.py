"""
Phase 2.2: Diff Syntax Validator

Validates and sanitizes unified diffs to prevent malformed patches.

Components:
1. Syntax validation - checks for complete hunk headers, stray quotes, etc.
2. Multi-line string sanitizer - removes invalid triple-quote remnants
3. Hunk header completion - calculates missing line counts
"""

import re
from typing import Tuple, List


# ============================================================================
# VALIDATION
# ============================================================================

def validate_diff_syntax(diff: str) -> Tuple[bool, List[str]]:
    """
    Validate diff syntax and return (is_valid, list_of_errors).

    Checks:
    1. All hunks have complete headers: @@ -X,Y +A,B @@
    2. No stray triple-quotes outside context
    3. No markdown markers (```)
    4. Valid line prefixes (+, -, space)
    5. Proper file headers (diff --git, ---, +++)

    Args:
        diff: Unified diff string

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors = []

    if not diff or not diff.strip():
        errors.append("Empty diff")
        return (False, errors)

    # Check 1: Hunk header completeness
    # Valid: @@ -X,Y +A,B @@
    # Invalid: @@ -X,Y  (missing + side)
    incomplete_pattern = r'@@ -\d+,\d+(?!\s*\+)'
    for match in re.finditer(incomplete_pattern, diff):
        errors.append(f"Incomplete hunk header at position {match.start()}: {match.group()}")

    # Check 2: Stray triple-quotes outside valid context
    lines = diff.split('\n')
    for i, line in enumerate(lines, 1):
        if '"""' in line or "'''" in line:
            # Only allow in context (lines starting with space, +, or -)
            if not line.startswith((' ', '+', '-', 'diff', '---', '+++')):
                # Exception: Allow in file headers
                if not (line.startswith('diff ') or line.startswith('index ')):
                    errors.append(f"Stray triple-quote at line {i}: {line[:60]}...")

    # Check 3: Markdown code block markers
    if '```' in diff:
        errors.append("Markdown code block markers (```) found in diff")

    # Check 4: File header presence
    if not diff.strip().startswith(('diff --git', '--- a/', '+++ b/')):
        # Allow diffs that start with hunk header (partial diffs)
        if not diff.strip().startswith('@@'):
            errors.append("Missing proper file header (should start with 'diff --git' or '---')")

    # Check 5: Invalid line prefixes in hunks
    in_hunk = False
    for i, line in enumerate(lines, 1):
        if line.startswith('@@'):
            in_hunk = True
            continue

        if in_hunk and line.strip():  # Non-empty line in hunk
            # Valid prefixes: +, -, space, or hunk boundary
            if not line.startswith(('+', '-', ' ', '@@', 'diff', '---', '+++')):
                # Allow empty lines
                if line.strip():
                    errors.append(f"Invalid line prefix at line {i}: {line[:60]}...")

    return (len(errors) == 0, errors)


# ============================================================================
# SANITIZATION
# ============================================================================

def sanitize_multiline_strings(diff: str) -> str:
    """
    Remove stray triple-quoted string remnants from diff.

    Strategy:
    1. Identify lines with triple-quotes that are NOT valid context
    2. Remove them if they appear outside proper diff syntax
    3. Preserve valid multi-line strings in context

    Args:
        diff: Unified diff string

    Returns:
        Cleaned diff string
    """
    lines = diff.split('\n')
    cleaned_lines = []
    in_hunk = False

    for line in lines:
        # Track if we're in a hunk (after @@ header)
        if line.startswith('@@'):
            in_hunk = True
            cleaned_lines.append(line)
            continue

        # File headers
        if line.startswith(('diff ', '--- ', '+++ ', 'index ')):
            in_hunk = False
            cleaned_lines.append(line)
            continue

        # If in hunk, check for stray quotes
        if in_hunk:
            # Valid context line: starts with space, +, or -
            if line.startswith((' ', '+', '-')):
                cleaned_lines.append(line)
            # Allow empty lines in hunks
            elif not line.strip():
                cleaned_lines.append(line)
            else:
                # Invalid line in hunk - likely LLM hallucination
                # Examples: "......", stray text, incomplete lines
                # Skip all invalid lines (don't keep them)
                continue
        else:
            # Outside hunk - between file headers and hunk header
            # Only allow valid file header lines and empty lines
            if line.startswith(('diff ', '--- ', '+++ ', 'index ', '@@')):
                cleaned_lines.append(line)
            elif not line.strip():
                # Empty line - keep it
                cleaned_lines.append(line)
            else:
                # Invalid line between headers (e.g., "==== ==== ====")
                # Skip it - likely LLM hallucination
                continue

    return '\n'.join(cleaned_lines)


def complete_hunk_headers(diff: str) -> str:
    """
    Fix incomplete hunk headers by calculating missing line counts.

    Incomplete: @@ -57,10
    Complete:   @@ -57,10 +67,15 @@

    Strategy:
    1. Find incomplete headers (missing + side)
    2. Count lines in hunk to calculate new_count
    3. Calculate new_start from old_start and context
    4. Replace with complete header

    Args:
        diff: Unified diff string

    Returns:
        Diff with completed hunk headers
    """
    lines = diff.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for incomplete hunk header
        # Pattern: @@ -X,Y  (no + side)
        match = re.match(r'@@ -(\d+),(\d+)\s*$', line)
        if match:
            # Incomplete header found
            old_start = int(match.group(1))
            old_count = int(match.group(2))

            # Count hunk lines to calculate new side
            j = i + 1
            added = 0
            removed = 0
            context = 0

            # Scan until next hunk or end of diff
            while j < len(lines):
                next_line = lines[j]

                # Stop at next hunk or file header
                if next_line.startswith(('@@', 'diff ', '--- ', '+++ ')):
                    break

                if next_line.startswith('+'):
                    added += 1
                elif next_line.startswith('-'):
                    removed += 1
                elif next_line.startswith(' '):
                    context += 1

                j += 1

            # Calculate new side
            # new_start usually equals old_start (unless there are leading removals)
            new_start = old_start
            new_count = old_count - removed + added

            # Build complete header
            complete_header = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
            result.append(complete_header)
        else:
            # Not an incomplete header, keep as is
            result.append(line)

        i += 1

    return '\n'.join(result)


# ============================================================================
# COMBINED SANITIZATION PIPELINE
# ============================================================================

def sanitize_diff(diff: str) -> Tuple[str, List[str]]:
    """
    Apply full sanitization pipeline to diff.

    Pipeline:
    1. Remove stray multi-line strings
    2. Complete incomplete hunk headers
    3. Validate syntax

    Args:
        diff: Raw diff from LLM

    Returns:
        (sanitized_diff, list_of_warnings)
    """
    warnings = []

    # Step 1: Sanitize multi-line strings
    original_length = len(diff)
    diff = sanitize_multiline_strings(diff)
    if len(diff) != original_length:
        warnings.append("Removed stray multi-line string markers")

    # Step 2: Complete hunk headers
    original_diff = diff
    diff = complete_hunk_headers(diff)
    if diff != original_diff:
        warnings.append("Completed incomplete hunk headers")

    # Step 3: Validate
    is_valid, errors = validate_diff_syntax(diff)
    if not is_valid:
        # Return errors as warnings (caller decides what to do)
        warnings.extend([f"Validation: {err}" for err in errors])

    return (diff, warnings)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_hunk_info(hunk_header: str) -> dict:
    """
    Extract information from a hunk header.

    Args:
        hunk_header: String like "@@ -57,10 +67,15 @@"

    Returns:
        Dict with old_start, old_count, new_start, new_count
    """
    match = re.match(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', hunk_header)
    if match:
        return {
            'old_start': int(match.group(1)),
            'old_count': int(match.group(2)),
            'new_start': int(match.group(3)),
            'new_count': int(match.group(4))
        }
    return {}


def is_valid_hunk_header(line: str) -> bool:
    """Check if line is a valid complete hunk header."""
    pattern = r'@@ -\d+,\d+ \+\d+,\d+ @@'
    return bool(re.match(pattern, line))
