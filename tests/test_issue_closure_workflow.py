"""Workflow inputs remain data when invoking the issue-closure command."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("step_name", ["Validate release issue manifest", "Close only manifest-declared issues"])
def test_issue_closure_does_not_execute_manifest_input(tmp_path, step_name):
    document = yaml.safe_load((REPO / ".github/workflows/close-release-issues.yml").read_text())
    job = document["jobs"]["close-release-issues"]
    step = next(step for step in job["steps"] if step.get("name") == step_name)
    marker = tmp_path / "executed"
    manifest = f"$(touch {shlex.quote(str(marker))})"
    # Emulate GitHub interpolation as well as the process environment. A directly interpolated
    # value executes the command substitution before Python can reject the missing manifest.
    command = step["run"].replace("${{ inputs.manifest_path }}", manifest)
    environment = {"PATH": os.environ["PATH"], "GITHUB_REPOSITORY": "example/repo"}
    environment.update(
        {key: str(value).replace("${{ inputs.manifest_path }}", manifest) for key, value in job.get("env", {}).items()}
    )
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-ec", command],
        cwd=REPO,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert not marker.exists()
    assert result.returncode == 2
    assert "manifest does not exist" in result.stderr
