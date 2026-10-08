# Project Spec

The project spec selects Python, Go, or mixed checks. Unknown keys are rejected so a typo cannot silently disable a policy.

```yaml
name: my-project
language: python # use go for Go or mixed for both

security:
  max_severity: info
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

`security.max_severity` is the minimum severity to report: `critical` reports only critical security findings, while `info` reports all security findings. Ignore patterns skip whole files and match their path relative to the scan root or their basename.

The code-quality limits count physical source lines for function length, count explicit parameters (excluding `self` or `cls` on methods), and count nested control-flow blocks. Docstring checks apply to public functions and classes when enabled. TODO comments are informational; TODO age is not inferred.

`quality_gate` values determine pass, warning, and failure thresholds. Python code-quality thresholds apply only to Python. Go checks require a module-root `go.mod`, `go`, and `gofmt`; formatting findings, any Go vet diagnostic, or scan error fail the gate. `language: mixed` runs both supported analyzers. A gate warning returns exit code `1`; a failed gate or scan error returns `2`.

Generate a starter file with:

```bash
qguard . --spec-only --output qguard.yaml
```

The Python scanner uses AST and tokenizer rules. The Go scanner delegates formatting and static diagnostics to `gofmt` and `go vet`; it does not parse Go source itself. Automatic detection examines nested directories but skips hidden and common generated or virtual-environment directories. Set `language: mixed` explicitly when automatic detection is ambiguous.

Project test execution is opt-in with `qguard . --run-tests`. It invokes `python -m pytest` for Python and `go test ./...` for Go, with a 300-second timeout per command. It records command status and exit code and fails the gate when a command fails, times out, or cannot start. Test suites execute project code; use an appropriate environment.
