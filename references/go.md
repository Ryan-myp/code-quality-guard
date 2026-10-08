# Go Checks

Use this reference for Go implementation and verification. The bundled analyzer requires a Go module root containing `go.mod`, plus `go` and `gofmt` on `PATH`.

## Bundled Checks

```bash
qguard . --verbose
qguard gate . --min-score 70
```

The Go analyzer runs `gofmt -l` on discovered `.go` files and `go vet -json ./...` from the module root. Formatting differences are reported as `go.gofmt` findings and block the quality gate, as does any `go.vet` diagnostic. Tool failures, timeouts, invalid output, and modules with no Go source fail closed.

Project tests are opt-in. Run `qguard . --run-tests` to include `go test ./...` in the gate; for a mixed project, this also runs `python -m pytest`. Each command has a 300-second timeout. qguard shows test output in the terminal and records status and exit code in its report. Test execution runs project code, so use it only in an appropriate environment. qguard does not run dependency vulnerability checks. When the project uses `govulncheck` and it is available, run:

```bash
govulncheck ./...
```

Do not install tools or modify project dependencies unless the user or repository workflow authorizes it.

## Design And Review

- Map design requirements to Go packages, exported APIs, ownership boundaries, extension points, and tests before implementation.
- After the first representative path, compare the call graph and tests with the design before repeating the pattern across the feature.
- When new implementations are expected, define a small behavior contract at the consuming boundary and test a second implementation without changing core orchestration where practical.
- Do not replace a specified extension point with a growing type switch or provider-specific branch in the main flow. A switch remains appropriate for stable, closed sets of cases.
- Preserve Go error context with wrapping such as `%w`; handle returned errors instead of discarding them.
- Propagate `context.Context` through cancellable operations and bound external work with the project's timeout policy. Check goroutine shutdown and resource closing paths.
- Test normal behavior, boundary values, error paths, and extension contracts. `go vet` and formatting checks do not replace `go test`.

These are review prompts, not universal requirements to add interfaces, contexts, or abstractions where the design does not need them. For the language-neutral fidelity checklist, see [implementation-fidelity.md](implementation-fidelity.md).
