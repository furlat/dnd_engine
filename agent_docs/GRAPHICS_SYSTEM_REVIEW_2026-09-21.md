# Graphics and gameplay integration review — September 21

Status: review and cleanup proposal; no production implementation in this review.
Follow-up: the user's behavior-preserving Fire Bolt unification request is
incorporated in the independently reviewed
[execution plan](GRAPHICS_CLEANUP_EXECUTION_PLAN_2026-09-21.md), which supersedes
this document's preliminary cleanup order.
Branch: `codex/recovery-design`. Committed checkpoint: `018954bcd8` (`claned up`),
with the accumulated working tree included. This reviews the active Python/Pygame
system before the next level-two/three spell delivery, following the user's
request to check whether successful VFX demonstrations have concealed poor design.

## Verdict

The shared design is real, but the implementation is not fully clean or complete.
The principal problems found are incomplete integration of existing capabilities,
media-selection ownership and stale contracts. This is not evidence that we need
to replace the timeline system or introduce another generalized animation engine.

The active runtime generally dispatches on facts and presentation capabilities,
not on individual spell names. Recipes, rig mappings, attachments, media phases,
condition layers and movement tracks are authored data. Native mechanics still
own outcomes, conditions, geometry and object state; historical playback consumes
permitted recorded facts. Those foundations should be preserved.

However, a real projectile spell that downs a player can lose its cast animation;
some device-granted spells still measure range from the operator; an ordinary
cantrip reimport can break the selected Poison Spray; and new defaulted event
fields have broken older native archives. Passing focused demonstrations did not
prove these surrounding contracts. One existing test actually asserts the obsolete
projectile/downing refusal as correct behavior.

## Scope and method

Read the current recovery commitments and previous graphics cleanup/result, then
examined the active authoring loaders, importers, types, registration/drawing,
timeline/combat/choreography, historical state, condition/media lifetimes, motion,
portals, traps, devices, residues, event capture and player projection/reduction.
The review includes earlier active code when new work depends on it. Retired
server architecture is not a target for restoration.

Independent anti-slop and anti-OOP/ECS reviewers inspected presentation and native
boundaries respectively. Suspicions were checked against real behavior: a native
Fire Bolt downing action, actual source-item targeting, existing saved archives,
and a real media reimport into a temporary directory. Broad tests and typechecking
support the review; they do not substitute for these cases or human visual approval.

Evidence lives under `.runtime/graphics-audit-20260921/`. No game code, recipes,
media or saved inputs were edited by the review. Disposable probes are not a new
test platform, startup check or runtime dependency.

## Confirmed findings

### 1. Projectile presentation rejects normal player downing — high priority

`game/animation.py:1169` rejects both initially and subsequently `DYING`/`STABLE`
recipients. `tests/game/test_animation.py:343` expressly expects that rejection.
These restrictions date from the initial bounded cast implementation.

**Reproduction:** a real Fire Bolt against a 4-HP character with death saves
enabled completes successfully and leaves `0 HP / DYING`. Binding its retained
lineage produces zero cast nodes and reports the unsupported dying/stable state.
The renderer therefore loses the spell delivery at a routine gameplay boundary.

The shared damage/lifecycle and melee paths already distinguish downing, death,
stabilization and revival. This is an incomplete connection, not a missing native
rule. Removing the guard alone is not enough evidence: the existing shared life
state must commit at the owning authored point relative to contact and remain
correct through the rest of the lineage.

Planning follow-up clarified two details: commit means the existing authored
damage/lifecycle point relative to contact, not necessarily immediate arrival;
and DYING/STABLE currently lack an authored downed body pose. Native downing
installs capability modifiers directly and does not emit an Unconscious condition
application. The execution plan therefore adds a small state-selected pose/
transition authoring capability while retaining `LifeFact` as its state owner.

**Smallest repair:** connect projectile delivery to those existing semantics;
replace the outdated rejection test with genuine recorded downing, already-downed,
stable and terminal-death histories. Never substitute `DEAD` for `DYING` or infer
life state from HP. Preserve targets, anchors and approved standing spell output.

Evidence: `repro_projectile_downing.py`, `projectile-downing.log`.

### 2. Device-origin targeting is not consistently used by spell validators

The shared origin/distance seam exists in `dnd/actions.py:4466` and
`dnd/core/base_actions.py:1206`. Existing validators such as
`dnd/spells/enchantment.py:377` and `dnd/spells/necromancy.py:301` still call the
operator's sensory distance directly.

**Reproduction:** operator `(2,5)`, cannon `(3,5)`, target `(4,5)`, authored device
range five feet. Fire Bolt discovers the target and executes. Hold Person and
Chill Touch expose no target and reject the direct request as ten feet away.
The latter is already a rendered spell; Hold Person illustrates the next-batch
integration risk. This does not invalidate the working Sleep/Web/Fireball demos.

**Smallest repair:** route actual targeting distances through the existing origin
seam. Check discovery and execution together. Preserve each spell's eligibility,
range and observation rules, operator attribution and device sustain ownership.
Do not create per-cannon spell implementations or grant the operator extra sight.
Only primary target-range measurement belongs to this correction. Chain jumps,
auras and attached-zone distances can legitimately use different origins; a global
textual replacement of caster-distance calls would introduce new defects.

Evidence: `backend_probe.py`, `backend-probe.json`.

### 3. Media selection still depends on importer execution order

`devtools/import_cantrip_media.py:18` starts a new whole asset list. Lines 25–40
rebuild every delivered phase as impact-only; line 47 replaces the catalog.
The separate `import_projectile_media` path preserves other entries, but the
ordinary bundle importer does not preserve that later selected replacement.

**Reproduction:** import the retained real `cantrips-review` source into a temporary
copy of the current cantrip metadata. Poison Spray changes from travel+impact
to impact-only. The canonical recipe bytes are unchanged, yet compiling the
currently selected spell raises `travel: asset ... has no travel phase`.

This is not the former cross-spell recipe-generation problem; most new tools
correctly preserve recipes. It demonstrates why preserving JSON recipe bytes
alone is insufficient: media revisions, phase registration and selected storage
are also part of effective authoring.

**Smallest repair:** make the selected media inputs explicit and reimport those
inputs, preserving unrelated entries. The retired bundle/replacement sequence
must not silently downgrade a selected asset. Reuse existing manifests/bindings;
no source hashes, general build orchestrator or game-startup asset validation.
Test the real ordinary-import/replacement sequence, not only replacement twice.

Evidence: `import_probe.py`, `import_probe.log`. Live repository assets were not
overwritten; the reproduced failure exists only in the temporary output.

### 4. Older native archives fail on newly added optional facts

`game/event_record.py:105` treats every serialized model field as required, then
removes exceptions through the separate `ADDITIVE_FIELDS` list at line 61.
`temporary_hit_points_grant` and `resolved_speed_feet` were not added there.

**Reproduction:** retained native archives for Thunderwave, invisibility, a
device volley and mixed body residues reject those missing fields. The matching
`player-v1` inputs all still decode. This is specifically compatibility of the
native-v2 recording format and older inputs that rely on its decoder, not a
failure of all public player replay.

**Smallest repair:** admit those historically absent facts as unknown/`None` and
preserve the old interpretation. Do not invent a grant or resolved movement speed,
regenerate the encounter, remove causal/observation requirements, or blindly apply
every model default. Ensure one additive native fact does not silently invalidate
the old recordings used to review the game.

Evidence: `backend_probe.py`, `backend-probe.json`; all four corresponding public
inputs decoded with their original one/three/nine/thirty-three lineages.

### 5. The active coordinate contract contradicts the restored Fire Bolt

`game/data/PRESENTATION_CONTRACT.md:113` says Fire Bolt uses measured Attack5
sockets and the common body target. Its selected recipe actually retains the
approved original tile-center/canvas convention, with no source sockets and a
target forward offset of -16. The recovery status correctly says the human
rejected normalization and the original authored result was restored.

This is an actionable documentation defect: a future adapter or cleanup following
the contract can repeat the regression. Correct the contract to describe the
selected behavior; do not change the recipe to make the prose true. Tuned numbers
and the bounded legacy registration convention are legitimate authoring.

### 6. Verification still mixes supported gameplay and retired consumers

A plain `pytest tests/game tests/engine` cannot collect because five test modules
import removed catalog types or the retired server's old senses path. They are
listed in `tests.log`. Some assertions inside those modules may still cover
active behavior and need migration. This is not a newly discovered VFX runtime
dependency, and those entire modules should not be discarded without inspection.

The existing six expected failures concern real raised-terrain occlusion in jump
and forced movement. They remain known visual defects, not evidence of new spell
branching. They should have an explicit work item rather than disappear behind
another selected test count.

The broader collected run and its failure classification are recorded below.
Tests must distinguish current behavior from obsolete early-slice assumptions;
the downing rejection above is the clearest example. Do not blanket-delete tests,
relax assertions or restore retired systems just to make a command green.

The collected run finished with **52 failed, 2,825 passed and six expected
failures** in 1,000.49 seconds. These 52 failures are not 52 demonstrated runtime
bugs. Source inspection and disposable probes trace them to superseded assertions
or stale fixture construction as follows. They remain failures in the repository:
the diagnostic probes did not edit tests and do not make the suite green.

| Failing cases | Diagnosis and required test repair |
| --- | --- |
| 28 area/door occlusion | The test builds masks from old `stone_door_frame` and binary `wood_door_open/closed` art; production submits the selected smooth-door bank. Wall-only cases pass. Representative actual-raster probes found zero overwritten current-door solid pixels and zero changed truly empty blocked pixels. Use the selected geometry while preserving exact foreground protection, exposed receiving-face and open-passage assertions; do not relax tolerances or change masking to suit retired art. |
| 1 app smoke | Three exact frame/leaf draw lists and an old treatment label fail. A disposable evaluation reached all 56 assertions: the other disclosure, memory, light, water and locality checks passed. Assert the selected door's native state and visible frames rather than the number of depth-split drawing commands. |
| 1 Magic Missile source contract | The test demands unchanged original orientation and source/target anchors. The selected recipe has documented tangent and attachment corrections. All remaining assertions pass when those three expectations reflect the current selected authoring. Preserve the media import and choreography invariants; do not restore the visually rejected/incorrect old values. |
| 1 lethal combat history | The test takes the first `SpatialChangeEvent`, which now includes the injury's legitimate blood residue before death. Selecting the actual death child makes every remaining lineage, disclosure, historical animation and reset assertion pass. Keep checking causal parentage; identify the consequence being tested. |
| 1 legacy occupancy replay | The synthetic legacy builder recursively deletes every `occupancy_layer`, including the newer required `BodyReleaseResult` payload. That manufactures a record which predates layers but contains a later body-release schema. Leaving that unrelated payload intact makes the entire unknown-layer replay contract pass. Scope legacy fixture conversion to the historical actor/movement/spatial fields. This is distinct from the real archived-field incompatibility in finding 4. |
| 16 cold-world initialization | An exact field-name tuple predates tile `residues`. Extend the retained-world value contract to include residues; keep cold-state equality and event chronology. |
| 1 rich entity birth | Frozen field ordering and count predate occupancy and temporary-HP grant facts. Test the complete semantic birth value, including these facts, without freezing incidental model ordering. |
| 1 runtime reset | Reset clears the prior generation; rebuilding the grid legitimately emits twelve new tile completion facts. Check those fresh facts and the absence of old identities instead of requiring an empty event queue after new world creation. |
| 1 spike identity | The entire tile condition dictionary is compared to the trap alone, despite an injury now legitimately leaving blood. Preserve the trap's UUID, footprint and single-handler assertions while checking coexisting residue. |
| 1 forced movement | First entry activates the spike state, so damage descends through that state change; later raised-spike damage is a direct entry child. Check actual causal descent and ordering. Distance, movement cost, HP and combat-log assertions already pass. |

For all 20 engine cases and the three non-door game cases above, disposable
in-memory expectation changes allowed every remaining original assertion to
execute and pass. These are diagnosis aids, not proposed blanket expectation
updates. Evidence is in `engine-failure-classification.log`,
`test-contract-probe.log` and their scripts; door evidence came from the actual
sprites submitted by `compose_area`, not from accepting the failed old masks.
The original broad log remains `collected-tests.log`.

## What is working architecturally

| Area | Actual owner and judgment |
| --- | --- |
| Spell body, projectile and finite local media | Selected Studio-derived records plus shared compile/sample/draw capabilities; no spell-name executor chain found. |
| Reactions, repeated targets, child spells/attacks | Retained causal identities and shared lineage joins; separate events are not independently flattened into animations. |
| Events and player state | Public projection owns disclosure; initial state and updates come from records; ordinary playback does not read a live GridMap or Entity registry. |
| Sleep, buffs and temporary-HP visuals | Existing condition/grant membership and historical presentation lifetimes; the art is not the condition's mechanical owner. |
| Haste and jump | Native resolved movement facts and authored body/media rates; one jump traversal and prelaunch reactions remain shared semantics. |
| Devices | Ordinary item health/destruction, spell origin and concentration ownership; independent device art/muzzle data and selected spell. Validator adoption is incomplete as described above. |
| Traps, plates, doors and portals | Native state, grounded contact, typed consequences and independently disclosed endpoints; art follows state. Their distinct physical behavior justifies shared capability code. |
| Blood and other residues | Native material/receiving-region state plus authored particle/decal media. Blood-specific responses follow the approved blood-only handoff; they are not hidden spell executors. |
| Assets and runtime work | Demand-loaded media and bounded caches; no source/asset SHA audit or per-frame event reserialization found in the inspected presentation path. |
| Future TS reuse | JSON records and explicit execution semantics are reusable; the old unextended NeuroStudio executor is not already compatible with every new capability. No TS/Godot runtime is required by the game. |

The exception paths that do exist should be judged by ownership. A trap applying
poison or a spell having a particular save is a native mechanic, not automatically
slop. Sprite registration, a phase-specific rotation flag and a critical dagger
pose are authored choices. Conversely, a loader/importer silently changing a
chosen media phase is an ownership problem even without a spell-name branch.

Typed fact reduction is necessarily implemented in shared code: health, item
location, condition membership and spatial changes do not all mean the same
operation. Data-driven presentation means new content selects existing meaningful
capabilities without another spell-specific reducer or renderer. It does not
require making those core state transitions an interpreted JSON rules language.

## Scale and maintenance pressure

The current initialized view has 40 selected catalog spells, one Ice Knife child
recipe and one Hellish Rebuke action alias: 42 draft keys, not 42 distinct spells.
It lists 111 media records, 144 condition recipes and 75 catalog spells without a
selected cast draft. That does not mean their native outcomes are unrendered.
Five inherited condition bindings remain partial (wings and four weapon-coating
appearances); the user-accepted potion source strips are separately omitted.
None of the selected spell recipes enables the dormant area-sprite or extra
recovery track. Their mere presence in the source schema is not unfinished work.

Since the clean checkpoint, the selected working-tree areas contain roughly
7,289 net added Python lines outside tests, 11,740 net test lines, and 96,557 net
JSON lines (including untracked files; excluding media). Counts are context, not
a quality score. New capabilities and delivered frame/page metadata account for
much of the growth; saying the entire diff is assets would be inaccurate.

`game/choreography.py` is now about 1,590 lines and `animation.py` about 1,395.
Capability binding, child joins, activity selection and drawing have parallel
lists that require coordinated edits. There is maintenance pressure here.
Extract a coherent existing responsibility when a concrete change needs it;
do not replace explicit composition with an interpreter, manager hierarchy or
second event registry just to make the top-level file shorter.

Repeated prefix reduction during binding looked suspicious, but measured real
narratives did not establish a performance problem. Under cProfile, complete
binding took 15 ms for repeated missiles (73 events), 24 ms for repeated Fireball
(150), 7 ms for Hellish Rebuke (42) and 13 ms for Haste actions (97). These are
local probes, not frame/render/import timings or a general performance guarantee.
They do not justify another optimization project.

Trap control also repeats concrete mechanism membership in a few dispatch sites.
When adding the next control behavior, keep finite/maintained semantics with the
existing mechanism data rather than extending several class lists. This is a
maintenance observation, not a demonstrated broken current trap or authorization
for a control framework.

The recovery plan has also grown beyond 2,600 lines of chronological status,
including explicitly superseded pending entries below completed work. Keep a
short current status and next-work section, linking the existing implementation
records for history. This is a documentation consolidation opportunity, not a
reason to reinterpret approved behavior or erase earlier corrections.

One smaller tooling defect: the coverage CLI's default stdout starts with Pygame's
greeting, so direct redirection is not valid JSON unless the environment hides
that prompt. The coverage content itself correctly labels selected bindings
separately from observed execution. Fix output hygiene in the existing command,
not by adding another coverage service.

## Proposed cleanup order

1. **Preserve the effective visual reference.** Keep the committed/working state
   and selected saved inputs. List the current approved output and known defects;
   do not treat every captured picture as approved. Use existing galleries for
   the cases affected by each repair, not a new pixel-diff framework.
   This does not require regenerating a universal baseline or rendering all spells.
2. **Close ordinary projectile/life integration.** Implement finding 1 through
   the current life/damage owners and replace its obsolete test contract. Keep
   presentation contact clocks and native state authority intact.
3. **Finish the existing device-origin contract.** Correct real validators and
   action discovery using the current seam; exercise mage and device variants,
   operator/emitter boundaries and the spells' actual eligibility rules.
4. **Make selected media reimportable.** Correct the cantrip intake path and
   document the current selected delivery. Verify output metadata and unchanged
   authored behavior in a temporary root, then replay the same inputs.
5. **Restore additive archive compatibility.** Repair only the demonstrated
   historical field omissions; directly replay the saved native and public
   fixtures, including old movement and temporary-HP state.
6. **Reconcile contracts and verification.** Correct Fire Bolt's stale prose,
   classify and repair the actual broader test failures, and separate retained
   active-engine tests from genuinely retired server consumers. Keep the known
   terrain defects visible. Tidy the coverage command's JSON output.

These are capability/ownership repairs, not six new systems. Ordinary additional
spells that fit implemented capabilities should continue to require recipes,
media registration and real event examples. A genuinely new rule or presentation
primitive may require shared code; its need must come from that behavior rather
than a desire for universal extensibility. This review does not authorize a new
art batch, rewrite existing spell art, restore potion strips, or implement flight.

Both independent reviewers approved this concrete proposal. Their amendments
are included: preserve the existing bounded references, classify active tests
inside modules with retired imports, and change primary target-range checks
without rewriting legitimate secondary geometry. Neither reviewer found grounds
for a choreography rewrite, generalized controller, or optimization project.
Review findings, rather than the number of reviewers or tests, determine which
changes are justified. Implementation still follows the user's next direction.

## Validation status

- `pyright game`: zero errors/warnings.
- Dependency graph/direction and no late/dynamic-import workaround checks:
  four passed, eighteen unrelated checks deselected.
- Independent native/device/portal/gas selection: 87 passed in 31.59 seconds.
- Complete game+engine collection: five import errors in retired consumers.
- Collected game+engine run excluding exactly those five modules: 2,825 passed,
  52 failed, six expected failures in 1,000.49 seconds; classified above.
- Three concrete probes reproduced findings 1–4 using real actions, saved data
  and the retained art handoff. Passing focused tests do not cover those defects.
- This is a broad active game/engine review, not a claim to have executed every
  manual, architecture, retired-server or browser test in the repository.
