"""Checked-in authority for unattended work, never agent-selected permissions."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import sqlite3
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from swfactory.config import FACTORY_ROOT
from swfactory.models import Approval, BoundaryModel, Issue, StageError
from swfactory.paths import normalize_relative_path

LINE = "autonomous"


class AutonomousPolicy(BoundaryModel):
    schema_version: Literal[1]
    enabled: bool
    repository: str
    base_branch: str
    required_labels: list[str] = Field(min_length=1)
    denied_labels: list[str]
    allowed_paths: list[str] = Field(min_length=1)
    protected_paths: list[str]
    budget_usd: float = Field(gt=0)
    required_checks: list[str] = Field(min_length=1)
    checks_app_id: int = Field(gt=0)
    max_files: int = Field(gt=0, le=100)
    merge_timeout_s: int = Field(gt=0, le=86400)
    revision: str = ""

    @field_validator("allowed_paths", "protected_paths")
    @classmethod
    def safe_patterns(cls, values: list[str]) -> list[str]:
        for value in values:
            normalize_relative_path(value.rstrip("/"), field="policy path")
        return values

    def issue_reason(self, issue: Issue, repository: str) -> str | None:
        if not self.enabled:
            return "policy_disabled"
        if repository != self.repository:
            return "repository_outside_policy"
        if issue.state != "open":
            return "issue_not_open"
        if not set(self.required_labels) <= set(issue.labels):
            return "required_labels_missing"
        if set(self.denied_labels) & set(issue.labels):
            return "denied_label"
        if not issue.title.strip() or not issue.body.strip():
            return "missing_intent"
        return None

    def check_paths(self, paths: list[str], *, artifact_prefix: str | None = None) -> None:
        if not paths or len(set(paths)) > self.max_files:
            raise StageError("policy", "empty or oversized autonomous change")
        for path in paths:
            normalized = normalize_relative_path(path, field="autonomous change path")
            if normalized != path:
                raise StageError("policy", "autonomous paths must be canonical")
            # Only the host-generated chain for this issue may be included in publication.
            if artifact_prefix and path.startswith(artifact_prefix + "/"):
                continue
            if any(_matches(path, pattern) for pattern in self.protected_paths):
                raise StageError("policy", f"protected path: {path}")
            if not any(_matches(path, pattern) for pattern in self.allowed_paths):
                raise StageError("policy", f"path outside autonomous policy: {path}")

    def check_budget(self, cost: float, ceiling: float) -> None:
        if not 0 <= cost <= self.budget_usd or not 0 < ceiling <= self.budget_usd:
            raise StageError("policy", "autonomous budget exceeds checked-in authority")


def _matches(path: str, pattern: str) -> bool:
    return (
        path == pattern.rstrip("/") or path.startswith(pattern.rstrip("/") + "/") or fnmatch.fnmatchcase(path, pattern)
    )


def load_policy(root: Path = FACTORY_ROOT) -> AutonomousPolicy:
    raw = (root / "config/autonomous.toml").read_bytes()
    document = tomllib.loads(raw.decode())
    # A policy revision binds the limits, protection contract, review skill and line itself.
    contract = tomllib.loads((root / "factory.toml").read_text())
    protected = contract["paths"]["protected"]
    authority = [raw, json.dumps(protected, sort_keys=True).encode()]
    authority.extend((root / name).read_bytes() for name in ("REVIEW.md", "blueprints/autonomous.toml"))
    document["protected_paths"] = list(dict.fromkeys(document["protected_paths"] + protected))
    document["revision"] = hashlib.sha256(b"\0".join(authority)).hexdigest()
    return AutonomousPolicy.model_validate(document)


class AutonomyStore:
    """Immutable decisions per Cell epoch, with durable blocked triage outcomes."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS decisions (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def bind(self, key: str, value: dict) -> dict:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO decisions VALUES (?, ?)", (key, encoded))
            previous = db.execute("SELECT value FROM decisions WHERE key = ?", (key,)).fetchone()[0]
        if previous != encoded:
            raise StageError("policy", "autonomous decision changed at the same Cell epoch")
        return value

    def get(self, key: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT value FROM decisions WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None


def gate_key(cell_id: str, epoch: int, gate: str) -> str:
    return f"{cell_id}:{epoch}:gate:{gate}"


def policy_approval(ctx, gate: str) -> Approval:
    """Ask the backend to approve current host-owned evidence, never a model's yes/no."""
    from swfactory import accepted_inputs
    from swfactory.backend_scm import BackendScm
    from swfactory.models import Plan
    from swfactory.stages import _gate_artifact, _persisted, cell_evidence

    if not isinstance(ctx.scm, BackendScm) or not cell_evidence(ctx)[2]:
        raise StageError("policy", "policy gates require a backend-managed Cell")
    policy = load_policy()
    artifact = ctx.read_artifact(_gate_artifact(ctx, gate))
    plan = Plan.model_validate_json(ctx.read_artifact(f"{ctx.art}/plan.json")) if gate == "plan" else None
    result = ctx.scm.autonomous_gate(
        gate=gate,
        revision=policy.revision,
        artifact_sha256=hashlib.sha256(artifact.encode()).hexdigest(),
        inputs_digest=accepted_inputs.require(ctx.state).digest,
        paths=plan.files if plan else [],
        plan_sha256=(hashlib.sha256(ctx.read_artifact(f"{ctx.art}/plan.json").encode()).hexdigest() if plan else None),
        cost_usd=sum(stage.cost_usd for stage in _persisted(ctx)),
        budget_usd=ctx.cfg.max_budget_usd,
    )
    return Approval.model_validate(result)
