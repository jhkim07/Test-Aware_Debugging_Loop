"""
Utilities for cleaning and fixing diff formats from LLM outputs.
"""
import re
import json


def fix_diff_hunk_headers(text: str) -> str:
    """
    Fix malformed diff hunk headers like '@@ -52,7 +59' to '@@ -52,7 +59,17 @@'
    """
    lines = text.split('\n')
    fixed_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Match malformed hunk headers: @@ -old_start,old_count +new_start (missing new_count and @@)
        # Pattern: @@ -52,7 +59 (no new_count, no closing @@)
        match = re.match(r'^(@@ -\d+,\d+ \+\d+)(\s*)$', line)
        if match:
            # Count added/removed lines in this hunk until next @@ or diff --git
            hunk_lines = []
            j = i + 1
            added_count = 0
            
            while j < len(lines):
                next_line = lines[j]
                if next_line.startswith('@@') or next_line.startswith('diff --git'):
                    break
                hunk_lines.append(next_line)
                if next_line.startswith('+') and not next_line.startswith('+++'):
                    added_count += 1
                j += 1
            
            # Extract old_count from the hunk header
            old_match = re.search(r'-(\d+),(\d+)', match.group(1))
            if old_match:
                old_start = int(old_match.group(1))
                old_count = int(old_match.group(2))
                new_start_match = re.search(r'\+(\d+)', match.group(1))
                if new_start_match:
                    new_start = int(new_start_match.group(1))
                    # new_count should be added_count
                    new_count = max(added_count, old_count) if added_count > 0 else old_count
                    fixed_line = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
                    fixed_lines.append(fixed_line)
                    i += 1
                    continue
        
        fixed_lines.append(line)
        i += 1
    
    return '\n'.join(fixed_lines)


def extract_and_convert_ta_split_json(text: str) -> str:
    """
    Extract .ta_split.json content and convert it to unified diff format.
    """
    # Pattern to find .ta_split.json section
    # Look for patterns like "=== .ta_split.json ===" or similar markers
    json_pattern = r'===?\s*\.ta_split\.json\s*===?\s*\n(.*?)(?=\n\s*===?|\Z)'
    json_match = re.search(json_pattern, text, re.DOTALL)
    
    if not json_match:
        # Try without === markers - look for JSON after .ta_split.json line
        json_pattern2 = r'\.ta_split\.json[^\n]*\n\s*(\{.*?\})\s*$'
        json_match = re.search(json_pattern2, text, re.DOTALL)
        if json_match:
            json_pattern = json_pattern2
    
    if json_match:
        json_content = json_match.group(1).strip()
        
        # Try to parse JSON
        try:
            json_data = json.loads(json_content)
            
            # Remove the text format from original
            text = re.sub(json_pattern, '', text, flags=re.DOTALL).strip()
            
            # Convert to unified diff format
            json_lines = json.dumps(json_data, indent=4).split('\n')
            
            # Create unified diff for .ta_split.json
            diff_lines = [
                "diff --git a/.ta_split.json b/.ta_split.json",
                "index 0000000..1111111 100644",
                "--- a/.ta_split.json",
                "+++ b/.ta_split.json",
                f"@@ -0,0 +1,{len(json_lines)} @@",
            ]
            
            for line in json_lines:
                diff_lines.append(f"+{line}")
            
            # Append the .ta_split.json diff to the end
            text = text + "\n\n" + "\n".join(diff_lines)
        except json.JSONDecodeError:
            # If JSON is invalid, just remove the text format part
            text = re.sub(json_pattern, '', text, flags=re.DOTALL).strip()
    
    return text


def remove_excessive_empty_lines(text: str) -> str:
    """
    Remove excessive empty lines from diff, but preserve structure.
    Keep single empty line between diff sections, remove multiple consecutive empty lines.
    Also remove empty lines that appear between hunk headers and content.
    """
    lines = text.split('\n')
    cleaned = []
    prev_empty = False
    
    for i, line in enumerate(lines):
        is_empty = not line.strip()
        
        # If this is an empty line
        if is_empty:
            # Only add if previous line wasn't empty (keep single empty line)
            if not prev_empty:
                # Don't add empty line right after @@ hunk header
                if cleaned and cleaned[-1].startswith('@@'):
                    prev_empty = True
                    continue
                # Preserve empty line between diff sections (before "diff --git")
                # This is required for proper patch format
                if i + 1 < len(lines) and lines[i + 1].startswith('diff --git'):
                    cleaned.append('')
                    prev_empty = True
                    continue
                cleaned.append('')
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False
    
    return '\n'.join(cleaned)


def fix_orphaned_hunk_headers(text: str) -> str:
    """
    Fix hunk headers that appear in the middle of file content.
    Hunk headers should only appear:
    1. After '--- a/file' or '+++ b/file' lines (start of a diff section)
    2. Or after a previous hunk within the same file (context lines between hunks are OK)
    
    A hunk header in the middle of actual content (lines starting with +, -, or context)
    without proper preceding structure is invalid.
    """
    lines = text.split('\n')
    fixed = []
    i = 0
    in_diff_section = False
    last_file_header = None
    
    while i < len(lines):
        line = lines[i]
        
        # Track when we enter a diff section
        if line.startswith('diff --git') or line.startswith('---'):
            in_diff_section = True
            last_file_header = i
            fixed.append(line)
            i += 1
            continue
        
        # Track file path lines
        if line.startswith('+++'):
            fixed.append(line)
            i += 1
            continue
        
        # Check if this is a hunk header
        if line.startswith('@@') and '@@' in line[2:]:
            # Valid if:
            # 1. We're in a diff section and previous line is +++ (file path)
            # 2. Or previous line is a context/+/ line from previous hunk (same file)
            # 3. Or previous line is also a @@ (shouldn't happen, but handle it)
            
            is_valid = False
            if fixed:
                prev_line = fixed[-1].strip()
                # Valid if previous is +++ (file path)
                if prev_line.startswith('+++'):
                    is_valid = True
                # Valid if previous is context/+/ line (we're in same diff)
                elif in_diff_section and (prev_line.startswith('+') or prev_line.startswith('-') or 
                                          (prev_line and not prev_line.startswith('@@') and not prev_line.startswith('diff'))):
                    is_valid = True
            
            if is_valid:
                fixed.append(line)
            else:
                # Orphaned header - skip it
                # Don't add to output
                pass
        else:
            # Regular line - add it
            fixed.append(line)
            # If we see a line that's not part of diff structure, we might have left diff section
            if line.startswith('diff --git'):
                in_diff_section = True
        
        i += 1
    
    return '\n'.join(fixed)


def clean_markdown_markers(text: str) -> str:
    """
    Aggressively remove all markdown code block markers from diff text.
    Handles various patterns: ```, ```python, ```diff, etc.
    """
    if not text:
        return text
    
    # Remove markdown code block markers at the start
    # Patterns: ```, ```python, ```diff, ```python3, etc.
    text = re.sub(r'^```\w*\s*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*\n', '', text, flags=re.MULTILINE)
    
    # Remove markdown code block markers at the end
    text = re.sub(r'\n```\w*\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n```\s*$', '', text, flags=re.MULTILINE)
    
    # Remove any remaining markdown markers (including inline)
    text = re.sub(r'```\w*', '', text)
    text = re.sub(r'```', '', text)
    
    # Remove any standalone backticks that might be left
    text = re.sub(r'^`\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*`\s*$', '', text, flags=re.MULTILINE)
    
    return text


def remove_conftest_from_diff(text: str) -> str:
    """
    Remove all conftest.py related sections from the diff.
    This prevents patch application failures due to conftest.py conflicts.
    """
    if not text:
        return text
    
    lines = text.split('\n')
    filtered_lines = []
    skip_conftest_section = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts a conftest.py diff section
        if line.startswith('diff --git') and 'conftest.py' in line:
            skip_conftest_section = True
            i += 1
            continue
        
        # If we're in a conftest.py section, skip until next diff section
        if skip_conftest_section:
            if line.startswith('diff --git'):
                skip_conftest_section = False
                # Don't skip this line, process it
            else:
                i += 1
                continue
        
        # Check for conftest.py in file paths
        if line.startswith('---') and 'conftest.py' in line:
            skip_conftest_section = True
            i += 1
            continue
        
        if line.startswith('+++') and 'conftest.py' in line:
            skip_conftest_section = True
            i += 1
            continue
        
        # Add line if not in conftest.py section
        if not skip_conftest_section:
            filtered_lines.append(line)
        
        i += 1
    
    return '\n'.join(filtered_lines)


def clean_diff_format(text: str) -> str:
    """
    Clean and fix diff format issues in LLM output.
    Enhanced with stronger markdown marker removal and conftest.py filtering.
    """
    if not text:
        return text
    
    # Step 1: Aggressively remove markdown markers (ENHANCED)
    text = clean_markdown_markers(text)
    
    # Step 2: Remove conftest.py sections (NEW)
    text = remove_conftest_from_diff(text)
    
    # Step 3: Remove excessive empty lines
    text = remove_excessive_empty_lines(text)
    
    # Step 4: Fix orphaned hunk headers (headers in middle of content)
    text = fix_orphaned_hunk_headers(text)
    
    # Step 5: Fix hunk headers (missing new_count)
    text = fix_diff_hunk_headers(text)
    
    # Step 6: Fix multi-hunk line numbers (IMPORTANT: must be after hunk header fixes)
    try:
        from bench_agent.protocol.diff_validator import fix_multihunk_line_numbers
        text = fix_multihunk_line_numbers(text)
    except Exception as e:
        # If validator fails, continue without it
        import sys
        print(f"[diff_cleaner] Warning: Failed to fix multi-hunk line numbers: {e}", file=sys.stderr)
    
    # Step 7: Convert .ta_split.json to unified diff format
    text = extract_and_convert_ta_split_json(text)
    
    # Step 8: Final validation - check for remaining markdown markers
    if '```' in text:
        import sys
        print(f"[diff_cleaner] Warning: Markdown markers still present after cleaning", file=sys.stderr)
        # Try one more aggressive pass
        text = clean_markdown_markers(text)
    
    # Step 9: Auto-fix common patch errors
    text = auto_fix_common_patch_errors(text)
    
    return text.strip()


def auto_fix_common_patch_errors(text: str) -> str:
    """
    Automatically fix common patch errors that can be corrected programmatically.
    
    Fixes:
    - Missing new_count in hunk headers (already handled by fix_diff_hunk_headers)
    - Trailing whitespace in diff lines
    - Inconsistent line endings
    """
    if not text:
        return text
    
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Remove trailing whitespace (except for empty lines)
        if line.strip():
            line = line.rstrip()
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)
