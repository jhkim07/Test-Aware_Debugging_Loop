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


# ============================================================================
# 4. TEST CANDIDATE SCORING & FALLTHROUGH (P0-1)
# ============================================================================

class TestCandidate:
    """
    Represents a test generation attempt with scoring data.

    P0-1 Key Insight: When max_test_iterations reached, we should fallthrough
    with the BEST test candidate rather than failing completely. This allows
    Code iteration phase to proceed and diagnose whether the blocker is:
    - Test generation quality (already diagnosed)
    - Patch generation quality (to be diagnosed)
    - Patch application (to be diagnosed)
    """

    def __init__(
        self,
        iteration: int,
        test_diff: str,
        brs_satisfied: bool = False,  # CRITICAL: True = tests FAIL on buggy = reproduces bug
        public_pass_count: int = 0,
        public_fail_count: int = 0,
        runs_ok: bool = False,
        patch_apply_ok: bool = True,
        policy_violation: bool = False,
        syntax_error: bool = False,
        import_error: bool = False,
        collection_error: bool = False,
        error_message: str = ""
    ):
        self.iteration = iteration
        self.test_diff = test_diff
        self.brs_satisfied = brs_satisfied  # True = bug reproduced successfully
        self.public_pass_count = public_pass_count
        self.public_fail_count = public_fail_count
        self.runs_ok = runs_ok
        self.patch_apply_ok = patch_apply_ok
        self.policy_violation = policy_violation
        self.syntax_error = syntax_error
        self.import_error = import_error
        self.collection_error = collection_error
        self.error_message = error_message

        # P0-1 Phase 1: Additional diagnostic fields for root cause analysis
        self.fail_signature = self._compute_fail_signature(error_message)
        self.diff_fingerprint = self._compute_diff_fingerprint(test_diff)
        self.failure_stage = self._classify_failure_stage()

    def _compute_fail_signature(self, error_msg: str) -> str:
        """Extract error type + first meaningful line for stuck detection"""
        if not error_msg:
            return "NO_ERROR"

        lines = error_msg.split('\n')
        for line in lines:
            if 'Error:' in line or 'Exception:' in line:
                return line[:60].strip()

        return error_msg[:60].strip()

    def _compute_diff_fingerprint(self, diff: str) -> str:
        """Compute hash of diff for duplicate detection"""
        import hashlib
        if not diff:
            return "EMPTY"
        return hashlib.md5(diff.encode()).hexdigest()[:8]

    def _classify_failure_stage(self) -> str:
        """Classify where failure occurred in test execution pipeline"""
        if self.policy_violation:
            return "POLICY"
        if self.collection_error:
            return "COLLECTION"
        if self.import_error:
            return "IMPORT"
        if self.syntax_error:
            return "SYNTAX"
        if not self.runs_ok:
            return "EXECUTION"
        if not self.brs_satisfied and self.runs_ok:
            return "ASSERTION"  # Tests ran but didn't reproduce bug
        if self.brs_satisfied:
            return "BRS_OK"
        return "UNKNOWN"

    def compute_score(self) -> float:
        """
        Compute quality score for test candidate.

        Scoring logic:
        - BRS satisfied: +20 (highest priority)
        - Public pass count: +3 per test (shows test runs)
        - Runs OK (no crashes): +10
        - Patch applies: +5
        - Policy violation: -20 (dealbreaker)
        - Collection error: -15 (can't run)
        - Import error: -10 (structural issue)
        - Syntax error: -5 (easy to fix but still bad)

        Returns:
            Quality score (higher is better)
        """
        score = 0.0

        # Positive factors
        if self.brs_satisfied:
            score += 20.0  # Highest priority - test reproduces bug

        score += self.public_pass_count * 3.0  # Shows test actually runs

        if self.runs_ok:
            score += 10.0  # Test execution completed

        if self.patch_apply_ok:
            score += 5.0  # No patch application issues

        # Negative factors (blockers)
        if self.policy_violation:
            score -= 20.0  # Dealbreaker - violates policy rules

        if self.collection_error:
            score -= 15.0  # Can't even collect tests

        if self.import_error:
            score -= 10.0  # Structural problem

        if self.syntax_error:
            score -= 5.0  # Easy to fix but still problematic

        return score

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'iteration': self.iteration,
            'score': self.compute_score(),
            'brs_satisfied': self.brs_satisfied,
            'public_pass_count': self.public_pass_count,
            'public_fail_count': self.public_fail_count,
            'runs_ok': self.runs_ok,
            'patch_apply_ok': self.patch_apply_ok,
            'policy_violation': self.policy_violation,
            'syntax_error': self.syntax_error,
            'import_error': self.import_error,
            'collection_error': self.collection_error,
            # P0-1 Phase 1: Diagnostic fields
            'fail_signature': self.fail_signature,
            'diff_fingerprint': self.diff_fingerprint,
            'failure_stage': self.failure_stage,
        }


# P0-1 Phase 1: Predicate functions for candidate validation
def is_valid_for_fallthrough(candidate: TestCandidate) -> bool:
    """
    Check if candidate is SAFE to use for fallthrough to Code phase.

    This is NOT about score - it's about execution safety.
    A candidate is valid for fallthrough if it:
    1. Runs without crashing (runs_ok=True)
    2. Reproduces the bug (brs_satisfied=True)
    3. Has no policy violations
    4. Has no collection errors

    Args:
        candidate: Test candidate to validate

    Returns:
        True if candidate can safely be used for Code phase

    Example:
        - BRS=1, runs_ok=True, no_policy → valid (can proceed to Code)
        - BRS=1, policy_violation=True → invalid (unsafe to execute)
        - BRS=0, runs_ok=True → invalid (doesn't reproduce bug)
    """
    if not candidate.runs_ok:
        return False
    if not candidate.brs_satisfied:
        return False
    if candidate.policy_violation:
        return False
    if candidate.collection_error:
        return False
    return True


def is_valid_for_diagnosis(candidate: TestCandidate) -> bool:
    """
    Check if candidate has DIAGNOSTIC VALUE even if not executable.

    A candidate has diagnostic value if:
    1. It reproduces the bug (brs_satisfied=True), OR
    2. It runs and produces test results (public pass/fail counts)

    This allows us to diagnose WHY fallthrough failed:
    - BRS=1 + policy_violation → "policy is blocker"
    - BRS=1 + collection_error → "test collection is blocker"
    - BRS=0 + runs_ok + public tests → "assertion is blocker"

    Args:
        candidate: Test candidate to validate

    Returns:
        True if candidate provides diagnostic information

    Example:
        - BRS=1, policy=True → valid for diagnosis (shows policy blocker)
        - BRS=0, runs_ok, public_pass=2 → valid for diagnosis (shows assertion issue)
        - BRS=0, collection_error → invalid (no useful info)
    """
    # Bug reproduction has diagnostic value regardless of execution state
    if candidate.brs_satisfied:
        return True

    # Successful execution with test results has diagnostic value
    if candidate.runs_ok and (candidate.public_pass_count > 0 or candidate.public_fail_count > 0):
        return True

    return False


class TestCandidateTracker:
    """
    Track all test generation attempts and select best candidate for fallthrough.

    P0-1: When max_test_iterations reached without public test success,
    select the BEST test candidate to proceed with Code iteration.
    """

    def __init__(self):
        self.candidates: List[TestCandidate] = []

    def add_candidate(self, candidate: TestCandidate):
        """Record a test generation attempt."""
        self.candidates.append(candidate)

    def get_best_candidate(self) -> Optional[TestCandidate]:
        """
        Select best test candidate based on scoring.

        Returns:
            Best test candidate or None if no candidates
        """
        if not self.candidates:
            return None

        # Sort by score (highest first)
        sorted_candidates = sorted(
            self.candidates,
            key=lambda c: c.compute_score(),
            reverse=True
        )

        return sorted_candidates[0]

    def has_valid_candidate(self) -> bool:
        """
        DEPRECATED: Use has_valid_for_fallthrough() instead.

        Check if we have at least one candidate that can proceed.
        This uses score-based validation (legacy, not recommended).

        Returns:
            True if we have at least one valid candidate
        """
        best = self.get_best_candidate()
        if not best:
            return False

        return best.compute_score() > 0

    def has_valid_for_fallthrough(self) -> bool:
        """
        Check if we have at least one candidate SAFE for fallthrough.

        Uses predicate-based validation (recommended over score threshold).

        Returns:
            True if we have at least one executable, bug-reproducing candidate
        """
        for candidate in self.candidates:
            if is_valid_for_fallthrough(candidate):
                return True
        return False

    def get_best_executable_candidate(self) -> Optional[TestCandidate]:
        """
        Get best candidate that is SAFE for fallthrough.

        Filters candidates using is_valid_for_fallthrough predicate,
        then selects highest-scoring among valid candidates.

        Returns:
            Best executable candidate or None if no valid candidates

        Example:
            If we have:
            - Candidate A: BRS=1, policy=True, score=0
            - Candidate B: BRS=1, runs_ok=True, score=30
            - Candidate C: BRS=0, runs_ok=True, score=13

            Returns: Candidate B (only valid-for-fallthrough candidate)
        """
        valid_candidates = [c for c in self.candidates if is_valid_for_fallthrough(c)]

        if not valid_candidates:
            return None

        # Sort by score (highest first)
        sorted_valid = sorted(
            valid_candidates,
            key=lambda c: c.compute_score(),
            reverse=True
        )

        return sorted_valid[0]

    def get_diagnostic_summary(self) -> dict:
        """
        Generate diagnostic summary for Phase 1 analysis.

        Returns comprehensive breakdown of candidate distribution:
        - Total candidates
        - Valid-for-fallthrough count
        - Valid-for-diagnosis count
        - Failure stage distribution
        - Stuck pattern detection (repeated fail_signature)

        Returns:
            Dictionary with diagnostic metrics

        Example output:
            {
                'total_candidates': 3,
                'valid_for_fallthrough': 1,
                'valid_for_diagnosis': 2,
                'failure_stages': {'POLICY': 1, 'BRS_OK': 1, 'ASSERTION': 1},
                'stuck_pattern_detected': True,
                'repeated_signatures': ['ModuleNotFoundError: No module'],
                'best_executable_score': 30.0
            }
        """
        if not self.candidates:
            return {
                'total_candidates': 0,
                'valid_for_fallthrough': 0,
                'valid_for_diagnosis': 0,
                'failure_stages': {},
                'stuck_pattern_detected': False,
            }

        valid_fallthrough = sum(1 for c in self.candidates if is_valid_for_fallthrough(c))
        valid_diagnosis = sum(1 for c in self.candidates if is_valid_for_diagnosis(c))

        # Count failure stages
        stage_counts = {}
        for candidate in self.candidates:
            stage = candidate.failure_stage
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        # Detect stuck patterns (same fail_signature repeated)
        signatures = [c.fail_signature for c in self.candidates]
        signature_counts = {}
        for sig in signatures:
            signature_counts[sig] = signature_counts.get(sig, 0) + 1

        repeated_signatures = [sig for sig, count in signature_counts.items() if count >= 2 and sig != "NO_ERROR"]

        best_executable = self.get_best_executable_candidate()

        return {
            'total_candidates': len(self.candidates),
            'valid_for_fallthrough': valid_fallthrough,
            'valid_for_diagnosis': valid_diagnosis,
            'failure_stages': stage_counts,
            'stuck_pattern_detected': len(repeated_signatures) > 0,
            'repeated_signatures': repeated_signatures,
            'best_executable_score': best_executable.compute_score() if best_executable else None,
            'best_executable_iteration': best_executable.iteration if best_executable else None,
        }

    def get_stats(self) -> dict:
        """Get candidate tracking statistics."""
        if not self.candidates:
            return {
                'total_candidates': 0,
                'best_score': None,
                'has_valid': False
            }

        best = self.get_best_candidate()
        return {
            'total_candidates': len(self.candidates),
            'best_score': best.compute_score() if best else None,
            'best_iteration': best.iteration if best else None,
            'has_valid': self.has_valid_candidate(),
            'all_scores': [c.compute_score() for c in self.candidates]
        }


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

    P0-1 Enhancement: Includes TestCandidateTracker for fallthrough when
    max_test_iterations is reached without public test success.
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
        self.test_candidate_tracker = TestCandidateTracker()  # P0-1

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

    def add_test_candidate(
        self,
        iteration: int,
        test_diff: str,
        brs_satisfied: bool = False,
        public_pass_count: int = 0,
        public_fail_count: int = 0,
        runs_ok: bool = False,
        patch_apply_ok: bool = True,
        policy_violation: bool = False,
        syntax_error: bool = False,
        import_error: bool = False,
        collection_error: bool = False,
        error_message: str = ""
    ):
        """
        Record a test generation attempt for P0-1 fallthrough.

        Args:
            iteration: Current iteration number
            test_diff: Generated test diff
            brs_satisfied: Whether BRS validation passed
            public_pass_count: Number of public tests that passed
            public_fail_count: Number of public tests that failed
            runs_ok: Whether test execution completed without crashes
            patch_apply_ok: Whether patch applied successfully
            policy_violation: Whether test violated policy rules
            syntax_error: Whether test has syntax errors
            import_error: Whether test has import errors
            collection_error: Whether test failed to collect
            error_message: Any error message from execution
        """
        candidate = TestCandidate(
            iteration=iteration,
            test_diff=test_diff,
            brs_satisfied=brs_satisfied,
            public_pass_count=public_pass_count,
            public_fail_count=public_fail_count,
            runs_ok=runs_ok,
            patch_apply_ok=patch_apply_ok,
            policy_violation=policy_violation,
            syntax_error=syntax_error,
            import_error=import_error,
            collection_error=collection_error,
            error_message=error_message
        )
        self.test_candidate_tracker.add_candidate(candidate)

    def get_best_test_candidate(self) -> Optional[TestCandidate]:
        """
        Get best test candidate for P0-1 fallthrough.

        Returns:
            Best test candidate or None
        """
        return self.test_candidate_tracker.get_best_candidate()

    def should_fallthrough_to_code(self) -> bool:
        """
        Check if we should fallthrough to Code iteration phase despite
        max_test_iterations being reached.

        P0-1 Logic:
        - If max_test_iterations reached
        - AND we have at least one valid test candidate (score > 0)
        - THEN proceed to Code iteration with best candidate
        - This allows diagnosis of whether blocker is test vs patch

        Returns:
            True if should fallthrough to code phase
        """
        # Only fallthrough if we've hit test iteration limit
        if self.test_iterations < self.max_test:
            return False

        # Check if we have a valid candidate
        return self.test_candidate_tracker.has_valid_candidate()

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
            'test_candidates': self.test_candidate_tracker.get_stats(),  # P0-1
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
