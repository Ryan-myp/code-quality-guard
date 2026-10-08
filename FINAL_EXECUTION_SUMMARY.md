# Current Project Summary

**As of October 8, 2026**

Code Quality Guard is an alpha Python and Go quality/security heuristic for coding agents. It supports mixed Python/Go repositories and is intended to guide implementation and verification, not claim comprehensive vulnerability detection.

## Current Capabilities

- AST-based Python checks for selected dynamic execution, secret-like literals, dynamic SQL, TLS configuration, shell execution, deserialization, random-number usage, exception handling, and code structure.
- Go `gofmt` and `go vet` checks, with formatting and vet findings blocking the gate.
- Opt-in project test execution with `qguard --run-tests` for `pytest` and/or `go test ./...`.
- A technical-design fidelity workflow that checks the requirement map before implementation, after a representative path, and before completion.
- Configurable project specs and severity-count gates with validation.
- Recursive project scanning, Python single-file scanning, JSON output, SARIF 2.1.0, and Agent guidance YAML.
- Local feedback persistence and a thirteen-sample scanner smoke benchmark with positive and negative controls.
- A separate human-rated implementation-fidelity benchmark protocol; no agent behavior scores are claimed yet.

## Verification

Run:

```bash
python -m pytest
python scripts/run_tests.py
python scripts/evaluate_benchmark.py
```

The scanner benchmark is deliberately small: thirteen annotated samples, precision `1.000`, recall `1.000`, and F1 `1.000`. The 6,614 collected code snippets are unlabeled and are not used to calculate these metrics; the smoke benchmark is not evidence of production accuracy.

## Limits

The scanner does not analyze TypeScript, JavaScript, or Rust, perform interprocedural data-flow analysis, or prove exploitability. Feedback collection is local storage only; it does not learn or retune rules automatically. The behavior benchmark is a protocol, not evidence that the skill guarantees architectural fidelity. Use project tests, code review, and specialized tools alongside this scanner.

See [README](README.md) for installation and configuration.
