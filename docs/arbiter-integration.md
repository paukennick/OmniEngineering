# Arbiter and OmniEngineering: how the two run as one loop

This is the handbook for the integration. It says what each tool owns, how
they are wired together in a repository, what happens on every edit, commit
and pull request, how to trace a finding from the interactive graph to its
source and to the requirement it belongs to, how the pieces stay level as
both projects move, and which switches turn each piece off. It describes
the behaviour as shipped; the dated detail per requirement is in
[`release-notes-2026-10-09.md`](release-notes-2026-10-09.md) and in
`CHANGELOG.md`.

## 1. Division of labour

| | OmniEngineering (`omni`) | Arbiter (`arbiter`) |
|---|---|---|
| What it is | The governance workspace: the `.ai/` tree, requirements registry, failure ledger, rulepacks, code graph, doctor and gate, MCP server, hooks. | The repository evaluator: probes and external analyzers, a scorecard that refuses to grade what it did not inspect, a gate, a claim ledger, adjudication and calibration, control packs, MCP server. |
| The question it answers | Is this change governed? Does it cite a requirement, update the changelog, record its defects, keep the registry and ledger consistent, pass the rules the team wrote? | Is this code sound? What is new, how severe, where, and how much of the system was actually looked at? |
| Where its state lives | `.ai/`, `CHANGELOG.md`, `.ai/project-graph.json`, `.mcp.json` | `arbiter.yaml`, `.arbiter/` (baseline, knowledge, cache), `arbiter-out/` (reports, history) |
| Its gate | `omni gate`: every required rule in the rulepacks, run on the change set since the merge base. | `arbiter gate`: findings at or above the configured severity, and findings that are new since the baseline. |

Neither replaces the other. `omni gate` runs `arbiter gate` as one of its
rules, Arbiter reads the workspace's ledger and requirement ids as one of
its probes, and the graph shows both sides' records as nodes you can click
through.

## 2. Three ways they meet

1. **Installed alongside an adopted workspace** (the normal case for a
   product repository). `omni adopt --with-arbiter [SOURCE]` installs Arbiter
   while adopting, and `omni arbiter install --source SOURCE` adds it to a
   repository adopted earlier. The source is a local checkout (editable
   install) or the GitHub URL. Arbiter is proprietary and not on PyPI.
2. **Vendored as a subtree** (this repository's `main`, since 2026-10-09). The whole
   Arbiter checkout sits under `arbiter/` with its own `.ai/` workspace. The
   root workspace recognises it as a vendored workspace: the requirement-id
   gate accepts ids from its registry, doctor checks its CLI copies are level
   with the root's, and CI runs its own suite, claim-integrity and mutation
   checks. The root still gates the whole tree with its own `arbiter.yaml`,
   which suppresses findings inside `arbiter/` because the subtree gates
   itself.
3. **Arbiter governing itself.** The Arbiter repository carries the
   OmniEngineering workspace at its root and wires its own gate into
   `omni gate`, so every Arbiter change is both governed and self-scanned.
   Its requirements use the `ARB-###` prefix so they never collide with this
   repository's `REQ-###` when the two registries sit in one tree.

## 3. What the wiring writes

`omni arbiter install` (and `adopt --with-arbiter`) writes five things, each
skipped when present and never overwritten:

| File | What it holds | Why |
|---|---|---|
| `.mcp.json` | an `arbiter` server entry (`arbiter mcp`) beside `omni` | assistants get `arbiter_scan`, `arbiter_gate`, `arbiter_review_queue` as tools; `omni doctor` starts the server for real |
| `.ai/rules/completion-workflow.json` | the required rule `completion.arbiter_gate`, type `command`, run text `arbiter gate . --changed {base} --profile offline --baseline .arbiter/baseline.json --out arbiter-out/omni-gate --format json,sarif,pr-comment` | `omni gate` runs Arbiter on the change set and fails when Arbiter fails |
| `arbiter.yaml` | a starter policy: profile offline, fail on critical, fail on new high | the gate has a policy on day one |
| `.gitignore` | `arbiter-out/` and `.arbiter/cache.json` | reports and the cache are never scanned as source (FAIL-012) and never committed |
| `.arbiter/baseline.json` | the ids of every finding present at install, from a full offline scan, plus the commit and the hash of `arbiter.yaml` | "new" means new since adoption, so a legacy repository can adopt without failing on its existing debt. Commit it. |

It also records `{source, version}` under `arbiter` in
`.ai/omni-version.json` so doctor can tell when the installed Arbiter drifts.

## 4. The loop, edit by edit

```
edit code
   │
   ▼
omni gate  (pre-commit hook, Claude Stop hook, CI)
   ├─ completion.changelog_gate, completion.requirements_registry, controlled.requirement_id, data.privacy ...
   ├─ impact: 2 requirement(s), 1 failure(s), 1 suite(s) ...        ← graph impact of the change set
   └─ completion.arbiter_gate ──► arbiter gate . --changed <base> --baseline .arbiter/baseline.json
                                    ├─ probes + analyzers on the changed files
                                    ├─ governance probe: reads .ai/failures/failure-ledger.json
                                    │     open FAIL whose affected file changed without its regression test → finding
                                    │     fixed FAIL whose regression test vanished → finding
                                    ├─ findings tagged req:<ID> from the commits since the base
                                    └─ arbiter-out/omni-gate/{report.json, report.sarif, pr-comment.md, history.jsonl}
   ▼
omni doctor ──► Posture: arbiter score 96.7 (coverage 97%, full scan 2026-10-09 09:06) · gate passed (new high+ 0, fresh) · failures open 0 · requirements open 2
   ▼
omni requirement complete REQ-0xx ──► refuses unless the newest Arbiter report was scanned at HEAD, after the last edit, and passed
   ▼
arbiter review arbiter-out/omni-gate/report.json --apply marked.md --ledger .ai/failures/failure-ledger.json
   └─ every finding marked real becomes an open FAIL-### entry (symptom, how_detected = the finding id, affected path)
   ▼
omni failure update FAIL-### --root-cause ... --fix ... --tests ...   (the ledger demands the reasoning)
   ▼
omni graph build ──► finding nodes (flags → file/symbol, cites → requirement, recorded_as → failure)
omni graph view  ──► click the finding: breadcrumb root › dir › file › class › method › finding, chain lit both ways
```

Each arrow is enforced, not advisory:

- **The gate runs Arbiter.** The rule is `required`, so `omni gate` exits 1
  when `arbiter gate` exits 1, and the hook blocks the commit. The run text
  scopes Arbiter to the change set (`--changed {base}`) so a pre-commit run
  reads only what changed; probes that need the whole repository are
  reported as skipped for that run, never as clean.
- **Arbiter reads the ledger.** The `governance` probe is applicable only when
  `.ai/failures/failure-ledger.json` exists (otherwise it is recorded as not
  applicable, which does not count against coverage). Its two rules are
  medium severity on purpose: they inform the review and never trip
  `new: high` on their own; raise them in `arbiter.yaml` under
  `probes.severity_overrides` once the team wants them blocking.
- **Findings carry the requirement.** Arbiter reads the commit messages since
  the base, collects the `REQ-###` (or `ARB-###`) ids they cite, and tags every
  finding inside the change with `req:<ID>`. The PR comment and `REPORT.md`
  group findings by requirement, so a review reads "REQ-042 introduced two
  highs" rather than a flat list.
- **Doctor shows the posture.** The `Posture:` line comes after the
  `Result:` line, which is unchanged for anything that parses it. It reads two
  reports, not one, because the gate's `--changed` run is a partial scan whose
  grade is withheld by design: the first part is the newest *full* report
  (`scan_scope.mode: full`, from `omni arbiter baseline` or a plain `arbiter
  scan`) with its grade, coverage and when it ran; the second is the newest
  *partial* report (the gate's own) with its verdict, the new high+ count and
  whether it still describes HEAD, judged against the rule's `when_changed`
  scope. Both are looked for under the `--out` directory's parent and one level
  below it (`arbiter-out/baseline/`, `arbiter-out/omni-gate/`). When one is
  missing the line names the command that makes it: `arbiter no full scan (run
  ./omni arbiter baseline)`, `gate no report (run ./omni gate)`; a gate report
  that no longer describes HEAD reads `gate stale: <reason>`. `omni doctor
  --json` (schema_version 2) is the machine contract: `posture.arbiter` carries
  `wired`, `full` and `gate`, each block with `present`, `path`, `started_at`,
  `fresh`, `reason`, `grade`, `score`, `coverage`, `new_high_or_above`,
  `existing_high_or_above`, `gate_passed` and `gate_reasons`. The schema 1 keys
  at the top of `posture.arbiter` (`present`, `fresh`, `grade`, `coverage`,
  `gate_passed`, ...) stay for one release, filled from the `gate` block; move
  readers to `posture.arbiter.gate` before they go.
- **Completion checks the gate.** `omni requirement complete` refuses with the
  exact command to run (`./omni gate`) when the report is missing, stale or
  red. `--no-arbiter-check REASON` records the reason in the requirement's
  note, so an override is auditable.
- **Adjudication feeds the ledger.** `arbiter review --apply --ledger` drafts
  one `open` ledger entry per true positive, deduplicated on the finding id in
  `how_detected`; `omni failure check` then insists on root cause, fix and a
  regression test (or an honest reason there is none).

## 5. Findings in the graph, and how to trace one

`omni graph build` reads the newest `report.json` under the gate rule's
`--out` directory (override with `findings_report` in `.ai/graph-config.json`;
`null` disables) and adds one `finding` node per unsuppressed finding. Only
the id, location, rule, dimension, severity, status, tags and title are
copied; the evidence snippet never reaches the graph or the viewer.

Edges:

| Edge | From → to | Meaning |
|---|---|---|
| `flags` | finding → file, and the function/class whose span covers the line | where it sits in the code |
| `cites` | finding → requirement | the requirement being worked when it appeared (from the `req:` tag) |
| `recorded_as` | finding → failure | the ledger entry it became after adjudication |
| `contains` | directory → file / subdirectory | the tree from the root down to the file |

A finding is traceable along four axes:

| Axis | CLI | Viewer |
|---|---|---|
| by id | `omni graph why f:<id>`, `omni graph show f:<id>` | search `f:<id>`, click it |
| by category and severity | `omni graph findings --dimension security --severity high` | colour mode "dimension" or "severity"; the findings filter section |
| by depth | `omni graph lineage f:<id> --depth 3` (1 stops at the file, 3 reaches the requirement) | select a node: upstream chain in cyan, downstream in gold; "Trace to requirement" / "Trace to failure" buttons |
| by directory tree | `omni graph findings --tree --under src/` | Tree layout; the Findings tab opens on it; `--focus <directory>` |

Walkthrough:

```bash
./omni gate                                   # Arbiter writes arbiter-out/omni-gate/report.json
./omni graph build                            # findings become nodes
./omni graph findings --tree --severity high  # roll-up by directory, counts by category and severity
./omni graph why f:17a59c37fc20               # the file, the symbol, the requirement, the failure (if adjudicated)
./omni graph view --focus f:17a59c37fc20 --open
#   the detail panel shows path:line with a copy button and an editor link,
#   the rule, severity, category and status, and the arbiter review command
arbiter review arbiter-out/omni-gate/report.json --rule arbiter/secrets.aws-access-key
#   mark [y] / [n] in the queue file, then:
arbiter review arbiter-out/omni-gate/report.json --apply queue.md --ledger .ai/failures/failure-ledger.json
./omni failure update FAIL-015 --root-cause "..." --fix "..." --tests tests/test_x.py::test_y
./omni graph build                            # the finding now links recorded_as → FAIL-015
```

The same queries are MCP tools (`graph_why`, `graph_findings`, `graph_impact`,
`graph_lineage`, `graph_trace`, `arbiter_review_queue`), so an assistant can run
the whole trace without leaving the conversation.

## 6. Impact and test selection

`omni graph impact [--changed BASE] [--depth N] [--json]` resolves the change
set the same way the gate does, walks the governance, history, assurance and
workspace edges (never code edges) and lists the requirements, changelog
entries, failures, test files, suites, rules and commits the change reaches,
each with the hop count and the edge it came by. `omni gate` prints the
one-line summary. `omni test run --impacted` runs only the registered suites
that intersect that set (all suites, with a note, when there is no graph);
`omni test run NAME` runs one; the recommended example rule `completion.tests`
shows how to make it a required gate.

## 7. Pull-request output

With `--github` (automatic under `GITHUB_ACTIONS=true`), `arbiter gate` prints
GitHub workflow commands (`::error file=,line=,title=rule::title` for the
findings that failed the gate, `::warning` for the rest, `::notice` for
findings outside the change) so they appear inline on the PR diff, appends
`pr-comment.md` to the job summary, and writes `report.sarif`, which CI
uploads to code scanning (`continue-on-error`, so the gate's own exit code
stays the verdict). Titles and rule ids only: no format ever reprints
evidence.

## 8. What CI proves

| Job | Proves |
|---|---|
| Tests, doctor & gate (3 OS × Python 3.10/3.12) | the workspace tooling on every platform; with a vendored Arbiter present and an interpreter that meets `requires-python` from `arbiter/pyproject.toml`, Arbiter is installed, doctor starts both MCP servers for real and the gate runs `arbiter gate`; the SARIF is uploaded |
| Vendored Arbiter subtree tests | the subtree's own pytest suite, claim-integrity and mutation checks, so the copy cannot rot |
| Adopt loop | `omni adopt --with-arbiter` into a temp directory, commit, plant `verify=False`, `omni gate` fails naming `completion.arbiter_gate`, fix it, `omni gate` passes: the seam works end to end, not just each half |
| Optional graph extra | the five-layer graph builds and the viewer renders |

Arbiter's own `pr-check` runs its suite, integrity and mutation tools, the
analyzers, `omni doctor`, `omni gate` and a self-scan with `--github` and
`--no-cache`.

## 9. Keeping the two level

| Situation | Command | What it does |
|---|---|---|
| The workspace template moved | `./omni update --source ../OmniEngineering` | 3-way merge of the template-managed files; warns when the installed `completion.arbiter_gate` rule drifted from the template |
| Arbiter moved | `./omni arbiter update [--source SRC]` | upgrades the package, rewrites the rule unless `--keep-rule`, pulls a vendored subtree (`--squash` only when the history was pulled that way; refuses to mix modes unless `--force`), re-records the version, suggests a baseline refresh |
| Doctor warns "recorded X, installed Y" | the same | the recorded and installed Arbiter versions differ |
| The gate is green and old debt was paid down | `./omni arbiter baseline --refresh` | re-baselines from a full scan; refuses when the last gate was red or the scan was partial; prunes ids that vanished so a reintroduced finding counts as new |
| Doctor warns the baseline predates a fixed ledger entry, or its config hash changed | the same | the baseline no longer describes the policy or the code |

## 10. Requirement ids across the two

Each repository owns a registry, and an id is unique only inside it. Two
registries on the `REQ` prefix collide the moment one is vendored into the
other, so Arbiter's registry uses `ARB-###`. The registry's `id_aliases` map
(`"REQ-038": "ARB-038"`) keeps the old ids valid: the gate's requirement-id
check, `requirement show/complete`, `failure check` and doctor resolve an
alias to its target, and doctor errors on duplicate ids across the root,
its archive and every vendored registry. `omni requirement renumber --prefix
ARB` did the rename: registry and archive renumbered keeping the numbers,
aliases written, references rewritten in governance text only (never code,
tests, vendored workspaces or git history).

## 11. Off switches and risks

Every piece has a switch so a misbehaving one is disabled, not reverted.

| Piece | Switch | Risk it bounds |
|---|---|---|
| Arbiter gate inside `omni gate` | remove or set `severity: recommended` on `completion.arbiter_gate` | a red Arbiter blocking unrelated work |
| Baseline | delete `.arbiter/baseline.json` (every finding is new again) | hidden debt; doctor warns when it is stale, `omni doctor --json` carries `existing_high_or_above` under `posture.arbiter.full` |
| Completion check | `--no-arbiter-check REASON` | a stale report blocking a completion; the reason is recorded |
| Findings in the graph | `findings_report: null` in `.ai/graph-config.json` | a bad report polluting the graph |
| Result cache | `cache.enabled: false` in `arbiter.yaml` or `--no-cache` | stale findings; CI never uses the cache, `--verify-cache` samples hits |
| History | `--no-history` | nothing: the file is gitignored |
| PR output | `--no-github` | noise in logs |
| Governance probe severity | `probes.severity_overrides` | the probe being too loud or too quiet |

Secrets never travel: annotations, SARIF, graph nodes, history lines and the
viewer carry rule, title, path and line, and tests assert that no output
format reprints a planted secret.

## 12. Further reading

- This repository: `README.md` ("Arbiter alongside the workspace", "Code
  Graph", "Trace an Arbiter finding", "Daily Use"), `CHANGELOG.md`,
  `.ai/failures/failure-ledger.json` (FAIL-010 to FAIL-014 are the defects
  the integration surfaced and fixed).
- Arbiter: `docs/probes.md` (the governance probe and probe scopes),
  `docs/ci.md` (annotations, step summary, SARIF, scanning only what
  changed), `docs/cli.md` (formats, cache, history, dashboard),
  `docs/architecture.md` (the result cache), `docs/calibration.md`
  (adjudication and the ledger bridge), `.claude/skills/arbiter/SKILL.md`.
