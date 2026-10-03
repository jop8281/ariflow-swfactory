---
id: SELFHOST-2
title: The swfactory gateway allowlist blocks islo.yaml's own uv installer
labels:
- factory
- selfhost
- islo
url: file:///private/var/folders/w2/81x9sfys2dl6v07z7wnq7yt40000gp/T/swf-stress.SqrFaA/factory/demo/selfhost-2.md
run_id: fb18e643
---
Observed live on islo (2026-09-27, islo CLI 0.53.1): with a gateway profile built exactly from the
documented allowlist (`api.anthropic.com github.com api.github.com pypi.org files.pythonhosted.org
astral.sh`, default action deny), `islo use ... --init minimal` DOES run the repo-root `islo.yaml`
setup script, and that script fails:

    ✗ Setup failed: Setup script
      curl: (22) The requested URL returned error: 403

Cause: `https://astral.sh/uv/install.sh` answers `301 -> https://releases.astral.sh/installers/uv/latest/uv-installer.sh`,
and `releases.astral.sh` is not allowed. The installer's GitHub fallback redirects to
`release-assets.githubusercontent.com`, also not allowed. With both hosts added the setup script
succeeds and `uv sync --group dev` + the suite pass in the cell. Without them `uv` is missing, so
the contract's `uv run --group dev pytest` can never pass on islo.

Fix every place the allowlist is stated so the documented bootstrap produces a working cell:
- `GATEWAY_ALLOW_HOSTS` in `src/swfactory/doctor.py` (it feeds `gateway_fix`).
- `ALLOW_HOSTS` in `deploy/islo/bootstrap.sh`, and the allow comment in `deploy/islo/deploy.sh`.
- The gateway row of `docs/islo.md`.
- `docs/selfhost.md` still says it is "unsettled whether `islo use --init minimal` executes the
  repo-root `islo.yaml` setup script" - it is settled: it does, and it failed for exactly this reason.

Acceptance:
- `releases.astral.sh` and `release-assets.githubusercontent.com` are in all of the above.
- A hermetic test pins that `gateway_fix()` names both hosts, and that the doctor list and the
  bootstrap.sh `ALLOW_HOSTS` array contain the same hosts (read the shell file as text).
- Do not touch protected paths (factory.toml, blueprints/, scripts/, .github/, agent.py, sandbox.py, stages.py ...).
