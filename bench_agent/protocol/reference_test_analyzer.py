"""
Extract key information from Reference Test Patch for better guidance.
"""
import re
from typing import Dict, List, Optional


def analyze_reference_test_patch(test_patch: str) -> Dict:
    """
    Analyze reference test patch and extract key information.
    
    Returns:
        Dictionary with analysis results:
        {
            'test_file': 'path/to/test_file.py',
            'test_functions': [...],
            'expected_values': {...},
            'structure_type': 'function' or 'dictionary',
            'summary': "...",
        }
    """
    if not test_patch:
        return {}
    
    lines = test_patch.split('\n')
    test_file = None
    test_functions = []
    expected_values = {}
    structure_type = None
    in_test_function = False
    current_function = None
    current_expected = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Extract test file path
        if line.startswith('diff --git'):
            match = re.search(r'diff --git a/([^\s]+)', line)
            if match:
                test_file = match.group(1)
        
        # Detect test function
        if re.match(r'^\+def test_', line):
            match = re.search(r'def (test_\w+)', line)
            if match:
                test_functions.append(match.group(1))
                structure_type = 'function'
                in_test_function = True
                current_function = match.group(1)
        
        # Detect dictionary structure (e.g., compound_models['key'] = ...)
        if re.search(r"^\+.*\[['\"].*['\"]\]\s*=", line) or re.search(r"^\+.*\{.*\}", line):
            if structure_type is None:
                structure_type = 'dictionary'
        
        # Detect expected value definitions
        if re.search(r'^\+.*expected.*=', line, re.IGNORECASE):
            match = re.search(r'(\w+_expected\w*)\s*=', line)
            if match:
                expected_name = match.group(1)
                expected_values[expected_name] = line.strip()
        
        # Detect assert statements with expected values
        if in_test_function and re.search(r'assert.*==', line):
            match = re.search(r'assert\s+.*==\s+(\w+)', line)
            if match:
                var_name = match.group(1)
                if 'expected' in var_name.lower():
                    expected_values[var_name] = f"Used in {current_function}"
        
        i += 1
    
    summary_parts = []
    if test_file:
        summary_parts.append(f"Reference test patch modifies: {test_file}")
    if structure_type:
        summary_parts.append(f"Structure type: {structure_type}")
    if test_functions:
        summary_parts.append(f"Test functions: {', '.join(test_functions)}")
    if expected_values:
        summary_parts.append(f"Expected values found: {', '.join(expected_values.keys())}")
    
    return {
        'test_file': test_file,
        'test_functions': test_functions,
        'expected_values': expected_values,
        'structure_type': structure_type,
        'summary': '\n'.join(summary_parts) if summary_parts else "No test structure detected",
    }


