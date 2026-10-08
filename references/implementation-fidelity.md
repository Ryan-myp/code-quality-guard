# Implementation Fidelity

Use this checklist for a substantial feature with an approved technical design, acceptance criteria, or explicit extensibility requirements. It is intended to catch divergence early; it cannot prove that an implementation matches intent without review.

## Before Broad Implementation

Extract only material requirements and classify each as:

- **Required behavior:** observable outcomes, inputs, outputs, and failure behavior.
- **Architecture constraint:** ownership boundaries, dependencies, data flow, or required interfaces.
- **Extension requirement:** what is expected to vary and the designated place to add a variant.
- **Non-goal or constraint:** explicitly excluded work, compatibility, security, performance, or rollout limits.

Create a compact implementation map:

| Requirement | Owning layer or interface | Extension point, if any | Acceptance evidence |
|---|---|---|---|
| Example: providers can be added without changing billing flow | provider adapter contract | provider registration/composition | contract tests for two providers |

Use this to identify conflicts with existing code before implementation. Do not turn illustrative examples into extra requirements. Ask a focused question only when a choice materially changes user-visible behavior, interface ownership, data ownership, or the required extension mechanism. Otherwise record a conservative assumption.

## Check The First Path

Implement one representative vertical path through the intended layers and its tests. Before applying the pattern to remaining cases, compare the actual call flow, data ownership, and extension point with the map.

If the design calls for another implementation to be addable without editing core orchestration, inspect the consuming contract and test at least two implementations when practical. A new `if`/`switch` is not automatically wrong: it is a mismatch when each new variant requires another branch in core flow despite an explicit extension contract.

## Review Literals And Branches

Inspect newly introduced literals and conditionals and classify them:

- **Stable domain invariant:** a fixed protocol value, invariant, or closed set; keeping it local may be clearest.
- **Variable policy or deployment value:** retries, limits, timeouts, rollout choices, per-customer behavior, and environment-specific endpoints; keep it in the owning configuration or policy layer, validate it, and test defaults and invalid inputs.
- **Credential or secret:** never commit it; use the project's established secret source.
- **Closed finite choice:** a small explicit branch can be correct when the design defines a fixed set and no independent implementations are expected.

Do not add abstraction solely to remove every conditional or literal. Check whether adding the next expected variant would require modifying orchestration, duplicating policy, or bypassing a documented boundary.

## Final Trace

For each material requirement, identify:

1. The implementation location that owns it.
2. The test or other observable evidence that verifies it, including relevant boundaries and failure paths.
3. Any deviation, its reason, and whether user agreement is still needed.

Review the final diff against the implementation map. Re-check hard-coded values, main-flow branching, layer bypasses, duplicated policy, and tests that only assert the happy path. Report evidence and residual gaps; do not claim that a prompt, scanner, or passing test suite guarantees architectural quality.
