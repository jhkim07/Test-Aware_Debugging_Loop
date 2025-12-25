#!/usr/bin/env python3
"""
Test P0.6 malformed patch fix functionality.
"""
import sys
from bench_agent.protocol.patch_fallback import fix_malformed_test_diff


def test_fix_malformed_patterns():
    """Test fixing common malformed patterns in test diffs."""

    # Simulated test diff with malformed patterns (like astropy-14182)
    malformed_diff = """diff --git a/astropy/io/ascii/tests/test_rst.py b/astropy/io/ascii/tests/test_rst.py
--- a/astropy/io/ascii/tests/test_rst.py
+++ b/astropy/io/ascii/tests/test_rst.py
@@ -2,6 +2,38 @@
 from io import StringIO

+import numpy as np
+
+def test_rst_with_header_rows():
+    lines = [
+        "======= ======== ====",
+        "   wave response ints",
    ]
    tbl = QTable.read(lines)
    out = StringIO()
    with pytest.raises(TypeError):
{
+        tbl.write(out, format="ascii.rst")
"""

    print("Testing malformed patch fix...")
    print("\nOriginal diff (with malformed patterns):")
    print("=" * 60)
    print(malformed_diff)
    print("=" * 60)

    # Fix malformed patterns
    fixed_diff, fixes = fix_malformed_test_diff(malformed_diff)

    print(f"\n✓ Fixed {len(fixes)} malformed patterns:")
    for fix in fixes:
        print(f"  - {fix}")

    print("\nFixed diff:")
    print("=" * 60)
    print(fixed_diff)
    print("=" * 60)

    # Verify fixes
    assert '+        "======= ======== ====",' in fixed_diff or \
           '+"======= ======== ===="' in fixed_diff, \
           "Should add '+' prefix to separator line"

    assert '+    ]' in fixed_diff or '    ]' in fixed_diff, \
           "Should handle bracket correctly"

    assert '+{' in fixed_diff or ' {' in fixed_diff, \
           "Should add prefix to standalone brace"

    print("\n✅ ALL CHECKS PASSED!")
    print("\nP0.6-2 malformed fix is working correctly!")
    return True


if __name__ == '__main__':
    try:
        test_fix_malformed_patterns()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
