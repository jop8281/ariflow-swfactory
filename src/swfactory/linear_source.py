"""Read-only Linear source previews on a trusted controller, before managed intake exists."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from swfactory.security_contract import redact_text

ENDPOINT = "https://api.linear.app/graphql"
MAX_RESPONSE_BYTES = 1024 * 1024
ISSUE_QUERY = """query FactoryLinearPreview($id: String!) {
  organization { id urlKey }
  issue(id: $id) {
    id identifier url title description updatedAt archivedAt
    team { id }
    project { id }
    state { type }
  }
}"""


class LinearSourceError(ValueError):
    """A refused source read. Messages never contain remote content or credentials."""


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise LinearSourceError("Linear identity must be an immutable UUID")
    try:
        canonical = str(UUID(value))
    except ValueError:
        raise LinearSourceError("Linear identity must be an immutable UUID") from None
    if value.lower() != canonical or canonical == str(UUID(int=0)):
        raise LinearSourceError("Linear identity must be a nonzero hyphenated UUID")
    return canonical


def _text(value: object, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise LinearSourceError("Linear response has a missing or invalid text field")
    if len(value) > MAX_RESPONSE_BYTES:
        raise LinearSourceError("Linear response text exceeds preview limit")
    if redact_text(value) != value or re.search(r"\blin_api_[A-Za-z0-9_-]+", value):
        raise LinearSourceError("Linear source contains credential-like content")
    return value


def _timestamp(value: object) -> str:
    value = _text(value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise LinearSourceError("Linear response has an invalid timestamp") from None
    if parsed.tzinfo is None:
        raise LinearSourceError("Linear timestamp must include a timezone")
    return value


@dataclass(frozen=True)
class LinearPreview:
    workspace_id: str
    issue_id: str
    identifier: str
    url: str
    team_id: str
    project_id: str
    title: str
    description: str
    updated_at: str
    state_type: str
    archived_at: str | None

    @property
    def source_key(self) -> str:
        return f"linear:{self.workspace_id}:{self.issue_id}"

    @property
    def intent_digest(self) -> str:
        content = {
            "source_key": self.source_key,
            "team_id": self.team_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
        }
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": "linear_source_preview",
            "admission_ready": False,
            "source_key": self.source_key,
            "intent_digest": self.intent_digest,
            **asdict(self),
        }


def parse_preview(payload: object, *, workspace_id: str, project_id: str, issue_id: str) -> LinearPreview:
    """Validate a complete GraphQL read without treating its status as delivery evidence."""
    workspace_id, project_id, issue_id = map(_uuid, (workspace_id, project_id, issue_id))
    if not isinstance(payload, dict) or payload.get("errors"):
        raise LinearSourceError("Linear returned GraphQL errors or an invalid document")
    try:
        data = payload["data"]
        organization, issue = data["organization"], data["issue"]
        if _uuid(organization["id"]) != workspace_id:
            raise LinearSourceError("Linear workspace differs from the configured workspace")
        if _uuid(issue["id"]) != issue_id:
            raise LinearSourceError("Linear issue differs from the requested UUID")
        if _uuid(issue["project"]["id"]) != project_id:
            raise LinearSourceError("Linear project differs from the configured project")
        identifier = _text(issue["identifier"])
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*-[1-9][0-9]*", identifier):
            raise LinearSourceError("Linear response has an invalid display identifier")
        workspace_slug = _text(organization["urlKey"])
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", workspace_slug):
            raise LinearSourceError("Linear response has an invalid workspace URL key")
        url = _text(issue["url"])
        try:
            parsed = urlsplit(url)
        except ValueError:
            raise LinearSourceError("Linear response has an invalid canonical issue URL") from None
        expected_path = f"/{workspace_slug}/issue/{identifier}"
        if (
            any(character.isspace() for character in url)
            or parsed.scheme != "https"
            or parsed.netloc != "linear.app"
            or parsed.query
            or parsed.fragment
            or not (parsed.path == expected_path or parsed.path.startswith(expected_path + "/"))
        ):
            raise LinearSourceError("Linear response has an invalid canonical issue URL")
        state_type = _text(issue["state"]["type"])
        if state_type not in {"triage", "backlog", "unstarted", "started", "completed", "canceled", "duplicate"}:
            raise LinearSourceError("Linear response has an unsupported workflow state")
        return LinearPreview(
            workspace_id=workspace_id,
            issue_id=issue_id,
            identifier=identifier,
            url=url,
            team_id=_uuid(issue["team"]["id"]),
            project_id=project_id,
            title=_text(issue["title"]),
            description="" if issue["description"] is None else _text(issue["description"], empty=True),
            updated_at=_timestamp(issue["updatedAt"]),
            state_type=state_type,
            archived_at=None if issue["archivedAt"] is None else _timestamp(issue["archivedAt"]),
        )
    except (KeyError, TypeError, AttributeError):
        raise LinearSourceError("Linear response is missing required source fields") from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class LinearSource:
    api_key: str = field(repr=False)
    workspace_id: str
    project_id: str

    def __post_init__(self) -> None:
        _uuid(self.workspace_id)
        _uuid(self.project_id)
        if not self.api_key or any(c.isspace() for c in self.api_key):
            raise LinearSourceError("A Linear personal API key is required on the trusted controller")

    def preview(self, issue_id: str) -> LinearPreview:
        issue_id = _uuid(issue_id)
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps({"query": ISSUE_QUERY, "variables": {"id": issue_id}}).encode(),
            headers={"Authorization": self.api_key, "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            error.close()
            raise LinearSourceError(f"Linear source read failed with HTTP {error.code}") from None
        except (OSError, urllib.error.URLError):
            raise LinearSourceError("Linear source read failed; retry the read after checking connectivity") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise LinearSourceError("Linear response exceeds preview limit")
        if self.api_key.encode() in raw:
            raise LinearSourceError("Linear source response contains the controller credential")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise LinearSourceError("Linear returned invalid JSON") from None
        return parse_preview(payload, workspace_id=self.workspace_id, project_id=self.project_id, issue_id=issue_id)
