# Original cleanup implementation checkpoint — historical

**Current status:** the authorized repairs and independent source reviews are
recorded in [the repair implementation report](CLEANUP_REPAIR_IMPLEMENTATION_2026-10-03.md).
The complete game-suite receipt is being reconciled there. Everything below is
the earlier checkpoint, preserved as diagnostic history rather than current status.


**Correction after independent implementation review, October 3:** the earlier
completion claim below was too broad. All three implementation reviewers
request changes. The [anti-slop review](audits/CLEANUP_IMPLEMENTATION_ANTISLOP_REVIEW_2026-10-03.md)
also reproduces Spike Growth entry damage incorrectly joining a pushing spell's
result and appearing twice. The [ECS review](audits/CLEANUP_IMPLEMENTATION_ECS_REVIEW_2026-10-03.md)
reproduces rejected-effect ownership leaks and a new speed-query mutation; the
[event review](audits/CLEANUP_IMPLEMENTATION_EVENT_RENDER_REVIEW_2026-10-03.md)
reproduces unsafe legacy retaliation ownership, early temporary-HP timing and
missing authoring-schema exports. Passing focused checks did not cover those
contracts. The independent reviews and the
[complete repair plan](CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md) are separate from
the historical design approvals. No repair implementation has started.

The revised repair proposal now has separate
[anti-slop](audits/CLEANUP_TEST_REPAIR_PLAN_ANTISLOP_REVIEW_2026-10-03.md) and
[ECS](audits/CLEANUP_TEST_REPAIR_PLAN_ECS_REVIEW_2026-10-03.md) approvals at SHA256
`78f6cb43170e26eff5b8f37dbf886838d98070ec33e1b262ea8e93c4e7200c06`.
Those approvals do not change the implementation's REQUEST CHANGES verdicts.
Every prior game failure/error has a disposition in
`.runtime/cleanup-20261003/validation/game-repair-dispositions.json`: 294 planned
repairs and 50 focused passes awaiting the final full rerun.

Implementation authorized October 3, 2026. Starting commit:
`981079bc0208dbb23f3ccc927347eef77fef4c30` (`pre-cleanup`); clean checkout.
Approved design SHA256:
`6fc466f87c66b5398af39655d27abbf7614389c19f548f851cd847f0edc34f58`.
See the [plan](ANTISLOP_CLEANUP_PLAN_2026-10-03.md) and
[independent approvals](audits/ANTISLOP_CLEANUP_PLAN_REVIEWS_2026-10-03.md).

Recovery source archive, SHA256 manifest and initial tracked diff:
`/home/tommaso/.local/share/dnd-engine-recovery/cleanup-20261003-981079bc0208`.
The archive contains 2,995 tracked source/configuration/document files, not art.
The user commit also preserves the complete tracked starting state.

## Progress

| Step | State |
| --- | --- |
| 0 Preserve starting state | Complete |
| 1 Remove ammunition expansion | Implemented; focused validation passes |
| 2 Weapon semantics and typed Multiattack choice | Implemented; focused validation passes |
| 3 Unified speed/expenditure and mode-aware Move | Implemented; contextual speed-query purity failed independent review |
| 4 Canonical spell/trait/item ownership | Implemented; rejected admission leaks failed independent review |
| 5 Resource and typed event contracts | Implemented; legacy causal migration and Spike Growth exposure ownership failed independent review |
| 6 Shared event digestion/presentation/schema | Implemented; unknown-owner HP timing and export coverage need repair |
| 7 Typed discovery | Implemented; native checks and typing pass |
| 8 Full active validation and closure | Incomplete; recorded full-suite failures and independent blockers require the repair plan and final rerun |

## First acceptance boundary

Inputs: ordinary ranged Attack/Multiattack with empty ammunition inventory;
retired arrow content IDs; existing powered quiver with an equipped ranged weapon.
Observable contract: ordinary attacks retain their established costs/results,
retired arrow IDs cannot be admitted, and quiver eligibility uses weapon kind
without retaining any selected-ammunition route. Preserve source saves and the
accepted finite-use item/coating behavior.

## Implementation evidence

The four retired arrow IDs fail admission explicitly. Existing ordinary attacks,
Basic Poison and item coatings retain their execution paths. Weapon definitions
now carry kind/material, and Multiattack's optional replacement is typed data.
Walking/flying speeds use the existing value system with exact arithmetic factors;
one expenditure ledger and turn-owned Dash credit determine remaining movement.
Flight uses ordinary Move. The three task-owned runtime modules are deleted;
retained spells, traits and wearable powers use their existing domain owners.

Focused native validation: **210 passed** in `/tmp/cleanup-native-focus.log`.
This preceded the resource/concentration edits and is not full-suite acceptance.
The early full-engine diagnostic was deliberately stopped after finding a stale
movement API test; it provides no full-suite result. Mechanical test migrations
replace old remaining-movement reads with the explicit budget query without
changing expected results.

Resource work uses lineage history for terminal-once release and stale preparation
rejection, explicit consume/recharge semantics, and action-owned closure of pending
preparations. The historical resource wire identity remains. Concentration teardown
publishes changed state at the committed graph boundary; unchanged cleanup does
not emit another state change.

Player sequence v2 carries resolution/application ownership, distinct requested
and committed damage, exact observed source versions, spatial commit versions,
and construction/concentration instance ownership. Native field installation
publishes its observation before appearance callbacks. Capture preserves causal
headers; projection independently removes undisclosed references. Old recordings
are preserved. Independent review found that the new compatibility migration
incorrectly treats immediate Attack/Spell parentage as sufficient ownership proof;
this claim is not satisfied until repaired.

The existing choreography compiler uses one causal index, retains ordered damage
results and shares compiled impact timings between body, HP and feedback. It no
longer splits sensory nodes for formation or decides result ownership from art
availability. Four lifetime consumers share traversal while retaining their
separate membership policies. World bindings have one passive schema admission.
Schema export covers player, draft and world-binding roots without the paused
server, but omits required action/context/rig authoring roots. Discovery consumes
typed descriptions from its action owner.

## Validation results

Runtime: `/home/tommaso/.cache/dnd-engine/venv`, Python 3.13.12 through
`uv run --no-sync`; sources on WSL `/mnt/c`. Tests do not omit known failures.

| Boundary | Result / receipt |
| --- | --- |
| Full engine + progression + AI | 2,342 passed, 4 failed, 2 collection errors; `/tmp/cleanup-native-final24.log` |
| AI baseline reproduction | Same 4 failures, 2 passed at pre-cleanup source; `/tmp/cleanup-baseline-ai29.log` |
| Architecture | 76 passed, 5 failed; `/tmp/cleanup-architecture31.log` |
| Full game suite, all 228 files | 2,665 passed, 157 failed, 187 errors, 2 xfailed; partition receipts and corrections below |
| Typing: dnd, game, affected gallery entry points | 0 errors; `/tmp/cleanup-types41.log` |
| Typing: two subsequently corrected replay files | 0 errors; `/tmp/cleanup-final-types47.log` |
| Ownership, current/legacy replay, projection, damage | 23 passed; `/tmp/cleanup-replay30.log` |
| Spatial commit, portal/opportunity movement, attack | 116 passed; `/tmp/cleanup-spatial21.log` |
| Wall heat, formation, AoE, attacks | 56 passed; `/tmp/cleanup-walls17.log` |
| Destruction clearance | 6 passed; `/tmp/cleanup-milestones15.log` |
| Coverage and capability reporting | 9 passed; `/tmp/cleanup-coverage36.log` |
| Injury/result consumers, Shield interception, spell replay | 132 passed; `/tmp/cleanup-result-consumers38.log` |
| Resource/ownership legacy compatibility | 16 passed; `/tmp/cleanup-resource-compat39.log` |
| Legacy empty-application round trip and ownership | 8 passed; `/tmp/cleanup-legacy-roundtrip45.log` |
| Extra Attack, Haste, Action Surge, Slow, offhand/Frenzy matrix | 366 passed; `/tmp/cleanup-attack-budget43.log` |

The first full game diagnostic was interrupted after fixes made its source snapshot
obsolete (87 failed, 1,243 passed, 139 errors, 2 xfailed). It is not full acceptance.
All 228 game test files completed in three process partitions, including
collection failures: `/tmp/cleanup-game-final{0,1,2}.log`. Their raw results were
respectively 1,129/52/27, 936/68/3, and 600/37/157 passed/failed/errors; the last
partition also reports two existing xfails. Wall times were 716.80s, 974.91s and
920.94s. No test file or failing collection was excluded.

The broad run had already loaded tests using the old combined damage fact.
Their 49 failures were corrected by selecting `DamageResultFact` for committed
injury and `DamageRequestFact` for interception. Expected outcomes are unchanged;
all 132 checks in the eight migrated files pass in
`/tmp/cleanup-result-consumers38.log`. One legacy empty-application round-trip
regression was then corrected; its existing case plus all seven ownership/replay
cases pass in `/tmp/cleanup-legacy-roundtrip45.log`. These are focused reruns, not
a claim that a second full game run passed.

Every broad-run failure/error is accounted for:

| Cause | Raw failures/errors | Disposition |
| --- | ---: | --- |
| Damage fact test consumers | 49 | Migrated and passing focused rerun |
| Empty legacy application marked as missing | 1 | Fixed and passing existing regression |
| Catalog-wide `call-lightning` union mismatch | 86 | Existing catalog admission defect, including two collection errors |
| Baseline-only fixtures omit required wall media | 179 | Existing fixture/admission mismatch |
| Older native archives omit required damage/attack fields | 11 | Existing archive compatibility debt |
| Obsolete finite Blindness/Deafness media assumptions | 12 | Existing tests, including response fixtures borrowing those strips |
| Ice/Stone formation disclosure | 2 | Existing native producer defect |
| Lethal-delivery idle frame clock | 2 | Existing playback defect |
| Stacked condition pre-contact membership | 2 | Existing playback defect |

The final seven categories account for 294 remaining failures/errors. This is a
classification of the broad run after the 50 corrected cases, not a newly run
all-green suite. Per-case traces are saved in the three
`validation/game-part*-failures.json` receipts. The two construction xfails stay
reported separately.

The normal four-camera gallery replays saved public v2 bytes for item transfer,
wall formation damage and cloud movement: **7/7 clips, 154 checks, zero gaps**.
Inputs and original native recordings:
`.runtime/cleanup-20261003/review/inputs`. The first attempt caught a coverage
consumer still assuming a flat fact union; it was corrected to read the actual
schema discriminator. Render receipt: `/tmp/cleanup-gallery37.log`.
Gallery: `.runtime/cleanup-20261003/review/runs/20261003T002630Z-2404ba/index.html`.
Sampled cloud movement, wall impact and floor-dagger frames were inspected. Wall
art starts at 1,218.75ms; simultaneous recipient injury starts at 1,875ms. No new
art, palette treatment or wall/cloud composition was introduced.

Completed receipts are copied into `.runtime/cleanup-20261003/validation`.
Production hashes at partition start are preserved separately. Two later production
changes make the missing legacy item-operation label explicitly null and correct
the omission marker for an explicitly empty legacy application. Their focused
resource/ownership/replay receipts pass. Current producers always disclose
consume/recharge. Old after-values still reduce identically.

### Failures and diagnoses from the first full-suite receipts

- AI decision rows omit `double_on_critical` and other native damage-profile
  values. Four failures reproduce at the pre-cleanup commit; no AI rule change
  is folded into this cleanup.
- Two progression modules import deleted character/server modules. The paused
  server's catalog cold-start also imports `dnd.core.senses`.
- Four architecture evidence checks retain old content hashes, structural-owner
  counts or item inventories. These are provenance/content reconciliation work,
  distinct from the passing dependency-boundary checks.
- Outdated animation test setup omits the current authored bundles but still
  loads world bindings that require them. Both baseline and current source reject
  that combination; full production loading works. The checked wall bank's 27
  referenced files exist. Tests must follow current assets, not restore an older
  game asset set.
- The review catalog contains `call-lightning`, absent from its scenario union.
  This breaks catalog-wide collection and cases unrelated to that spell. The
  acceptance gallery captures only its three existing typed cases via the normal
  capture API and then uses the standard review CLI; no catalog row is deleted.
- Ice/Stone construction formation is not published with its sections present:
  CREATED precedes section placement, and the observer receives SEEN later.
  Baseline and current native traces show the same missing formation fact.
- Earlier native archives omit `TakeDamageEvent.effect_origin`; the committed
  decoder already rejects these records. Preserve them for an explicit migration.
- Blindness/deafness finite-media expectations predate the accepted sustained
  glyph change; see `SPELL_QUEUE_INTEGRATION_PLAN_2026-10-02.md`, lines 346–352.
  Seven support-response tests borrow that now-empty finite fixture; the same
  failures reproduce on pre-cleanup source in `/tmp/cleanup-baseline-support46.log`.
- The earlier classification of the idle/stacked assertions as proven playback
  defects was too strong. A further native-history probe shows completed Idle
  correctly uses the scene clock supplied by the test. The stacked test asks for
  an intermediate native membership before two commits' shared timestamp.
  The repair plan preserves finite delivery and tests grouped commit semantics,
  including appearance sampling; it does not change accepted visuals to match
  stale expectations.
- Three older attack fixtures lack magical-attack/projectile-deflection facts.
  The pre-cleanup decoder already rejects these archives (and also demanded the
  now-removed ammunition fields). The separate empty-application round-trip
  regression introduced here is fixed and passes its existing regression case.

The bounded gallery rendered successfully, but implementation acceptance is
incomplete. Its seven clips represent three scenes and cannot establish complete
event, renderer or game integrity. The 294 residual game cases are a classification
of earlier partition receipts after 50 focused corrections, not a fresh final
full-suite run. Source changes remain uncommitted, with no push or history rewrite.

The user subsequently authorized independent implementation reviews and a full
repair plan. Reviewers made no production/test edits. Unrelated agent coordination
remains stopped.
