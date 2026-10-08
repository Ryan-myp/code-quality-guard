---
name: code-quality-guard
description: Use when implementing, refactoring, or reviewing code, especially when work must follow a technical design, preserve intended extension points, and be verified with tests and explicit quality checks.
metadata:
  version: "22.2.0a1"
---

# Code Quality Guard

Help coding agents deliver correct, maintainable, and secure changes while preserving the user's requested scope. The implementation guidance applies across programming languages. The bundled analyzer supports Python and Go checks.

## Workflow

1. Read the repository's `AGENTS.md`, project guidance, nearby implementation, and relevant tests. Treat repository instructions as constraints, not a reason to expand the task.
2. For work driven by a technical design or detailed specification, use the Technical-Design Fidelity check below before implementation.
3. Before behavior changes, define the expected behavior and important boundaries or failure cases in focused tests. Add or update those tests before implementation.
4. Implement the smallest coherent change that fulfills the agreed design and fits the existing architecture. If an explicit design requirement conflicts with the current architecture, resolve or surface the conflict instead of silently overriding either. Keep error handling explicit; do not swallow failures or expose secrets in logs and reports.
5. Verify normal behavior, boundary conditions, and failure paths. Run focused checks first, then broader project checks when practical. Aim for at least 80% coverage of changed code when coverage measurement is available and useful.
6. Report exactly what changed, which checks ran, and any remaining failures or limitations. Never imply a skipped or failed check passed.

For review-only requests, do not edit files. Lead with actionable defects and risks, ordered by severity and tied to file and line references.

## Technical-Design Fidelity

Before coding from a design, briefly map each material requirement to its target layer or interface, intended extension point, and acceptance test. Separate explicit constraints from examples or preferences. For substantial changes, show this implementation map and surface assumptions before editing; ask for clarification only when an unresolved choice could materially change interfaces, data ownership, or the extension mechanism. Otherwise state a conservative assumption and proceed.

When the design calls for extensibility, identify what is expected to vary and where a new implementation should plug in. Add a contract-level test for that boundary where practical, such as exercising a second implementation without changing core orchestration. Use the repository's established pattern; do not introduce registries, strategies, or plugin systems for hypothetical variation the design does not require.

Review hard-coded values and branching against the design rather than banning them categorically. Keep stable domain invariants simple; centralize values that vary by environment, customer, or policy, and never hard-code credentials. A small `if`/`else` for a stable finite choice can be appropriate; it is a design mismatch when each new supported variant must add another branch to core flow despite a specified extension point.

Compare the changed files and tests with the implementation map during substantial work and again before completion. Report requirement coverage with concrete code or test evidence, and call out any deviation with its reason. Do not silently replace an architectural requirement with a simpler implementation just because its tests pass.

## Quality Review

- **Correctness:** check input validation, state transitions, empty cases, boundaries, and error paths.
- **Readability:** use precise names and focused functions; avoid deep nesting when a clearer structure is practical.
- **Architecture:** follow local ownership boundaries and established patterns unless an explicit, agreed design calls for changing them; avoid unnecessary abstractions.
- **Security:** do not hardcode credentials, use unsafe dynamic execution or deserialization, interpolate untrusted SQL, or weaken transport verification without a justified design.
- **Performance:** look for repeated I/O or queries in loops, unbounded work, avoidable quadratic behavior, and missing timeouts on external requests.

Treat thresholds and analyzer findings as prompts to inspect context, not as proof of a defect. Do not modify unrelated code just to silence a check.

## Optional Analyzers

Use the bundled scanner when it adds signal for supported languages:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/code-quality-guard"
python3 "$SKILL_DIR/scripts/qguard.py" /path/to/project --verbose
python3 "$SKILL_DIR/scripts/qguard.py" gate /path/to/project --min-score 70
```

The Python analyzer checks `.py` files with AST and tokenizer rules; it does not perform interprocedural data-flow analysis or prove exploitability. The Go analyzer requires a module-root `go.mod` and Go tools on `PATH`; it runs `gofmt` and `go vet -json ./...`. It does not run `go test`, `govulncheck`, or a custom Go AST/data-flow analysis. Invalid source, unavailable tools, unreadable files, and scans with no eligible source files fail closed. Review findings and run the target project's tests and other relevant tools; do not use this scanner as the sole security or CI gate.

Use `--config` for a checked-in project spec. `--spec-only` writes a starter spec; choose an explicit output path before running it. `--sarif` exports SARIF 2.1.0 and `--agent-rules` exports scan-specific guidance YAML.

For Go implementation and validation details, consult [references/go.md](references/go.md). For scanner rule semantics or configuration, consult [references/rules.md](references/rules.md) and [references/spec-guide.md](references/spec-guide.md). Use [references/best-practices.md](references/best-practices.md) for concise implementation guidance. Feedback is local storage only; see [references/feedback.md](references/feedback.md) when the task concerns feedback records.

To run the bundled checks:

```bash
python3 -m pytest
python3 "$SKILL_DIR/scripts/run_tests.py"
```
