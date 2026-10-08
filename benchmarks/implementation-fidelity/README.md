# Implementation-Fidelity Behavior Evaluation

This is a **human-rated coding-agent behavior benchmark** for evaluating whether a loaded skill improves implementation fidelity. It is separate from `benchmarks/v22`, which measures the Python scanner against annotated code samples. No agent/model result is claimed until the cases are run and the resulting code and tests are reviewed.

## Protocol

1. Choose and archive a small repository fixture that satisfies each case's preconditions. Run each case in a fresh copy. Use the same model, settings, starting revision, and task prompt for paired runs with and without the skill.
2. Give the agent the task requirements and available acceptance tests, but not the reviewer rubric or score thresholds. Review the resulting diff, tests, and command outcomes afterward; explanations without code or test evidence do not earn points.
3. Score each dimension from 0 to 2 using the rubric below. Record the exact diff/test evidence and any test command that failed or was skipped.
4. A case passes at 8/10 or higher only when requirement fidelity, architecture, and verification each score at least 1. A direct violation of an explicit architecture constraint is a critical failure regardless of total score.
5. Compare paired scores across all cases. Report the case count, per-dimension scores, critical failures, and limitations. Do not infer general effectiveness from one run or a small sample.

## Cases

### Provider Extension

**Fixture precondition:** the repository has an existing provider contract, one implementation, and core orchestration that consumes the contract.

**Task:** Add a second provider. The design says implementations must plug into the existing contract, core orchestration must remain provider-agnostic, and both implementations must pass the same behavior contract. Do not expand unrelated provider capabilities.

**Review evidence:** the second implementation satisfies the same contract; core orchestration does not gain provider-specific branches; tests exercise both implementations and at least one failure path.

### Variable Retry Policy

**Fixture precondition:** an existing service has retry behavior and a project-supported configuration mechanism.

**Task:** Make the retry limit configurable by the documented deployment/customer policy while retaining the specified default. Validate invalid values, preserve current behavior when unset, and keep retry policy out of request orchestration.

**Review evidence:** value comes from the owning configuration/policy source; tests cover default, override, invalid boundary, and exhausted retries; no duplicate or unexplained retry literals were added.

### Closed State Set

**Fixture precondition:** a small state machine has a documented, finite set of states and no requirement for third-party state extensions.

**Task:** Add the specified `archived` state and its allowed transitions. Keep the existing state model; do not introduce a plugin or registry mechanism.

**Review evidence:** valid and invalid transitions are tested; implementation remains proportionate to the closed set; no unrelated extensibility framework is added.

### Design-To-Code Trace

**Fixture precondition:** a short technical design names request-handler, service, and repository responsibilities plus success, not-found, and dependency-failure acceptance criteria.

**Task:** Implement one end-to-end operation within those boundaries. Preserve error semantics and add tests for the stated outcomes. Do not move persistence into the handler or broaden the API.

**Review evidence:** changed call graph preserves the named boundaries; each acceptance criterion maps to code and a test; failure behavior is observable and not swallowed.

## Scoring Rubric

Score every dimension 0, 1, or 2:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Requirement fidelity | Material behavior or scope is missed | Main path matches; a minor criterion is incomplete | All material requirements and non-goals are respected |
| Architecture | Explicit boundary/extension requirement is violated | Mostly aligned, with a justified minor deviation | Ownership and extension behavior match the design |
| Values and branching | Variable policy is hard-coded or variants leak into core flow | Mostly centralized; one questionable literal or branch remains | Variable policy is owned/configured; branching matches open/closed design |
| Verification | Tests absent or do not verify requested behavior | Main behavior tested; boundaries/failures incomplete | Acceptance, boundary, failure, and extension contract are evidenced as applicable |
| Scope and evidence | Unrelated changes or unsupported completion claims | Small scope drift or incomplete reporting | Focused diff with commands, outcomes, and deviations accurately reported |

Store raw prompts, starting revisions, generated diffs, test output, and reviewer scores with any published results. A scorecard alone is not evidence that the implementation passed.
