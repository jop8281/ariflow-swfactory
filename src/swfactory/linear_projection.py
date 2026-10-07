"""Bounded Linear attachment transport for the trusted backend's operation journal."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from swfactory.linear_source import ENDPOINT, MAX_RESPONSE_BYTES

ATTACH = """mutation FactoryPRAttachment($input: AttachmentCreateInput!) {
  attachmentCreate(input: $input) { success attachment { id url metadata issue { id } } }
}"""
OBSERVE = """query FactoryPRAttachmentObservation($url: String!) {
  attachmentsForURL(url: $url) { nodes { id url metadata issue { id } } pageInfo { hasNextPage } }
}"""


class ProjectionTransportError(ValueError):
    """Remote outcome is unverified; callers must reconcile through the journal."""


def _uuid(value: str) -> str:
    try:
        canonical = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ProjectionTransportError("Projection identity must be a canonical UUID") from None
    if canonical != value:
        raise ProjectionTransportError("Projection identity must be a canonical UUID")
    return value


def _pr_url(value: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*", value) is None
    ):
        raise ProjectionTransportError("Projection requires a canonical GitHub PR URL")
    return value


def _head(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ProjectionTransportError("Projection requires an exact candidate head")
    return value


@dataclass(frozen=True)
class AttachmentReceipt:
    attachment_id: str
    issue_id: str
    url: str
    head_sha: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class LinearProjectionTransport:
    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.api_key or any(c.isspace() for c in self.api_key):
            raise ProjectionTransportError("Linear projection requires a trusted controller key")

    def _request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={"Authorization": self.api_key, "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            raise ProjectionTransportError(f"Linear projection returned HTTP {code}") from None
        except (OSError, urllib.error.URLError):
            raise ProjectionTransportError("Linear projection outcome is unverified") from None
        if len(raw) > MAX_RESPONSE_BYTES or self.api_key.encode() in raw:
            raise ProjectionTransportError("Linear projection response failed boundary checks")
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get("errors") or not isinstance(payload.get("data"), dict):
                raise ValueError
            return payload["data"]
        except (ValueError, UnicodeError):
            raise ProjectionTransportError("Linear projection response is invalid") from None

    @staticmethod
    def _receipt(row: object, issue_id: str, url: str, head_sha: str) -> AttachmentReceipt:
        if not isinstance(row, dict) or not isinstance(row.get("issue"), dict):
            raise ProjectionTransportError("Linear attachment receipt is invalid")
        if row["issue"].get("id") != issue_id or row.get("url") != url:
            raise ProjectionTransportError("Linear attachment receipt identity differs")
        if not isinstance(row.get("metadata"), dict) or row["metadata"].get("headSha") != head_sha:
            raise ProjectionTransportError("Linear attachment candidate head differs")
        return AttachmentReceipt(_uuid(row.get("id")), issue_id, url, head_sha)

    def observe_attachment(self, issue_id: str, url: str, head_sha: str) -> AttachmentReceipt | None:
        issue_id, url = _uuid(issue_id), _pr_url(url)
        _head(head_sha)
        data = self._request(OBSERVE, {"url": url})
        connection = data.get("attachmentsForURL")
        if (
            not isinstance(connection, dict)
            or not isinstance(connection.get("pageInfo"), dict)
            or connection["pageInfo"].get("hasNextPage") is not False
            or not isinstance(connection.get("nodes"), list)
        ):
            raise ProjectionTransportError("Linear attachment observation is incomplete")
        nodes = connection["nodes"]
        if any(not isinstance(row, dict) or not isinstance(row.get("issue"), dict) for row in nodes):
            raise ProjectionTransportError("Linear attachment observation is invalid")
        matches = [row for row in nodes if row["issue"].get("id") == issue_id]
        if len(matches) > 1:
            raise ProjectionTransportError("Linear attachment observation is ambiguous")
        return None if not matches else self._receipt(matches[0], issue_id, url, head_sha)

    def attach_pr(self, issue_id: str, url: str, head_sha: str) -> AttachmentReceipt:
        issue_id, url = _uuid(issue_id), _pr_url(url)
        _head(head_sha)
        data = self._request(
            ATTACH,
            {
                "input": {
                    "issueId": issue_id,
                    "url": url,
                    "title": "Factory pull request",
                    "metadata": {"headSha": head_sha},
                }
            },
        )
        result = data.get("attachmentCreate")
        if not isinstance(result, dict) or result.get("success") is not True:
            raise ProjectionTransportError("Linear attachment write is unverified")
        return self._receipt(result.get("attachment"), issue_id, url, head_sha)

    def resolve_state(self, workspace_id: str, team_id: str, state_id: str, state_type: str) -> str:
        workspace_id, team_id, state_id = _uuid(workspace_id), _uuid(team_id), _uuid(state_id)
        if state_type not in {"started", "completed"}:
            raise ProjectionTransportError("Projection state category is unsupported")
        data = self._request(
            """query FactoryProjectionState($id: String!) {
              organization { id }
              workflowState(id: $id) { id type team { id } }
            }""",
            {"id": state_id},
        )
        organization, state = data.get("organization"), data.get("workflowState")
        if not isinstance(organization, dict) or organization.get("id") != workspace_id:
            raise ProjectionTransportError("Linear workflow workspace differs")
        if not isinstance(state, dict) or not isinstance(state.get("team"), dict):
            raise ProjectionTransportError("Linear workflow state is invalid")
        if state.get("id") != state_id or state.get("type") != state_type or state["team"].get("id") != team_id:
            raise ProjectionTransportError("Linear workflow identity or category differs")
        return state_id
