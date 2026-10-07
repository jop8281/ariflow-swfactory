# Linear source preview

`swfactory linear-preview` reads one Linear issue on a trusted controller and prints a JSON
preview. It requires an immutable issue UUID, the expected workspace UUID, and the expected
project UUID. It preserves the title and description exactly and rejects mismatched identities.

The preview is a read-only source adapter. The separate [native intake route](native-linear-intake.md)
accepts its digest through the existing backend work-order API. Both are maintenance changes
following the [intake design in PR2361](https://github.com/zozo123/ariflow-swfactory/pull/2361).

## Run on a trusted controller

Provide `SWF_LINEAR_API_KEY` in the controller's environment through its existing secret
configuration. Do not put the key in the command, issue text, a work cell, or a worker bundle.
The command supports a Linear personal API key and uses the documented
[GraphQL authentication and error behavior](https://linear.app/developers/graphql).

```bash
uv run swfactory linear-preview <issue-uuid> \
  --workspace-id <workspace-uuid> \
  --project-id <project-uuid>
```

The workspace ID is Linear's organization UUID. The team UUID and URL slug cannot substitute
for it. The trusted controller must verify its own workspace and project scope. The command
refuses missing credentials before network I/O.

## Implemented flow

```mermaid
flowchart LR
  O[Trusted controller command] --> V[Validate requested UUIDs]
  K[Controller-only API key] --> Q[Single Linear GraphQL query]
  V --> Q
  Q --> S[Verify workspace, project, issue and canonical URL]
  S --> P[Immutable source preview]
  P --> J[JSON with admission_ready false]
  Q -->|HTTP, GraphQL or incomplete response| R[Refuse without remote error text]
  S -->|Identity mismatch or credential-like content| R
```

The source key is `linear:<workspace UUID>:<issue UUID>`. Display identifiers and issue URLs do
not determine identity. The intent digest covers that key, project UUID, team UUID, original
title, and original description. Status, identifier, URL, and `updatedAt` changes do not change
the digest. A changed title or description does. An appended PR link in the description is a
description edit and therefore changes the digest; future status projection must use Linear
attachments instead of editing accepted text.

This digest identifies the preview's text only. It is not the final work-order key or an
accepted-input receipt. Dependencies, allowed paths, target, blueprint and policy must be bound
at managed admission. A completed or archived issue can be inspected, but every preview still
says `admission_ready: false`. Linear Done never proves merged delivery.

The client issues a single bounded read, refuses redirects, and does not retry automatically.
GraphQL partial errors, oversized or malformed responses, unknown workflow states and missing
required fields all refuse the read. Error messages do not echo server text. Known credential
patterns and a response containing the controller key are rejected; this check cannot detect
every possible secret in free text, so a preview must not be passed directly to a work cell.

## Managed admission

```mermaid
flowchart LR
  L[Verified Linear source] --> A[Existing backend operations and durable admission]
  A --> C[Cell identity and epoch fence]
  A --> D[Airflow dispatch outbox]
  D --> W[Worker loads immutable accepted snapshot]
  W --> H[Human intent and plan gates]
  H --> T[Bounded edits and fresh evidence]
  T --> G[Backend publishes exact candidate PR]
  G --> M[Authorized merge and verified delivery]
  G -.pending.-> I[Linear In Review projection]
  M -.pending.-> F[Linear Done projection]
```

Native intake stores the accepted snapshot in the existing work order and serves it to workers
through the current Cell epoch. Use `linear-submit`, as described in the native intake document,
instead of passing a Linear UUID as a legacy GitHub issue reference. The dotted projection steps
remain unimplemented. Dependency receipts and Linear maintenance incidents also remain pending;
dependent work and GitHub issue creation for native Cells refuse instead of falling back.

Deployment qualification still requires actual backend credentials, provider and sandbox checks,
doctor, managed-worker wiring, target contract qualification and effective promotion protection.
A managed pilot cannot run until those checks and reviewed native intake are complete.

## Verification

`uv run pytest tests/test_linear_source.py` exercises the real parser and CLI with an injected
HTTP transport. It covers immutable text, stable UUID identity across JSON reloads, intent
edits, status-only changes, malformed/unauthorized source data, GraphQL partial success,
credential rejection, bounded responses, API errors and absence of admission in CLI output.
The transport assertions require one GraphQL query and no mutation operation.

These tests do not prove a live Linear credential, restart-safe admission, a managed Cell,
Airflow execution, publication, status projection or a qualified deployment. Those require the
eight behavior gates in the intake design and exact-candidate factory CI.
