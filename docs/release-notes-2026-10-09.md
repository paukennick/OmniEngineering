# Release notes, 2026-10-09: the Arbiter loop

What changed in OmniEngineering and in Arbiter on this date, what it means for
an adopter, and the steps to take. The mechanics are explained in
[`arbiter-integration.md`](arbiter-integration.md); the per-requirement detail
is in each repository's `CHANGELOG.md`.

## OmniEngineering (this repository)

| Requirement | Change |
|---|---|
| REQ-031 | `withdrawn` requirement status and `omni requirement archive`; doctor starts every server in `.mcp.json` for real |
| REQ-032 | the `command` gate validation type; `defect_category_pattern` configuration |
| REQ-033 | `omni adopt --with-arbiter` and `omni arbiter install` |
| REQ-034 | vendored workspaces recognised by the gate, doctor and CI |
| REQ-036 | `omni doctor` `Posture:` line and `--json`; duplicate requirement ids across registries are an error |
| REQ-037 | `omni requirement complete` refuses on a missing, stale or red Arbiter report; `--no-arbiter-check REASON` |
| REQ-038 | a committed Arbiter baseline at install; `omni arbiter baseline [--refresh]`; doctor baseline checks |
| REQ-039 | `omni graph impact`; the gate's impact line; the `graph_impact` MCP tool |
| REQ-040 | `omni test run [--impacted]`; the recommended `completion.tests` example rule |
| REQ-041 | the adopt loop proven in CI and in a test; SARIF upload; Arbiter's Python floor read from its `pyproject.toml` |
| REQ-042 | Arbiter version recorded in `.ai/omni-version.json`; `omni arbiter update`; drift warnings |
| REQ-043 | Arbiter findings as graph nodes; `omni graph findings`; the viewer's Findings tab, colour modes, filters, source row and one-click traces; the `graph_findings` MCP tool |
| REQ-044 | requirement id aliases and `omni requirement renumber --prefix` |

Defects found and fixed on the way: FAIL-010 (CI YAML), FAIL-011 (schema enum),
FAIL-012 (committed Arbiter reports scanned as source), FAIL-013 (suite timeout
did not kill the process tree on Windows), FAIL-014 (a path assertion on
Windows).

## Arbiter

| Requirement | Change |
|---|---|
| ARB-031 to ARB-037 | re-synced to this workspace, self-gating in `pr-check`, probe precision, analyzers in CI, `review --ledger`, the Claude skill, the commercial control packs |
| ARB-038 | the `governance` probe (reads the failure ledger) and `req:` tags; reports group findings by requirement |
| ARB-039 | `--format annotations`, `--github` (annotations plus the PR comment in the job summary), SARIF upload in `pr-check`, `failing_ids` on the gate |
| ARB-040 | runs on Python 3.10 (`tomllib` with a `tomli` fallback) |
| ARB-041 | the opt-in per-file result cache with integrity invariant CI-13 and `--verify-cache` |
| ARB-042 | `history.jsonl` per run and `arbiter dashboard` |
| ARB-043 | the workspace tooling synced from this repository; requirements renumbered from `REQ-###` to `ARB-###` with aliases |

## For an adopter

1. `./omni update --source <OmniEngineering checkout>` brings the new tooling.
2. `./omni arbiter install --source <Arbiter checkout or URL>` (or `omni arbiter
   update` if already installed) rewrites the gate rule to pass the baseline and
   the three output formats, records the version, and cuts the baseline.
3. Commit `.arbiter/baseline.json`.
4. `./omni gate`, then `./omni graph build`; `./omni doctor` now ends with the
   posture line.
5. In CI, add the SARIF upload step and `permissions: security-events: write`
   (see `.github/workflows/ci.yml`).
