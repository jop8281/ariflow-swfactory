# WorldGen delivery through the Airflow factory

Use this factory implementation to develop [WorldGen](https://github.com/jop8281/zozo123-genworld).
Track product work in the [WorldGen Linear project](https://linear.app/yossi-zozo123/project/worldgen-f83badd4a2c7).
The factory baseline inspected for this setup is `d6c472564069021c6c8e1d16a13f37e6d77b5081`.
Pin the deployed revision and record any later upgrade separately.

Linear is the sole issue tracker: it owns work orders, priorities, dependencies, and execution evidence.
GitHub holds code and reviewable PRs. Do not create GitHub issues or issue mirrors.
The existing GitHub-based admission path does not meet this policy; direct Linear intake is required.
Airflow remains the only managed lifecycle scheduler. The backend owns Cell mutations and publication.
People approve intent, plan, and merge decisions.

## Product target and readiness

The existing `selfhost` route targets this factory repository. It is not the WorldGen route.
Before admitting product work, define a blueprint targeting `jop8281/zozo123-genworld` and a
`factory.toml` in the product checkout. Follow [backend setup](factory-backend.md),
[operator commands](swf.md), [the agent contract](../AGENTS.md), and
[promotion policy](promotion-policy.md).

[Deployment qualification, YOS-102](https://linear.app/yossi-zozo123/issue/YOS-102)
precedes [the managed product pilot, YOS-103](https://linear.app/yossi-zozo123/issue/YOS-103).
Qualification must establish:

- A trusted backend and Airflow deployment with successful doctor checks and managed-worker wiring.
- An installed operator client and a context bound to the product repository.
- Direct Linear intake under [YOS-104](https://linear.app/yossi-zozo123/issue/YOS-104),
  with an immutable Linear UUID as the work-order identity and no GitHub issue creation.
- A product target contract with fresh JUnit evidence and protected engine and governance paths.
- Bun for product dependency installation and commands, with Node available for the existing
  deterministic snippet sandbox. PR #79 in WorldGen introduces this tooling setup.
- A sandbox provider that satisfies the current product decision and its required boundary.
- Effective promotion protection and exact-candidate checks on the product repository.

Model and provider choices belong to the current WorldGen contract and are configured on trusted
hosts. Keep credentials out of world bundles, reports, datasets, and inner stage sandboxes.
No label should admit work until qualification has passed.

## Work orders and status

A coding work order states the originator's intent, observable acceptance criteria, target,
allowed files, constraints, and verification command. Preserve the originator's intent verbatim.
Link the Linear task to its resulting GitHub PR. Inspect existing Linear tasks before creating another.
Native Linear intake is not implemented at the inspected baseline. YOS-104 must implement it through
the existing operations layer, preserving retry and duplicate-event behavior without GitHub issue mirrors.

| Linear status | Evidence |
| --- | --- |
| Backlog | Scope or readiness is incomplete, or a dependency is unresolved. |
| Todo | Concrete scope and dependencies are ready for admission. |
| In Progress | Operator work has begun, or Airflow accepted the work order. State which applies. |
| In Review | A reviewable PR exists. Record its exact head SHA and check results. |
| Done | Acceptance criteria are verified. A coding delivery also requires an authorized merge and merged PR. |
| Canceled | Work was withdrawn or rejected. Preserve the reason. |

The team has no dedicated Blocked status. Record the actual failure and blocking dependency in the
issue. A failed or rejected run must not become Done. Updating Linear does not approve a factory gate.

## Admission and release

Managed admission remains blocked until the product route and direct Linear intake are implemented
and qualified. The baseline harness accepts a GitHub issue number; do not pass a Linear identifier
to that argument or create a GitHub issue to satisfy it. YOS-104 must define and verify the supported
Linear admission command before this runbook can publish a runnable template.

Keep session identity stable for retries; independent sessions use distinct factory IDs.
Read exact intent and plan artifacts before obtaining the human's explicit gate decisions.

Retain Cell and run identities, deployed factory revision, blueprint and target, sandbox boundary,
artifact-bound approvals, fresh verification results, review disposition, candidate SHA, and PR URL.
Distinguish reported, published, and independently verified evidence.
Required candidate-readiness checks must pass for the exact head before promotion.
A changed head requires current evidence again. A human owns the final merge decision.

## Bootstrap evidence

On October 6, 2026, this session directly checked and verified WorldGen's golden helpdesk and
exercised ticket assignment and exact reset over HTTP. Bun migration is in
[WorldGen PR #79](https://github.com/jop8281/zozo123-genworld/pull/79), tracked by
[YOS-106](https://linear.app/yossi-zozo123/issue/YOS-106).
Direct product verification is not an Airflow-managed coding run.
No managed Cell has been submitted, no live factory gate answered, and no managed delivery verified.

The operator machine has Docker and uv, but `swf` was absent from PATH.
A managed backend connection and doctor result were not established.
The factory repository's branch-protection API returned 404 and its ruleset list was empty.
Verify effective protection for both the deployed factory and the product before live admission.
