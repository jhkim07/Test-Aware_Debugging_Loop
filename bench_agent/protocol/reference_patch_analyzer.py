"""
Extract key information from Reference Solution Patch for better guidance.
"""
import re
from typing import Dict, List, Tuple, Optional


def extract_file_paths_from_patch(patch_text: str) -> List[str]:
    """
    Extract file paths modified in the patch.
    
    Returns:
        List of file paths (e.g., ['astropy/io/ascii/rst.py'])
    """
    file_paths = []
    for line in patch_text.split('\n'):
        if line.startswith('diff --git'):
            # Format: diff --git a/path/to/file.py b/path/to/file.py
            match = re.search(r'diff --git a/([^\s]+)', line)
            if match:
                file_paths.append(match.group(1))
    return file_paths


def extract_hunk_headers_from_patch(patch_text: str) -> Dict[str, List[Dict]]:
    """
    Extract hunk headers for each file in the patch.
    
    Returns:
        Dictionary mapping file path to list of hunk info:
        {
            'file.py': [
                {'old_start': 27, 'old_count': 7, 'new_start': 27, 'new_count': 6, 'line_num': 45},
                ...
            ]
        }
    """
    result = {}
    lines = patch_text.split('\n')
    current_file = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Track current file
        if line.startswith('diff --git'):
            match = re.search(r'diff --git a/([^\s]+)', line)
            if match:
                current_file = match.group(1)
                result[current_file] = []
        
        # Extract hunk header
        hunk_match = re.match(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
        if hunk_match and current_file:
            hunk_info = {
                'old_start': int(hunk_match.group(1)),
                'old_count': int(hunk_match.group(2)),
                'new_start': int(hunk_match.group(3)),
                'new_count': int(hunk_match.group(4)),
                'line_num': i + 1,  # Line number in patch (1-indexed)
            }
            result[current_file].append(hunk_info)
        
        i += 1
    
    return result


def extract_context_lines_from_patch(patch_text: str, file_path: str, line_start: int, context_size: int = 15) -> Optional[str]:
    """
    Extract context lines around a specific line number from the patch.
    
    Args:
        patch_text: Full patch text
        file_path: File path to extract context for
        line_start: Starting line number in the original file
        context_size: Number of lines of context to extract (before and after)
    
    Returns:
        Context lines as string, or None if not found
    """
    lines = patch_text.split('\n')
    current_file = None
    in_target_file = False
    context_lines = []
    current_line_in_file = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Track current file
        if line.startswith('diff --git'):
            match = re.search(r'diff --git a/([^\s]+)', line)
            if match:
                current_file = match.group(1)
                in_target_file = (current_file == file_path)
                current_line_in_file = 0
                context_lines = []
        
        if in_target_file:
            # Track hunk headers
            hunk_match = re.match(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
            if hunk_match:
                current_line_in_file = int(hunk_match.group(1)) - 1  # -1 because we start counting from 0
            
            # Collect context lines near target
            if (not line.startswith('diff --git') and 
                not line.startswith('---') and 
                not line.startswith('+++') and
                not line.startswith('@@')):
                
                # Check if this line is in the target range
                if line_start - context_size <= current_line_in_file <= line_start + context_size:
                    # Remove diff markers for context
                    clean_line = line[1:] if line.startswith(('+', '-', ' ')) else line
                    context_lines.append(clean_line)
                
                # Only increment for context lines (lines starting with space or -)
                if line.startswith((' ', '-')):
                    current_line_in_file += 1
        
        i += 1
    
    if context_lines:
        return '\n'.join(context_lines)
    return None


def analyze_reference_patch(patch_text: str) -> Dict:
    """
    Analyze reference patch and extract key information for guidance.
    
    Returns:
        Dictionary with analysis results:
        {
            'file_paths': [...],
            'hunk_info': {...},
            'summary': "...",
        }
    """
    file_paths = extract_file_paths_from_patch(patch_text)
    hunk_info = extract_hunk_headers_from_patch(patch_text)
    
    summary_parts = []
    summary_parts.append(f"Reference patch modifies {len(file_paths)} file(s):")
    for file_path in file_paths:
        hunks = hunk_info.get(file_path, [])
        summary_parts.append(f"\n  {file_path}:")
        for hunk in hunks:
            summary_parts.append(
                f"    Line {hunk['old_start']}: @@ -{hunk['old_start']},{hunk['old_count']} "
                f"+{hunk['new_start']},{hunk['new_count']} @@"
            )
    
    return {
        'file_paths': file_paths,
        'hunk_info': hunk_info,
        'summary': '\n'.join(summary_parts),
    }


