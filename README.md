# Code Quality Guard

> Python code-quality guidance and static checks for AI coding agents.

Code Quality Guard helps agents inspect project conventions, catch a focused set of common defects, and verify work before handing it back. It is an advisory heuristic, not a substitute for tests, review, a security audit, or a language-aware static-analysis platform.

## Scope

The scanner currently analyzes **Python `.py` files only**. It uses Python's AST for code rules, so calls or assignments inside comments and string literals are not treated as executable code. It does not perform interprocedural taint analysis, prove exploitability, or guarantee that all vulnerabilities are detected.

Current checks include risky dynamic execution, hardcoded secret-like string assignments, dynamic SQL strings, disabled TLS verification, shell execution, unsafe deserialization, literal parent-directory paths, weak `random` calls, broad exception handling, TODO/FIXME comments, and configurable function/parameter/nesting/line-length/docstring checks. The YAML rule catalog is loaded at runtime and included in built distributions.

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Use

```bash
# Scan a project or a single Python file
qguard .
qguard src/service.py
qguard gate . --min-score 70

# Save the complete JSON report
qguard . --config qguard.yaml --output build/qguard.json

# Export SARIF 2.1.0 or agent guidance YAML
qguard . --sarif --output build/qguard.sarif
qguard . --agent-rules --output build/agent-rules.yaml

# Generate a starter spec
qguard . --spec-only --output qguard.yaml
```

The scanner reports file read, decoding, and syntax errors and fails the gate rather than silently treating those files as clean. Exit codes are `0` for pass, `1` for warning, and `2` for failure or scan error. If a project contains no scannable Python files, the scan fails with an explicit scope message.

## Configuration

```yaml
name: example
language: python

security:
  max_severity: info # Report this severity and more severe findings.
  ignore_patterns:
    - "test_*.py"
    - "__init__.py"
    - "conftest.py"

code_quality:
  max_function_length: 50
  max_nesting_depth: 4
  max_parameters: 7
  max_line_length: 100
  require_docstrings: false

quality_gate:
  max_critical: 0
  max_high: 5
  max_warning: 20
  max_info: 100
  min_confidence: 0.7
  forbidden_rules: []
```

`max_severity` is a reporting threshold: `critical` reports only critical security findings; `info` reports every security severity. Ignore patterns apply to entire Python files and match either the relative path or filename. Unsupported or misspelled settings are rejected instead of silently ignored.

## Tests And Benchmark

```bash
python -m pytest
python scripts/run_tests.py
python scripts/evaluate_benchmark.py
```

The reproducible benchmark currently contains five hand-annotated examples. Its evaluation unit is the unique rule ID per sample. The latest run reports precision `1.000`, recall `1.000`, and F1 `1.000`. These small examples are a smoke benchmark, not evidence of production precision or recall. The 6,614 collected source snippets in `benchmarks/v22/real_samples/` do not have ground-truth labels and are not included in these metrics.

## Project Files

- `SKILL.md`: cross-language implementation guidance for coding agents.
- `engines/`: analyzer, spec loader, quality gate, report exporters, and feedback storage.
- `rules/v22/v22_rules.yaml`: runtime rule metadata.
- `scripts/qguard.py`: CLI.
- `scripts/evaluate_benchmark.py`: reproducible annotated-sample evaluation.
- `tests/`: pytest regression tests and the original YAML smoke suite.
- `references/`: agent guidance and configuration documentation.

See [the rule catalog](rules/v22/v22_rules.yaml), [spec guide](references/spec-guide.md), and [benchmark report](benchmarks/v22/VERIFICATION_REPORT.md).

## License

MIT. See [LICENSE](LICENSE).

*Updated: September 24, 2026.*
