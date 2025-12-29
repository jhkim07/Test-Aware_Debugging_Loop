#!/usr/bin/env python3
"""
Investigate Component 3 Anchor Selection Issue

This script reproduces the malformed diff issue by:
1. Loading the test file from astropy-12907
2. Extracting anchor candidates
3. Analyzing which anchors are selected
4. Showing why the wrong anchor is chosen
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bench_agent.editor import extract_anchor_candidates


# Test file content from astropy-12907 around line 136
TEST_FILE_CONTENT = '''
def test_separable():
    c1 = models.Linear1D(10) & models.Linear1D(5)
    c2 = models.Linear1D(10) | models.Linear1D(5)
    # ... more tests ...


def test_custom_model_separable():
    @custom_model
    def model_a(x):
        return x

    @custom_model
    def model_b(x):
        return x

    @custom_model
    def model_c(x):
        return x

    m1 = model_a | model_b
    # ... more code ...
'''


def main():
    print("=" * 80)
    print("Component 3 - Anchor Selection Investigation")
    print("=" * 80)
    print()

    # Extract anchors
    print("Extracting anchor candidates...")
    candidates = extract_anchor_candidates(TEST_FILE_CONTENT)

    print(f"Total candidates extracted: {len(candidates)}")
    print()

    # Show all candidates
    print("All Anchor Candidates:")
    print("-" * 80)
    for i, c in enumerate(candidates, 1):
        line_num = c.get('line_number', '?')
        anchor_type = c.get('type', '?')
        text = c.get('text', '?')[:60].replace('\n', '\\n')
        score = c.get('score', 0.0)

        print(f"{i:3}. Line {line_num:3} [{anchor_type:15}] Score: {score:.2f}")
        print(f"     Text: {text}")
        print()

    # Analyze the critical area (lines 6-20)
    print()
    print("=" * 80)
    print("Critical Area Analysis (lines 6-20)")
    print("=" * 80)
    print()

    critical_candidates = [c for c in candidates if 6 <= c.get('line_number', 0) <= 20]

    print(f"Found {len(critical_candidates)} candidates in critical area:")
    print()

    for c in critical_candidates:
        line_num = c['line_number']
        anchor_type = c['type']
        text = c['text'][:80].replace('\n', '\\n')
        score = c.get('score', 0.0)

        print(f"Line {line_num}: {anchor_type}")
        print(f"  Text: {text}")
        print(f"  Score: {score:.2f}")
        print()

    # Identify the issue
    print("=" * 80)
    print("ISSUE ANALYSIS")
    print("=" * 80)
    print()

    # Expected: Line 8 (def test_custom_model_separable) should have highest score
    # Actual: Line 9 (@custom_model) likely has higher score

    func_def = next((c for c in critical_candidates if 'def test_custom_model_separable' in c['text']), None)
    decorator = next((c for c in critical_candidates if '@custom_model' in c['text']), None)

    if func_def and decorator:
        func_score = func_def.get('score', 0.0)
        dec_score = decorator.get('score', 0.0)

        print(f"Function definition anchor (line {func_def['line_number']}):")
        print(f"  Text: {func_def['text'][:60]}")
        print(f"  Score: {func_score:.2f}")
        print()

        print(f"Decorator anchor (line {decorator['line_number']}):")
        print(f"  Text: {decorator['text'][:60]}")
        print(f"  Score: {dec_score:.2f}")
        print()

        if dec_score > func_score:
            print("❌ BUG CONFIRMED!")
            print(f"  Decorator score ({dec_score:.2f}) > Function def score ({func_score:.2f})")
            print(f"  LLM will select decorator as anchor")
            print(f"  Insertion will happen INSIDE function instead of BEFORE it")
        else:
            print("✅ Scoring looks correct")
            print(f"  Function def score ({func_score:.2f}) > Decorator score ({dec_score:.2f})")
    else:
        if not func_def:
            print("❌ Function definition NOT extracted as anchor!")
        if not decorator:
            print("ℹ️  Decorator not extracted as anchor")

    print()
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()

    if func_def and decorator and decorator.get('score', 0) > func_def.get('score', 0):
        print("FIX REQUIRED:")
        print("1. Increase score for function definitions (def, class)")
        print("2. Decrease score for decorators")
        print("3. Add 'depth' tracking to penalize nested statements")
        print()
        print("Expected result:")
        print(f"  Function def (line {func_def['line_number']}): score > 0.8")
        print(f"  Decorator (line {decorator['line_number']}): score < 0.5")
    else:
        print("Anchor scoring appears correct.")
        print("Issue may be in edit application or diff generation.")


if __name__ == '__main__':
    main()
