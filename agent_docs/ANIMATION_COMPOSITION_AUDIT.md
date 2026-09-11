# Animation composition audit

2026-09-11, `codex/recovery-design` working tree. This is a coverage record for
the active recovery plan, not a replacement plan or a mechanics repair backlog.
It compares the current Python code with the original source at
`/home/tommaso/Dev/NeuroClient/app`.

## Event recording contract correction — September 11

**Working-tree implementation note:** the audit below describes `f6a0a1a`.
The repair now preserves concrete passive event values, consumes saved inputs
in the gallery, records native weapon stance, emits initial sensory events,
and admits actors from earlier native facts at their actual observation.
Version 2 stores initialization events and later complete lineages; it derives
the starting state through the ordinary reducer. All 72 saved-input replays
passed with identical video/input bytes and matching gameplay state. Use the
active unit in [RECOVERY_PLAN](../RECOVERY_PLAN.md) for measured checks and the
explicit process-local diagnostic hash difference.

Two boundaries remain distinct from those implemented checks. The retained local
archive includes objective diagnostics and foreign sensory records, so it is not
yet a player transmission payload. Also, a native actor moving from outside the
view into it is rejected by the existing known-participant capture gate. The
reproduction uses observer `(0, 3)` and an unseen actor moving `(11, 3)` →
`(10, 3)` through its discovered action; capture raises the existing identified-
participant limitation before binding. Observer movement toward an unseen actor
and later deployment into view are accepted and covered. Do not describe those
two accepted cases as complete partial-visibility support or loosen subjectivity
to admit the rejected case.

### Implemented recording boundary

- `game/event_record.py` uses the original concrete `wire_type` principle and
  existing event schemas. It explicitly retains the projected log, observation
  grants and effective handler presentation data excluded from native dumps.
  Missing recorded fields are rejected instead of gaining fresh identities or
  ambient defaults. The supported set is the retained event families used by
  this presentation, not arbitrary executable engine object graphs.
- `PASSIVE_EVENT_REPLAY` is a validation context in the native dependency leaf.
  Event, action, object and dice construction retain their normal behavior for
  mechanics; passive validation skips registration and ambient inheritance.
  This avoids a duplicate generated event model or a runtime class importer.
- `game/replay.py` records the actual setup interval before the producer closes
  its runtime. World construction, observer composition, observed actor
  admissions, initial senses and any real pre-clip actions rebuild the baseline.
  Neither a materialized `before` value nor a live sensory/equipment handoff is
  a required replay input. The encounter startup uses the same reducer path.
- `game/actor_facts.py` shares one after-value fold between recorded history at
  capture and the presentation reducer. The native equipment owner publishes
  its selected active set; the client does not repeat reconciliation rules.
  Actor admission uses current recorded HP/equipment and enters the displayed
  history at its actual observation, even when latest has advanced further.
- Equipment gestures preserve NeuroClient's authored commit-frame meaning.
  Native sword removal selects the surviving bow at that point; same-set item
  replacements settle membership at the existing completion boundary. Binding
  and sampling use the same historical head and imported Studio data.

A final fidelity comparison found that header capture still used normal Event
construction: a pre-encounter condition with no turn acquired the turn active
during capture. The real `movement_with_paralysis(17)` regression failed before
the fix and passes with the existing passive validation context. Metadata is
compared against original native versions, not just against another copy of
the recording. Fourteen affected inputs were replaced; the other 58 remained
unchanged. The final run `20260911T175347Z-ca915d` replayed all 72 with native
production/bootstrap unavailable and empty EventQueue/entities. Its 6,561
four-view frames and all input/provenance bytes match the corresponding source
captures. Fourteen raw initial diagnostics differ only in the known
process-local `sense_modes_hash`; semantic state, timelines and recorded facts
match without any array-order normalization. Raw and semantic comparison
reports are retained separately in the run's `inspection` directory.

The sections below preserve the original audit against `f6a0a1a`. Present-tense
failure descriptions there refer to that checkpoint, not the corrected working
tree. The remaining entering-view and outgoing-projection section describes
current limits.

Audit of `f6a0a1a` against recovery base `16a6bfe`, following the user's rejection
of serialization and later actor discovery as optional future work. The
[complaint record](USER_COMPLAINTS.md) preserves those requirements separately
from these findings. This section qualifies earlier references below to retained
replay and portable trace data. No runtime code was changed during the audit.

### The acceptance contract was bypassed

The user requires native sequences to be generated once and saved, then replayed
through Python reduction and rendering without rerunning the game. The current
implementation proves a weaker boundary:

1. `devtools/animation_review/record.py:35` calls `produce(case)` to run the native
   scenario and obtain Python objects.
2. It exports those objects through `STATE` and `LINEAGE` TypeAdapters, then
   continues reducing and rendering the original objects. The export is never
   read back to provide playback input.
3. `devtools/animation_review/__main__.py` implements `--review` by extracting
   selected case IDs and invoking the producers again. It does not replay the
   selected trace.
4. `tests/game/test_animation_review.py` checks the produced videos and JSON
   evidence. The retained-history tests reset the engine while keeping the
   original Python values. Neither establishes disk-to-reducer equivalence.

This is a missing required path in the recovery implementation. A successful
gallery run cannot certify it. The exporter and its tests first appear in
`58b0946`; later gameplay coverage continued using that same boundary.

### Actual failures and their attribution

| Finding | Source and attribution |
| --- | --- |
| Baseline JSON does not decode through its declared adapter | `PresentationTarget` contains coordinate-keyed indexes. Their JSON keys become strings, while the adapter expects tuples. These indexes are a read model, not a verified event archive. |
| Lineage decoding loses concrete event fields | `CompletedLineage.root` and `.events` are annotated with base `Event`. Exporting with `serialize_as_any=True` writes subclass fields; validating that JSON through the same declared adapter reconstructs base Events. There is no concrete decoder in this new path. |
| Turn identity and projected logs disappear | The in-memory reducer consumes retained identity grants; the encounter UI consumes retained projected logs. Native fields are marked `exclude=True`, so this exporter drops them. Those exclusions predate `16a6bfe`; the new consumer/exporter combination failed to preserve the information it needs. |
| Reading the world event can register it | Startup keeps the native world's `use_register=True`. Native Event construction registers unless opted out. The default and constructor behavior predate recovery; using native construction as passive archive ingestion is the new boundary mistake. |
| Later actor admission is absent | `seed_actors` initializes a chosen startup roster. `reduce_lineage` updates existing actors but has no birth/discovery admission path. `scene_actors` can only draw those indexed actors. The user rejects this as a sufficient game design. |
| Active weapon state is partly handed over separately | Native `Equipment.active_weapon_set` and its activation/reconciliation logic already exist. Startup passes a live map of those values to `seed_actors`; attacks update the retained set from their slot. General recorded initial/transition coverage is unfinished. |

The weapon gap was reproduced through public mechanics: an actor equipped with
a shortsword in MELEE_MAIN and a longbow in RANGED_MAIN starts in MELEE. After
`actor.unequip_item(MELEE_MAIN)`, native equipment correctly selects RANGED.
The resulting WeaponUnequipEvent and ItemLocationStateEvent remove the sword
from the retained equipment, but the retained active set remains MELEE.
`EntityCreatedEvent` lacks the initial active set, and the equipment/location
events lack its reconciliation after-value, already at `16a6bfe`. Recording the
existing owner's result is required; the client must not reproduce that rule.

The diff of `dnd/core/events.py` from `16a6bfe` changes Event inheritance from
BaseObject to BaseModel, preserves the inherited fields/defaults, removes
duplicate BaseObject registration, and keeps sensory validation rejecting
runtime Events. It does **not** introduce the grant/log serialization exclusions
or remove active weapon state. `dnd/actions.py`, `dnd/blocks/equipment.py`,
`dnd/core/base_conditions.py`, `dnd/blocks/base_item.py`, `dnd/core/item_types.py`
and `dnd/entity.py` have no diff from that baseline. This attributes the observed
losses; it does not certify every native event for arbitrary object archival.

### Existing source meaning to preserve

`server/event_contract.py:44` already defines a concrete `wire_type` boundary;
`server/timeline_contracts.py:178` receives those values as passive `WireEvent`
records without constructing mechanical Events. Objective replay stores those
concrete inputs. Subjective replay stores the exact delivered observer bootstrap
and updates. These are established source designs, not code newly invented by
this audit. Their generated event schema already drifted before `16a6bfe`, so
the old server package is not a drop-in current adapter.

The NeuroClient source at `d274f2d` uses those received subjective values with
independent latest and presentation histories. `stateSync.ts:203` stages newly
admitted actor summaries and visual loadouts before their first transaction.
The earlier server's `build_entity_visual_loadout` captures native active weapon
state, and `diff_subjective_worlds` emits its replacement. These explain why
recorded client input could supply facts that the new Python path currently
hands over locally or omits. Preserve their meaning without reinstating the old
server's orchestration or moving animation authoring into the backend.

Initial sensory capture also predates recovery: `reduce_senses_snapshot` takes
an existing snapshot, and `tests/engine/test_subjective_combat_log_replay.py:850`
explicitly retains initial senses before applying the native sensory events.
`Entity.update_all_entities_senses` can recompute caches without publishing an
event; `game/session.py:90` calls it. Thus this audit does not establish that
recovery deleted an already complete event-only initial bootstrap. The archive
must record the initial observer facts too; replay cannot fetch those values
again from a live Entity or silently omit the initialization boundary.

Existing subjectivity is not being redesigned. Native event-time grants,
observer sensory changes and `project_combat_log` remain the authority. A native
Shove capture contained four sensory updates, two for another observer. The
current reducer ignores foreign updates, but the local capture still includes
them and objective diagnostics. That entire debug capture is therefore not the
player's transmission payload. Completing the integration must apply the
existing objective-to-subjective meaning at the actual outgoing boundary.

### What the isolated replay experiment did establish

A temporary decoder outside the repository restored coordinate indexes and
concrete event types and disabled world registration. Fourteen roots across
Shove/lethal displacement, Fire Bolt and paralysis recovery bound and sampled
with zero live entities and zero EventQueue entries. Shove/lethal and Fire Bolt
after-state summaries matched the recordings. Three recovery turn-identity
summaries differed because the export had lost the observer grants; projected
combat logs were absent too. The temporary decoder used diagnostic class data
and is not an implemented archive reader or a proposed production design.
Scratch reproduction scripts are `/tmp/dnd_transport_audit.py` and
`/tmp/dnd_transport_old_wire_audit.py`; their findings are retained here because
temporary files are not durable project evidence. The latter accepted 36
retained events through the historical wire decoder and rejected 19 for the
preexisting generated-schema drift. No old server was started.

The animation sampler does not require live mechanics. The recorded-input
contract remains unsatisfied, and the missing facts/connections must be repaired
there. Re-running the game is not an acceptable substitute for faithful replay.

### Source study for the remaining entering-view connection

A native actor moving `(11, 3)` → `(10, 3)` with observer `(0, 3)` produces
valid discovery despite the capture rejection described above. The observer
does not identify the mover at root EFFECT, does identify it at Step completion,
has no grant for the origin, and has a destination grant. A causal sensory fact
adds its visual contact at `(10, 3)`. No mechanics repair is indicated.

July's `server/player_replication/mapper.py::_step_geometry_allowed` requires
ownership or the same observer in both endpoint grants. The matching later
server uses the same geometry rule and forms contiguous authorized runs. Thus
this particular entering edge supplies an actor/state update, without a movement
animation revealing its hidden origin. NeuroClient's
`src/render/subjectivePresentationMapper.ts` accepts frames without animation
cues; `src/engine/eventIngestion.ts` commits their state and positions. Its
`src/engine/stateSync.ts` stages newly admitted bodies at disclosed entry anchors
when there is animation. These are connections to reuse, not new subjectivity.

The historical implementations differ: July gates Step identity, while the
later failed mapper gates frozen root-EFFECT identity and its runtime publishes
each committed Step as an observable projection boundary. Do not restore those
Step queues/stores. Our objective remains complete causal lineages and one
historical head. Multiple visible runs within a partially observed movement
need a deliberate reconciliation of that source difference; the one entering
edge does not authorize silently choosing a broader identity rule.

The existing outgoing projection also distinguishes controlled actors' full
equipment from other observed actors' visual loadouts. The current retained
`ActorAdmission.actor.items` contains inventory. Together with objective headers,
world data and foreign sensory rows, this is a concrete reason the local archive
must not yet be sent as a player packet. The private historical fold provides
the required source facts; it does not replace that existing outgoing projection.

The current `objective_rows` also supplies a structural index. Choreography's
`_before_event` needs the first version's source index, not just the terminal
event order. Reduction, subtree extraction and admission timing need each
version's `source_index`, `event_uuid` and `lineage_uuid`. Names, status text and
actor details are diagnostic consumers of that row, not prerequisites for those
operations. Preserve the required index when keeping diagnostics local. Existing
Event parent/ordered-child lineage fields already own the causal graph; another
graph or queue is unnecessary. NeuroClient's graph mapper around2920 and
Studio's cue builder around855 retain parent/ordered-child presentation IDs and
separate presentation order from the source-event causal watermark. Do not
substitute that watermark for Python's version-order index without preserving
entry state and admission ownership.

For supported map/equipment cases, this study found no missing native input for
the original structural projection. World initialization records boundary
geometry and blocking channels; spatial changes record their after-values;
observer events record visibility, light and capabilities. Structural walls
are not necessarily ordinary object contacts, so filtering every object by
contact membership would misapply the original projection. A public door probe
found an existing reducer omission from `16a6bfe`: opening records empty blocking
channels, but the retained object updates only placement and `is_open`. Its
structure remains closed. Current drawing and visibility use the correctly
updated open flag and sensory events, and no current gameplay failure was
reproduced. Apply the already-recorded structure when connecting the offline
structural projection; this is not a missing native mechanic or a prerequisite
for the current clip replay.

References examined without executing the old server:

- Current `server/player_replication/mapper.py`: Step identity around739,
  endpoint geometry around2627.
- `dnd_engine_broken/deprecated/server_deprecated/player_replication/mapper.py`:
  authorized runs around1734, frozen root identity around1961, endpoint geometry
  around3964; `runtime.py` observable Step boundary around1305.
- The same historical `world_projection.py`: perceived identities around245,
  controlled/visual loadouts around288, world/visibility replacements around398.
- NeuroClient `subjectivePresentationMapper.ts` around445,
  `eventIngestion.ts` around415 and `stateSync.ts` around326.

## Forced movement — September 11

The human requested this shared capability after the jump correction at
`48abb31`. Native Shove and ForcedMovement already existed. This unit connects
their complete retained lineages to the same choreography and renderer used
by the encounter and recorder; no native mechanic or world painter changed.

**Original authoring:** NeuroClient `src/render/clips/ShoveClip.ts` starts the
shove body, dispatches children at its contact and joins their completion with
the body. The exact `action.shove` recipe supplies Kick, contact frame 7, speed 1.
`ForcedMoveClip.ts` plays the recipient to its brace, holds that frame over
eased grid motion, resumes the rest of the body and optionally recovers. The
original `actionContextPresentation.json` forced_movement row owns easing,
facing and scales. Studio preview `studioSubjectiveActionFrame.ts` lines 658–674
supplied TakeDamage, brace frame 3, speed 1 and travel 420ms outside that JSON. A small
`forced-movement-profile.json` adapts those exact cue values and records the
original file/revision/hash. Original imported source JSON remains unchanged.
The old server's different speed/brace/distance formula is not the contract
selected here. The runtime needs Python/Pygame and the imported data, with no
TypeScript materialization at playback time.

**Media:** 21 original modular Kick sheets total 2,525,473 bytes. The existing
importer verifies 327 outputs. All imported fixed rigs already supply their
own TakeDamage mapping; no new fixed-rig aliases or invented sprites were
added. A fixed rig lacking a source Kick gesture remains an explicit binding
gap. The gallery exercises a modular source and modular/Goblin recipients.

**Ownership:** two passive cue records join the existing BoundChoreography:
ShoveCue owns source body/contact, ForcedMovementCue owns recipient brace,
actual path, support height and release. The shared sample returns contacts
to the existing scene compositor. No artificial Attack event, extra historical
head, queue, clock, per-spell executor or gameplay decision was introduced.
Original data and detached trace values remain usable by a later TS sampler.

**Spatial effects:** native Entity position is committed before LEFT and
ENTERED publication. Shove's actual direct spatial children define the reached
path, including partial obstruction or an incapacitating endpoint. Inverse
context easing maps those actual cells to presentation times. Children keep
their identities/ancestry and bind at their reached contact; a forced subtree
does not inherit an outer attack's damage ownership. A small shared DamageCue
uses the existing damage primitive for actual unowned TakeDamage descendants,
including their exact applied packet and owned life event. It is connected
only under forced movement in this unit. This deliberately does not inherit
the original client's leaf-only forced-cue assumption, which would drop these
real native descendants.

**Legal and visual positions:** the lethal spike stops at native (2,11), but
the retained last-live sensory contact remains (2,10): death removes visual
contact before the ENTERED completion fact. Existing VisualPosition now also
receives settled choreography contacts. The corpse therefore stays at (2,11)
through death, head release and idle without changing legal/sensory facts.
Living completion keeps current vitals and joins the ordinary idle clock.

The eleven new catalog cases cover full/resisted/fully blocked/partly blocked
shoves; reaction and movement-resource preservation; actual allowed stair
heights; a Goblin recipient; two spike entries (40→35→28HP); lethal first
entry (4→−1HP/DEAD); and the real Telekinesis-granted Move action. Telekinesis's
native cast/grab is established before that recorded action. This validates
reuse outside Shove, not complete casting/delivery coverage for Telekinesis,
Thunderwave, Gust or other producers. These are committed displacements over
native allowed positions, not a new cliff-falling mechanic.

**Explicit visual exception:** the existing terrace painter occludes stair
displacement. At travel midpoint, correct contacts/heights are up (16,22.5),
z 1.5 and down (16,23.5), z 0.5. Visible/opaque body pixels across quadrants 0–3
are up 66/424, 391/588, 278/434, 31/579 and down 1/434, 5/579, 54/424, 93/588. Height and
actual body-surface checks pass separately; two strict expected map-visibility
failures preserve this finding. Both gallery cards carry `known-occlusion`.
This extends the known hill-jump finding; it does not silently approve those
pixels or authorize a terrain redesign.

**Targeted checks:** 139 passed and two strict map-visibility xfails. The
non-overlapping groups contain 27 authoring/source/rig checks (97.96s), 11
native forced histories (10.25s), six standalone damage checks, ten forced
playback checks, 71 prior attack/motion/placement/condition/life/equipment
regressions (126.23s), and 14 recorder/HTTP/encounter/gameplay checks (109.77s).
Changed-file Pyright reports zero errors. This is a targeted validation record,
not a claim that the entire repository's historical test suite is green.

The anti-slop reviewer approved native ancestry, committed-cell timing,
damage/life ownership and reached-corpse settlement. The anti-OOP reviewer
approved passive data and shared sampling, then independently inspected the
encoded four-view success/Goblin/spikes/lethal/Telekinesis contact sheets.
Those selected images show brace/travel/release, native HP and stable corpse
placement; stair visibility remains excluded. The root also inspected the
final-resolution encoded success, lethal and stair contact sheets.

Final run `20260911T022551Z-96e142` passes all **69 recording cases**, with
6,204 four-view frames. All **58 previous videos and encoder-input pixel
sequences are identical** to `20260910T215953Z-b06297`. All eleven new cases
have no binding gaps. Source hash
`816df2efcd36d1e169c1044bebb2ebfa281f48c659ecb6ed2313a6976f38df87`
covers 814 files, all matching the final implementation. The capture records
the pre-commit base and dirty state honestly; completion documentation is
outside its hash scope. `inspection/verification.json` records the exact
comparison, test groups, reviewers and scope limits; sampled images and their
frame indices are alongside it. Gallery HTML and MP4 range requests return
HTTP 200/206.

## Jump correction — September 11

The human rejected the airborne opportunity-reaction hold and requested one
jump animation traversal lasting the whole airtime, including short/reversed
jumps and landing. This supersedes the earlier airborne behavior described in
the historical checkpoints below. The original Studio JSON, body assets,
duration/arc parameters, event ancestry and native mechanics remain the source.

The reproduced defect was a body substitution during flight: Rolling →
Idle/TakeDamage → late Rolling. In an identical actual second-Step history,
the previous code began its reaction at 565ms, grid (3, 1.6706), lift 35.66px.
The corrected timeline begins that complete subtree at 0ms, grid (3, 3), lift
0. Surviving reactions join before a single flight leg; native death/paralysis
produces no flight leg. The sampler accepts the resulting reaction-only head
and keeps its grounded body through release into idle playback.

The uninterrupted water-jump video already traversed frames 0–14 once; no
separate plain-flight wrap was reproduced. Explicit non-looping motion data
now ties the selected rig's frame index to normalized flight progress, keeping
the complete clip within the airtime regardless of distance, camera or Step
count. Four-view checks sample every authored pose from the shared compositor,
inspect the actual distinct layered surfaces, and verify last-frame/landing/
idle boundaries for short, long, reversed, diagonal and elevated jumps.

The native engine still resolves reactions within Steps. A lethal second-Step
reaction can leave the first Step legally committed, so legal (3, 2) and
grounded visual (3, 3) intentionally differ. Existing VisualPosition carries
that presentation pose across head release and subsequent state changes; no
backend rollback or new placement system was introduced. Complete subtrees
retain identities, grants, HP, conditions and action results. Two actual OAs
join sequentially before one flight.

There is a concrete spatial limit: on jump (3, 3)→(1, 1), a reactor at (1, 3)
is in native reach only at the later Step. Playing that subtree at visual launch
puts it beyond melee reach. The `jump-later-reach` card is explicitly tagged
`known-reach-presentation`. It exposes the result without altering native OA
eligibility, relocating the reactor or silently committing a new rules policy.
The previously recorded rear-view hill occlusion remains a separate known
visual exception; the world renderer was not changed.

The anti-OOP reviewer approved existing ECS/data ownership. Its focused
movement/interruption/placement group passed 39 tests (73s), with changed-file
Pyright clean. Review also removed a temporary eager Rolling lookup from the
binder, preserving the established missing-media Idle path for rigs without
that clip. Reaction-context admission still applies only to actual reactions.
The anti-slop reviewer independently approved actual Step ancestry, native
committed prefixes, complete reaction order and the explicit spatial limits.
It performed source/diff review, not a duplicate test run.

Further validation passed 86 checks across attack/motion, condition playback,
body lift, recording and architecture controls, with four strict expected
terrain failures. Three legacy architecture checks failed: the old server
imports missing `dnd.core.senses`, its world contracts violate the cold-leaf
rule, and EquipmentSlot has two reported owners. The implicated source/test
files are byte-equivalent after newline normalization to `7365184`; the
referenced missing module is absent at that commit too. This is source-confirmed
existing debt, not a new baseline-suite run or authorization to revive the old
server. Another 17 encounter/gameplay/condition/life history checks passed.
Combined with the focused 39, these non-overlapping groups contain 142 passing
tests, four expected terrain failures and three unrelated architecture failures.

Encoded video inspection confirms one contiguous Rolling 0–14 sequence for
short/long forward/reverse flights and the one-/two-reaction continuations. The
lethal case has no Rolling frame. Six selected encoded moments per case were
cropped from each of the four camera views to inspect takeoff, rotation, the
final pose, landing or grounded death. These artifacts and the full frame-order
report live in the new run's `inspection/` directory. The independent visual
reviewer also inspected all four views of six encoded contact sheets and found
no new issue within that bounded review. Grounded paralysis pixels were
separately inspected in the final recording.

Final run `20260910T215953Z-b06297` passes all **58 recording cases**, with
5,341 four-view frames. Its 46 unchanged pre-existing videos and input pixel
sequences match `20260910T211349Z-a5d2b1` byte-for-byte. Only the seven intended
jump-reaction/recovery videos differ; five new cards cover short-forward,
long-forward/reverse, two reactions and the explicitly limited later reactor.
All 18 jump heads pass trace checks for grounded prefixes and one contiguous
Rolling 0–14 traversal or no flight when stopped. The complete manifest and
`inspection/verification.json` retain the comparison, test results and visual
limits. The gallery and MP4 byte-range requests return HTTP 200/206.

The capture's source hash is
`bf945f0102d5f5f52cd624f0f6d901acdf23c3acf05875edf6a3c4fcfe36f2c1`
over 785 files. Runtime, data, catalog and test hashes match the final working
implementation. A single README sentence was clarified after capture to say
the gameplay tag **includes the initial** 15 cases; capture provenance is
preserved and that documentation-only difference is explicit in verification.
Plan/audit completion notes are outside the recorder's source hash scope.

## Creatures, equipment and movement — September 10

This unit implements the human's gameplay coverage request. It adds 15 native
histories to the four-camera catalog and connects the existing equipment
primitive to normal encounter/gallery composition. It adds no spell effects.
Final run `20260910T211349Z-a5d2b1` passes all 53 recording cases and contains
4,973 four-view frames. Its 53 encoded videos/input pixel sequences match the
inspected full run exactly, and all 785 source-file hashes match. The plan links
the gallery; `inspection/verification.json` within the run records comparison
and review scope. Hill-jump visual completion remains explicitly excluded.

**What remains portable:** original Studio action/context JSON, exact fixed-rig
JSON, selected sprite bytes and the existing
`content_data/ledgers/neuroclient_authored_item_visuals.json` equipment layers.
The latter already contains render layer, sprite key and tint; Python does not
own another authored wardrobe table. Traces serialize retained native histories
and compiled attack/cast/equipment/movement values. A future TypeScript client
can import those data resources, but must implement/adapt the generic evaluator
and presentation reduction/event binding. Native engine mechanics may remain
in Python behind that frontend. This unit does not create a TS runtime or
replacement schema.

| Coverage | Existing owners used and resulting behavior |
| --- | --- |
| Equipment and wardrobe | Real equip/unequip notifications remain passive. ItemLocation supplies committed membership and native armor class. Existing EquipmentTimeline/NeuroClient context supplies the gesture inside the shared choreography. |
| Same-turn melee then ranged | A real level-5 Fighter spends its action on melee and its granted Extra Attack on the longbow. Original AttackClip activates the selected weapon set on entry; no synthetic switch root or extra delay. |
| Actual item replacement | Original SwitchWeaponClip's frame 4 callback changes stance, not item identity. Same-stance replacement retains old item layers until the gesture/frame settles. Both old/new gear, subsequent Idle and actual longbow pixels are checked in all four views. |
| Ordinary/Haste/bonus Dash movement | Native discovered routes spend 30 or 50 feet. Haste's actual cast establishes the movement baseline; Cunning Action Dash remains a real returned action/condition tree. Extra native distance does not change Studio's authored walk rate. |
| Multi-cell jumps | One original flight duration/arc spans existing Step children. MotionLeg fractions preserve each step's native reaction/commit ancestry. A reaction can pause the second step after the first committed; survival continues and death retains its airborne visual pose. |
| New creatures | Native Dretch, Skeleton Archer and Wolf move/attack/receive hits/die using their own canonical content refs and purchased rigs. The same shared attack/damage/death primitives interpret their rig maps. |

**Asset selection:** 28 original PNGs (2,197,697 bytes) for
`smallscale.demonbeast01`, `smallscale.skeletonarcher05` and
`smallscale.greywolf`. The unchanged fixed-rig importer verifies their archive
members and provenance. Demon/undead cells are 128 px; wolf cells 64 px; all use
15 frames and 8 directions. Only the demon package supplies separate shadow sheets.
The other two bindings are body-only. Vendor named-direction images confirm
undead/wolf row order; demon row order was visually reviewed. FPS/pivots are
explicit adaptations. No empty/truncated selected body frames are accepted.
Thirteen original Ranged4 sheets supply the Fighter's actual longbow; the
existing NeuroClient importer reproduces all 305 outputs. No new art was authored.

**Terrain actually shown:** the legacy mechanical hazard map has water costs
on stone surfaces; the generic elevation proving map has stone stairs outside
the renderer's selected earth stair assembly. Those fixtures do not establish
the requested rendered terrain. Gallery jumps therefore use the existing
`battlefield.visual_vertical_seam`: dry banks (33,28)→(35,26) over actual WATER
at (34,27); lower ground (13,20)↔terrace (14,20); full stairs (16,25)→(16,22).
Native darkvision supplies the existing dark world's visibility. Healthy
clothed actors, actual material/support heights and legal landing are asserted.
Neither the world renderer nor terrain mechanics were changed for these cases.

**Known terrain visual exception:** cameras 0/1 in the hill jumps can lose body
pixels that are physically above the terrace. An attempted flat-floor depth
split was rejected: it altered an established rear-wall pixel result and did
not fix the uphill case. Last-writer instrumentation identified cliff tile
(14,20), `terrain.cliff.w` in camera 0 and `terrain.cliff.n` in camera 1, covering
114/147 protected uphill pixels after the floor-only prototype. The final world
renderer remains unchanged. The focused regression exempts authored pixels
below the floor plane, keeps legitimate lower-ground hiding/front-view controls,
and marks only confirmed rear-view losses as strict expected failures. On the
unchanged renderer, protected losses are 299/324 uphill and 12/1 downhill in
cameras 0/1; cameras 2/3 lose none. The 16-sample regression yields 12 passing
controls and 4 strict expected failures. Eight established wall/cliff pixel
controls also pass after removing the prototype. The hill cards are tagged
`known-occlusion`. Native jump/timeline correctness and passing
recording checks do not claim visual completion of this terrain case.

**Recording correction:** a second-step jump exposed 26 opaque body pixels under
camera 0's header in the small 640×480 review view. Framing now uses the existing
compiled motion envelope plus rig cell/pivot/scale values before recording.
All four cameras retain one fixed focus/zoom. Every recorded frame checks actual
opaque body bounds against the viewport excluding the header. The regression
passes 49 frames, and independent visual review confirms the corrected body.
Retained outfits are acquired in one existing media-loader call. Live encounter
play acquires newly equipped layers at its equipment head using the same cache.

**Dretch scope is partial and explicit:** it composes existing native fiend
facts, elemental resistance, poison/Poisoned immunity, Bite/Claws and configured
Multiattack. The established roster hit-die policy yields 22 HP versus the printed
18. As with the existing Ghoul, LIGHT on the secondary natural weapon permits
the engine's off-hand slot and exposes its bonus attack. Fetid Cloud and
telepathy are absent. Demon Beast 1 is a chosen visual adaptation, not a vendor
claim that the art depicts a Dretch. Gallery attacks are ordinary discovered
attacks; Multiattack mechanics are tested separately and its presentation
sequencing is not claimed here. None of these limits justifies a parallel
monster/equipment rules system in this unit.

**Validation:** dedicated movement 19, equipment 4 and creature-history 3 tests
pass. Existing affected encounter/history/lifecycle/placement regressions pass 96;
equipment/source/rig/lifecycle/import-direction regression group passes 56;
recorder/server/import checks pass 9, plus the new framing regression 1. These
groups overlap. Current content/rig checks pass 67 across the batch and corrected
reruns, including native Dretch 8. The broad changed-file Pyright run reports
three existing `authored_item_builders.py` errors (unused local and two dice
Literal annotations); the exact same three were reproduced against its `ebff88c`
file. Other checked changed Python files report no errors. A separate check of
the unchanged world renderer reports its existing `app.py:629` water-evidence
type error; no renderer edits remain. Anti-slop and
anti-OOP reviews approve the bounded ownership and data reuse, excluding
raised-terrace jump visual completion.

**Historical test boundary:** three CR-0/CR-I audit checks still require frozen
pre-Dretch ledger hashes/669 icon rows or an old importer allowlist. Their
historical artifacts remain unchanged. Current native/materialization/icon and
direct-item boundaries pass after the explicit new content additions. An old
source-coverage test cannot collect because it imports deleted
`dnd.items.armors`; it was not repaired as part of this unit. These results are
not a claim that the entire repository suite is green.

**Still outside coverage:** full nonprojectile spell delivery, forced movement,
general inventory/roster UI and additional optional Studio fields remain the
prior plan's work. Fixed-rig slash media gaps are explicit; unavailable
decorative slash layers do not block native creature body/damage playback.

## Native life transitions and lifecycle feedback — September 10

The next shared capability consumes the seven existing `lifecycle.deathSave`
and `lifecycle.lifeState` JSON rows. Their typed fields remain enabled/text/color;
actual natural rolls and committed life facts select the row. Ordinary
FeedbackTracks supply their original badge style and independent lifetime.
They add no wait to the lineage. Turn banners and encounter result UI remain
unconsumed source context.

The source distinction matters: `subjectivePresentationMapper.ts:2300`
maps mechanical DYING/STABLE to badges only. `createProjectedAnimatedEntity`
initializes those actors as Idle. The animation FSM's `Dying` instead means
playing Die toward frozen Dead. `ReviveClip`/`reviveFromPresentedState` release
that frozen state on a real ALIVE transition, with no authored stand-up clip.
The earlier recovery-body concern below was an incorrect interpretation,
corrected in the plan, tests and gallery description.

An uncovered DEAD transition now contributes one imported Die interval to the
existing choreography. It reuses body duration/sampling, scene media and actor
drawing. Exact life-event UUIDs owned by bound Attack/Cast primitives prevent
another body or join from being added to their existing lethal deliveries.
Mechanical DYING still recovers from TakeDamage to Idle at the original time;
its Dying badge follows the existing child anchor. A native explicit revival
also exposed an actual reducer defect: `revive(hit_points=3)` ended at native
ALIVE/3 but retained ALIVE/0. Consuming the life event's already committed
`normal_hit_points` fixes this without modifying the engine.

The first native recording/tests found a real ordering detail that static
review had missed. `_transition_life_state` commits sensory removal before its
life completion is registered. Reducing up to that completion can therefore
leave the pre-DEAD actor without a current visual contact. Binding the life
cue's geometry at its exact causal parent's entry retains the admitted pose;
HP/life still come from the later pre-transition facts. The existing scene
admission, witnessed-corpse contact and interrupted-movement overlay remain
the owners. No visibility rule or backend ordering changed. Tests explicitly
bind without an optional supplied contact, require a present cue and nonzero
death interval, and check frames 0→1→last and changed death pixels.

Four-corner visual inspection caught a second concrete omission: opportunity
downing briefly displayed the damage packet's intermediate −2 HP, even though
the owned DYING fact and reducer already said 0. BoundAttack now takes HP and
life from that same exact selected life event, at its unchanged HP anchor.
The packet still owns the damage number (6 in this native case). This is no
clamp or whole-lineage final-state lookup. The regression fails on the old
binding and checks HP before/at the authored callback, recovery, completion
and idle, along with unchanged damage feedback. Independent review approved
this value correction against the original mapper/TakeDamageClip contract.

The finite native producer uses real injury, seeded turn-start saves, actual
stabilization/healing and explicit revival, retaining every separate turn and
round root. The eight catalog additions cover ordinary success/failure,
critical failure/recovery, stabilization then healing, death then revival,
paused death while latest is already revived, and opportunity downing. Tests
check native HP/life, real ancestry/grants after teardown, absolute seeking,
one body, four-camera corpse/placement/lift continuity, unchanged lethal
Attack/Cast timing, and actual frozen encoded pixels while latest is ALIVE/3.
Both anti-slop and anti-OOP reviewers approved the source meaning and final
implementation; the final test review approved these acceptance boundaries.

**Validation:** the regression group passes 159 tests in 180.75 s, including
the live paused encounter, encounter completion and required import DAG/direction.
The focused native/healing/paused-death group passes 19 tests in 70.06 s;
after the final HP correction, 45 affected tests pass in 59.78 s. These groups
overlap. Changed-file Pyright is clean. Final gallery
`20260910T192249Z-2eb59a` passes 38/38 at 24 FPS and 1920×1280 (four corners
per frame). Extracted death, corpse, revival, critical recovery and downing
frames and the comparison proof are under the run's `inspection/` directory.
All 679 captured source files match the final implementation. The previous 30
cases retain 29 pixel-identical frame sequences; only healing-dying changes to
include the original Revived badge and its independent tail. The verification
also checks native zero against every shown DYING HP value in walk-downed.
Final four-corner inspection confirmed the corrected 0/4 label, retained
corpse pose and the actual revival's 3/20 result. Automatic passing and this
inspection remain separate from the human's visual approval.

**Remaining scope:** selected nonempty death hiddenSlots/media, healing
body/media, nested healing HP timing and cast DYING/STABLE delivery are still
explicit limits. This unit adds no mechanics, subjectivity rule, queue, clock,
FSM or per-spell executor. The new opportunity fixture also exposes the
existing Goblin slash asset gap; no replacement art is invented.

## Native continuing lifecycle checkpoint — September 10

The six-case unit in `RECOVERY_PLAN.md` passed independent anti-slop and
anti-OOP reviews before implementation and again after implementation. Actual
native histories now continue through initial opportunity paralysis, successful
or failed repeat saves, separate turn/round/expiry roots and a discovered
Disengage followed by Move/Jump. A Dodge control expires on the next native turn.
The exact applied condition UUID tree survives failed saves and is removed by
its real successful-save owner. No mechanics or game renderer changes were
necessary for these cases.

`test_condition_lifecycle_history.py` checks native ancestry, results and
choices after engine reset. `test_condition_lifecycle_playback.py` checks every
root boundary in all four cameras: held contact/support/lift, unchanged body
pixels through unchanged membership, neutral body pixels at removal, original
next-motion duration and legal endpoint. The paused clip asserts both original
memberships while latest has removed them and moved on. Recorder frames now
hash the actual RGB bytes passed to the encoder, so frozen metadata cannot
conceal changing pixels. The existing live paused-encounter test remains the
separate proof that event intake continues independently.

Full run `20260910T175626Z-4e0063` passes 28/28 and preserves every previous case.
Extracted boundary frames are under that run's `inspection/` directory. Visual
inspection confirmed the failed-save gray body, instant original color on
removal, held jump elevation through turns, resumed motion and Dodge expiry.
Focused lifecycle/placement/feedback/live encounter tests: 28 passed in 126.14 s.
Native history/attack/movement group: 32 passed in 20.47 s (overlapping coverage).
Changed-file Pyright: zero errors. Import direction and DAG: two passed.
Only the existing Goblin ranged body/slash gaps occur in the full gallery;
automatic checks and this inspection do not replace the human's visual review.

## Bounded standalone healing extension — September 10

Native `receive_healing` supplies the amount actually restored after the cap,
committed normal/temporary HP and any real life-state child. The new producer
first creates a real injury, then captures the heal in an ordinary encounter
whose startup installs the existing observer computers. It preserves those
grants and closes/resets the engine before playback. The living case requests
20 HP at 13/20 and restores 7; the dying player receives 5 HP and retains the
actual DYING→ALIVE child. No condition-removal tree is invented for healing.

The existing `vital_effect.healing` JSON now has its original typed fields in
Python, including the source-valid zero-duration feedback setting. A passive
HealEvent/anchor record joins the current choreography traversal. The shared
feedback lane reads its capped amount and original `Heal` label, green color
4521796 and 900 ms duration. Default body `none` and empty media add no wait;
the existing immediate head exposes native HP/life after-values at entry, and
the number continues independently. Placement and body lift remain playback
geometry; healing does not relocate the actor.

Original `HealClip.ts` patches HP at entry and `mapHeal` dispatches actual
children. The source then maps DYING/STABLE→ALIVE to ReviveClip and the lifecycle
`Revived` badge. At this checkpoint the badge was unported. **Correction from
the subsequent source review:** mechanical DYING/STABLE correctly sample Idle;
the animation FSM's `Dying` plays Die toward Dead and describes a different
state. ReviveClip releases frozen Dead; it has no authored get-up body. The
old gallery's claimed recovery-body gap was mistaken. The following lifecycle
unit connects the badge and actual dead-to-alive presentation. A heal
inside a bound attack/cast also reports its missing HP-at-entry timing:
anchoring its feedback is not equivalent to implementing nested vital changes.
Nonempty selected healing body/media likewise report their own gaps. This is
standalone healing feedback coverage, not healing-spell delivery or revival of
the dead.

The anti-slop and anti-OOP reviewers approved this bounded connection. The
architecture reviewer corrected three field constraints against the source
validator before acceptance. Native healing plus lifecycle tests: 7 passed in
3.67 s; four healing playback/capture tests passed in 28.70 s. Existing
attack/cast/movement/equipment/feedback group: 120 passed in 54.72 s.
Changed-file Pyright reports zero errors. The broader dependency test module
passes 19 checks, including the required DAG and import direction, and reports
three failures in unchanged checkpoint code: the legacy server imports missing
`dnd.core.senses`, the same import fails the world-contract leaf check, and
the neutral-symbol assertion also matches Studio's `EquipmentSlot` alias in
`game.condition_types`. The relevant test/source files are unchanged from the
human's `58b0946`; this work does not modify those unrelated owners or turn the
legacy server into a Pygame requirement.

Final gallery `20260910T181136Z-be08be` passes **30/30**. Every RGB frame hash
and frame count in the previous 28 cases matches the primary checkpoint run
`20260910T175626Z-4e0063`. The comparison is retained at
`inspection/verification.json` within the final run. Four-corner healing frames
before/at entry and during the decorative tail were inspected: capped amounts,
committed HP and the original green label agree with the trace. The final
gallery reported the pre-existing Goblin ranged media gap and a healing
life-state badge/body gap, whose body interpretation is corrected above.
Both reviewers approved the completed
implementation; automatic passing still leaves visual approval to the human.

## The answer to “is it data driven?”

Partly, and the distinction matters. Authored recipes select clips, source
frames, speeds, anchors, projectile appearance, feedback and condition
appearance. Python still implements the finite primitives and causal dispatch.
Several authored domains remain unsupported. Importing a JSON field does not
mean the renderer executes it.

The original design also used coded primitives. `src/render/types.ts:768`
defines `ParallelIntent`, ordered `SequenceIntent.groups` and a finite
`ClipIntent` union. `AttackClip`, `CastClip`, `TakeDamageClip` and `ConditionClip`
interpret typed data and await their children. Recovering this composition does
not require a new JSON programming language, backend animation fields or a class
hierarchy with one executor per spell.

State reduction is a different responsibility. `game/presentation.py:813`
dispatches on existing event families and applies retained after-values. Damage
packets replace HP, condition facts add/remove a condition UUID, life events
replace life state, senses supplies positions, and turn events supply the
historical actor/round. These are coded protocol semantics, not authored
animation recipes and not a second D&D rules implementation. Original
`sdk/typescript/src/reducer.ts` and `subjectiveJournal.ts` likewise use the same
coded reducer for latest and historical state.

## What now has one owner

| Concern | Current owner and meaning |
| --- | --- |
| Engine rules, condition handlers, reactions, interception and committed movement | Existing engine. The renderer does not decide whether paralysis stops a step. |
| Subjectivity and attachment | Existing grants and sensory facts retained by `capture_lineage`; no party-wide vision union or rewritten disclosure policy. |
| Complete causal identity | `CompletedLineage`, ordinary event/lineage UUIDs, parent/child relationships and objective source indices. A condition sidecar retains passive facts without copying executable conditions. |
| Latest state | `encounter_play.receive` reduces every completed actual root immediately. |
| Historical progression | One pending deque and one active head in `game/encounter_play.py`. Native controller work can progress while that head is paused. Human input requires the corresponding settled displayed boundary. |
| Action/child composition | `game/choreography.py:68`, shared by standalone actions and reactions embedded in Move/Jump. It owns no queue, mutable playback clock or engine queries. |
| Primitive sampling | `animation.py`, `attack.py`, `condition_animation.py`: explicit elapsed time in, passive sample out. |
| Decorative feedback | `feedback.py`: passive number/badge tracks with authored lifetime and frozen launch contact, sampled by the existing presentation clock independently of a completed head. |
| Movement interpolation | `motion.py:70`: actual direct Step children, authored lead/duration/arc, complete reaction groups, then only committed continuation. |
| Rig pixels and condition color | `animation_draw.py`, `condition_draw.py`; the same actor drawer serves idle, movement, attacks and casts. |

The import direction remains presentation facts/data → primitive binding and
sampling → shared composition → movement/application → Pygame adapters. Frozen
records describe plans and samples; they are not entities with their own rule
lifecycles, schedulers or event registries. Pygame is confined to the adapters
and application. No TypeScript runtime is required to play the game.

## What the recursive cut preserves

The source mapper keeps each movement reaction subtree together and in cursor
order (`subjectivePresentationMapper.ts:1243`). `MoveClip.ts:71` and
`JumpClip.ts:142` wait each complete group. `AttackClip.ts:32` dispatches on-hit
children at melee contact; ranged delivery dispatches on arrival, and the
primitive waits both its body and delivery chain. `TakeDamageClip.ts:67`
attaches ordinary child effects at `conditionFrame`; lethal children dispatch
immediately. `CastClip.ts:547` dispatches the actual disclosed effect subtree.

The Python compositor now follows actual child lineages recursively:

- Attack contact or projectile arrival supplies the direct on-hit anchor.
- Each repeated Spell application keeps its own identity and arrival time.
- Nested Attack/Spell roots bind their own subtree. The parent primitive excludes
  their damage, avoiding duplicate ownership of the same consequence.
- TakeDamage descendants use the authored condition frame and impact delay;
  direct attack riders remain contact siblings. The engine's ancestry decides
  which relation applies.
- Condition leaves receive the nearest cast's existing condition delay/feedback
  override, retain actual condition UUID membership, and join real alpha fades.
- Postorder joins include only actual descendants. Cast recovery starts after
  the complete delivery subtree, including a longer condition fade or nested
  action. Release, impact, HP and child anchors are unchanged; only recovery and
  completion move. Attack joins also extend to their complete child subtree.
- A movement reaction holds its subcell position until the whole group ends.
  A failed Step retains its rendered stop position; a committed Step continues.
  Legal state still records the uncommitted Step's origin. This supersedes the
  source origin-restoration behavior following the user's gallery review.
  No visual condition-name predicate substitutes for the committed result.
- Walk and Jump use the same action compositor. Jump retains the interrupted
  curve position/lift, and the shared map adapter converts source pixel lift to
  the current camera scale.

This restores a useful composition boundary. It does not implement every member
of the source `ClipIntent` union or prove a weapon-triggered spell executor
exists in the backend. The native on-hit case uses the existing configured
paralysis rider and real save/condition handlers; it is not a fabricated Hold
Person spell.

## Authored coverage, including explicit limits

| Domain | Data actually consumed | Current boundary |
| --- | --- | --- |
| Cast | Existing materialized Studio JSON, exact semantic binding, body/release, selected prepare/travel/impact, repeated applications, damage and enabled body recovery after children | The selected executor requires projectile delivery without an area. Self/touch/position/area and healing-specific presentation are not implemented by this compiler. Unbound cases retain their actual state and report gaps. |
| Projectile art | Existing sprite asset/phase metadata and CodexFX override bundle; original generated dart/bolt geometry primitives | Unsupported sprite color/orientation/media policies reject explicitly. The current Rune Dart comes from the authored CodexFX bundle. Loading other catalogs is not equivalent to having their art locally. |
| Attack | Existing attack recipe/profile predicates, body clip/speed, contact or release frame, ranged speed/minimum duration/endpoints, trajectory/depth, outcome feedback | Ranged geometry currently implements the source bolt primitive. Body media and hidden-slot profiles are rejected. Attack VFX currently draw a supported slash layer; other selected layers produce media gaps. |
| Per-rig mapping | Explicit body clip/frame/FPS, slots, resources and creature-content mappings in rig data | A missing ranged clip can retain the root rig's authored clock with Idle and an explicit missing-body gap. This is degraded art, not a claim that the creature has a ranged animation. |
| Walk/Jump | Source clips, walk speed/duration, jump duration bounds/arc, pre-reaction lead and badge, actual retained Step endpoints | Walk/jump media and recovery fields are parsed but not executed. Enabled pre-reaction body/media/recovery rejects motion binding. The default imported media/recovery fields are empty/disabled. |
| Damage/life | Retained direct packet HP/life after-values; authored hit/death body, palette, impact delay, flash and number frames | A primitive currently binds one direct damage packet per target application and a single final life transition. Standalone damage/forced movement and broader packet composition still need their respective source primitives. The cast compiler's DYING/STABLE outcome remains outside its selected coverage. |
| Life transitions | Seven original save/life badges; uncovered DEAD plays the imported Die interval, actual revival restores Idle and committed HP | Exact Attack/Cast life UUID ownership preserves their existing timings. Mechanical DYING/STABLE add badges only. Selected nonempty standalone-death hiddenSlots/media remain explicit gaps; turn/result UI is not consumed. |
| Standalone healing | Original healing context, capped native amount, entry HP/life after-values and independent number lifetime; original Revived badge on its real life child | Default empty body/media work through the existing immediate head. Selected healing body/media and nested healing HP timing remain explicit gaps. DYING/STABLE correctly use Idle. |
| Conditions | All 141 original recipe rows, exact behavior identity, composition priority/exclusivity/group limits, alpha, body tint/saturation/brightness, badge text/color/style, application/removal delay | Persistent/transition strips, equipment modifiers and appearance replacements are not executed; nonempty selected fields produce explicit gaps. `state_only` is intentional neutral authoring. Missing rows preserve membership with a gap and no fabricated transition. |
| Condition relationships | Trigger, immunity, suppression, grant and classification metadata remain losslessly parsed | These records do not become a second rules engine. Actual condition events remain authoritative. |

The current local spell selection is **three bound drafts**: Fire Bolt, Acid
Splash and Magic Missile. Fire Bolt and Magic Missile exercise the selected
projectile path; Acid Splash's area delivery is currently rejected. This is not
a complete spell catalog implementation. The copied action recipe file has
**88 rows**, of which the loader selects **five attack recipes**. Three have
selectable variants (`action.attack`, `reaction.opportunity_attack`,
`action.feature.extra_attack`); Frenzied Strike and natural attack have no
variants in that file and therefore do not bind through this selector.

The copied condition document contains 141 rows: 32 `state_only`, 16 with body
color, three with non-neutral alpha, four with equipment modifiers and one with
appearance layers. It currently contains no persistent or transition strips.
Those counts overlap; they describe authoring, not 141 distinct implemented
executors. The strict schema round-trips every original row unchanged.

Condition appearance uses the source composition across current memberships.
Visual recipe deduplication does not collapse actual condition UUIDs. Body color
applies only to the original body/equipment slots. Aura, slash, effect layers and
shadow retain their own color policy. Hit flash overrides the color filter;
condition alpha still applies to the entire actor, including its shadow. The
pixel adapter follows Pixi's exact equal-channel saturation matrix, then tint
and brightness, rather than substituting a luminance approximation. Sources:
`ConditionOverlayController.ts:22,198`, `AnimatedEntity.ts:970`, and the local
Pixi `ColorMatrixFilter.mjs:152,202,496`.

## Source parity corrections validated in this checkpoint

Two review findings were fixed in this same working checkpoint:

1. **Decorative feedback lifetime.** Original `FloatingText.ts:83` returns
   immediately while its fade continues independently. `game/feedback.py` now
   extracts the existing authored number/badge tracks, including the source
   pre-reaction label. The application retains them until their own expiry,
   fixes their launch contact, and filters duplicate feedback from the group
   drawer. A neutral-alpha Dodge badge can survive its immediate causal join;
   fading overlays neither delay player input nor create another action queue.
2. **Cast recovery after longer children.** Original `CastClip.ts:118–137`
   awaits the complete delivery/child chain before movement recovery. The
   compositor now computes descendant joins in postorder and shifts only the
   parent's recovery/completion. The actual Fire Bolt/concentration-removal test
   below validates this timing with recovery enabled and disabled.

Remaining source parity limits are the unsupported domains in the table: shove
reaction groups, enabled walk/jump recovery/media, pre-reaction body/media and
separate turn/action body tracks, plus broader delivery/effect primitives. A
backend weapon-triggered nested cast was not fabricated for this exercise;
recursive nested action ancestry is implemented, but that full mechanical
scenario remains unexercised. These are capability boundaries, not new mechanics
repair prerequisites. Their future implementations should consume existing
source records through the same owners.

## Evidence and review judgment

`tests/game/test_movement_interruptions.py` exercises actual Move and Jump with
a configured longsword opportunity rider: failed save/paralysis, successful
save, miss, death and committed/noncommitted continuation. Its authored-data
variant changes the real Paralyzed alpha/duration and proves the whole reaction
waits beyond the attack body. `test_attack_animation.py` covers native melee,
later-edge retained HP, ranged release/arrival and per-rig clocks.
`test_ranged_map_draw.py` checks actual ranged pixels on the map.
`test_playback_placement.py` covers the completion-to-idle boundary in all four
views, continued movement from a retained pose and fresh facts at that pose.
`test_body_lift.py` checks body/projectile attachment agreement and unchanged
support shadows. `test_feedback_layout.py` checks original actor pixels with
stacked feedback at screen edges. Paralyzed still uses the original saturation
`0.35` and brightness `0.86`; the port did not add a new condition shader.

`test_choreography_recovery.py` uses the existing public Fire Bolt scenario with
a native Concentrating recipient. The actual failed Constitution save removes
that condition beneath TakeDamage. After engine reset, changing only valid
Studio recovery/condition authoring proves unchanged release/impact/HP anchors,
condition removal at its authored frame/delay, an idle caster during the longer
fade, and recovery frame zero at the completed child join. Both enabled/disabled
recovery cases pass (12.22 seconds including the existing scenario setup).
`test_feedback.py` verifies independent Dodge/attack/repeated-cast overlay
lifetime, source duration and retained application identities. Its final five
cases also include a real opportunity reaction: toggling only the authored
reaction badge preserves movement timing and settled state while suppressing
that badge. All five pass.

`test_gameplay_history.py` proves positions, condition expiry, turn histories,
real grants and replay after engine reset. `test_encounter_play.py` checks a
paused historical head while native enemy decisions advance. These are gameplay
contracts; a source-text check alone would not establish them.

The final real X11 encounter run settles 26 lineages and reaches victory at
frame 200, with displayed history equal to latest. Its explicit media gaps are
the fixed Goblin rig's missing ranged body/slash clips. Evidence and captures
are under `.runtime/reaction-composition/final-encounter`; the adjacent
`final-encounter.json` records the result. A separate 32-frame X11 review shows
walking/jumping reaction holds, actual condition appearance, continuation and
terminal positions in two camera views.

The condition leaf and public drawer tests (`test_condition_animation.py`,
`test_condition_draw.py`) pass nine cases, including all-row round-trip,
duplicate condition UUIDs, exclusion priority, seeking, a later neutral wrapper
not overwriting an active alpha transition, exact pixels by slot, hit-flash
priority and shadow alpha. Their changed modules pass Pyright.

**Anti-slop judgment:** the shared compositor and condition leaf remove a real
flattening problem and make authored changes flow through common primitives.
The implementation must still report the limits above. Loading all recipes or
playing one encounter does not establish universal animation coverage.

**Anti-OOP judgment:** the new owners are passive plans plus functions over
existing retained identities. They add no per-spell executor hierarchy, new
mechanical event vocabulary, live-condition copies or independent action queue.
Further source primitives should join this same composition boundary; adding
more wrappers around the same state would not improve the design.
