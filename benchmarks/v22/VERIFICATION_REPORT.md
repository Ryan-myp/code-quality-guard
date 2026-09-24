# Annotated Benchmark Report

**Evaluation date:** September 24, 2026
**Command:** `python scripts/evaluate_benchmark.py`

## Scope

The evaluator runs the current analyzer against `annotated_samples.json`. The evaluation unit is the unique set of expected and detected rule IDs per sample; multiple occurrences of one rule in the same sample count once. This is a five-sample smoke benchmark, not a representative estimate of production behavior.

## Results

| Measure | Result |
|---|---:|
| Annotated samples | 5 |
| True positives | 7 |
| False positives | 0 |
| False negatives | 0 |
| Precision | 1.000 |
| Recall | 1.000 |
| F1 | 1.000 |

The 6,614 collected snippets in `real_samples/collected_samples.json` have no ground-truth annotations. They are not evaluated here and cannot support precision, recall, or F1 claims.

## Reproduce

```bash
python scripts/evaluate_benchmark.py
```

The command rewrites `metrics_result.json` with per-sample expected, detected, matched, false-positive, and false-negative rule IDs.
