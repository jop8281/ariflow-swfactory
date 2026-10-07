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
