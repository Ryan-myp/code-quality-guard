# Go Checks

Use this reference for Go implementation and verification. The bundled analyzer requires a Go module root containing `go.mod`, plus `go` and `gofmt` on `PATH`.

## Bundled Checks

```bash
qguard . --verbose
qguard gate . --min-score 70
```

The Go analyzer runs `gofmt -l` on discovered `.go` files and `go vet -json ./...` from the module root. Formatting differences are reported as `go.gofmt` warnings. Any `go.vet` diagnostic fails the quality gate. Tool failures, timeouts, invalid output, and modules with no Go source fail closed.

The analyzer does not run tests or dependency vulnerability checks. Verify behavior separately:

```bash
go test ./...
```

When the project uses `govulncheck` and it is available, run `govulncheck ./...` as an additional dependency and reachable-vulnerability check. Do not install tools or modify project dependencies unless the user or repository workflow authorizes it.

## Design And Review

- Map design requirements to Go packages, exported APIs, ownership boundaries, extension points, and tests before implementation.
- When new implementations are expected, define a small behavior contract at the consuming boundary and test a second implementation without changing core orchestration where practical.
- Do not replace a specified extension point with a growing type switch or provider-specific branch in the main flow. A switch remains appropriate for stable, closed sets of cases.
- Preserve Go error context with wrapping such as `%w`; handle returned errors instead of discarding them.
- Propagate `context.Context` through cancellable operations and bound external work with the project's timeout policy. Check goroutine shutdown and resource closing paths.
- Test normal behavior, boundary values, error paths, and extension contracts. `go vet` and formatting checks do not replace `go test`.

These are review prompts, not universal requirements to add interfaces, contexts, or abstractions where the design does not need them.
