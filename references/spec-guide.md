# Project Spec

The project spec controls the checks performed by the current Python scanner. Unknown keys are rejected so a typo cannot silently disable a policy.

```yaml
name: my-project
language: python

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

`quality_gate` values determine pass, warning, and failure thresholds. Any scan error, invalid Python syntax, or scan with no eligible Python files fails closed. A gate warning returns exit code `1`; a failed gate or scan error returns `2`.

Generate a starter file with:

```bash
qguard . --spec-only --output qguard.yaml
```

The current scanner supports Python only. `language` is retained as explicit project metadata; selecting another language does not enable parsing for it.
