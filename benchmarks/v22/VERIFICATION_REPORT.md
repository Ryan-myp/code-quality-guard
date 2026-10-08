# Annotated Benchmark Report

**Evaluation date:** October 8, 2026
**Command:** `python scripts/evaluate_benchmark.py`

## Scope

The evaluator runs the current Python analyzer against `annotated_samples.json`. The evaluation unit is the unique set of expected and detected rule IDs per sample; multiple occurrences of one rule in the same sample count once. The 13 samples include positive examples and negative controls. This remains a small smoke benchmark, not a representative estimate of production behavior.

## Results

| Measure | Result |
|---|---:|
| Annotated samples | 13 |
| True positives | 11 |
| False positives | 0 |
| False negatives | 0 |
| Precision | 1.000 |
| Recall | 1.000 |
| F1 | 1.000 |

The 6,614 collected snippets in `real_samples/collected_samples.json` have no ground-truth annotations. They are not evaluated here and cannot support precision, recall, or F1 claims. These scanner metrics do not evaluate whether a coding agent follows a technical design; the separate human-rated protocol is in `benchmarks/implementation-fidelity/README.md`, and no agent behavior results are claimed.

## Reproduce

```bash
python scripts/evaluate_benchmark.py
```

The command rewrites `metrics_result.json` with per-sample expected, detected, matched, false-positive, and false-negative rule IDs.
