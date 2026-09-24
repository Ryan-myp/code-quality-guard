import json
from pathlib import Path

from scripts.evaluate_benchmark import evaluate, main


def test_benchmark_evaluation_reports_rule_level_counts():
    result = evaluate(
        [
            {
                "id": "one",
                "code": "eval(value)\n",
                "expected_issues": ["security.eval_exec"],
            },
            {
                "id": "two",
                "code": "value = 1\n",
                "expected_issues": ["security.exec"],
            },
        ]
    )

    assert result["true_positives"] == 1
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 1
    assert result["precision"] == 1.0
    assert result["recall"] == 0.5


def test_benchmark_command_writes_reproducible_result(tmp_path):
    samples = tmp_path / "samples.json"
    output = tmp_path / "nested" / "metrics.json"
    samples.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "id": "one",
                        "code": "eval(value)\n",
                        "expected_issues": ["security.eval_exec"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["--samples", str(samples), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["true_positives"] == 1


def test_long_function_annotation_contains_the_labeled_source_lines():
    benchmark_path = (
        Path(__file__).parent.parent / "benchmarks" / "v22" / "annotated_samples.json"
    )
    samples = json.loads(benchmark_path.read_text(encoding="utf-8"))["samples"]
    sample = next(item for item in samples if item["id"] == "sample_005")

    assert len(sample["code"].splitlines()) > 50
    assert evaluate([sample])["false_negatives"] == 0
