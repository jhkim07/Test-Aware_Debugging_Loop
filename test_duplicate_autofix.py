#!/usr/bin/env python3
"""
Quick test for duplicate code auto-fix functionality
"""

import sys
sys.path.insert(0, '/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop')

from bench_agent.editor.edit_validator import auto_fix_duplicate_code, validate_no_duplicate_code

# Test case: LLM uses insert_before when it should use replace
source_code = """def test_function():
    x = 10
    y = 20
    return x + y
"""

# Bad edit script: tries to insert code that already exists
# NOTE: Using REAL LLM format with dict anchor (not string)
bad_edit_script = {
    "file": "test.py",
    "edits": [
        {
            "type": "insert_before",
            "anchor": {
                "selected": "return x + y",
                "type": "line_pattern"
            },
            "content": "    x = 10\n    y = 20",
            "description": "Add variable initialization (duplicate test)"
        }
    ]
}

print("=" * 80)
print("Testing Duplicate Code Auto-Fix")
print("=" * 80)
print()

print("Source Code:")
print(source_code)
print()

print("Bad Edit Script (insert when should be replace):")
import json
print(json.dumps(bad_edit_script, indent=2))
print()

# Check for duplicates
print("Step 1: Check for duplicates...")
validation = validate_no_duplicate_code(source_code, bad_edit_script)
if validation.warnings:
    print(f"✓ Detected {len(validation.warnings)} duplicate warnings:")
    for w in validation.warnings:
        print(f"  - {w}")
else:
    print("✗ No duplicates detected (unexpected!)")
print()

# Auto-fix
print("Step 2: Apply auto-fix...")
fixed_script, fixes = auto_fix_duplicate_code(source_code, bad_edit_script)
if fixes:
    print(f"✓ Auto-fix successful! Applied {len(fixes)} fixes:")
    for fix in fixes:
        print(f"  ✓ {fix}")
    print()
    print("Fixed Edit Script:")
    print(json.dumps(fixed_script, indent=2))
else:
    print("✗ Auto-fix failed (no fixes applied)")
print()

# Verify fix
print("Step 3: Verify fixed script has no duplicates...")
validation2 = validate_no_duplicate_code(source_code, fixed_script)
if validation2.warnings:
    print(f"✗ Still has {len(validation2.warnings)} warnings:")
    for w in validation2.warnings:
        print(f"  - {w}")
else:
    print("✓ No duplicate warnings! Auto-fix successful!")
print()

print("=" * 80)
print("Test Complete")
print("=" * 80)
