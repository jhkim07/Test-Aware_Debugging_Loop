"""
Extract key information from Reference Test Patch for better guidance.
"""
import re
from typing import Dict, List, Optional


def analyze_reference_test_patch(test_patch: str) -> Dict:
    """
    Analyze reference test patch and extract key information.

    P0-2 Enhancement: Extract expected values and assertions to enforce in test generation.

    Returns:
        Dictionary with analysis results:
        {
            'test_file': 'path/to/test_file.py',
            'test_functions': [...],
            'expected_values': {...},  # {var_name: value_str}
            'assertions': [...],  # List of assertion statements
            'structure_type': 'function' or 'dictionary',
            'summary': "...",
            'expected_value_hints': str,  # Formatted hints for LLM
        }
    """
    if not test_patch:
        return {}

    lines = test_patch.split('\n')
    test_file = None
    test_functions = []
    expected_values = {}
    assertions = []
    structure_type = None
    in_test_function = False
    current_function = None

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

        # P0-2: Enhanced expected value extraction
        # Pattern 1: variable_expected = value
        if re.search(r'^\+.*expected.*=', line, re.IGNORECASE):
            match = re.search(r'(\w+_expected\w*)\s*=\s*(.+)', line)
            if match:
                expected_name = match.group(1)
                expected_value = match.group(2).strip()
                expected_values[expected_name] = expected_value

        # Pattern 2: Literal values in assertions
        # assert result == 123, assert foo == "bar", assert x == [1, 2, 3]
        if in_test_function and re.search(r'^\+.*assert.*==', line):
            assertions.append(line.strip())
            # Try to extract the expected value (right side of ==)
            match = re.search(r'assert\s+.*==\s+(.+?)(?:\s*#|$)', line)
            if match:
                expected_literal = match.group(1).strip()
                # If it's a literal (number, string, list, etc), save it
                if re.match(r'^[\d\[\]\"\'\{\}\-\+\.eE,\s]+$', expected_literal):
                    expected_values[f"literal_in_assertion_{len(expected_values)}"] = expected_literal

        i += 1

    # P0-2: Create formatted hints for LLM
    expected_value_hints = ""
    if expected_values:
        expected_value_hints = "CRITICAL - Use these expected values from reference test:\n"
        for var_name, value in expected_values.items():
            expected_value_hints += f"  {var_name} = {value}\n"
        expected_value_hints += "\nYou MUST use these exact expected values to ensure bug reproduction."

    if assertions:
        expected_value_hints += "\n\nReference assertions:\n"
        for assertion in assertions[:5]:  # Limit to 5 examples
            expected_value_hints += f"  {assertion}\n"

    summary_parts = []
    if test_file:
        summary_parts.append(f"Reference test patch modifies: {test_file}")
    if structure_type:
        summary_parts.append(f"Structure type: {structure_type}")
    if test_functions:
        summary_parts.append(f"Test functions: {', '.join(test_functions)}")
    if expected_values:
        summary_parts.append(f"Expected values found: {len(expected_values)} value(s)")

    return {
        'test_file': test_file,
        'test_functions': test_functions,
        'expected_values': expected_values,
        'assertions': assertions,
        'structure_type': structure_type,
        'summary': '\n'.join(summary_parts) if summary_parts else "No test structure detected",
        'expected_value_hints': expected_value_hints,
    }


