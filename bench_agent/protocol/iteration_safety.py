"""
Component 1: Iteration Safety Guards

Prevents infinite loops and ensures clean iteration state.
Includes repository reset, normalized hash duplicate detection,
and failure signature classification.
"""

import hashlib
import re
import subprocess
from typing import Tuple, List, Optional, Set
from pathlib import Path


# ============================================================================
# SAFETY CONFIGURATION
# ============================================================================

# Hard limits for iteration control
MAX_TOTAL_ITERATIONS = 8  # Absolute maximum across all stages
MAX_TEST_ITERATIONS = 3   # Maximum iterations for test generation
MAX_CODE_ITERATIONS = 5   # Maximum iterations for code generation

# Failure signature patterns
FAILURE_SIGNATURES = {
    'malformed_patch': [
        r'Malformed patch at line \d+',
        r'patch does not apply',
        r'corrupt patch at line \d+',
    ],
    'test_failure': [
        r'FAILED.*test_',
        r'AssertionError',
        r'ERROR.*test_',
    ],
    'syntax_error': [
        r'SyntaxError',
        r'IndentationError',
        r'invalid syntax',
    ],
    'import_error': [
        r'ImportError',
        r'ModuleNotFoundError',
        r'cannot import name',
    ],
}


# ============================================================================
# 1. REPOSITORY RESET
# ============================================================================

def reset_repository_state(repo_path: str, instance_id: str) -> Tuple[bool, str]:
    """
    Reset repository to clean state before each iteration.

    Critical for iteration integrity - without this, subsequent iterations
    compound previous failures and feedback becomes meaningless.

    Args:
        repo_path: Path to the repository
        instance_id: Instance ID for logging

    Returns:
        (success, error_message)
    """
    try:
        repo_path_obj = Path(repo_path)

        if not repo_path_obj.exists():
            return (False, f"Repository path does not exist: {repo_path}")

        # Step 1: Reset all tracked files to HEAD
        result = subprocess.run(
            ['git', 'reset', '--hard', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return (False, f"git reset failed: {result.stderr}")

        # Step 2: Clean untracked files and directories
        result = subprocess.run(
            ['git', 'clean', '-fdx'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return (False, f"git clean failed: {result.stderr}")

        return (True, "Repository reset successful")

    except subprocess.TimeoutExpired:
        return (False, "Repository reset timed out")
    except Exception as e:
        return (False, f"Repository reset error: {e}")


# ============================================================================
# 2. NORMALIZED HASH FOR DUPLICATE DETECTION
# ============================================================================

def normalize_diff(diff: str) -> str:
    """
    Normalize diff for hash comparison.

    Removes whitespace and formatting variations that don't affect
    semantic content. This prevents LLM from generating "different"
    diffs that are actually identical.

    Strategy:
    1. Normalize line prefix whitespace (preserve diff markers +, -, space)
    2. Remove empty lines
    3. Normalize internal whitespace to single space
    4. Preserve line order (don't sort)

    Args:
        diff: Raw diff string

    Returns:
        Normalized diff string for hashing
    """
    if not diff:
        return ""

    lines = []
    for line in diff.split('\n'):
        # Skip completely empty lines
        if not line.strip():
            continue

        # Preserve diff markers (+, -, space) but normalize rest
        if line.startswith(('+', '-', ' ')):
            # Extract marker and content
            marker = line[0]
            content = line[1:].strip()

            # Normalize internal whitespace
            normalized_content = re.sub(r'\s+', ' ', content)

            # Reconstruct: marker + space + content
            normalized = marker + ' ' + normalized_content if normalized_content else marker
        else:
            # Non-diff lines (headers, etc.) - just strip and normalize
            normalized = re.sub(r'\s+', ' ', line.strip())

        lines.append(normalized)

    # Preserve line order
    return '\n'.join(lines)


def compute_diff_hash(diff: str) -> str:
    """
    Compute normalized hash of diff.

    Args:
        diff: Diff string to hash

    Returns:
        SHA256 hash hex string
    """
    normalized = normalize_diff(diff)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


class DuplicateDetector:
    """
    Tracks seen diffs to detect duplicates across iterations.
    """

    def __init__(self):
        self.seen_hashes: Set[str] = set()
        self.iteration_hashes: List[str] = []

    def is_duplicate(self, diff: str) -> bool:
        """
        Check if diff has been seen before.

        Args:
            diff: Diff string to check

        Returns:
            True if duplicate, False otherwise
        """
        diff_hash = compute_diff_hash(diff)

        if diff_hash in self.seen_hashes:
            return True

        # Not a duplicate - record it
        self.seen_hashes.add(diff_hash)
        self.iteration_hashes.append(diff_hash)

        return False

    def get_stats(self) -> dict:
        """Get duplicate detection statistics."""
        return {
            'total_seen': len(self.iteration_hashes),
            'unique_count': len(self.seen_hashes),
            'duplicate_count': len(self.iteration_hashes) - len(self.seen_hashes)
        }


# ============================================================================
# 3. FAILURE SIGNATURE CLASSIFICATION
# ============================================================================

def classify_failure(error_message: str) -> Optional[str]:
    """
    Classify failure by pattern matching.

    Args:
        error_message: Error message or log output

    Returns:
        Failure category name or None if unclassified
    """
    if not error_message:
        return None

    for category, patterns in FAILURE_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return category

    return None


class FailureTracker:
    """
    Track failure patterns across iterations.
    """

    def __init__(self):
        self.failure_history: List[Tuple[int, str, Optional[str]]] = []

    def record_failure(self, iteration: int, error_message: str):
        """
        Record a failure with classification.

        Args:
            iteration: Iteration number (1-based)
            error_message: Error message
        """
        category = classify_failure(error_message)
        self.failure_history.append((iteration, error_message, category))

    def is_stuck(self, window_size: int = 3) -> bool:
        """
        Check if stuck in repeating failure pattern.

        Args:
            window_size: Number of recent iterations to check

        Returns:
            True if same failure category repeated window_size times
        """
        if len(self.failure_history) < window_size:
            return False

        # Get last window_size failure categories
        recent_categories = [
            cat for (_, _, cat) in self.failure_history[-window_size:]
        ]

        # Check if all are the same and not None
        if recent_categories[0] is None:
            return False

        return all(cat == recent_categories[0] for cat in recent_categories)

    def get_dominant_failure(self) -> Optional[str]:
        """
        Get the most common failure category.

        Returns:
            Most common failure category or None
        """
        if not self.failure_history:
            return None

        # Count categories
        category_counts = {}
        for (_, _, cat) in self.failure_history:
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1

        if not category_counts:
            return None

        # Return most common
        return max(category_counts.items(), key=lambda x: x[1])[0]

    def get_stats(self) -> dict:
        """Get failure tracking statistics."""
        categories = [cat for (_, _, cat) in self.failure_history if cat]

        return {
            'total_failures': len(self.failure_history),
            'classified': len(categories),
            'unclassified': len(self.failure_history) - len(categories),
            'dominant_failure': self.get_dominant_failure(),
            'is_stuck': self.is_stuck()
        }


# ============================================================================
# 4. ITERATION SAFETY CONTROLLER
# ============================================================================

class IterationSafetyController:
    """
    Unified controller for all iteration safety mechanisms.
    """

    def __init__(
        self,
        repo_path: str,
        instance_id: str,
        max_total: int = MAX_TOTAL_ITERATIONS,
        max_test: int = MAX_TEST_ITERATIONS,
        max_code: int = MAX_CODE_ITERATIONS
    ):
        self.repo_path = repo_path
        self.instance_id = instance_id

        # Limits
        self.max_total = max_total
        self.max_test = max_test
        self.max_code = max_code

        # Trackers
        self.duplicate_detector = DuplicateDetector()
        self.failure_tracker = FailureTracker()

        # Counters
        self.total_iterations = 0
        self.test_iterations = 0
        self.code_iterations = 0

    def should_continue(self, stage: str) -> Tuple[bool, str]:
        """
        Check if iteration should continue.

        Args:
            stage: "test" or "code"

        Returns:
            (should_continue, reason_if_stop)
        """
        # Check total limit
        if self.total_iterations >= self.max_total:
            return (False, f"Reached max total iterations ({self.max_total})")

        # Check stage-specific limit
        if stage == "test" and self.test_iterations >= self.max_test:
            return (False, f"Reached max test iterations ({self.max_test})")

        if stage == "code" and self.code_iterations >= self.max_code:
            return (False, f"Reached max code iterations ({self.max_code})")

        # Check if stuck in failure loop
        if self.failure_tracker.is_stuck():
            dominant = self.failure_tracker.get_dominant_failure()
            return (False, f"Stuck in repeating failure pattern: {dominant}")

        return (True, "")

    def start_iteration(self, stage: str) -> Tuple[bool, str]:
        """
        Prepare for new iteration.

        Args:
            stage: "test" or "code"

        Returns:
            (success, error_message)
        """
        # Check if should continue
        should_continue, reason = self.should_continue(stage)
        if not should_continue:
            return (False, reason)

        # Reset repository
        success, message = reset_repository_state(self.repo_path, self.instance_id)
        if not success:
            return (False, f"Repository reset failed: {message}")

        # Increment counters
        self.total_iterations += 1
        if stage == "test":
            self.test_iterations += 1
        elif stage == "code":
            self.code_iterations += 1

        return (True, "Iteration started")

    def check_duplicate(self, diff: str) -> bool:
        """
        Check if diff is duplicate.

        Args:
            diff: Diff string

        Returns:
            True if duplicate
        """
        return self.duplicate_detector.is_duplicate(diff)

    def record_failure(self, error_message: str):
        """
        Record iteration failure.

        Args:
            error_message: Error message
        """
        self.failure_tracker.record_failure(
            self.total_iterations,
            error_message
        )

    def get_stats(self) -> dict:
        """Get comprehensive safety statistics."""
        return {
            'iterations': {
                'total': self.total_iterations,
                'test': self.test_iterations,
                'code': self.code_iterations,
                'max_total': self.max_total,
                'max_test': self.max_test,
                'max_code': self.max_code,
            },
            'duplicates': self.duplicate_detector.get_stats(),
            'failures': self.failure_tracker.get_stats(),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_safety_stats(stats: dict) -> str:
    """Format safety statistics for logging."""
    lines = [
        "=== Iteration Safety Statistics ===",
        f"Total Iterations: {stats['iterations']['total']}/{stats['iterations']['max_total']}",
        f"Test Iterations: {stats['iterations']['test']}/{stats['iterations']['max_test']}",
        f"Code Iterations: {stats['iterations']['code']}/{stats['iterations']['max_code']}",
        "",
        "Duplicate Detection:",
        f"  Unique diffs: {stats['duplicates']['unique_count']}",
        f"  Duplicates found: {stats['duplicates']['duplicate_count']}",
        "",
        "Failure Tracking:",
        f"  Total failures: {stats['failures']['total_failures']}",
        f"  Classified: {stats['failures']['classified']}",
        f"  Dominant pattern: {stats['failures']['dominant_failure'] or 'None'}",
        f"  Is stuck: {stats['failures']['is_stuck']}",
    ]

    return '\n'.join(lines)
