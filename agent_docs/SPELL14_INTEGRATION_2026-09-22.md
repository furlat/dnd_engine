# Fourteen accepted spell presentations — implementation unit

## Authorized outcome

The user's correction is explicit: integrate all fourteen accepted outstanding
presentations, request their necessary extra viewpoints/exports, and own runtime
timing, offsets and defects here. Intake alone is not completion. Keep working
through implementation, saved gameplay replay and four-camera review. No new
permission checkpoint is needed for work inside this unit.

Scope: Mage Armor, Shield, Grease, Spike Growth, Fog Cloud, Cloudkill, Stinking
Cloud, Darkness, Incendiary Cloud, Insect Plague, Blur, Mirror Image,
Enlarge/Reduce and Protection from Energy. The
[received inventory](GODOT_BACKLOG_INTAKE_2026-09-22.md) links exact approved art.
Sanctuary, Enhance Ability, stacked floors and unrelated interiors remain out.
Previously approved targeting, rig identity/equipment and spell output stay intact.

**Latest feedback correction:** review only the latest fourteen spells and existing
barrels. The earlier request for all authored spells was superseded after the broad
collection proved too much to review. Barrel coverage corrections remain queued.

**Completed checkpoint (22 September):** all fourteen presentations are installed.
The [focused handoff](SPELL14_AND_BARRELS_FEEDBACK_2026-09-22.md) now provides
[90 four-camera clips](http://127.0.0.1:8767/runs/20260922T113258Z-latest-spells-and-barrels/index.html): 62 latest-spell and 28 existing barrel clips.
The new-spell actors also now compose the existing blood-response handler, which
had been omitted from their fixture. All 18 injury experiments / 36 clips were
recaptured with real material-release events and lasting floor residue. The fix
changes fixture composition, not native rules, rendering or artwork. Its 43 focused
tests and changed-module typing pass. Noninjury stories and barrel clips retain
valid existing inputs. Previous full-suite results below predate this correction.

Final review corrected two inadequate fixture stories without changing gameplay:
failed Grease now spends real movement before falling and recovers on the next
turn; Darkness now enters its actual 15-foot field. Its corrected pair is
`20260922T111213Z-b0daed`, replacing the earlier outside-only walk. Saved replay
proves entry, sight loss and recovery for Darkness, Fog and Stinking Cloud.

Validation: 1,476 engine tests and 2,120 game tests passed; after the final
fixture-only correction all 11 persistent gameplay tests pass, including three
new entry/visibility cases. Native/game and changed-module typing is clean.
The focused page's two group filters, real browser trace export and original
input/trace identities are checked. Source runs and evidence are recorded in
the handoff; automated checks are not human visual approval.

Barrel coverage corrections remain queued, Wet body media is still unbound,
and the upcast Fog clip has conservative wide framing. These limitations are
explicitly retained for feedback. No additional barrel authoring or unrelated
interiors work was resumed during this spell unit.

## Observed starting points

All fourteen spell mechanics already exist. Existing complete event lineages,
subjective projection, condition ownership, spatial conditions and retained
after-values are the game contract. Real application/removal, saved initialization,
concentration loss, reactions, movement and turn events drive presentation.

Initial inspection finds actual gaps to close:

- Mirror Image mutates its remaining duplicates without a retained intermediate
  condition update. Condition state also omits Enlarge/Reduce mode and Protection
  energy type. Actor birth already records Size, but passive actor projection
  drops it and evaluated stats omit later size changes.
- Several native zones have mechanics but do not opt into public spatial
  observations. Publish through existing spatial disclosure, retaining the
  existing Spike Growth detection gate and ordinary sensory rules.
- Shared condition media already support application, maintained membership,
  cold acquisition, overlapping owners, finite transition effects and removal.
  Shared spatial media already retain lifetimes, but sphere rear/front placement
  alone cannot resolve cloud/swarm depth against arbitrary actors and walls.
- Registered sparse media already carry raw per-pixel world footpoints and share
  the normal painter partition. Use these for actual volume depth and receiving
  cell coverage; do not put a whole cloud at one blanket front/back depth.
- Current condition authoring has no body-size transform, live duplicate slots
  or sampled historical-pose treatment. Add only the passive fields and shared
  executors required by the three approved body effects.

## Implementation responsibilities

### Native and public state

Reuse conditions' identity and lifecycle. Record typed native after-values for
remaining images, transformation mode, elemental resistance and evaluated actor
size where needed. A condition update must remain a child of its causal attack
or effect; it must not masquerade as removal/reapplication or restart its visual
application. Do not encode sprite scales, colors, asset names or animation clocks
in native state. Public reduction must work from serialized events alone.

Retain existing area geometry and moving-zone origins in spatial observations.
Existing shape, obstacle, movement/contact/turn gates and concentration owners
remain authoritative. Repair only demonstrated gaps that prevent the covered
stories. Preserve ruleset/project decisions rather than rewriting spells from
art descriptions. Ground reactions follow full movement/event ancestry; jumps
contact ground effects only where native landing/contact says so.

### Shared presentation and authoring

Keep authoring in passive JSON, using the current Studio recipes and condition,
spatial and body records. Extend those schemas narrowly for actual missing
properties; document each extension in PRESENTATION_CONTRACT.md. Importers copy
media and translate declared storage/registration only; authored behavior has a
single explicit owner and is never inferred from another spell or list position.

- Condition apply/hold/clear use existing owner UUIDs and historical clocks.
  Use real clear assets when delivered, not an invented expiry from a finite
  demonstration. Refresh/overlap keeps phase; cold acquisition starts maintained
  state. Element variants select from retained native energy type.
- Shield contact follows an actual intercepted attack in its complete reaction
  lineage. Incoming travel direction is distinct from camera/actor facing. A
  damaging hit must not appear blocked. Shell application is not replayed for
  every contact; preserve legitimate interruption/reaction timing.
- Size presentation uses approved 1.175×/0.75× relative to resolved base appearance.
  Keep feet fixed; one transform applies to body, gear and pose attachments,
  including hands, torso targets and condition layers. Gameplay Size/reach is
  native and is not calculated from these cosmetic factors.
- Mirror copies use the current actual pose/equipment and retained duplicate
  count, stable authored slots and individual world depth. Removal dissipates
  the corresponding slot. They are not extra entities or recursive clones.
- Blur operates on the actor composite, including stationary distortion and
  limited prior presentation poses during motion. Any needed pose history is
  bounded presentation data, shared by all cameras and deterministic under
  replay/seeking; never another rules simulation. Teleport and loss of observable
  continuity break trails. UI, ground and unrelated media are unaffected.
- Terrain uses actual native footprint and existing support/ground composition.
  Grease spell's four-cell footprint is distinct from barrel Grease. Thorn clumps
  have stable authored placement and independent ground depth. Contact effects
  and damage reactions come from real native resolution.
- Volumes reuse registered media/footpoints and shared painter/fixture clipping.
  Their pixels never disclose an actor or unobserved cell. Movement uses native
  zone transforms; stationary internal motion does not contain a compulsory
  browser movement route. Apply, hold and clear retain authored phase boundaries.

No runtime source hashes, eager asset audit, generic effect-framework rewrite,
per-spell renderer switches, fallback particle invention or Node/Godot runtime.
Keep lazy bounded media loading and pure Python/Pygame playback.

### Source exports

Godot task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec` has the active request:
terrain first, then actor protection and prototype volume production exports.
It preserves accepted pixels/palettes/scale and supplies additional actual
camera views, declared numerical projection bases, correct registration and
genuine lifecycle phases. Validate one volume footpoint prototype before
multiplying five clouds and the swarm. Insect must retain its 360-insect motion;
no substitute tinted cloud or population reduction. Root owns placement/timing
and asks for a new render only when source material is actually missing/wrong.

## Sequence and division of work

1. Native/public-state study and small real scenarios proceed alongside export
   preparation. Independent reviews below validate this plan before production
   edits in their areas.
2. Implement necessary public after-values, ordinary condition updates and
   native area disclosure. Exercise actual spells and state transitions.
3. Wire ready terrain art and shared maintained field lifecycle first. In
   parallel implement the body/condition capabilities and prepare explicit
   authoring records for each delivered family. Missing one family never blocks
   useful work on the others.
4. Integrate prototype cloud ownership/depth, then all remaining approved media
   and Shield contacts using those shared capabilities. Fix demonstrated native,
   timing or registration errors in this branch.
5. Finish the whole fourteen-spell acceptance matrix, saved clips, independent
   final review, appropriate regression tests and typing. Update current status
   throughout. Do not return with only an intake, proposal or first spell done.

## Observable acceptance

Use public actions, reactions and turns to record histories once; replay public
packets after native runtime teardown. Every story has both actual subjective
participants and four cameras. Tests state expected received state/behavior,
not mock sequences or private helper structure.

- Every spell: actual cast/reaction, correct recipient/footprint, application,
  maintained state and real removal/expiration/concentration loss as applicable.
- Mage Armor/Protection: movement, equipment/pose fit, selected element and
  damage consistent with real resistance; no fabricated invulnerability.
- Shield: actual triggering attack, intercepted miss versus damaging hit,
  repeat contacts and expiration; melee/ranged direction where native supported.
- Grease/Spike: entry/exit/internal travel, saves/prone and real recovery,
  difficult terrain versus damage distance, jump over/landing, hidden/discovered
  Spike Growth, obstacle/raised-ground support.
- Clouds/swarm: affected/unaffected participants, real turn/entry damage or
  denial, zone movement where native supported, own versus other observation,
  physical fog versus magical darkness sensory differences, boundaries/walls,
  sustained loop and removal. Never infer rules from translucency.
- Mirror: 3→2→1→0 from actual attacks, equipment/pose/facing continuity and
  disappearing copies with independent depth. Blur: still/moving/stopping,
  attacks, teleport/no trail bridge, removal and replay seek.
- Enlarge/Reduce: both modes and removal through actual actions, body/gear/hand/
  head/torso attachments and hit target registration during movement/cast/hit,
  while preserving actual gameplay size and normal baseline appearance.

Test shared media phase/registration/lifetime boundaries without running full
videos for every edit. Then capture a grouped, tagged real-gameplay gallery and
inspect all families, ordinary ground plus difficult geometry, saved replay and
all four views. Existing approved Fire Bolt, Sleep/wake, weapon contact and
liquid checks are relevant regression references. No new visual-test framework.

## Required independent review and progress

- Anti-OOP/ECS/native review: `spell14_native_review`.
- Anti-slop/presentation review: `spell14_presentation_review`.
- Both receive the full objective and verify actual ownership/code, not merely
  approve this prose. Record concrete findings and subsequent decisions here.

2026-09-22: all fourteen authorized, work active; initial study found the native
state/disclosure gaps above. Godot confirmed terrain-first delivery and proposed
a Cloudkill phase/footpoint prototype. No presentation is marked integrated
until native replay, actual media and the required views work together.

### Implementation checkpoint — 22 September, continued

The ready families are connected: Grease/Spike Growth, Blur/Mirror Image/
Enlarge-Reduce, Mage Armor and Shield. Shield's incoming contacts use its real
interception owner and the eight authored incoming-direction banks, independently
of the four camera views. Cold Protection media has arrived; the other four
elemental palettes and full cloud/swarm lifecycles are exporting. This is an
intermediate checkpoint, not completion of the fourteen-spell unit.

Native condition updates now retain duplicate count, selected energy and size
mode, while actor snapshots retain evaluated size. Cloud observation now
distinguishes the visible volume from hidden ground and occupants; a cold
observation must carry its own geometric elevation rather than require floor
knowledge. The raw world-footpoint cloud prototype is accepted for the remaining
source exports after real public replay and wall/observer checks.

The user's spatial-occupancy requirement is tracked in
[the measured occupancy review](SPELL14_SPATIAL_OCCUPANCY_2026-09-22.md).
Grease's four cells and Spike Growth's 49 authored clump anchors align. Several
barrel-liquid variants leave admitted cell centers dry; a source-shape correction
covering those centers is requested. Preserve the correct projection, pivot and
native nine-cell footprint rather than inflating every sprite.

Acceptance found two real follow-ups: ranged Shield footage exposed a shared
pose/equipment transition defect, and Protection's original clip did not receive
incoming matching damage. These are being corrected before the final gallery.
Mage Armor removal will use the existing native armor-equip rule; the engine has
no implemented Dispel Magic action to use in a purported real gameplay clip.
