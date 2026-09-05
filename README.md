# Rerun Transient Failures

A GitHub Action that re-runs a workflow run's **failed jobs** — but only once,
and only when the failure logs match a known transient / infrastructure
signature (DNS blips, TLS handshake timeouts, package-mirror 5xx, `apt` lock
races, runner shutdowns, disk-full). A real failure — a failed test, a compile
error, a lint violation — is left alone.

Unlike a blanket "retry failed workflow" action, this one reads the logs and
decides. No config needed for the common cases; add your own signatures when
you have infra quirks of your own.

## Usage

Trigger it from `workflow_run` on the workflows you want covered:

```yaml
# .github/workflows/rerun-transient-failures.yml
name: rerun-transient-failures
on:
  workflow_run:
    workflows: [CI, lint, tests]      # names of the workflows to watch
    types: [completed]

permissions: {}

jobs:
  rerun:
    if: github.event.workflow_run.conclusion == 'failure'
    runs-on: ubuntu-latest
    permissions:
      actions: write                  # required: to call `gh run rerun`
    steps:
      - uses: hugoh/rerun-transient-failures@v1
        with:
          run-id: ${{ github.event.workflow_run.id }}
```

`workflow_run` workflows run from the **default branch**, so this covers
push-to-default and same-repo pull requests. Fork PRs are not covered (their
`GITHUB_TOKEN` is read-only by design).

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `run-id` | yes | — | The workflow run id to inspect and possibly re-run. |
| `token` | no | `${{ github.token }}` | A token with `actions: write` on the repo. |
| `patterns-file` | no | `""` | Path (in the checked-out repo) to a file of extra transient regexes. |
| `patterns-mode` | no | `append` | `append` adds to the built-in list; `replace` uses only `patterns-file`. |

To use `patterns-file` you must check the repo out first:

```yaml
    steps:
      - uses: actions/checkout@v4
      - uses: hugoh/rerun-transient-failures@v1
        with:
          run-id: ${{ github.event.workflow_run.id }}
          patterns-file: .github/transient-patterns.txt
```

## Outputs

| Output | Description |
|---|---|
| `reran` | `true` if the failed jobs were re-run, else `false`. |
| `matched` | The transient signature that triggered the rerun, if any. |

## What counts as transient

The built-in list is [`default-patterns.txt`](default-patterns.txt) — curated
to be high-confidence, since a false positive silently burns a rerun. It
covers `curl` exit codes, DNS / connection resets, TLS handshake failures,
HTTP 429 / 5xx from dependencies, package and toolchain download failures,
git transport drops, GitHub Actions infra messages, and runner resource
exhaustion.

A `patterns-file` entry is one Python regex per line; `#` comments and blank
lines are ignored; matching is case-insensitive and searched anywhere in the
concatenated failed-job logs.

## Behaviour

- **Runs once.** If the run is already on attempt ≥ 2, it no-ops.
- **Needs failed-job logs.** If none are available, it no-ops.
- **Conservative.** No signature match → the run is left failed.

## License

MIT — see [LICENSE](LICENSE).
