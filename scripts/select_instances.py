#!/usr/bin/env python3
"""
Instance selection script for scale-up phases.

Supports multiple sampling strategies:
- stratified: Repository and difficulty-based stratification
- representative: Maximize diversity across all dimensions
- random: Simple random sampling
"""

import json
import random
import argparse
from pathlib import Path
from typing import List, Dict, Set
from collections import Counter, defaultdict


def load_swebench_lite(data_path: str) -> List[Dict]:
    """Load SWE-bench Lite dataset."""
    with open(data_path, 'r') as f:
        return [json.loads(line) for line in f]


def extract_repo(instance_id: str) -> str:
    """Extract repository name from instance ID."""
    # Format: repo__owner__repo-number
    parts = instance_id.split('__')
    if len(parts) >= 2:
        return parts[0]
    return 'unknown'


def estimate_difficulty(instance: Dict) -> str:
    """Estimate difficulty based on heuristics."""
    # Heuristics:
    # - Number of test files modified
    # - Patch complexity
    # - Problem statement length

    # Simple heuristic for now
    problem_length = len(instance.get('problem_statement', ''))

    if problem_length < 500:
        return 'easy'
    elif problem_length < 1000:
        return 'medium'
    elif problem_length < 2000:
        return 'hard'
    else:
        return 'very_hard'


def stratified_sampling(
    instances: List[Dict],
    n: int,
    ensure_baseline: List[str] = None
) -> List[str]:
    """Stratified sampling by repository and difficulty."""

    # Group by repository
    repo_groups = defaultdict(list)
    for inst in instances:
        repo = extract_repo(inst['instance_id'])
        repo_groups[repo].append(inst)

    # Calculate proportional allocation
    total = len(instances)
    allocation = {
        repo: max(1, int(len(insts) / total * n))
        for repo, insts in repo_groups.items()
    }

    # Adjust to exactly n
    current_total = sum(allocation.values())
    if current_total < n:
        # Add to largest repositories
        sorted_repos = sorted(allocation.keys(), key=lambda r: len(repo_groups[r]), reverse=True)
        for repo in sorted_repos:
            if current_total >= n:
                break
            allocation[repo] += 1
            current_total += 1

    # Sample from each repository
    selected = []
    for repo, count in allocation.items():
        repo_instances = repo_groups[repo]
        if len(repo_instances) <= count:
            selected.extend([inst['instance_id'] for inst in repo_instances])
        else:
            sampled = random.sample(repo_instances, count)
            selected.extend([inst['instance_id'] for inst in sampled])

    # Ensure baseline instances are included
    if ensure_baseline:
        selected_set = set(selected)
        for baseline_id in ensure_baseline:
            if baseline_id not in selected_set:
                # Replace a random instance from same repo
                baseline_repo = extract_repo(baseline_id)
                for i, inst_id in enumerate(selected):
                    if extract_repo(inst_id) == baseline_repo and inst_id not in ensure_baseline:
                        selected[i] = baseline_id
                        break

    return selected[:n]


def representative_sampling(
    instances: List[Dict],
    n: int,
    ensure_baseline: List[str] = None
) -> List[str]:
    """Representative sampling for maximum diversity."""

    # Score instances by diversity contribution
    repo_counts = Counter(extract_repo(inst['instance_id']) for inst in instances)

    def diversity_score(inst: Dict) -> float:
        """Higher score = more valuable for diversity."""
        repo = extract_repo(inst['instance_id'])

        # Prefer underrepresented repositories
        repo_score = 1.0 / repo_counts[repo]

        # Prefer varied difficulty
        difficulty = estimate_difficulty(inst)
        diff_score = {
            'easy': 1.0,
            'medium': 1.2,
            'hard': 1.5,
            'very_hard': 2.0
        }[difficulty]

        return repo_score * diff_score

    # Sort by diversity score
    scored = [(inst, diversity_score(inst)) for inst in instances]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Select top n
    selected = [inst['instance_id'] for inst, _ in scored[:n]]

    # Ensure baseline instances
    if ensure_baseline:
        selected_set = set(selected)
        for baseline_id in ensure_baseline:
            if baseline_id not in selected_set:
                # Replace lowest scoring non-baseline
                for i in range(len(selected) - 1, -1, -1):
                    if selected[i] not in ensure_baseline:
                        selected[i] = baseline_id
                        break

    return selected[:n]


def random_sampling(
    instances: List[Dict],
    n: int,
    ensure_baseline: List[str] = None
) -> List[str]:
    """Simple random sampling."""

    sampled = random.sample(instances, min(n, len(instances)))
    selected = [inst['instance_id'] for inst in sampled]

    # Ensure baseline instances
    if ensure_baseline:
        selected_set = set(selected)
        for baseline_id in ensure_baseline:
            if baseline_id not in selected_set:
                # Replace random non-baseline
                for i in range(len(selected)):
                    if selected[i] not in ensure_baseline:
                        selected[i] = baseline_id
                        break

    return selected[:n]


def main():
    parser = argparse.ArgumentParser(description='Select instances for scale-up testing')
    parser.add_argument('--data', type=str,
                       default='data/swe-bench-lite-instances.jsonl',
                       help='Path to SWE-bench Lite data')
    parser.add_argument('--strategy', type=str,
                       choices=['stratified', 'representative', 'random'],
                       default='stratified',
                       help='Sampling strategy')
    parser.add_argument('--n', type=int, required=True,
                       help='Number of instances to select')
    parser.add_argument('--output', type=str, required=True,
                       help='Output file path')
    parser.add_argument('--ensure_baseline', action='store_true',
                       help='Ensure baseline 4 instances are included')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility')

    args = parser.parse_args()

    # Set random seed
    random.seed(args.seed)

    # Load data
    print(f"Loading SWE-bench Lite data from {args.data}...")
    instances = load_swebench_lite(args.data)
    print(f"Loaded {len(instances)} instances")

    # Baseline instances
    baseline_ids = [
        'astropy__astropy-12907',
        'sympy__sympy-20590',
        'astropy__astropy-14182',
        'astropy__astropy-14365',
    ] if args.ensure_baseline else None

    # Select instances
    print(f"Selecting {args.n} instances using {args.strategy} strategy...")

    if args.strategy == 'stratified':
        selected = stratified_sampling(instances, args.n, baseline_ids)
    elif args.strategy == 'representative':
        selected = representative_sampling(instances, args.n, baseline_ids)
    else:
        selected = random_sampling(instances, args.n, baseline_ids)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        for instance_id in selected:
            f.write(f"{instance_id}\n")

    print(f"Selected {len(selected)} instances")
    print(f"Written to {args.output}")

    # Print summary
    repo_dist = Counter(extract_repo(iid) for iid in selected)
    print("\nRepository distribution:")
    for repo, count in repo_dist.most_common():
        print(f"  {repo}: {count}")

    if baseline_ids:
        baseline_included = sum(1 for bid in baseline_ids if bid in selected)
        print(f"\nBaseline instances included: {baseline_included}/{len(baseline_ids)}")


if __name__ == '__main__':
    main()
