#!/usr/bin/env python3
"""
P0.7 Module Tests: MalformedPatternLearner and Context-Aware Generation

Tests for the new P0.7 features:
1. MalformedPatternLearner - learns from failures and generates education prompts
2. Context-Aware Prompts - instance-specific guidance
3. Real-time Validation - validates and corrects diffs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from bench_agent.protocol.pre_apply_normalization import (
    MalformedPatternLearner,
    PreApplyNormalizationGate
)


def test_malformed_pattern_learner():
    """Test MalformedPatternLearner functionality."""
    print("=" * 60)
    print("Testing MalformedPatternLearner")
    print("=" * 60)

    learner = MalformedPatternLearner()

    # Test learning from failures
    malformed_patch = '''diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,10 @@
 def test_example():
     lines = [
=======
     "data"
     ]
'''

    # Learn from separator pattern failure
    learner.learn_from_failure(malformed_patch, 7, "Malformed patch at line 7: =======")

    # Learn from another failure
    learner.learn_from_failure(malformed_patch, 8, "Malformed patch at line 8: data")

    # Check learned patterns
    stats = learner.get_pattern_statistics()
    print(f"✓ Learned {stats['total_patterns']} patterns from {stats['total_failures']} failures")

    # Test education prompt generation
    education_prompt = learner.get_education_prompt(max_patterns=3)
    print("✓ Generated education prompt:")
    print(education_prompt[:200] + "..." if len(education_prompt) > 200 else education_prompt)

    assert stats['total_patterns'] > 0, "Should have learned patterns"
    assert education_prompt, "Should generate education prompt"
    print("✓ MalformedPatternLearner tests passed\n")


def test_context_aware_prompts():
    """Test context-aware prompt generation."""
    print("=" * 60)
    print("Testing Context-Aware Prompts")
    print("=" * 60)

    # Test astropy-14182 specific prompt
    reference_patch = "dummy reference patch"
    gate_14182 = PreApplyNormalizationGate(reference_patch, instance_id="astropy__astropy-14182")

    prompt_14182 = gate_14182.get_context_aware_prompt()
    print("✓ Generated astropy-14182 specific prompt:")
    print(prompt_14182[:300] + "..." if len(prompt_14182) > 300 else prompt_14182)

    assert "astropy-14182" in prompt_14182, "Should contain astropy-14182 specific guidance"
    assert "test_rst_with_header_rows" in prompt_14182, "Should mention test function"

    # Test general instance
    gate_general = PreApplyNormalizationGate(reference_patch, instance_id="general-instance")
    prompt_general = gate_general.get_context_aware_prompt()

    assert "GENERAL MALFORMED PATCH AVOIDANCE" in prompt_general, "Should contain general guidance"
    print("✓ Context-aware prompts tests passed\n")


def test_real_time_validation():
    """Test real-time validation and correction."""
    print("=" * 60)
    print("Testing Real-time Validation")
    print("=" * 60)

    gate = PreApplyNormalizationGate("dummy reference")

    # Test valid diff
    valid_diff = '''diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,6 @@
 def test():
+    x = 1
+    y = 2
'''

    result, regenerated, messages = gate.validate_and_correct_diff(valid_diff)
    print("✓ Valid diff validation result:", "PASS" if result == valid_diff and not regenerated else "FAIL")
    assert result == valid_diff, "Valid diff should remain unchanged"
    assert not regenerated, "Valid diff should not trigger regeneration"

    # Test malformed diff
    malformed_diff = '''diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,6 @@
 def test():
     x = 1
y = 2
'''

    result, regenerated, messages = gate.validate_and_correct_diff(malformed_diff)
    print("✓ Malformed diff corrected:", "YES" if result != malformed_diff else "NO")
    print("✓ Messages:", messages[:2] if messages else "None")

    # Should detect malformed pattern
    assert len(messages) > 0, "Should detect malformed patterns"
    print("✓ Real-time validation tests passed\n")


def test_pattern_extraction():
    """Test pattern extraction from various malformed cases."""
    print("=" * 60)
    print("Testing Pattern Extraction")
    print("=" * 60)

    learner = MalformedPatternLearner()

    # Test cases
    test_cases = [
        ("=======", 7, "separator_line_without_prefix"),
        ("{", 8, "bracket_without_prefix"),
        ('x = "hello"', 7, "variable_assignment_without_prefix"),
    ]

    patch_template = '''diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,10 @@
 def test():
     lines = [
{error_line}
     ]
'''

    for error_content, error_line, expected_pattern in test_cases:
        patch = patch_template.replace("{error_line}", error_content)
        extracted = learner._extract_pattern_around_line(patch, error_line)

        print(f"✓ '{error_content}' -> '{extracted}' (expected: '{expected_pattern}')")
        assert extracted == expected_pattern, f"Expected {expected_pattern}, got {extracted}"

    print("✓ Pattern extraction tests passed\n")


def run_all_tests():
    """Run all P0.7 tests."""
    print("🚀 Starting P0.7 Module Tests")
    print("=" * 80)

    try:
        test_malformed_pattern_learner()
        test_context_aware_prompts()
        test_real_time_validation()
        test_pattern_extraction()

        print("=" * 80)
        print("🎉 ALL P0.7 TESTS PASSED!")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
