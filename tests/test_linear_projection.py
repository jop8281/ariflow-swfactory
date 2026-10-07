from __future__ import annotations

import io
import json

import pytest

from swfactory import linear_projection as module
from swfactory.linear_projection import LinearProjectionTransport, ProjectionTransportError

ISSUE = "32345678-1234-4234-8234-123456789abc"
ATTACHMENT = "52345678-1234-4234-8234-123456789abc"
OTHER = "62345678-1234-4234-8234-123456789abc"
URL = "https://github.com/zozo123/ariflow-swfactory/pull/2362"
HEAD = "a" * 40
KEY = "fixture_not_a_real_key"


def row(issue=ISSUE):
    return {"id": ATTACHMENT, "url": URL, "issue": {"id": issue}, "metadata": {"headSha": HEAD}}


def serve(monkeypatch, handler):
    class Opener:
        def open(self, request, timeout):
            assert timeout == 15
            assert request.full_url == module.ENDPOINT
            payload = json.loads(request.data)
            result = handler(payload)
            return io.BytesIO(json.dumps(result).encode())

    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *args: Opener())


def test_duplicate_write_and_lost_response_observation_use_same_issue_url(monkeypatch):
    writes = []

    def handler(payload):
        if payload["query"] == module.ATTACH:
            writes.append(payload["variables"]["input"])
            return {"data": {"attachmentCreate": {"success": True, "attachment": row()}}}
        return {"data": {"attachmentsForURL": {"nodes": [row(OTHER), row()], "pageInfo": {"hasNextPage": False}}}}

    serve(monkeypatch, handler)
    transport = LinearProjectionTransport(KEY)
    first = transport.attach_pr(ISSUE, URL, HEAD)
    assert transport.attach_pr(ISSUE, URL, HEAD) == first
    assert transport.observe_attachment(ISSUE, URL, HEAD) == first
    assert (
        writes == [{"issueId": ISSUE, "url": URL, "title": "Factory pull request", "metadata": {"headSha": HEAD}}] * 2
    )
    assert KEY not in repr(transport)


@pytest.mark.parametrize("nodes,more", [([], True), ([row(), row()], False), ([None], False)])
def test_incomplete_or_ambiguous_observation_refuses(monkeypatch, nodes, more):
    serve(monkeypatch, lambda p: {"data": {"attachmentsForURL": {"nodes": nodes, "pageInfo": {"hasNextPage": more}}}})
    with pytest.raises(ProjectionTransportError):
        LinearProjectionTransport(KEY).observe_attachment(ISSUE, URL, HEAD)


def test_missing_attachment_is_absent_only_after_complete_observation(monkeypatch):
    serve(
        monkeypatch,
        lambda p: {"data": {"attachmentsForURL": {"nodes": [row(OTHER)], "pageInfo": {"hasNextPage": False}}}},
    )
    assert LinearProjectionTransport(KEY).observe_attachment(ISSUE, URL, HEAD) is None


@pytest.mark.parametrize(
    "response",
    [
        {"errors": [{"message": KEY}]},
        {"data": {"attachmentCreate": {"success": False}}},
        {"data": {"attachmentCreate": {"success": True, "attachment": row(OTHER)}}},
    ],
)
def test_failed_or_mismatched_write_is_not_a_receipt(monkeypatch, response):
    serve(monkeypatch, lambda p: response)
    with pytest.raises(ProjectionTransportError) as error:
        LinearProjectionTransport(KEY).attach_pr(ISSUE, URL, HEAD)
    assert KEY not in str(error.value)


@pytest.mark.parametrize(
    "issue,url,head", [("YOS-134", URL, HEAD), (ISSUE, URL + "?token=secret", HEAD), (ISSUE, URL, "main")]
)
def test_invalid_identity_never_reaches_transport(monkeypatch, issue, url, head):
    serve(monkeypatch, lambda p: pytest.fail("invalid input reached network"))
    with pytest.raises(ProjectionTransportError):
        LinearProjectionTransport(KEY).attach_pr(issue, url, head)


def test_redirect_is_refused():
    assert module._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid") is None


def test_null_page_info_is_refused(monkeypatch):
    serve(monkeypatch, lambda p: {"data": {"attachmentsForURL": {"nodes": [], "pageInfo": None}}})
    with pytest.raises(ProjectionTransportError):
        LinearProjectionTransport(KEY).observe_attachment(ISSUE, URL, HEAD)


def test_attachment_observation_refuses_another_candidate_head(monkeypatch):
    stale = row()
    stale["metadata"] = {"headSha": "b" * 40}
    serve(
        monkeypatch, lambda p: {"data": {"attachmentsForURL": {"nodes": [stale], "pageInfo": {"hasNextPage": False}}}}
    )
    with pytest.raises(ProjectionTransportError, match="candidate head differs"):
        LinearProjectionTransport(KEY).observe_attachment(ISSUE, URL, HEAD)


WORKSPACE = "12345678-1234-4234-8234-123456789abc"
TEAM = "42345678-1234-4234-8234-123456789abc"
STATE = "72345678-1234-4234-8234-123456789abc"


def state_document():
    return {
        "data": {
            "organization": {"id": WORKSPACE},
            "workflowState": {"id": STATE, "type": "started", "team": {"id": TEAM}},
        }
    }


def test_workflow_state_resolves_exact_controller_configured_identity(monkeypatch):
    serve(monkeypatch, lambda p: state_document())
    assert LinearProjectionTransport(KEY).resolve_state(WORKSPACE, TEAM, STATE, "started") == STATE


@pytest.mark.parametrize("field", ["workspace", "team", "state", "category"])
def test_workflow_state_rejects_wrong_identity_or_category(monkeypatch, field):
    response = state_document()
    if field == "workspace":
        response["data"]["organization"]["id"] = OTHER
    elif field == "team":
        response["data"]["workflowState"]["team"]["id"] = OTHER
    elif field == "state":
        response["data"]["workflowState"]["id"] = OTHER
    else:
        response["data"]["workflowState"]["type"] = "canceled"
    serve(monkeypatch, lambda p: response)
    with pytest.raises(ProjectionTransportError):
        LinearProjectionTransport(KEY).resolve_state(WORKSPACE, TEAM, STATE, "started")


def issue_state(state_id=OTHER, state_type="unstarted"):
    return {"id": ISSUE, "team": {"id": TEAM}, "state": {"id": state_id, "type": state_type}}


def test_status_update_and_repeat_observation_converge_without_second_write(monkeypatch):
    current = issue_state()
    writes = []

    def handler(payload):
        nonlocal current
        if "FactoryProjectionState(" in payload["query"]:
            return state_document()
        if "FactoryProjectionIssueState(" in payload["query"]:
            return {"data": {"issue": current}}
        writes.append(payload["variables"])
        current = issue_state(STATE, "started")
        return {"data": {"issueUpdate": {"success": True, "issue": current}}}

    serve(monkeypatch, handler)
    transport = LinearProjectionTransport(KEY)
    first = transport.update_issue_state(WORKSPACE, ISSUE, TEAM, STATE, "started")
    assert first.state_id == STATE
    assert transport.update_issue_state(WORKSPACE, ISSUE, TEAM, STATE, "started") == first
    assert writes == [{"id": ISSUE, "input": {"stateId": STATE}}]


@pytest.mark.parametrize("state_type", ["completed", "canceled"])
def test_terminal_state_is_not_downgraded(monkeypatch, state_type):
    def handler(payload):
        if "FactoryProjectionState(" in payload["query"]:
            return state_document()
        if "FactoryProjectionIssueState(" in payload["query"]:
            return {"data": {"issue": issue_state(OTHER, state_type)}}
        pytest.fail("terminal issue was mutated")

    serve(monkeypatch, handler)
    with pytest.raises(ProjectionTransportError, match="Terminal"):
        LinearProjectionTransport(KEY).update_issue_state(WORKSPACE, ISSUE, TEAM, STATE, "started")


def test_attachment_lost_response_recovers_after_journal_restart(monkeypatch, tmp_path):
    from dataclasses import asdict

    from swfactory.idempotency import MutationOutcome, OperationJournal, OperationRef

    remote = None
    writes = []

    def handler(payload):
        nonlocal remote
        if payload["query"] == module.ATTACH:
            writes.append(payload["variables"]["input"])
            remote = row()
            raise OSError("response lost after server commit")
        return {
            "data": {
                "attachmentsForURL": {"nodes": [] if remote is None else [remote], "pageInfo": {"hasNextPage": False}}
            }
        }

    serve(monkeypatch, handler)
    transport = LinearProjectionTransport(KEY)
    ref = OperationRef.build("cell_0769b1604171d921fa6d6ffa", 1, "linear_attachment", ISSUE, URL, HEAD)
    database = tmp_path / "operations.sqlite3"
    journal = OperationJournal(database)
    with pytest.raises(ProjectionTransportError):
        journal.execute(
            ref,
            lambda: asdict(transport.attach_pr(ISSUE, URL, HEAD)),
            replay_safe=True,
            intent_digest="sha256:" + "c" * 64,
        )
    assert journal.get(ref.key)["state"] == "in_doubt"
    journal.close()
    restarted = OperationJournal(database)
    try:

        def reconcile():
            receipt = transport.observe_attachment(ISSUE, URL, HEAD)
            return (
                MutationOutcome("definitely_absent")
                if receipt is None
                else MutationOutcome("committed", asdict(receipt))
            )

        recovered = restarted.execute(
            ref,
            lambda: pytest.fail("attachment write repeated"),
            replay_safe=True,
            reconcile=reconcile,
            intent_digest="sha256:" + "c" * 64,
        )
        assert recovered == {"attachment_id": ATTACHMENT, "issue_id": ISSUE, "url": URL, "head_sha": HEAD}
        assert restarted.get(ref.key)["state"] == "committed"
        assert len(writes) == 1
        assert (
            restarted.execute(ref, lambda: pytest.fail("committed effect repeated"), intent_digest="sha256:" + "c" * 64)
            == recovered
        )
    finally:
        restarted.close()


def test_status_lost_response_recovers_from_remote_state_without_second_write(monkeypatch, tmp_path):
    from dataclasses import asdict

    from swfactory.idempotency import MutationOutcome, OperationJournal, OperationRef

    current = issue_state()
    writes = []

    def handler(payload):
        nonlocal current
        if "FactoryProjectionState(" in payload["query"]:
            return state_document()
        if "FactoryProjectionIssueState(" in payload["query"]:
            return {"data": {"issue": current}}
        writes.append(payload["variables"])
        current = issue_state(STATE, "started")
        raise OSError("state committed but reply lost")

    serve(monkeypatch, handler)
    transport = LinearProjectionTransport(KEY)
    ref = OperationRef.build("cell_0769b1604171d921fa6d6ffa", 1, "linear_state", ISSUE, STATE, HEAD)
    database = tmp_path / "state.sqlite3"
    journal = OperationJournal(database)
    with pytest.raises(ProjectionTransportError):
        journal.execute(
            ref,
            lambda: asdict(transport.update_issue_state(WORKSPACE, ISSUE, TEAM, STATE, "started")),
            replay_safe=True,
            intent_digest="sha256:" + "d" * 64,
        )
    journal.close()
    restarted = OperationJournal(database)
    try:
        receipt = transport.observe_issue_state(ISSUE, TEAM)
        assert receipt.state_id == STATE and receipt.state_type == "started"
        result = restarted.execute(
            ref,
            lambda: pytest.fail("status write repeated"),
            replay_safe=True,
            reconcile=lambda: MutationOutcome("committed", asdict(receipt)),
            intent_digest="sha256:" + "d" * 64,
        )
        assert result["state_id"] == STATE
        assert len(writes) == 1
    finally:
        restarted.close()


def source_document():
    return {
        "data": {
            "organization": {"id": WORKSPACE, "urlKey": "factory-fixture"},
            "issue": {
                "id": ISSUE,
                "identifier": "YOS-134",
                "url": "https://linear.app/factory-fixture/issue/YOS-134/projection",
                "title": "Preserve accepted work",
                "description": "Exact acceptance criteria",
                "updatedAt": "2026-10-07T07:00:00Z",
                "archivedAt": None,
                "team": {"id": TEAM},
                "project": {"id": OTHER},
                "state": {"type": "unstarted"},
            },
        }
    }


def accepted_document():
    from swfactory.linear_intake import accepted_source
    from swfactory.linear_source import parse_preview

    preview = parse_preview(source_document(), workspace_id=WORKSPACE, project_id=OTHER, issue_id=ISSUE)
    return accepted_source(preview), "linear_" + WORKSPACE.replace("-", "") + "_" + ISSUE.replace("-", "")


def test_source_validation_preserves_intent_across_status_change(monkeypatch):
    accepted, ref = accepted_document()
    response = source_document()
    response["data"]["issue"]["state"]["type"] = "started"
    serve(monkeypatch, lambda p: response)
    current = LinearProjectionTransport(KEY).validate_accepted_source(accepted, ref)
    assert current.intent_digest == accepted["intent_digest"]
    assert current.state_type == "started"


@pytest.mark.parametrize("field", ["title", "description", "team", "project", "workspace"])
def test_changed_source_identity_or_intent_refuses_projection(monkeypatch, field):
    accepted, ref = accepted_document()
    response = source_document()
    if field == "workspace":
        response["data"]["organization"]["id"] = TEAM
    elif field in {"team", "project"}:
        response["data"]["issue"][field]["id"] = STATE
    else:
        response["data"]["issue"][field] = "changed"
    serve(monkeypatch, lambda p: response)
    with pytest.raises(ProjectionTransportError):
        LinearProjectionTransport(KEY).validate_accepted_source(accepted, ref)


def test_corrupt_accepted_snapshot_never_reaches_network(monkeypatch):
    accepted, ref = accepted_document()
    accepted["snapshot"]["title"] = "tampered"
    serve(monkeypatch, lambda p: pytest.fail("corrupt snapshot reached remote"))
    with pytest.raises(ProjectionTransportError):
        LinearProjectionTransport(KEY).validate_accepted_source(accepted, ref)


@pytest.mark.parametrize("operation", ["attachment", "state"])
@pytest.mark.parametrize("change", ["description", "archived", "canceled", "duplicate"])
def test_accepted_writes_refuse_changed_or_withdrawn_source(monkeypatch, operation, change):
    accepted, ref = accepted_document()
    response = source_document()
    issue = response["data"]["issue"]
    if change == "description":
        issue["description"] = "Different acceptance criteria"
    elif change == "archived":
        issue["archivedAt"] = "2026-10-07T08:00:00Z"
    else:
        issue["state"]["type"] = change
    reads = []

    def handler(payload):
        assert payload["query"] == module.ISSUE_QUERY
        reads.append(payload["variables"])
        return response

    serve(monkeypatch, handler)
    transport = LinearProjectionTransport(KEY)
    with pytest.raises(ProjectionTransportError):
        if operation == "attachment":
            transport.attach_accepted_pr(accepted, ref, URL, HEAD)
        else:
            transport.update_accepted_issue_state(accepted, ref, STATE, "started")
    assert reads == [{"id": ISSUE}]


def test_accepted_attachment_checks_source_before_write(monkeypatch):
    accepted, ref = accepted_document()
    queries = []

    def handler(payload):
        queries.append(payload["query"])
        if payload["query"] == module.ISSUE_QUERY:
            return source_document()
        assert payload["variables"]["input"]["issueId"] == ISSUE
        return {"data": {"attachmentCreate": {"success": True, "attachment": row()}}}

    serve(monkeypatch, handler)
    receipt = LinearProjectionTransport(KEY).attach_accepted_pr(accepted, ref, URL, HEAD)
    assert receipt.issue_id == ISSUE
    assert queries == [module.ISSUE_QUERY, module.ATTACH]


def test_accepted_status_uses_source_workspace_and_team(monkeypatch):
    accepted, ref = accepted_document()
    queries = []

    def handler(payload):
        queries.append(payload["query"])
        if payload["query"] == module.ISSUE_QUERY:
            return source_document()
        if "FactoryProjectionState(" in payload["query"]:
            return state_document()
        if "FactoryProjectionIssueState(" in payload["query"]:
            return {"data": {"issue": issue_state()}}
        assert payload["variables"] == {"id": ISSUE, "input": {"stateId": STATE}}
        return {"data": {"issueUpdate": {"success": True, "issue": issue_state(STATE, "started")}}}

    serve(monkeypatch, handler)
    receipt = LinearProjectionTransport(KEY).update_accepted_issue_state(accepted, ref, STATE, "started")
    assert receipt.team_id == TEAM
    assert len(queries) == 4
    assert queries[0] == module.ISSUE_QUERY
