# Current Project Summary

**As of September 24, 2026**

Code Quality Guard is an alpha Python-only quality and security heuristic for coding agents. Its purpose is to guide implementation and verification, not to claim comprehensive vulnerability detection.

## Current Capabilities

- AST-based Python checks for selected dynamic execution, secret-like literals, dynamic SQL, TLS configuration, shell execution, deserialization, random-number usage, exception handling, and code structure.
- Configurable project specs and severity-count gates with validation.
- Recursive project and single-file scanning, JSON output, SARIF 2.1.0, and Agent guidance YAML.
- Local feedback persistence and a five-sample annotated benchmark evaluator.

## Verification

Run:

```bash
python -m pytest
python scripts/run_tests.py
python scripts/evaluate_benchmark.py
```

The benchmark is deliberately small: five annotated samples, precision `1.000`, recall `1.000`, and F1 `1.000`. The 6,614 collected code snippets are unlabeled and are not used to calculate these metrics; the small smoke benchmark is not evidence of production accuracy.

## Limits

The scanner does not parse non-Python languages, perform interprocedural data-flow analysis, or prove exploitability. Feedback collection is local storage only; it does not learn or retune rules automatically. Use project tests, code review, and specialized tools alongside this scanner.

See [README](README.md) for installation and configuration.
