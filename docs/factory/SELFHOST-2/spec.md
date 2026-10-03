# spec.md

## Requirements

**R1** `swfactory.doctor.GATEWAY_ALLOW_HOSTS` contains `"releases.astral.sh"`.

**R2** `swfactory.doctor.GATEWAY_ALLOW_HOSTS` contains `"release-assets.githubusercontent.com"`.

**R3** `GATEWAY_ALLOW_HOSTS` still contains, unchanged, the six existing hosts (`api.anthropic.com`, `github.com`, `api.github.com`, `pypi.org`, `files.pythonhosted.org`, `astral.sh`) — backwards compatibility: nothing is removed or renamed, so an already-bootstrapped profile stays valid and only needs two added rules.

**R4** `gateway_fix(profile)` names `releases.astral.sh` in its returned string (it interpolates `GATEWAY_ALLOW_HOSTS`, so this follows from R1 but is pinned separately per the intent's acceptance).

**R5** `gateway_fix(profile)` names `release-assets.githubusercontent.com`.

**R6** `gateway_fix(profile)` keeps its existing shape: it starts with `islo gateway create --name <profile> --default-action deny --internet-access true` and contains `add-rule --host <host> --action allow` (pinned today by `tests/test_doctor.py::test_missing_gateway_profile`).

**R7** The `ALLOW_HOSTS=(...)` array in `deploy/islo/bootstrap.sh` (line 23) lists both new hosts.

**R8** The set of hosts parsed out of `deploy/islo/bootstrap.sh`'s `ALLOW_HOSTS` array, read as **text** (no shell execution), equals `set(doctor.GATEWAY_ALLOW_HOSTS)` — one hermetic test, so the two lists can never drift again.

**R9** The `allow:` comment block in `deploy/islo/deploy.sh` (lines 12–13, the orchestrator profile) lists both new hosts alongside its existing `islo.dev` / `releases.islo.dev` entries; that profile's setup script runs the same `astral.sh` installer (`deploy/islo/orchestrator/islo.yaml:25`).

**R10** Both gateway host lists in `docs/islo.md` — the Agents row of the trust table (line 10) and the `gateway` row of the bootstrap table (line 52) — list both new hosts.

**R11** `docs/selfhost.md` no longer claims it is "unsettled whether `islo use --init minimal` executes the repo-root `islo.yaml` setup script" (lines 147–150); the replacement states that it does execute it, that the script failed with `curl: (22) ... 403` under the six-host allowlist, and names the two redirect targets as the cause. Observation date/CLI version (2026-09-27, islo 0.53.1) are recorded.

**R12** The adjacent unproven-evidence claims in that same `docs/selfhost.md` paragraph (no real-model run, no islo run, no self-authored merged PR) are preserved — only the `--init minimal` uncertainty is resolved.

**R13** Error/edge case: the parity test (R8) fails loudly with a readable diff if `bootstrap.sh` is missing the `ALLOW_HOSTS=` line or the array is reformatted such that no hosts can be extracted (an empty parse is a failure, never a vacuous pass).

**R14** No protected path is modified: `factory.toml`, `blueprints/`, `dags/`, `scripts/`, `.github/`, `src/swfactory/agent.py`, `sandbox.py`, `stages.py` and the rest of `factory.toml`'s `protected` list stay byte-identical. `src/swfactory/doctor.py`, `deploy/**`, `docs/**` and `tests/**` are not protected for `build`.

**R15** The whole suite stays hermetic: the new test performs no network access and no `islo`/`curl` invocation — it reads `GATEWAY_ALLOW_HOSTS` and the shell file from the repo tree only.

## API

No new or removed exported names; no signature changes.

- `swfactory.doctor.GATEWAY_ALLOW_HOSTS: tuple[str, ...]` — value changes from 6 to 8 entries (the six existing, plus `releases.astral.sh` and `release-assets.githubusercontent.com`). Remains a module-level frozen tuple of lowercase bare hostnames (no scheme, no path).
- `swfactory.doctor.gateway_fix(profile: str) -> str` — unchanged signature and return type; the returned remediation string now enumerates 8 hosts. Raises nothing.
- `_check_gateway` / `run_doctor` behaviour unchanged: the doctor validates `default_action == "deny"` and `internet_enabled is True` only; it never enumerates the profile's actual rules, so adding hosts changes no check outcome, exit code, or the `11 checks` table shape.
- `deploy/islo/bootstrap.sh`: `ALLOW_HOSTS` bash array (8 elements) consumed by its existing idempotent `add-rule` loop; no new flags or env vars.
- Test surface: one new hermetic test in `tests/` (natural home `tests/test_doctor.py`, which already imports `doctor` and iterates `GATEWAY_ALLOW_HOSTS`).

## Concerns

- **Correctness — silent drift between Python and shell.** Mitigated by R8: parity is asserted, not documented.
- **Correctness — vacuous parity test.** A regex that stops matching after a reformat would pass trivially; R13 requires the empty-parse case to fail.
- **Security — allowlist widening.** Two hosts are added to a deny-by-default profile. Both are narrow, vendor-owned redirect targets of tooling already allowed (`astral.sh`, `github.com`); no wildcard, no CDN-wide entry, and `crates.io` stays absent so `factory.toml`'s Python-only test command rationale (lines 21–24) and `docs/selfhost.md:78-81` remain true. `release-assets.githubusercontent.com` serves GitHub release assets only; it grants no API or write capability, and no GitHub token ever enters the cell.
- **Security — self-hosting.** The change lives in `doctor.py` + `deploy/` + `docs/` + `tests/`; R14 keeps the confinement modules and contract untouched, so the cell does not widen its own cage.
- **Performance.** Two extra `islo gateway add-rule` calls in a one-time idempotent bootstrap; negligible. No runtime cost in `doctor`.
- **Maintainability — five statements of one list.** The Python tuple is the single source of truth for the shell array (R8); the three prose sites (`deploy.sh` comment, `docs/islo.md` ×2, `docs/selfhost.md`) stay human-maintained and are not test-pinned beyond the intent's acceptance, to avoid brittle doc-string assertions.

## Open questions

1. **Should `config.SRT_DEFAULT_DOMAINS` (`src/swfactory/config.py:28`) also gain the two hosts?** It lists `astral.sh` for the srt backend and has the identical redirect exposure. *Assumption:* out of scope — the intent enumerates the islo gateway sites only; left unchanged and flagged here.
2. **Does the orchestrator profile comment count as "the allowlist"?** `deploy/islo/deploy.sh:12` is named by the intent, so it is in scope (R9); the near-duplicate host list in the comment at `deploy/islo/orchestrator/islo.yaml:12` is not named. *Assumption:* update `deploy.sh` per the intent and leave `orchestrator/islo.yaml` alone, since both files would otherwise describe the same profile inconsistently — noted as the one residual inconsistency.
3. **Exact `ALLOW_HOSTS` parse rule.** *Assumption:* extract the text between `ALLOW_HOSTS=(` and the next `)` and split on whitespace; the array stays a single line with bare hostnames and no quoting or comments so this parse is exact.
4. **Which file holds the new test.** *Assumption:* `tests/test_doctor.py`, extending the existing gateway-fix tests rather than adding a module.
5. **Whether the 403 evidence belongs verbatim in `docs/selfhost.md`.** *Assumption:* yes — one short quoted `curl: (22) ... 403` line plus the two redirect hosts, keeping the paragraph's evidence-only tone and not claiming a green end-to-end islo run (none is claimed by this issue beyond "the setup script succeeds and the suite passes in the cell").
