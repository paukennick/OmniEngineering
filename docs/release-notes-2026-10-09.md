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
| REQ-035 | Arbiter vendored under `arbiter/` as a git subtree with its full history; `arbiter.yaml` at the root with `arbiter/**` suppressed; the `arbiter` MCP server beside `omni`; `arbiter/` kept out of the root code graph; `NOTICE` and `LICENSES/README.md` state that the Apache-2.0 grant stops at `arbiter/` |
| REQ-036 | `omni doctor` `Posture:` line and `--json`; duplicate requirement ids across registries are an error |
| REQ-037 | `omni requirement complete` refuses on a missing, stale or red Arbiter report; `--no-arbiter-check REASON` |
| REQ-038 | a committed Arbiter baseline at install; `omni arbiter baseline [--refresh]`; doctor baseline checks |
| REQ-039 | `omni graph impact`; the gate's impact line; the `graph_impact` MCP tool |
| REQ-040 | `omni test run [--impacted]`; the recommended `completion.tests` example rule |
| REQ-041 | the adopt loop proven in CI and in a test; SARIF upload; Arbiter's Python floor read from its `pyproject.toml` |
| REQ-042 | Arbiter version recorded in `.ai/omni-version.json`; `omni arbiter update`; drift warnings |
| REQ-043 | Arbiter findings as graph nodes; `omni graph findings`; the viewer's Findings tab, colour modes, filters, source row and one-click traces; the `graph_findings` MCP tool |
| REQ-044 | requirement id aliases and `omni requirement renumber --prefix` |
| REQ-045 | the integration handbook `docs/arbiter-integration.md` and these release notes, linked from the README and the context brief |

Defects found and fixed on the way: FAIL-010 (CI YAML), FAIL-011 (schema enum),
FAIL-012 (committed Arbiter reports scanned as source), FAIL-013 (suite timeout
did not kill the process tree on Windows), FAIL-014 (a path assertion on
Windows), FAIL-015 (`omni adopt --include-cli` into an empty target exited 1).

## Arbiter

| Requirement | Change |
|---|---|
| ARB-031 to ARB-037 | re-synced to this workspace, self-gating in `pr-check`, probe precision, analyzers in CI, `review --ledger`, the Claude skill, the commercial control packs |
| ARB-038 | the `governance` probe (reads the failure ledger) and `req:` tags; reports group findings by requirement |
| ARB-039 | `--format annotations`, `--github` (annotations plus the PR comment in the job summary), SARIF upload in `pr-check`, `failing_ids` on the gate |
| ARB-040 | runs on Python 3.10 (`tomllib` with a `tomli` fallback) |
| ARB-041 | the opt-in per-file result cache with integrity invariant CI-13 and `--verify-cache` |
| ARB-042 | `history.jsonl` per run and `arbiter dashboard` |
| ARB-043 | the workspace tooling synced from this repository (posture line, baseline, impact, findings, `omni test run`, the version record, the gate rule's full run text) |
| ARB-044 | requirements renumbered from `REQ-###` to `ARB-###` with `id_aliases`, so the two registries never collide in one tree |

## What the repository now contains

Everything the two lists above put into the tree, so a reviewer can see the
whole of it in one place. Paths are relative to the repository root; the
`arbiter/` subtree is listed once and its contents are described by its own
`README.md`, `CHANGELOG.md` and `docs/`.

| Path | What it is | Landed by |
|---|---|---|
| `arbiter/` | the Arbiter repository evaluator, vendored as a git subtree with its full history: its source, tests, fixtures, CI, docs, its own `.ai/` workspace (registry on the `ARB` prefix), `LICENSE` (all rights reserved) and `NOTICE.md`. Not covered by the root Apache-2.0 grant. | REQ-035 |
| `arbiter.yaml` | this repository's Arbiter policy: profile offline, fail on critical, fail on new high; `arbiter/**` suppressed because the subtree gates itself | REQ-035 |
| `.arbiter/baseline.json` | the committed baseline: every finding id present when it was cut, the commit and the sha256 of `arbiter.yaml`; "new" means new since it | REQ-038 |
| `.mcp.json` | the `arbiter` (`arbiter mcp`) and `omni` (`omni mcp serve`) servers; `omni doctor` starts both for real | REQ-031, REQ-035 |
| `.ai/rules/completion-workflow.json` | the required rule `completion.arbiter_gate` (type `command`, runs `arbiter gate` on the change set with the baseline) and the recommended example rule `completion.tests` | REQ-032, REQ-033, REQ-038, REQ-040 |
| `.github/workflows/ci.yml` | the matrix job installs a vendored Arbiter and uploads the gate's SARIF; new jobs `vendored-arbiter` (the subtree's suite, claim-integrity and mutation checks) and `adopt-loop` (adopt, plant a defect, gate fails, fix, gate passes) | REQ-034, REQ-041 |
| `.gitignore` | `arbiter-out/` (reports) and `.arbiter/cache.json` (the per-file cache), so neither is ever scanned as source or committed | REQ-033, REQ-038 |
| `NOTICE`, `LICENSES/README.md` | the statement that the Apache-2.0 licence of this repository does not extend to `arbiter/` | REQ-035 |
| `docs/arbiter-integration.md`, `docs/release-notes-2026-10-09.md` | the handbook and these notes; `docs/` is an allowed root path | REQ-045 |
| `make_ai.py`, `omni_graph.py`, `omni_mcp.py`, `.ai/graph-viewer/viewer.html` | the CLI, graph, MCP and viewer code behind every command named above | REQ-031 to REQ-044 |
| `tests/` | thirteen test files, new or extended (adopt loop, Arbiter install and update, doctor MCP probe and posture, gate rules, graph findings and impact, requirement aliases, archive and completion, `omni test run`, the viewer) | REQ-031 to REQ-044 |
| `.ai/requirements/requirements.json`, `.ai/failures/failure-ledger.json`, `CHANGELOG.md`, `.ai/project-map.md`, `.ai/context-brief.md` | the fifteen requirements (all completed), the six defects (FAIL-010 to FAIL-015, all fixed), one changelog entry per requirement, the project map and the brief's pointer to the handbook | REQ-031 to REQ-045 |

The commands that did not exist before this date: `omni adopt
--with-arbiter`, `omni arbiter install | baseline | update`, `omni doctor
--json`, `omni requirement archive | renumber`, `omni requirement complete
--no-arbiter-check`, `omni graph impact`, `omni graph findings`, `omni test
run`; inside the subtree, `arbiter gate --format annotations | --github`,
`arbiter scan --no-cache | --verify-cache`, `arbiter dashboard`.

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
