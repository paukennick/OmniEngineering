---
name: arbiter
description: Use when working in or on the Arbiter repository evaluator - scanning a repository or system, reading a report whose grade was withheld, gating a change, adjudicating findings, or deciding between the arbiter MCP tools and the CLI. Also use before claiming a change to Arbiter is complete, because pr-check runs Arbiter on itself.
---

# Arbiter

Arbiter scans a repository, or a system of several, and refuses to grade what
it did not inspect. Read `README.md` "Principles" before changing anything in
`src/arbiter/`: coverage is reported never assumed, deterministic and inferred
findings never blend, the tool never executes the target.

## Which surface to use

| Need | Use |
| --- | --- |
| Scan or gate from an assistant session | the `arbiter_scan` / `arbiter_gate` MCP tools from `.mcp.json`: structured JSON back, no shell prompt |
| Draw a review queue | `arbiter_review_queue` (MCP) or `arbiter review` (CLI) |
| Record a verdict | the CLI only: `arbiter review --apply FILE --reviewer NAME`; no MCP tool records a verdict, by design |
| Anything with `--changed`, `--baseline`, `--system`, formats | the CLI: `arbiter scan`, `arbiter gate`, `arbiter diff`, `arbiter ab` |
| One finding in full | `arbiter explain <finding-id>` |
| A scan that must not remember the last one (CI, a measurement) | `--no-cache`; the file-local probes otherwise reuse `.arbiter/cache.json`, and `--verify-cache` audits it |
| What was and was not checked for a framework | `arbiter controls --framework <id>` |
| The trend across runs | `arbiter dashboard`, from `<out>/history.jsonl`, which every scan and gate appends to (`--no-history` skips it) |

## Reading a report

- `scorecard.withheld: true` means coverage fell below the threshold in
  `arbiter.yaml` (`score.coverage_threshold`, default 0.6). The grade is not
  low; it is absent. Say so. The `NOT ASSESSED` block names each probe that
  did not run and why: a missing binary, a profile that forbids network, or
  `not applicable` (nothing to check, such as seams on a single repository).
  Only the first two lower coverage.
- Every finding carries `provenance` (`deterministic` or `inferred`),
  `confidence`, and `remediation_source`. Never present an inferred finding
  as a deterministic one, and never present a bare reference link as a fix.
- A suppressed finding is still in the report, marked and attributed. That is
  the feature; do not delete it from the corpus.

## Gating a change to Arbiter itself

`.github/workflows/pr-check.yml` runs the suite, `tools/integrity.py`,
`tools/mutate_tests.py`, `python omni doctor`, `python omni gate`, and on
Linux `arbiter gate .` with the external analyzers installed. Before saying a
change is complete:

```bash
python -m pytest tests/ -q
python tools/mutate_tests.py
arbiter gate .            # the repository's own policy, from arbiter.yaml
python omni gate          # CHANGELOG.md and the requirement registry co-change
```

A planted defect belongs in `fixtures/` with an entry in
`.arbiter-expected.yaml`; a fixed defect belongs in the failure ledger
(`python omni failure add`), which `arbiter review --apply --ledger` can draft
from a true-positive verdict.

## Adjudicating

Verdicts are permanent and attributed. Use `arbiter review` to draw a queue,
mark the file, then `arbiter review --apply FILE --reviewer NAME`. A rule needs
enough adjudications before calibration trusts it; `arbiter learn` shows how
many it has. Do not adjudicate from a non-interactive session: the CLI refuses.
