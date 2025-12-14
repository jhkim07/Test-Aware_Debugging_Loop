"""
Extract and analyze error messages from patch application failures and test failures.
"""
import re
from typing import Dict, List, Optional, Tuple


def extract_patch_apply_errors(stdout: str, stderr: str) -> Dict:
    """
    Extract detailed error information from patch application failures.
    
    Returns:
        Dictionary with error details:
        {
            'failed': True/False,
            'error_type': 'malformed_patch' | 'hunk_failed' | 'file_not_found' | 'other',
            'error_message': "...",
            'failed_file': 'path/to/file.py',
            'failed_line': 123,
            'suggestions': [...],
        }
    """
    combined = stdout + "\n" + stderr
    errors = {
        'failed': False,
        'error_type': None,
        'error_message': '',
        'failed_file': None,
        'failed_line': None,
        'suggestions': [],
    }
    
    # Check for patch apply failure
    if 'Patch Apply Failed' in combined or 'malformed patch' in combined.lower():
        errors['failed'] = True
        
        # Extract malformed patch error
        malformed_match = re.search(r'malformed patch at line (\d+):\s*(.+)', combined, re.IGNORECASE)
        if malformed_match:
            errors['error_type'] = 'malformed_patch'
            errors['failed_line'] = int(malformed_match.group(1))
            errors['error_message'] = f"Malformed patch at line {malformed_match.group(1)}: {malformed_match.group(2)}"
            errors['suggestions'].append("Check for markdown code block markers (```) in the patch")
            errors['suggestions'].append("Verify hunk header format: @@ -old_start,old_count +new_start,new_count @@")
        
        # Extract hunk failure
        hunk_match = re.search(r'Hunk #(\d+) FAILED at (\d+)', combined, re.IGNORECASE)
        if hunk_match:
            errors['error_type'] = 'hunk_failed'
            errors['failed_line'] = int(hunk_match.group(2))
            errors['error_message'] = f"Hunk #{hunk_match.group(1)} failed at line {hunk_match.group(2)}"
            errors['suggestions'].append("Check if line numbers in hunk header match the actual file")
            errors['suggestions'].append("Verify context lines match the original file")
            errors['suggestions'].append("Ensure sufficient context lines (15-20 lines) around changes")
        
        # Extract file path from error
        file_match = re.search(r'patching file ([^\s]+)', combined, re.IGNORECASE)
        if file_match:
            errors['failed_file'] = file_match.group(1)
        
        # Extract file not found
        if 'No file to patch' in combined or 'file does not exist' in combined.lower():
            errors['error_type'] = 'file_not_found'
            errors['suggestions'].append("Verify the file path in the patch matches the repository structure")
    
    return errors


def extract_test_failure_errors(stdout: str, stderr: str) -> Dict:
    """
    Extract detailed error information from test failures.
    
    Returns:
        Dictionary with test failure details:
        {
            'failed_tests': [...],
            'error_messages': [...],
            'traceback': "...",
        }
    """
    combined = stdout + "\n" + stderr
    errors = {
        'failed_tests': [],
        'error_messages': [],
        'traceback': '',
    }
    
    # Extract failed test names
    failed_pattern = r'FAILED\s+([^\s]+::[^\s]+)'
    failed_matches = re.findall(failed_pattern, combined)
    errors['failed_tests'] = list(set(failed_matches))
    
    # Extract error messages
    error_pattern = r'(AssertionError|ValueError|TypeError|AttributeError):\s*(.+)'
    error_matches = re.findall(error_pattern, combined)
    errors['error_messages'] = [f"{e[0]}: {e[1][:200]}" for e in error_matches[:5]]
    
    # Extract traceback (last one)
    traceback_pattern = r'(Traceback \(most recent call last\):.*?)(?=\n\w|\n\n|$)'
    traceback_match = re.search(traceback_pattern, combined, re.DOTALL)
    if traceback_match:
        errors['traceback'] = traceback_match.group(1)[-1000:]  # Last 1000 chars
    
    return errors


def generate_error_feedback(patch_errors: Dict, test_errors: Dict, brs_failed: bool = False) -> str:
    """
    Generate human-readable feedback from errors for LLM.
    
    Args:
        patch_errors: Result from extract_patch_apply_errors
        test_errors: Result from extract_test_failure_errors
        brs_failed: Whether BRS check failed (tests passed on buggy code)
    
    Returns:
        Formatted feedback string
    """
    feedback_parts = []
    
    if patch_errors.get('failed'):
        feedback_parts.append("=" * 80)
        feedback_parts.append("PATCH APPLICATION FAILED")
        feedback_parts.append("=" * 80)
        feedback_parts.append(f"Error Type: {patch_errors.get('error_type', 'unknown')}")
        feedback_parts.append(f"Error Message: {patch_errors.get('error_message', 'Unknown error')}")
        if patch_errors.get('failed_file'):
            feedback_parts.append(f"Failed File: {patch_errors.get('failed_file')}")
        if patch_errors.get('failed_line'):
            feedback_parts.append(f"Failed Line: {patch_errors.get('failed_line')}")
        if patch_errors.get('suggestions'):
            feedback_parts.append("\nSuggestions:")
            for suggestion in patch_errors.get('suggestions', []):
                feedback_parts.append(f"  - {suggestion}")
    
    if test_errors.get('failed_tests'):
        feedback_parts.append("\n" + "=" * 80)
        feedback_parts.append("TEST FAILURES")
        feedback_parts.append("=" * 80)
        feedback_parts.append(f"Failed Tests: {', '.join(test_errors.get('failed_tests', [])[:5])}")
        if test_errors.get('error_messages'):
            feedback_parts.append("\nError Messages:")
            for msg in test_errors.get('error_messages', [])[:3]:
                feedback_parts.append(f"  - {msg}")
    
    if brs_failed:
        feedback_parts.append("\n" + "=" * 80)
        feedback_parts.append("BRS (BUG REPRODUCTION STRENGTH) FAILED")
        feedback_parts.append("=" * 80)
        feedback_parts.append("CRITICAL: Your tests PASSED on the buggy code, which means they do NOT reproduce the bug.")
        feedback_parts.append("Your tests MUST fail on buggy code to demonstrate they can detect the bug.")
        feedback_parts.append("\nTo fix this:")
        feedback_parts.append("1. Review the Problem Statement to understand what the bug actually does")
        feedback_parts.append("2. Check the Reference Test Patch to see how the bug should be reproduced")
        feedback_parts.append("3. Ensure your test's expected value is the CORRECT result (not the buggy result)")
        feedback_parts.append("4. Verify your test actually calls the buggy function with the scenario from Problem Statement")
    
    return "\n".join(feedback_parts) if feedback_parts else ""


