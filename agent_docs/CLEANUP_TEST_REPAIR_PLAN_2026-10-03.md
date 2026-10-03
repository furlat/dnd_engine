# Cleanup repair and complete acceptance plan

Status: draft for independent anti-slop and ECS review. Implementation has not
started. This plan follows the user's request to explain and repair the complete
test situation while independently reviewing the cleanup implementation. It does
not reopen content design, the paused server, artwork production or wall/cloud
compositing.

Baseline: `981079bc0208dbb23f3ccc927347eef77fef4c30` (`pre-cleanup`). The current
uncommitted cleanup is the implementation under review. Preserve both. The
approved architectural direction remains
[the cleanup plan](ANTISLOP_CLEANUP_PLAN_2026-10-03.md); its plan approvals are not
implementation approvals.

## 1. What the failures actually establish

The three full game partitions reported **2,665 passed, 157 failed, 187 errors,
2 xfailed**. Fifty cases subsequently received focused passing checks: 49 result
selectors and one empty-application archive round trip. **294 is the residual
classification from those receipts, not a fresh final suite result.** Unblocking
setup may expose additional assertion failures. No projected passing total is an
acceptance result.

Receipts and the per-case inventory are under
`.runtime/cleanup-20261003/validation/`, particularly
`game-failure-classification.json`. Keep those original receipts unchanged; add a
new disposition/verification report keyed by test ID.

| Remaining game category | Cases | Established cause | Repair step |
| --- | ---: | --- | --- |
| Current world definitions with obsolete asset setup | 179 | Tests exclude authored bundles while full world bindings require their wall media | 2 |
| Review catalog schema/producer mismatch | 86 | The admitted `call-lightning` row has no scenario-union member or producer | 3 |
| Finite condition-media assumptions | 12 | Accepted sustained Blindness/Deafness glyphs replaced the finite fixture some tests borrow | 4 |
| Older native archives | 11 | Decoder requires newly added optional damage/attack fields absent from retained recordings | 5 |
| Completed-body idle clock | 2 | Test compares a finite clip clock with the ordinary scene's presentation clock; investigate as a test-contract mismatch | 4 |
| Stacked condition membership | 2 | Two ordered native condition changes share one presentation timestamp; the test asks to display their intermediate state before that timestamp | 4 |
| Construction formation disclosure | 2 | CREATED is published before wall sections exist in the spatial observation | 7 |

Outside that game tally: full native/AI testing reported **2,342 passed, 4 failed,
2 collection errors**; architecture reported **76 passed, 5 failed**. The four
AI failures are incomplete damage-profile projection. Four architecture failures
are content-evidence/inventory drift. Two progression collection errors and one
architecture failure enter paused server dependencies. The two existing
construction xfails are also retained as work, rather than disappearing from
acceptance.

Independent implementation reviews additionally found issues not caught by this
failure tally. The three implementation reviews all request changes:
[anti-slop](audits/CLEANUP_IMPLEMENTATION_ANTISLOP_REVIEW_2026-10-03.md),
[ECS/import DAG](audits/CLEANUP_IMPLEMENTATION_ECS_REVIEW_2026-10-03.md), and
[events/presentation](audits/CLEANUP_IMPLEMENTATION_EVENT_RENDER_REVIEW_2026-10-03.md).
The mapping below includes every reproduced blocker, deduplicating the legacy
retaliation finding independently reproduced by two reviewers.

| Review finding | Repair |
| --- | --- |
| Anti-slop F1 / events ER1: legacy retaliation ownership | 5 |
| Anti-slop F2: Spike Growth entry ownership/double presentation | 6 |
| Events ER2: unknown-owner temporary HP timing | 6 |
| ECS-1: rejected concentration leaves dependent effect | 8 |
| ECS-2: rejected effects leak owned runtime state | 8 |
| ECS-3: contextual speed reads mutate serialized cache | 8 |
| Events ER3: incomplete admitted authoring export | 9 |

Whether a defect predates the cleanup
is provenance, not a reason to accept it inside the cleanup's promised contract.

## 2. Fix asset setup against today's production assets

**The current installed artwork and bindings are the reference.** No download,
repacking, old NeuroClient restoration or replacement art is required by the
179 failures diagnosed here.

The bounded baseline/current probe establishes that:

- Default `load_animation_data()` succeeds in both source versions.
- `load_animation_data(authored_bundles=())` fails in both because it still reads
  the complete world definitions, then rejects an unregistered wall asset.
- The named `wall.wall_v35_d0_v0.back.hold` bank is registered by the current
  bundle; all 27 referenced files checked for it exist. This is evidence for this
  dependency, not a claim that every private media file has been audited.
- The checked world-bindings hash is identical in both versions. The loader's
  dependency validation predates this cleanup.

Change the fixtures in these eleven modules, grouped by the behavior they test:
`test_animation`, `test_animation_space`, `test_animation_volley`,
`test_tangent_projectiles`, `test_body_lift`, `test_presentation_contract`,
`test_liquid_media_import`, `test_magic_missile_timing`,
`test_attachment_authoring`, `test_authored_projectiles`,
`test_combat_map_draw` under `tests/game`.

1. Normal game, drawing and current binding tests use the production bundle set
   and the real current rigs needed by their actors. Put repeated setup in one
   small shared test helper/fixture. Do not invent a second asset resolver.
2. Geometry, anchor, tangent and timing tests explicitly author their minimal
   typed recipe input when that input is the contract. They may use an existing
   rig/media source, but must not depend on an obsolete production recipe merely
   because its old shape makes an assertion convenient.
3. Actual archive/schema conversion tests retain their historical input. When
   an isolated loader is needed, pass a matching explicit `world_source` using
   the existing API. A minimal test world is not an alternative game asset set.
4. For each changed assertion, record the preserved behavior: contact placement,
   timing, finite lifetime, projectile trajectory, media decoding or production
   dependency admission. Do not replace expected values with sampled output.
5. Correct the misleading loader documentation for `authored_bundles=()`:
   excluding bundles does not select a matching historical world. Preserve
   strict validation of the supplied world and its selected media.

Files: the named tests/shared fixture, `game/animation_data.py` documentation;
existing `game/authoring_conversion.py` validation remains strict. No exception
swallowing, removal of wall bindings, dynamic deletion of unresolved entries or
new production fallback.

Acceptance: full production loading succeeds; an explicitly omitted required
bank still raises a useful admission error; historical conversion checks remain;
all 179 cases execute past setup. Rerun their assertions and classify newly
exposed failures before claiming they pass.

## 3. Make the existing review catalog executable

`devtools/animation_review/catalog.json` admits `call-lightning-area-repeat`, but
`cases.py` has no `CallLightning` scenario variant and `produce.py` has no branch
for it. The native spell and `tests/engine/test_call_lightning_area.py` exist.

Add one typed case and a producer through the existing capture route. Its
recorded public actions must match the catalog's advertised story: initial cast,
three affected occupants resolving their real saves, an outside occupant left
untouched, a later legal strike, and concentration removal revoking the strike.
Reuse native helpers and the existing replay harness; do not implement spell
rules in the producer or write a parallel demonstration.

Acceptance: the whole catalog parses; every scenario kind has a supported
producer; the Call Lightning case captures and replays actual events; one
unrelated existing case still does. Rerun all 86 blocked cases in fourteen game
modules. Do not delete the row, filter the catalog for normal tests or globally
catch validation errors to obtain collection success.

## 4. Repair stale presentation expectations without changing accepted visuals

### Condition media

Files: `tests/game/test_control_condition_sampling.py`,
`test_condition_transition_media.py`, `test_support_condition_rendering.py`.

Integration tests must assert the accepted sustained Blindness/Deafness glyph
lifetime, including removal. Tests of a generic finite response must use an
explicit finite recipe/media fixture, rather than borrowing the now-empty
Blinded application. Preserve the positive response and expiry checks; do not
delete finite-media coverage or change production glyphs to satisfy old tests.

### Completed-body clock

`test_lifecycle_playback.py` passes both elapsed time and `presentation_ms =
elapsed + 5000`, then demands the finite clip's Idle frame even after completion.
`game/body_presentation.py` explicitly rejoins the scene's ambient idle clock at
completion. A bounded probe with the test's actual goblin rig confirmed that the
only differences at the three tested times are completed Idle frames: attack
8 versus scene 7, cast 2 versus scene 1. Both scene values exactly match ambient
sampling at the supplied presentation time.

During delivery, retain exact authored contact/injury/death timing. At completion,
compare Idle against ordinary scene sampling at the same presentation time, and
retain exactly-one-body, settled facing, death pose and HP assertions. If a
finite frame also differs, treat that separately as a renderer defect. Do not
freeze or reset ambient idle merely to satisfy this comparison.

### Simultaneous condition commits

In the real stacked Guidance recording, Concentrating application and its link
update share the 583.333ms milestone. The second event's native before-state
already includes Concentrating; it cannot be expected before that shared visual
milestone. Group assertions by recipient and timestamp: just before, use the
first ordered commit's before-membership; at the milestone, use the final
ordered commit's after-membership. Keep every event and its source order.

Check both `sample_choreography` membership and condition appearance sampling,
including seek backwards and removal at a shared timestamp. If appearance
sampling exposes an intermediate state early, fix the existing shared sampler
for the whole same-time group. Do not introduce epsilon delays, extra condition
events or a concentration-only timing rule.

Acceptance: all 16 cases in these three categories pass for their observable
contract, with no modification to artwork or accepted condition semantics.

## 5. Repair recorded-event compatibility and causal identity

### Additive fields in old native recordings

Files: `game/event_record.py`, `game/recording_compat.py`, existing archive tests
`tests/game/test_recorded_history.py` and `test_device_destruction.py`.

Extend only the named input compatibility migration for omitted
`TakeDamageEvent.effect_origin`, `AttackEvent.attack_is_magical` and
`AttackEvent.projectile_deflection_position`. Preserve recorded omission metadata
and round-trip omission. Missing optional origin/deflection means unknown/none;
it does not authorize looking up live engine state or inventing a magical-attack
fact. Preserve immutable fixture bytes. Required IDs and malformed results must
still reject, and current producers must supply current typed facts.

### Do not infer resolution identity from an immediate event parent alone

The implementation reviewers reproduced a legacy Fire Shield counterexample:
retaliation is directly parented to the incoming AttackEvent, but has a different
resolution. Both native and player migrations currently guess that the parent's
resolution owns every direct damage child. That merges incoming and retaliatory
results.

Use only evidence actually present in the retained format to recover identity.
Where a known archive version explicitly carries an unambiguous result link,
convert it at the input boundary. Parent proximity, damage type, target/time or
the chosen animation recipe are not proof. Ambiguous legacy damage gets an exact
diagnostic and the source recording is preserved, as the approved cleanup plan
requires. Missing historical proof is distinct from an explicit current-schema
unknown cause, which remains supported by step 6. Never overwrite explicit
current references. Share the rule at the existing
compatibility boundary instead of making native and player guesses diverge.

Acceptance: current Fire Shield keeps distinct incoming/retaliatory IDs after
round trip; an old recording without sufficient proof diagnoses the precise
ambiguity instead of inventing equality;
ordinary legacy results still reduce to the same HP/conditions; malformed
required fields reject; the eleven archive failures and prior compatibility
regressions pass. Include multi-result attacks and hidden causes.

## 6. Schedule all committed damage at its authored milestone

### Persistent exposure must own its result

Files: the existing SpikeGrowthZone entry handler in
`dnd/spells/transmutation.py`, the existing `receive_damage` contract, and native
forced-movement/public replay tests.

The anti-slop reviewer reproduced a Thunderwave push through two Spike Growth
cells: native damage is 2 thunder + 2 piercing + 2 piercing, but both entries
inherit Thunderwave's resolution. The cast cue aggregates 6 damage while both
2-damage entry packets also receive standalone cues. The native damage total is
correct; result ownership and presentation are wrong.

Mark the existing entry damage request `independent_resolution=True` and retain
the field's existing instance origin in `effect_origin`. Keep the movement/spell
as trigger ancestry. Use the already introduced contract; add no new event,
effect-name exclusion, executor or damage rule. Check the other existing
persistent-exposure producers against this same ownership boundary; any omitted
writer belongs in the same migration, without expanding spell mechanics.

Acceptance: the real failed-save two-entry Thunderwave push produces one
2-damage cast application and two independently owned 2-damage entry cues.
Every result is presented once at its own milestone, and no cast HP snapshot
includes later entry damage. Ordinary Move through the same field also gives
each exposure its own resolution and correct retained field origin. Native
packet amounts, movement and saves remain unchanged; replay/seek agree.

### Unknown causal ownership must not bypass committed HP scheduling

Files: `game/choreography.py`, `game/damage.py`, result-contract/replay tests.

The event reviewer reproduced a visible target taking 7 damage from an
undisclosed cause: 40 normal HP + 5 temporary HP. With damage `numberFrame=3`,
the authored milestone is 250ms. Temporary HP currently disappears at 0ms while
the normal HP overlay waits until 250ms. `result_placements` excludes damage
whose permitted `resolution_ref` is absent even though `bind_damage` supports
unknown ownership.

Populate committed result timing from the bound damage results, including
unknown-owner results, using their event/result identity. The same scheduled
commit must drive normal HP, temporary HP, injury and feedback. Do not invent a
hidden action owner, disclose its source, delay native damage or add a second
temporary-HP scheduler.

Acceptance: at 0ms and 249.999ms the recipient remains 40+5; at 250ms it becomes
38+0. Sampling and seek agree; multiple packets retain exact order; known and
unknown causes share the contract; private source details remain undisclosed.

## 7. Correct construction publication and section targeting

Files: `dnd/spells/wall_constructions.py`, existing activation commit boundary in
`dnd/spatial/area_conditions.py`, existing typed attack/spatial query plumbing,
`tests/game/test_construction_presentation.py` and native wall tests.

The wall's CREATED observation currently runs before its sections are placed or
in `zone.sections`, so the observation contains no formation. Later SEEN cannot
stand in for the missing committed formation. Keep preflight before mutation;
commit the admitted sections and the owner's section data inside the existing
activation boundary before publishing CREATED. Cancellation before commit must
leave neither objects nor a live field. Do not seed unplaced objects for
observers, emit an extra synthetic creation, or introduce a transaction engine.

Two existing strict xfails also show a section being blocked by its own field
when attacked. Trace and carry the existing terminal target identity through the
ordinary Attack spatial query. Exempt only the targeted terminal provider;
intervening sections still block. Remove each xfail only after its real public
attack succeeds with the intended action budget and destruction outcome.

Acceptance: observers receive one formation with committed section positions;
damage/break/removal follow existing order; hostile observers do not gain hidden
sections; a section can be attacked without attacking through another section;
Ice's accepted 120HP dome pool, Force rules and concentration cleanup remain.
No wall geometry, cloud mask, VFX retiming or new artwork is part of this fix.

## 8. Close native ownership and read-purity review blockers

### Rejected concentration and provisional condition state

Files: `dnd/actions.py` / the existing `SpellAction` ownership helper,
`dnd/core/base_conditions.py`, affected effects in spell-school modules.

The reviewer reproduced a rejected Concentrating application followed by Fly
remaining active and a `KeyError`. Reuse `BaseBlock.add_condition`'s existing
`required_condition` and prepared-removal commit path for paired child/sustainer
admission. `Entity.add_condition` currently overrides the method without that
parameter: share the existing membership/replacement commit part while keeping
Entity's immunity, saving throw, names and provenance preparation. Do not call
the base implementation to bypass those Entity checks or copy its transaction
body into the spell.

Prepare the dependent effect and required concentration through that existing
boundary; commit replacement only after both admissions and required removals
succeed. Simply calling `ensure_concentration` earlier is insufficient: it can
destroy the old owner's children before the new child rejects. Failure preserves
the previous owner/children and rolls back only the new provisional ownership.
Set `cast_concentrating_uuid` and link the child only to the exact admitted UUID;
an older condition found by the same name is not the newly admitted owner.
Retain the existing same-cast owner reuse and item sustainer capacity semantics.
A failed owner admission leaves no new Fly speed or child condition and follows
the existing action cancellation result. No new transaction framework is needed.

Shillelagh's cancelled application leaves the staff d8/magical with an override.
Produce Flame/Fire Shield were also reproduced leaking their light and
granted-action state. Route provisional state through the existing
condition-owned release hook on failed admission, as well as ordinary removal.
Make release safe once per owned instance. Do not invent a second condition
lifecycle or let one source remove another source's weapon modifiers/grants.

Acceptance: public casts with admission veto at the supported phases leave
equipment, movement, light and granted actions unchanged; successful casts and
replacement/expiry still work; a cancelled source does not remove an unrelated
accepted effect. Cover failed child admission, failed sustainer admission,
failed replacement and vetoed removal with an already active owner and children.
Preserve committed action cost and completed item releases;
this is not an ancestry-wide rollback/refund mechanism. Verify all six retained
spells and three powered items at their
relevant ownership boundary, rather than copying a test for every class.

### Speed reads must not mutate authoritative serialized state

Files: `dnd/blocks/action_economy.py`, existing value/modifier evaluation in
`dnd/core/values.py` and `dnd/core/modifiers.py`.

The reviewer reproduced repeated `current_speed()` reads with plate armor and
STR10: the answer remains 20ft, but serialized contextual modifier caches acquire
new NumericalModifier UUIDs on every read. The cleanup removed a detached copy
without making the underlying evaluation pure.

Separate computed evaluation/cache ownership from authoritative modifier data
within the existing value evaluator. A speed query must resolve modifiers
without writing newly generated results into serialized economy. Keep one
walking/flying budget and expenditure owner. Do not restore a full deep copy on
every read, parallel speed state or a general replacement value framework.

Acceptance: repeated speed queries and action discovery leave serialized state
identical; plate/strength, Haste, Slow, Dash and ground-to-ground Fly still produce
their exact existing budgets; actual equipment/condition changes invalidate or
recompute values correctly. Re-run the movement and attack-economy matrices.

## 9. Complete the promised passive schema export

Files: `game/export_schema.py` and existing passive animation/authoring types;
architecture/round-trip tests.

Export currently covers PlayerSequence, StudioDraftFile and WorldBindingsSource,
but reviewers found the admitted timing vocabulary absent: DamageContext,
DeathContext, AttackRecipe, VoluntaryMovementContext, ConditionRecipe, BodyRig
and RigTables. Add named
schema roots/reachable definitions for the actual existing authoring contract,
including those types. Use their current definitions, not another JSON language
or duplicated TypeScript-oriented model. Document the version and entry points.

Acceptance: representative admitted production authoring validates and round
trips; timing fields required by a second client are present; schema generation
in a fresh process imports no live Entity/EventQueue/content registry/server or
Pygame initialization. This proves contract availability, not a completed TS port.

## 10. Repair AI projection and reconcile content evidence

### AI damage-profile contract: four failures

`dnd/ai/contracts/control.py` and `dnd/ai/runtime/decision_epoch.py` omit
`save_dc`, `save_ability`, `double_on_critical` from the native DamageRollProfile.
Add their passive fields and projection without importing native executors into
AI contracts. Preserve per-packet values and JSON round trip. Do not drop native
fields from the equality test or change tactical scoring to hide missing data.

### Content evidence: four failures

Files: `content_data/ledgers/content_recovery_cr0_evidence.json`,
`tests/architecture/test_content_recovery_cr0_evidence.py`,
`tests/architecture/test_content_recovery_cri_direct_items.py` and their named
current evidence artifacts.

Reconcile exact added/removed IDs and authored owners against accepted work:
178/742 SRD playable/missing counts versus 177/743 in old evidence; eleven
structural owners versus ten (including Wight Multiattack); accepted item and
environment additions and the four rejected arrow admissions removed by cleanup;
the current appearance artifact hash. Preserve historical accepted-commit
evidence and label it historical. Update the current inventory from verified
registrations with explicit deltas. Never regenerate all hashes/counts and call
that verification, or make runtime code depend on an audit ledger.

Acceptance: each current registered entry has its intended owner and admission;
retired entries cannot silently return; provenance points to the correct artifact
revision; the historical baseline remains checkable independently.

## 11. Keep the paused server distinct from the active game

The two progression collection errors import deleted server character modules;
the architecture cold-start probe imports `server.spell_catalog`, which still
requires removed `dnd.core.senses`. They do not establish failure of in-process
character persistence.

Proposed disposition for approval with this plan: preserve server integration
tests in an explicitly named paused-server test lane. These two modules exercise
`server.character_directory_service.CharacterDirectoryService`,
`server.game_directory.repository.GameDirectoryRepository`, HTTP composition and
server deployment. Keep those database/API assertions in that lane; relocating
them does not create a native replacement service.

Active coverage remains at the actual existing boundaries:
`CharacterItemV2` authenticated JSON round trips in
`tests/progression/test_direct_item_durable_and_proficiency.py`,
`CharacterBuild` / `create_character` composition in
`tests/progression/test_direct_character_builds.py`, and native equipment
mutation/transfer tests. Split a server test only if it contains a separately
useful assertion at one of those existing boundaries. These checks are not proof
that the paused server's persistent character directory works.
Point the active catalog cold-start probe at current native bootstrap. Preserve
the old server probe in the paused lane; do not revive server compatibility APIs.

Document explicit active-suite and paused-server commands and file membership.
No `importorskip`, silent collection filtering or mass xfail. A full repository
command must not be described as all green while this lane is paused; report its
known failures separately. Record each old test's disposition and the actual
active durable-record/composition/equipment coverage. No new disk persistence
service, account directory or deployment pipeline is authorized by this plan.

## 12. Execution order and final acceptance

1. Preserve the current source and test receipts; record exact source hashes and
   environment. Incorporate every independent implementation finding and obtain
   independent anti-slop and ECS approval of this repair plan.
2. Repair setup/catalog (steps 2–3). Run those modules and account for every newly
   exposed failure; expand only the concrete contract correction needed.
3. Correct stale expectations (step 4) and recorded input/timing (steps 5–6).
4. Correct native publication/ownership/purity (steps 7–8), then schema export,
   AI projection, evidence and the explicitly approved server-lane disposition
   (steps 9–11). Each implementation fix gets a minimal failing public-boundary
   reproduction before its repair and the appropriate neighboring regression.
5. Run complete active native/AI/progression, architecture and all game tests on
   the final source revision. Partition only for resource control; collect every
   test, prove partitions do not omit or duplicate cases, preserve logs and exact
   commands. Run project typing and import-DAG checks. A source change afterward
   invalidates affected receipts and requires appropriate reruns.
6. Inspect the in-engine visual matrix below from saved public recordings. Use
   existing production art and ordinary gallery, not static mock previews.
7. Independent implementation re-review: anti-slop, ECS/import DAG and
   events/presentation. Record exact reviewed hashes, findings and final verdicts.
   Plan approval never substitutes for these implementation reviews.

### In-engine visual acceptance

Seven clips of three scenes cover those scenes only. Reuse existing recorded
cases where possible; capture a new case only for an uncovered observable path.
For each row, identify the case, observer, exact milestones inspected and result.

| Behavior | What must be visible and correct |
| --- | --- |
| Ordinary creature/object attacks | Actual selected melee/ranged/offhand loadout; contact before HP/feedback; one destruction result; no duplicate object/body |
| Multiple results and retaliation | Incoming hit and Fire Shield retaliation stay distinct; multi-packet/area results commit at their own authored milestones |
| Hidden damage cause | Visible recipient normal and temporary HP change together; no source/location disclosure |
| Condition lifetime | Sustained glyphs apply/remove; simultaneous updates settle once; rejected/expired/replaced effects leave no stale appearance |
| Movement and interruption | Existing opportunity/death/reaction playback, ground-to-ground Fly and normal idle resume; camera rotation and seeking do not create duplicate bodies |
| Walls/clouds and construction | Preserve accepted movement, open-edge/wall/Globe visuals; formation precedes its damage; section break/removal matches native state |
| Items/powered equipment | Coating remains on the actual held/ground/transferred item; charges consume/recharge once; cancelled use has no stale grant |
| Replay independence | Public bytes replay and seek without live rules/content lookups; paired observers preserve different permitted facts |

Use the four existing camera corners where occlusion/placement matters and paired
observers where knowledge differs. Visual checks do not replace the full attack
economy matrix (Extra Attack × Haste × Action Surge × Slow plus offhand/Frenzy/
opportunity attacks) or native ownership tests. No new art, signatures, mechanics
or general scenario revamp is authorized by this acceptance work.

### Completion report

Publish final source hashes, exact active-suite totals, every remaining paused
test by ID, complete failure-inventory dispositions, visual case evidence and
independent verdicts. Any unresolved active engine/event defect means incomplete,
even if it predates the cleanup. Any new product decision is brought to the user
with the exact conflict, not resolved by silently dropping coverage or adding
rules. No claim of full integrity is supported by focused checks alone.
