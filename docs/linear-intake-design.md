# Direct Linear intake for WorldGen

Status: design for YOS-104; not an implemented or qualified admission route.

Linear is the sole issue tracker. GitHub supplies repository content, commit checks, pull requests,
and promotion. No step may create a GitHub issue to obtain a factory identity.
The design targets factory baseline d6c472564069021c6c8e1d16a13f37e6d77b5081.

## Identity and accepted intent

Separate the work source from the code repository. A work reference contains a source kind,
Linear workspace identity, immutable issue UUID, display identifier, and canonical URL.
Use the workspace and UUID for durable identity; YOS-104 is a display identifier, not the key.
A code target independently contains repository, base branch, and target contract.

The trusted backend resolves a Linear reference, verifies workspace/project access, and captures
an immutable accepted-input snapshot: original title and description, acceptance criteria,
allowed paths, dependencies, revision metadata, and a digest of execution-relevant content.
Retain the originator's text. Credential-bearing inputs are rejected before entering a Cell.
Status-only changes and link updates do not create a new execution revision.
Changes to intent require a fresh accepted snapshot and invalidate prior artifact-bound gates.
An operator must explicitly request a new attempt; a webhook update does not grant approval.

## Existing boundaries to change

| Current boundary | Required behavior |
| --- | --- |
| `webhook.submit_work_order` posts `issues` and `targets` to `/v1/work-orders` | Add a versioned, explicit work-source reference to the canonical backend request; do not call Airflow directly. |
| `backend.service._work_order` persists jobs, request digest, policy, and blueprint | Persist the accepted Linear snapshot and source identity in the immutable work order. Keep desired Cell epochs outside the request digest. |
| `backend.service.submit` and `backend.autonomous_service` fetch GitHub issues | Resolve work through the configured Linear source. Preserve readiness and autonomous policy checks; do not silently fall back to GitHub. |
| `runtime._prepare_ctx` fetches issue content | Load the accepted snapshot from the backend, including after restart. Never re-read mutable Linear text as accepted intent. |
| `scm.GitHubScm` mixes issue retrieval and code publication | Separate work-source operations from code SCM; keep GitHub PR/check/publication operations behind the existing Cell fence. |
| `intake_governance` resolves dependency closure from GitHub issue state | Use Linear dependencies and verified delivery receipts. A Linear Done state alone cannot prove merged delivery. |
| `maintain`, `maintenance_incidents`, and `self_improvement.issue_commands` create GitHub issues | Create or reconcile Linear incidents/tasks through the trusted operations layer; keep an immutable incident identity and no GitHub issue fallback. |
| `control` backlog selection and operator harness examples | Select Linear work explicitly and expose supported Linear commands only after the backend contract is implemented and verified. |

This is a protected control-plane change requiring a reviewed maintenance PR. The WorldGen
blueprint must opt into the Linear source explicitly. An unknown source, missing snapshot,
or old worker unable to decode the new schema refuses admission before external mutation.

## Delivery, retries, and reconciliation

The work key is source workspace + issue UUID + accepted revision + target + blueprint/policy
identity. Event delivery IDs deduplicate transport only; they are not execution identity.
Persist receipt and snapshot before dispatch. Duplicate deliveries return the same admission
receipt. An ambiguous submission outcome is reconciled by the durable key before retrying;
never create a second Cell because a response was lost.

Use the existing durable admission, dispatch leases, Cell identity and epoch fencing. Airflow
remains the only lifecycle scheduler. Linear credentials stay on the trusted backend, not in
work cells or worker bundles. Linear status writes are projections of backend evidence and
must not trigger another run. A projection failure leaves a retryable reconciliation record;
it does not undo a published PR or create another execution.

Map queued work to Todo, active execution to In Progress, and published PR evidence to In Review.
Done requires verified acceptance and, for code delivery, an authorized merged PR at the recorded
candidate. Cancellation records a reason and requests cancellation through the operations layer;
changing a Linear status does not itself terminate a Cell or approve a gate.

## Verification required before YOS-103 admission

1. Submit a real Linear task to a qualified WorldGen blueprint with GitHub issues disabled.
   Obtain one durable receipt and one Cell, and verify no GitHub issue API was invoked.
2. Replay the same request and duplicate event, including after backend restart. Require the
   same receipt and no second execution. Inject a lost response and reconcile by work key.
3. Edit intent after acceptance. Require a new revision and fresh human intent/plan decisions;
   a status or PR-link update must retain the accepted revision and avoid dispatch.
4. Reject unknown workspace, unauthorized target, canceled or unresolved dependencies, malformed
   references, and missing snapshots before Cell activation. Old workers reject the new schema.
5. Run an inner stage without Linear/GitHub service credentials. Verify restart uses the accepted
   snapshot. Exercise stale epoch publication and require refusal through the existing fence.
6. Publish a PR, fail the Linear status write, then retry projection. Require one PR and accurate
   Linear evidence. A manually set Done state must not authorize promotion or satisfy a dependency.
7. Create the same maintenance incident twice across a restart. Require one Linear task and zero
   GitHub issues. Confirm all operator examples use the implemented admission contract.
8. Complete fresh candidate checks, human gates, and authorized merge. Record revision, target,
   Cell/run IDs, candidate SHA, PR URL, evidence and independently verified delivery in Linear.

These are behavior gates for implementation, not results claimed by this design.
