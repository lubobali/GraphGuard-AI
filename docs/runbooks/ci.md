# Runbook — GraphGuard's CI (S5b.2)

| | |
|---|---|
| Runner | `graphguard-runner.service`, config `runner/config.yml` (gitignored) |
| Job image | `graphguard/ci:1` — `docker/ci.Dockerfile` (pinned Node 22 LTS base + git, curl) |
| Job sandbox | a fresh network per job, `--cap-drop=ALL`, `no-new-privileges`, 2 GB / 2 CPU / 512 pids |
| First step | `scripts/ci/isolation-probe.sh` — fails the build if isolation regresses |
| Checks | lint, format, guards, secret scan (whole history), dependency check (locks + OSV), tests |

## Everyday

```
just ci-sandbox        # EVERY CI step on the committed HEAD, in the real job sandbox
just ci-probe          # the isolation probe, locally, the way a CI job runs it
just secrets-staged    # what the pre-commit hook runs
just secrets-history   # what CI runs: every commit, every branch
just deps-check        # locks current + no known vulnerability (OSV)
```

**Before pushing a CI change, run `just ci-sandbox`.** A copy of the repo checked on the
host runs with root's powers and hides failures; the first S5b.2 push went red because
`tar` needed a capability the job no longer has, which only the sandbox shows.

## When a check fails

- **Isolation probe:** the job could reach another container, had capabilities, or
  could not reach PyPI. Check `runner/config.yml` (`network: ""`, the `options`), then
  `systemctl restart graphguard-runner`. Never "fix" it by loosening the probe.
- **Secret scan:** if it is a real secret, **rotate it first**, then remove it. If it is
  a deliberate test value, add `# betterleaks:allow -- <why>` on that line; for an old
  commit, add the finding to `.betterleaks-baseline.json`. Never ignore a whole path.
- **deps-check, lock not current:** run `uv lock` and commit. **A new advisory:**
  upgrade the package (`uv lock --upgrade-package <name>`); if no fix exists or it does
  not apply to us, record it in `osv-scanner.toml` with the reason and a review date.
- **`exclude-newer` blocks an urgent security release:** add the package to
  `exclude-newer-package` in `pyproject.toml` with the reason.

## Changing the job image

Edit `docker/ci.Dockerfile` (keep the base pinned by digest), `just ci-image` with a new
tag, update the label in `runner/config.yml` and `tests/test_ci_supply_chain.py`,
restart the runner, and check the next run's probe step.

## Updating a pinned action

Resolve the new tag's commit **from data.forgejo.org** (where this instance fetches
actions): `git ls-remote https://data.forgejo.org/actions/checkout 'refs/tags/v4*'`. Read
the diff, then pin the SHA with the version in a comment.
