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
    return {"id": ATTACHMENT, "url": URL, "issue": {"id": issue}}


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
    assert transport.observe_attachment(ISSUE, URL) == first
    assert (
        writes == [{"issueId": ISSUE, "url": URL, "title": "Factory pull request", "metadata": {"headSha": HEAD}}] * 2
    )
    assert KEY not in repr(transport)


@pytest.mark.parametrize("nodes,more", [([], True), ([row(), row()], False), ([None], False)])
def test_incomplete_or_ambiguous_observation_refuses(monkeypatch, nodes, more):
    serve(monkeypatch, lambda p: {"data": {"attachmentsForURL": {"nodes": nodes, "pageInfo": {"hasNextPage": more}}}})
    with pytest.raises(ProjectionTransportError):
        LinearProjectionTransport(KEY).observe_attachment(ISSUE, URL)


def test_missing_attachment_is_absent_only_after_complete_observation(monkeypatch):
    serve(
        monkeypatch,
        lambda p: {"data": {"attachmentsForURL": {"nodes": [row(OTHER)], "pageInfo": {"hasNextPage": False}}}},
    )
    assert LinearProjectionTransport(KEY).observe_attachment(ISSUE, URL) is None


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
        LinearProjectionTransport(KEY).observe_attachment(ISSUE, URL)
