"""Reproducible rule-level evaluation for the small annotated sample set."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.enhanced_analyzer import EnhancedAnalyzer
from engines.spec_parser import ProjectSpec


def evaluate(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare unique detected rule IDs with each sample's expected rule IDs."""
    analyzer = EnhancedAnalyzer(ProjectSpec())
    true_positives = false_positives = false_negatives = 0
    sample_results = []

    for sample in samples:
        expected = set(sample.get("expected_issues", []))
        detected = {
            issue.rule_id for issue in analyzer.analyze(sample.get("code", ""))
        }
        matched = expected & detected
        false_positive_rules = detected - expected
        missed = expected - detected
        true_positives += len(matched)
        false_positives += len(false_positive_rules)
        false_negatives += len(missed)
        sample_results.append(
            {
                "id": sample.get("id"),
                "expected": sorted(expected),
                "detected": sorted(detected),
                "matched": sorted(matched),
                "false_positives": sorted(false_positive_rules),
                "false_negatives": sorted(missed),
            }
        )

    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = (
        true_positives / precision_denominator if precision_denominator else 0.0
    )
    recall = true_positives / recall_denominator if recall_denominator else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "evaluation_unit": "unique rule IDs per annotated sample",
        "annotated_samples": len(samples),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "samples": sample_results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--samples",
        type=Path,
        default=ROOT / "benchmarks" / "v22" / "annotated_samples.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmarks" / "v22" / "metrics_result.json",
    )
    args = parser.parse_args(argv)
    with args.samples.open("r", encoding="utf-8") as sample_file:
        data = json.load(sample_file)
    samples = data.get("samples")
    if not isinstance(samples, list):
        parser.error("benchmark file must contain a samples list")
    result = evaluate(samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Evaluated {} samples: precision={}, recall={}, F1={}".format(
            result["annotated_samples"],
            result["precision"],
            result["recall"],
            result["f1"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
