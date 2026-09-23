# Spell handoff integration: Fireball/walls, Eldritch Blast, Guiding Bolt, Acid Splash

September 19, 2026, `codex/recovery-design`. Authorized by the user after the
body/residue unit. Implementation and the review gallery are complete; results
and remaining limits are below. Existing dirty work and the completed
body/residue contracts are preserved.

## Outcome and evidence

Real native actions must produce complete subjective event recordings that play
through existing Python/Pygame choreography using the delivered artwork. Include
Fireball's physical wall interaction and floor/wall scorch, not just its travel
sprite. Replays run without the engine, preserve per-target results and observer
permissions, and retain the existing independent event/render processes.

Handoffs read:
- `/home/tommaso/.codex/worktrees/1aac/dnd_engine/docs/SPELL_VFX_HANDOFF_2026-09-19.md`
- That task's `output/weapon-vfx/spell-audit/integration-status-final.md`
- `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/PRODUCTION-FIREBALL-SCORCH-HANDOFF.md`

The art tasks delivered exports and detached prototypes, not finished game
implementations. The proposed native impact schema and fixed-wall JavaScript
sorter are suggestions, not existing authoritative contracts to copy wholesale.

Gaps observed before implementation (addressed below):
- Acid Splash has an old draft and metadata but missing local selected media.
- Guiding Bolt and Eldritch have no selected current draft.
- Eldritch currently rolls one level-scaled attack. It needs the native existing
  repeated-target machinery so each beam has its own attack/damage application.
- Fireball has native area mechanics but no selected visual delivery; the cast
  compiler currently rejects areas. Its art requires paired normal-alpha smoke
  and additive fire, paged images and a real ground endpoint.
- The smoke image includes a luminous ground ring. Both layers currently require
  physical propagation masking; filenames do not establish elevated smoke.
- Floor/wall scorch is a reviewed prototype whose stable composition should be
  reused. Its fixed map, global-Y wall coordinates and loop reset are not rules.

## Ownership and implementation order

1. Inspect existing repeated applications, native AoE result publication,
   subjective geometry filtering, wall/support state and Studio attachment data.
   Independent anti-slop and ECS/anti-OOP reviewers verify this plan against those
   owners before broad presentation changes. Record concrete findings here.
2. Repair Eldritch's demonstrated native multiattack gap using existing target
   allocation/convolution. Keep independent hits/misses/crits and one resource
   payment. Test levels 1/5/11/17, repeated/split targets and real recorded results.
   Check Guiding's existing mark lifecycle and Acid's target allocation; change
   only a reproduced defect needed for this contract.
3. Import the selected existing export files and explicit data bindings. Retain
   Studio recipes, phase FPS/anchors/directions and existing volley semantics.
   Preserve Fire Bolt/Magic Missile. Use exact source hand/target registration;
   do not copy preview actor coordinates or double-apply baked scale.
4. Extend shared media access only for the demonstrated paged/layered delivery.
   Bound decoded memory and load needed phases/directions/pages. Preprocess the
   authored caster-glow palette once in the existing media cache; never recolor
   the composed actor or perform pixel classification every frame.
5. Connect area delivery once through recorded native geometry/applications.
   Separate gameplay affected cells, physical propagation, observer disclosure
   and painter depth. Reuse the objective AoE computation/result rather than
   rerunning gameplay from Pygame or treating visible tiles as the blast mask.
6. Connect persistent floor/wall scorch through native surface state and its
   permitted after-values. Reuse existing condition/tile ownership where it fits.
   Ground/wall material eligibility and wall-local coordinates belong to actual
   surface data, not Fireball-specific camera branches. Keep marks inert; no
   combustion, spreading damage, cleanup simulation or new chemistry system.
   Lifetime and repeat-hit policy are to be settled from existing state conventions
   before implementing the persistent mutation, not inherited from preview loops.
7. Capture real native narratives from both observers, four camera corners per
   clip. Cover hit/miss/repeated applications, Guiding mark use/removal, Acid
   paired targets, Fireball empty/occupied areas, solid wall/doorway, both wall
   orientations, aftermath/repeated impact and later observation. Replay saved
   inputs, inspect contact/occlusion/pause frames, publish one labeled gallery.

## Integration boundaries

Mixed phase FPS already exists: use explicit recipe overrides for 144Hz impacts
and Eldritch travel rather than adding another clock. Retain every delivered
observation; realtime display may skip samples naturally. The 160ms Eldritch
stagger/held release and preparation hand sockets are supplied candidate recipe
values to validate through the shared evaluator, not per-spell imperative loops.

Fireball's 20ft area belongs to native mechanics. The delivered 1536px layer
canvases and scale are calibrated artwork; do not shrink them into point effects
or treat their visible particles as targeting. Paged media is a storage concern,
not a new spell type. Large artwork must not trigger full-atlas startup loads,
source audits, SHA checks or frame-by-frame defensive copies.

The floor atlas is a motif library, not certified seamless autotiles. Compose a
bounded stable field with one occupancy mask and cache it on state change. Wall
marks need face-local placement and original-alpha clipping. No new render cues,
random seed policy or preview timestamps belong in backend facts merely because
a handoff suggests them; use existing causal identities and state first.

No rays, weapon cannon gameplay, generic spell catalogue expansion, airborne
movement features or unrelated body-residue changes are included.

## Validation and review owners

Read `HOW_TO_TEST.md` before adding tests. Define expected gameplay/state first;
use native actions and saved packets at public boundaries. Validate the shared
media subset and real surfaces, not a copied implementation or string/SHA audit.

- Anti-slop reviewer: inspect shared recipe/media reuse, import scope, unnecessary
  abstractions, performance and the actual delivered art contracts.
- ECS/anti-OOP reviewer: inspect native application/geometry/surface ownership,
  causal lineages, subjective disclosure and replay boundaries.
- Root: integrate findings, implement, run focused tests and real clip review,
  update RECOVERY_PLAN and record remaining limits without claiming art approval.

## Findings and implementation log

The anti-slop review confirmed that giant decoded atlases would dominate memory:
use exact exported phase-local PNG frames with a shared 128 MiB decoded-frame
cache. Five logical assets cover the four spells (Fireball travel and impact have
different frame sizes). Import copies 147 MiB of selected PNGs, not source projects
or other tasks' symlinks. The existing Studio recipes remain the base; optional
source-sheet/socket, preparation-overlap and volley-pose fields are explicit
serializable presentation adaptations, not claimed to be original Studio fields.

The ECS/anti-OOP review confirmed that native target allocation must retain
Eldritch's independent attacks, and Fireball's resolved area must be recorded once
before recipient convolution. Other spells' custom target selection remains
unchanged. Point delivery and one ground delivery share the clock; the area
destination has no fake actor identity. A discovered caster-self-hit body conflict
is corrected through ordinary reaction precedence (one body per actor).

The user explicitly selected native **Ashen** tile conditions on September 19.
`ASHEN_RESIDUE` uses existing tile condition membership; repeated hits preserve one
inert membership. Fireball applies it to actual supports in its recorded footprint,
including empty areas. Wall conditions retain outward contacted faces on existing
boundary items. No animation time, renderer seed or sprite ID enters these facts.
Persistence follows existing inert residue lifetime; later elemental mechanics
are outside this unit. Floor and wall presentation consume that state.

Native area/ash checks cover empty areas, repeated casts, east/north walls,
open/closed doors, off-map coordinates and affected recipients. Player projection
retains a witnessed area root despite hidden recipients, preserves native child
indices/topology and filters coordinates/faces using existing recorded grants.
A wall's unseen face is neither disclosed nor silently erased by an unseen change;
later observation updates it. Prior native packets remain decodable with the new
optional fields absent. Standalone native probes require the normal content
bootstrap that pytest's session fixture supplies; missing that setup is not an
engine catalog defect.

## Completed result and review evidence

The [30-clip gallery](http://127.0.0.1:8767/runs/20260919T151344Z-4b12b5/index.html)
contains 15 real native experiments, each from caster and perceiver, with four
cameras sampled together. The saved run is under
`.runtime/animation-review/runs/20260919T151344Z-4b12b5/`.
It covers level 5/11 repeated and split Eldritch beams, mixed hit/miss results,
Guiding hit/mark consumption by a later shortbow attack and miss, Acid's two
independent saves, Fireball empty/populated areas, east/north walls, closed/open
doors and repeated casts on real successive turns.

All **30/30 clips pass**, covering **3,304 frames** with no reported gaps. The
saved-input replay process asserted `EventQueue.event_cursor() == 0` after all
clips. Direct comparison with run `20260919T150806Z-4c97d6` finds all 30 input
files byte-identical and all initial/latest states, lineages, heads and sampled
semantic frame states identical. All 16 point-spell videos are byte-identical.
The 14 area videos intentionally have improved fixed camera framing; that
change does not affect presentation time or gameplay. Comparison results and
inspected frames are in the run's `inspection/` directory. This bounded check
does not implement the proposed general pixel-regression tool.

Root inspected point-spell hand/torso contacts, Eldritch split launches, both
wall orientations, closed/open doors and persistent floor/wall aftermath in
four-camera images. The large Fireball canvas is framed around its actual
ground destination, with one stable camera setup for the complete history.
Native condition state persists after playback and repeated casts do not
duplicate Ashen membership. Wall face disclosure follows recorded observer
grants and later observation, rather than revealing unseen faces.

Two demonstrated shared defects were corrected during integration: point
effects using legacy tile offsets despite measured sockets, and initial native
object placements being omitted from capture after WorldInitialized. The latter
made real walls absent from early recordings. Initialization now retains the
existing placement/removal events alongside changes; no new visibility rule or
out-of-band wall snapshot was introduced. The final gallery uses fresh native
recordings containing those placements, then replays them without native work.

Validation runs (overlapping sets, not additive totals):

- 121 checks passed across area timelines, recovered media, existing animation,
  body action playback and lazy projectile media. They cover empty/populated
  ground delivery, caster self-hit/death, measured sockets and rig torso points,
  held volley release, mixed phase clocks and normal/additive wall masking.
- A final fresh run passed 28 area-projection, real handoff-replay and Ashen
  presentation checks. The native area suite passes 11 cases, and Eldritch's
  independent-application suite passes nine.
- Broader existing checks passed for combat/history, subjectivity, passive
  replay, body/dread residues, traps, teleport and review recording. Three
  review tests initially encountered a concurrent JSON/schema edit and passed
  when rerun in a fresh process after that edit completed.
- Targeted Pyright and diff checks passed for the changed integration modules.
  The repository-wide legacy failures are not represented as fixed: manual
  spellcasting fixtures still reference retired `Entity._entity_by_position`;
  architecture checks still include retired server imports and duplicate
  EquipmentSlot ownership. These are outside this unit.

Independent anti-slop and ECS/anti-OOP implementation review found no blocking
issue. Native mechanics own the footprint, applications and surface conditions;
player projection owns disclosure; shared timeline and media code own playback.
Selected JSON carries recipe, phase and rig attachment choices. Media access is
lazy with a 128 MiB decoded projectile cache and a 32 MiB residue cache. Four
physical masks are cached per cast, one per camera orientation. No source/SHA
audit, full-atlas startup load or renderer query into live GridMap was added.

## Remaining limits

- The physical mask is for the delivered ground-plane fire/smoke shapes. It is
  not volumetric fire or an elevated smoke simulation over walls.
- Floor and wall marks consume persistent native conditions. Stair-tread
  following artwork is not authored; no claim of full stair scorch acceptance
  follows from flat-floor/wall tests.
- Ashen is inert and persistent. Spreading, cleanup and elemental interactions
  remain later mechanics, not hidden rendering rules.
- Fireball uses the existing Attack5 gesture; no distinct delivered Fireball
  caster animation was available. Optional detached-preview arrival hold and
  impact speed changes were not imported as engine behavior.
- All presentation additions are JSON-serializable, but a future TS reader must
  admit the documented optional socket/phase/layer fields. A live TS renderer
  was not implemented or tested here.
- These clips provide reviewable artwork evidence, not automatic human visual
  approval or completion of the broader gameplay recovery plan.

## Follow-up: residual projectile rotation

### September 21 correction: Fireball travel must also align

The earlier instruction below to keep Fireball's orientation unchanged was too
broad: its ground explosion and its travelling sprite require different rules.
User review of `20260921T001500Z-8cd69a` found the projectile sliding obliquely.
In the saved mage cast, cameras 0–3 need residual rotations of +12.1°, −8.3°,
−15.2° and +17.5°; the selected recipe supplied zero for all four. Cannon travel
also remained unrotated while its real flight tangent changed along the curve.

Bounded plan, reviewed before editing by `fireball_antislop` and `fireball_ecs`:
use the existing travel-phase `fineRotation: "isometricHybrid"` override only.
Keep the overall `none` mode, which preserves the ground explosion's orientation.
No trajectory, socket, pivot, scale, speed, backend, importer or renderer change.
The source capture's camera `(12, 9.797958971, 12)` matches the canonical 2:1
projected row basis; travel has a centered anchor and zero offsets. It needs
residual alignment of the actual exported rows, not replacement artwork.

Completed: the selected Fireball JSON now owns that one phase override. Eight
new regression cases failed before the change and pass afterward. They load the
actual selected Fireball recipe, test mage/cannon travel across four cameras and
five points along the flight, and preserve positions, rows, clocks and impact.
The device opt-out test now explicitly disables the phase override as well.
Running the adjacent suite exposed an older movement import assertion that still
required empty optional media; it now checks retained source timing together
with the selected local Jump/Haste/Dash media. The Sleep sprite assertion also
explicitly requires a sprite sample, fixing its existing union-type error.

Validation: 84 focused cases across tangent projectiles, authored projectiles,
device animation and pending-spell presentation pass after those test corrections;
the three edited test modules pass Pyright. Six saved-event clips, 1,202 frames,
both observers and four cameras each pass with zero presentation gaps:
[Fireball alignment review](http://127.0.0.1:8767/runs/20260921T081914Z-ec0461/index.html).
The mage input files are byte-identical to the user's reported run. Actual
rendered projectile before/after contact sheets were inspected; residual rotation
now follows travel while retaining the authored animated fire/sparks.
Human visual approval remains pending.

User review found Eldritch travel art locked to the eight canonical directions.
NeuroClient's `SpriteProjectileFx.ts:776` selects the authored row and then, for
`isometricHybrid`, rotates by the actual trajectory angle minus that row's
canonical projected angle. Its preparation caller supplies no trajectory angle.
The Python sampler and Pygame blitter already implement this contract; the new
point-spell importer incorrectly replaced the inherited mode with `none`.

Requested behavior: preserve authored directional rows and their residual
alignment to the real hand-to-body path. Boundary/input: loaded selected JSON,
public cast sampling/projection and actual saved-event clip playback. Expected
output: aligned travel/impact across four cameras, socket offsets and height
differences, with unchanged preparation, trajectory and mechanics.

Bounded correction: remove the point-spell importer override and restore the
three selected point recipes. Keep Fireball's ground artwork orientation as
authored. Anti-slop reviewer `spell_data` verified export directions and the
handoff: the prohibition on faking all directions from one rotated row does not
prohibit residual rotation after selecting an actual authored row. ECS/anti-OOP
reviewer `ashen_native` confirmed this needs no backend, schema or renderer
change. Add an observed alignment regression and rerender saved point clips.
The initial 24 flat/socket alignment cases reproduce the defect before repair.

Completed: importer override removed, three selected JSON values restored.
All **142 focused tests pass**, including the expanded 36-case alignment matrix
and original NeuroClient playback references. The
[corrected 16-clip gallery](http://127.0.0.1:8767/runs/20260919T161448Z-2a27a7/index.html)
passes from saved inputs, with zero native events generated. Direct comparison
confirms identical input bytes, initial/latest states, lineages and semantic
frame samples. Compiled heads differ only in the recipe's fineRotation value;
rendered pixels/bounds intentionally differ. Four-camera Eldritch before/after
images and comparison results are retained in that run's `inspection/` folder.

## Follow-up: Fireball contact, spreading Ashen and travel tuning

User review requires Ashen during the blast, starting at contact, with a possible
outward expansion. Fireball travel should be faster and its projectile 20% larger.
The observed defect is at the historical boundary: ground arrival is compiled,
but its world after-values are not assigned `state_at_effect`; Ashen only appears
when the head settles. Native conditions and recorded packets already contain
the correct changes.

Requested boundary/input: real saved Fireball lineages through shared history
sampling and painting. Expected output: no new Ashen before impact, the center
marked at contact, surrounding new marks revealed outward during the blast,
old marks retained on repeated hits, and the same final permitted state.

Bounded plan, with anti-slop (`spell_data`) and ECS/anti-OOP (`ashen_native`)
review: attach area world changes to the existing ground-impact anchor; add an
explicit optional presentation `area.surfaceReveal` for selected residue IDs and
spread speed. Schedule recorded changes once on the existing history clock,
using disclosed contacts and world distances. Preserve atomically recorded
updates, existing marks/faces and actor reaction/HP timing. Do not reuse Studio's
temporary geometry animation fields as persistent-condition semantics.

Use 10 tiles/second for Ashen (400ms over the native 20ft radius), beginning at
contact. Increase travel from 180 to 360 Studio pixels/second, retaining its
150ms minimum. An optional phase scale sets travel to 0.6 while impact retains
0.5. These are documented presentation adaptations, not new backend facts or
spell-specific executors. Verify contact/spread/repeat through native recordings,
phase sizing through the shared draw path, and regenerate paired Fireball clips.

Completed and reviewed: the real contact regression failed before the correction
and passes afterward. The delta comparison deliberately uses `displayed_before`,
not the binding state's already staged after-values. Surface scheduling compares
the selected residue values, including full wall faces, and uses one placement
time for removal/replacement pairs. An independent native opposite-side cast
probe verified removal then union-face application at the same 150ms delay.
Repeated recorded casts with zero surface changes retain existing marks.

Saved-world sampling at pre-contact/contact/+200/+500ms gives 0/1/13/48 Ashen
tiles in the open scene and 0/1/12/36 at the wall. Actor bodies, conditions and HP
matched across 35 comparison samples with reveal enabled/disabled. No source
query, native mutation, new executor or second rendering clock was introduced.

The [14 updated Fireball clips](http://127.0.0.1:8767/runs/20260919T162630Z-c573f3/index.html)
pass all checks across 1,594 four-camera frames. Input bytes, initial/latest state
and lineages are unchanged from the prior gallery; historical contact timing and
surface reveal intentionally change. The replay process created zero native
events. Root inspected east/north walls, open/closed doors and aftermath frames;
images and direct comparison evidence are in that run's `inspection/` directory.
47 targeted contact/media checks pass; 169 separate animation/history/interaction/
residue/trap checks pass; the final expanded area suite passes 76. These sets
overlap. Targeted Pyright reports no errors. Both independent reviews approve
the timing/size implementation.

### Wall coverage clarified after user review

The user asked whether the original wall handoff was actually being tested.
Current native clips cover straight solid walls on two axes, closed/open doors,
both observers and four cameras. Pixel tests cover physical ground shadows,
both blend modes, finite wall ends, L-shaped boundaries and vertical extents
below/within/above the wall band in every camera. Below the base of a suspended
wall is intentionally outside its blocking volume; this is not a waiver for
rendering through an ordinary grounded wall.

The full handoff's rear-wall alpha silhouette re-admission remains unimplemented.
That feature allows near-side fire to overlap the actual visible wall face while
still excluding space beyond it. Current ground masking is conservative and can
over-clip the lower rear-wall face; a reviewer confirmed the geometric case.
This does not demonstrate spill beyond a solid wall, but it is an explicit
presentation gap. Full elevated and L-junction native scene videos also remain
unproven. Do not describe the ground mask tests as exhaustive wall-art acceptance
or conflate this face-overlap gap with the separate elevated-smoke limitation.
# Foreground wall leak correction — 2026-09-19

Requested behavior: Fireball east-boundary/caster camera 0 must not paint over
the foreground wall. The same applies to boundary orientations, camera sides,
and the solid parts of open/closed doors. Boundary: final `draw_frame` pixels
from retained player state and sampled area artwork. Input: the existing saved
Fireball histories and small explicit map-composition fixtures. Expected:
foreground structural pixels remain covered, while exposed fire remains visible.

The reproduced cause is one painter key for the whole explosion against separate
keys for wall segments. Some segments of a continuous foreground wall sort before
the explosion and get overwritten. Ground-propagation masks alone cannot establish
camera occlusion. Their passing tests did not establish correct scene composition.

Bounded implementation: carry the area origin explicitly in a shared draw-command
value; collect the actual submitted wall/frame/leaf silhouettes in the map painter;
classify the foreground side using the physical boundary plane and camera direction;
mask overlapping area pixels for both normal and additive layers. Preserve native
facts, playback timing and ordinary painter order. Open doors still have solid
frames/leaves. Use their submitted pixels, not a full-cell doorway rectangle.

Anti-slop reviewer: `spell_data`. ECS/anti-OOP reviewer: `ashen_native`. Both
independently confirm this ownership and reject spell/camera overrides or drawing
all walls last. Rear-wall face re-admission needs separate face-overlay ordering;
it is not silently included in this foreground correction. Mixed composite corners
also require bounded acceptance rather than claiming full per-face depth support.

Validation: reproduce the failure at the final-image boundary first; check real
walls and doors, both blends, camera rotation, both sides and raised supports;
rerender the existing paired Fireball inputs from four cameras and inspect frames.

Completed: `game/draw_commands.py` holds the shared passive command value with
an optional area origin. The map painter collects the exact submitted boundary
sprites; `game/area_media.py` masks foreground overlaps for the shared area path.
No spell-name or camera-number exception, native rule change, asset scan, or
alternate actor ordering was added. Actual source images remain unchanged.

Results: 64 final-image cases pass; disabling foreground occlusion reproduces
1,629 changed opaque wall pixels in the first east-wall case, versus zero with
the correction. Open-door cases also assert visible fire inside the aperture.
250 related tests and 41 gallery/live/ranged/trap tests pass; targeted Pyright
reports no errors. The
[14 updated clips](http://127.0.0.1:8767/runs/20260919T164739Z-060990/index.html)
pass across 1,594 four-camera frames. All saved input bytes, initial/latest states,
lineages, bound heads and frame traces match the preceding run exactly. Images
were inspected for both axes and both door states. The inspection directory
contains the direct comparison and extracted frames.

Both reviewers approve the delivered opaque pixel-art foreground correction.
Review limits: mixed-corner silhouettes conservatively cover both arms; matching
raised supports are tested, not every mixed-height scene. Rear-face flame overlap
still needs its separate composition fix. This is not general translucent-wall
composition: partial alpha can be attenuated twice when a masked wall is drawn
later. The inspected wall/door sprites have at most one partial-alpha pixel each.
No broader transparency feature is implied by this change.

The ECS review's warm local probe measured 0.73ms/frame for the map and 2.43ms with
the sampled effect; foreground masking averaged 0.70ms/layer across 60 calls at
960×640, zoom 0.5. These exclude asset loading and sampling, and are not whole-game
startup or throughput measurements.

## Exposed wall contact correction — 2026-09-19

User clarification: an exposed, physically reachable wall face must receive the
fire and remain charred. The forbidden behavior is crossing or appearing beyond
the wall. Existing native receiving-face conditions, subjective after-values and
soot rendering are already connected; paired saved replays show seven marked
sections, with only the contacted side darkened. No new mechanics are required.

Bounded plan: defer area composition until the actual boundary sprites are known.
Carry the raw layer plus the existing captured area geometry as passive draw data.
Partition it into the ground-masked image and disjoint reachable rear-wall slices.
Place each slice immediately above its receiving wall in the ordinary painter
order, preserving actors and foreground occlusion. Check reachability against
other captured blockers at the wall's world-space footpoint, not at its projected
elevated pixels. Preserve both normal and additive layers, source images, existing
Ashen timing and native recorded inputs. No draw-all-walls-last rule or spell/camera
exceptions. Mixed front/rear composite corners retain conservative occlusion.

Anti-slop reviewer: `spell_data`; ECS/anti-OOP reviewer: `ashen_native`. Both
confirm presentation ownership. Acceptance: actual layer pixels touch the exposed
rear face without reopening the foreground leak or lighting a blocked farther
wall; ordinary foreground bodies still occlude the effect. Re-render paired saved
wall/door clips in four cameras and inspect contact and charred aftermath.

Implemented: raw area layers now reach the shared map compositor with a passive
ground-contact/retained-geometry payload. The compositor partitions ground and
receiving-wall pixels, then inserts each wall slice at that wall's painter depth.
It neither derives contact from old Ashen marks nor changes any native event.
The new exposed-face test failed with zero receiving pixels before the repair.

Validation: 104 final-composition tests pass, including the original 64 foreground
cases, 32 rear-wall/door views and eight two-wall/body/blend cases. The latter
requires an intervening wall to hide the farther wall's elevated top, exact single
blending on overlapping opaque silhouettes, and normal foreground-body occlusion.
The combined composition/timeline suite passes 180; the separate native area,
projection, scorch timing, replay and media suite passes 171 (overlapping sets).
Focused Pyright reports no errors. Both independent reviews pass.

Review identified actual repeated mask work, which was removed before completion.
Geometry masks are now bounded to four views per historical cast and shared by
normal/additive layers. Pre-soot silhouettes retain the same alpha while persistent
marks reveal. A fresh-frame/cached-frame comparison is byte-identical. The same
11-wall warm probe measures both layers at 0.61ms for a 768-square canvas/half zoom,
and 4.87ms for a 1536-square canvas/full zoom; the uncached first draft measured
8.76ms and 28.35ms. These exclude native execution, decoding and the rest of the
frame. Source surfaces stay unchanged and unlocked. No integrity/source scan is
part of this reuse.

Limits remain explicit: mixed front/rear composite corners conservatively occlude
the complete corner sprite. One fractional edge pixel per east wall sprite is
outside the opaque-overlap equality test; general stacked translucent surfaces
were not expanded into this work. Stair-shaped soot and volumetric smoke remain
the previously documented limits.

The [updated 14-clip gallery](http://127.0.0.1:8767/runs/20260919T172957Z-0a2de3/index.html)
passes across 1,594 four-camera frames from both participants. Saved input bytes
are unchanged from `20260919T164739Z-060990`. State, lineage, bound-head and frame
traces are equivalent after admitting the `TileResidueState.amount=1` default
introduced by the separately pending blood integration; old traces omit that
field. The comparison preserves both exact and normalized results explicitly.
No mechanics were rerun to generate these clips. Contact and charred aftermath
were inspected for both axes and door states; extracted frames and comparison
results live in the run's `inspection/` directory.

## Received art handoff — September 20

Initially queued ice production-v8 from art task
`01a0b6af-5fa9-7ec0-9915-0ecee0a6baec` was subsequently authorized after the
material-creature review. Implementation and final validation are recorded in
[the new spell integration plan](ICE_SPELL_AND_PALETTE_INTEGRATION_2026-09-20.md).
Source handoff:
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/docs/ICE_SPELL_PRODUCTION_HANDOFF_2026-09-20.md`;
package README and manifest are under
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ice-spells/production-v8/`.

The source task reports revised Ray of Frost, Ice Knife and Chill Touch media,
with authored per-facing registration, palettes and alpha/additive phases.
Preserve shared timing, sockets and depth ownership when integrating; do not
recenter individual frames. It also relays the requirement for exact per-spell
caster effects and target flashes across all authored spells, preserving actor
body/clothes outside the isolated effects and the existing 150ms target flash.

A chilled-ground design proposal was also requested: distinguish cosmetic traces,
mechanical freezing and ground hazards, and consider existing blood/charred
state. The [reviewed proposal](CHILLED_GROUND_PROPOSAL_2026-09-20.md) preserves
that distinction. No ground-freezing behavior was added by this integration.
