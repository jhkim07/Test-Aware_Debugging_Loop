"""
P0.9.3 Phase 2.1: Enhanced Candidate Generation

Combines Step B (2-line anchors) and Step C (safety filtering) for better anchor selection.
"""

from typing import Dict, List, Optional
from .anchor_extractor import (
    AnchorCandidate,
    TwoLineAnchor,
    extract_anchor_candidates,
    extract_two_line_anchors,
    filter_top_level_only
)
from .candidate_ranker import (
    filter_unique_candidates,
    rank_candidates,
    rank_for_replace_delete,
    rank_for_insert
)


def generate_enhanced_candidates(
    source_code: str,
    target_line: Optional[int],
    edit_type: Optional[str] = None,
    max_candidates: int = 20,
    require_unique: bool = True
) -> List[AnchorCandidate]:
    """
    Generate enhanced anchor candidates with Phase 2.1 improvements.

    Improvements:
    - Step B: Prioritize 2-line anchors for replace/delete
    - Step C: Filter out function_def/class_def for replace/delete (safety)
    - Uses adaptive ranking based on edit_type

    Args:
        source_code: Source code
        target_line: Target line number (if known)
        edit_type: Type of edit ('replace', 'delete', 'insert_before', 'insert_after')
        max_candidates: Maximum candidates to return
        require_unique: Only include unique anchors

    Returns:
        List of AnchorCandidate, ranked by quality
    """
    all_candidates = []

    # Step B: Extract 2-line anchors for replace/delete
    # If edit_type is None (unknown), still generate 2-line anchors (they're useful for most operations)
    if target_line is not None and (edit_type in ('replace', 'delete', None)):
        two_line_anchors = extract_two_line_anchors(
            source_code,
            target_line=target_line,
            search_range=10  # Narrow window around target
        )

        # Convert to AnchorCandidate format
        for tl_anchor in two_line_anchors:
            all_candidates.append(tl_anchor.to_anchor_candidate())

    # Extract regular anchor candidates
    candidates_dict = extract_anchor_candidates(
        source_code,
        target_line=target_line,
        search_range=30 if target_line else None
    )

    # Filter to top-level only
    candidates_dict = filter_top_level_only(candidates_dict, allow_single_indent=False)

    # Convert dict to list
    for cand_list in candidates_dict.values():
        all_candidates.extend(cand_list)

    # Step C: Filter out function_def/class_def for replace/delete (SAFETY)
    if edit_type in ('replace', 'delete'):
        all_candidates = [
            c for c in all_candidates
            if c.type not in ('function_def', 'class_def')
        ]

    # Filter to unique only if required
    if require_unique:
        all_candidates = filter_unique_candidates(source_code, all_candidates)

    # Adaptive ranking based on edit_type
    if edit_type in ('replace', 'delete'):
        ranked = rank_for_replace_delete(source_code, all_candidates, target_line)
    elif edit_type in ('insert_before', 'insert_after'):
        ranked = rank_for_insert(source_code, all_candidates, target_line)
    else:
        # Default ranking (precision-first now with Phase 2 weights)
        ranked = rank_candidates(source_code, all_candidates, target_line)

    # Return top candidates
    top_candidates = [r.candidate for r in ranked[:max_candidates]]

    return top_candidates


def generate_candidates_by_type(
    source_code: str,
    target_line: Optional[int],
    edit_type: Optional[str] = None,
    max_candidates: int = 20,
    require_unique: bool = True
) -> Dict[str, List[AnchorCandidate]]:
    """
    Generate enhanced candidates and group by type for prompt formatting.

    Args:
        source_code: Source code
        target_line: Target line number
        edit_type: Type of edit
        max_candidates: Maximum candidates
        require_unique: Filter unique only

    Returns:
        Dict mapping type to list of candidates
    """
    candidates = generate_enhanced_candidates(
        source_code,
        target_line,
        edit_type,
        max_candidates,
        require_unique
    )

    # Group by type
    by_type = {
        'two_line': [],
        'function_definitions': [],
        'class_definitions': [],
        'import_statements': [],
        'line_patterns': [],
        'decorators': []
    }

    for cand in candidates:
        if cand.type == 'two_line':
            by_type['two_line'].append(cand)
        elif cand.type == 'function_def':
            by_type['function_definitions'].append(cand)
        elif cand.type == 'class_def':
            by_type['class_definitions'].append(cand)
        elif cand.type == 'import_stmt':
            by_type['import_statements'].append(cand)
        elif cand.type == 'line_pattern':
            by_type['line_patterns'].append(cand)
        elif cand.type == 'decorator':
            by_type['decorators'].append(cand)

    return by_type
