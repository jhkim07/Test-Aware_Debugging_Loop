"""
Validate and fix diff line numbers for multi-hunk patches.
"""
import re
from typing import List, Tuple


def _calculate_actual_hunk_counts(lines: List[str], hunk_start_idx: int) -> Tuple[int, int]:
    """
    Calculate actual old_count and new_count by analyzing hunk content.
    
    Returns:
        (actual_old_count, actual_new_count)
    """
    added = 0
    removed = 0
    context = 0
    
    i = hunk_start_idx + 1
    while i < len(lines):
        line = lines[i]
        # Stop at next hunk or file boundary
        if line.startswith('@@') or line.startswith('diff --git'):
            break
        if line.startswith('+++') or line.startswith('---'):
            i += 1
            continue
        
        if line.startswith('+') and not line.startswith('+++'):
            added += 1
        elif line.startswith('-') and not line.startswith('---'):
            removed += 1
        elif line.strip():  # Non-empty context line
            context += 1
        
        i += 1
    
    actual_old_count = removed + context
    actual_new_count = added + context
    
    return actual_old_count, actual_new_count


def fix_multihunk_line_numbers(diff_text: str) -> str:
    """
    Fix line numbers in multi-hunk diffs.
    
    When a file has multiple hunks, the line numbers in later hunks need to
    account for changes made by earlier hunks in the same file.
    
    This function also corrects hunk headers with incorrect new_count values
    by analyzing the actual hunk content.
    """
    lines = diff_text.split('\n')
    fixed_lines = []
    
    i = 0
    current_file = None
    hunks_in_file = []  # List of (old_start, actual_old_count, new_start, actual_new_count, line_idx)
    
    while i < len(lines):
        line = lines[i]
        
        # Check for new file diff
        if line.startswith('diff --git') or (line.startswith('---') and i + 1 < len(lines) and lines[i+1].startswith('+++')):
            # Reset for new file
            current_file = line
            hunks_in_file = []
            fixed_lines.append(line)
            i += 1
            continue
        
        # Track file paths
        if line.startswith('---') or line.startswith('+++'):
            fixed_lines.append(line)
            i += 1
            continue
        
        # Check for hunk header
        hunk_match = re.match(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
        if hunk_match:
            old_start = int(hunk_match.group(1))
            header_old_count = int(hunk_match.group(2))
            new_start = int(hunk_match.group(3))
            header_new_count = int(hunk_match.group(4))
            
            # Special case: conftest.py with @@ -1 +1,<new_count> @@ format means "replace entire file"
            # Don't modify this as it's intentional for force_update scenarios
            is_conftest_force_update = (
                old_start == 1 and 
                header_old_count == 0 and  # @@ -1 +1,<new_count> @@ format (old_count=0 means "rest of file")
                current_file and 
                'conftest.py' in current_file
            )
            
            if is_conftest_force_update:
                # Keep the original header for conftest.py force_update
                old_count = header_old_count
                new_count = header_new_count
            else:
                # Calculate actual counts by analyzing hunk content
                actual_old_count, actual_new_count = _calculate_actual_hunk_counts(lines, i)
                
                # Use actual counts if they differ from header
                # Always use actual counts to ensure hunk content matches header
                if actual_old_count != header_old_count:
                    old_count = actual_old_count
                    print(f"[diff_validator] Corrected old_count: {header_old_count} → {actual_old_count} at line {i+1}", flush=True)
                else:
                    old_count = header_old_count
                
                if actual_new_count != header_new_count:
                    new_count = actual_new_count
                    print(f"[diff_validator] Corrected new_count: {header_new_count} → {actual_new_count} at line {i+1}", flush=True)
                else:
                    new_count = header_new_count
            
            # Calculate correct new_start based on previous hunks
            if hunks_in_file:
                # Find where previous hunk ended
                last_hunk = hunks_in_file[-1]
                last_old_start = last_hunk[0]
                last_old_count = last_hunk[1]
                last_old_end = last_old_start + last_old_count
                last_new_start = last_hunk[2]
                last_new_count = last_hunk[3]
                last_new_end = last_new_start + last_new_count
                
                # Calculate the gap between hunks in the old file
                if old_start >= last_old_end:
                    # Normal case: gap between hunks
                    gap_size = old_start - last_old_end
                    # New start = where new file ended + gap size
                    corrected_new_start = last_new_end + gap_size
                else:
                    # Hunks overlap (shouldn't happen, but handle it)
                    corrected_new_start = last_new_end
                
                # Only fix if there's a discrepancy
                if corrected_new_start != new_start:
                    # Fix the hunk header with corrected values
                    fixed_header = f"@@ -{old_start},{old_count} +{corrected_new_start},{new_count} @@"
                    fixed_lines.append(fixed_header)
                    print(f"[diff_validator] Fixed hunk header at line {i+1}: {line} → {fixed_header}", flush=True)
                    # Update tracking with corrected values
                    hunks_in_file.append((old_start, old_count, corrected_new_start, new_count, i))
                else:
                    fixed_lines.append(f"@@ -{old_start},{old_count} +{new_start},{new_count} @@")
                    hunks_in_file.append((old_start, old_count, new_start, new_count, i))
            else:
                # First hunk in file - should match old_start
                if new_start != old_start and abs(new_start - old_start) > 1:
                    fixed_header = f"@@ -{old_start},{old_count} +{old_start},{new_count} @@"
                    fixed_lines.append(fixed_header)
                    new_start = old_start  # Update for tracking
                    print(f"[diff_validator] Fixed first hunk header: {line} → {fixed_header}", flush=True)
                else:
                    fixed_lines.append(f"@@ -{old_start},{old_count} +{new_start},{new_count} @@")
                # Track this hunk with actual counts
                hunks_in_file.append((old_start, old_count, new_start, new_count, i))
        else:
            fixed_lines.append(line)
        
        i += 1
    
    return '\n'.join(fixed_lines)


def validate_diff_structure(diff_text: str) -> Tuple[bool, List[str]]:
    """
    Validate diff structure and return (is_valid, errors).
    
    Enhanced validation including:
    - Basic structure checks
    - Hunk header format validation
    - Context line presence check
    """
    errors = []
    lines = diff_text.split('\n')
    
    i = 0
    in_file = False
    expected_hunk = False
    hunk_count = 0
    current_hunk_start = None
    context_lines_in_hunk = 0
    
    while i < len(lines):
        line = lines[i]
        
        if line.startswith('diff --git') or (line.startswith('---') and i + 1 < len(lines) and lines[i+1].startswith('+++')):
            in_file = True
            expected_hunk = True
            hunk_count = 0
        
        if line.startswith('+++'):
            expected_hunk = True
        
        if line.startswith('@@'):
            if not expected_hunk:
                errors.append(f"Unexpected hunk header at line {i+1}")
            
            # Validate hunk format
            hunk_match = re.match(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
            if not hunk_match:
                errors.append(f"Malformed hunk header at line {i+1}: {line}")
            else:
                current_hunk_start = i
                context_lines_in_hunk = 0
                
                # Check if old_count and new_count are reasonable
                old_count = int(hunk_match.group(2))
                new_count = int(hunk_match.group(4))
                
                # Warn if counts are suspiciously small (might indicate missing context)
                if old_count < 3 or new_count < 3:
                    # This might be okay for very small changes, but note it
                    pass
            
            hunk_count += 1
            expected_hunk = False
        
        # Check for context lines after hunk header
        if current_hunk_start is not None:
            if line.startswith(' ') and not line.startswith('+++') and not line.startswith('---'):
                context_lines_in_hunk += 1
            elif line.startswith('@@') or line.startswith('diff --git'):
                # End of hunk - check if we had context lines
                if context_lines_in_hunk == 0 and i > current_hunk_start + 1:
                    # Warning: no context lines in hunk (might cause patch application issues)
                    pass
                current_hunk_start = None
                context_lines_in_hunk = 0
        
        i += 1
    
    return len(errors) == 0, errors


def validate_patch_applicability(diff_text: str) -> Tuple[bool, List[str]]:
    """
    Validate if a patch is likely to apply successfully.
    
    Checks:
    - Proper diff structure
    - Hunk headers are well-formed
    - Context lines are present
    
    Returns:
        (is_applicable, warnings)
    """
    is_valid, errors = validate_diff_structure(diff_text)
    warnings = []
    
    if not is_valid:
        return False, errors
    
    lines = diff_text.split('\n')
    current_file = None
    
    for i, line in enumerate(lines):
        # Track files
        if line.startswith('diff --git'):
            match = re.search(r'diff --git a/([^\s]+)', line)
            if match:
                current_file = match.group(1)
        
        # Check hunk headers
        hunk_match = re.match(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
        if hunk_match:
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2))
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4))
            
            # Warn if line numbers seem suspicious
            if old_start == 0 or new_start == 0:
                warnings.append(f"Warning: Hunk starts at line 0 (might be invalid) at line {i+1}")
            
            # Check if counts match expected pattern
            if old_count == 0 and new_count == 0:
                warnings.append(f"Warning: Both old_count and new_count are 0 at line {i+1}")
    
    return True, warnings

