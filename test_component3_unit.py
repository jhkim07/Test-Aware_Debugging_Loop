"""
Component 3 Unit Tests

Verifies Edit Script workflow without requiring SWE-bench environment.
"""

import json
from bench_agent.editor import (
    extract_anchor_candidates,
    apply_edit_script,
    validate_edit_script,
    generate_unified_diff,
    format_validation_result,
)


def test_anchor_extraction():
    """Test 1: Verify anchor extraction works."""
    print("\n" + "="*80)
    print("TEST 1: Anchor Extraction")
    print("="*80)

    source_code = """
import pytest

def test_basic():
    assert 1 + 1 == 2

def test_edge_case():
    assert 0 == 0

class TestFoo:
    def test_method(self):
        pass
"""

    candidates = extract_anchor_candidates(source_code)

    print(f"\n✓ Extracted {len(candidates['function_definitions'])} function definitions")
    print(f"✓ Extracted {len(candidates['class_definitions'])} class definitions")
    print(f"✓ Extracted {len(candidates['import_statements'])} import statements")
    print(f"✓ Extracted {len(candidates['line_patterns'])} line patterns")

    # Verify we got expected anchors
    func_names = [c.name for c in candidates['function_definitions']]
    assert 'test_basic' in func_names, "Should find test_basic"
    assert 'test_edge_case' in func_names, "Should find test_edge_case"

    class_names = [c.name for c in candidates['class_definitions']]
    assert 'TestFoo' in class_names, "Should find TestFoo"

    print("\n✅ TEST 1 PASSED: Anchor extraction works correctly")
    return True


def test_edit_application():
    """Test 2: Verify edit script application works."""
    print("\n" + "="*80)
    print("TEST 2: Edit Script Application")
    print("="*80)

    source_code = """
def test_basic():
    assert 1 + 1 == 2
"""

    # Edit script: Insert new test after test_basic
    edit_script = {
        "file": "test_file.py",
        "edits": [
            {
                "type": "insert_after",
                "anchor": {
                    "type": "function_def",
                    "selected": "def test_basic():"
                },
                "content": "\ndef test_new():\n    assert 2 + 2 == 4\n",
                "description": "Add new test case"
            }
        ]
    }

    # Apply edit script
    result = apply_edit_script(source_code, edit_script)

    print(f"\n✓ Edit application success: {result.success}")
    print(f"✓ Edits applied: {result.applied_count}")
    print(f"✓ Edits skipped: {result.skipped_count}")
    print(f"✓ Errors: {len(result.errors)}")

    assert result.success, "Edit should succeed"
    assert result.applied_count == 1, "Should apply 1 edit"
    assert "test_new" in result.modified_code, "Modified code should contain new test"

    print("\nModified code preview:")
    print("-" * 40)
    print(result.modified_code[:200])
    print("-" * 40)

    print("\n✅ TEST 2 PASSED: Edit script application works correctly")
    return True


def test_validation():
    """Test 3: Verify edit script validation works."""
    print("\n" + "="*80)
    print("TEST 3: Edit Script Validation")
    print("="*80)

    source_code = """
def test_basic():
    assert 1 + 1 == 2
"""

    # Valid edit script
    valid_script = {
        "file": "test_file.py",
        "edits": [
            {
                "type": "insert_after",
                "anchor": {
                    "type": "function_def",
                    "selected": "def test_basic():"
                },
                "content": "\ndef test_new():\n    pass\n",
                "description": "Add test"
            }
        ]
    }

    # Invalid edit script (hallucinated anchor)
    invalid_script = {
        "file": "test_file.py",
        "edits": [
            {
                "type": "insert_after",
                "anchor": {
                    "type": "function_def",
                    "selected": "def test_nonexistent():"  # Doesn't exist!
                },
                "content": "\ndef test_new():\n    pass\n",
                "description": "Add test"
            }
        ]
    }

    # Test valid script
    validation_valid = validate_edit_script(source_code, valid_script)
    print(f"\n✓ Valid script - is_valid: {validation_valid.is_valid}")
    print(f"✓ Valid script - errors: {len(validation_valid.errors)}")

    assert validation_valid.is_valid, "Valid script should pass validation"

    # Test invalid script
    validation_invalid = validate_edit_script(source_code, invalid_script)
    print(f"\n✓ Invalid script - is_valid: {validation_invalid.is_valid}")
    print(f"✓ Invalid script - errors: {len(validation_invalid.errors)}")

    assert not validation_invalid.is_valid, "Invalid script should fail validation"
    assert len(validation_invalid.errors) > 0, "Should have validation errors"

    print("\nValidation errors for invalid script:")
    print(format_validation_result(validation_invalid))

    print("\n✅ TEST 3 PASSED: Validation works correctly")
    return True


def test_diff_generation():
    """Test 4: Verify diff generation works."""
    print("\n" + "="*80)
    print("TEST 4: Unified Diff Generation")
    print("="*80)

    original = """
def test_basic():
    assert 1 + 1 == 2
"""

    modified = """
def test_basic():
    assert 1 + 1 == 2

def test_new():
    assert 2 + 2 == 4
"""

    # Generate diff
    diff = generate_unified_diff(original, modified, "test_file.py")

    print(f"\n✓ Generated diff length: {len(diff)} bytes")
    print(f"✓ Diff is not empty: {len(diff) > 0}")

    # Verify diff format
    assert "---" in diff, "Should have from-file header"
    assert "+++" in diff, "Should have to-file header"
    assert "@@" in diff, "Should have hunk header"
    assert "+def test_new():" in diff, "Should show added function"

    print("\nGenerated diff:")
    print("-" * 40)
    print(diff)
    print("-" * 40)

    print("\n✅ TEST 4 PASSED: Diff generation works correctly")
    return True


def test_end_to_end_workflow():
    """Test 5: End-to-end workflow (without LLM)."""
    print("\n" + "="*80)
    print("TEST 5: End-to-End Workflow")
    print("="*80)

    source_code = """
import pytest

def test_basic():
    assert 1 + 1 == 2
"""

    # Step 1: Extract anchors
    print("\nStep 1: Extract anchor candidates")
    candidates = extract_anchor_candidates(source_code)
    print(f"✓ Found {len(candidates['function_definitions'])} function anchors")

    # Step 2: Create edit script (simulating LLM output)
    print("\nStep 2: Create edit script (simulating LLM)")
    edit_script = {
        "file": "test_file.py",
        "edits": [
            {
                "type": "insert_after",
                "anchor": {
                    "type": "function_def",
                    "selected": "def test_basic():"
                },
                "content": "\ndef test_edge_case():\n    assert 0 == 0\n",
                "description": "Add edge case test"
            }
        ]
    }
    print("✓ Edit script created")

    # Step 3: Validate edit script
    print("\nStep 3: Validate edit script")
    validation = validate_edit_script(source_code, edit_script)
    print(f"✓ Validation result: {validation.is_valid}")
    assert validation.is_valid, "Edit script should be valid"

    # Step 4: Apply edits
    print("\nStep 4: Apply edit script")
    result = apply_edit_script(source_code, edit_script)
    print(f"✓ Application result: {result.success}")
    print(f"✓ Edits applied: {result.applied_count}")
    assert result.success, "Edit application should succeed"

    # Step 5: Generate diff
    print("\nStep 5: Generate unified diff")
    diff = generate_unified_diff(source_code, result.modified_code, "test_file.py")
    print(f"✓ Diff generated: {len(diff)} bytes")
    assert len(diff) > 0, "Diff should not be empty"

    print("\nFinal diff:")
    print("-" * 40)
    print(diff)
    print("-" * 40)

    print("\n✅ TEST 5 PASSED: End-to-end workflow works correctly")
    return True


def main():
    """Run all Component 3 unit tests."""
    print("\n" + "="*80)
    print("COMPONENT 3 UNIT TESTS")
    print("="*80)
    print("\nTesting Edit Script workflow without SWE-bench environment")

    tests = [
        test_anchor_extraction,
        test_edit_application,
        test_validation,
        test_diff_generation,
        test_end_to_end_workflow,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test.__name__}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nComponent 3 core functionality verified:")
        print("  ✓ Anchor extraction (AST-based)")
        print("  ✓ Edit script application (deterministic)")
        print("  ✓ Edit script validation (anti-hallucination)")
        print("  ✓ Diff generation (difflib, always valid)")
        print("  ✓ End-to-end workflow")
        print("\nComponent 3 is ready for integration testing with LLM.")
        return 0
    else:
        print(f"\n❌ {total - passed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
