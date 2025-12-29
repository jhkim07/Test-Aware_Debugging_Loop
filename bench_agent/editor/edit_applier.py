"""
Component 3: Edit Applier

Applies edit scripts to source code deterministically.
Handles insert_before, insert_after, replace, and delete operations.
"""

from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import json


@dataclass
class EditOperation:
    """Represents a single edit operation."""
    type: str  # 'insert_before', 'insert_after', 'replace', 'delete'
    anchor: Dict  # Anchor specification
    content: Optional[str] = None  # New content (not needed for delete)
    description: Optional[str] = None  # Human-readable description


@dataclass
class EditResult:
    """Result of applying edits."""
    success: bool
    modified_code: str
    errors: List[str]
    applied_count: int
    skipped_count: int


# ============================================================================
# EDIT APPLICATION ENGINE
# ============================================================================

def apply_edit_script(
    source_code: str,
    edit_script: Dict,
    validate_anchors: bool = True
) -> EditResult:
    """
    Apply edit script to source code.

    Args:
        source_code: Original source code
        edit_script: Parsed JSON edit script
        validate_anchors: Whether to validate anchor uniqueness

    Returns:
        EditResult with modified code and stats
    """
    lines = source_code.split('\n')
    errors = []
    applied_count = 0
    skipped_count = 0

    # Parse edits
    edits = edit_script.get('edits', [])

    if not edits:
        errors.append("No edits in edit script")
        return EditResult(
            success=False,
            modified_code=source_code,
            errors=errors,
            applied_count=0,
            skipped_count=0
        )

    # Apply edits in sequence
    for i, edit_dict in enumerate(edits):
        try:
            # Parse edit
            edit = _parse_edit(edit_dict)

            # Find anchor
            anchor_idx, anchor_count = _find_anchor(lines, edit.anchor)

            if anchor_idx is None:
                errors.append(f"Edit {i+1}: Anchor not found: {edit.anchor.get('selected', 'N/A')}")
                skipped_count += 1
                continue

            # Validate uniqueness
            if validate_anchors and anchor_count > 1:
                errors.append(f"Edit {i+1}: Anchor not unique ({anchor_count} occurrences)")
                skipped_count += 1
                continue

            # Apply edit
            lines, success = _apply_single_edit(lines, edit, anchor_idx)

            if success:
                applied_count += 1
            else:
                errors.append(f"Edit {i+1}: Application failed")
                skipped_count += 1

        except Exception as e:
            errors.append(f"Edit {i+1}: {str(e)}")
            skipped_count += 1

    # Reconstruct code
    modified_code = '\n'.join(lines)

    success = applied_count > 0 and len(errors) == 0

    return EditResult(
        success=success,
        modified_code=modified_code,
        errors=errors,
        applied_count=applied_count,
        skipped_count=skipped_count
    )


def _parse_edit(edit_dict: Dict) -> EditOperation:
    """Parse edit dictionary into EditOperation."""
    return EditOperation(
        type=edit_dict.get('type', 'unknown'),
        anchor=edit_dict.get('anchor', {}),
        content=edit_dict.get('content'),
        description=edit_dict.get('description')
    )


def _find_anchor(
    lines: List[str],
    anchor: Dict
) -> Tuple[Optional[int], int]:
    """
    Find anchor in lines.

    CRITICAL FIX (P0.9.3 Phase 2.1): Added support for 'two_line' anchor type.
    This matches the fix in anchor_extractor.py to enable 2-line anchor usage.

    Args:
        lines: Source code lines
        anchor: Anchor specification dict

    Returns:
        (line_index, occurrence_count)
        line_index is 0-based, None if not found
    """
    anchor_type = anchor.get('type', 'line_pattern')
    selected_text = anchor.get('selected', '')

    if not selected_text:
        return (None, 0)

    # Special handling for two-line anchors
    if anchor_type == 'two_line':
        # selected_text format: "before_line\ntarget_line"
        if '\n' in selected_text:
            parts = selected_text.split('\n', 1)
            if len(parts) == 2:
                before_text, target_text = parts
                before_stripped = before_text.strip()
                target_stripped = target_text.strip()

                occurrences = []
                for i in range(1, len(lines)):  # Start from 1 (need before line)
                    if (lines[i-1].strip() == before_stripped and
                        lines[i].strip() == target_stripped):
                        occurrences.append(i)  # Index of target line

                if not occurrences:
                    return (None, 0)
                return (occurrences[0], len(occurrences))

        # Malformed two_line anchor
        return (None, 0)

    # Standard anchor types
    selected_stripped = selected_text.strip()
    occurrences = []

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        if anchor_type == 'line_pattern':
            # Exact match (after stripping)
            if line_stripped == selected_stripped:
                occurrences.append(i)

        elif anchor_type == 'function_def':
            # Match function definition
            if line_stripped.startswith('def ') and selected_stripped in line:
                occurrences.append(i)

        elif anchor_type == 'class_def':
            # Match class definition
            if line_stripped.startswith('class ') and selected_stripped in line:
                occurrences.append(i)

        elif anchor_type == 'import_stmt':
            # Match import
            if 'import ' in line and selected_stripped in line:
                occurrences.append(i)

        elif anchor_type == 'decorator':
            # Match decorator
            if line_stripped.startswith('@') and selected_stripped in line:
                occurrences.append(i)

    if not occurrences:
        return (None, 0)

    return (occurrences[0], len(occurrences))


def _apply_single_edit(
    lines: List[str],
    edit: EditOperation,
    anchor_idx: int
) -> Tuple[List[str], bool]:
    """
    Apply a single edit operation.

    Args:
        lines: Source code lines
        edit: Edit operation
        anchor_idx: Index of anchor line (0-based)

    Returns:
        (modified_lines, success)
    """
    try:
        if edit.type == 'insert_after':
            return _insert_after(lines, anchor_idx, edit.content or ''), True

        elif edit.type == 'insert_before':
            return _insert_before(lines, anchor_idx, edit.content or ''), True

        elif edit.type == 'replace':
            return _replace_line(lines, anchor_idx, edit.content or ''), True

        elif edit.type == 'delete':
            return _delete_line(lines, anchor_idx), True

        else:
            # Unknown edit type
            return lines, False

    except Exception:
        return lines, False


def _insert_after(lines: List[str], anchor_idx: int, content: str) -> List[str]:
    """Insert content after anchor line."""
    new_lines = lines[:anchor_idx + 1]
    # Use splitlines() to avoid empty strings from leading/trailing newlines
    content_lines = content.splitlines() if content else []
    new_lines.extend(content_lines)
    new_lines.extend(lines[anchor_idx + 1:])
    return new_lines


def _insert_before(lines: List[str], anchor_idx: int, content: str) -> List[str]:
    """Insert content before anchor line."""
    new_lines = lines[:anchor_idx]
    # Use splitlines() to avoid empty strings from leading/trailing newlines
    content_lines = content.splitlines() if content else []
    new_lines.extend(content_lines)
    new_lines.extend(lines[anchor_idx:])
    return new_lines


def _replace_line(lines: List[str], anchor_idx: int, content: str) -> List[str]:
    """
    Replace anchor line with content, preserving indentation.

    CRITICAL: The LLM provides content WITHOUT indentation.
    We must preserve the original line's indentation to avoid syntax errors.
    """
    # Get original line's indentation
    original_line = lines[anchor_idx]
    indent = len(original_line) - len(original_line.lstrip())
    indent_str = original_line[:indent]

    new_lines = lines[:anchor_idx]
    # Use splitlines() to avoid empty strings from leading/trailing newlines
    content_lines = content.splitlines() if content else []

    # Apply original indentation to each line of new content
    indented_content = []
    for line in content_lines:
        # Only add indentation if the line is not empty
        if line.strip():
            indented_content.append(indent_str + line.lstrip())
        else:
            indented_content.append(line)  # Keep empty lines as-is

    new_lines.extend(indented_content)
    new_lines.extend(lines[anchor_idx + 1:])
    return new_lines


def _delete_line(lines: List[str], anchor_idx: int) -> List[str]:
    """Delete anchor line."""
    return lines[:anchor_idx] + lines[anchor_idx + 1:]


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_edit_script(edit_script: Dict) -> Tuple[bool, List[str]]:
    """
    Validate edit script structure.

    Args:
        edit_script: Edit script dict

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    if 'file' not in edit_script:
        errors.append("Missing 'file' field")

    if 'edits' not in edit_script:
        errors.append("Missing 'edits' field")
        return (False, errors)

    edits = edit_script['edits']

    if not isinstance(edits, list):
        errors.append("'edits' must be a list")
        return (False, errors)

    # Validate each edit
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            errors.append(f"Edit {i+1}: Must be a dict")
            continue

        # Check required fields
        if 'type' not in edit:
            errors.append(f"Edit {i+1}: Missing 'type' field")

        if 'anchor' not in edit:
            errors.append(f"Edit {i+1}: Missing 'anchor' field")

        # Validate anchor
        anchor = edit.get('anchor', {})
        if not isinstance(anchor, dict):
            errors.append(f"Edit {i+1}: 'anchor' must be a dict")
        elif 'selected' not in anchor:
            errors.append(f"Edit {i+1}: Anchor missing 'selected' field")

        # Validate content (required for non-delete ops)
        edit_type = edit.get('type')
        if edit_type != 'delete' and 'content' not in edit:
            errors.append(f"Edit {i+1}: Missing 'content' field (required for {edit_type})")

    return (len(errors) == 0, errors)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def apply_edit_script_from_json(
    source_code: str,
    json_str: str,
    validate_anchors: bool = True
) -> EditResult:
    """
    Parse JSON and apply edit script.

    Args:
        source_code: Source code
        json_str: JSON edit script string
        validate_anchors: Whether to validate anchors

    Returns:
        EditResult
    """
    try:
        edit_script = json.loads(json_str)
    except json.JSONDecodeError as e:
        return EditResult(
            success=False,
            modified_code=source_code,
            errors=[f"JSON parse error: {e}"],
            applied_count=0,
            skipped_count=0
        )

    # Validate structure
    is_valid, validation_errors = validate_edit_script(edit_script)
    if not is_valid:
        return EditResult(
            success=False,
            modified_code=source_code,
            errors=validation_errors,
            applied_count=0,
            skipped_count=0
        )

    # Apply edits
    return apply_edit_script(source_code, edit_script, validate_anchors)
