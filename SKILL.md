---
name: code-quality-guard
description: Use when implementing, refactoring, or reviewing code and the task benefits from tests-first work, explicit quality checks, security awareness, and verifiable completion.
metadata:
  version: "22.1.0a1"
---

# Code Quality Guard

Help coding agents deliver correct, maintainable, and secure changes while preserving the user's requested scope. The guidance below applies across programming languages. The bundled analyzer currently supports Python only.

## Workflow

1. Read the repository's `AGENTS.md`, project guidance, nearby implementation, and relevant tests. Treat repository instructions as constraints, not a reason to expand the task.
2. Before behavior changes, define the expected behavior and important boundaries or failure cases in focused tests. Add or update those tests before implementation.
3. Implement the smallest coherent change that fits the existing architecture. Keep error handling explicit; do not swallow failures or expose secrets in logs and reports.
4. Verify normal behavior, boundary conditions, and failure paths. Run focused checks first, then broader project checks when practical. Aim for at least 80% coverage of changed code when coverage measurement is available and useful.
5. Report exactly what changed, which checks ran, and any remaining failures or limitations. Never imply a skipped or failed check passed.

For review-only requests, do not edit files. Lead with actionable defects and risks, ordered by severity and tied to file and line references.

## Quality Review

- **Correctness:** check input validation, state transitions, empty cases, boundaries, and error paths.
- **Readability:** use precise names and focused functions; avoid deep nesting when a clearer structure is practical.
- **Architecture:** follow local ownership boundaries and established patterns; avoid unnecessary abstractions.
- **Security:** do not hardcode credentials, use unsafe dynamic execution or deserialization, interpolate untrusted SQL, or weaken transport verification without a justified design.
- **Performance:** look for repeated I/O or queries in loops, unbounded work, avoidable quadratic behavior, and missing timeouts on external requests.

Treat thresholds and analyzer findings as prompts to inspect context, not as proof of a defect. Do not modify unrelated code just to silence a check.

## Optional Python Analyzer

Use the bundled scanner when it adds signal for Python changes:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/code-quality-guard"
python3 "$SKILL_DIR/scripts/qguard.py" /path/to/project --verbose
python3 "$SKILL_DIR/scripts/qguard.py" gate /path/to/project --min-score 70
```

The analyzer supports Python `.py` files only. It uses AST and tokenizer checks, but does not perform interprocedural data-flow analysis or prove exploitability. Invalid Python, unreadable files, and scans with no eligible Python files fail the gate. Review the findings and verify them with the target project's tests and tools; do not use this scanner as the sole security or CI gate.

Use `--config` for a checked-in project spec. `--spec-only` writes a starter spec; choose an explicit output path before running it. `--sarif` exports SARIF 2.1.0 and `--agent-rules` exports scan-specific guidance YAML.

For scanner rule semantics or configuration, consult [references/rules.md](references/rules.md) and [references/spec-guide.md](references/spec-guide.md). Use [references/best-practices.md](references/best-practices.md) for concise implementation guidance. Feedback is local storage only; see [references/feedback.md](references/feedback.md) when the task concerns feedback records.

To run the bundled checks:

```bash
python3 -m pytest
python3 "$SKILL_DIR/scripts/run_tests.py"
```
