# D&D recovery: plan of action

The [user complaint record](agent_docs/USER_COMPLAINTS.md) preserves the user's
corrections and required contracts, including record-once event replay. Read it
alongside this plan; a bounded implementation status does not relax those contracts.

Updated 2026-09-24, retaining the user's correction: **develop the game, not a
sequence of spell demonstrations.** Working branch: **codex/recovery-design**,
based on **codex/july-reconstruction at 16a6bfe**. The human committed the
validated recovery implementation as **58b0946** (`visio nextraction working`).

**Objective:** a playable in-process D&D encounter using the existing engine and
NeuroStudio data through Python/Pygame. Complete subjective lineages reduce
independently of historical playback. The engine already owns the rules; the
application must connect movement, actions, turns, reactions and state into a
coherent game. Hundreds of spells exercise shared capabilities and data, rather
than receiving separate executors or becoming serial release milestones.

**Available foundation:** retained lineages, independent latest/history, the
map/camera/picker, rig drawing, authored cast sampling, repeated applications and
equipment playback work. The finite Fire Bolt/Magic Missile programs remain
regression references. Their success does not constitute the game. The earlier
Magic Missile geometry was a generated fallback; the actual CodexFX Rune Dart
is now imported through the original Studio schema, independently of gameplay.

## Active work — playable encounter through shared capabilities

### Current position — read this before the checkpoint details

**Completed September 24 unit — reviewed rendering cleanup and private asset migration.**
Required U0–U8/A1–A3 work is implemented and independently reviewed; optional
resizing remains unneeded. Current public JSON has explicit composition,
registration and storage semantics; draw metadata is typed, importers preserve
selected authoring, and saved subjective lineages remain the playback input.
Fresh packed-only validation closed all 79 broad-run failure/error cases:
333 affected tests pass, whole-game/native-event typing is clean, and 26 retained
four-camera observer clips pass. The source archive preserves all 62,769 files;
the separate private production release contains 24,783 files / 15.066 GB.
[ASSETS.md](ASSETS.md) is the short operating guide, linked from `AGENTS.md`.
[Implementation, exact validation scope and release evidence](agent_docs/CLEANUP_IMPLEMENTATION_STATUS_2026-09-24.md).
Do not redo the inventory or resume new content as part of this completed unit.
Private remote publication and historical Git removal remain separate; current
media untracking does not erase earlier commits.

**Completed September 24 unit — detailed cleanup implementation plan.** The
[implementation plan](agent_docs/RENDERING_ASSET_CLEANUP_IMPLEMENTATION_PLAN_2026-09-24.md)
turns the reviews below into 14 ordered units with code owners, concrete changes,
dependencies, commit boundaries, focused validation and final acceptance. Two
independent anti-slop and anti-OOP/ECS reviewers approved it after a correction
round and complete reread; asset/setup review also passed revalidation. Rendering
ownership and replay fixes are primary. Private setup/packing is a parallel track;
historical Git scrubbing remains secondary and deferred. Implementation is completed as recorded above;
do not restart the inventory or add new spell content under this unit. The plan retains current
approved visuals and separates mechanical migrations from the intentional cap
fix. It also includes the discovered ordinary-installer full-read cost and the
packet-cache registration requirement before physical payload sharing.

**Completed September 24 unit — complete production asset inventory.** Three
local specialists and the private-assets task reconciled all 62,769 installed
files, with zero unresolved decisions or missing packing owners. Keep 57,218
physical references; 5,551 files are archive-only for current production.
At that inventory checkpoint, excluding those and sharing exact retained payloads reduced the measured encoded
content from 26.661 GB to 14.919 GB (44.04%), before new compression or cell
compaction. These are historical pre-implementation estimates; the implementation
status above records the corrected Gust selection and actual packed release.
The [complete inventory and reviewed packing choices](agent_docs/PRODUCTION_ASSET_INVENTORY_2026-09-24.md)
records exact frame/state subsets, real fixed-size candidates, shared/dynamic
scaling, and missing supported modular content. Anti-slop and anti-OOP cross-review
passed. Offline evidence is in `.runtime/asset-inventory-20260924/`; durable
specialist reports are in `agent_docs/audits/`. No production code or media was
changed during that inventory. The subsequently authorized implementation is
recorded above; no broad downsample or compression estimate is assumed.

**Completed September 23–24 unit — rendering architecture audit; feature work paused.**
The user requested a thorough multi-agent anti-slop / anti-OOP review of XYZ
rendering, event causality, object/asset metadata and typed authoring portability.
Three independent reviews and cross-review of the consolidated plan are complete.
The audit changed documentation only. It proposed repairing current
public destruction JSON replay and separate retained-native-archive decoding,
then importer ownership, explicit geometry/typed authoring and support reporting.
The broad selected game run finished with 2,052 passed, 206 failed and 7 setup
errors; the report classifies every failure group rather than waiving them as
preexisting. Whole-game typing is clean. See
[findings, reviewed cleanup sequence and exact validation scope](agent_docs/RENDERING_ARCHITECTURE_REVIEW_2026-09-23.md).
The private licensed-assets repository/install workflow is a separate project
task, `01a0d026-c987-7ea1-b474-4a352d1f9b41`; its migration is not part of this review.
At that audit checkpoint production packaging was reasoning-only: preserve the source archive,
identify every runtime-required frame and no excess, then assess lossless sharing,
packing and compression. The completed dependency inventory above supplies those
inputs; source preservation and an explicit packing adapter remain necessary.

**Completed September 23 unit — seven additional AoE XYZ deliveries.**
Burning Hands, Gust of Wind, Thunderwave, Shatter, Color Spray, Sleep arrival
mist and Ice Knife burst now use the shared registered-surface path. The author
supplied the missing Color Spray banks and corrected Shatter's duplicated view.
Native policy is recorded into public spell facts; clocks and mechanics remain
unchanged. Whole-origin components preserve blend order; historical supports
clip below-floor particles; Color Spray retains dynamic hand alignment through
an explicit baked-point delta. Gust preserves its existing maintained clock.
[Implementation, reviews and validation](agent_docs/AOE_XYZ_BATCH_2026-09-23.md).
[26 paired four-camera clips](http://127.0.0.1:8767/runs/20260923T183603Z-0c1ae2/index.html)
pass with zero presentation gaps. The relevant suite and late-tail checks pass;
Pygame/native changed-file typing is clean. These are review captures, not a
claim of new human visual approval.

**Queued handoff, not part of the completed AoE batch:** the Godot author has
also delivered Darkvision / See Invisibility / True Seeing revision
`sensory-four-camera-v5` at
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/sensory-spells-review/production-handoff/HANDOFF.md`.
Use `media-four-camera.json` camera banks when that integration is scheduled;
this note records receipt, not production integration or acceptance.

**Completed September 23 unit — six healing/support spells.** Aid, Lesser
Restoration, Greater Restoration, Heal, Mass Cure Wounds and Mass Heal use
explicit Studio recipes and all four delivered camera banks. Aid uses the
author's application/quiet-hold crossfade and phase-preserving removal fade.
Discovered native scenarios expose real targets, HP caps, condition removal,
movement and unaffected bystanders through saved public lineages. Fixed Aid's
obsolete target-count hook and condition-stat replay, including repeated casts;
recipient media now avoids inappropriate terrain-area projection.
[Bounded implementation and review evidence](agent_docs/HEALING_HANDOFF_INTEGRATION_2026-09-23.md).
[14 paired four-camera clips](http://127.0.0.1:8767/runs/20260923T202705Z-702275/index.html)
pass with zero presentation gaps. 152 distinct focused tests pass and scoped
typing is clean. Captures were inspected, pending human visual review. The
queued sensory handoff remains separate from this completed request.

**Completed September 23 unit — Fireball connected propagation and Globe XYZ.**
The user approved Fireball's bounded connected spread through open doorways
(policy C) and requested production backend/rendering integration of the Godot
handoff. This supersedes the earlier read-only area study and Globe-art deferral.
Only Fireball changes its propagation policy. Globe now discloses its visible
presence through ordinary sensory events and attributes suppression to actual
spell events; replay uses saved public observations. Paired color/XYZ media
feeds the existing painter, with finite wall occlusion and spherical protection.
See [implementation and validation](agent_docs/FIREBALL_GLOBE_XYZ_IMPLEMENTATION_2026-09-23.md).
Current validation covers native damage/Ashen, ordinary and protected Ice Knife
lineages, cold replay, four-camera coordinates and bounded media decoding.
The [20 paired four-camera clips](http://127.0.0.1:8767/runs/20260923T160308Z-1dfea8/index.html)
pass with zero presentation gaps; 218 selected tests pass and scoped typing is
clean. A measured Ashen sensory cascade was also fixed using existing valid
observer fields, preserving per-event observations (protected native Fireball
2259→343 ms in the documented diagnostic). Both reviewers approved. Additional
The next seven-effect XYZ batch is now integrated; its installation does not
authorize changing other spells' native propagation rules. See the current
batch record below.

**Fireball flicker follow-up:** user playback review exposed smoke/fire material
order reversing in the new per-pixel depth partition. The shared compositor now
keeps authored components ordered within common external depth bands. The export
and playback clock are unchanged; the before/after trace contains all 48 impact
frames in order. The six real source comparisons match exactly, 95 selected
tests pass, typing is clean, and both reviewers approved. See the follow-up in
the implementation record above for the defect and updated replay evidence.
All [20 corrected paired clips](http://127.0.0.1:8767/runs/20260923T175550Z-17c120/index.html)
pass with zero presentation gaps, replaying the same saved inputs.


**Completed September 23 unit — Sanctuary and interrupted actions.** The user
requested real handler fixes and cancellation presentation that distinguishes
an unpaid attempt from an action already paid for. Native Sanctuary now gates
harmful selected-target spells, respects beneficial/area semantics, and retains
its existing attack gate. The shared cost owner records actual expenditure;
public replay retains cancellation phase and outcome without private amounts.
Counterspell's separate reaction roots retain their original trigger links and
reduce in order while sharing the existing playback head. Original NeuroStudio
body recipes and passive interruption rules drive attempts; no fabricated hits.
See [scope, reviews and verification](agent_docs/SANCTUARY_INTERRUPTION_2026-09-23.md).
The user requested longer readable direct-cast preparation and Counterspell
VFX. The follow-up now integrates four-camera success/failure bursts, source-hand
energy and neutral projectile dispersal, keeping the native cutoff separate from
the visual tail. The
[updated 20 paired four-camera clips](http://127.0.0.1:8767/runs/20260923T104902Z-be3b63/index.html)
replay the same saved inputs; all checks pass with no gaps. Counterspell art is
integrated **for user review**, not claimed visually approved. Ordinary approved
spell targets and trajectories are unchanged. Direct suppression currently bursts
at the casting actor; formation-specific cloud suppression remains a separate
candidate with the Godot author. Details, reviewers and tests are in the record.
Globe already has tested native rules; its art and Dispel Magic remain outside
this follow-up.

**September 23 read-only area/geometry study:** the user asked which other AoEs
need Fireball's spatial rendering treatment and whether XYZ data is necessary.
The [native inventory and rendering-data findings](agent_docs/AOE_PROPAGATION_REVIEW_2026-09-23.md)
separate ground coverage, spatial volume composition, native propagation and
subjective protection facts. The study also reproduces an Ice Knife/Globe gap;
the existing passing Globe tests do not cover that secondary burst. No native
rules or production rendering changes are included in this study.

**September 23 environment-content batch implemented:** all 21 agreed freestanding
props now have authored HP, placement, channel blocking, destruction/debris and
reviewed media bindings through the existing systems. No per-object behavior
classes or renderer branches were introduced. The
[implementation record](agent_docs/ENVIRONMENT_CONTENT_IMPLEMENTATION_2026-09-23.md)
contains both design reviews, the physical profiles and validation: 110 selected
tests pass, scoped typing is clean, and all
[42 paired four-camera captures](http://127.0.0.1:8767/runs/20260923T145511Z-6d4722/index.html)
pass with no presentation gaps. Clips use real attacks, destruction and movement
from saved subjective events. The three optional subjects, mounts, windows and
full building assembly remain outside this batch.

**Environment destruction timing follow-up:** the user approved the remaining
appearance and identified early disclosure behind still-intact break frames.
The [shared clearance timing correction](agent_docs/DESTRUCTION_VISIBILITY_TIMING_2026-09-23.md)
adds an authored bank frame for historical geometry/sensory admission, preserving
impact timing and immediate native resolution. Six opaque props have inspected
markers. [Twelve updated paired clips](http://127.0.0.1:8767/runs/20260923T151946Z-aef733/index.html)
replay the same saved inputs and pass their checks. Unmarked banks, barrel
release and device cleanup retain their existing timing. The record distinguishes
this fix from the archived event-schema fixture failures found in wider checks.

**Sanctuary follow-up integrated.** The user-requested yin-yang presentation now
uses the existing native ward and shared condition renderer, with explicit passive
cast/condition data and a genuine source-owned apply/hold/clear export.
[Four paired-observer clips](http://127.0.0.1:8767/runs/20260922T123011Z-44b2f6/index.html) show failed/pass attacker saves, real blood,
movement, hostile-action removal and a maintained ward across its full loop.
Native ten-turn expiry remains tested. See the
[implementation and known native limits](agent_docs/SANCTUARY_INTEGRATION_2026-09-22.md).
The final 33 selected gameplay tests, changed-module typing and saved-input capture
checks pass. No native rules or renderer code changed. This small review stays
separate from the focused fourteen-spell/barrel page below.

**Current feedback handoff — latest fourteen spells and barrels only.**
The user narrowed review after the 181-clip collection proved too broad and
identified missing blood in its humanoid spell scenarios. The fixture now composes
the existing blood-response handler; all 18 injury experiments were recaptured
as 36 clips with real saved blood releases and persistent floor residue.
[Open the focused 90-clip gallery](http://127.0.0.1:8767/runs/20260922T113258Z-latest-spells-and-barrels/index.html): 62 clips for the latest fourteen
spells and 28 existing barrel clips. The earlier spell batch is excluded.
See the [focused handoff](agent_docs/SPELL14_AND_BARRELS_FEEDBACK_2026-09-22.md)
for scope, evidence and known visual limits. The correction passes 43 focused tests
and changed-module typing. Saved input, trace and original capture identities remain
exportable. No engine or renderer change was needed for this fixture correction.

All fourteen accepted outstanding presentations are integrated through shared
capabilities and authored data; the
[implementation record](agent_docs/SPELL14_INTEGRATION_2026-09-22.md) records
native state changes and their checks. Full suites passed 1,476 engine / 2,120
game tests before the later fixture corrections. The previous
[181-clip handoff](agent_docs/SPELLS_AND_BARRELS_REVIEW_2026-09-22.md) is historical.
**Barrel source-coverage corrections remain queued**; Wet body media is unbound,
burning-surface artwork is outside this unit, and upcast Fog uses wide review
framing. Do not mistake earlier liquid completion notes for closure of those
later coverage findings. Current work is ready for the user's visual feedback.

**Liquid-media delivery integrated.** All six materials × three approved
irregular variants now use four-camera floor/air exports and raw air footpoints.
Native geometry survives saved subjective replay; authored rupture starts the
spill, and settling continues independently of later actions. The
[28 paired gameplay clips](http://127.0.0.1:8767/runs/20260922T075227Z-718226/index.html)
pass their checks. See the [production result, tests and limits](agent_docs/LIQUID_MEDIA_INTEGRATION_RESULT_2026-09-22.md).
The whole 3×3 appearance supersedes the quarter-tile proposal; the unapproved L
experiment is excluded. The existing Wet condition has no body presentation
recipe and remains a reported gap; its native state and the water pool work.

**Complete Godot asset intake received.** The user requested all prepared/accepted
media not yet in production, using the illusion/transformation and historical
ten-spell handoffs as starting points. The
[reconciled intake](agent_docs/GODOT_BACKLOG_INTAKE_2026-09-22.md) links the full
Godot delivery: 14 accepted outstanding spell presentations, their exact exports,
readiness limits and existing production evidence. The old ten-spell batch is
already installed. Sanctuary was excluded as a prototype at intake; the newer
user-authorized integration above supersedes that classification. Enhance Ability
remains concept-only. No new spell was installed during intake. The user's subsequent
instruction now authorizes the entire fourteen-presentation implementation
above; use this current inventory rather than stale pending labels or finite
browser-preview behavior.

**Historical September 22 correction — surrounding barrel spills.** The user rejected the
one-cell result below and approved up to 3×3 surrounding native footprints for
**all six** liquid barrels. Follow the
[area correction plan](agent_docs/LIQUID_BARREL_AREAS_2026-09-22.md), including
real boundary/contact tests and wider dread-pool retreat behavior. A liquid
spilling animation is explicitly **required and queued** with the Godot task;
static appearing pools did not satisfy that final visual requirement. The
production result above now closes the spilling/rounded-pool work described here.
The further visual correction requires **authored material tiles with rounded
pool outlines**, not repeated splats or square-looking fills. The procedural
field experiment is withdrawn. The latest
[topology handoff](</home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/material-pools/HANDOFF.md>)
records the user's reassignment of **both material tiles and animations to Godot**;
the environment-art task paused overlapping authoring. All six materials are in
that request, with Grease reusing its accepted spell shader. Provisional static
PNGs remain uninstalled; rounded pools, shared-phase persistent loops and spilling
remain unfinished pending review and integration.
Native surrounding coverage and connected dread-pool retreat are now verified:
1,459 engine tests pass, focused public replay/render tests pass, and typing is
clean. See the [area result and explicit visual limits](agent_docs/LIQUID_BARREL_AREAS_RESULT_2026-09-22.md).

**Historical September 22 — first liquid barrels implemented.** The user expanded the destruction
unit to poison, water, oil, grease, blood and dread blood contents. The
[reviewed liquid-barrel plan](agent_docs/LIQUID_BARRELS_PLAN_2026-09-22.md) reuses
native surfaces/residues and the same destruction lineage; one-cell spills
survive their wreck. Ground contact and saved two-observer replay are acceptance
requirements, now covered by native contact tests, saved public replay and
[22 paired four-camera clips](http://127.0.0.1:8767/runs/20260921T231101Z-2f7c49/index.html).
See the [implementation record and exact limits](agent_docs/LIQUID_BARRELS_RESULT_2026-09-22.md).
Oil/water now publish native material observations; five materials draw through
the shared liquid/residue sampler. **Grease artwork is explicitly deferred by the user** to the
later accepted spell handoff. Persistent burning-surface artwork is also absent;
its handoff need is queued, without expanding this into terrain combustion.

**September 22 — shared destruction and first multi-cell prop unit implemented.**
The user authorized the reviewed destruction unit and assigned missing art to
task `01a0b501-8a27-7413-ba24-4a36e5b140d2`. The shared same-UUID transition and
current-family migration are implemented. The full engine suite plus maintained
item-registry checks passes 1,377 tests; the full game suite passes 1,954 tests;
native/game typing is clean. Cold furniture initialization also passes its
38-case focused regression and independent review.
`ItemDestructionEvent` owns the transition; geometry, mechanism, light and spill
events are its causal children. Physical breakage is distinct from terminal
consumption/expiry. See the [live implementation record](agent_docs/DESTRUCTION_IMPLEMENTATION_2026-09-21.md)
for actual tests and remaining work. Two-cell furniture, legal far-end contact,
owned debris terrain and saved two-observer replay now work. Three chest pairs,
crate, barrel, bed and table use accepted prop banks through the existing
renderer; the [20-clip gallery](http://127.0.0.1:8767/runs/20260921T222920Z-12c92c/index.html)
includes real chest contents and walking through wrecks. The potion has floor
state but no installed ground sprite. The broader 117-subject interiors intake,
mounts/supports and usable windows remain unfinished. New fixture destruction
art was delivered separately as user-unapproved candidates, not installed media.

**September 21 — complete interiors integration plan.**
The user requests a reviewed plan covering **all** consolidated handoff assets,
starting with native items and their visibility, walkability, placement, height
and support data. The [complete integration plan](agent_docs/INTERIORS_INTEGRATION_PLAN_2026-09-21.md)
replaces the earlier small-lodge delivery framing; its first room is a proving
step, not the whole objective. Exact asset dispositions are recorded in the
[coverage companion](agent_docs/INTERIORS_ASSET_COVERAGE_2026-09-21.md).
Existing doors/traps remain, furniture and supported-object lifecycle use the
current native owners, windows are gameplay openings, and replay remains event
driven. Independent content, anti-slop and anti-OOP/ECS review belongs to the
expanded plan, not merely its earlier revision.

**Destruction now has a dedicated plan, at the user's request.** The
[destruction lifecycle plan](agent_docs/DESTRUCTION_LIFECYCLE_PLAN_2026-09-21.md)
and [native/media coverage ledger](agent_docs/DESTRUCTION_COVERAGE_2026-09-21.md)
specify persistent intact → destroyed state on the **same item UUID**. This
supersedes replacement-wreck identity in the older interiors proposal. Reuse
Health, damage events and destruction hooks, while separating physical breakage
from terminal consumption/expiry. Adoption covers all current doors, physical
traps, devices and props plus selected delivered counterparts; methods, cleanup,
subjective replay and real behavioral tests must migrate together. Missing
bindings, native capabilities and genuinely missing art are separate gaps.
Implementation now follows this plan; new asset exports are not visual approval.

**First unit narrowed by the user:** carefully establish multi-cell furniture,
usable windows and attacking/destruction before broad content intake. Existing
trap/door item Health, damage and destruction hooks are reused under that
same-identity plan. The
plan's active core-first section defines one two-cell furniture object, a fixed
barred C4 window/solid-wall comparison and two observers. Footprint-wide spatial
updates, legal manual access and native aperture queries are the actual missing
contracts. The destruction subplan expands current-family adoption rather than
leaving doors/traps on a second lifecycle. Mounts, bulk content and houses follow;
no window glass/shutter mechanics are implied. Existing door/trap destruction
baseline rerun: 48 passed in 4.76 seconds. That historical baseline predates
the implementation; current validation belongs to the implementation record.

The user explicitly says **ignore the Z discussion for this plan**. Stacked
floor design is in the separate task **3D / XYZ backend map design**
(01a0c567-b928-7210-8f33-d9a8b099aae3), restored and resumed with the user's
request to scan all affected rules/systems, starting with walking/pathfinding,
light and senses. Its [existing proposal](agent_docs/MULTI_Z_MAP_PLAN_2026-09-21.md)
is background for that separate task. Do not reintroduce its migration or
sequence debate into interiors work. Preserve source upper-floor assemblies
without claiming they are already playable. Existing control-spell work remains
complete; the active destruction unit does not introduce stacked floors.

**September 21 follow-up completed — native typing and Goblin slash.** All 266
native typing errors and the warning are resolved with checker settings
unchanged; native and graphics/review checks are clean. The engine suite passes
1,117 tests, active progression passes 200, and the Goblin's saved four-camera
opportunity attack now has its authored slash and zero media gaps. See the
[repair result and validation limits](agent_docs/NATIVE_TYPING_AND_GOBLIN_CLEANUP_2026-09-21.md).
The investigation also found a separate, unresolved
[stats-read registry retention defect](agent_docs/STATS_SNAPSHOT_VALUE_RETENTION_2026-09-21.md);
it is not dismissed as test noise. The completed graphics checkpoint below
remains historical starting evidence, including its then-open typing/media gaps.

**September 21 — control-spell integration completed.** The
[reviewed implementation plan](agent_docs/CONTROL_SPELLS_IMPLEMENTATION_2026-09-21.md)
now connects Charm, Blindness/Deafness, Command, Color Spray, Silence and Sleep
through shared condition/spatial lifecycles and pose registration. Real overlap
ownership, selected Color Spray aim and witnessed spatial removal were repaired.
The corrected lethal opportunity experiment also records blood from its existing
body-response handler. The [34-clip gallery](http://127.0.0.1:8767/runs/20260921T132229Z-53ba67/index.html)
passes every replay check with zero media gaps, using both subjective views and
four cameras. The [result and exact validation limits](agent_docs/CONTROL_SPELLS_RESULT_2026-09-21.md)
record the full game run's three repaired failures and final 66-test passing
slice, clean native/graphics typing, measured modular socket coverage and the
remaining Color Spray duration rule discrepancy. No optimization or unrelated
gameplay redesign was introduced by this unit.

**September 21 — unified graphics cleanup implemented and reviewed.** The
[reviewed execution plan](agent_docs/GRAPHICS_CLEANUP_EXECUTION_PLAN_2026-09-21.md)
is completed within its stated scope. Native origin/range adoption, saved-record
compatibility, explicit media intake, test collection repairs and authored
downed/rest/recovery presentation are implemented. Local spell drafts use
version 2 with explicit root/body/ground bases, actual-path insets and consistent
image registration. Fire Bolt's approved mage placement remains intact; device
emission uses the measured muzzle. All six terrain xfails have passing geometric
tests, including preservation of a body on its own supporting floor.

The [implementation result](agent_docs/GRAPHICS_CLEANUP_IMPLEMENTATION_2026-09-21.md)
records exact validation and scope: 1,111 engine tests pass; the full game run's
six failures were resolved and both affected modules pass all 13 tests, with
280 final compositor tests passing. The 22,464 projectile samples are identical;
the whole-clip isolation comparison also preserves approved output while
separating intentional terrain changes. The
[46-clip four-camera gallery](http://127.0.0.1:8767/runs/20260921T105556Z-cf9048/index.html)
passes replay checks, with one preexisting goblin slash-overlay gap still
disclosed. Both subjective views are retained where captured. Graphics/review
typechecking is clean; the broader native check has 266 errors and one warning,
proven identical before/after this cleanup. These are explicit remaining limits,
not claims of a fully rendered spell catalog or a type-clean whole repository.

The [system review](agent_docs/GRAPHICS_SYSTEM_REVIEW_2026-09-21.md) records the
starting defects. The [preserved checkpoint chronology](agent_docs/RECOVERY_CHECKPOINT_CHRONOLOGY_THROUGH_2026-09-21.md)
contains previous dated work and decisions; it is historical evidence rather than
a competing current to-do list. Design commitments and earlier detailed
checkpoints remain below. No new VFX-authoring or feature expansion is part of
this cleanup.

### Validated checkpoint — recorded inputs drive the game presentation

**Required behavior:** generate native histories once, save their complete
presentation inputs, then load those bytes for subsequent reduction, binding,
rendering and gallery review. Receiving data must neither reconstruct live
entities nor register/re-execute mechanical events. The existing timeline,
subjectivity, authored recipes and per-rig mappings keep their meaning.

**Implementation order:**

1. Establish faithful concrete event encoding/decoding through the existing
   typed schemas and original concrete discriminator principle. Preserve all
   consumed facts and exact ancestry, projected logs and observer authority.
   Reuse the existing reducer/sampler; do not introduce another event taxonomy
   or a generic serializer for executable engine graphs.
2. Record native active-weapon state at birth and accepted equipment completion.
   Consume these after-values in presentation and remove startup's live stance
   handoff. The existing activation/reconciliation logic remains the sole rule.
3. Make recorded initialization sufficient and connect actor admission from
   existing composition/state and sensory facts. First discovery must use the
   actor's state at that point, including changes preceding discovery, and stage
   the received actor before binding its first visible lineage. Apply existing
   objective-to-subjective meaning before delivering player data.
4. Make the gallery load saved sequences. Case generation is an explicit input
   capture operation; re-recording/reviewing saved input uses no native producer.
   Keep all four camera views, pinned traces and the shared frame compositor.
5. Verify serialized inputs in a fresh process, compare every historical
   successor and representative pixels with the corresponding first recording,
   and include real discovery and active-set reconciliation histories. Update
   this plan and the audit with measured outcomes before broader gameplay work.

**Review:** the anti-OOP reviewer checks passive deserialization, typed schema
reuse, ownership and import direction; the anti-slop reviewer checks native
after-values, existing subjectivity and completeness of the gameplay cases.
They review the concrete design before edits to shared contracts, then the
implementation. Read HOW_TO_TEST before writing tests. Tests must cross actual
saved bytes rather than reuse the producer's Python objects or merely inspect
JSON fields. No VFX authoring, new stance rule, second animation queue or old
server reinstatement is part of this unit.

**Measured progress during this unit:** the broad game run passed 683 tests with
six existing expected failures; its two remaining failures were old gallery
callers needing explicit `--capture`, and both passed after that correction.
The dedicated gallery suite separately passed six tests, including saved-input
and exported-review replay in a fresh process with native production disabled.
Native sensory initialization/perception/lifecycle coverage passed 67 tests;
native equipment coverage passed 51. These focused checks overlap and are not
an additive total. Changed presentation/review production modules pass Pyright.

Comparison with original native rows caught 14 startup condition headers
inheriting the capture turn when their original turn was absent. Capture now
uses the same passive validation path as decoding; the real pre-encounter
condition regression and adjacent replay tests pass (12 tests). Only those
14 inputs were recaptured. The other 58 native recordings remain unchanged;
all recorded turn identities now match their original native versions.

**Final gallery:** [72 cases replayed from saved events](http://127.0.0.1:8767/runs/20260911T175347Z-ca915d/index.html)
contains 6,561 synchronized four-view frames and 277 completed heads. Every
video and input file is byte-identical to its corresponding capture, including
original input provenance. All event arrays, historical successors, timeline
samples and pixel hashes match. Fourteen initial-state diagnostics differ only
in `sense_modes_hash`, Python's process-local sensory cache hash; the actual
sense modes, contacts and capabilities match exactly. Both raw differences and
the comparison excluding only that field are preserved in the run's
`inspection/replay-verification.json` and `inspection/replay-comparison.json`.
Native scenario production and content bootstrap were disabled throughout this
fresh-process replay; EventQueue/entities stayed empty and the dice registry
was unchanged. This verifies saved input without rerunning the game. Existing
terrain/reach exceptions and nine cases' explicit rig-media gaps remain visible;
the replay result does not claim that every visual is complete. Anti-slop and
anti-OOP reviews approved the bounded implementation and these stated limits.

Architecture checks passed 46 and exposed three unchanged failures involving
the old server's `dnd.core.senses` import and the preexisting `EquipmentSlot`
alias. Full engine-suite collection also encounters unchanged old-server and
`dnd.content_system.item_bindings` imports. Those failures are not evidence of
this change, and restoring retired server code is outside the recovery plan.

**Boundary at the previous checkpoint:** C03/C04 in the complaint record were
partial. Observer movement could discover a previously unseen actor, and an actor
could be deployed into view with its current recorded equipment and HP. An unseen
actor moving into view was still rejected by the capture gate. The
original endpoint authority permits state discovery there without revealing
the hidden origin as an animation. Connect that existing rule within complete
lineages; do not restore the failed server's per-Step queues. The actual player
projection must also distinguish controlled inventory from observed visual
loadouts and keep local objective diagnostics/foreign sensory rows out of the
delivered packet. These are the next connections before calling this a complete
client/server-compatible subjective stream. The
[source study](agent_docs/ANIMATION_COMPOSITION_AUDIT.md#source-study-for-the-remaining-entering-view-connection)
records the native reproduction and historical implementation differences.

**Previous code checkpoint:** `48abb31` on `codex/recovery-design` completed
grounded jump reactions and one body traversal across the flight, with a
58-case gallery. The completed forced-movement unit connects native Shove and
ForcedMovement to the same historical choreography. All 69 four-view recordings
pass, including 11 new cases; the previous 58 videos and input pixel sequences
match exactly. Raised-terrace occlusion also affects the two stair-displacement
cards and remains an explicit visual exception.

**Where we are:** the in-process encounter and independent historical playback
work. We are expanding the shared presentation capabilities consumed by that
encounter. The gallery scenarios validate selected behavior; they do not
mean that the full NeuroStudio vocabulary or the full game is implemented.

| Plan area | Current status | Evidence and practical boundary |
| --- | --- | --- |
| Existing engine → retained lineages → independent playback | Recorded native input and public player projection connected | Original ancestry/grants, one public reducer for latest/history and one historical queue/head. Public bytes replay without live engine generation; objective diagnostics, foreign sensory data and private inventory stay in the separate native archive. |
| Playable Pygame encounter | Working bounded encounter | Discovered actions/targets, movement, attacks, player turns, native enemy decisions, resources and encounter completion. Live playback consumes the public projection, including movement into sight, contact loss and reacquisition. Paired viewpoints are available in the recorder; the encounter UI still controls one viewpoint. |
| Shared authored animation composition | Working, incomplete vocabulary | Original Studio data drives the connected attack/cast/movement/condition/equipment primitives, now including shove contact and forced brace/travel/release. Complete walking reactions interrupt at their edge; jump reactions join at launch before one flight. Authored fields outside those primitives remain explicit limits. |
| Repeatable visual validation | Paired public replay validated | Thirty visibility clips from 15 shared native histories, four cameras per viewpoint, plus six paired lethal/displacement clips. The 30 saved replays match capture videos byte for byte. Original 72 recordings are preserved. Selection/export retains the observer input and experiment link; capture is explicit. |
| Continuing condition and life histories | Completed prior unit | Native paralysis recovery/persistence, Dodge expiry, capped healing, death saves, stabilization, death/revival and correct retained placement/HP. |
| Creatures, equipment and movement | Implemented with explicit visual limits | Three exact rig identities; real wardrobe/item replacement; same-turn melee → longbow; turning routes with native Haste/Dash; grounded jump reactions followed by one flight across water/elevation. Rear-view terrace overlap and later-Step launch reach are documented below. |
| Forced movement | Completed bounded unit | Exact Shove contact, native actual path, original recipient brace/ease/release, reached-cell spatial damage/death and retained corpse placement. Telekinesis's granted displacement uses the same primitive. Stair terrain occlusion remains visible and tagged. |
| Broader gameplay presentation and content | Still partial | Self/touch/direct/area/persistent delivery, broader condition media, additional rigs and roster/map/inventory UI remain pending. Forced movement does not by itself complete every spell that can cause it. |

**What changed after the human's `58b0946` checkpoint:**

- `20f58db`: six continuing condition histories and stronger visual validation;
  existing production owners already handled those sequences.
- `80be2bd`: the original standalone healing feedback and two native cases.
- `ebff88c`: the original lifecycle badges, standalone death/revival playback,
  exact life-event ownership/HP corrections and eight further native cases.

These three commits deepen one shared area. They do not add general area/self/
touch casting, a full weapon-triggered Hold Person cast, or the demon/undead/
animal catalog. The tested sword rider applies native paralysis; its real
reaction/condition lineage is what the clip demonstrates.

**Completed lane:** forced movement extends the shared movement/action area after
the creature/equipment unit and jump correction. Event replay and the subsequent
visibility/player-projection unit connect that same gameplay to saved subjective
histories. Broader spell delivery remains the next pending shared-capability
area: reuse the original Studio vocabulary for self/touch/direct/area/persistent
delivery, with both participants' saved views in each applicable experiment.
New creature recipes and equipment media are used by
the live/recorded shared path; these clips do not add an inventory or roster UI.
The terrain finding is recorded for a bounded follow-up design investigation;
it does not authorize a renderer rewrite or displace the gameplay plan.

**Progress reporting:** at each unit boundary, state the parent plan area,
concrete outcome, what remains partial, and the next unit. During work, report
which acceptance check is being resolved and any scope change. At completion,
update this section as well as the detailed audit. Test/clip counts support the
status; they are not substitutes for explaining progress through the plan.

The sections below retain detailed checkpoint evidence. Completed sequences
and their earlier instructions are not the next work queue.

### Completed unit — forced movement through shared choreography

The human requested implementation after reviewing the jump correction at
`48abb31`. Connect native Shove/ForcedMovement lineages to the existing historical
head and four-camera recorder. Native rules, subjectivity, committed positions,
spatial handlers, costs and opportunity-attack eligibility remain authoritative.

**Source contract:** NeuroClient ShoveClip starts its owned forced-movement or
prone children at the authored contact frame, then joins body and children.
ForcedMoveClip plays the recipient body to its brace frame, holds that pose
while grid motion follows the context curve, resumes the remaining body frames,
then plays any authored recovery. The imported shove recipe uses Kick/contact7;
the original forced_movement context owns easing, facing and scales. The Studio
preview supplied TakeDamage/brace3/speed1/travel420ms in its cue constructor,
outside JSON. Preserve those exact values in a small portable adapter resource;
retain original source JSON unchanged. The old server's different brace/speed/
distance policy is historical evidence, not a rule to reintroduce.

**Implementation boundary:** two passive cues for shove body/contact and forced
displacement inside the existing BoundChoreography. They sample body poses and
actor contacts through the existing scene renderer. No artificial Attack event,
new queue, clock, rules engine, spell executor or Pygame-specific mechanics.
Existing per-rig TakeDamage mappings supply recipient bodies; import only the
missing original modular Kick sheets through the existing importer. Preserve
an explicit gap for rigs without that source gesture.

**Causality:** ForcedMovementEvent is not a voluntary Step. Shove's real
LEFT/ENTERED descendants occur at each committed cell and can cause damage,
conditions or death there. Bind those descendants at their reached positions
within the same head; do not inherit the old client's leaf-only assumption or
recompute eligibility/stopping. No failed/resisted/fully blocked shove invents
a displacement child. Legal and previously retained visual origins remain
separate through the existing placement contract.

**Finite acceptance:** actual discovered shove success/resistance/obstacles,
no-OA and native costs, modular/fixed-rig recipients, allowed height changes,
and one existing spatial effect lineage. Exercise a non-Shove native producer
through the same displacement primitive when available without building a new
spell delivery/VFX program. Verify contact anchoring, brace/travel/release,
native after-values and descendant identity, paused history, four-view pixels
and settlement into idle. Add data rows to the gallery and export compiled cue
timings in its existing traces. Keep prior gallery cases as regressions.

**Review/checkpoint:** the anti-OOP reviewer studies original Studio/runtime
authoring and passive timeline ownership; the anti-slop reviewer studies native
lineage/position/handler semantics and finite scope. Review these findings before
production edits, then review implementation and actual clips. Read HOW_TO_TEST
before writing tests. Record exact coverage, unresolved visual limits and any
source-confirmed unrelated test failures, update this dashboard and commit the
validated unit on this branch.

**Outcome:** the original Kick contact and recipient brace/travel/release now
run through shared choreography, with actual reached-cell spatial effects and
stable corpse placement. Success/resistance/full and partial obstruction,
native movement/reaction costs, a Goblin recipient, allowed stairs, nonlethal
and lethal spikes, and a Telekinesis-granted displacement are recorded.
The latter begins after its real cast/grab setup and does not claim complete
Telekinesis or other spell-delivery coverage. Fixed source rigs without Kick
keep an explicit gap; cliff falling remains outside this unit.

**Validation:** 139 targeted tests passed; two strict expected failures retain
the existing stair-map visibility limit. Height/body projection passes
separately. The anti-slop and anti-OOP reviewers approved ownership/source
design; selected encoded four-view clips were independently inspected.
Changed-file Pyright is clean and all 327 importer outputs match. The 21 exact
Kick PNGs total 2,525,473 bytes; no new VFX or native rules were authored.

**Gallery:** [69 cases, 11 new forced-movement histories](http://127.0.0.1:8767/runs/20260911T022551Z-96e142/index.html).
Run `20260911T022551Z-96e142` contains 6,204 four-view frames, with all 58
previous videos and pixel sequences unchanged from `20260910T215953Z-b06297`.
All 814 captured source files match the implementation. Its `inspection/`
directory records comparison, sampled encoded images, test groups and visual
limits. The gallery and MP4 byte ranges return HTTP 200/206. The detailed audit
retains source ownership and the measured stair occlusion.

### Completed correction — grounded jump reactions and one flight traversal

The human reviewed the gallery and rejected frozen airborne reactions. For a
jump, play its complete opportunity-reaction subtrees at the grounded visual
launch contact before takeoff. If the native result permits continuation, play
one uninterrupted jump; if stopped by paralysis/death, keep the body grounded.
The human also requires exactly one body-clip traversal spanning the full air
time, in both directions and for short/long/elevated jumps.

**Source evidence:** original NeuroClient JumpClip also advances 12–35% into
its arc before pausing for pre-motion groups. That behavior is superseded by
this correction, while its JSON, clips and duration/arc parameters remain the
authoring source. Actual current water-jump video pixels already traverse
Rolling frames 0–14 once. The reproduced OA discontinuity switches Rolling to
Idle/TakeDamage mid-air, then resumes at a late Rolling pose. Do not claim a
separate plain-flight frame-wrap defect without evidence.

**Bounded implementation:** compile jump reactions in native order into the
existing MotionTimeline before one flight leg. Keep complete children, event
identities, grants, native commit positions and all reducer after-values.
Reaction-only timelines may contain no flight legs; sample their settled body
directly. One explicit body-loop flag in the detached timeline distinguishes
continuous walking playback from a single jump traversal; normalized flight
progress selects the selected rig's frame once, independently of camera, Step
boundaries and reaction duration. No new queue, FSM, spell rules or art.

**Legal versus visual:** a Step-2 lethal OA can leave a committed native prefix
while the body is still visually at launch. Preserve that legal endpoint and
use the existing VisualPosition override for the grounded visual origin.
The verified later-only reactor at (1,3), jump (3,3)→(1,1), is outside launch
reach but legally reacts at Step 2. Preflight visualization has a spatial limit
there; this correction does not silently change native OA eligibility, move
the reactor or undo committed Steps. Exact native reach policies remain engine
work if the human later chooses to change them.

**Validation and reviewers:** the anti-OOP reviewer verified original source,
existing passive timeline ownership and actual encoded Rolling traversal. The
anti-slop reviewer independently verified native first/later-Step outcomes and
the legal/visual distinction. Rework the old airborne expectations to grounded
ones, keep walking regressions, check stopped-head release and later condition
recovery, and assert actual four-view jump body frames progress once from
launch to landing. Include short/long, reversed/elevated and multiple-reaction
histories, paused playback, native state parity and the existing terrain visual
exception. Regenerate affected clips for human review, update this dashboard
and record the code/test review before committing the correction.

**Implementation review:** the independent anti-OOP reviewer approved the
existing passive timeline/reducer ownership and verified 39 focused tests,
including actual layered body pixels for all 15 poses in four cameras. A
concrete compatibility regression found during review was removed: binding a
jump must not demand a Rolling resource before the shared renderer can choose
the established missing-clip fallback. No new rig alias or artwork was added.
Short/long forward and reverse gallery entries use separately discovered native
jumps; Jump spends a bonus action, so the recorder does not fabricate two jumps
in one turn. The anti-slop reviewer independently approved actual event
ancestry, complete reactions and preserved native committed prefixes. Encoded
four-camera sheets received an additional independent visual review.

**Final result:** [58-case gallery](http://127.0.0.1:8767/runs/20260910T215953Z-b06297/index.html),
run `20260910T215953Z-b06297`: 58 recording checks pass, 5,341 four-view frames.
The seven corrected jump-reaction histories changed; all other 46 pre-existing
videos and input pixel sequences are byte-identical to the previous gallery.
Five new cards provide duration/direction, multiple-OA and later-reach evidence.
All 18 jump heads were checked for grounded reaction prefixes and either one
contiguous body traversal or no takeoff. Relevant test groups contain 142
passes, four known terrain expected failures and three source-confirmed legacy
architecture failures; changed-file Pyright is clean. Runtime, data, catalog
and test source hashes match the capture. Only a README wording clarification
followed capture; the run's `inspection/verification.json` records that
distinction and the two explicit visual limits. This completes the jump
correction without changing native mechanics or the world renderer.

### Latest unit — creatures, equipment and movement

**Requested outcome:** review actual demon, undead and animal actors; clothed
modular characters; actual equipment changes and melee then ranged attacks in
one legal turn; ordinary movement around corners; movement after Haste and
bonus-action Dash; jumps across water, uphill and downhill. Every case uses the
same retained-history renderer as the game and records all four camera views
in one pass. Existing reaction/death/condition cases remain regressions.

**Result:** the completed gallery is
`20260910T211349Z-a5d2b1` at
<http://127.0.0.1:8767/runs/20260910T211349Z-a5d2b1/index.html>.
All **53 recording cases pass**, including 15 new gameplay histories; 4,973
four-camera frames were encoded. All 53 videos and input pixel sequences are
byte-identical to the independently inspected full run `20260910T205130Z-d61669`.
All 785 captured source-file hashes match the final working implementation
(source hash `9e79e49e3d5d187439f82c2815c1fa7ffadd52124157abc405a53961e8c1f6f9`).
The run's `inspection/verification.json` records those checks and names the
known hill-jump visual exceptions. Relevant native, presentation, recorder and
import tests pass; the terrain pixel matrix has 12 passing controls and four
strict expected failures. Detailed overlapping test groups, partial Dretch
support, frozen historical audit failures and unchanged type errors are recorded
in `agent_docs/ANIMATION_COMPOSITION_AUDIT.md`. This is a bounded gameplay
checkpoint, not a claim that the entire game or repository suite is complete.

**Portable-data boundary:** original Studio JSON owns recipes, body frames,
anchors and timeline contexts. Pack-specific names, sheet geometry, identity
bindings and clip compatibility belong in fixed-rig JSON. These resources can
be consumed by a later TypeScript implementation. Python owns today's native
mechanics and presentation reducer, event-to-timeline binding and evaluator;
these functions are not automatically importable into TS. A TS frontend can
keep the Python engine as its authoritative event producer. Do not claim a
completed TS consumer or invent another timeline schema/export platform in this
unit. Retained event
and compiled-timeline JSON in traces provide concrete inputs/results to port
and compare. Gameplay scenarios are native producers, not replacement rules.

**Source findings at entry:**

- Existing equipment binding and the original Taunt/commit-frame context work
  in the old finite playback path but are absent from normal encounter/gallery
  composition. Connect that primitive to the shared path.
- Original AttackClip activates the selected weapon type at attack entry.
  Native accepted attacks also activate their slot. An automatic ranged attack
  does not justify manufacturing a SwitchWeapon root or extra Taunt delay.
- Native Haste doubles speed and Cunning Action Dash spends the bonus action
  to add current-speed movement. Original movement presentation uses authored
  travel timing independently. Validate extra legal travel/resources; do not
  invent a Haste/Dash animation-rate multiplier.
- Current motion binding creates a fresh jump arc per native Step. Compare a
  real multi-cell jump with NeuroClient's contiguous jump leg/arc before any
  correction. Keep the engine's Step facts and reaction ancestry intact.
- Goblin is the only installed fixed rig. The purchased demon/undead/animal
  packages need exact selections and mappings. Native undead and wolf owners
  exist; the active roster has no implemented fiend. A demon must have an
  explicit canonical composition and honest capability metadata, never be an
  unrelated creature renamed for its sprite.

**Implementation sequence:**

1. Three independent source studies cover equipment/action economy, native
   movement/terrain and purchased rigs/native creature identities. The
   **anti-slop reviewer** checks these findings, finite scope, original source
   reuse and actual game coverage. The **anti-OOP reviewer** checks ECS
   ownership, existing event ancestry, single queue/clock, portable data and
   shared rendering before the production connections are changed.
2. Add a finite rig selection through the existing importer, preserving PNG
   bytes and provenance. Bind exact canonical creature refs in JSON. Reuse
   the existing canonical creature composition for native attacks/movement;
   any new fiend entry uses existing mechanics owners and explicitly records
   unimplemented special traits. Do not bulk-import purchased archives.
3. Give modular scenario actors real equipped apparel before their birth
   capture. Select already available authored layers where possible. Add
   native equipment/clothing replacement histories plus a same-turn melee →
   ranged sequence with the real Extra Attack/action-economy owner. Preserve
   the independent equipment roots and their real commit semantics. Connect
   the existing equipment primitive through shared composition/media/drawing
   so normal play and recording agree; do not add another playback queue.
4. Produce native movement cases on a real published battlefield: a turning
   route; a longer Haste route; bonus-action Dash followed by travel; one jump
   over water with level banks; one ascending jump and one descending jump.
   Use discovered actions/targets and record committed positions, heights,
   costs and condition/resource results. If the reproduced multi-Step jump
   differs from the original single arc, correct only that shared geometry/
   timing compilation and preserve canceled native endpoints. The original
   mid-flight hold requirement from this checkpoint was superseded by the
   grounded-reaction correction above. No per-case trajectory patches.
5. Add the cases to the existing JSON gallery catalog and shared producers.
   Preload actual retained outfits/rigs. Camera framing must include the route
   and elevations in every quadrant. Export selected equip/body samples and
   native histories with existing trace conventions. The same JSON recipes
   and rig maps must drive every view, with no renderer species/spell cases.
6. Verify at public native and sampled-frame boundaries: legal same-turn
   actions/resources; original loadout identity at settlement and weapon-set
   selection at its authored cue/attack anchor; active attack weapon;
   mapped fixed-rig bodies; actual travel route/elevation/landing; reaction
   interruption and paused-history independence. Inspect affected four-view
   clips, run relevant regressions, changed-file types and import checks.
   Complete anti-slop/anti-OOP code review, then regenerate the catalog once
   the implementation is stable, update this dashboard/audit and commit.

**Acceptance boundaries:** more native travel is evidence of Haste/Dash;
animation speed stays at its authored rate. Equipment identity is native
state and visual layer selection is data-driven. A multi-cell jump visibly
leaves its source once and lands at its actual destination once, including
support-height differences; reactions still interrupt at their actual causal
edge. Fixed creatures use their own packaged sheets in all four views and
retain their own native creature identities/defenses/actions. Missing optional
media or special traits must be named, not covered by invented assets/rules.

**Visual acceptance exception:** ascending/descending jumps expose terrain
painting over airborne body pixels in cameras 0 and 1. Native travel/height and
the contiguous authored arc are correct. Testing a depth-varying flat-floor
raster changed an established rear-wall overlap and still left uphill clipping,
so the prototype was removed. Actual last-writer instrumentation traced the
remaining uphill pixels to `terrain.cliff.w` / `terrain.cliff.n` for native tile
(14,20): the structural cliff sprite participates in the overlap too. This is
an existing shared terrain composition limit, not a jump timing defect.

The regression only protects authored pixels demonstrably above the floor
plane; Rolling artwork can extend below its rig pivot, so requiring the entire
sprite to remain visible would be an invented rule. Lower-ground hiding and
clear front views remain ordinary passing controls. Confirmed rear-view losses
are strict expected failures, and the two gallery cards carry `known-occlusion`
and a visible description. The anti-slop and anti-OOP reviewers approve the
gameplay changes with this exception and reject the insufficient terrain patch.
A later correction must model the actual flat/vertical authored surfaces while
preserving accepted wall/cliff overlap. Do not restart by assigning a height
bonus to every actor or drawing jump bodies above the world.

**Deferred:** new spell VFX, broad spell delivery, campaign/inventory/map-editor
UI, generalized scripting/rig inference, event registry redesign, old server
repair and unrelated legacy test failures. Nothing in this unit makes those
prerequisites to the requested gameplay clips.

### Completed unit — native life transitions and original lifecycle feedback

**Authorization:** the human asked to continue after `80be2bd`. This unit
continues the shared-capability and clip-extractor plan: real lifecycle facts,
original authoring, complete historical lineages and four-corner validation.

**Result:** both independent design and code reviews
approved the bounded connection. The native producer and playback tests now
pass, including the reproduced revival HP defect, original badges, standalone
death and existing lethal ownership. The final regression group passes
**159 tests**, including the live paused encounter and import DAG/direction;
the focused native/healing/paused-death group passes **19 tests** (overlapping
coverage). Changed-file Pyright is clean. The final gallery
`20260910T192249Z-2eb59a` passes **38/38**, including all eight new cases.
All captured source files match the final implementation. Of the previous 30
clips, 29 retain every RGB frame; only healing-dying changes, with the original
Revived badge and its decorative tail. The run's
`inspection/verification.json` stores this comparison and checks shown HP
against native zero in every downed frame. Boundary images were inspected in
all four cameras. Existing Goblin bow/slash media gaps remain explicit.

Final visual inspection caught intermediate packet HP being shown alongside
the later DYING state. Attack binding now takes both HP/life from its exact
owned life fact at the same authored HP anchor; the actual damage number is
unchanged. The new regression first failed at −2 versus native 0; all **45
affected tests** and changed-file types pass after the correction. Source
review approved the value selection, with no clamp or unrelated final-state
lookup. The final gallery was regenerated from this corrected binding.

**Source correction before implementation.** Mechanical DYING/STABLE are not
NeuroClient's animation FSM `Dying`. `mapLifeState` emits only the original
badges for mechanical dying/stable, and initial actors in those states use
Idle. FSM `Dying` plays Die on the way to frozen Dead. ReviveClip releases that
frozen presentation on an authoritative ALIVE transition; it has no stand-up
clip. The preceding audit's claimed missing DYING/recovery body was mistaken.
Do not carry it into a new implementation or invent a prone/get-up animation.

**Problems at entry:** seven existing lifecycle badge recipes
(four death-save outcomes, dying, stable, revived) were not consumed. An actual
death-save death outside an Attack/Cast jumped directly to the last
Die frame. A native `revive(hit_points=3)` was independently reproduced ending
at native ALIVE/3 HP but retained ALIVE/0 HP: the life event already carries the
missing committed `normal_hit_points`. These are presentation connections;
engine life rules, handlers, grants and turn progression remain their owners.

**Implementation sequence and boundaries:**

1. Read the source mapper/FSM/clips and actual native producers; independently
   verify the distinction above. Anti-slop review validates source meaning and
   finite cases. Anti-OOP review validates passive records, exact ownership,
   existing queue/clock/media and the import DAG before production changes.
2. Produce real histories from native injury, actual turn-start death saves,
   healing and explicit revival. Capture every separate root immediately and
   preserve actual ancestry/grants. Begin save histories at the already-injured
   baseline; use a native opportunity downing case to cover entry into DYING
   through an already-bound Attack. Verified seeds: 0→13/success, 1→5/failure,
   5→20/critical recovery, 31→1/two failures. No injected rules or forced rolls.
3. Parse the original death-save/life-state badge records and extract ordinary
   FeedbackTracks at existing causal anchors. Their source badge lifetime is
   decorative and introduces no join. Turn banners/result screens remain
   unconsumed context, outside this unit.
4. Consume committed life-event HP in the retained reducer, backed by the
   native revival regression. Carry exact life-event ownership from the
   existing Attack/Cast bindings. Bind only an uncovered DEAD transition's
   body interval inside the same choreography head. Reuse death clip/speed,
   body duration/sampling, scene media and actor drawing. Sample from the
   retained pre-transition contact so Die starts at frame zero. Existing
   attack/cast deaths must acquire neither a second body nor additional time.
   Apply uncovered life facts at their existing entry anchor. ALIVE naturally
   selects the current Idle body; preserve placement, equipment and visibility.
5. Inspect four-corner clips before/at/after transitions, including an actual
   death → idle corpse → native revival history and pause while latest is
   already revived. Verify absolute seeking, native HP/life, one visible body,
   final corpse frame, and independent badge lifetime. Run changed-family
   tests, existing lethal controls, live encounter checks, types and required
   import checks. Regenerate the full catalog, complete anti-slop/anti-OOP
   review, update the audit and commit this unit on the current branch.

**Finite catalog:** ordinary save success, ordinary failure, critical failure,
critical recovery, three-success stabilization followed by native healing,
failure/success/critical-failure death followed by explicit revival, a paused
version of that death/revival history, and walking opportunity damage entering
mechanical DYING. Reuse current scenario/catalog data and the same recorder.

**Acceptance:** exact natural-roll outcomes and native transition ancestry;
retained revival HP agrees with engine after teardown; authored text/colors
and zero extra badge wait; standalone Die advances from first to final frame
at its imported speed and retains contact/lift across corpse and revival;
owned lethal Attack/Cast timing stays unchanged; latest may contain revival
while paused historical state/pixels still show the earlier death. Default
death hiddenSlots/media are empty: selected nonempty fields remain explicit
gaps instead of adding an equipment controller or media executor here.

**Scope discipline:** no new mechanics, subjectivity rules, queue, clock, FSM,
per-spell executor or body authoring. Projectile DYING/STABLE support and
nested healing HP timing require their own actual delivery coverage and are
outside this unit. The three unchanged legacy architecture-test failures
remain recorded results, not prerequisites or a repair campaign.

### Bounded session — native condition lifecycle and recovery

**Status:** the six primary cases and bounded standalone healing extension are
implemented, externally reviewed and validated. Execution was
authorized after independent external review of the
written plan at `43b4ca0`. Both fresh reviewers approved its native producers,
scope and ownership. They required assertions for the exact applied-versus-
removed memberships while paused, placement at every intervening root and
resumed movement entry, and real separate expiry roots in completion order.
Native removal targets identify the recovering actor even when the event's
source is the original reactor. Instant equal-alpha transitions stay instant.
The implementation starts from the human's checkpoint `58b0946`. The human requested a
work unit suitable for a few hours without interactive supervision. Target
roughly 2–3 hours of useful work, finishing when the acceptance cases pass;
time is a planning estimate, not a reason to add more systems or code.

**Primary result (committed as `20f58db`):** full gallery `20260910T175626Z-4e0063` passes **28/28**,
retaining the previous 22 cases. The existing mechanics, reducer, choreography
and placement owners already handle the continuing lifecycle; no production
gameplay changes were needed. New native producers retain all separate roots,
and regression coverage checks every boundary, actual body color and resumed
motion timing. Paused capture now compares a hash of the RGB bytes actually
encoded. Both external reviewers approved the implementation after those
assertions were strengthened. The focused lifecycle/placement/feedback/live
encounter group passes **28 tests**, native history/attack/movement coverage
passes **32 tests** (overlapping groups), changed-file Pyright reports no errors,
and both import-direction/DAG checks pass. Four-corner boundary pixels were
inspected for held jump lift, failed-save color, instant removal and Dodge
expiry. The only gallery media gaps remain the previously reported Goblin
ranged body/slash. Details are in the composition audit.

**Outcome:** the same real character is interrupted, remains restricted while
paralyzed, recovers through the engine's own later save/removal, and resumes a
discovered legal action from the retained visible pose. Produce reviewable
four-corner videos for the whole sequence, including intervening real turns.
This closes the gap between isolated reaction clips and a continuing game.

**Known owners to reuse.** `GhoulParalysisEffect._repeat_save` in
`dnd/monsters/traits.py` already reacts to TURN_END/EFFECT and creates a native
CON10 save. Success calls existing condition-tree removal, including its
Paralyzed child. `Encounter` owns turn progression. `game/presentation.py`
already retains/removes exact condition UUIDs; `game/choreography.py` already
binds condition descendants under technical roots. Original Studio condition
records own appearance/removal/feedback. `game/visual_position.py` and the
shared frame compositor own the stopped visual pose. `ReviewSequence` and the
recorder already accept multiple complete roots.

The current `movement_with_paralysis` producer closes the encounter after its
first movement. Existing placement tests supply a passive prior pose to a
separately generated move. Extend that proof with an actual native sequence;
do not assume a new condition lifecycle implementation is needed.

| Catalog case | Native sequence and observable result |
| --- | --- |
| Walking recovery | Move → opportunity paralysis → successful end-turn repeat save → owned condition-tree removal → mover's next turn → Disengage → Move. The new motion begins at the held visual contact and reaches its committed tile. |
| Jumping recovery | The same lifecycle with Jump. Retain body lift through intervening roots and begin the next authored movement from that pose. |
| Paralysis persists | Initial paralysis → failed repeat save → next turn. Exact condition memberships and real action restrictions remain; there is no invented visual recovery. |
| Delayed recovery | Failed repeat save, then successful save on a later native turn → next turn → Disengage and movement. Distinct saves, removals and turn roots remain distinct. |
| Natural expiry control | Discovered Dodge → another participant's real turn/action → owner's next turn → native expiry. Reuse the existing expiry scenario in `test_gameplay_history.py`. |
| History behind latest | Pause historical playback during the walking recovery sequence while latest already contains removal and resumed movement. Historical membership, placement and pixels remain tied to the paused point. |

Use public action discovery/execution and actual turn progression. Discover
Disengage before the recovered movement so a refreshed opportunity reaction
does not obscure this case's purpose. Preserve the real Disengaging condition
and its roots. Select deterministic seeds by observing native save outcomes;
do not replace handlers or force completed event values. Parameterize the
existing finite scenario/catalog data instead of adding one executor per case.

**Execution checkpoints:**

1. **Trace the concrete sequence and review ownership (20–30 minutes).** Read
   the native repeat-save/removal/turn owners, existing expiry test and relevant
   NeuroClient ConditionClip/MoveClip/JumpClip behavior. Record the actual root
   order, child relations and observed conditions at each boundary. The
   anti-slop reviewer checks that this is an integration gap with a real
   observable outcome. The anti-OOP reviewer checks the selected owners before
   shared production contracts change.
2. **Produce and retain native histories (35–50 minutes).** Keep the encounter
   alive through the selected operations. Capture each operation before the
   next runs, including separately completed turn/expiry roots. Reuse existing
   public capture patterns and `ReviewSequence`. Save an initial retained
   baseline and actual lineages, then close/reset the engine. Keep independent
   roots separate; use their original parent/child identities within each root.
3. **Connect only demonstrated gaps (30–45 minutes).** Replay through the
   existing reducer, bindings, feedback tracks and frame sampler. If a concrete
   case fails, use `bug-fix`, identify the actual owner and correct that shared
   contract. An already-working owner needs evidence, not a replacement.
   Check fresh HP/gear/conditions with retained placement, source removal timing
   and the next movement's start. Clearing a condition adds no new landing or
   gravity rule. Run the affected behavioral checks after a correction.
4. **Validate and capture the unit (30–45 minutes).** Run the six cases through
   the shared recorder in all four corners. Validate actual state/UUIDs,
   head transitions and legal versus rendered positions. Inspect the pixels
   around application, failed save, removal and resumed movement. Retain the
   current gallery cases and regenerate the full catalog at completion. Run
   the existing live paused-encounter regression as the separate proof of
   independent intake; the offline pause clip does not replace that proof.
5. **Review and close the checkpoint (15–20 minutes).** Anti-slop review checks
   the actual source/trace/pixel evidence, honest coverage and absence of
   condition-name patches. Anti-OOP review checks passive histories, ECS/public
   producers, the import DAG and one owner each for queue/clock/placement.
   Resolve concrete findings, update this plan/audit with results and limits,
   and commit the validated unit separately from `58b0946`.

**Acceptance:**

- Every save and removal is earned by a native operation. The exact wrapper
  and child UUIDs remain after failure and are removed by the successful tree
  removal; final retained state agrees with captured native after-values.
- Discovered choices reflect actual restriction and recovery. Mechanics are
  not inferred from sprite color, HP labels, recipe names or playback time.
- Historical color, badges and membership remain correct while latest is
  ahead. Pausing/seeking uses retained values after the engine has been reset.
- The rendered stop contact/support/body lift survives intervening turn and
  condition roots. The next movement starts there, retains its authored timing,
  and finishes at the actual committed endpoint. Legal positions remain engine
  facts throughout.
- All six new cases produce four-corner MP4s and exportable traces with source
  identity, native root ancestry and frame evidence. Existing cases remain
  present; automatic success and human visual approval remain distinct.
- Relevant lifecycle/placement/feedback/encounter regressions, changed-file
  type checks and dependency checks pass. Fix a demonstrated failure at its
  shared owner; do not turn observations into a speculative repair backlog.

**Bounded extension if the core unit finishes early:** connect the original
standalone healing feedback context as one shared capability. The native
`receive_healing` producer already provides capped `actual_healing`, committed
HP and authoritative life-state children; the reducer consumes those facts.
The original `actionContextPresentation.json` healing context specifies no
body clip or media and a green number with a 900 ms decorative lifetime. That
lifetime does not delay the lineage: original HealClip patches HP at entry,
and the default empty body/media add no wait. Preserve any actual life-state
children. Study and consume that context through the existing schema/feedback
lane, reporting any selected
unsupported field honestly. Validate an injured living actor healed to its
cap and a dying player restored by native healing. A dead actor's revival is
a different native contract; healing must not invent it. This extension is
conditional on completing the six primary cases and their reviews, and must
not become individual spell/VFX work.

The extension completed after the primary checkpoint and independent review
of the selected healing contract. Original `mapHeal` also
maps the actual life-state child to ReviveClip/`Revived`. The badge was unported
at this checkpoint; the later life-transition unit connects it. Its source
review corrected the previous recovery-body concern: mechanical DYING/STABLE
correctly draw Idle, and ReviveClip releases frozen Dead without a get-up clip.
This cut added the original healing feedback context
and native entry state through the existing zero-duration head. Feedback can
retain an inherited child anchor, but nested healing's HP-at-entry timing is
not yet implemented by the attack/cast sampler; report that selected gap
without claiming this standalone proof covers it. Neither gap calls for an
invented animation or a new timing system in this unit.

**Final gallery:** `20260910T181136Z-be08be` passes **30/30**. All 28 clips from
the primary checkpoint have identical frame counts and RGB pixel hashes after
the healing connection. The two new healing clips were inspected in all four
views at entry and after head release. Their original green number, capped
amount and retained native HP/life results agree. The run's
`inspection/verification.json` records the comparison; captures/traces and
known gaps remain in the normal review/export interface. Healing native tests
plus lifecycle history: **7 passed**; healing playback/capture: **4 passed**;
existing animation/movement/equipment/feedback: **120 passed**. Changed-file
Pyright is clean. The broader architecture module passes 19 checks, including
DAG/direction, with three failures in unchanged checkpoint server/schema code;
the composition audit records the exact findings without expanding this unit.

**Autonomy boundary:** proceed through these checkpoints without interactive
milestones. Ordinary integration defects stay inside this unit and get solved.
If a new rule/design decision is actually required, record the concrete trace
and decision, continue the other independent cases, and leave that disputed
case explicitly incomplete. Do not rewrite subjectivity, handlers, event
progression or authored timing to make a scenario convenient. Do not add a
second lifecycle controller, condition timer, queue, serializer framework or
per-spell executor. Additional art and map authoring are outside this unit.

### Completed gallery feedback — interrupted poses and legible feedback

The human observed a lethal opportunity attack snapping the corpse back to the
legal tile center. Keep authoritative positions and Step results intact;
preserve the rendered stop/death contact through head completion and later
idle frames. Study the equivalent walking/jumping/paralysis boundaries and
the next action's attachment before choosing the shared correction. Review
the imported Paralyzed color recipe against NeuroClient, and report what it
actually applies. Place floating feedback clear of the animation, choosing
above/below according to screen space instead of covering bodies or clipping.
The anti-slop reviewer checks real captured cases and removes assertions that
mistakenly equate visual contacts with legal tile centers. The anti-OOP
reviewer checks that retained visual placement belongs to playback, with no
backend animation data, second mechanics implementation or new clock/queue.
Regenerate the affected four-corner clips for human review.

**Finding and selected correction:** NeuroClient's Move/Jump completion also
restored the authoritative origin. The human explicitly superseded that
behavior: an uncommitted Step keeps its legal origin while playback retains
the contact at which the reaction stopped. This affects living paralysis and
lethal walking/jumping reactions. Playback owns a small geometry-only placement
map alongside facings; fresh historical actor facts and visibility still own
HP, conditions, gear and admission. A later legal relocation supersedes the
placement; a later bound motion starts at the visible pose. Body lift is
separate from support elevation so actors and their attachments agree while
shadows stay on the support plane. Head completion uses the same global idle
clock as the following idle frame. There are no new landing or gravity rules.

The Paralyzed appearance is unchanged original data: no RGB tint, saturation
`0.35`, brightness `0.86`, alpha `1`. Pygame's color transform matches the
NeuroClient filter. `Ghoul Paralysis` is a state-only wrapper without its own
body color or feedback. Floating messages and actor labels now share placement
against actual nontransparent body bounds: above first, below when necessary,
clamped to the usable viewport and stacked away from other labels. Recipe
timing, text, fonts and opacity are preserved.

**Correction validated 2026-09-10:** full run `20260910T164415Z-666bea`
passes all 22 capture cases, with 88 views and 1,881 frames. The existing Goblin
ranged body/slash media gap remains the only reported gap. Side-by-side trace
checks for walk/jump × death/paralysis show identical actor screen coordinates
before completion, at completion and on the next idle frame in all four views;
the old run visibly changed those coordinates. Evidence is in
`.runtime/animation-review/interruption-validation.json`, with a four-corner
feedback frame at `.runtime/animation-review/paralyzed-feedback-four-corners.png`.
Movement, placement, text layout, recorder, encounter, geometry and original
timing regressions pass, as do import-direction/DAG checks and changed-file
Pyright. Anti-slop/anti-OOP review found no blocking issue. The capture records
the exact game/devtool source hash used for those frames. Review the new run at
`http://127.0.0.1:8767/runs/20260910T164415Z-666bea/index.html`.

**Visual review checkpoint — requested 2026-09-10.** Maintain a named catalog
of real standardized event sequences and generate tagged video snippets plus a
local HTML review gallery with one command. The reviewer can play the clips in
parallel, pause/seek, mark a case and time, add a note, and export the selected
cases' debug traces. Preserve run/source identity so feedback refers to the
pixels and retained facts that were actually reviewed.

The user's current emphasis is **engine as clip extractor**. Execute each
scenario once and sample all four camera corners at the same presentation
times in one pass. Encode a synchronized 2×2 video per case. Every recorded
frame retains the common state and each corner's draw evidence. This visual
checkpoint is the immediate work; the encounter remains the shared source of
playback behavior. Run the affected catalog cases at each implementation step,
and the full catalog at a checkpoint; human visual approval remains separate
from automatic state/capture checks.

The implemented entry is `python -m devtools.animation_review`, with 22
catalog entries under `devtools/animation_review/catalog.json` and instructions
in its README. The local `.serve` entry supports video byte ranges, so browser
frame stepping and pinned-time seeking work. Each unique generated run keeps
its clips, traces and source hashes; exported reviews include the selected
frame index, all four view samples and the actual retained root identity.
The shared scene composition was extracted from `game/encounter_play.py` into
`game/playback_frame.py`; clocks, queues and head transitions kept their owners.
The scenario builders were moved into shared test support without importing
pytest into the extractor or test support into the game.

The anti-slop/anti-OOP review corrected two recorder gaps: source hashing now
includes the consumed `content_data` visual ledger, and unbound movement remains
an explicit coverage failure. The full capture also exposed a Fire Bolt trace
serialization error; using the existing typed authoring serializers preserves
its frozen maps. Six recording/HTTP tests pass, including that real cast; 52
scenario regressions, six encounter checks and four import-direction/DAG checks
pass. Browser checks cover parallel playback, native fullscreen, pin/step,
per-run review persistence, complete exports and visible failure handling.
These checks do not approve the animations visually on the human's behalf.
The completed full run `20260910T150620Z-42c3df` records all 22 cases successfully
as four-corner videos (88 views). Its manifest/traces are under
`.runtime/animation-review/runs/20260910T150620Z-42c3df`; the only reported media
gaps are the existing fixed Goblin ranged body/slash clips. The browser review
URL is `http://127.0.0.1:8767/`, served by the local review tool. Future runs get
their own directory and become the latest report at that URL.

Use existing public scenario producers, retained lineages, reducers and the
same Pygame scene sampling/drawing as the game. Extract the existing frame
composition only as needed to share it; do not create another animation
implementation. Keep catalog entries as data. Initial coverage includes melee,
ranged, walking/jumping opportunity reactions (save/miss/paralysis/death),
existing casts and repeated targets, varied camera views, and reduction facts.
Each clip records its seed/setup, actual complete event ancestry, authored
anchors, sampled states, gaps and validation results. A failed capture or check
must remain visible in the report. Generated videos/traces stay under ignored
`.runtime`; checked-in code/catalog and instructions make each run repeatable.

The **anti-slop reviewer** checks whether the gallery makes failures selectable
and exportable, rather than merely showing attractive clips, and whether adding
a case reuses existing producers. The **anti-OOP reviewer** checks shared frame
ownership, passive trace data, original lineage identity, no engine imports of
review tooling and no additional gameplay clock/queue. Validate generated media
and the review/export flow as well as the existing encounter regressions.

**Current correction — reaction composition and ranged delivery.** A successful
encounter demonstration is not evidence that the authored degrees of freedom
survived the port. Compare original Move/Jump, Attack, TakeDamage and Condition
recipes/primitives with the Python owners. Restore the complete reaction-child
join and its authored effect anchors; validate a real configured longsword
paralysis rider, successful saves, death and continued movement using actual
committed Step facts. Implement the existing ranged attack recipe in the same
chunk. Keep condition rules and continuation decisions in the engine.

The anti-slop reviewer must distinguish imported-but-unused data from executed
data, and reject content-name branches or flattened child effects. The anti-OOP
reviewer must check passive composition, original causal identities, the import
DAG and the single historical-head owner. Document coded event-family reduction
semantics honestly; moving them into arbitrary JSON would not by itself recover
the authored animation design. The source has condition recipes, but no current
general weapon-on-hit spell executor was found; a configured existing paralysis
rider is not a full Hold Person spell.

This supersedes the spell-by-spell expansion order and the suggestion that the
next main task should be another terrace VFX correction. Keep existing hard
terrain regressions, but develop and exercise gameplay on flat, bright land too.

1. **Use current game composition.** Build the existing direct fighter and
   sorcerer premades, canonical Goblins, a current bright battlefield, Game and
   Encounter. Install the existing opportunity-attack hook and native enemy
   controller. Do not revive obsolete player-creature catalog references or
   build a second rules system. Live session values belong to the application;
   rendering continues to consume retained facts.
2. **Connect complete gameplay histories.** Capture every actual root completed
   by each public action/controller/turn operation, then retain each root's own
   lineage. Extend the existing family capture/reducer for movement, attacks,
   rolls, condition lifecycle and turns using actual observed payloads. Senses
   already owns committed positions. Retain state facts and existing grants;
   do not copy live condition/handler/value graphs or invent a simulated condition.
   Ordinary causal/log-only events remain visible in coverage without owning
   duplicate mechanics.
3. **Replace fixed input with discovered choices.** The existing
   `get_available_actions` / `execute_available_action` boundary supplies action
   rows, typed targets, paths, costs and target allocation. Add a simple Pygame
   action/target surface and End Turn. Human commands wait for their settled
   presentation boundary; native enemy decisions can proceed ahead. One pending
   lineage deque and one active historical head remain the owners. Scripted
   validation uses this same command boundary.
4. **Represent the whole encounter.** Draw all known historical actors, resources,
   conditions and outcome text. Use existing authored body/movement/feedback
   contexts and installed spell capabilities; missing decorative media must not
   halt game progression. Asset completeness is explicit and separate from
   semantic/state coverage. Do not turn unknown recipes into fabricated authored
   VFX, silently lose their actual consequences, or create one executor per spell.
5. **Validate arrangements and play, not just one effect.** Use data cases for
   flat land at several distances/directions, swapped caster/recipient positions,
   all four cameras, and raised/lowered support. Execute movement, attacks,
   actual reactions, condition application/expiry, player changes and native
   enemy turns. Verify latest can advance during paused history and that player
   input resumes on the corresponding displayed state. Inspect real windows.
   Shared space defects belong to projection/depth owners; don't retune every
   spell against the same difficult stair.
6. **Keep asset work independent.** Dedicated work may import already-authored
   CodexFX exports and extend shared presentation capabilities. Existing source
   materializers/catalog mappings choose assets and recipes. Preserve their
   provenance and distinguish saved authoring from generated fallbacks. No Godot
   authoring or individual spell polish becomes a prerequisite to the game lane.
7. **Review the structure at working checkpoints.** Anti-slop review asks whether
   a change advances actual gameplay or merely expands a demonstration. Anti-OOP
   review checks existing ECS/public owners, passive histories, no second queue,
   and the import DAG. Use actual traces and playable results; do not accumulate
   hypothetical repair prerequisites. Continue the game work when an asset task
   finishes or the user asks a question.

**Current source findings:** direct premades already install standard actions and
publish their own births. Canonical Goblins need their normal composition call.
The obsolete encounter assembler's player-creature reference is unavailable;
use current direct builders without restoring it. Native controller action
boundaries already support independent enemy progression. Public probes emit
Move/Step, Attack/OA, Jump, damage-roll/applied facts, condition markers/expiry and
independent turn/round roots. These observations guide family-level integration.

## Playable checkpoint — 2026-09-10

`python -m game` now opens the actual encounter. The finite spell programs are
explicit references (`--reference`, `--magic-missile`, and their existing options).

| Owner | Connected behavior |
| --- | --- |
| `game/session.py` | Direct fighter/sorcerer builds, canonical Goblins, current Game/Encounter/native AI, actual action discovery, execution and terminal roots. |
| `game/controls.py` | Discovered actions/targets, multi-target allocation, map previews, costs/reasons and End Turn; no mechanics or scheduling. |
| `game/presentation.py` | Passive movement, attacks, conditions, HP, senses, corpses and turn histories, retaining actual grants and causal identities. |
| `game/encounter_play.py` | One pending deque and active historical head. Native decisions advance independently; human commands require the displayed human boundary. |
| `game/motion.py` | Original walk/jump clocks and heights; complete shared reaction groups, committed continuation or retained interrupted visual contact. |
| `game/visual_position.py`, `game/playback_frame.py` | Passive placement distinct from legal tiles, carried through head completion/idle; one shared game/review frame compositor. |
| `game/attack.py` | Original profile selection, melee contact/ranged release and body/delivery/damage join. No per-weapon implementation. |
| `game/choreography.py` | Shared standalone/reaction subtree compilation, authored child anchors and postorder recovery joins. |
| `game/scene.py`, existing drawers | All known historical actors, actual equipment/rig layers, visible conditions, HP, feedback and shared map projection. |

The independent art lane imported the existing CodexFX Rune Dart, the actual
premade appearance layers, and existing modular/Goblin movement and attack
clips. No new artwork was authored. The bright map's stone floor uses four
original Ground D1 poses, with source hashes in `game/data/stone_floor_source.json`.
The current local sprite totals are 273 NeuroClient PNGs (37.7 MB), one CodexFX
PNG (0.36 MB), and 14 fixed-rig PNGs (1.78 MB); these totals include earlier work.

Three integration corrections came from actual play, not injected mechanics:

- Portable-torch movement emits `SpatialChangeEvent.LIGHT_CHANGED` with a Tile
  identity. Capture must not classify that identity as a character.
- A dead actor's later TurnEnd can lack identity grants. Existing encounter
  projection retains the transition and hides the acting identity; capture now
  follows that rule instead of rejecting the entire operation.
- An observer can witness an opportunity attack and then die during it. Its
  historical attachment can use that child lineage's own initial grants;
  terminal grants and actual sensory removal remain unchanged.

Public validation covers a full round with paused history and independent enemy
progress, four flat layouts/cameras with swapped roles, real melee and A/B/A
volleys, and an actual encounter ending in round two. The ending run checks
movement/action/slot costs, condition membership, exact retained HP and closed
input afterward. Real X11 captures and results are in
`.runtime/encounter-layouts/validation.json` and
`.runtime/encounter-layouts/x11-completion-summary.json`. Pure history tests
also replay these retained facts after engine reset.

Validation results: the broad game suite completed with 471 passing tests and
two failures. The asset expectation now includes the four added stone poses;
all 49 asset checks pass. The remaining failure is the older door/light demo's
eight-second fresh-process startup budget: its functional assertions pass, but
an isolated normal-cache run takes 8.596 seconds on this workspace. Profiling
shows imports, tile construction and filesystem validation dominate; it does
not establish a new gameplay regression. The budget was not weakened. After
the final integration changes, 50 focused gameplay/history/drawing checks pass;
the encounter-completion check also passes. Changed production modules pass
Pyright, and the import-direction/cycle checks pass.

The anti-slop/anti-OOP checkpoint corrected stale input-readiness reporting,
starting a new head while paused, unreported unsupported payloads, and conversion
of jump lift from NeuroClient reference pixels. There is no new backend clock,
rules dispatcher, event registry, synthetic action root or second playback queue.

**Practical limits remain explicit:** the current encounter retains one player
viewpoint and an initially known actor set. Unbound action presentation shows
the actual resulting state/projected log and records coverage; it does not
invent authored media or block the engine. Shortbow/projectile delivery and
Jump reactions now use the shared composition. The current Goblin pack has no
bow body clip; it displays Idle with an explicit media gap while its authored
ranged delivery and damage play. The pre-motion reaction badge now executes.
Area/self/persistent spell presentation and broader roster/map/inventory UI
remain shared capability/content work. These are not prerequisites for each new
spell and must not turn into individual spell-polishing sessions.

The next implementation checkpoint should choose a **shared missing gameplay
capability from actual play**, consume its existing authored data where present,
and repeat the same full encounter, varied-space and history checks. Continue to
keep asset work parallel to that main lane. Do not call this first playable
encounter completion of the entire D&D game.

## Reaction composition checkpoint — 2026-09-10

The source comparison and honest coverage inventory are in
[ANIMATION_COMPOSITION_AUDIT.md](agent_docs/ANIMATION_COMPOSITION_AUDIT.md).
Imported JSON is not evidence that every field executes. Three spell drafts are
bound locally; Fire Bolt and Magic Missile execute, while Acid Splash requires
the unimplemented area primitive. Five attack recipe rows load, three with
selectable variants; the original source contains 88 action recipe rows.

The shared compositor keeps the actual hierarchy through technical events:
movement edge → reaction → direct on-hit or nested damage effects. Conditions
use their owning contact/condition frame, actual UUID membership and original
appearance recipes. Postorder composition waits for the complete children
before cast recovery. Neither continuation nor timing uses a condition-name
switch. Exact creature-to-rig associations now live in the packaged rig data.

The native longsword test configures the existing paralysis rider with its real
CON10 save. A failed save stops a living mover, a successful save or miss permits
the actual committed continuation, and death stops the edge. These outcomes
are checked for both walking and jumping after engine reset. Changing only the
Paralyzed alpha/duration extends the reaction join without changing engine facts.
A separate real Fire Bolt/concentration-removal lineage verifies that an
authored long fade delays cast recovery while release/impact/HP anchors stay fixed.
There is still no general item-on-hit spell executor; the configured rider is
not advertised as a full Hold Person proc.

All 141 original condition rows round-trip through the typed schema. Current
execution covers body color, alpha, composition and transition feedback;
equipment modifiers/replacement layers and other unimplemented domains remain
explicit. The Pygame adapter preserves the source per-slot color matrix,
hit-flash precedence and whole-actor alpha. Decorative feedback uses passive
tracks on the existing presentation clock, retains its frozen launch anchor and
outlives a finished root without delaying it or adding another action queue.

Verification: 40 combined attack/movement/condition/feedback checks pass, plus
two native cast-recovery cases. A final five-case feedback run adds a real
opportunity-reaction badge toggle check: authoring controls its display without
changing movement timing or the settled state. Six full-encounter cases and 13 existing
cast/equipment/history integration cases pass. Ranged coverage also includes
20 map arrangements/views and four settled death frames. The earlier shared
animation/source regression run passed 147 cases. Changed production modules
pass Pyright and all four selected import-DAG/direction checks pass.
The paused encounter test's frame guard is now 240: the actual newly animated
ranged attacks and Jump legs settle at frame 202; its state/timing assertions
were preserved. Evidence lives under `.runtime/reaction-composition`, including
32 real X11 frames of held reactions, condition appearance and final positions.
The final X11 encounter run ends in victory at frame 200, with all 26 retained
lineages settled and historical state equal to latest. Its only media gaps are
the fixed Goblin rig's missing ranged body/slash clips; captures and the exact
result are in `.runtime/reaction-composition/final-encounter.json` and the
adjacent `final-encounter` directory.

The anti-slop/anti-OOP review is recorded in the audit. Remaining source
capabilities should be connected through these owners, never through a growing
collection of spell-name or creature-name branches. Nested casts share the
compiler path but do not yet have a native weapon-proc gameplay test.

## 1. Authority and evidence

- [HISTORY_BEFORE_ME.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/HISTORY_BEFORE_ME.md) records historical intent, the failed architecture, July reconstruction and the overnight experiment.
- [CURRENT_CODEBASE_STUDY.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md) records present owners, source coverage and observed behavior. Its injected diagnostics and unverified concerns are not an implementation backlog.
- This plan defines the current objective, implementation sequence and acceptance. The appendices retain completed source/data/timing work so it is reused.

Read the affected owner notes and actual code before editing. The [branch guide](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_BRANCH_DESIGN_GUIDE.md) and [in-process architecture roadmap](/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md) locate the existing architecture. Old branches and NeuroClient are references for intent, not replacement runtime dependencies.

A requirement belongs in the active work when it follows from the user's design or the concrete behavior being implemented. A gameplay bug needs a named mechanic, its supported interception point and an observable violation. A diagnostic that installs an arbitrary handler does not establish those semantics by itself. Optional robustness work becomes necessary when the selected caller or adapter actually introduces that exposure; it is not an automatic prerequisite to the first integration.

## 2. Foundation already available

| Area | Existing work to use | Actual integration work |
| --- | --- | --- |
| Mechanics | Entity/component composition, actions, conditions, modifiers, handlers, resources, spatial owners, Game and Encounter | Invoke the current public owners and retain their results. |
| Causality | EventQueue versions/lineages, parent-child references, reaction-trigger links and multi-target application identity; selected completed-cast capture | Feed retained casts to the application. Add other causal shapes when their gameplay case is selected. |
| Subjectivity | Event-time grants, senses/contact history and subjective combat-log projection | Apply existing disclosure meaning to the finite facts needed by this presentation. |
| NeuroStudio data | Original JSON plus output from the original offline TypeScript materializer | Load the local records through Python; do not remake recipes or generated defaults. |
| Animation | `compile_cast`, `sample_cast`, `crossed_anchors`, Python data loader/drawer and real cast binding in `game/combat.py` | Use the bound historical input in actual map playback. |
| Actor history | Explicit known-actor startup, passive actor facts, shared latest/historical reduction and authored appearance binding | Connect these values to the frame pump; demonstrate changing gear/contact when those actions are selected. |
| Height and rigs | Detached G5 support/duration adaptation, modular root rig and Goblin recipient rig | Use their metadata with actual map composition and actor identity. |
| Current Pygame app | `game.play` integrates input, independent latest reduction, historical playback and the existing map painter; `game.app.run` retains the door/light regression demo | Extend the selected combat outcome using these same owners. |
| Creature content | Existing declared builders and canonical creature materialization, including Goblin | Use the current creation/composition/deployment path and bind identity to presentation. |

The old P1/P2/G5 labels describe completed reference work. Their evidence is in appendix A; they are not tasks to restart.

## 3. Design commitments

### Existing mechanics remain authoritative

Entities compose data and systems. Conditions, modifiers, receipts, handlers, equipment and spatial effects retain their concrete owners and exact cleanup identities. Presentation must not reroll, apply conditions, tick durations, decide death, simulate targeting or manage a second copy of mechanics.

Interception is defined by the concrete Event family and producer. Counterspell interrupts CAST_SPELL/EXECUTION; Shield blocks the child TAKE_DAMAGE/EXECUTION; Death Ward modifies TAKE_DAMAGE/EFFECT before HP changes. DAMAGE_APPLIED records an already committed result. The same phase name does not imply universal cancellation, rollback or refund semantics. Preserve committed costs and the actual resulting lineage.

### Render complete lineages

Use the actual version UUIDs, logical lineages, parent-child references and explicit reaction-trigger links. Multi-target applications retain their existing identity, including repeated A/B/A targets. Fire Bolt does not need an invented AttackEvent child or a new application ID.

A delivery batch is not a render job. Follow the selected producer through its real required children and completion. Completeness follows the observer-permitted lineage being presented, using the existing relationship semantics.

### Retain the facts the presentation consumes

Latest backend state may advance while old work is on screen. Historical HP, life, support/contact, identity and equipment therefore cannot be fetched from current live entities during playback.

For each consumed fact, identify its producer, observation authority and capture boundary. Use existing passive values such as damage resolutions, item facts and sensory snapshots where applicable. Keep the existing finite ordinary Event space; do not introduce a parallel cue taxonomy or a universal object serializer.

For the selected cast, `capture_lineage` runs after the synchronous public operation and copies the consumed terminal facts from its actual descendants. This boundary preserves the values the current consumer needs. Reconsider a field's capture point when a selected gameplay case demonstrates a different lifetime.

Use the existing subjectivity rules without changing permitted detail. Unknown source, identification and location have distinct meanings. Resolve representation questions for the consumed family with valid examples and affected consumers; do not solve global source nullability or change information policy to make a fixture easy. The first fully observed cast can establish the connection without claiming unknown-observer support is complete.

### Separate current reduction from historical playback

Maintain latest subjective state and the historical state for the active lineage. The same reducer meaning should produce both latest results and the expected successor of the displayed history. Pending work retains facts; it does not need a world snapshot per action.

The active animation uses its own historical actor/contact/result values. Later reduction cannot change its elapsed time, gear or endpoints. When that animation finishes, the following lineage starts from the corresponding historical result. Preserve one owner of pending causal work and one active head; the sampler does not acquire another pending queue.

Use current cursors and generation information where the actual application needs them. The retained cast reducer already produces both latest and historical successors; the application should use that same operation.

### Preserve authored execution, space and rigs

NeuroStudio already defines preparation, body release, travel, impact, feedback, recovery and their overlap. Use the existing Python compiler/sampler and original timing oracle. Absolute elapsed time preserves pause, seek and large-delta behavior; queue depth never retimes the animation. TypeScript/Godot remain offline tools, not runtime requirements.

Packaged sprite groups map clips, rows, frames, FPS, slots and pivots to the root modular vocabulary. Use real clip capability and data overrides where necessary. Historical equipped items are distinct from temporary authored hiding/glow. Fixed sprites do not gain removable gear layers.

Use the existing 2.5D supports, map projection and painter ordering. The implemented G5 duration metric stays independent of camera movement. Engine range, visual travel distance, sprite padding and draw depth are different quantities; do not redesign them as one metric.

## 4. Earlier connection sequence — retained implementation evidence

### Step 1 — Close the first real lineage's contract

**Implemented for the selected known-actor positive hit.** The field mapping and actual public trace are in the [first cast contract](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#first-cast-integration-contract--2026-09-09). The requirements below record that completed work.

Use one public Fire Bolt cast between known actors with the unchanged imported recipe. Start with the already-supported positive hit. Record only the facts needed to connect that real history to the sampler:

1. The public action/Encounter entry, actual root and child order, damage result and relevant life/contact changes. Reuse the existing hit/death traces; investigate only a missing junction.
2. A compact field mapping: source owner, permitted fact, capture point, passive representation, reducer use and authored consequence.
3. Historical actor/appearance/equipment/support initialization through current owners. Identify which values are already supplied and which finite binding is missing.
4. The files/functions that change and one concrete retained input example. Check the design with anti-slop and anti-OOP reviewers before editing shared contracts.

**Exit:** we can explain this actual cast from public input through its retained complete lineage to the existing `CastInput`-level requirements.

### Step 2 — Capture and reduce that history

**Implemented and verified for that case.** `seed_actors`, `capture_lineage` and `reduce_lineage` retain the startup/history and produce separate successors. Replay after engine reset passes.

Extend [game/presentation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py) at the selected boundaries. Reuse EventQueue and existing information/log owners. Retain final accepted facts that the chosen reducer consumes, preserving exact causal relationships. Observation-only combat text continues through the existing log path; do not synthesize mechanics from prose.

Keep mechanics synchronous within each public operation. The async application yields between ordinary operations. Determine the selected lineage's completion from its actual producer/children. If a consumed required fact is missing or capture fails, report that failure; do not silently claim a complete cast. This does not require a fault-recovery or transaction framework.

Extend the current passive presentation data with the actor/vital/contact values this case needs. Keep latest reduction separate from the active historical scene; never alias a mutable latest target into that scene. Reuse one reduction meaning rather than implementing the rules twice.

**Exit:** the actual cast's retained facts survive later backend mutation and reduce to its expected values. No live Entity/GridMap lookup or rule execution occurs during that retained replay. This checks the selected families, not arbitrary engine-object serialization.

### Step 3 — Bind the existing authored executor

**Implemented and verified for positive hits and ordinary misses.** `bind_cast` supplies real contact, support, appearance, result and causal identity to the existing compiler. `resolve_actor_layers` uses existing rig metadata and the authored equipment ledger. The integration fixture uses stationary, unequipped modular actors; equipment variants and fixed-rig layers have separate binding tests.

Use semantic identity bindings to select the imported recipe. Adapt the existing [animation_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_types.py), [animation_data.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py) and [animation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation.py) inputs only where the real history exposes a fixture limitation: absent single-target application ID, historical appearance/contact, or exact consequences.

Normal HP, temporary HP, packet damage and life state remain distinct facts in presentation state. A projectile arriving does not infer damage or death. Use actual child results without also applying aggregate totals. Preserve the source's joins, anchors, equipment overrides and disabled settings. The detached preview remains a reference.

**Exit:** the real retained positive hit uses the same compiler/sampler as the existing preview and matches its authored timing. Check immediate death when that selected result is added; use the actual later life fact. Extend other outcomes when selected, without claiming the first hit proves them all.

### Step 4 — Connect the same-thread frame pump and actual map

**Implemented for the selected two-cast scene.** `game.play` owns input time, one pending lineage deque and one active historical cast. `game.app.draw_frame` accepts already-built draw commands; it does not import animation schemas or own playback. The shared painter places boundaries at their actual half-edge sort contacts while preserving authored image pivots.

Read the affected [game/app.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/app.py) drawing/projection helpers before editing; the earlier study did not reread all of them. Intake/reduction can advance while Pygame handles input/camera and samples the current historical animation. Preload required media before starting its visual clock.

Integrate [animation_draw.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_draw.py) into the existing map painter. Reuse current support/shadow/depth conventions and the G5 adapter. Check an actual raised/lowered support and a wall/door/cliff occlusion case; detached stage rendering alone does not prove map composition.

Reuse ordinary sample → draw → display.flip → progress accounting. The displayed values/pose must match the current historical result before starting the next head. The sampler remains a pure function of its retained input and elapsed time, with authored durations controlling playback.

**Exit:** the selected cast appears on the real map with correct contacts/depth and authored timing. Camera rotation changes projection without changing duration. Existing map/door/light behavior remains correct. Run the existing loader/drawing checks and add only integration-specific coverage.

### Step 5 — Prove independent progression and open the next capability

**Application proof now passes.** `test_combat_play.py` exercises actual SDL input, map draw and publication: later reduction occurs during the first displayed travel, and a paused first sample stays fixed while latest HP advances. Each next head begins at elapsed zero from its historical predecessor. A real X11 window also completed the two-cast run; the earlier library-only proof remains useful for retained replay.

Use a finite script of two legal public casts, through the current action/turn owners. Advance the first animation into release/travel, execute/capture/reduce the later cast, then continue rendering the first.

**Central acceptance:** later reduction advances, while the first cast's samples, historical appearance/contact/HP and timing match the run with no later cast pending. The next head begins from the first head's historical result. A second compatible target/distance changes input, not the executor design.

Once this proof works, select the next real case from section 5. Before allowing unrestricted player choices, support the outcomes those choices can actually produce or clearly limit the exposed capability. Ordinary misses, Counterspell, temporary HP and concentration are useful real next cases; they are not all prerequisites to showing the first positive cast.

## 5. Expand by actual gameplay need

Each next case extends the demonstrated structure through the current mechanic and existing presentation data. Select a concrete case after the integrated two-cast proof. Reuse the same capture/reduction, semantic binding, authored executor and painter; extend the affected owner when the new case needs a capability. This table is a capability roadmap, not a prerequisite checklist or permission for a broad engine cleanup.

| Next case | What to preserve and demonstrate |
| --- | --- |
| Miss/prevention/reaction | Use the actual attack result, damage prevention or Counterspell lineage. Reuse supported no-damage contact/disposition behavior and existing recipes; do not invent cast-EFFECT vetoes. |
| Temporary HP, concentration and additional life states | Retain actual damage/cleanup/life facts. DYING, STABLE and DEAD come from the engine. |
| Repeated A/B/A applications | Existing Magic Missile data, one cast body, three real applications and separate arrival/consequence values. Check against original runtime semantics rather than collapsing by target. |
| Weapons and equipment changes | Preserve historical item identity/loadout, actual damage facts and existing causal relationships as equipment changes during playback. |
| Movement, opportunity attacks and terrain | Follow real Move/Step/sensory histories, committed positions and reactions. Jump, forced movement and connectors retain their own trajectories and cost points. |
| Conditions, areas, healing and other delivery shapes | Reuse existing Studio unions/context recipes and current condition/spatial/healing owners. Add only primitives the concrete case needs. |
| Fixed creatures and additional rigs | Use existing canonical creature creation, then identity-to-rig binding. `materialize_creature` already builds a real Goblin through current content owners; a new monster migration is not required merely to use the Goblin recipient rig. |
| Small playable encounter | Author backend map/height/doors/light/objects/actors together. Script and human input use the same legal action/turn path. Include a meaningful selected reaction or condition and two rigs when their bindings are ready. |

Use [dnd/content_system/creature_materialization.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/creature_materialization.py) and current declared builders before declaring a creature capability missing. The older [content migration record](/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md) is background; its cut numbers are not present-day gates.

Portraits/icons, further demon/undead/animal rigs and offline Godot VFX enter when selected gameplay needs them. Preserve original assets/provenance and report data/binary sizes separately. Old machinery is retired only when the actual replacement is established; no cleanup campaign is implied by a visual integration task.

## 6. Verification proportional to the change

Read [HOW_TO_TEST.MD](/mnt/c/users/tommaso/documents/dev/dnd_engine/HOW_TO_TEST.MD). State the requested behavior, real boundary, input and observable result before writing tests. Existing authored timing, rig, drawing and mechanics tests are assets to reuse.

The first integration needs these proofs:

- Real public cast, actual required children/results and permitted retained facts.
- Retained replay without live mechanics lookups, and separate ownership of active history and latest state.
- Existing authored timing and actual map composition after that layer is connected.
- The two-cast ahead-of-display proof.
- Relevant regressions/type/import checks for the changed owners, with unrelated baseline failures reported honestly.

Add tests for errors actually introduced by the adapter: a required value/media cannot silently disappear, and an incomplete capture cannot be reported as success. Reuse existing reset and loader behavior. Further robustness work follows the actual exposure introduced by a selected capability.

Match claims to evidence. A successful finite cast does not certify all player actions; a dummy renderer does not certify real map output; source inspection is not a gameplay reproduction. Conversely, a hypothetical API misuse is not evidence that shipped mechanics need repair.

## 7. Review and code discipline

**Anti-slop reviewer:** first verify that each proposed requirement comes from the user's design, the selected feature or an actual owner contract. Identify the real gameplay subscriber before approving a mechanics-interception fix. Check source reuse and the independent-history proof. Reject mandatory hypothetical hardening, copied timelines, invented IDs, blanket graph closure and unrelated cleanup.

**Anti-OOP reviewer:** check specialized ECS ownership, exact modifier/condition/receipt cleanup, data-oriented rig/appearance binding and the import DAG. Reject new managers, generic rollback/contribution frameworks, late imports and reflection used to bypass dependencies.

Reviewers may cover multiple roles. Inspect the first concrete retained example before shared-contract edits and review the actual two-cast/map results before expanding. A review count is not evidence that its premise was correct; reviewers must challenge the requirement itself.

Production dependencies remain a DAG: the application calls public mechanics and presentation; capture reads allowed facts; animation consumes passive data; drawing owns Pygame/assets. Backend mechanics contain no sprite paths, authored timing or renderer readiness. Add a module/class only for a demonstrated responsibility; no module is mandated merely because the plan names an ownership concern.

Report production code, tests, original JSON, generated output and media separately. Continue within the active cut; ask only about an actual unresolved change to accepted gameplay/design. Do not ask the user to repeat the established framing or treat every source observation as a new blocker.

## 8. Completed integration checkpoints

The first retained cast connection is implemented. No backend mechanics repair was needed for it.

| Work | Current evidence |
| --- | --- |
| Public producer and complete lineage | Two discovered Fire Bolt casts through `Encounter.execute_action`, spending actual actions on successive legal turns. |
| Historical reduction and authored binding | Five passing integration cases in `tests/game/test_combat_history.py`, including Goblin survival/death; unchanged historical samples and replay after engine reset. |
| Appearance binding | Existing body/rig metadata and item-visual ledger feed neutral `RigLayer` values. Separate appearance tests cover authored equipment, visibility/active set and fixed Goblin layers. |
| Actual app scheduling and map composition | Five SDL frame-loop cases pass, including input/reduction during paused playback, miss and canonical Goblin survival/death. Earlier real X11 hit/miss playback completed both casts; six raster cases verify cliff and front/back straight/corner wall overlap. |
| Ordinary miss | Public MISS/CRIT_MISS bind to the existing no-damage input, retain the projected miss text and replay after engine reset. A third SDL app case verifies an actual missed second cast through the same map loop. |
| Canonical fixed creature | Actual materialization supplies full identity, 10 HP, scale 0.82, darkvision and default equipment. The existing fixed rig renders hit/miss/death results. The real internal damage marker and death/perceivability/sensory descendants remain retained causal children. |

**Current equipment cut completed:** retained replacement now drives actual playback using NeuroClient's original context, imported Melee3 media and shared actor drawing. Anti-slop and anti-OOP reviews found no blocking issue in the selected contract. One pending deque handles both cast and equipment roots. Item identities change at historical completion, independently of latest state.

**Repeated-application checkpoint:** the roadmap's A/B/A Magic Missile case tests multiple applications within one complete cast lineage. Its actual producer and existing materialized recipe were studied together before extending the executor, as recorded below. Equipment playback alone did not establish this contract; its implementation now shares the same cast executor and queue.

### Implemented: one Magic Missile lineage, ordered A/B/A applications

The public producer and original runtime have now been traced by anti-OOP and
anti-slop reviewers. A raised-map probe succeeds with the existing capture and
reducer unchanged: caster (16,25), A (16,20), B (18,20), supports 0/2/2. Public
`execute_by_index` supplies `extra_target_uuids=[B,A]` during an actual Encounter
turn. Two casts spend two actions and two level-1 slots. Each complete root
retains three distinct Spell applications with indices 0/1/2, each with its own
TakeDamage → DamageApplied descendants. Join terminal records through their
existing lineage links; parent version UUIDs can refer to intermediate phases.

**Contract:** the first root applies damage 5/5/2 (A 80→75→73, B 80→75); the next
root applies 3/2/4 (A 73→70→66, B 75→73). Latest may reach those final values while
the first root is still displayed. A/B/A remains three applications under one
cast body, one historical head and one queue. Each packet retains its actual
after-value and identity; actor deduplication is only for drawing one body.

1. Generalize the existing cast input/timeline to an ordered application tuple.
   Fire Bolt becomes the one-application case; do not retain duplicate singular
   fields or implement a second full cast executor for volleys. Samples expose
   per-actor vitals and distinct application effects. Existing body/equipment
   helpers and the same pending deque remain the owners.
2. Reuse the exact imported Magic Missile draft: Special1, speed 1, release frame
   8, launch stagger 80 ms, Bézier curvature .3 and same-target spread. Add the
   original Special1 sheets through the pinned importer. Geometry dart style
   already exists in the imported generated profile. Missing spell damage
   overrides preserve the imported global vital context and actual Force
   palette; do not edit the source JSON to fill the absence.
3. Use one body sample per recipient. Repeated TakingHit reenters and restarts
   that body, with source waiter/callback behavior accounted for. Current Magic
   Missile defaults put HP/flash/number at frame 0. Preserve separate packet
   feedback and absolute after-values. Sprite Fire Bolt retains its existing
   delayed anchors. Distinct sprite/geometry sample records avoid fake assets.
4. Preserve authored screen-space curvature and the existing independent
   height/support adaptation. Geometry has no sprite canvas offset and no
   separate impact sprite. Depth uses the curved head's ground position after
   removing support/apex lift; the trail shares its head's painter key. Original
   geometry keeps eight rendered-frame trail points; use a documented 60 Hz
   reference cadence for deterministic seeking, matching the game's nominal
   display cadence without coupling trail history to actual frame rate. This
   is a visual sampling adaptation, not a change to launch/arrival timing.
   Actual map inspection also showed geometry launching below the feet. The
   original helper forces an actor-art root despite the generated geometry's
   `tileCenter` basis; its default lift does not compensate that root. Honor the
   existing ground basis for point geometry in projection, preserving sprite
   registration and the compiled source clock. Compare actual frames and
   record this explicit source-runtime correction; do not invent a second
   alignment catalog or edit imported JSON.
   Keep the interpolated authored vertical lift in visual height during depth
   inversion too. Otherwise an above-floor dart moves backward in ground depth
   and its target tile covers the head, as the actual near-arrival frame showed.
   Forward/side offsets and screen curvature still belong to planar placement.
5. Connect optional `--magic-missile` to the finite three-actor script and actual
   map loop. Preserve the ordinary Fire Bolt/equipment variants. Validate two
   legal volleys, paused independent reduction, retained replay, repeated A
   body/HP/number samples, original launch/arrival timings, camera projection
   and map output. Extend the existing offline oracle using the unchanged
   source CastClip/TakeDamage/AnimatedEntity runtime, rather than copying the
   editor's per-target earliest-impact summary.
6. Review the resulting structure with both reviewers before completion. Record
   source/runtime parity, explicit visual adaptations, scoped code/media size
   and real-window evidence. No mechanics repair, new disclosure policy,
   reaction framework or new scheduling owner is part of this positive case.

**Result, 2026-09-10:** `python -m game --magic-missile` now runs the two real
volleys; `--replace-weapon` also works with all three actors. Paused playback
retains A/B at 80/80 while latest reaches 66/73. Each dart preserves its own
application ID, after-value and number; repeated A restarts one reaction body.
The original runtime oracle agrees on all 66 observed body frames and explicitly
accounts for its 1 ms callback pump. The existing Fire Bolt oracle still
reproduces byte for byte. Relevant history/playback/drawing/projection tests,
production type checking, four dependency checks and all 81 import outputs pass.
Both final reviews found the selected ownership coherent. Ten original Special1
PNGs add 1,409,000 bytes; no backend mechanics file changed in this session.

Actual X11 playback completed both casts and all six roots with the equipment
option, then matched historical to latest. Captures and a five-second recording
are under `.runtime/magic-missile-play/`; four camera views were inspected.
The observed target-floor coverage in the front view was corrected by separating
authored vertical lift from planar depth; the actual map regression now passes.
The whole-tile painter can still cover approaching darts in reverse views;
some mid-flight curves also remain occluded near the terrace.
Keep that concrete visual limitation distinct from timeline/state correctness.
The next visual review should use the recorded frames to distinguish path
placement from painter ordering before proposing another change; there is no new mechanics
repair or general collision-routing prerequisite here. Detailed source owners,
commands and evidence are in `agent_docs/CURRENT_CODEBASE_STUDY.md`.

**First equipment connection completed:** public same-slot dagger→shortsword replacement produces four separate completed roots. They remain unchanged; slot-transition roots explain the operation, and cold item-location after-values update retained items/slots. Completion order allows independent declarations to overlap. The public test proves immutable earlier appearances and replay after reset; ten cast/history/miss/import regressions pass. The original frame-4 callback changes active weapon set, while replacement item identities install at historical frame completion; this replacement keeps MELEE unchanged. Reuse that distinction rather than inventing a universal gear-change anchor.

### Completed equipment session: equipment between two casts

Budget approximately 2–3 hours of useful work; finish on evidence, not on elapsed time. The user need not supply another implementation plan or restart work after a question.

**Observable outcome:** run a legal Fire Bolt with a dagger equipped, replace it through the public equipment owner, then cast again with the shortsword. Latest reduction can reach the second cast while the first historical cast still plays. The old dagger remains throughout that cast and the equipment gesture; the shortsword appears at the gesture's completion and belongs to the second historical cast. Both actors remain on the real raised map.

1. **Contract and ownership review (about 25 minutes).** Anti-slop and anti-OOP reviewers inspect the actual producer, original context and current drawing/application boundaries. Keep all four roots separate. Attach the single gesture to the incoming item-location fact that changes resolved visible layers; consume cause-only and unchanged-appearance roots without invented animations. This adapts the original batch-attached loadout gesture to the current per-lineage boundary, rather than recreating old batch machinery.
2. **Authored body and media (about 30 minutes).** Type the existing `equipment_transition` JSON; reuse Taunt, speed 3 and last-index completion (388.889 ms on this rig). Frame 4 selects stance in the source; unchanged MELEE has no mutation there. Add Melee3 through the pinned importer. Extract shared body loading/drawing from the cast drawer so equipment does not need a fake spell or projectile.
3. **Real mixed playback (about 55 minutes).** Add an optional replacement to the finite public input script. Deliver the four roots at the equipment command's input deadline and the next legal cast at its own deadline. Use the existing single pending deque and one active head. Bind each historical head before its visual clock starts; preserve historical appearance, support, facing and the other actor's body. Load its required pixels before playback. No backend mechanics change is planned.
4. **Self-validation (about 35 minutes).** Exercise the pure body timeline at frame 4, completion and a large time step; replay retained inputs after reset. Use the actual SDL loop to show latest gear/HP advancing during an unchanged paused first sample, dagger during the gesture, shortsword on the next cast, and matching final historical/latest values. Run relevant source/timing/appearance/map regressions and type/import checks. Review real-window playback and visible gear in all four camera orientations; retain a reproducible clip.
5. **Design review and handoff evidence (about 25 minutes).** Anti-slop checks original timing, complete roots and scope; anti-OOP checks passive records, shared drawer ownership and the import DAG. Address concrete findings, remove unnecessary intermediate scaffolding, and document actual behavior, commands, limitations and code/data/media sizes. Do not expand into a new gameplay family merely to fill the time budget.

At each checkpoint, reconsider the overall structure before adding the next part. Passing tests alone do not justify a new abstraction. Completion is a runnable, reviewed mixed sequence with independent historical playback, not a collection of disconnected helpers.

**Session result:** all five checkpoints are complete. The three public commands deliver six separate completed lineages. Shared actor pixels are preloaded per head, old/new appearances are explicit immutable values, and equipment retains the previous displayed facing. The sampler remains renderer-independent; Pygame draws bodies through the same actor/shadow helper used by casts. The original context's nonempty media tracks and active-set changes remain outside this same-MELEE case.

Validation: seven SDL app cases, nine retained-history/miss cases, four dependency/import rules, the existing timing/rig/map/source regressions and changed-file Pyright all pass. Real X11 runs in quadrants 0–3 each complete six roots and reconcile history; the latter runs include canonical Goblin miss and death. Terrain still occludes actors where appropriate. `.runtime/equipment-play/playback.mp4` and `.gif` record the real frame loop, with source frames and wall-clock durations retained under `recording/`. Eight production Python files were extended/refactored, plus the offline importer; five original PNGs add **627,398 bytes**. The importer reproduces all **71** outputs, with original JSON and existing materialized recipes unchanged.

**Completed height adaptation:** one frozen presentation input, `travel_apex_steps`, defaults to zero. The existing finite terrace scene supplies 1 step: the full-cell support-envelope minimum, measured at the upper stair's entry rather than only its center. Both drawers consume the same sampled height; projected fine rotation follows the vertical tangent and retains the incoming tangent at impact. Original JSON, facing rows, offsets, authored clocks and backend targeting retain their owners. This is scene-authored presentation geometry, not automatic routing for arbitrary spells or terrain. Acceptance covers attachments, full-cell stair clearance, all four views, impact continuity and the existing independent-history app loop.

**Review checkpoint:** anti-slop and anti-OOP reviewers examined the integrated input/history/frame ownership and actual map result. The Goblin review checked canonical input, full content key and the real marker. Both roles then traced the lethal input: initial-root identity/location establishes its historical participants, later terminal grants remain unchanged, and actual contact loss still reduces. No condition simulator or serializer framework was added. Stair review confirmed the explicit scene apex, shared height ownership, original timing, fine-rotation adaptation and all four map views. Equipment review confirmed original body fields/bounds, completion-only item replacement, facing continuity, independent complete roots and the shared drawer's limited ownership.

The [plan audit record](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#planning-requirement-audit--2026-09-09) names the withdrawn or narrowed items and why. It is a record of corrections, not another task list.

## Appendix A: completed foundation and source reference

These are retained evidence records from 2026-09-08, not fresh test results from this plan rewrite. They preserve what is implemented and why it should be reused. Detailed present mechanics and the later reread's exact test commands remain in CURRENT_CODEBASE_STUDY.

### A1. Local NeuroStudio data and original materialization

<a id="113-p1--import-source-data-and-export-what-already-exists-in-ts"></a>

The P1 source import is implemented in [devtools/import_neuroclient_presentation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/import_neuroclient_presentation.py); local usage/provenance is in [game/data/neuroclient/README.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/neuroclient/README.md). The legacy anchor above preserves the existing data README's link.

NeuroClient source is `/home/tommaso/Dev/NeuroClient/app` at `d274f2d62ca9c1c5ed62a77841cacf6cc0347491`. Original JSON stays byte-preserved beside generated outputs. The offline tool calls the original TypeScript validators/materializer with explicit current catalog evidence; Python does not recreate generated defaults or merge rules.

| Reused source under NeuroClient app | Recorded content |
| --- | --- |
| `public/studio/spell-studio-drafts.json` | Version 6; exact saved Fire Bolt and Acid Splash overrides. |
| `public/studio/spell-projectile-assets.json` | Twenty projectile asset descriptions. |
| `src/render/data/animation/generatedSpellPresentationProfile.json` | Version 8 generated defaults, consumed by the original materializer. |
| `contentActionPresentationRecipes.json` in the same animation directory | Version 13; 88 action recipes. |
| `actionContextPresentation.json` | Version 17; eight contexts. |
| `actionPresentationDispositions.json` | Version 4; three entries. |
| `conditionPresentation.json` | Version 12; 141 recipes. |
| `actionMediaAssets.json` | Version 1; 23 media descriptions. |
| Palette/hue and actor/ancestry profile/binding JSON | Original presentation/color/identity inputs retained as source material. |

The two saved overrides are not the full authored population: generated baselines and exact overrides are merged by the existing owner. The current exported set contains Fire Bolt, Acid Splash and a generated-only Magic Missile case. Their imported records do not certify that every delivery/media capability is executable.

The unmodified Fire Bolt reference retains Attack5/release frame 7, hidden main weapon, Magic2 glow and original colors; disabled Effect1; disabled Taunt recovery at speed 1; prepare at body frame 1; the existing `lelu_fire_strike_128_pixel_lab_fire24_px8` prepare/travel/impact sprite; travel at 180 reference pixels/second with 150ms minimum and 24 FPS; original source/target anchors; and damage delay 15ms with flash/number/death fields at frames 5/7/12. Those values are source data, not settings to redesign.

**Recorded P1 evidence:** initial export/check reproduced 57 outputs. Five detached artifact tests and an earlier combined run including 49 existing asset tests passed; importer Pyright was clean. Missing/corrupt output, destination collision and a temporary Git checkout with `core.autocrlf=true` exercised failure/byte-preservation. Initial import contained 14 original JSON files (22,100 existing authored lines), generated bindings/provenance and 38 PNGs (5,215,146 bytes).

P2 recovery subsequently added nine original Taunt sheets, yielding 47 PNGs/6,412,169 bytes and 66 reproducible enumerated source-import outputs. No old TS application, SDK runtime or server was vendored. Additional import follows this existing route with exact provenance and local URL bindings.

### A2. Python timing, drawing and actual source oracle

The implemented owners are [game/animation_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_types.py), [animation_data.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py), [animation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation.py), [animation_draw.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_draw.py) and [animation_preview.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_preview.py). Typed source loading and passive rig metadata feed an absolute-time compiler/sampler. The drawer owns preloaded pixels/fonts and projection, without live Entity lookups or clock advancement. The preview uses this same execution path.

[devtools/trace_neuroclient_animation.ts](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/trace_neuroclient_animation.ts) runs the original clip/queue/FSM owners offline. Its retained oracle is [tests/game/fixtures/neuroclient_animation_timing.json](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/fixtures/neuroclient_animation_timing.json). Original execution uses supplied 1ms frame delivery, with diagnostics/texture/font/GPU IO and watchdog timing substituted. It is source timing evidence, not a runnable current SDK integration or GPU pixel parity proof.

The source runtime ends a 15-frame body at its last index-14 boundary; the editor's count/FPS duration differs. In the recorded ordinary case release occurs at 584ms and settlement at 2611ms. At body speed 2, release-frame crossing occurs at 292ms but launch waits until 542ms because preparation still joins. The saved main-weapon override and cast layers clear at Casting exit. NeuroClient's separate `hiddenSlots` visibility scope restores after the body/delivery join; the selected oracle has `hiddenSlots=[]` and uses the action-VFX weapon override. Preserve these distinct owners when extending support. Editor bar estimates are not the execution oracle.

The original runtime also starts children late after a single 1500ms hitch. Python's absolute sampling deliberately corrects that large-delta behavior by evaluating remaining elapsed time and crossed anchors; it does not change saved recipe values or normal timing relationships. Repeated-target editor summaries choose the earliest impact per target and cannot replace application-specific runtime evidence.

Enabled recovery is already implemented; `--recovery` selects a validated variant without changing the saved disabled default. Required body/delivery work joins before recovery; decorative feedback tails do not become a new queue barrier. Disabled floating-number display does not remove the permitted HP anchor. Life uses the existing passive LifeState type; the selected death-only reference does not implement engine DYING/STABLE merely because a source animation FSM used the label “Dying.”

**Recorded P2 evidence:** 58 evaluator/data, five artifact and four Pygame boundary cases passed together (67 in 7.34s), alongside the three relevant architecture checks and clean changed-Python Pyright. Ordinary travel, lethal speed-2 and recovery captures were inspected. Preload failure, rendering after temporary source-link removal and seek pixel equality were exercised. Later G5/rig selections supersede the combined count without erasing its original scope.

Recorded P2 limits included tangent-facing/subpixel no-travel cases, selected optional-media policies and some color/blend/equipment modes. Original unused data remains present. Magic Missile's later selected implementation is recorded in §8; Acid Splash still has imported data without an executable-family claim.

The original Fire Bolt strip appears high over half-scale actors because of its actual cell content and pivot. No compensating art offset was introduced. Adjusting that visible authored binding would be a separate data decision, not a time-correction shortcut.

### A3. Implemented height/contact adaptation

The engine has one support per XY, with five-foot height steps. July's 128×64 projection and 64px lift per step are twice NeuroClient's 64×32 reference scale before zoom. Contacts, authored local offsets and camera transforms retain separate meanings.

The completed detached G5 adaptation keeps the camera-0 flat reference endpoint delta after authored offsets and adds height independently:

```text
distance_reference_px = hypot(flat_dx, flat_dy, 32 * difference_in_5ft_steps)
travel_ms = max(saved_minimum_ms, 1000 * distance_reference_px / saved_speed_px_per_second)
```

This preserves the original direction-dependent isometric flat timing. It is a visual reference metric, not engine range or Euclidean feet. Camera changes reproject frozen endpoints without recomputing duration. View-local sprite padding is not inverse-projected into world XY and rotated.

| Unmodified Fire Bolt; actor visual scale 0.5 | Flat delta | Height component | Recorded travel |
| --- | --- | --- | --- |
| `(0,0,0ft)` to `(3,-3,0ft)` | `(152,0)` reference px | 0px | 844.444444ms |
| Same target at 5ft | `(152,0)` | 32px | 862.955015ms |
| `(0,0,0ft)` to `(1,1,5ft)`, collapsed support projection in quadrant 0 | `(0,8)` after source inset clamping | 32px | 183.249139ms |

**Recorded G5 evidence:** 25 spatial cases added; 92 focused cases passed together in 8.42s, changed Python type-checks passed, and raised/four-view/collapsed/recovery captures were inspected. These prove detached contacts/time/reprojection. They do not prove joint wall/cliff/door occlusion; that remains step 4.

The reference preloader measured 150MiB of default four-view media buffers and 183.75MiB with recovery. A separate P2 SDL-dummy diagnostic measured preload 761ms and clear/draw median 0.52ms/p95 1.34ms over 121 samples with one warmup. These exclude full engine, UI and frame publication costs, may use warm filesystem data, and establish no integrated-game performance threshold.

### A4. Root and Goblin rig reference; other assets

`BodyClip`/`BodyRig` and `ActorContact.rig_id` already select per-actor metadata through the shared compiler, sampler and drawer. [game/data/rigs/goblin01.json](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/rigs/goblin01.json) maps Goblin 01 Idle, TakeDamage 1 and Die 1 to the root vocabulary. Six original body/shadow PNGs (695,418 bytes) are reproduced by [devtools/import_fixed_rig.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/import_fixed_rig.py); current combined imported media totals 53 PNGs/7,107,587 bytes.

The selected Goblin sheets have fifteen 128px frames in eight rows. 12 FPS, support pixel `(64,87)` and shadow alpha 0.5 are explicit reviewed adaptations, not claimed vendor metadata. Original PNG bytes, including alpha=1 residue, are preserved. Fixed weapons remain baked into the body. Goblin casting fails on missing clip/capability data; recipient compatibility is the implemented scope.

**Recorded rig evidence:** 141 combined animation/rig/drawer/artifact cases passed in 24.41s; three architecture checks passed in 4.84s; changed runtime/importer Pyright was clean. Actual ZIP reproduction, eight-direction row checks, unchanged root-stage pixels and raised Goblin travel/hit/death/recovery captures were verified. Hypothetical alternate-count metadata tests do not claim the real PNGs have different geometry.

Read-only source inventory also selected Demon Beast 1 and undead 5Archer as promising future groups. Their common naming is compatible enough for direct mapping, but actual clips/capabilities remain decisive. Goblin Block has six columns, Demon Beast Block seven; skeleton 6Warrior has truncated TakeDamage sheets and a blank Special1 column. Skeleton 5Archer row order was matched to named direction frames; the selected Goblin/demon PNG-only packs lack equivalent textual metadata. No broad rig inference or universal pack importer is needed.

User-supplied sources remain:

- NeuroClient modular layers, portraits, spell icons and authored JSON.
- `C:\Users\tommaso\Downloads\2D Orcs and Goblins - TopDown - V1.0.zip`.
- `C:\Users\tommaso\Downloads\2D Demons - TopDown assetpack v1.1.zip`.
- `C:\Users\tommaso\Documents\assets\smallscale`, including the undead pack.
- NeuroVFX/CodexFX, for offline Godot-authored and exported media.

Demons/skeletons, more maps, portraits/icons and beam media are future selected imports, not prerequisites for the first lineage connection. Record code/data/binary sizes separately when importing them. Runtime uses only contained local resources.

Existing preview commands remain useful regression/inspection tools:

```bash
python -m game.animation_preview
python -m game.animation_preview --target-rig smallscale.goblin01 --target-height-steps 1
python -m game.animation_preview --lethal --recovery --quadrant 3
python -m game.animation_preview --headless --at-ms 900 --capture /absolute/path/fire.png
```

Space pauses; replay/seek, Q/E camera turns, `--cast-speed`, `--playback-rate` and `--collapsed` exercise the same selected reference. None of these commands runs an integrated combat encounter.

### A5. Event registry correction

Event now inherits BaseModel directly and remains a typed runtime object with its existing fields/lifecycle. EventQueue owns every registered version; BaseObject no longer retains only the constructor version. Sneak Attack's maintained lookup uses EventQueue; sensory replay still rejects nested runtime Events. Required source UUID, UUID coercion, subjectivity, handler behavior and parent/turn semantics were preserved.

**Recorded evidence:** 152 relevant behavioral checks and three architecture checks passed. Common Event JSON schema matched except registry documentation; unregistered round-trip values and missing/null-source rejection remained intact. The two changed production files had 21 net new lines. Changed-production Pyright still reported two diagnostics also reproduced on isolated `16a6bfe`: the existing validator-proxy call in events.py and anchor_uuid override in traits.py. This is explicitly not a clean-type-check claim.

Registration opt-out still does not guarantee passive construction. Nested DiceRoll construction registers; Event/ActionEvent construction can perform parent/turn/binding work. A diagnostic invalid ActionEvent registered before an after-validator rejected it. Account for these contracts only where the selected retained fields require constructing those types; no global constructor rewrite is implied.

## Appendix B: prior public cast traces and unresolved evidence

These diagnostics preceded the broad owner reread. They are retained factual evidence, not a replacement forward sequence or a current passing gameplay milestone. The later study adds complete condition, handler, value, spatial and content context.

### B1. Public hit, miss and life ordering

`FireBolt.apply()` produced 15 stored versions for a nonlethal hit, 26 for an immediate-death hit and seven for a miss. Hit input used fixed d20=18/d10=8; miss used d20=2. Fire Bolt's SpellEvent carries the attack result; there is no AttackEvent child or explicit single-target application ID.

| Immediate-death target starts at 5 HP, death saves disabled | Recorded HP | Recorded life |
| --- | --- | --- |
| Spell execution after action cost | 5 | ALIVE |
| Attack-d20 completion / spell EFFECT | 5 | ALIVE |
| DamageApplied COMPLETION | -3 | ALIVE |
| Later sensory/life transition facts | -3 | DEAD |
| Death, TakeDamage and root Spell completions | -3 | DEAD |
| Action batch notification and public spell return | -3 | DEAD |

Both the damage after-value and subsequent life fact matter. Positive damage's EFFECT subscribers can add saves, concentration/condition removal and reactions. A later live snapshot cannot replace the earlier retained facts, and a damage child completion is not the whole rendering unit.

### B2. Cancellation, reaction and exception

- An ordinary CAST_SPELL/EFFECT handler canceled Fire Bolt, but its public return was CANCEL while HP still fell from 30 to 22 and DamageApplied completed with 8 damage. This used an injected handler, not a shipped mechanic. The subsequent speculative patch and its tests were withdrawn. This diagnostic is not evidence of a shipped gameplay defect.
- Real Counterspell produced six stored versions and no damage, with the caster's action already spent. Reaction events have `parent_event=None`; `triggered_event_uuid` and `triggered_lineage_uuid` carry their relationship.
- Deliberate fixed-dice exhaustion during damage raised after spending the action. The batch still flushed six versions ending at Spell EFFECT, without a completed root. This proves the failure boundary, not normal dice-source failure.
- Queue observer callbacks run before ordinary mechanical dispatch and swallow observer exceptions. A callback must retain its own failure status; throwing from capture neither stops mechanics nor guarantees valid delivery.

SpellAction releases cast-local contribution claims after BaseAction's inner batch exits, and Encounter can perform post-action death checks. This is why public-operation accounting must be named accurately while complete existing lineages remain the presentation units.

### B3. Information and passive representation

The current same-model combat-log projector and observer-specific sensory replay are established owners. The targeted study found no existing ordinary same-Event projector to reuse wholesale; legacy ProjectedEventSlot retains the original Event, and the old server mapper emits a separate cue vocabulary.

The old mapper is a bounded rule witness for the independently unknown attacker/identified victim case, preserving exact permitted damage/HP. It is not a runnable current adapter or an import target. The plan requires a valid selected Event representation following that existing meaning; it authorizes neither a new withholding policy nor the withdrawn global source-nullability change.

BaseCost, DamageResolution and item presentation facts already supply useful value contracts. DiceRoll is mutable and registers on construction. SpellEvent attack/AC/damage fields can retain live value graphs; condition application/removal Events retain live condition/duration/ownership graphs. Frozen outer envelopes and blanket deep copies do not resolve those boundaries.

Standalone observation-only combat text bypasses EventQueue history and uses the existing Encounter log range. Preserve that separate factual/log accounting; do not build a second mechanical Event from text.

### B4. Presentation gap before cast binding; exact NeuroClient reference

The studied `game.app` reduced only when `current is None`, then drew that same mutable target. Engine production could advance, but reduction waited for display. The subsequent `game.play` integration addresses that gap for the selected casts; the old map-only demo remains a regression tool. The detached sampler's fixed appearance and single-cast fixture did not supply actor initialization or general vital state; the retained actor/cast connection added since this study is recorded in section 8.

NeuroClient `eventIngestion.ts` accepts intake without awaiting visuals, previews one historical candidate, plays/checks/commits it, and uses a ClipQueue with no second causal backlog. `stateSync.ts` preserves existing actors' pre-head state while staging needed new actors. Recover those invariants.

The matching preview/commit journal API is historical D&D `74cc1f9e3d2d5524e3758ae3b7e73f7b8fd7b89e:sdk/typescript/src/subjectiveJournal.ts`. The SDK currently linked into NeuroClient has a different numeric commit API and no previewPresentationFrame. The source study pins the actual ranges/hashes; no current combined-runtime compatibility is claimed. Old frame-derived transaction identities must not replace current Event lineage IDs.

## Appendix C: review and correction record

The September 8 rewrite was reviewed for ownership and source reuse, but its reviewers missed the unsupported cast-EFFECT interception premise. Those approvals do not certify the withdrawn spell-defect claim or the larger set of prerequisites that grew around it.

The September 9 requirement audit checked the active plan against current mechanics, actual production subscribers, Python presentation ownership and the original NeuroClient source. It preserved complete lineages, established subjectivity, historical reduction, authored-data reuse, rigs and height. It removed or narrowed the items recorded in the study's planning audit. No new gameplay skill, disclosure policy, timeline system or backend repair campaign was introduced.

Source-import anchors and retained evidence links remain available. Historical test counts describe their recorded candidates; the withdrawn Fire Bolt tests are not current acceptance evidence. After removing that candidate, four existing spell/protection tests passed in 1.70s, including normal evocation, Shield, protective abjurations and Counterspell against cantrips.

After the retained cast integration, a bounded anti-slop/anti-OOP review updated
stale progress and the selected capture decision, and trimmed repeated discussion
of abandoned prerequisites. Three new integration tests passed; the broader
presentation/app and architecture run had 45 passes and the two previously
recorded server import-boundary failures. The [verification checkpoint](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#verification-and-plan-checkpoint)
records the scope. At that checkpoint, actual Pygame scheduling and map composition
were the next implementation, with the independent retained reducer/sampler verified.

The subsequent map/frame-pump implementation and miss extension are recorded in
the [integrated playback study](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#integrated-map-playback-and-ordinary-miss--2026-09-09).
The final selected app/map/projection/import run passed 171 tests in 81.15s,
including the existing startup timing test. Earlier timing overruns also occurred
with HEAD's map owners; the comparison is retained without changing the threshold.
