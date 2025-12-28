"""
Component 3: Anchor Extractor

Extracts anchor candidates from source code using AST and pattern matching.
System-generated anchors prevent LLM hallucination.
"""

import ast
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class AnchorCandidate:
    """Represents a potential anchor point in code."""
    type: str  # 'function_def', 'class_def', 'line_pattern', 'import_stmt'
    text: str  # Exact text of the anchor
    lineno: int  # Line number (1-indexed)
    end_lineno: Optional[int] = None  # For multi-line constructs
    name: Optional[str] = None  # Function/class name if applicable
    context: Optional[str] = None  # Surrounding context


# ============================================================================
# AST-BASED EXTRACTION
# ============================================================================

def extract_anchor_candidates(
    source_code: str,
    target_line: Optional[int] = None,
    search_range: int = 20
) -> Dict[str, List[AnchorCandidate]]:
    """
    Extract anchor candidates from Python source code.

    Uses AST for structural anchors (functions, classes, imports)
    and pattern matching for line-based anchors.

    Args:
        source_code: Python source code
        target_line: Optional line number to focus search around
        search_range: Number of lines to search around target_line

    Returns:
        Dict mapping anchor type to list of candidates
    """
    candidates = {
        'function_definitions': [],
        'class_definitions': [],
        'import_statements': [],
        'line_patterns': [],
        'decorators': []
    }

    lines = source_code.split('\n')

    # Try AST parsing (may fail for incomplete/invalid code)
    try:
        tree = ast.parse(source_code)
        _extract_from_ast(tree, source_code, candidates)
    except SyntaxError as e:
        # Fall back to pattern matching only
        import sys
        print(f"[anchor_extractor] AST parse failed: {e}. Using pattern matching only.", file=sys.stderr)

    # Add line pattern candidates (always useful)
    _extract_line_patterns(lines, target_line, search_range, candidates)

    # Add decorator candidates
    _extract_decorators(lines, candidates)

    return candidates


def _extract_from_ast(
    tree: ast.AST,
    source_code: str,
    candidates: Dict[str, List[AnchorCandidate]]
) -> None:
    """Extract anchors from AST."""
    lines = source_code.split('\n')

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Function definition
            if hasattr(node, 'lineno'):
                lineno = node.lineno
                if 0 < lineno <= len(lines):
                    line_text = lines[lineno - 1]
                    candidates['function_definitions'].append(
                        AnchorCandidate(
                            type='function_def',
                            text=line_text,
                            lineno=lineno,
                            end_lineno=getattr(node, 'end_lineno', None),
                            name=node.name
                        )
                    )

        elif isinstance(node, ast.ClassDef):
            # Class definition
            if hasattr(node, 'lineno'):
                lineno = node.lineno
                if 0 < lineno <= len(lines):
                    line_text = lines[lineno - 1]
                    candidates['class_definitions'].append(
                        AnchorCandidate(
                            type='class_def',
                            text=line_text,
                            lineno=lineno,
                            end_lineno=getattr(node, 'end_lineno', None),
                            name=node.name
                        )
                    )

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # Import statement
            if hasattr(node, 'lineno'):
                lineno = node.lineno
                if 0 < lineno <= len(lines):
                    line_text = lines[lineno - 1]
                    candidates['import_statements'].append(
                        AnchorCandidate(
                            type='import_stmt',
                            text=line_text,
                            lineno=lineno
                        )
                    )


def _extract_line_patterns(
    lines: List[str],
    target_line: Optional[int],
    search_range: int,
    candidates: Dict[str, List[AnchorCandidate]]
) -> None:
    """Extract line pattern anchors around target line."""

    if target_line is None:
        # No target, use all non-empty lines
        for i, line in enumerate(lines, 1):
            if line.strip() and not line.strip().startswith('#'):
                candidates['line_patterns'].append(
                    AnchorCandidate(
                        type='line_pattern',
                        text=line,
                        lineno=i
                    )
                )
    else:
        # Search around target line
        start = max(1, target_line - search_range)
        end = min(len(lines), target_line + search_range)

        for i in range(start - 1, end):
            if i < len(lines):
                line = lines[i]
                if line.strip() and not line.strip().startswith('#'):
                    candidates['line_patterns'].append(
                        AnchorCandidate(
                            type='line_pattern',
                            text=line,
                            lineno=i + 1
                        )
                    )


def _extract_decorators(
    lines: List[str],
    candidates: Dict[str, List[AnchorCandidate]]
) -> None:
    """Extract decorator anchors (@decorator_name)."""
    decorator_pattern = re.compile(r'^\s*@\w+')

    for i, line in enumerate(lines, 1):
        if decorator_pattern.match(line):
            candidates['decorators'].append(
                AnchorCandidate(
                    type='decorator',
                    text=line,
                    lineno=i
                )
            )


# ============================================================================
# ANCHOR SEARCH AND VALIDATION
# ============================================================================

def find_anchor_in_source(
    source_code: str,
    anchor_text: str,
    anchor_type: str = 'line_pattern'
) -> Tuple[Optional[int], int]:
    """
    Find anchor in source code.

    Args:
        source_code: Source code to search
        anchor_text: Anchor text to find
        anchor_type: Type of anchor

    Returns:
        (line_index, occurrence_count)
        line_index is 0-based, None if not found
    """
    lines = source_code.split('\n')
    occurrences = []

    anchor_text_stripped = anchor_text.strip()

    for i, line in enumerate(lines):
        if anchor_type == 'line_pattern':
            # Exact match (after stripping)
            if line.strip() == anchor_text_stripped:
                occurrences.append(i)
        elif anchor_type == 'function_def':
            # Match function definition
            if line.strip().startswith('def ') and anchor_text_stripped in line:
                occurrences.append(i)
        elif anchor_type == 'class_def':
            # Match class definition
            if line.strip().startswith('class ') and anchor_text_stripped in line:
                occurrences.append(i)
        elif anchor_type == 'import_stmt':
            # Match import
            if 'import ' in line and anchor_text_stripped in line:
                occurrences.append(i)
        elif anchor_type == 'decorator':
            # Match decorator
            if line.strip().startswith('@') and anchor_text_stripped in line:
                occurrences.append(i)

    if not occurrences:
        return (None, 0)

    # Return first occurrence and count
    return (occurrences[0], len(occurrences))


def is_anchor_unique(source_code: str, anchor_text: str, anchor_type: str = 'line_pattern') -> bool:
    """
    Check if anchor appears exactly once in source.

    Args:
        source_code: Source code
        anchor_text: Anchor text
        anchor_type: Type of anchor

    Returns:
        True if anchor is unique (appears exactly once)
    """
    _, count = find_anchor_in_source(source_code, anchor_text, anchor_type)
    return count == 1


# ============================================================================
# CANDIDATE FILTERING
# ============================================================================

def filter_unique_candidates(
    source_code: str,
    candidates: Dict[str, List[AnchorCandidate]]
) -> Dict[str, List[AnchorCandidate]]:
    """
    Filter candidates to only include unique anchors.

    Args:
        source_code: Source code
        candidates: All candidates

    Returns:
        Filtered candidates (unique only)
    """
    filtered = {key: [] for key in candidates.keys()}

    for anchor_type, candidate_list in candidates.items():
        for candidate in candidate_list:
            if is_anchor_unique(source_code, candidate.text, candidate.type):
                filtered[anchor_type].append(candidate)

    return filtered


def get_candidates_near_line(
    candidates: Dict[str, List[AnchorCandidate]],
    target_line: int,
    max_distance: int = 10
) -> List[AnchorCandidate]:
    """
    Get candidates within max_distance of target line.

    Args:
        candidates: All candidates
        target_line: Target line number (1-indexed)
        max_distance: Maximum distance from target

    Returns:
        List of nearby candidates, sorted by proximity
    """
    nearby = []

    for candidate_list in candidates.values():
        for candidate in candidate_list:
            distance = abs(candidate.lineno - target_line)
            if distance <= max_distance:
                nearby.append((distance, candidate))

    # Sort by distance (closest first)
    nearby.sort(key=lambda x: x[0])

    return [c for (d, c) in nearby]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_candidates_for_prompt(
    candidates: Dict[str, List[AnchorCandidate]],
    max_per_type: int = 10
) -> str:
    """
    Format candidates for LLM prompt.

    Args:
        candidates: Anchor candidates
        max_per_type: Maximum candidates to show per type

    Returns:
        Formatted string for prompt
    """
    lines = []

    for anchor_type, candidate_list in candidates.items():
        if not candidate_list:
            continue

        # Show limited number per type
        shown = candidate_list[:max_per_type]

        lines.append(f"\n{anchor_type.replace('_', ' ').title()}:")
        for i, candidate in enumerate(shown, 1):
            # Format: [line number] exact text
            lines.append(f"  {i}. [Line {candidate.lineno}] {candidate.text.strip()}")

        if len(candidate_list) > max_per_type:
            lines.append(f"  ... and {len(candidate_list) - max_per_type} more")

    return '\n'.join(lines)


def filter_top_level_only(
    candidates: Dict[str, List[AnchorCandidate]],
    allow_single_indent: bool = False
) -> Dict[str, List[AnchorCandidate]]:
    """
    Filter candidates to only include top-level (non-nested) items.

    This prevents LLM from selecting anchors inside functions/classes,
    which causes malformed diffs when code is inserted at wrong locations.

    Args:
        candidates: All anchor candidates
        allow_single_indent: If True, allow 4-space indented items (for class methods)

    Returns:
        Filtered candidates with only top-level items
    """
    filtered = {key: [] for key in candidates.keys()}

    for anchor_type, candidate_list in candidates.items():
        for candidate in candidate_list:
            # Calculate indentation level (number of leading spaces)
            text = candidate.text
            indent_spaces = len(text) - len(text.lstrip())

            # Top-level only (no indentation)
            if indent_spaces == 0:
                filtered[anchor_type].append(candidate)
            elif allow_single_indent and indent_spaces == 4:
                # For class methods, optionally allow 1 level (4 spaces)
                # Only for function/class definitions, not decorators or patterns
                if anchor_type in ['function_definitions', 'class_definitions']:
                    filtered[anchor_type].append(candidate)

    return filtered


def count_candidates(candidates: Dict[str, List[AnchorCandidate]]) -> int:
    """Count total number of candidates."""
    return sum(len(lst) for lst in candidates.values())
