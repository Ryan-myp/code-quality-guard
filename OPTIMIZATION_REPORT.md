# Code Quality Guard Hardening Report

**Updated:** September 24, 2026
**Version:** 22.1.0a1

This report replaces earlier performance claims that were not reproducible from the checked-in annotations. Code Quality Guard remains an alpha, heuristic Python scanner.

## Changes

- Replaced raw line-regex analysis with AST checks for Python code and tokenizer-based TODO comment detection.
- Corrected physical function-line and full parameter counts; added configurable line-length and public-definition docstring checks.
- Limited scanning to `.py`, added single-file support, file ignore patterns, clear unsupported-language errors, and fail-closed handling for read, decoding, syntax, and empty-scan errors.
- Aggregated findings across all files and applied every configured quality-gate limit, including informational findings.
- Added validation for specs and gate settings. Unsupported settings now produce an error rather than appearing to work.
- Implemented SARIF 2.1.0 and Agent guidance exports.
- Made the YAML rule catalog the runtime metadata source and included it in package builds.
- Corrected package metadata, the console entry point, runtime dependency declaration, and pytest import behavior.
- Replaced unverified benchmark claims with a repeatable evaluator over the five checked-in annotated examples.

The self-check `python3 scripts/qguard.py gate . --min-score 70` passes at 100/100 with no findings.

## Measured Evidence

The current annotated benchmark reports precision `1.000`, recall `1.000`, and F1 `1.000` over five samples. It contains seven matched rule/sample pairs, zero unmatched detections, and zero false negatives. This five-sample smoke benchmark is not evidence of broad or production recall.

The 6,614 collected source snippets have no labels and are not benchmark outcomes. Earlier reports that described this corpus as a validated, sampled, or zero-false-positive benchmark have been withdrawn.

## Known Limits

- Python only; no TypeScript, JavaScript, Go, or Rust parser is bundled.
- The checks are syntax-based heuristics, not data-flow analysis or proof of exploitability.
- Path traversal detection is limited to literal parent-directory components.
- The five labeled examples are too few and too narrow to estimate real-world accuracy.
- Feedback is stored locally; it does not automatically tune rules or train a model.

See [README](README.md), [rule notes](references/rules.md), and the [reproducible benchmark report](benchmarks/v22/VERIFICATION_REPORT.md).
