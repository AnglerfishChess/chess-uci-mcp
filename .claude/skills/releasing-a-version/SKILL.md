---
name: releasing-a-version
description: Cut a release of chess-uci-mcp to PyPI and the MCP registry. Use when the user asks to release, publish, ship or tag a new version, or names a version and asks to get it out. Covers preconditions, the version bump across every file that repeats it, tagging, the GitHub release that triggers publishing, and post-release verification of PyPI, the MCP registry and Context7. Never invoke this on your own initiative -- a release is the user's decision to make.
argument-hint: [version]
disable-model-invocation: true
---

# Release chess-uci-mcp

Release `$1` — a bare semver such as `0.2.0`, with no leading `v`, since the tag adds it.

The pipeline is: GitHub release → `.github/workflows/publish.yml` → PyPI via trusted publisher (OIDC, no tokens
anywhere) → the MCP registry, which the same workflow republishes. Everything below is what happens around that
trigger. Work through the steps in order and stop at the first failure instead of improvising past it: most of
these steps are cheap to retry, and the two that are not — the tag and the release — come last for that reason.

## 1. Check the preconditions

- `git status -sb` — clean tree, on `main`, in sync with `origin/main`. Unpushed work either joins the release
  deliberately or waits; it must not ride along unnoticed.
- `$1` is unreleased: absent from `git tag`, and from `https://pypi.org/pypi/chess-uci-mcp/json`.
- **Confirm a UCI engine is on PATH before trusting the tests**: `command -v stockfish`. This matters more here
  than in most projects, because `tests/test_engines.py` skips itself at module level when no engine is found —
  so `uv run pytest` passes having exercised nothing at all. A green run without that check is not evidence.
- Then run them: `uv run pytest`.
- `gh run list --branch main --limit 1` — CI green on HEAD. That job installs Stockfish itself, so it is the run
  that genuinely drove an engine, on a platform you do not develop on.

## 2. Bump the version

`pyproject.toml` holds the version; every other occurrence is a copy. Set `version = "$1"` there, let the lockfile
follow, then propagate it to `chess_uci_mcp/__init__.py` and to both version fields in `server.json`:

```bash
uv sync
uv run python ${CLAUDE_SKILL_DIR}/scripts/sync_version.py
```

Commit it all as one change. The version in the code, in `server.json` and on the tag has to be a single string:
a wheel reporting a version its tag never had is a support puzzle, and a `server.json` naming a package version
PyPI does not serve is rejected by the registry outright.

## 3. Tag, and release

Push the bump, then **wait for its own CI run to finish before tagging**. The green you checked in step 1 belonged
to the commit *before* the bump; pushing starts a fresh run, and the commit actually being released is the one
nobody has verified yet.

```bash
git push origin main
until [ "$(gh run list --branch main --limit 1 --json status --jq '.[0].status')" = completed ]; do sleep 20; done
gh run list --branch main --limit 1 --json headSha,conclusion --jq '.[0] | "\(.headSha[0:7]) \(.conclusion)"'
```

Expect the bump commit's short SHA and `success`. Anything else: stop. The tag is the point of no return.

```bash
git tag v$1 && git push origin v$1
gh release create v$1 --title "v$1 — <short summary>" --notes "<what changed and why it matters>"
```

Write release notes as what changed and what it displaces, not a list of touched files. Creating the release is
the publish trigger; after this command the release is happening.

## 4. Watch it land

```bash
gh run watch $(gh run list --workflow publish.yml --limit 1 --json databaseId -q '.[0].databaseId') --exit-status
```

Then confirm PyPI serves it — `curl -s https://pypi.org/pypi/chess-uci-mcp/json` should report `info.version` as
`$1` — and cold-run the path a real user takes:

```bash
uvx --refresh chess-uci-mcp@$1 --help
```

`--help` returns before the engine-path argument is validated, so this works without an engine installed.

## 5. Confirm the indexes caught up

**The MCP registry republishes itself.** `publish.yml` waits for PyPI to serve `$1`, authenticates with
`github-oidc` using the id-token permission it already holds for PyPI, and publishes the `server.json` that step 2
updated. Nothing to run and nothing to log into — just confirm it landed:

```bash
curl -sS "https://registry.modelcontextprotocol.io/v0/servers?search=chess-uci-mcp&limit=3"
```

Expect `$1`, `status: active`, `isLatest: true`. If that workflow step failed with a 400 naming
`ownership validation failed`, the description PyPI serves for `$1` is missing the
`mcp-name: io.github.AnglerfishChess/chess-uci-mcp` marker that sits near the top of `README.md`. The registry
reads that marker from the *published artifact*, so having it in git is not enough and retrying will not help —
it takes another release.

**Refresh Context7**, which otherwise re-crawls a project this size about every 45 days and would keep describing
the previous release for weeks:

```bash
curl -sS -X POST https://context7.com/api/v1/refresh \
  -H "Authorization: Bearer $CONTEXT7_API_KEY" -H "Content-Type: application/json" \
  -d '{"libraryName": "/anglerfishchess/chess-uci-mcp"}'
```

The key is `libraryName` and the body must be JSON — a form-encoded post, or the `libraryId` spelling the API
guide implies, returns a bare 500 that explains nothing. Refreshes are capped at one per 10 days, so
`{"error":"too-early", ...}` means the index is already recent enough: report it and move on rather than retrying.
Skip this step entirely when `CONTEXT7_API_KEY` is unset; the key comes from context7.com/dashboard and a release
does not depend on it.

## 6. Leave the docs true

Three files describe the release to people who cannot see this repository, and each goes stale silently:

- **README.md** — its *Available MCP Commands* list is what PyPI and the registry display. It must describe the
  tools the released version actually serves, never ones still in progress.
- **context7.json** — the `rules` are printed verbatim ahead of every answer Context7 gives about this project, so
  a stale rule is wrong in public and invisible from here.
- **server.json** — `packageArguments` is how every MCP client installing from the registry learns to invoke the
  server. If the command-line interface changed, this changed with it.
