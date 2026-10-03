# Summoning presentation, flight and creature corrections — final phase

Date: 2026-10-03. Status: design for independent anti-slop and anti-OOP/ECS/import-DAG
review; implementation has not started for the new integrations below.

This is the final amendment to [the unified summoning plan](SUMMONING_BACKEND_PLAN_2026-10-03.md),
not a new roster or spell expansion. The human requested a planning checkpoint
before proceeding and explicitly **accepted the summoning artwork in this chat**.
That acceptance supersedes the artist handoff's older candidate label. Integration
acceptance still requires native gameplay. No Git commit is part of this work.

## 1. Scope and current evidence

Deliver these together:

1. Finish received-damage/blood, Prone/recovery/death sorting and Wolf scale
   corrections raised on the original 38-clip gallery.
2. Integrate **Fly only** from the final utility artwork delivery. Naturally
   winged Huntsman/Fellwing and spell-granted flight share movement presentation.
3. Integrate accepted summoning S1/S2/S3/S5. S4 already uses the existing Fey
   material and needs no additional halo artwork.
4. Verify six demon scales against original silhouettes and show them together
   with a modular human on real paving. Preserve intended differences.

No Telekinesis, Antimagic, other queued spells, new monsters, creature mechanics,
airborne combat/hovering, stacked multi-Z, new body artwork, or external artist
messages. Existing native Fly grants speed and permits admitted ground-to-ground
movement; this phase does not add a second flight action or pathfinder.

Source handoffs (read in full for the selected work):

- `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/PRODUCTION_VFX_BACKLOG_HANDOFF_2026-10-03.md`
- `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/final-utility-batch/HANDOFF.md`
- `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/summoning-vfx-study/HANDOFF.md`

Observed gaps, rather than assumed missing systems:

- The old gallery showed outgoing attacks, not enough incoming injury/death.
  Ordinary new beasts/devils lacked the existing normal blood response. Current
  bounded correction installs it; Corrosive/Dread retain one special response.
- A further smoke capture found lethal summoned-Wolf damage losing its blood
  in the player packet. The native handler runs, but premature retirement removes
  location evidence before DamageApplied completion freezes observer permissions.
  Terminal departure also precedes the damage/life facts. This is a real native
  ordering defect, still unfixed at this planning checkpoint; visibility filters
  must not be weakened to hide it.
- The modular fall sheet moves the body/shadow across the ground while the old
  painter key remains at standing contact. The bounded `ground_depth` socket
  correction is source-reviewed; corrected native overlap acceptance is pending.
- Flying movement is already recorded as its own mode. The current shared
  renderer defaults to walking timing/pose; Huntsman's planted Idle override is
  an unresolved placeholder. The temporary Run substitution was withdrawn.
- `ConditionAppearanceLayer` exists but its runtime support is explicitly absent.
  Do not claim that adding Fly JSON alone makes manifested Bag8 wings work.
- Native summon origin and terminal reasons are recorded, but public player facts
  retain only manifestation, faction and a terminal-departure boolean. The new
  cues require narrowly projected event provenance, not live-engine lookups.

## 2. Decisions that stay fixed

**Flight:** ground start and ground end, no persistent hovering or new altitude
state. No walking/Run animation disguised as flying. A Fly condition can remain
while a creature stands, attacks or chooses ordinary walking. Only an actual
recorded flying move selects flight motion. Source-owned Fly expiration must not
remove innate flight or somebody else's wing appearance.

**Wings:** modular recipients use the accepted existing Bag8 wings and cyan wind
treatment. Native-wing rigs keep their own wings, including when Fly is cast on
them. Existing equipped/manifested wings do not gain a duplicate pair. Fixed
non-winged bodies keep their anatomy and use the magical wind treatment with an
authored airborne pose; do not paste humanoid Bag8 wings onto an incompatible rig.

**Shadows:** use the original separate shadow layers, their registered alpha and
ground contact. Never import the artist's demonstration actors/floor or generate
oval shadow replacements. Fey color/reveal/dissolve operate separately from
neutral shadow RGB; reveal/removal can fade body and shadow together.

**Scales — explicit human correction after plan review:** all six demons use
**1.00**, retaining original artwork proportions. Remove the unrequested inherited
Small 0.82 / Large 1.28 multipliers; gameplay Size does not authorize a change in
their artwork scale. No demon enlargement or shrinking is proposed. Original
128-pixel cells contain different silhouettes; do not normalize their bounds.
Preserve the explicitly approved animal enlargements: Wolf 1.30, Raptor 1.55,
Mammoth 2.60 and the other already approved animal values. Audit current animals
for unintended shrinking and report any older out-of-batch scaling separately.

## 3. Work packets and exact ownership

### A. Finish injury and pose corrections first

Owners: `dnd/monsters/{srd_roster,beasts,fiends,demon_variants}.py`, existing
`dnd/body_responses.py`, `dnd/summoning/system.py`, existing damage/retirement
owners; `game/animation_draw.py`, `game/animation_types.py` and pose socket data.

- Keep normal blood registration in canonical creature construction, so ordinary
  and summoned instances agree. Special blood replaces normal blood exactly once.
- Repair the lethal ordering at the existing completion/retirement boundary:
  move SummoningSystem's defeat hook from DAMAGE_APPLIED pre-completion to the
  existing outer TAKE_DAMAGE pre-completion, retaining DEATH/INSTANT_DEATH hooks.
  `Entity.receive_damage` settles DamageApplied/body response and normal life
  transition first; Death's hook already follows its life-state transition.
  The zero-HP death-save branch is covered by the outer TAKE_DAMAGE hook.
  Preserve completion-time observer evidence, one terminal release and cleanup
  in the same causal operation, before any later action/AI selection. Do not add
  a new damage event, bypass body handlers or delay retirement until a game turn.
- Keep the existing measured fall-depth correction: change painter placement
  from source ground displacement, not entity position, sprite origin or height.
  Cover fall, final Prone, ordinary death and reversed recovery in four cameras.
- Ordinary lethal injury ends in its existing corpse/death pose. A defeated
  summon shows its actual hit/terminal response then dissolution, with no retained
  corpse. The full ordinary Die duration must not become a gameplay lifetime.

Exit: actual injury histories and independent review of outcome/terminal order,
not only assertions that the creature eventually disappeared.

### B. One shared flying movement presentation

Owners: `game/animation_types.py` (existing movement/body data),
`game/choreography.py` (`bind_motion`, `MotionLeg`, `motion_leg_contact`, shared
sampler), `game/animation_data.py`, `game/data/movement-media.json` and existing
per-rig JSON. The loader currently reads original voluntary movement defaults from
`game/data/neuroclient/source/src/render/data/animation/actionContextPresentation.json`
then overlays `movement-media.json`. Put the optional typed flight profile in that
existing local movement document and load it into the voluntary context; leave
the preserved source copy unchanged.

- Add one optional typed flight profile to the existing voluntary movement
  context: takeoff/cruise/landing phase proportions, bounded visual clearance and
  default `BodyContext`. This is data consumed by the existing motion binder, not a new
  flight runner, event consumer or movement registry.
- Keep exact `MovementBodyQualifier(mode, trajectory, connector)` selection.
  Use existing normalized `frameKeys`, including repeated frame values to hold
  an airborne pose, without a new body-context schema. Source inspection found
  Huntsman's Jump frames 5–8 suitable for glide (takeoff 0–4, landing 10–14).
  Fellwing has no Jump/Fly strip: Attack4 frames 4–6 are an airborne candidate;
  only those phases may be reused, never its full attacking/stomping sequence.
  Its Roll and Slide are unsuitable. Import that original body/shadow pair through
  the existing fixed-rig importer if selected. These are frame candidates, not
  accepted final animation; verify all eight rows in actual movement.
- Modular source candidate: AttackRun frames 6–8, holding 7 during cruise, with
  matching original body/Bag8/equipment/shadow frames. These are not currently
  registered flight bindings. Preserve the existing NeuroClient-modified
  NakedBody source; it differs from the vendor ZIP, whose matching Bag8/gear
  banks can otherwise be reused. Never replace the current body to simplify an
  import. Missing source alignment is a visible review finding,
  never permission to substitute Run. No invented flapping where the source has
  none. Measure source-baked body/shadow displacement so authored lift is applied
  once and all attachments retain the correct source pivot.
- Fixed non-winged Fly recipients get explicit held source poses with magical
  wind and shared lift, selected in their existing rig data. Their Run-based jump
  mappings are not flight defaults. Audit coverage across current legal recipient
  rigs; source pose selection does not change their ordinary actions or anatomy.
- Evaluate one continuous lift envelope over each uninterrupted admitted flight
  span, not one bounce per tile. Preserve every authoritative path leg, turn,
  stop, speed, reaction and endpoint. Do not replace the path with a direct chord.
- Interpolate recorded support elevations and apply visual lift separately.
  For admitted rising/falling edges, clear the known support riser and settle
  relative to destination elevation, never global zero. No new authoritative Z
  field or clearance admission rule. An impassable native wall stays impassable.
- Pauses, reactions, cancellation and return use the same sampled body contact;
  do not snap to a standing origin or keep a completed endpoint mask while moving.
  Hidden path segments stay hidden and are not reconstructed from the root path.
- Expose the same contact to body, equipment, wings, wind media, hit effects and
  depth sorting. Ground shadow remains at support. No per-layer duplicate path
  calculation or last-frame black mask.

The backend already validates per-edge flight and computes 3D support-distance
cost on elevation changes (`dnd/actions.py`, `dnd/core/gridmap.py`). Preserve
those rules. If a native admissibility defect is reproduced, report it separately
before expanding this phase; visual lift cannot authorize travel through a wall.

### C. Fly's source-owned appearance

Owners: `game/condition_types.py`, `game/condition_animation.py`, existing rig/layer
composition in `game/animation.py` / `game/animation_draw.py`, condition recipes
and registered media. `dnd/spells/transmutation.py` continues owning Fly mechanics.

- Implement the already-declared condition appearance-layer path needed by Fly,
  rather than creating a fake backpack item or mutating native equipment.
  Resolve immutable extra rig layers from current condition membership and pass
  them into the normal equipment compositor at its existing backpack order.
- Encode native wing capability in passive rig data. Deduplicate native/equipped/
  condition-owned wings through resolved appearance; no creature-name branch.
  Keep actual backpack items and their bonuses. On last Fly-owner removal, retire
  only its temporary overlay/wind and expose unchanged ordinary equipment.
- Keep source ownership when two grants overlap; removal of one does not clear
  another. On winged demons, Fly removal leaves innate wings and innate speed.
- Wing frames use the selected body's same viewed facing, source frame and clock.
  Where a required Bag8 bank is absent, inspect the original existing pack and
  register only the needed original frames; never substitute misaligned frames.
- Register Bag8 for all reachable ordinary body clips while Fly remains active
  (standing/casting/hit/death as well as flight). The existing Bag8 palette and
  declared condition-layer schema supply the material/attachment inputs; bind
  accepted cyan coloration through palette replacement and bounded glow. Do not
  route this through legacy multiplicative tint or claim the exact Fly treatment
  is already implemented just because those schema fields exist.
- Use accepted cyan wind from its existing registered Longstrider dependency;
  don't import Telekinesis/Antimagic banks from the same manifest. Keep finite
  manifestation/removal separate from the condition's real duration.
- Standing is grounded. The handoff's tentative hover pose is not a gameplay or
  animation requirement; choose the flight pose through B's source inspection.

### D. Summoning media and typed lifecycle cues

Owners: existing `game/player_facts.py`, `game/player_projection.py`,
`game/player_reduction.py`, `game/presentation.py`, `game/choreography.py`,
`game/choreography_draw.py`, normal paged-media loading and authored JSON.
A small `game/entity_lifecycle.py` may contain pure bind/sample functions and
passive cue records, feeding the existing choreography traversal once. It must
not introduce a second renderer, event bus or summoning simulation.

1. **Project only observed facts.** Expose a witnessed creation fact tied to the
   existing `EntityCreatedEvent`, with minimal manifested family/causal identity.
   Carry the required terminal cause/identity on the existing spatial fact and
   exact control-loss provenance on the existing faction fact. Preserve older
   recordings with absent optional provenance and no invented lifecycle effect.
   Do not export the complete private summon rule/recipe/control record.
2. **Bind data, not spell code.** One lifecycle recipe family selects natural,
   Fey and Fiend palette replacements and finite media phases. Existing cast
   lineage/release schedules S1; witnessed creation schedules S2; terminal spatial
   release schedules S3; Fey control-loss faction change alone schedules S5.
3. **Single causal scheduler.** Add these cues to the existing bound choreography
   and timeline traversal. Do not scan event history again in drawing, match
   by names/timestamps, or invent presentation events. Root and nested movement/
   reaction consequences use the same route.
4. **Retiring presentation only.** S3 retains the last permitted actor pose/contact
   for a finite dissolution after native removal. This is immutable playback data,
   never a recreated gameplay entity or an active actor available for targeting.
   Actor and shadow are removed exactly once; ordinary deaths use the ordinary path.

Exact delivered clocks at 32 FPS:

| Cue | Duration | Required marker / behavior |
| --- | --- | --- |
| S1 caster accent | 0.750 s | Decorative release 0.250 s; align to actual caster gesture release, retaining the gesture's original FPS. |
| S2 arrival | 1.750 s | Body reveal 0.500–0.625 s; tail stays at recorded birth point when actor moves. |
| S3 departure | 1.500 s | Dissolve 0.1875–0.6875 s; body and shadow absent by 0.6875 s. |
| S4 Fey material | Existing | Existing blue replacement and body alpha 0.7, original neutral shadow. |
| S5 control break | 0.750 s | Bond release 0.1875 s; same identity/HP/position/lifetime/Fey material. |

Arrival must be readable before the first visible action; use the existing causal
presentation milestones and trim/accelerate reveal if required. Never postpone
native actions. A lethal hit's feedback precedes terminal disappearance. Independent
recipients/effects with the same causal start run together, not serially per actor.

Hidden births/departures produce no cue. Reacquisition produces no birth. Contact
loss produces no departure. Seeking samples original clocks; no restarts. All
native `CLOSED` releases are silent: the existing owner uses this same cause for
shutdown/reset and supplies no separate witnessed gameplay-close intent. S3 runs
only for `expired`, `dismissed`, `defeated` and `sustain_lost`. This deliberately
narrows the handoff's illustrative `closed` branch to the actual engine contract;
do not invent a discriminator or infer shutdown from missing parents/timestamps.
Replacement
retains distinct old/new IDs and can show departure/arrival concurrently.

Preserve 32 unique neutral RGBA pages (4,640,796 bytes), four camera registrations,
crop offsets, pivot [192,249.6] and actual phase times. Family colors use palette
replacement, not tint multiplication. VFX scale is independent of body scale:
supported range 0.50–1.65; the art's Wolf 0.68/Mammoth 1.65 examples are starting
values to check with the current canonical bodies, not gameplay sizes.

### E. Clipping, installation and acceptance

Reuse `game/boundary_occlusion.py`, current world/body ordering, observed contacts
and existing visibility masks. Source front/back banks only wrap their owner;
they are not universal wall-depth evidence. Check finite walls, exposed corners,
window apertures and adjacent bodies in four views at intermediate flight and
effect times. No fixed end-state mask, blanket wall-over-everything rule, or
new black fill to conceal clipped pixels.

Keep ground/rear/body/front commands registered separately. For an effect that
actually intersects geometry, demonstrate clipping from the existing registered
geometry/masks. Do not hide failure by suppressing the whole effect. If that is
insufficient, record the reproduced defect and exact additional spatial consumer
needed before requesting any companion. No blanket XYZ imports; never discard Y
if a specific accepted companion is required.

Use `ASSETS.md`: archive exact originals privately, stage selected resources,
install local/private copies with matching hashes and update the existing asset
manifest. Public files contain registration/recipes only. Reuse paged media and
its current importer primitives; add a bounded summoning intake adapter only for
the supplied manifest, not a new asset framework. Never overwrite source exports.
No artist/Godot job is needed for ordinary integration. Render review videos serially.

## 4. Verification and stopping point

Each packet gets independent anti-slop and anti-OOP/ECS/import-DAG review before the next
depends on it. Review actual code and observed outcomes; passing metadata checks
are not visual acceptance. Final reviewers examine the combined source and clips.

| Boundary | Required evidence |
| --- | --- |
| Injury | Normal and special blood exactly once; nonlethal and lethal; ordinary corpse versus summon departure; no retirement before committed injury consequences. |
| Pose/scale | Wolf hit/Prone/stand/death; four-camera peer/wall overlap; human plus all six demons on identical paving; no stretched body pixels. |
| Flight | Modular Fly plus Huntsman/Fellwing innate; walking remains walking; Fly on innate flier; eight viewed headings, short/long/corner paths, supported rise/descent, interrupted motion and grounded landing. |
| Appearance | Equipment/wings/facing/frame alignment; original grounded shadows; backpack preserved; overlapping grants and removal; one fixed non-winged Fly recipient; no duplicated wings. |
| Summoning | Three families; small and large body; birth then immediate action; dismissal/expiry/sustain-loss/defeat; Fey control loss with no despawn; replacement; hidden creation/retirement, reacquisition and seek. |
| Geometry | Foreground/background solid wall, window aperture, adjacent actor, support-height edge; moving body and media obey the same current contact and masks. |
| Architecture | No backend media IDs, new native duplicate events, species executors, late imports, live-engine reads during playback, speculative fallback or import cycle. |

Use `HOW_TO_TEST.md`: native commands/events and recorded packets as test inputs,
not direct state mutations to stage success. Retain actual floor assets and the
standard paired-observer/four-camera engine gallery. A case can cover multiple
rows; do not create an exhaustive cartesian product of redundant videos. Inspect
the reported bad frames and intermediate frames, not just start/end screenshots.

Focused tests cover native blood/terminal order, condition layers, movement/replay,
geometry and media admission. At source freeze run the full engine/game suites
once, plus typing/architecture checks; record and reconcile failures rather than
silently changing expected results or looping full suites during visual tuning.

The prior complete status covered the original scope and insufficient injury
footage. Append a correction/addendum to the implementation ledger rather than
claiming those old clips prove this phase. Completion requires the integrated
native gallery, inspected flight and lifecycle outcomes, exact source/media
receipts and both independent final approvals. This planning checkpoint itself
does not claim any new art is installed or any new flight pose is accepted.
