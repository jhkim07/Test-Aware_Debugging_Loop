"""
Component 3: Edit Script System

System-generated anchors + LLM-selected edits → Deterministic application.

This package provides a complete edit script workflow:
1. Extract anchor candidates from source (AST-based)
2. Generate LLM prompts with system-extracted anchors
3. Validate edit scripts (anchors exist, are unique)
4. Apply edits deterministically
5. Generate diffs for SWE-bench

Main workflow:
```python
from bench_agent.editor import (
    extract_anchor_candidates,
    generate_test_edit_prompt,
    validate_edit_script,
    apply_edit_script,
    generate_unified_diff
)

# 1. Extract anchors
candidates = extract_anchor_candidates(source_code, target_line=50)

# 2. Generate prompt (LLM gets candidates, not free-form access)
prompt = generate_test_edit_prompt(
    filepath="test_file.py",
    source_code=source_code,
    task_description="Add test for edge case",
    candidates=candidates
)

# 3. LLM generates edit script (JSON)
edit_script = llm.generate(prompt)

# 4. Validate before applying
validation = validate_edit_script(source_code, edit_script)
if not validation.is_valid:
    print(validation.errors)
    return

# 5. Apply edits
result = apply_edit_script(source_code, edit_script)
if result.success:
    modified_code = result.modified_code

# 6. Generate diff
diff = generate_unified_diff(source_code, modified_code, filepath)
```
"""

# Anchor extraction
from .anchor_extractor import (
    AnchorCandidate,
    extract_anchor_candidates,
    find_anchor_in_source,
    is_anchor_unique,
    filter_unique_candidates,
    filter_top_level_only,
    get_candidates_near_line,
    format_candidates_for_prompt,
    count_candidates
)

# Edit application
from .edit_applier import (
    EditOperation,
    EditResult,
    apply_edit_script,
    apply_edit_script_from_json,
    validate_edit_script as validate_edit_script_structure
)

# Edit validation
from .edit_validator import (
    ValidationError,
    ValidationResult,
    validate_edit_script,
    validate_anchor_existence,
    validate_anchor_uniqueness,
    validate_anchors_in_edit_script,
    validate_edit_script_structure,
    format_validation_errors,
    format_validation_result
)

# Diff generation
from .diff_generator import (
    DiffResult,
    generate_unified_diff,
    generate_diff_with_stats,
    compute_diff_stats,
    is_empty_diff,
    validate_diff_format,
    create_patch_from_edits,
    verify_patch_applies,
    generate_multi_file_diff
)

# Prompt generation
from .edit_script_generator import (
    EDIT_SCRIPT_SYSTEM_PROMPT,
    generate_test_edit_prompt,
    generate_code_edit_prompt,
    generate_focused_edit_prompt,
    generate_iterative_edit_prompt,
    create_edit_prompt
)

# Candidate ranking
from .candidate_ranker import (
    RankedCandidate,
    rank_candidates,
    rank_candidates_by_type,
    get_best_candidates,
    get_unique_best_candidates,
    recommend_anchors_for_edit,
    format_ranked_candidates
)

__all__ = [
    # Anchor extraction
    'AnchorCandidate',
    'extract_anchor_candidates',
    'find_anchor_in_source',
    'is_anchor_unique',
    'filter_unique_candidates',
    'filter_top_level_only',
    'get_candidates_near_line',
    'format_candidates_for_prompt',
    'count_candidates',

    # Edit application
    'EditOperation',
    'EditResult',
    'apply_edit_script',
    'apply_edit_script_from_json',

    # Edit validation
    'ValidationError',
    'ValidationResult',
    'validate_edit_script',
    'validate_anchor_existence',
    'validate_anchor_uniqueness',
    'validate_anchors_in_edit_script',
    'validate_edit_script_structure',
    'format_validation_errors',
    'format_validation_result',

    # Diff generation
    'DiffResult',
    'generate_unified_diff',
    'generate_diff_with_stats',
    'compute_diff_stats',
    'is_empty_diff',
    'validate_diff_format',
    'create_patch_from_edits',
    'verify_patch_applies',
    'generate_multi_file_diff',

    # Prompt generation
    'EDIT_SCRIPT_SYSTEM_PROMPT',
    'generate_test_edit_prompt',
    'generate_code_edit_prompt',
    'generate_focused_edit_prompt',
    'generate_iterative_edit_prompt',
    'create_edit_prompt',

    # Candidate ranking
    'RankedCandidate',
    'rank_candidates',
    'rank_candidates_by_type',
    'get_best_candidates',
    'get_unique_best_candidates',
    'recommend_anchors_for_edit',
    'format_ranked_candidates',
]
