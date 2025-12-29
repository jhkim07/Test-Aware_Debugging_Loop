"""
Component 3: Edit Validator

Validates edit scripts before application.
Checks anchor uniqueness, existence, and structural correctness.
"""

from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass

from .anchor_extractor import find_anchor_in_source, extract_anchor_candidates


@dataclass
class ValidationError:
    """Represents a validation error."""
    edit_index: int  # 0-based index of edit in script
    error_type: str  # 'anchor_not_found', 'anchor_not_unique', 'structure', etc.
    message: str
    anchor_text: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of edit script validation."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[str]


# ============================================================================
# ANCHOR VALIDATION
# ============================================================================

def validate_anchor_existence(
    source_code: str,
    anchor: Dict,
    edit_index: int
) -> Optional[ValidationError]:
    """
    Validate that anchor exists in source code.

    Args:
        source_code: Source code to search
        anchor: Anchor specification dict
        edit_index: Index of edit (for error reporting)

    Returns:
        ValidationError if anchor not found, None otherwise
    """
    anchor_text = anchor.get('selected', '')
    anchor_type = anchor.get('type', 'line_pattern')

    if not anchor_text:
        return ValidationError(
            edit_index=edit_index,
            error_type='anchor_empty',
            message="Anchor 'selected' field is empty",
            anchor_text=None
        )

    # Search for anchor
    line_idx, count = find_anchor_in_source(source_code, anchor_text, anchor_type)

    if line_idx is None or count == 0:
        return ValidationError(
            edit_index=edit_index,
            error_type='anchor_not_found',
            message=f"Anchor not found in source: {anchor_text[:50]}...",
            anchor_text=anchor_text
        )

    return None


def validate_anchor_uniqueness(
    source_code: str,
    anchor: Dict,
    edit_index: int,
    require_unique: bool = True
) -> Optional[ValidationError]:
    """
    Validate that anchor is unique in source code.

    Args:
        source_code: Source code to search
        anchor: Anchor specification dict
        edit_index: Index of edit (for error reporting)
        require_unique: If True, require exactly 1 occurrence

    Returns:
        ValidationError if anchor not unique, None otherwise
    """
    if not require_unique:
        return None

    anchor_text = anchor.get('selected', '')
    anchor_type = anchor.get('type', 'line_pattern')

    if not anchor_text:
        return None  # Already caught by existence check

    # Count occurrences
    line_idx, count = find_anchor_in_source(source_code, anchor_text, anchor_type)

    if count > 1:
        return ValidationError(
            edit_index=edit_index,
            error_type='anchor_not_unique',
            message=f"Anchor appears {count} times (must be unique): {anchor_text[:50]}...",
            anchor_text=anchor_text
        )

    return None


def validate_anchors_in_edit_script(
    source_code: str,
    edit_script: Dict,
    require_unique: bool = True
) -> List[ValidationError]:
    """
    Validate all anchors in edit script.

    Args:
        source_code: Source code
        edit_script: Edit script dict
        require_unique: If True, require unique anchors

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    edits = edit_script.get('edits', [])

    for i, edit in enumerate(edits):
        anchor = edit.get('anchor', {})

        # Check existence
        existence_error = validate_anchor_existence(source_code, anchor, i)
        if existence_error:
            errors.append(existence_error)
            continue  # Skip uniqueness check if not found

        # Check uniqueness
        uniqueness_error = validate_anchor_uniqueness(
            source_code, anchor, i, require_unique
        )
        if uniqueness_error:
            errors.append(uniqueness_error)

    return errors


# ============================================================================
# STRUCTURE VALIDATION
# ============================================================================

def validate_edit_script_structure(edit_script: Dict) -> List[ValidationError]:
    """
    Validate edit script structure.

    Checks required fields, types, and value constraints.

    Args:
        edit_script: Edit script dict

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required top-level fields
    if 'file' not in edit_script:
        errors.append(ValidationError(
            edit_index=-1,
            error_type='structure',
            message="Missing required field 'file'"
        ))

    if 'edits' not in edit_script:
        errors.append(ValidationError(
            edit_index=-1,
            error_type='structure',
            message="Missing required field 'edits'"
        ))
        return errors  # Can't continue without edits

    edits = edit_script['edits']

    if not isinstance(edits, list):
        errors.append(ValidationError(
            edit_index=-1,
            error_type='structure',
            message="Field 'edits' must be a list"
        ))
        return errors

    # Validate each edit
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            errors.append(ValidationError(
                edit_index=i,
                error_type='structure',
                message="Edit must be a dict"
            ))
            continue

        # Check required fields
        if 'type' not in edit:
            errors.append(ValidationError(
                edit_index=i,
                error_type='structure',
                message="Missing required field 'type'"
            ))

        if 'anchor' not in edit:
            errors.append(ValidationError(
                edit_index=i,
                error_type='structure',
                message="Missing required field 'anchor'"
            ))

        # Validate type
        edit_type = edit.get('type')
        valid_types = {'insert_before', 'insert_after', 'replace', 'delete'}
        if edit_type not in valid_types:
            errors.append(ValidationError(
                edit_index=i,
                error_type='structure',
                message=f"Invalid edit type '{edit_type}'. Must be one of: {valid_types}"
            ))

        # Validate anchor structure
        anchor = edit.get('anchor', {})
        if not isinstance(anchor, dict):
            errors.append(ValidationError(
                edit_index=i,
                error_type='structure',
                message="Field 'anchor' must be a dict"
            ))
        elif 'selected' not in anchor:
            errors.append(ValidationError(
                edit_index=i,
                error_type='structure',
                message="Anchor missing required field 'selected'"
            ))

        # Validate content (required for non-delete operations)
        if edit_type != 'delete' and 'content' not in edit:
            errors.append(ValidationError(
                edit_index=i,
                error_type='structure',
                message=f"Edit type '{edit_type}' requires 'content' field"
            ))

    return errors


# ============================================================================
# COMPREHENSIVE VALIDATION
# ============================================================================

def validate_edit_script(
    source_code: str,
    edit_script: Dict,
    require_unique_anchors: bool = True,
    skip_anchor_validation: bool = False
) -> ValidationResult:
    """
    Comprehensive edit script validation.

    Args:
        source_code: Source code to validate against
        edit_script: Edit script to validate
        require_unique_anchors: If True, require unique anchors
        skip_anchor_validation: If True, skip anchor existence/uniqueness checks

    Returns:
        ValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    # Step 1: Validate structure
    structure_errors = validate_edit_script_structure(edit_script)
    errors.extend(structure_errors)

    # If structure is invalid, can't continue
    if structure_errors:
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings
        )

    # Step 2: Validate anchors (if enabled)
    if not skip_anchor_validation:
        anchor_errors = validate_anchors_in_edit_script(
            source_code,
            edit_script,
            require_unique=require_unique_anchors
        )
        errors.extend(anchor_errors)

    # Step 3: Check for warnings
    edits = edit_script.get('edits', [])

    # Warn if no edits
    if len(edits) == 0:
        warnings.append("Edit script contains no edits")

    # Warn if too many edits (might be complex)
    if len(edits) > 10:
        warnings.append(f"Edit script contains {len(edits)} edits (might be complex)")

    # Warn if missing descriptions
    missing_descriptions = sum(
        1 for edit in edits if not edit.get('description')
    )
    if missing_descriptions > 0:
        warnings.append(
            f"{missing_descriptions}/{len(edits)} edits missing 'description' field"
        )

    # Determine validity
    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_validation_errors(errors: List[ValidationError]) -> str:
    """
    Format validation errors for display.

    Args:
        errors: List of validation errors

    Returns:
        Formatted error string
    """
    if not errors:
        return "No errors"

    lines = []
    for error in errors:
        if error.edit_index >= 0:
            prefix = f"Edit {error.edit_index + 1}"
        else:
            prefix = "Script"

        lines.append(f"[{prefix}] {error.error_type}: {error.message}")

        if error.anchor_text:
            # Show first 100 chars of anchor
            anchor_preview = error.anchor_text[:100]
            if len(error.anchor_text) > 100:
                anchor_preview += "..."
            lines.append(f"  Anchor: {anchor_preview}")

    return '\n'.join(lines)


def format_validation_result(result: ValidationResult) -> str:
    """
    Format validation result for display.

    Args:
        result: ValidationResult

    Returns:
        Formatted result string
    """
    lines = []

    if result.is_valid:
        lines.append("✓ Edit script is valid")
    else:
        lines.append("✗ Edit script validation failed")

    if result.errors:
        lines.append(f"\nErrors ({len(result.errors)}):")
        lines.append(format_validation_errors(result.errors))

    if result.warnings:
        lines.append(f"\nWarnings ({len(result.warnings)}):")
        for warning in result.warnings:
            lines.append(f"  - {warning}")

    return '\n'.join(lines)


# ============================================================================
# ANCHOR CANDIDATE VALIDATION
# ============================================================================

def validate_anchor_is_system_generated(
    anchor_text: str,
    source_code: str,
    edit_index: int
) -> Optional[ValidationError]:
    """
    Validate that anchor comes from system-extracted candidates.

    This prevents LLM hallucination by ensuring anchor actually exists
    in the source code.

    Args:
        anchor_text: Anchor text to validate
        source_code: Source code
        edit_index: Index of edit (for error reporting)

    Returns:
        ValidationError if anchor not in source, None otherwise
    """
    # Extract all possible anchors from source
    candidates = extract_anchor_candidates(source_code)

    # Check if anchor matches any candidate
    for candidate_list in candidates.values():
        for candidate in candidate_list:
            if candidate.text.strip() == anchor_text.strip():
                return None  # Found match

    # No match found - anchor was likely hallucinated
    return ValidationError(
        edit_index=edit_index,
        error_type='anchor_hallucinated',
        message=f"Anchor not found in system-extracted candidates (possible hallucination): {anchor_text[:50]}...",
        anchor_text=anchor_text
    )


def validate_all_anchors_system_generated(
    source_code: str,
    edit_script: Dict
) -> List[ValidationError]:
    """
    Validate that all anchors are system-generated.

    Args:
        source_code: Source code
        edit_script: Edit script

    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []

    edits = edit_script.get('edits', [])

    for i, edit in enumerate(edits):
        anchor = edit.get('anchor', {})
        anchor_text = anchor.get('selected', '')

        if anchor_text:
            error = validate_anchor_is_system_generated(
                anchor_text, source_code, i
            )
            if error:
                errors.append(error)

    return errors


# ============================================================================
# DUPLICATE CODE DETECTION
# ============================================================================

def check_for_duplicate_code_patterns(
    source_code: str,
    edit_script: Dict
) -> List[str]:
    """
    Check if edit script would create duplicate code patterns.

    Detects cases where LLM used "insert" instead of "replace",
    which creates duplicates of existing code.

    Args:
        source_code: Original source code
        edit_script: Edit script to check

    Returns:
        List of warning messages (empty if no duplicates detected)
    """
    warnings = []

    edits = edit_script.get('edits', [])
    lines = source_code.split('\n')

    for i, edit in enumerate(edits):
        edit_type = edit.get('type')

        # Only check insert operations (replace is safe)
        if edit_type not in ('insert_before', 'insert_after'):
            continue

        content = edit.get('content', '')
        if not content:
            continue

        # Get content lines
        content_lines = content.strip().split('\n')

        # Check if any content line already exists in source
        for content_line in content_lines:
            content_stripped = content_line.strip()

            # Skip empty lines and comments
            if not content_stripped or content_stripped.startswith('#'):
                continue

            # Check if this exact line exists in source
            for src_line in lines:
                if src_line.strip() == content_stripped:
                    warnings.append(
                        f"Edit {i+1}: Line '{content_stripped[:60]}...' already exists in source. "
                        f"Consider using 'replace' instead of '{edit_type}' to avoid duplicates."
                    )
                    break

    return warnings


def validate_no_duplicate_code(
    source_code: str,
    edit_script: Dict
) -> ValidationResult:
    """
    Validate that edit script won't create duplicate code.

    This is a specialized validation to catch the common LLM error
    of using "insert" when "replace" should be used.

    Args:
        source_code: Original source code
        edit_script: Edit script

    Returns:
        ValidationResult with warnings for potential duplicates
    """
    warnings = check_for_duplicate_code_patterns(source_code, edit_script)

    # No errors, only warnings
    return ValidationResult(
        is_valid=True,  # Still valid, but with warnings
        errors=[],
        warnings=warnings
    )
