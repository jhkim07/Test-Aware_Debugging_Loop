"""
Component 3: Candidate Ranker

Ranks anchor candidates by quality (uniqueness, proximity, stability).
Helps LLM select best anchors from candidates.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass

from .anchor_extractor import AnchorCandidate, find_anchor_in_source


@dataclass
class RankedCandidate:
    """Anchor candidate with quality score."""
    candidate: AnchorCandidate
    score: float
    uniqueness_score: float
    proximity_score: float
    stability_score: float
    rank: int


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def score_uniqueness(source_code: str, candidate: AnchorCandidate) -> float:
    """
    Score anchor uniqueness (higher = more unique).

    Args:
        source_code: Source code
        candidate: Anchor candidate

    Returns:
        Uniqueness score (0.0 to 1.0)
    """
    _, count = find_anchor_in_source(
        source_code,
        candidate.text,
        candidate.type
    )

    if count == 0:
        return 0.0  # Not found (shouldn't happen)
    elif count == 1:
        return 1.0  # Perfectly unique
    else:
        # Penalize by occurrence count
        # count=2 → 0.5, count=3 → 0.33, etc.
        return 1.0 / count


def score_proximity(
    candidate: AnchorCandidate,
    target_line: Optional[int],
    max_distance: int = 50
) -> float:
    """
    Score anchor proximity to target line (higher = closer).

    Args:
        candidate: Anchor candidate
        target_line: Target line number (1-indexed)
        max_distance: Maximum distance for scoring

    Returns:
        Proximity score (0.0 to 1.0)
    """
    if target_line is None:
        return 0.5  # Neutral score if no target

    distance = abs(candidate.lineno - target_line)

    if distance > max_distance:
        return 0.0  # Too far

    # Linear decay: distance=0 → 1.0, distance=max → 0.0
    return 1.0 - (distance / max_distance)


def score_stability(candidate: AnchorCandidate) -> float:
    """
    Score anchor stability (resistance to unrelated changes).

    Structural anchors (functions, classes) are more stable than line patterns.

    Args:
        candidate: Anchor candidate

    Returns:
        Stability score (0.0 to 1.0)
    """
    stability_map = {
        'function_def': 1.0,     # Very stable
        'class_def': 1.0,        # Very stable
        'decorator': 0.8,        # Fairly stable
        'import_stmt': 0.6,      # Moderately stable (can change)
        'line_pattern': 0.4,     # Less stable (formatting can change)
    }

    return stability_map.get(candidate.type, 0.5)


def compute_candidate_score(
    source_code: str,
    candidate: AnchorCandidate,
    target_line: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Compute composite score for anchor candidate.

    Args:
        source_code: Source code
        candidate: Anchor candidate
        target_line: Optional target line for proximity scoring
        weights: Optional weight overrides

    Returns:
        Dict with individual scores and composite score
    """
    # Default weights - UPDATED: Uniqueness is CRITICAL (P0.9.3)
    if weights is None:
        weights = {
            'uniqueness': 0.7,   # CRITICAL - Increased from 0.5 to 0.7
            'proximity': 0.15,   # Reduced from 0.3
            'stability': 0.15,   # Reduced from 0.2
        }

    # Compute individual scores
    uniqueness = score_uniqueness(source_code, candidate)
    proximity = score_proximity(candidate, target_line)
    stability = score_stability(candidate)

    # Compute weighted composite score
    composite = (
        uniqueness * weights['uniqueness'] +
        proximity * weights['proximity'] +
        stability * weights['stability']
    )

    return {
        'uniqueness': uniqueness,
        'proximity': proximity,
        'stability': stability,
        'composite': composite
    }


# ============================================================================
# RANKING FUNCTIONS
# ============================================================================

def rank_candidates(
    source_code: str,
    candidates: List[AnchorCandidate],
    target_line: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None
) -> List[RankedCandidate]:
    """
    Rank anchor candidates by quality.

    Args:
        source_code: Source code
        candidates: List of anchor candidates
        target_line: Optional target line
        weights: Optional scoring weights

    Returns:
        List of RankedCandidate, sorted by score (highest first)
    """
    ranked = []

    for candidate in candidates:
        scores = compute_candidate_score(
            source_code,
            candidate,
            target_line,
            weights
        )

        ranked.append(RankedCandidate(
            candidate=candidate,
            score=scores['composite'],
            uniqueness_score=scores['uniqueness'],
            proximity_score=scores['proximity'],
            stability_score=scores['stability'],
            rank=0  # Will be set after sorting
        ))

    # Sort by score (descending)
    ranked.sort(key=lambda x: x.score, reverse=True)

    # Assign ranks
    for i, r in enumerate(ranked, 1):
        r.rank = i

    return ranked


def rank_candidates_by_type(
    source_code: str,
    candidates: Dict[str, List[AnchorCandidate]],
    target_line: Optional[int] = None,
    top_k_per_type: int = 5
) -> Dict[str, List[RankedCandidate]]:
    """
    Rank candidates within each type category.

    Args:
        source_code: Source code
        candidates: Dict mapping type to candidates
        target_line: Optional target line
        top_k_per_type: Keep top K per type

    Returns:
        Dict mapping type to ranked candidates
    """
    ranked_by_type = {}

    for anchor_type, candidate_list in candidates.items():
        if not candidate_list:
            ranked_by_type[anchor_type] = []
            continue

        # Rank candidates
        ranked = rank_candidates(
            source_code,
            candidate_list,
            target_line
        )

        # Keep top K
        ranked_by_type[anchor_type] = ranked[:top_k_per_type]

    return ranked_by_type


# ============================================================================
# FILTERING
# ============================================================================

def filter_unique_candidates(
    source_code: str,
    candidates: List[AnchorCandidate]
) -> List[AnchorCandidate]:
    """
    Filter to only unique candidates (score = 1.0).

    Args:
        source_code: Source code
        candidates: List of candidates

    Returns:
        List of unique candidates
    """
    unique = []

    for candidate in candidates:
        uniqueness = score_uniqueness(source_code, candidate)
        if uniqueness == 1.0:
            unique.append(candidate)

    return unique


def filter_by_score_threshold(
    ranked: List[RankedCandidate],
    min_score: float = 0.5
) -> List[RankedCandidate]:
    """
    Filter ranked candidates by minimum score.

    Args:
        ranked: Ranked candidates
        min_score: Minimum composite score

    Returns:
        Filtered list
    """
    return [r for r in ranked if r.score >= min_score]


def filter_nearby_candidates(
    ranked: List[RankedCandidate],
    target_line: int,
    max_distance: int = 20
) -> List[RankedCandidate]:
    """
    Filter to candidates near target line.

    Args:
        ranked: Ranked candidates
        target_line: Target line (1-indexed)
        max_distance: Maximum distance

    Returns:
        Filtered list
    """
    nearby = []

    for r in ranked:
        distance = abs(r.candidate.lineno - target_line)
        if distance <= max_distance:
            nearby.append(r)

    return nearby


# ============================================================================
# FORMATTING
# ============================================================================

def format_ranked_candidates(
    ranked: List[RankedCandidate],
    max_display: int = 10
) -> str:
    """
    Format ranked candidates for display.

    Args:
        ranked: Ranked candidates
        max_display: Maximum to display

    Returns:
        Formatted string
    """
    if not ranked:
        return "No candidates"

    lines = []
    for r in ranked[:max_display]:
        lines.append(
            f"{r.rank}. [Line {r.candidate.lineno}] "
            f"{r.candidate.type} (score: {r.score:.2f})\n"
            f"   {r.candidate.text.strip()[:80]}\n"
            f"   Uniqueness: {r.uniqueness_score:.2f}, "
            f"Proximity: {r.proximity_score:.2f}, "
            f"Stability: {r.stability_score:.2f}"
        )

    if len(ranked) > max_display:
        lines.append(f"... and {len(ranked) - max_display} more")

    return '\n'.join(lines)


def format_ranked_by_type(
    ranked_by_type: Dict[str, List[RankedCandidate]]
) -> str:
    """
    Format ranked candidates grouped by type.

    Args:
        ranked_by_type: Dict of ranked candidates by type

    Returns:
        Formatted string
    """
    lines = []

    for anchor_type, ranked in ranked_by_type.items():
        if not ranked:
            continue

        type_label = anchor_type.replace('_', ' ').title()
        lines.append(f"\n{type_label}:")

        for r in ranked:
            lines.append(
                f"  {r.rank}. [Line {r.candidate.lineno}] "
                f"(score: {r.score:.2f})\n"
                f"     {r.candidate.text.strip()[:70]}"
            )

    return '\n'.join(lines)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_best_candidates(
    source_code: str,
    candidates: Dict[str, List[AnchorCandidate]],
    target_line: Optional[int] = None,
    max_candidates: int = 20
) -> List[RankedCandidate]:
    """
    Get best anchor candidates across all types.

    Args:
        source_code: Source code
        candidates: Dict of candidates by type
        target_line: Optional target line
        max_candidates: Maximum to return

    Returns:
        Top-ranked candidates (mixed types)
    """
    # Collect all candidates
    all_candidates = []
    for candidate_list in candidates.values():
        all_candidates.extend(candidate_list)

    # Rank them
    ranked = rank_candidates(
        source_code,
        all_candidates,
        target_line
    )

    # Return top K
    return ranked[:max_candidates]


def get_unique_best_candidates(
    source_code: str,
    candidates: Dict[str, List[AnchorCandidate]],
    target_line: Optional[int] = None,
    max_candidates: int = 20
) -> List[RankedCandidate]:
    """
    Get best unique-only candidates.

    Args:
        source_code: Source code
        candidates: Dict of candidates by type
        target_line: Optional target line
        max_candidates: Maximum to return

    Returns:
        Top-ranked unique candidates
    """
    # Get all best candidates
    best = get_best_candidates(
        source_code,
        candidates,
        target_line,
        max_candidates * 2  # Get more to account for filtering
    )

    # Filter to unique only
    unique = [r for r in best if r.uniqueness_score == 1.0]

    # Return top K
    return unique[:max_candidates]


# ============================================================================
# ANCHOR RECOMMENDATION
# ============================================================================

def recommend_anchors_for_edit(
    source_code: str,
    candidates: Dict[str, List[AnchorCandidate]],
    edit_type: str,
    target_line: Optional[int] = None
) -> List[RankedCandidate]:
    """
    Recommend best anchors for specific edit type.

    Different edit types prefer different anchor types:
    - insert_after function: prefer function_def anchors
    - replace line: prefer line_pattern anchors
    - etc.

    Args:
        source_code: Source code
        candidates: Dict of candidates by type
        edit_type: Edit type (insert_before, insert_after, replace, delete)
        target_line: Optional target line

    Returns:
        Recommended anchors
    """
    # Adjust weights based on edit type - UPDATED (P0.9.3)
    if edit_type in ('insert_before', 'insert_after'):
        # Prefer stable structural anchors, but uniqueness still critical
        weights = {
            'uniqueness': 0.6,   # UPDATED: Still prioritize uniqueness
            'proximity': 0.15,
            'stability': 0.25,   # Structural anchors good for insertion
        }
    elif edit_type in ('replace', 'delete'):
        # Uniqueness is CRITICAL for replace/delete
        weights = {
            'uniqueness': 0.8,   # UPDATED: Even higher for replace/delete
            'proximity': 0.1,
            'stability': 0.1,
        }
    else:
        weights = None  # Use defaults (0.7/0.15/0.15)

    # Get best candidates with adjusted weights
    all_candidates = []
    for candidate_list in candidates.values():
        all_candidates.extend(candidate_list)

    ranked = rank_candidates(
        source_code,
        all_candidates,
        target_line,
        weights
    )

    return ranked[:20]
