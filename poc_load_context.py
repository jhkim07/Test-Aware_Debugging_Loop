#!/usr/bin/env python3
"""
Load real context for astropy-14182 from dataset.

This prepares the context dict for poc_two_stage.py
"""

import json
from datasets import load_dataset
from pathlib import Path


def load_astropy_14182_context():
    """Load real context for astropy-14182."""

    # Load SWE-bench dataset
    print("Loading SWE-bench dataset...")
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split='test')

    # Find astropy-14182
    instance = None
    for item in ds:
        if item['instance_id'] == 'astropy__astropy-14182':
            instance = item
            break

    if not instance:
        raise ValueError("astropy-14182 not found in dataset")

    print(f"Found instance: {instance['instance_id']}")

    # Extract key fields
    context = {
        "instance_id": instance['instance_id'],
        "problem_statement": instance['problem_statement'],
        "reference_patch": instance.get('patch', ''),
        "reference_test_patch": instance.get('test_patch', ''),
        "repo": instance['repo'],
        "base_commit": instance['base_commit'],
        "version": instance.get('version', 'unknown')
    }

    # Save to file for poc_two_stage.py
    output_file = Path("outputs/poc_two_stage/astropy_14182_context.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(context, f, indent=2)

    print(f"\nContext saved to: {output_file}")
    print(f"\nProblem Statement Preview:")
    print(context['problem_statement'][:500])
    print("\n...")

    print(f"\nReference Patch Preview:")
    print(context['reference_patch'][:500] if context['reference_patch'] else "N/A")
    print("\n...")

    return context


if __name__ == "__main__":
    try:
        context = load_astropy_14182_context()
        print("\n✅ Context loaded successfully")
    except Exception as e:
        print(f"\n❌ Failed to load context: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
