# Unified graphics cleanup implementation — September 21, 2026

Status: reviewed cleanup implemented and validated; remaining preexisting scope
limits are explicitly recorded below.
Plan: [reviewed execution plan](GRAPHICS_CLEANUP_EXECUTION_PLAN_2026-09-21.md).
Starting evidence: [system review](GRAPHICS_SYSTEM_REVIEW_2026-09-21.md).
Branch: `codex/recovery-design`. Existing uncommitted work is preserved; this
cleanup has not created a commit. The pre-change reference includes the working
tree, not only HEAD.

## Result and ownership

| Unit | Implemented change | Evidence / remaining work |
| --- | --- | --- |
| A — active tests | Restore native assertions from five import-blocked modules; repair stale selected-content and causal assertions. Preserve retired server assertions as tracked historical source. | Engine 1,111 passed. Full game run found six final failures; both affected modules now pass all 13 tests after correction. Exact run disposition below. |
| B — replay | Admit the two historically absent optional native facts explicitly; no generic relaxation, invented defaults or recapture. | Four real archives reproduce their retained public state with empty engine registries. |
| B — media intake | Explicit bundle/replacement selection, merge unrelated assets/storage, preserve selected recipe and metadata. | Eight tests; real Poison replacement reimports identically, including 24 pages and compiled behavior. |
| C — attachments | Version-2 root/body/ground bases, recipient chord inset, one shared rig-point calculation, uniform scalar/directional pivot semantics. | 22,464 actual projectile-layer comparisons match pre-change pixels, destinations, blending and clocks exactly. |
| D — life presentation | Recorded life facts own authored fall/rest/recovery using the existing finite body sampling. | Real downing, stable/dying recipients, repeated native volley, both subjective views and existing Sleep cases pass. |
| E — native device targeting | Relevant primary range checks use existing origin/distance/effective-range functions. Secondary distances stay with their actual rules. | 53 classified adoptions; native mage/device execution, range, perception, costs and concentration tests pass. |
| F — terrain | Shared depth partition fixes above-support body masking while retaining foreground occlusion, coplanar bodies and unchanged static terrain. | All six xfails removed. Final support correction: 80 focused and 280 broader presentation tests pass, including all four cameras on an actor's own floor. |
| F — contracts | Explicit authoring semantics and truthful coverage output; previous status chronology archived with links. | Architecture checks 33 passed; final architecture plus attachment selection 35 passed. Game/review tooling typecheck clean. Native typing debt classified below. |

## What the new data means

[Presentation contract](../game/data/PRESENTATION_CONTRACT.md) is the portable
execution specification. There is still one Studio-shaped authoring format and
one shared sampler, with a Pygame raster adapter. No TypeScript runtime, native
rendering cues, spell-ID execution branches, callback managers, source hashes or
startup asset audits were added.

Local `dnd.spellStudioDrafts` is now version 2. Original NeuroStudio v6 and local
v1 inputs convert supported legacy placements once at the authoring boundary;
selected local records are written explicitly. The imported reference remains
unchanged. Scalar and eight-direction image pivots now mean the same thing.
Source sockets and finite cast media use the same rig-cell geometry calculation.

Fire Bolt's approved mage placement is represented by `rigRoot`, lift −64,
source chord inset 24 and recipient chord inset −16, with center image
registration. This preserves its actual former result, including rig scaling,
height and resting-target displacement; replacing it blindly with the torso
point would have moved it. Device shots use the measured cannon muzzle, with
target inset along the actual cannon-to-target chord. Existing ground-targeted
cannon spells retain their delivery.

The native origin adoption changes range validation/discovery, not spell rules.
It retains operator sight, source attribution, costs, eligibility and bounded
item concentration. Seven classified reaction, secondary-chain and follow-up
checks intentionally retain their own distance semantics.

`life-state-poses.json` selects DYING/STABLE entry, held pose and recovery through
the same finite body records/sampler used by conditions. An already downed body
does not stand and fall again on stabilization or death. A repeated volley
continues its first fall; healing relinquishes the life-owned pose while a real
remaining Sleep condition retains its own pose. Every owned native LifeFact is
retained, including a single hit's STABLE → DYING → DEAD sequence. Damage commits
at the existing impact-delay/HP-frame clock rather than being moved to arrival.

A real native replay exposed a separate five-line repair: an already DYING or
STABLE death-save actor's DamageApplied event published negative HP before the
engine silently normalized it to zero. Normalization now precedes that fact's
construction. Actual damage, overkill, temporary HP and death-save accounting
remain native. Eight native combinations and saved replay cover the repair;
presentation contains no compensating HP arithmetic.

## Evidence boundaries

The before reference lives under `.runtime/graphics-cleanup-20260921/before`.
The disposable comparison uses the actual pre-change and new modules/data;
it compares bytes directly, not hashes. It is evidence for this change, not a
new visual-baseline framework or a runtime check.

The 22,464 samples cover eight spells (Fire Bolt, Magic Missile, Poison Spray,
Ray of Frost, Ice Knife, Acid Splash, Guiding Bolt and Eldritch Blast), eight
Fire Bolt rigs, unequal actor scales, three position/height combinations,
standing/resting targets, phase samples, all four cameras and two zooms.
Release/anchor/completion clocks also match. This does not by itself prove
whole-world composition; the saved-input comparison below supplies separate
evidence. New captures are automated review evidence, not human approval.

### Final saved-input visual review

[46 perspective clips, each with all four cameras](http://127.0.0.1:8767/runs/20260921T105556Z-cf9048/index.html)
replay 3,022 mosaic frames at 12 fps. All replay/encoding/history checks pass.
Inputs are retained public events; existing inputs were not regenerated.
Only the four new native projectile-life experiments needed new capture, once
per experiment with both participants from that same generation. The final
version gives their caster an ordinary explicit 20-HP starting pool.

The matrix covers mage and cannon Fireball/Sleep/Web, Fire Bolt across height,
Poison Spray, Ray of Frost, Ice Knife, repeated Magic Missile, support and direct
effects, a smooth door, jaw injury, jump/forced movement, opportunity downing,
stabilization/healing, and the new native downing/stable/dying/repeated histories.

Eleven before/after reference clips contain 1,007 frames. Four clips (400 frames,
Fireball cannon and mage Sleep, both perspectives) are pixel-identical with the
final compositor. The seven raised-terrain Fire Bolt/Magic Missile clips reflect
the intentional terrain correction. A disposable isolation run uses **current
playback, data and media with the preserved former terrain painter**: all 607
frames of those seven clips are pixel-identical to the original reference.
This proves the attachment/lifecycle refactor preserved those whole scenes when
terrain is held constant; it does not claim the corrected terrain is unchanged.

Raw poster inspection after the support fix shows zero Fire Bolt height changes
at the reference instant. The remaining 89 Fire Bolt level / 18 Magic Missile
poster pixels are confined to the stair flight, above its upper support plane;
the independent reviewer confirmed they are intended visibility corrections.
Compressed video differences spread through encoder prediction and should not
be read as counts of distinct changed gameplay pixels. No automated regression
framework or runtime hash was introduced.

The `walk-downed` recording still reports one selected goblin slash-media gap;
passing replay checks are not a claim that this recording has no media gaps.
This is preexisting: the selected Goblin rig, attack profile and layer selection
match the before snapshot. Its body/shadow supply `Attack1`, while the separate
modular `slash/Slash1` overlay is absent. The final trace confirms Attack1 frames
0–13 in all four cameras, contact at 666.67 ms, six damage and DYING at zero HP.
The missing overlay does not suppress the attack, damage or downing body.

The importer probe used the retained cantrip bundle plus the explicitly selected
`poison-local-fix/delivery` in a temporary output. Ordinary selected reimport,
replacement and repeated import retained effective asset metadata, storage,
recipe and compiled applications. The 24 selected page files match directly.
Bare historical bundle invocation now requests explicit selection before writes;
`--bundle-only` remains available for an intentional older selection.

Four old native recordings — Thunderwave, allied invisibility, device volley and
mixed residues — decode, project and reduce to the same retained public result
without executing native scenarios. Both engine registries and the event queue
remain empty. Missing movement speed and temporary-HP grant stay unknown, rather
than becoming a fabricated speed or owner.

## Terrain disposition and cost

Whole raised-floor/cliff pictures hid body pixels already above the upper
support. The shared partitioner now limits floor/cliff/stair occlusion to
their known upper support. The ceiling can move terrain behind above-plane
pixels; it cannot promote a supporting floor over the feet of its own actor.
It partitions only where
incoming visible world pixels cross the depth ordering; static seams and pixels
outside those pictures remain unchanged.

Four jump xfails were reproduced masking errors. Two stair xfails asserted an
arbitrary minimum number of visible body pixels in every view. Their replacement
requires visibility above the terrace plane while retaining valid foreground
hiding below it. All six now have passing geometric assertions. Eight measured
views have zero missing above-plane pixels and zero static/outside-body changes.

The whole-frame comparison caught a regression missed by the initial tests:
uncapped floor depth clipped feet on the actor's own support. The corrected
floor uses the same ceiling-only cap as cliffs/stairs. The new four-camera
native landing/idle check requires the entire opaque body to survive, recovering
54/0/61/19 previously lost pixels. The earlier above-plane-only assertions were
insufficient for coplanar sprites. All eight raised-terrain comparison views
were rerun after this correction with the same zero-loss/outside-change result.

This additional raster work has a measured cost: roughly 2.0 ms before versus
3.3 ms after in aggregate for the final warm 640×480 terrain scene. Per-view
medians were 1.8–2.7 ms versus 2.9–4.1 ms under concurrent work. This is a small
bounded frame measurement with scheduling noise, not a global performance
claim. Native gameplay is unaffected.

## Test restoration and retirement

[Tracked disposition](retired_server_tests/2026-09-21/README.md) identifies each
retired HTTP/session/objective-cache assertion and where active native assertions
remain. Originals are preserved as `.py.txt`, not silently skipped or deleted.
The current game cold-import check replaces the old server cold-import check.
The native `EquipmentSlot` owner is distinct from the Studio string-slot alias;
the existing passive senses-to-geometry edge is declared explicitly. DAG,
no-late-import and direction checks retain their requirements.

This work does not restore the retired server or claim that all historical
manual-server wrappers are an active test lane. The documented active lane is
`tests/game tests/engine`, with selected native device tests under `tests/manual`.
No ad hoc five-file exclusion is needed.

## Validation record

WSL source: `/mnt/c/users/tommaso/documents/dev/dnd_engine`.
Environment: `/home/tommaso/.cache/dnd-engine/venv`, invoked through
`/home/tommaso/.local/bin/uv run --no-sync`, SDL dummy video/audio.
Evidence logs are under `.runtime/graphics-cleanup-20260921/`.

- Engine before the additional already-downed recording repair: 1,103 passed.
- Final engine suite after that repair: **1,111 passed**, 119.10 seconds.
- Focused native/device/archive checks: 100 passed; two added Shocking Grasp
  range rows also pass. These overlap other selections and are not additive.
- Attachment/reference/volley/source-data/device checks: 137 passed; new explicit
  attachment checks: 42 passed; measured device-muzzle checks: 10 passed.
- Terrain/environment broad check: 276 passed; final focused check: 96 passed.
- Media import and coverage stdout: 8 passed.
- Architecture dependency and AI import-direction modules: 33 passed.
- Integrated architecture plus explicit attachment checks: 35 passed.
- Historical NeuroClient timing/visible-frame oracle: 54 passed. Assertions now
  compare the equivalent image point after registration conversion, and replace
  the former downed-state rejection with actual pose/HP/life timing checks.
- Native projectile-life presentation: 12 passed after giving the gallery's
  caster an ordinary explicit 20-HP starting pool.
- All `game` and animation-review Python modules plus the coverage CLI:
  **zero Pyright errors or warnings** with the project interpreter.
- Full game run: **1,836 passed, six failed**, 1,207.23 seconds. That process had
  loaded the earlier floor formula; four failures were spatial-deployment
  actor occlusion, closed by the coplanar correction. Two healing tests still
  expected a zero-duration recovery and were corrected to check immediate HP/
  life with the authored 1,250-ms reverse body and independent 900-ms feedback.
- Final rerun of both failing modules: **13 passed** in 27.26 seconds, including
  all four subjective healing clips and their four-camera checks. No failure
  from the full run remains unresolved. The independently repeated final
  compositor selection passes **280 tests**; the new life fixture passes 12.
  These overlapping runs are not added together as a new whole-suite count.
- Final collection: **1,847 tests**. Four coplanar body cases and one additional
  healing-context parameter were added after the full run's collection. This
  report does not invent a later single all-green full-suite invocation.
- Final follow-up typecheck of the compositor and native-life capture fixture:
  zero errors/warnings. Working-tree `git diff --check` also passes.
- Final gallery: **46/46 passed**, 3,022 frames; actual gap disclosure above.

### Native typecheck scope

The broader native Pyright run is **not clean: 266 errors and one warning** over
249 files. A disposable paired comparison reconstructs the native code before
this cleanup by reversing only its classified distance/range changes and the
five-line downed-HP repair; unrelated accumulated branch changes stay present.
Both copies produce identical full diagnostics, including source ranges, rules
and messages: zero introduced and zero resolved. Eleven errors are at unchanged
sites in four touched spell files; the other 255 and the warning are in untouched
native files. `dnd/entity.py` has none. Runtime test success does not erase this
debt, and this result does not describe the whole repository as type-clean.
The full classification and reproducing probe are retained under
`.runtime/graphics-cleanup-20260921/native-types-*`; no suppression was added.

### Coverage remains an inventory, not an approval claim

The initialized report contains 72 event categories, 54 retained native models
and 398 presentation rows. It reports 257 selected bindings, 75 catalog spells
without bindings, 38 state-only rows, 19 declared fact routes, five partial
condition presentations and four accepted potion-source-media omissions.
The five partial entries are Dragon Wings' rig layer and four weapon-coating
equipment modifiers. Their actual missing consumers remain stated. The new
DYING/STABLE authored poses appear in the same inventory. No asset audit or
encounter execution is needed to produce it.

## Independent review

Anti-slop and anti-OOP/ECS reviewers approved the plan before implementation.
Both approved the final attachment/lifecycle/native integration: passive data,
shared sampling, actual facts, preserved timing and no new manager or spell
executor branches. The final whole-frame comparison additionally caught the
coplanar-floor regression; its correction, strict four-view test and remaining
stair visibility differences received the independent follow-up review described
above. The real native HP publication defect was independently reproduced before
its narrow correction. Reviewer records and complete logs remain under
`.runtime/graphics-cleanup-20260921/`.
