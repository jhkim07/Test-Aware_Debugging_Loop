#!/usr/bin/env python3
"""
Setup SWE-bench Instance Repository

Clones and prepares a repository for a specific SWE-bench instance.
This enables Component 3 to read source files before harness evaluation.

Usage:
    python scripts/setup_instance_repo.py astropy__astropy-14182
"""

import subprocess
import sys
from pathlib import Path
from datasets import load_dataset


def setup_instance_repository(instance_id: str, force: bool = False) -> tuple[bool, str]:
    """
    Setup repository for a SWE-bench instance.

    Args:
        instance_id: SWE-bench instance ID (e.g., 'astropy__astropy-14182')
        force: If True, remove existing repo and re-clone

    Returns:
        (success, message)
    """
    print(f"\n{'='*80}")
    print(f"Setting up repository for instance: {instance_id}")
    print(f"{'='*80}\n")

    # Step 1: Load instance metadata from SWE-bench dataset
    print("Step 1: Loading instance metadata from SWE-bench dataset...")
    try:
        ds = load_dataset('princeton-nlp/SWE-bench_Lite', split='test')
        instances = [x for x in ds if x['instance_id'] == instance_id]

        if not instances:
            return (False, f"Instance {instance_id} not found in SWE-bench_Lite dataset")

        inst = instances[0]
        repo_name = inst['repo']  # e.g., 'astropy/astropy'
        base_commit = inst['base_commit']

        print(f"✓ Found instance metadata:")
        print(f"  - Repository: {repo_name}")
        print(f"  - Base commit: {base_commit}")

    except Exception as e:
        return (False, f"Failed to load instance metadata: {e}")

    # Step 2: Determine target path
    repo_path = Path(f"/tmp/{repo_name.replace('/', '_')}_{instance_id}")

    print(f"\nStep 2: Target repository path:")
    print(f"  {repo_path}")

    # Check if already exists
    if repo_path.exists():
        if force:
            print(f"\n⚠️  Repository already exists, removing (force=True)...")
            import shutil
            shutil.rmtree(repo_path)
        else:
            print(f"\n✓ Repository already exists at {repo_path}")
            print(f"  Use --force to re-clone")
            return (True, f"Repository already exists: {repo_path}")

    # Step 3: Clone repository
    print(f"\nStep 3: Cloning repository...")
    github_url = f"https://github.com/{repo_name}.git"

    try:
        # Clone with depth=1 for faster cloning
        print(f"  Executing: git clone --depth 1 {github_url} {repo_path}")
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', github_url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        if result.returncode != 0:
            return (False, f"Git clone failed: {result.stderr}")

        print(f"✓ Repository cloned successfully")

    except subprocess.TimeoutExpired:
        return (False, "Git clone timed out (5 minutes)")
    except Exception as e:
        return (False, f"Git clone error: {e}")

    # Step 4: Checkout specific commit
    print(f"\nStep 4: Checking out base commit {base_commit}...")

    try:
        # First, fetch the full history to get the specific commit
        print(f"  Fetching commit history...")
        result = subprocess.run(
            ['git', 'fetch', '--unshallow'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300
        )

        # Checkout the base commit
        print(f"  Executing: git checkout {base_commit}")
        result = subprocess.run(
            ['git', 'checkout', base_commit],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return (False, f"Git checkout failed: {result.stderr}")

        print(f"✓ Checked out commit {base_commit}")

    except subprocess.TimeoutExpired:
        return (False, "Git checkout timed out")
    except Exception as e:
        return (False, f"Git checkout error: {e}")

    # Step 5: Verify repository is ready
    print(f"\nStep 5: Verifying repository...")

    # Check if key Python files exist
    py_files = list(repo_path.glob("**/*.py"))
    print(f"✓ Found {len(py_files)} Python files")

    if len(py_files) == 0:
        return (False, "No Python files found in repository")

    # Success
    print(f"\n{'='*80}")
    print(f"✅ Repository setup complete!")
    print(f"{'='*80}")
    print(f"\nRepository ready at: {repo_path}")
    print(f"Python files: {len(py_files)}")
    print(f"\nYou can now run Component 3 on this instance:")
    print(f"  USE_EDIT_SCRIPT=1 python scripts/run_mvp.py \\")
    print(f"    --config configs/p091_component3_single_test.yaml \\")
    print(f"    --run-id p091-c3-test-$(date +%Y%m%d-%H%M%S)")

    return (True, f"Repository setup complete: {repo_path}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Setup SWE-bench instance repository for Component 3 testing'
    )
    parser.add_argument(
        'instance_id',
        help='SWE-bench instance ID (e.g., astropy__astropy-14182)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-clone if repository already exists'
    )

    args = parser.parse_args()

    # Setup repository
    success, message = setup_instance_repository(args.instance_id, args.force)

    if success:
        print(f"\n✅ SUCCESS: {message}\n")
        return 0
    else:
        print(f"\n❌ FAILED: {message}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
