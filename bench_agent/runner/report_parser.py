"""
Parse SWE-bench harness reports to extract test results.
"""
import json
import re
from pathlib import Path
from typing import Optional


def check_patch_apply_failed(stdout: str, stderr: str) -> bool:
    """
    Check if patch application failed by looking for error messages.

    P0-1 Enhancement: More accurate detection of patch apply failures
    including "Hunk #N FAILED" pattern from astropy__astropy-14182 logs.

    Args:
        stdout: Harness stdout text
        stderr: Harness stderr text

    Returns:
        True if patch application failed, False otherwise
    """
    combined = (stdout or "") + "\n" + (stderr or "")

    # Definite failure indicators (high confidence)
    definite_failures = [
        "Patch Apply Failed",
        "malformed patch",
        "patch: ****",
        "Failed to apply patch",
        r"Hunk #\d+ FAILED",  # regex pattern for hunk failures
        "patch does not apply",
        "can't find file to patch",
        "No such file or directory",
    ]

    # Check definite failures
    for indicator in definite_failures:
        if indicator.startswith(r'Hunk'):
            # Use regex for hunk failure pattern
            if re.search(indicator, combined, re.IGNORECASE):
                return True
        elif indicator in combined:
            return True

    # Check for "patching file" followed by "FAILED" within next few lines
    # This catches cases where patch starts but fails mid-way
    if "patching file" in combined and "FAILED" in combined:
        # More sophisticated check: look for FAILED within 100 chars of "patching file"
        patch_positions = [m.start() for m in re.finditer(r'patching file', combined)]
        for pos in patch_positions:
            nearby_text = combined[pos:pos+200]
            if "FAILED" in nearby_text:
                return True

    return False


def parse_harness_report(report_dir: Path, instance_id: str, debug: bool = False) -> dict:
    """
    Parse SWE-bench harness report to extract test results.
    
    Args:
        report_dir: Directory containing report files
        instance_id: Instance ID to search for
        debug: Enable debug output
    
    Returns:
        dict with keys:
        - passed: number of passed tests
        - failed: number of failed tests
        - total: total number of tests
        - pass_rate: pass rate (0.0 to 1.0)
        - ok: bool indicating if all tests passed
    """
    result = {
        "passed": 0,
        "failed": 0,
        "total": 0,
        "pass_rate": 0.0,
        "ok": False,
    }
    
    if not report_dir.exists():
        if debug:
            print(f"Report directory does not exist: {report_dir}")
        return result
    
    # Look for common report file patterns (more comprehensive)
    patterns = [
        "**/*results*.json",
        "**/*report*.json",
        "**/*.json",
        "**/*log*.txt",
        "**/*.txt",
        "**/stdout.txt",
        "**/stderr.txt",
        f"**/*{instance_id}*.json",
        f"**/*{instance_id}*.txt",
    ]
    
    all_files = []
    for pattern in patterns:
        all_files.extend(report_dir.glob(pattern))
    
    # Remove duplicates
    report_files = list(set([f for f in all_files if f.is_file()]))
    
    if debug:
        print(f"Found {len(report_files)} files in {report_dir}")
        for f in report_files[:10]:  # Print first 10
            print(f"  - {f}")
    
    for report_file in report_files:
        if report_file.stat().st_size > 10_000_000:  # Skip huge files
            continue
        
        try:
            content = report_file.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue
            
            # Try JSON parsing first
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    # Pattern 1: Direct result fields
                    if "passed" in data and "failed" in data:
                        result["passed"] = int(data.get("passed", 0))
                        result["failed"] = int(data.get("failed", 0))
                        result["total"] = result["passed"] + result["failed"]
                        if result["total"] > 0:
                            result["pass_rate"] = result["passed"] / result["total"]
                        result["ok"] = result["failed"] == 0
                        if debug:
                            print(f"Found results in {report_file.name}: {result}")
                        return result
                    
                    # Pattern 2: Instance-specific results
                    if instance_id in data:
                        inst_data = data[instance_id]
                        if isinstance(inst_data, dict) and "passed" in inst_data:
                            result["passed"] = int(inst_data.get("passed", 0))
                            result["failed"] = int(inst_data.get("failed", 0))
                            result["total"] = result["passed"] + result["failed"]
                            if result["total"] > 0:
                                result["pass_rate"] = result["passed"] / result["total"]
                            result["ok"] = result["failed"] == 0
                            if debug:
                                print(f"Found instance results in {report_file.name}: {result}")
                            return result
                    
                    # Pattern 3: Nested structures
                    for key, value in data.items():
                        if isinstance(value, dict) and "passed" in value and "failed" in value:
                            result["passed"] = int(value.get("passed", 0))
                            result["failed"] = int(value.get("failed", 0))
                            result["total"] = result["passed"] + result["failed"]
                            if result["total"] > 0:
                                result["pass_rate"] = result["passed"] / result["total"]
                            result["ok"] = result["failed"] == 0
                            if debug:
                                print(f"Found nested results in {report_file.name}: {result}")
                            return result
            except json.JSONDecodeError:
                pass
            
            # Try regex parsing for text reports (more comprehensive patterns)
            text_result = parse_pytest_output(content)
            if text_result["total"] > 0:
                if debug:
                    print(f"Parsed text results from {report_file.name}: {text_result}")
                return text_result
                    
        except Exception as e:
            if debug:
                print(f"Error parsing {report_file}: {e}")
            continue
    
    # Fallback: parse from stdout/stderr if available
    # This is handled separately in the caller
    return result


def parse_pytest_output(text: str) -> dict:
    """
    Parse pytest output text to extract test results.
    
    Supports multiple pytest output formats:
    - "X passed, Y failed"
    - "X passed in Y.YYs"
    - "X failed in Y.YYs"
    - Summary lines with test counts
    
    Returns:
        dict with passed, failed, total, pass_rate, ok
    """
    result = {
        "passed": 0,
        "failed": 0,
        "total": 0,
        "pass_rate": 0.0,
        "ok": False,
    }
    
    if not text:
        return result
    
    # Comprehensive patterns for pytest output
    patterns = [
        # "X passed, Y failed in Zs"
        (r"(\d+)\s+passed(?:,\s*(\d+)\s+failed)?(?:\s+in\s+[\d.]+s)?", True, False),
        # "X failed, Y passed in Zs"
        (r"(\d+)\s+failed(?:,\s*(\d+)\s+passed)?(?:\s+in\s+[\d.]+s)?", False, True),
        # "X passed in Ys"
        (r"(\d+)\s+passed(?:\s+in\s+[\d.]+s)?", True, False),
        # "X failed in Ys"
        (r"(\d+)\s+failed(?:\s+in\s+[\d.]+s)?", False, True),
        # "tests passed" or "test passed"
        (r"(\d+)\s+test(?:s)?\s+passed", True, False),
        # Summary format: "=== X passed, Y failed ==="
        (r"===\s*(\d+)\s+passed(?:,\s*(\d+)\s+failed)?\s+===", True, False),
        # Collection format: "collected X items"
        (r"collected\s+(\d+)\s+item(?:s)?", None, None),
    ]
    
    for pattern, is_passed_first, is_failed_first in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            groups = match.groups()
            if is_passed_first is not None:
                if is_passed_first:
                    result["passed"] = int(groups[0])
                    if len(groups) > 1 and groups[1]:
                        result["failed"] = int(groups[1])
                elif is_failed_first:
                    result["failed"] = int(groups[0])
                    if len(groups) > 1 and groups[1]:
                        result["passed"] = int(groups[1])
                
                result["total"] = result["passed"] + result["failed"]
                if result["total"] > 0:
                    result["pass_rate"] = result["passed"] / result["total"]
                result["ok"] = result["failed"] == 0
                return result
    
    # Try to count individual test outcomes
    passed_count = len(re.findall(r"(?:PASSED|✓|PASS)", text, re.IGNORECASE))
    failed_count = len(re.findall(r"(?:FAILED|✗|FAIL)", text, re.IGNORECASE))
    
    if passed_count > 0 or failed_count > 0:
        result["passed"] = passed_count
        result["failed"] = failed_count
        result["total"] = passed_count + failed_count
        if result["total"] > 0:
            result["pass_rate"] = result["passed"] / result["total"]
        result["ok"] = result["failed"] == 0
        return result
    
    return result

