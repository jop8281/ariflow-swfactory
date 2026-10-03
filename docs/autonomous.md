# Policy-governed autonomous runs

This is an experimental capability validated with hermetic backend tests and Airflow DAG tests.
A real unattended deployment and paid-provider run have not yet been validated.

An eligible GitHub issue can run through triage, intent, specification, plan, implementation,
tests, review, publication, and merge without a person answering a gate. The checked-in
[policy](../config/autonomous.toml) supplies authority; the implementation agent does not.
Airflow remains the lifecycle scheduler. The backend alone holds GitHub mutation credentials.

## The initial policy

Issue events (`opened`, `labeled`, `reopened`) automatically call backend triage. An open issue
with a nonempty title/body and the `factory:autonomous` label may enter the `autonomous` line.
`security`, `human-only`, and `factory:blocked` labels block it. The backend re-fetches the issue;
it does not trust an event's labels, agent prose, or a caller-supplied allowlist.

The initial authority is deliberately small: at most 30 changed files, at most $8 per job,
documentation paths, excluding every path protected by `factory.toml`. The factory source itself
contains the backend and its imported authority implementation, so source changes remain human
maintenance until a reviewed policy explicitly scopes a separate product surface. The existing
contract protects the tests directory; this line cannot edit tests. The host-generated artifact
chain under `docs/factory/<this-issue>/` is included separately. Changing another issue's chain
is blocked. A production signal may create an issue with the same label, but cannot expand the
paths, budget, protections, review skill, or required checks.

Outside-policy issues receive a durable `blocked` triage outcome before any work order, Cell,
or model expenditure. They are recorded in the backend's `autonomy.sqlite3`; they are not
silently treated as a completed implementation. Missing deployment configuration fails intake
visibly in GitHub Actions. Existing human lines and local replay fixtures retain their behavior.

## Artifact gates remain gates

Intent and plan have `mode = "policy"`. Their Airflow record tasks ask the backend for a decision
instead of waiting on a HITL operator. Local unmanaged runs cannot satisfy policy gates.

The recorded approver is `policy:<revision>`. The revision hashes the policy, protected-path
contract, autonomous blueprint, and review skill. Each approval also binds the artifact SHA-256,
accepted-input digest, Cell identity, and epoch. Plan decisions also bind the structured
`plan.json` consumed by implementation, so changing JSON while keeping Markdown cannot reuse approval. Plan approval requires intent approval over the
same accepted inputs, checks all declared plan paths, and enforces the checked-in budget.

The backend stores each decision immutably per Cell epoch. Retries can recover the same approval;
they cannot restamp it over a changed artifact. Runtime accepted-input checks and delivery checks
also refuse changed policy, artifact, issue, blueprint, or execution inputs. Such changes require
a new admission/epoch; an environment variable cannot broaden the authority.

## Merge is a managed mutation

Publication retains host-generated test/review evidence and the backend-owned approval chain.
The backend checks the actual patch against both the policy and approved plan paths before
publishing. It stores the publication receipt and artifact digests at that Cell epoch.

After publication, Airflow's `job.merge` sensor waits in **reschedule** mode, with a 30-second
interval and the policy's timeout. It does not occupy a worker while CI runs. The Cell remains
live until merge completes or the task fails; only then does lifecycle completion release it.

The backend re-reads GitHub immediately before merging. It requires:

- The published head SHA and base repository/branch still match.
- The actual PR paths still match the approved publication and stay inside policy.
- The published intent, rendered/structured plan, review, metrics, and approvals still match host-recorded digests.
- `candidate-readiness` and `protected-paths` checks for that SHA finish successfully from the
  configured GitHub Actions app. Missing/running checks wait; failed, cancelled, skipped, or
  wrong-SHA checks cannot authorize merge. A later rerun supersedes an earlier result.
- No outstanding GitHub change-request review, and a passing factory review without blockers.
- The Cell epoch and bound policy remain current.

The backend performs a squash merge through GitHub's atomic `sha` compare-and-merge parameter,
using the existing scoped credential lease and durable managed-mutation journal. A lost response
is reconciled against the remote before any retry; an observed same-SHA merge is adopted.
Scripted replay is refused for autonomous publication/merge. The implementation agent never
receives GitHub credentials, publishes, approves itself, or merges.

## Deployment

Deploy the updated backend and Airflow DAGs from the **same revision**. Keep their policy assets
identical. A published wheel includes the policy and protection contract; an older backend cannot
implement this line merely because a newer workflow submits it.

Configure repository Actions secrets `SWF_BACKEND_URL` (reachable HTTPS backend base URL) and
`SWF_BACKEND_TOKEN` (the existing backend bearer credential). The backend needs its normal
GitHub publication credential with repository contents/pull-request write permission and its
normal Airflow/provider configuration. No GitHub administration token is needed.

Create an issue already carrying `factory:autonomous`, or apply that label to an existing issue.
No `swf submit` or `swf gates approve` command is needed. Follow the dispatch workflow, backend
work order/Cell evidence, and Airflow's `autonomous` DAG. A blocked policy outcome is expected
for work outside the policy. Paid provider access and the real deployment must be validated
separately from hermetic tests.

Policy, budget, protection, review-skill, and authority-implementation changes remain human
maintenance changes. The autonomous line cannot merge them, even if a PR edits its own policy
in the same diff. Governance enforcement issue #2048 remains separate from unattended execution.
