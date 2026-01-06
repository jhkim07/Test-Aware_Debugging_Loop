#!/usr/bin/env python3
"""
Comprehensive analysis script for scale-up phase results.

Generates:
- Distribution statistics
- Metric correlations
- Failure mode analysis
- Visualization plots
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict, Counter
import numpy as np
from dataclasses import dataclass


@dataclass
class InstanceMetrics:
    """Metrics for a single instance."""
    instance_id: str
    overall: float
    hfs: float
    tss: float
    brs: float
    overfit_gap: float
    patch_size: int
    iterations: int
    time_seconds: float
    cost_dollars: float
    success: bool


def load_instance_metrics(output_dir: Path) -> List[InstanceMetrics]:
    """Load metrics from all instance outputs."""
    metrics_list = []

    for instance_dir in output_dir.iterdir():
        if not instance_dir.is_dir():
            continue

        metrics_file = instance_dir / 'metrics.json'
        if not metrics_file.exists():
            continue

        with open(metrics_file, 'r') as f:
            data = json.load(f)

        metrics = InstanceMetrics(
            instance_id=instance_dir.name,
            overall=data.get('overall_score', 0.0),
            hfs=data.get('hfs', 0.0),
            tss=data.get('tss', 0.0),
            brs=data.get('brs', 0.0),
            overfit_gap=data.get('overfit_gap', 0.0),
            patch_size=data.get('patch_size_bytes', 0),
            iterations=data.get('iterations', 0),
            time_seconds=data.get('time_seconds', 0.0),
            cost_dollars=data.get('cost_dollars', 0.0),
            success=data.get('overall_score', 0.0) >= 0.5,
        )
        metrics_list.append(metrics)

    return metrics_list


def calculate_statistics(values: List[float]) -> Dict:
    """Calculate comprehensive statistics."""
    if not values:
        return {}

    arr = np.array(values)
    return {
        'count': len(values),
        'mean': float(np.mean(arr)),
        'std': float(np.std(arr)),
        'min': float(np.min(arr)),
        'q1': float(np.percentile(arr, 25)),
        'median': float(np.median(arr)),
        'q3': float(np.percentile(arr, 75)),
        'max': float(np.max(arr)),
        'iqr': float(np.percentile(arr, 75) - np.percentile(arr, 25)),
        'cv': float(np.std(arr) / np.mean(arr)) if np.mean(arr) > 0 else 0.0,
    }


def generate_distribution(values: List[float], bins: List[float]) -> Dict:
    """Generate distribution histogram."""
    hist, _ = np.histogram(values, bins=bins)
    return {
        'bins': [f"[{bins[i]:.2f}-{bins[i+1]:.2f})" for i in range(len(bins)-1)],
        'counts': hist.tolist(),
        'percentages': (hist / len(values) * 100).tolist() if values else []
    }


def extract_repo(instance_id: str) -> str:
    """Extract repository name."""
    return instance_id.split('__')[0] if '__' in instance_id else 'unknown'


def analyze_metrics(metrics_list: List[InstanceMetrics]) -> Dict:
    """Comprehensive metric analysis."""

    if not metrics_list:
        return {'error': 'No metrics found'}

    # Overall statistics
    overall_stats = {
        'overall': calculate_statistics([m.overall for m in metrics_list]),
        'hfs': calculate_statistics([m.hfs for m in metrics_list]),
        'tss': calculate_statistics([m.tss for m in metrics_list]),
        'brs': calculate_statistics([m.brs for m in metrics_list]),
        'overfit_gap': calculate_statistics([m.overfit_gap for m in metrics_list]),
        'patch_size': calculate_statistics([m.patch_size for m in metrics_list]),
        'iterations': calculate_statistics([m.iterations for m in metrics_list]),
        'time_seconds': calculate_statistics([m.time_seconds for m in metrics_list]),
        'cost_dollars': calculate_statistics([m.cost_dollars for m in metrics_list]),
    }

    # Distributions
    distributions = {
        'overall': generate_distribution(
            [m.overall for m in metrics_list],
            [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        ),
        'overfit_gap': generate_distribution(
            [m.overfit_gap for m in metrics_list],
            [-0.2, -0.1, 0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
        ),
    }

    # BRS analysis
    brs_counts = Counter([m.brs for m in metrics_list])
    brs_analysis = {
        'brs_0': brs_counts.get(0.0, 0),
        'brs_1': brs_counts.get(1.0, 0),
        'brs_rate': brs_counts.get(1.0, 0) / len(metrics_list) if metrics_list else 0.0,
    }

    # Success analysis
    success_count = sum(1 for m in metrics_list if m.success)
    success_rate = success_count / len(metrics_list) if metrics_list else 0.0

    # Repository breakdown
    repo_metrics = defaultdict(list)
    for m in metrics_list:
        repo = extract_repo(m.instance_id)
        repo_metrics[repo].append(m)

    repo_analysis = {}
    for repo, repo_ms in repo_metrics.items():
        repo_analysis[repo] = {
            'count': len(repo_ms),
            'mean_overall': np.mean([m.overall for m in repo_ms]),
            'mean_brs': np.mean([m.brs for m in repo_ms]),
            'success_rate': sum(1 for m in repo_ms if m.success) / len(repo_ms),
        }

    # Overfit risk categorization
    overfit_categories = {
        'excellent': sum(1 for m in metrics_list if m.overfit_gap < 0.05),
        'good': sum(1 for m in metrics_list if 0.05 <= m.overfit_gap < 0.10),
        'acceptable': sum(1 for m in metrics_list if 0.10 <= m.overfit_gap < 0.15),
        'concerning': sum(1 for m in metrics_list if m.overfit_gap >= 0.15),
    }

    # Performance categories
    performance_categories = {
        'failed': sum(1 for m in metrics_list if m.overall < 0.3),
        'partial': sum(1 for m in metrics_list if 0.3 <= m.overall < 0.6),
        'good': sum(1 for m in metrics_list if 0.6 <= m.overall < 0.8),
        'excellent': sum(1 for m in metrics_list if m.overall >= 0.8),
    }

    # Total cost and time
    total_cost = sum(m.cost_dollars for m in metrics_list)
    total_time_hours = sum(m.time_seconds for m in metrics_list) / 3600

    return {
        'summary': {
            'total_instances': len(metrics_list),
            'success_count': success_count,
            'success_rate': success_rate,
            'total_cost': total_cost,
            'avg_cost_per_instance': total_cost / len(metrics_list) if metrics_list else 0.0,
            'total_time_hours': total_time_hours,
            'avg_time_minutes': (total_time_hours * 60) / len(metrics_list) if metrics_list else 0.0,
        },
        'statistics': overall_stats,
        'distributions': distributions,
        'brs_analysis': brs_analysis,
        'overfit_categories': overfit_categories,
        'performance_categories': performance_categories,
        'repository_breakdown': repo_analysis,
    }


def generate_report(analysis: Dict, output_file: str):
    """Generate markdown report."""

    lines = [
        "# Scale-up Phase Results Analysis",
        "",
        "## Summary",
        "",
        f"- **Total Instances**: {analysis['summary']['total_instances']}",
        f"- **Success Rate**: {analysis['summary']['success_rate']:.1%}",
        f"- **Total Cost**: ${analysis['summary']['total_cost']:.2f}",
        f"- **Avg Cost/Instance**: ${analysis['summary']['avg_cost_per_instance']:.2f}",
        f"- **Total Time**: {analysis['summary']['total_time_hours']:.1f} hours",
        f"- **Avg Time/Instance**: {analysis['summary']['avg_time_minutes']:.1f} minutes",
        "",
        "## Key Metrics",
        "",
        "| Metric | Mean | Median | Std | Min | Max |",
        "|--------|------|--------|-----|-----|-----|",
    ]

    for metric_name in ['overall', 'hfs', 'tss', 'brs', 'overfit_gap']:
        stats = analysis['statistics'][metric_name]
        lines.append(
            f"| {metric_name.upper()} | {stats['mean']:.3f} | {stats['median']:.3f} | "
            f"{stats['std']:.3f} | {stats['min']:.3f} | {stats['max']:.3f} |"
        )

    # BRS Analysis
    brs = analysis['brs_analysis']
    lines.extend([
        "",
        "## BRS (Bug Reproduction Strength) Analysis",
        "",
        f"- **BRS = 1**: {brs['brs_1']} instances ({brs['brs_rate']:.1%})",
        f"- **BRS = 0**: {brs['brs_0']} instances ({(1-brs['brs_rate']):.1%})",
        "",
    ])

    # Overfit Analysis
    overfit = analysis['overfit_categories']
    total = analysis['summary']['total_instances']
    lines.extend([
        "## Overfit Gap Categories",
        "",
        f"- **Excellent (< 0.05)**: {overfit['excellent']} ({overfit['excellent']/total:.1%})",
        f"- **Good (0.05-0.10)**: {overfit['good']} ({overfit['good']/total:.1%})",
        f"- **Acceptable (0.10-0.15)**: {overfit['acceptable']} ({overfit['acceptable']/total:.1%})",
        f"- **Concerning (≥ 0.15)**: {overfit['concerning']} ({overfit['concerning']/total:.1%})",
        "",
    ])

    # Performance Categories
    perf = analysis['performance_categories']
    lines.extend([
        "## Performance Categories",
        "",
        f"- **Failed (< 0.3)**: {perf['failed']} ({perf['failed']/total:.1%})",
        f"- **Partial (0.3-0.6)**: {perf['partial']} ({perf['partial']/total:.1%})",
        f"- **Good (0.6-0.8)**: {perf['good']} ({perf['good']/total:.1%})",
        f"- **Excellent (≥ 0.8)**: {perf['excellent']} ({perf['excellent']/total:.1%})",
        "",
    ])

    # Repository Breakdown
    lines.extend([
        "## Repository Breakdown",
        "",
        "| Repository | Count | Mean Overall | BRS Rate | Success Rate |",
        "|------------|-------|--------------|----------|--------------|",
    ])

    repo_breakdown = analysis['repository_breakdown']
    sorted_repos = sorted(repo_breakdown.items(), key=lambda x: x[1]['count'], reverse=True)

    for repo, stats in sorted_repos[:10]:  # Top 10
        lines.append(
            f"| {repo} | {stats['count']} | {stats['mean_overall']:.3f} | "
            f"{stats['mean_brs']:.1%} | {stats['success_rate']:.1%} |"
        )

    # Distributions
    lines.extend([
        "",
        "## Overall Score Distribution",
        "",
        "```",
    ])

    dist = analysis['distributions']['overall']
    for i, (bin_label, count, pct) in enumerate(zip(dist['bins'], dist['counts'], dist['percentages'])):
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        lines.append(f"{bin_label:12} {bar} {count:3d} ({pct:5.1f}%)")

    lines.append("```")

    # Write report
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))

    print(f"Report written to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Analyze phase results')
    parser.add_argument('--output_dir', type=str, required=True,
                       help='Output directory with instance results')
    parser.add_argument('--report', type=str, required=True,
                       help='Output report file')
    parser.add_argument('--json', type=str,
                       help='Output JSON file for detailed analysis')

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"Error: {output_dir} does not exist")
        return

    print(f"Loading metrics from {output_dir}...")
    metrics_list = load_instance_metrics(output_dir)
    print(f"Loaded {len(metrics_list)} instances")

    if not metrics_list:
        print("No metrics found!")
        return

    print("Analyzing metrics...")
    analysis = analyze_metrics(metrics_list)

    print("Generating report...")
    generate_report(analysis, args.report)

    if args.json:
        with open(args.json, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"JSON analysis written to {args.json}")

    # Print summary to console
    print("\n=== SUMMARY ===")
    print(f"Total instances: {analysis['summary']['total_instances']}")
    print(f"Success rate: {analysis['summary']['success_rate']:.1%}")
    print(f"Mean Overall: {analysis['statistics']['overall']['mean']:.3f}")
    print(f"Mean BRS: {analysis['brs_analysis']['brs_rate']:.1%}")
    print(f"Mean Overfit Gap: {analysis['statistics']['overfit_gap']['mean']:.3f}")
    print(f"Total cost: ${analysis['summary']['total_cost']:.2f}")


if __name__ == '__main__':
    main()
