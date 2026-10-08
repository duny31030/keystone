# Release & Publishing

> How keystone's version numbers move and how a release reaches npm and PyPI.

---

## Overview

Keystone ships to two registries from one repository: a Python distribution
(`keystone-hook` on PyPI, built from `src/keystone`) and an npm package
(`keystone-hook`, which embeds a copy of the same Python source and starts it
through a Node shim). Both are published by GitHub Actions when a `v*` tag is
pushed. There is no manual `npm publish` step in the normal flow.

---

## Version: one source, five copies

`pyproject.toml` → `[project] version` is the **only** place a human edits the
version. Everything else is a consumer:

| Location | Who writes it | Enforced by |
|---|---|---|
| `pyproject.toml` | human (source of truth) | — |
| `src/keystone/__init__.py` `__version__` | human, must match | `scripts/release.sh` preflight only — **no test asserts this** |
| `npm/package.json` `version` | `scripts/sync_npm.py` | CI post-sync check |
| `npm/python/keystone/**` | `scripts/sync_npm.py` (copy of `src/keystone`) | CI post-sync `git diff --exit-code` |
| `npm/README.md`, `npm/LICENSE` | `scripts/sync_npm.py` (copy from root) | CI post-sync `git diff --exit-code` |

`sync_npm.py` is the single sync mechanism. Never hand-edit anything under
`npm/python/`, `npm/package.json`, `npm/README.md`, or `npm/LICENSE` — they are
generated and a later sync (in CI) will either overwrite the edit or fail the
build.

**Rule**: after any version bump, run `python3 scripts/sync_npm.py` and commit
the result. CI checks that a clean checkout plus one sync run produces no diff.

---

## Release flow

```
./scripts/release.sh 0.3.0          git push of tag v0.3.0
        │                                    │
        ├─ preflight: clean tree             ▼
        ├─ three-way version match      ┌─ build (gates) ─┐
        ├─ pytest                       ├─ publish-pypi   │ needs: build
        ├─ sync_npm.py                  └─ publish-npm    ┘
        ├─ uv build + npm pack
        ├─ tag v<version>
        └─ git push origin main --tags
```

`release.sh` prepares and tags; **it does not publish**. The tag push is what
publishes, via `.github/workflows/release.yml`. Never publish by hand — the
workflow is the only path that runs the gates first.

### CI gates, in order (`build` job)

1. **tag↔pyproject version match.** `GITHUB_REF_NAME` with one leading `v`
   stripped must equal `pyproject.toml`'s version. Fails fast on a mis-tagged
   push, before any install or test work.
2. **`pytest`.** A red test blocks both publish jobs via `needs: build`.
3. **`sync_npm.py`**, then **no-drift check**: version equality *and*
   `git diff --exit-code` over the generated npm paths. Catches a stale
   committed payload, not just a stale version string.
4. **Build once** (`python -m build`, `npm pack`) and upload two artifacts:
   `python-dist` and `npm-tarball`.
5. **Publish jobs download those artifacts — they never rebuild.** What was
   tested is what is published; publishing a fresh build would break that
   invariant.

---

## Idempotency

Re-running a workflow for an already-published tag must succeed, not error.

- **PyPI**: `skip-existing: true` on `pypa/gh-action-pypi-publish` (registry-side).
- **npm**: no equivalent flag exists, so the workflow probes first. The probe's
  exit-code contract is the mechanism:

  | Command | Version exists | Version absent |
  |---|---|---|
  | `npm view keystone-hook@<v> version` | stdout `<v>`, **exit 0** | stderr `E404 No match found for version`, **exit 1** |

  Exit 0 → print a skip notice and stop. Non-zero → publish. The probe fails
  **closed**: a registry outage makes it look like "absent", which degrades to a
  publish attempt that npm rejects — it cannot silently skip a needed publish.

---

## Credentials

| Secret | Consumed as | Scope needed |
|---|---|---|
| `PYPI_TOKEN` | `password:` input of `gh-action-pypi-publish` | account-scoped for the **first** publish, then project-scoped |
| `NPM_TOKEN` | `NODE_AUTH_TOKEN` env on `npm publish` | npm automation token |

Both are configured by the repository owner in GitHub → Settings → Secrets.
`gh-action-pypi-publish` has **no `token:` input** — the token goes in
`password:` and `user` stays at its `__token__` default. Do not add a
`permissions:` block: token auth does not need `id-token: write` (that is
OIDC-only).

---

## Non-obvious constraints

- **This repository is private, so PyPI trusted publishing (OIDC) is
  unavailable.** PyPI's trusted-publisher config requires a public repo. Token
  auth is not a preference here, it is the only option.
- **First PyPI publish needs an account-scoped token.** A project-scoped token
  cannot be created before the project exists on pypi.org.
- **Publishing is irreversible.** PyPI allows yanking (version stays, is not
  resolved by default); npm allows unpublish only within 72 hours. A pushed tag
  is therefore a published release — recovery means shipping a new version, not
  retracting one.
- **Do not rename the `build` job** without checking branch-protection required
  status checks; a required check whose name no longer exists is unsatisfiable.
- The `npm` `latest` tag is what a plain `npm install -g keystone-hook`
  resolves. A version published but not tagged `latest` (e.g. publishing an
  older version after a newer one) will not be picked up by default.

---

## Common Mistakes

| Mistake | Symptom |
|---|---|
| Bumping only `pyproject.toml` and tagging | CI fails at the post-sync no-drift check; tag exists but nothing publishes |
| Hand-editing `npm/python/**` | Edit is silently reverted by the next sync, or fails the CI drift check |
| Tagging before `release.sh` commits the sync | Committed npm payload is stale; CI drift check fails |
| Expecting `release.sh` to publish | Nothing appears on the registries; only the tag push does |
| Tagging `v0.3.0` while pyproject says `0.2.1` | `build` fails at step 1, by design |