# Cleanup repair implementation

Status: **complete and independently accepted**. Implementation, complete
active-suite reconciliation, visual checks and all three final review addenda
are complete. This supersedes the diagnostic
status in [the original implementation checkpoint](ANTISLOP_CLEANUP_IMPLEMENTATION_2026-10-03.md).
The approved [repair plan](CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md) is preserved
at SHA256 `78f6cb43170e26eff5b8f37dbf886838d98070ec33e1b262ea8e93c4e7200c06`.

## Implemented result

| Plan work | Implementation and preserved contract |
| --- | --- |
| Current assets and fixtures | Production world tests load the current bundles. Tests of a specific geometry/timing recipe author that input explicitly through one test helper. Required-media admission stays strict; no artwork was restored, removed or repacked. |
| Review catalog | Typed Call Lightning scenario and existing native capture route cover initial three-target cast, save, outside occupant, repeat strike and concentration removal. No spell rule is implemented in the recorder. |
| Condition media and playback expectations | Sustained Blindness/Deafness glyphs use their current lifetime. Generic finite-effect tests have an explicit finite fixture. Completed bodies rejoin ambient Idle; simultaneous condition commits assert first-before/final-after. |
| Recorded event compatibility | Named additive fields retain recorded omission. Legacy damage ownership requires actual proof; ambiguous old packets diagnose precisely instead of inheriting the nearest parent's identity. Explicit current unknown ownership remains valid. Fixture bytes are preserved. |
| Result ownership | Spike Growth exposures own independent results while retaining trigger ancestry and field origin. Known and unknown causes both schedule normal and temporary HP at the authored damage commit. |
| Damage/movement order | Shared scheduling uses preceding typed result commits and each recorded displacement arrival. Ordinary forced movement clears the inherited cast state milestone, preventing destination disclosure before travel; existing avoidance hops keep their explicit landing milestone. No spell-name branch or second scheduler was added. |
| Construction | Accepted sections and formation displacement commit before CREATED. Cancelled activation leaves no objects. Two strict xfails were faulty scenario loops attacking an already retired section after negative HP; the ordinary spatial targeting rule was already correct. Both now pass without an engine targeting exception. |
| Effect ownership | Entity and BaseBlock share the existing declared-condition commit boundary while keeping Entity immunity/save gates. Dependent effects and concentration use paired admission. Failed admission/cancelled casts release only provisional modifiers, light and grants. Resistance uses that boundary too, including Warden pack use. |
| Read purity | Contextual computed caches are private evaluation data; transient armor-speed modifiers are not globally registered. Repeated speed/discovery reads do not mutate serialized authoritative state. One movement expenditure owner remains. |
| Passive schema | Sixteen actual authoring/public roots are exported, including damage/death/movement/condition/rig timing. Fresh-process export does not import live rules/content/server or initialize Pygame. [Schema contract](PRESENTATION_SCHEMA_EXPORT.md). |
| AI and evidence | Restored passive damage save/critical fields. Reconciled current item/icon/SRD admissions with explicit deltas while preserving historical ledger authority. No runtime dependency on audit ledgers. |
| Paused server | Original HTTP/database tests remain in an explicit paused directory without skip/xfail/filtering. Active character record/build/equipment tests run. No server service or compatibility API was recreated. |

The original cleanup's ammunition removal, six requested spells and three powered
backpacks remain. This repair adds no content rules or rendering framework.
Diagnostic corrections, including Dretch rather than Wight as the extra ledger
owner, are recorded in [the evidence notes](audits/CLEANUP_REPAIR_EVIDENCE_2026-10-03.md).

## Verification receipts

All receipts below are under `.runtime/cleanup-20261003/validation/final/`.
Commands use `UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv
/home/tommaso/.local/bin/uv run --no-sync`; Python 3.13.12, Pygame 2.5.8.

| Command after the runtime prefix | Receipt | Result |
| --- | --- | --- |
| `pytest -q tests/engine tests/ai tests/progression` | `native-final.log/xml` | 2,386 passed; no failed, skipped or xfailed tests |
| `pytest -q tests/architecture tests/test_*.py` | `architecture-packaging-final.log/xml` | 120 passed; includes fresh-process dependency/schema checks |
| `pytest -q tests/game` | `game-final.log/xml` | 3,045 passed + 1 exposed hop regression in the full run; corrected, then all 34 affected-module tests passed |
| `pyright dnd game` | `pyright-active-final.log` | 0 errors |
| `pyright` using configured project roots | `pyright-final.log` | 134 errors, all in 21 paused `server/` files |
| `pytest -q tests/paused_server` | `paused-server.log/xml` | Two retained collection errors importing removed server character modules |
| Explicit paused cold-start test | `paused-cold-start.log` | One retained failure importing removed `dnd.core.senses` |

These are the exact active directories required by repair-plan step 12, plus
root packaging tests. The historical `tests/manual` tutorial/server migration
material is not included in these totals; no whole-repository green claim is made.

`acceptance-receipts.json` reconciles **5,552 unique active tests**: 2,386 native/AI/
progression, 120 architecture/root and 3,046 game. Full game execution matches all
3,046 collected IDs exactly. No active test was skipped or xfailed. The complete
run took 2,795.65 seconds and retains its one failure; the bounded 34-test rerun
took 46.78 seconds. Its IDs are already part of the 3,046, not added to the total.
`game-repair-dispositions-final.json` accounts for **all 344 original game
failure/error entries**. `outside-game-dispositions.json` separately identifies
the original AI, architecture and paused-server outcomes.

`paused-test-inventory.json` lists all eight retained static test-definition IDs;
seven are inside the two uncollectable modules, so this is not a claim that their
parameter instances ran. `pytest tests` still enters the paused lane and is not
described as green. Active durable-record/build coverage is documented in
`tests/paused_server/README.md`.

A separate, broader `pyright dnd game devtools` probe reports eight stale imports
in the historical `devtools/generate_srd_5_1_source_coverage.py` offline generator.
That directory is outside the configured project typing roots; the receipt is
`pyright-all-devtools.log`. The generator was not run or used to regenerate the
accepted evidence. This is an explicit tooling limitation, not an active game
typing failure or a reason to silently broaden this repair.

Earlier full-game runs loaded changing capture schemas and are retained as
`game.log` and `game-schema-stale.log/xml`; they are superseded diagnostic runs,
not final acceptance. The retained full run started before the final one-line hop correction. Its
existing landing test exposes that regression; `hop-forced-final.log/xml` records
all 34 affected-module tests passing afterward. Final acceptance reconciles the
complete collection with that explicit rerun; it does not relabel the original
full run as a single all-green execution.

## Visual and independent review

The [visual acceptance matrix](audits/CLEANUP_REPAIR_VISUAL_ACCEPTANCE_2026-10-03.md)
records 44 observer clips across 24 native scenarios, exact inspected moments,
four-camera results, paired knowledge boundaries, and explicit existing artwork
limits. Call Lightning's targetless repeat-action delivery has two retained
missing-binding diagnostics; recipient lightning and native results are present.
Fly retains the existing movement pose. No new art or binding work is claimed.

- [Independent anti-slop review](audits/FINAL_CLEANUP_ANTISLOP_REVIEW_2026-10-03.md): final acceptance APPROVE, including the final damage/position and avoidance-hop corrections.
- [Independent ECS/import-DAG review](audits/FINAL_CLEANUP_ECS_REVIEW_2026-10-03.md): final acceptance APPROVE, including rejection/replacement and Warden ownership checks.
- [Independent event/presentation review](audits/FINAL_CLEANUP_EVENTS_REVIEW_2026-10-03.md): final acceptance APPROVE, including archive ambiguity, typed causal identity, HP timing and displacement arrivals.

These are implementation reviews, distinct from the earlier plan approvals.
All three final receipt addenda independently reconcile the complete collection,
the bounded hop rerun, all 344 diagnostic dispositions, source pins and the
44-clip evidence. No unresolved blocker remains within the approved scope.
`final-review-receipts.json` records the three report hashes.

## Source and recovery

Base commit `981079bc0208dbb23f3ccc927347eef77fef4c30` remains unchanged.
Edits are uncommitted. The source archive at
`/home/tommaso/.local/share/dnd-engine-recovery/repair-20261003-start` preserves
the 3,031-file pre-repair snapshot and starting diff; the original cleanup
backup is separate at `cleanup-20261003-981079bc0208` in the same parent.

`source-freeze.json` records 1,284 executable-source/config/test paths (including
deletions), digest
`1afbfeb3a79e4a308dd2d3deb74a61757be97ce973c0b43f417f28a0493d8226`.
Documentation is outside this digest so review receipts can be appended without
changing the tested source. Final validation checks every recorded path again.

`source-final.json` records the final source digest
`723bc6198c189c65358880edff89190acd0149a05b2e1782dab34807870b3727`.
Within that declared snapshot scope, only `game/choreography.py` differs from
the original full-run snapshot: the
inherited state reset is now inside the no-owned-hop branch. The affected rerun
and all three review addenda identify that exact revision.

The 1,284-path receipts cover `dnd`, `game`, `devtools`, tests, content and
root code/config; they do not include the top-level `ai/` tree. Its sole changed
file, `ai/policy/generations/registry.py`, removes one unused import and is
independently pinned in both the anti-slop and ECS reports at SHA256
`202febf89f6276104a0bc83bd2042e11a7913ca14ea3b8c95f024b2f54769bcf`.
That pin still matches. Neither receipt is described as a hash of every file
in the repository.
