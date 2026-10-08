# Research: CI publish mechanics (PyPI token + npm, tag-triggered)

- Query: exact technical mechanics for a tag-triggered GH Actions release workflow publishing to production PyPI (token auth) and npmjs
- Scope: external (action docs + empirical probes) + internal (repo state)
- Date: 2026-10-08
- Consumer: implementation agent. Snippets are verified where marked "verified".

## Repo facts observed (read-only)

- `.github/workflows/release.yml` already exists: `on: push: tags: ['v*']`, one `test` job that runs pytest + `sync_npm.py` + `python -m build` + `npm pack`, uploads artifact `release-artifacts` with `path: | dist/ ; npm/*.tgz`. Publish jobs are commented out.
- `pyproject.toml` line 7: `version = "0.2.1"` (only one `version =` line in file; `requires-python = ">=3.9"`, setuptools backend, `readme = "README.md"`).
- `npm/package.json`: `name = keystone-hook` (UNSCOPED), `version = 0.2.1`, has `repository` field.
- npm registry live state: `npm view keystone-hook dist-tags` -> `{ latest: '0.1.0' }`; `versions` -> `['0.1.0']`.
- PyPI: `https://pypi.org/pypi/keystone-hook/json` -> HTTP 404 (not registered).
- `scripts/release.sh` tail still prints manual `npm publish` / `uv publish --publish-url https://test.pypi.org/legacy/` hints (R9 target).
- Local toolchain: node v22.22.3, npm 10.9.8, uv 0.12.17, python 3.14.7.

---

## Q1. pypa/gh-action-pypi-publish — token auth

### Recommendation

- There is **no `token:` input**. The action's inputs (from `action.yml` on `release/v1`) are exactly: `user` (default `__token__`), `password`, `repository-url`, `packages-dir`, `verify-metadata`, `skip-existing`, `print-hash`, `verbose`, `attestations`. Nothing else.
- `password:` with `${{ secrets.X }}` **is still supported** and is the correct input for API-token publishing. Use it with the default `user` (`__token__`); do not set `user`.
- `permissions:` is **NOT required** for the token flow. `id-token: write` is only needed for Trusted Publishing (OIDC), which is unavailable here (private repo).
- `attestations` defaults to `true`, but the action auto-disables it when an explicit password is supplied and only emits a `::warning::`; it does **not** fail. No need to set `attestations: false` (harmless to set it anyway).
- The action does **not** checkout the repo. It is a Docker-based action; it only reads `packages-dir` from the workspace. So a `checkout` + a prior artifact download is needed to place `dist/` locally. It must run on Linux (fails fast otherwise).
- `skip-existing: true` gives registry-side idempotency (second safety layer behind the probe in Q3).

### Exact `with:` block

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_TOKEN }}
    # defaults that apply implicitly:
    #   user: __token__
    #   repository-url: https://upload.pypi.org/legacy/   (production PyPI)
    #   packages-dir: dist
    #   skip-existing: false
    #   verify-metadata: true
    #   print-hash: true
    #   verbose: true
```

With idempotency hardening (see Q3):

```yaml
- uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_TOKEN }}
    skip-existing: true
```

If the dists are not under `dist/` after download:

```yaml
    packages-dir: path/to/dist
```

### Evidence

- `action.yml` @ `release/v1` (fetched `https://raw.githubusercontent.com/pypa/gh-action-pypi-publish/release/v1/action.yml`): input list above; `user.default: __token__`; `password: "Password for your PyPI user or an access token"`; `repository-url` default `https://upload.pypi.org/legacy/`; `packages-dir` default `dist`; `attestations` default `'true'`; `runs.using: composite`; first step `if: runner.os != 'Linux'` -> `exit 1`.
- `twine-upload.sh` @ `release/v1`:
  - line 124: `elif [[ "${INPUT_USER}" == '__token__' ]]; then echo '::debug::Using a user-provided API token for authentication' ...` — confirms token path is `user=__token__` + `password=<token>`.
  - lines 102-108: if `attestations != false` and not trusted publishing -> emits `ATTESTATIONS_WITHOUT_TP_WARNING` ("attestations input ignored") and sets `INPUT_ATTESTATIONS="false"`. No `exit`.
  - lines 146-167: if `user == __token__` and password does not start with `pypi-`, only emits `::warning ... EMPTY TOKEN / POTENTIALLY INVALID TOKEN`. No `exit`.
  - line 190: `--skip-existing` passed to twine when `skip-existing != false`.
  - line 123: OIDC token exchange (`oidc-exchange.py`) only runs when `password` is empty.
- README @ `release/v1` lines 57-58 ("...configure this action's job with the `id-token: write` permission and **without** an explicit username or password") and lines 246-259 (token example: `password: ${{ secrets.TEST_PYPI_API_TOKEN }}` + `repository-url: https://test.pypi.org/legacy/`).
- pypa latest release is `v1.14.2` (2026-07-29); `release/v1` branch exists and resolves (GitHub API `refs/heads/release/v1` -> sha `dc37677b2e1c`, same sha as `release/v1.14`).

---

## Q2. Tag-vs-pyproject version validation

### Recommendation

Minimal, no third-party tools. `GITHUB_REF_NAME` for a tag push is the bare tag (`v0.2.1`). Strip the leading `v` with shell parameter expansion; parse pyproject with stdlib `tomllib` (Python >= 3.11, available on `actions/setup-python@v5+` runners). `tomllib` beats regex here because it is authoritative and the repo's `requires-python` floor (3.9) does not bind CI (CI selects its own Python).

### Exact snippet (verified working)

```yaml
- name: Validate tag matches pyproject version
  shell: bash
  run: |
    set -euo pipefail
    TAG_VERSION="${GITHUB_REF_NAME#v}"
    PYPROJECT_VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
    echo "tag=$TAG_VERSION pyproject=$PYPROJECT_VERSION"
    if [ "$TAG_VERSION" != "$PYPROJECT_VERSION" ]; then
      echo "::error::tag ($TAG_VERSION) != pyproject.toml ($PYPROJECT_VERSION)"
      exit 1
    fi
```

Regex-only fallback if `tomllib` is unavailable (works on any Python 3, no `tomllib` dependency):

```bash
    PYPROJECT_VERSION="$(python3 -c "import re,pathlib; print(re.search(r'^version\s*=\s*\"([^\"]+)\"', pathlib.Path('pyproject.toml').read_text(encoding='utf-8'), re.M).group(1))")"
```

Note: the tag-check job must `actions/checkout@v4` first (pyproject must be present). `TAG_VERSION="${GITHUB_REF_NAME#v}"` strips exactly one leading `v`; a tag like `v0.2.1` -> `0.2.1`. A tag without the `v` prefix (e.g. `0.2.1`) still yields `0.2.1` because `#v` is a no-op when absent.

### Evidence (run locally in repo root)

- `python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"` -> `0.2.1`, exit 0.
- `GITHUB_REF_NAME=v0.2.1 bash -c 'echo "${GITHUB_REF_NAME#v}"'` -> `0.2.1`.
- Snippet behavior with `TAG=v0.2.1`: `tag=0.2.1 pyproject=0.2.1`, exit 0.
- Snippet behavior with `TAG=v0.3.0`: `tag=0.3.0 pyproject=0.2.1`, `::error::version mismatch`, exit 1.

---

## Q3. Idempotency probes (exact commands + semantics)

### 3a. npm: does version already exist?

Command:

```bash
npm view "keystone-hook@${VERSION}" version
```

Semantics (verified against the real registry):

| Case | stdout | stderr | exit |
|---|---|---|---|
| version exists (`keystone-hook@0.1.0`) | `0.1.0` | (empty) | `0` |
| version missing (`keystone-hook@9.9.9`) | (empty) | `npm error code E404` / `npm error 404 No match found for version 9.9.9` / `'keystone-hook@9.9.9' is not in this registry.` | `1` |
| version missing (`keystone-hook@0.2.1`, a real not-yet-published version) | (empty) | same E404 shape | `1` |
| whole package missing | (empty) | `npm error code E404 ... Not Found - GET https://registry.npmjs.org/<pkg>` | `1` |

So: **exit 0 => skip publish; exit 1 => safe to publish.** (Both missing-version and missing-package give exit 1, which is exactly the "not published yet, proceed" case.)

Exact step:

```yaml
- name: Check if npm version already published
  id: npm_check
  shell: bash
  run: |
    set -euo pipefail
    VERSION="${GITHUB_REF_NAME#v}"
    if npm view "keystone-hook@${VERSION}" version >/dev/null 2>&1; then
      echo "exists=true" >> "$GITHUB_OUTPUT"
      echo "::notice::keystone-hook@${VERSION} already on npm - skipping"
    else
      echo "exists=false" >> "$GITHUB_OUTPUT"
    fi
```

Raw observed output for the missing-version probe:

```
$ npm view keystone-hook@9.9.9 version; echo "exit=$?"
npm error code E404
npm error 404 No match found for version 9.9.9
npm error 404
npm error 404  'keystone-hook@9.9.9' is not in this registry.
npm error 404
npm error 404 Note that you can also install from a
npm error 404 tarball, folder, http url, or git url.
exit=1
```

Also note: npm will **hard-fail** a duplicate publish. Docs (`npm help publish`): "The publish will fail if the package name and version combination already exists in the specified registry." So the probe (or an `if:`-guarded publish) is mandatory for R7.

### 3b. PyPI: does release version already exist?

Probe URL: `https://pypi.org/pypi/<pkg>/<version>/json`

Semantics (verified with real `requests`):

| Case | HTTP | Body |
|---|---|---|
| package exists + version exists (`requests/2.31.0`) | `200` | full JSON |
| package exists + version missing (`requests/99.99.99`) | `404` | `{"message": "Not Found"}` |
| package missing entirely (`this-pkg-does-not-exist-xyz/1.0.0`) | `404` | `{"message": "Not Found"}` |
| `keystone-hook` (unregistered) `/json` | `404` | `{"message": "Not Found"}` |

**Critical:** HTTP 404 is returned for BOTH "package exists but version missing" and "package does not exist". The endpoint cannot distinguish them. For this task that is fine: any non-200 means "not published -> publish"; first-ever publish sees 404 and proceeds.

Exact step using `curl -sf` (exit 0 on 2xx, exit 22 on >=400 — verified):

```yaml
- name: Check if PyPI version already published
  id: pypi_check
  shell: bash
  run: |
    set -euo pipefail
    VERSION="${GITHUB_REF_NAME#v}"
    if curl -sf "https://pypi.org/pypi/keystone-hook/${VERSION}/json" >/dev/null; then
      echo "exists=true" >> "$GITHUB_OUTPUT"
      echo "::notice::keystone-hook ${VERSION} already on PyPI - skipping"
    else
      echo "exists=false" >> "$GITHUB_OUTPUT"
    fi
```

If raw status code is preferred:

```bash
    CODE="$(curl -s -o /dev/null -w '%{http_code}' "https://pypi.org/pypi/keystone-hook/${VERSION}/json")"
    if [ "$CODE" = "200" ]; then ...skip...; else ...publish...; fi
```

Verified `curl -sf` exit codes: `requests/2.31.0` -> 0; `requests/99.99.99` -> 22; `keystone-hook/json` -> 22; `keystone-hook/0.2.1/json` -> 22.

Belt-and-braces: also pass `skip-existing: true` to the PyPI action, so even if the probe races, a duplicate upload is treated as success rather than failing (R7).

---

## Q4. Artifact consistency (build once, publish exact bytes)

### Recommendation

Build in the `test`/build job, upload, then in each publish job **download the artifact and publish the downloaded files**. Do not rebuild in the publish job (that would violate R8).

Key `download-artifact@v4` semantics (from its README):

- `name:` specified (single artifact) -> contents are extracted **directly into `path:`** (or `$GITHUB_WORKSPACE` if `path` omitted). **No subdirectory is created.** `merge-multiple` is irrelevant/not needed for a single named artifact.
- `name` omitted (all artifacts) -> each artifact gets its own subdirectory named after the artifact, unless `merge-multiple: true`.

`upload-artifact@v4` semantics relevant here: "If multiple paths are provided as input, the least common ancestor of all the search paths will be used as the root directory of the artifact." (Also, vertical truth: v4.4+ excludes hidden files by default; `dist/.gitignore` (content `*`, created by `uv build`) is hidden and therefore excluded — harmless, it is not publishable content.)

### Recommended shape

Upload two artifacts in the build job (unambiguous layout):

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: python-dist
    path: dist/              # directory, no wildcard -> layout deterministic

- uses: actions/upload-artifact@v4
  with:
    name: npm-tarball
    path: npm/*.tgz          # wildcard; see caveat below
```

Download + publish (PyPI job):

```yaml
- uses: actions/checkout@v4           # optional; only needed if you re-validate
- uses: actions/download-artifact@v4
  with:
    name: python-dist
    path: dist/                        # restores dist/*.whl and dist/*.tar.gz here
- uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_TOKEN }}
    skip-existing: true
    # packages-dir defaults to `dist`; matches the download path above
```

Download + publish (npm job):

```yaml
- uses: actions/download-artifact@v4
  with:
    name: npm-tarball
    path: npm-dist/                    # contents land directly here (single artifact)
- name: Show downloaded files
  run: ls -R npm-dist
- run: npm publish ./npm-dist/*.tgz --access public
  env:
    NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

Publishing a **tarball path** is supported by npm (verified locally with `npm publish ./keystone-hook-0.2.1.tgz --dry-run`), which is exactly what enforces "publish the tested bytes".

### Caveat / ambiguity to verify in-run

The existing `release.yml` uploads one artifact named `release-artifacts` with `path: | dist/` + `npm/*.tgz`. Per upload-artifact docs, with a wildcard the hierarchy is preserved only *after* the first wildcard, so `npm/*.tgz` is very likely flattened to the artifact root (the `npm/` prefix dropped), while the directory path `dist/` keeps its name. Combined with the multi-path LCA rule this layout is not fully specified by the docs. **Do not depend on `npm/` surviving.** Either (a) upload `python-dist` and `npm-tarball` as separate artifacts (recommended), or (b) after download add a `ls -R` / `find . -name '*.tgz'` step and publish the discovered path. If one combined artifact must be kept, upload `path: | dist/` `npm/` (the `npm/` **directory**, no glob) so the structure is deterministic, and set `packages-dir: dist` for the PyPI action.

### Evidence

- `download-artifact@v4` README: "If the `name` input parameter is not provided, all artifacts will be downloaded... a directory denoted by the artifacts name will be created for each individual artifact. This behavior can be changed with the `merge-multiple` input parameter." Single-artifact examples show `name: my-artifact` + `path: your/destination/dir` extracting directly.
- `download-artifact@v4` input doc: "When downloading a single artifact (by name or ID), it will always be extracted directly to the specified path."
- `upload-artifact@v4` README: LCA rule (line 187); wildcard flatten rule (lines 173-185); hidden-files-excluded default (v4.4+, line 67).
- Local `uv build` produced `dist/.gitignore` containing `*` (1 byte) — hidden, therefore not uploaded by v4.4+.

---

## Q5. Action version pins (verified 2026-10-08)

Latest releases (GitHub API `/releases/latest`):

| Action | Latest release | Latest major ref | `runs.using` on latest major | Oldest ref used by repo | `runs.using` there |
|---|---|---|---|---|---|
| actions/checkout | v7.0.1 | `v7` (exists) | `node24` | `v4` (exists) | `node20` |
| actions/setup-python | v7.0.0 | `v7` (exists) | `node24` | `v5` (exists) | (node20 line) |
| actions/setup-node | v7.1.0 | `v7` (exists) | `node24` | `v4` (exists) | `node20` |
| actions/upload-artifact | v7.0.2 | `v7` (exists) | `node24` | `v4` (exists) | `node20` |
| actions/download-artifact | v8.0.2 | `v8` (exists) | `node24` | `v4` (exists) | `node20` |
| pypa/gh-action-pypi-publish | v1.14.2 | `release/v1` branch (exists; sha `dc37677b2e1c`) | composite (not a node runtime) | same | n/a |

All refs in both columns were confirmed to resolve (HTTP 200 from `raw.githubusercontent.com/<repo>/<ref>/action.yml`). So the existing pins (`checkout@v4`, `setup-python@v5`, `setup-node@v4`, `upload-artifact@v4`, `download-artifact@v4`, `gh-action-pypi-publish@release/v1`) all still work today.

Note on cross-major compatibility: `upload-artifact@v4` and `download-artifact@v4` are compatible; `download-artifact@v8` can read v4-uploaded artifacts, but do not mix a newer download major with an older upload major without checking. Keep the two artifact actions on the same major (both `v4`, or both bumped together).

Recommendation: either keep the repo's current `v4`/`v5` pins (minimal diff, proven to resolve), or pin to the newest majors (`checkout@v7`, `setup-python@v7`, `setup-node@v7`, `upload-artifact@v7`, `download-artifact@v8`) to get `node24` and avoid the eventual `node20` retirement. If a `permissions:` block is added, it must retain `contents: read` for `checkout`.

---

## Gotchas

1. **Token flow needs NO `permissions:` block.** Do not add `id-token: write` (that is the Trusted Publishing flow, unavailable here). If you add a `permissions:` block for any reason, include `contents: read` or checkout breaks.
2. **No `token:` input exists on the PyPI action.** Use `password:`. Do not set `user:` (default `__token__` is correct). A token not starting with `pypi-` only warns, it does not fail — but it will fail at upload with auth error.
3. **PyPI token must be account-scoped for the FIRST publish.** `keystone-hook` does not exist on pypi.org (404), so a project-scoped token cannot be created yet; `packaging.python.org` instructs using "Entire account" scope for a first upload. After the first successful publish, replace it with a project-scoped token (PyPI help: "When using an API token from a CI provider, we recommend scoping the token down to the minimum necessary projects").
4. **First PyPI publish permanently claims the name.** Package names cannot be deleted, only yanked (PyPI help / npm analog: "Once a package is published with a given name and version, that specific name and version combination can never be used again"). Requires verified PyPI account email before any upload.
5. **Duplicate npm publish hard-fails** (`npm help publish`: "The publish will fail if the package name and version combination already exists"). The Q3 npm probe (exit 0 => skip) or an `if:`-guarded publish is required for R7.
6. **PyPI 404 is ambiguous** (missing version vs missing package are identical). Treat any non-200 as "publish". Use `skip-existing: true` as the registry-side safety net.
7. **`--access public` is a no-op-but-harmless for `keystone-hook`.** It is an UNSCOPED package, and unscoped packages are public by default (npm docs: "By default npm will publish to the public registry"); `npm access get status keystone-hook` -> `keystone-hook: public`. Verified locally: `npm publish <tgz> --dry-run` prints "with tag latest and default access" without the flag, and "...and public access" with it; both succeed. The flag is only mandatory for *scoped* packages ("Scoped packages are not public by default"). Keeping `--access public` is safe and future-proofs a scope move; dropping it also works today.
8. **`repository` field is already present** in `npm/package.json` (`git+https://github.com/duny31030/keystone.git`), so no fix needed. npm does not hard-require it for a plain publish (it is needed for `--provenance`, which requires OIDC and is out of scope).
9. **npm auth wiring:** `actions/setup-node@v4` with `registry-url: 'https://registry.npmjs.org'` writes `.npmrc` to `$RUNNER_TEMP` and exports `NPM_CONFIG_USERCONFIG`, so it is honored even when the publish step runs in a different cwd. Verified locally that `NPM_CONFIG_USERCONFIG=/path/.npmrc` is honored from a subdirectory. The `NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}` env must be set on the step that runs `npm publish`. Only `NPM_TOKEN` becomes `NODE_AUTH_TOKEN` via that env mapping — setup-node does not rename secrets.
10. **`uv build` vs `python -m build`:** identical filenames and layout here — both produced `keystone_hook-0.2.1-py3-none-any.whl` + `keystone_hook-0.2.1.tar.gz` (normalized name: underscore, not hyphen). Difference: `uv build` additionally writes `dist/.gitignore` containing `*` (hidden, excluded by upload-artifact v4.4+ anyway). Both use the setuptools backend declared in `pyproject.toml`; either is safe. `python -m build` is the more conventional CI choice and is what the existing workflow already used.
11. **README rendering / metadata:** `twine check dist/*` PASSED for both artifacts on this repo (verified with `uvx --from twine twine check`), so `readme = "README.md"` renders fine. A first-time publish will otherwise fail with PyPI's "description failed to render". Keep the pre-upload `verify-metadata` default (`true`) so this is caught before upload.
12. **PyPI action is Docker/Linux-only** and does not checkout. It reads `dist/` from the workspace, so the publish job must download the artifact (or checkout + copy dists) before invoking it. Do not invoke `pypi-publish` more than once per job (README: unsupported); use separate jobs for PyPI vs npm.
13. **Tag-trigger hygiene:** R1 holds via `on: push: tags: ['v*']`. `github.ref_name` is the bare tag on a tag push; use `"${GITHUB_REF_NAME#v}"`. A non-`v` tag like `1.2.3` is not matched by the `v*` filter, so the `#v` strip cannot misfire in practice.
14. **Artifact layout for `npm/*.tgz` is not fully deterministic** under the multi-path LCA + wildcard rules (see Q4 caveat). Prefer separate `python-dist` / `npm-tarball` artifacts and an `ls -R` sanity step before publishing.
15. **`_authToken` is "protected"** — `npm config get //registry.npmjs.org/:_authToken` errors with "option is protected, and can not be retrieved in this way". Do not try to read it back for debugging; use `npm config list` (shows `(protected)`) or `npm whoami`.
16. **Order of publish jobs vs duplicate-name race:** if npm succeeds and PyPI fails, re-running the same tag is safe — the npm probe skips and PyPI proceeds. Make both publish jobs independently idempotent (probe first, `skip-existing: true` for PyPI).