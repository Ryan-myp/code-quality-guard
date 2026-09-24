# Rule Catalog

Runtime rule metadata lives in [`rules/v22/v22_rules.yaml`](../rules/v22/v22_rules.yaml). The analyzer loads and validates that catalog at startup; the implementation is in `engines/enhanced_analyzer.py`.

## Security

- `security.eval_exec`: flags calls to `eval()` and `exec()` as separate rules.
- `security.hardcoded_secret`: flags non-empty string literals assigned to credential-like names or passed through credential-like keyword arguments. Report context redacts string literals.
- `security.sql_injection`: flags dynamic SQL f-strings, `+`, `%`, or `.format()` expressions beginning with a common SQL statement, including when passed to `execute()`, `executemany()`, or `query()`. It does not trace values through variables or function calls.
- `security.ssl_disabled`: flags literal `verify=False` call arguments and assignments.
- `security.command_injection`: flags `os.system()` / `os.popen()` and common `subprocess` calls with `shell=True`.
- `security.unsafe_deserialization`: flags pickle/marshal loaders, YAML loaders without a safe loader, and YAML `unsafe_load()` calls.
- `security.path_traversal`: flags literal paths containing a `..` path component. This is a narrow heuristic; it does not trace user-controlled paths.
- `security.insecure_random`: flags selected calls from the standard `random` module. Use `secrets` when values protect credentials or security decisions.

`security.max_severity` filters security findings only. Findings below the configured threshold are omitted.

## Error Handling

- `ai_slop.bare_except`: flags `except:` handlers.
- `ai_slop.generic_exception`: flags `except Exception` and tuples containing `Exception`.
- `ai_slop.swallow_exception`: flags handlers whose only statement is `pass`.

These are review prompts, not blanket prohibitions. A broad handler can be appropriate at a process boundary when it logs, handles, or re-raises safely.

## Code Quality

- `code_quality.function_too_long`: compares physical source-line span with `max_function_length`.
- `code_quality.too_many_parameters`: counts positional-only, positional, keyword-only, `*args`, and `**kwargs`; `self` and `cls` are excluded for methods.
- `code_quality.deep_nesting`: counts nested control-flow blocks.
- `code_quality.line_too_long`: compares physical line length with `max_line_length`.
- `code_quality.missing_docstring`: reports public functions/classes when `require_docstrings` is enabled.
- `ai_slop.redundant_todo`: reports TODO/FIXME comment tokens, not occurrences inside string literals. It does not infer age.

AST-based checks require valid Python syntax. Invalid files are reported as scan errors and fail the quality gate.
