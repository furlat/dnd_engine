# Body releases, persistent residue, skeletons and demons

Date: September 19, 2026. Branch: `codex/recovery-design`.
Status: selected native profiles, paid dread retreat, passive presentation and
the playable workshop are implemented. The delivered floor/burst artwork is
integrated; 22 paired four-camera clips are available for visual review.
Section 13 records the implementation, validation and remaining limits.
The narrowed A0 integrated run passed 195 tests. Four jump-only clips replay
identically; two ordinary views are accepted and two interrupted views retain
a documented visual discrepancy. Flight/hover remains outside this unit.
Parent: [RECOVERY_PLAN](../RECOVERY_PLAN.md).
Earlier study: [Bloodied tile discussion](TRAP_STATE_PLAN_2026-09-19.md#bloodied-tile-study--ownership-agreed-implementation-paused).

**User-selected first priority:** repair jump triggering of floor traps
before implementing the body-release and residue features. Phase A0 is a
prerequisite, not optional cleanup after adding new content.

## 1. Outcome and scope

A damaged creature can release its authored substance. Blood splashes, skeleton
fragments and demonic fluid use one shared body-response implementation with
different data. A release can leave persistent state on the affected tile.
That state drives ordinary ground traces, the bloodied spike variant, and,
where explicitly authored, damage or fear when another creature enters.

The result must work in an actual encounter and replay from saved subjective
events without running the engine again. The same native behavior must work
with a modular NeuroClient body or a packaged fixed rig. Pygame consumes the
existing Studio timeline model; no executable TypeScript is required at runtime.

The user has requested:

- A shared damage-response handler installed on each participating creature.
- Blood, bone fragments, poisonous fluid or smoke as possible body releases.
- Tile-owned residue; known spikes on a Bloodied tile use bloodied artwork.
- Skeleton support through both modular Body 2 and the dedicated Undead pack.
- Demon-pack creatures and demonic residue that can damage or provoke a low-DC
  fear save when crossed.
- A full plan before implementation, keeping mechanics and scalable design
  central rather than turning the work into individual VFX demonstrations.

Ordinary blood stays mechanically inert. Harmful demonic blood is separately
authored content, not a retroactive rule for every Bloodied tile or every fiend.
The authorized implementation uses the initial authored content below: positive
effective normal-HP damage with a positive physical component releases material;
blood and bone persist inertly; corrosive blood deals 1d4 acid on ground entry;
dread blood uses Wisdom DC 10 and the user's paid-retreat rule. These are authored
game content, not claims about official D&D rules. AIR injuries record their
release without depositing on a ground tile. Optional smoke, poison and sharp
bones are not prerequisites for completing this unit.

## 2. Verified starting point

This table describes the pre-A0 baseline. Current implementation evidence is in
sections 12–13; do not treat a starting-point omission as a remaining defect.

| Area | Current code/data | Consequence for this work |
| --- | --- | --- |
| Skeleton bodies | `dnd/monsters/bestiary.py` defines `SKELETON_APPEARANCE` with `NakedBody2`; normal/warrior/archer/warlock factories use it | Preserve the modular body and gear path |
| Dedicated skeleton rig | `game/data/rigs/skeletonarcher05.json` maps the existing skeleton archer to Undead pack `5Archer` | Already imported; extend rather than reimport |
| Demon rig | `game/data/rigs/demonbeast01.json` maps Dretch to Demon Beast 1, including separate shadow sheets | A functioning demon foundation already exists |
| Creature experiments | `devtools/animation_review/catalog.json` has demon-dretch and undead-skeleton-archer cases; `tests/game/creature_scenarios.py` executes native movement/combat | Reuse these entry points for the expanded roster |
| Damage consequences | `Entity.receive_damage` emits `DamageAppliedEvent` after mitigation/HP application and before life-state consequences | Body response listens at `DAMAGE_APPLIED / EFFECT` |
| Handler ownership | `BaseBlock.add_event_handler`, target-filtered `Trigger`, ordinary handler removal | One configured instance per body; no map service or global scan |
| Tile conditions | Tiles already host ordinary conditions; application/removal emits `resulting_tile` | Residue can have one authoritative owner |
| Local environmental triggers | `SpatialHandler` and `EventQueue.add_spatial_handler` already index handlers by position | A hazardous tile condition can own a local entry handler |
| Jump contact | Jump publishes ENTER for intermediate cells as well as its destination; parent steps record trajectory and path index | Publish explicit native layer transitions; floor handlers must not infer contact from animation geometry |
| Existing flight capability | `Move` has FLYING mode and Dragon Wings supplies a real `Fly` action | Outside this jump repair; the user rejected expanding A0 into flight/hover rules |
| Hazard/path support | Tile conditions participate in hazard queries; movement paths use a movement revision | Hazard installation/removal must invalidate the existing movement cache |
| Recorded tile state | `WorldTileState` currently exposes condition names, with world-fact projection and remembered tiles | Add stable semantic membership for passive bindings; avoid description matching |
| Public damage state | `DamageFact` carries damage/HP results, but no body-release result | Add the small missing semantic result to saved events |
| Fear | `Frightened` currently checks a visible entity source | Ground-sourced fear needs a bounded explicit source extension |

The native monster modules already contain several skeleton variants. Adding
bone releases does not require a new Skeleton entity class or a second statblock
family. Appearance remains gameplay-inert: `NakedBody2`, a sprite filename or a
rig ID never determines the emitted substance.

## 3. Ownership and data flow

```text
authored creature/body composition
  -> configured instance of shared damage-response handler

action / attack / trap / hazard
  -> TakeDamage
     -> DamageApplied, with recorded body-release result when applicable
        -> ordinary tile-condition application, when deposition is new
     -> existing life-state consequences

later entry into a hazardous residue tile
  -> existing spatial entry event
     -> residue's authored damage or saving throw
        -> existing damage / condition events

complete native lineage
  -> existing observer projection
     -> saved subjective lineage
        -> latest state reduction
        -> independent historical Studio playback
```

These are three distinct facts:

1. **Response configuration:** what this body releases under the qualifying rule.
2. **Occurrence:** what it actually released on this particular injury.
3. **Persistent result:** what now remains on the tile.

Two injuries on one tile can produce two bursts and leave one Bloodied condition.
Seeing that tile later reveals its current residue, not an old splash animation.
Death or departure of the donor does not erase the ground state.

### Creature response

Use one processor configured from authored body/creature data and installed through
the existing owner API. Target-filter its trigger to that creature's applied
damage. Use existing configured-callable patterns and content provenance.
`BehaviorBinding` carries identity and ownership, not arbitrary profile parameters.
It must not be presented as a configuration store that already exists.

The finite response profile needs only:

- A stable semantic release identity/substance.
- Its qualifying damage policy.
- An optional residue profile to deposit.

No extra `has_blood`/`can_bleed` flag merely duplicates the installed response.
No body simulation, blood-volume counters, generic rule-expression interpreter,
new handler manager or processor per monster. If another mechanic later needs a
body fact, expose the authored fact through the existing composition rather than
deriving it from the renderer or adding competing defaults.

Incoming damage type and released substance remain independent. A poisoned hit
does not make a human release poison; an arrow hitting a skeleton can release bone.

### Release record

Preferred first representation: one optional typed release result on the existing
`DamageAppliedEvent`, carried into the corresponding public `DamageFact`.
Record the semantic release identity and the native origin/deposition cell needed
to replay the result. Do not serialize the processor or reconstruct its decision
from a creature factory, current HP, appearance or an unfiltered native registry.

The ordinary tile-condition child owns the persistent mutation. Do not duplicate
the full tile after-value inside the release result. A separate release event is
only justified if actual native rules need to subscribe independently to releases;
do not implement both representations for the same occurrence.

No sprite name, particle count, frame number, tint, animation duration or Pygame
coordinate belongs in the native result. Public projection must apply existing
identity/location disclosure to the added fields. An observed stain must not
expose an unseen donor or the hidden injury that caused it.

The EFFECT handler returns the updated event value through the existing handler
result path (`with_updates`); completion then retains the release result. Do not
post another DAMAGE_APPLIED EFFECT to publish it and invoke the response again.

### Tile residue

Use an ordinary tile-owned condition for each semantic residue profile. One
shared condition implementation can install optional entry behavior from data.
An inert profile requires no entry handler. A hazardous profile owns a position-
indexed spatial handler and returns its UUID through the existing condition
lifecycle so removal releases it normally.

This is one authoritative condition, not a stain flag plus a separate hazard
registry. It can coexist with spikes and other tile conditions. Do not put
residue into the current exclusive `GROUND_SURFACE` spatial-effect slot: spikes
already occupy that slot and different content currently requires a transformation.
Do not create fake trap states to use `PerceivedSpatialEffect` either.

Extend the existing tile after-value with the minimum passive semantic membership
needed to identify active residue and its description. Use stable content identity
and condition identity where source references require it. Native mechanics stay
on the condition; the public tile snapshot does not carry callable behavior.

Same-profile deposition on the same tile retains the existing condition and does
not accumulate damage handlers or stronger stacks. Different profiles coexist;
blood plus bone debris plus a spike fixture is a supported combination. No
automatic mixing, spreading, evaporation, chemistry or conversion is introduced.
Concretely, `BaseBlock.add_condition` indexes and replaces by condition name,
after applying incoming mechanics. Give each authored residue profile a distinct
native condition key/name and check for that profile before constructing/applying
another instance. A repeated burst retains the existing condition UUID and handlers;
this does not require changing the engine's condition index.

**User follow-up during implementation:** ordinary humanoid blood needs different
ground amounts, from a small splat to an almost-full pool. Retain this requirement
for the next blood-content pass without interrupting the active backend/replay
unit. Amount belongs to the existing tile residue and its recorded after-value;
it must not be a random renderer choice or another condition/handler per splat.
The injury-to-amount and repeated-injury accumulation rules have not been selected.
Do not silently apply the same amounts to bone fragments or demonic profiles.

Descriptions follow known tile state: bloodstained stone, scattered bone fragments,
or an authored demonic stain. Describe only what existing observation permits;
the renderer does not supply descriptions back to the engine.

## 4. Proposed content and gameplay defaults

These values make the plan executable and reviewable. They remain proposals.
Keep them in authored content so balancing does not alter the shared processors.

| Profile | Body response | Persistent tile result | Proposed crossing effect |
| --- | --- | --- | --- |
| Ordinary blood | Small blood burst | Bloodied | None |
| Skeleton | Bone-chip/shatter burst; death animation remains separate | Bone fragments | None initially |
| Corrosive demon | Distinct demonic-fluid burst | Corrosive demonic blood | `1d4` acid damage on entry |
| Dread demon | Distinct demonic-fluid burst | Dread blood | Proposed Wisdom DC 10; failure compels a paid retreat toward the entry cell, with fear ending on that exit |
| Sharp bone variant, optional | Same bone family | Explicitly sharp bone shrapnel | 1 piercing damage on entry |
| Smoke release, later content | Smoke burst | None unless explicitly authored | None implied |

Implement ordinary bone debris in the main unit. Sharp shrapnel is an optional
data variant using the same entry-damage capability, not a prerequisite or an
automatic consequence of every skeleton hit. Poisonous fluid remains another
possible profile; it does not imply Poisoned without an authored save/payload.

### Injury qualification proposal

Start with positive **normal HP loss** from physical bludgeoning/piercing/slashing
injuries for blood and bone profiles. This demonstrates wounds from melee, arrows
and spikes while avoiding automatic blood from every psychic hit or temp-HP loss.
The earlier discussion did not approve that policy: confirm it as content when
the plan is agreed. Demonic profiles may use the same starting policy.

Use resolved damage information, not the incoming packet alone. The precise
proposed predicate is positive effective normal-HP damage for the packet and at
least one physical component with positive `after_affinity_damage`. Thus a fully
immune physical component accompanied by poison damage does not qualify merely
because the attack originally contained physical damage. The engine applies later
flat reductions, temporary HP and survival caps to the packet; it does not say
which component consumed normal HP. Do not infer that allocation or implement a
new mitigation pass to obtain it.

Lethal qualifying damage releases material before normal death processing. Do
not add another release merely because the existing death animation also plays.
Bone shatter on a nonlethal hit means chips, not destruction of the whole actor.

### Contact and repetition proposal

- Entry is the initial active trigger. Exit causes no new damage/save; source-owned
  dread fear is removed on its specified retreat exit. Standing still adds no tick
  damage. Deposition under an occupant does not synthesize a second entry.
- Each real exit and re-entry can trigger again. Repeated deposition does not
  multiply one tile's same-profile payload. No new per-turn immunity ledger.
- Damage/save/condition consequences are children of the actual entry event.
- Walk, forced movement, landing and teleport arrival use existing spatial
  semantics. A ground hazard must not hit merely because an airborne path draws
  across its screen position. Jump currently emits ENTER per crossed cell.
  Its trajectory/path metadata exposed the defect; the fix should publish the
  actual layer/contact transition from movement execution, as specified in A0,
  so each hazard need not inspect parent actions or rendering trajectories.
  Preserve intermediate occupancy/sensory events. Misty Step already publishes
  only destination entry.
- The selected repair covers existing floor traps and later residues: jumping
  clear over them does not activate or damage; landing on an enabled trap does.
  Misty Step to supported ground triggers on arrival and has no intermediate
  contact. These are native tests. The earlier flight/hover acceptance expansion
  is superseded by the user's explicit jump-only scope correction.
- Damage profile values pass through existing resistance, immunity, HP and
  condition-immunity rules. No renderer-driven eligibility or implicit faction
  immunity. Same-side and opposing-side entrants are both exercised.
- Different active residue profiles on one tile each retain their authored effect.
  No special blood/bone reaction is required.

Corrosive and dread profiles are distinct authored demon variants. Preserve the
existing canonical Dretch identity/statblock rather than silently giving all
Dretches or fiends homebrew caustic blood. Reuse its appropriate mechanical
composition where useful, then name and describe the variant honestly.

An interrupted jump needs its actual settled ground contact represented by the
native action. Reproduce that case before choosing any missing publication; do
not retrospectively call an earlier interior ENTER a landing or consult animation
height. If an explicit native landing result is needed, publish it at settlement
and feed the same residue contact behavior. This is a bounded ground-contact
connection, not a new falling/flight simulation or a change to opportunity-attack
timing. Cover it before claiming full jump/hazard acceptance.

## 5. Fear from persistent ground

This is the one concrete extra condition capability required by the dread profile.
Current `Frightened` looks in `senses.entities` for its source. A residue UUID would
produce a badge without the intended penalties; using the donor demon would make
the pool's influence depend on whether the donor is still visible/alive.

Add the smallest typed distinction to the existing fear origin: current entity
origin remains the default; a residue origin names its actual condition/tile.
The residue owns this source relationship after the donor leaves. Keep donor
attribution separate from the mechanical source of fear.
Presence means that exact condition is still owned by the tile; an object remaining
in a runtime registry is insufficient. Existing subjective rules govern what is
reported/rendered. The pool's retreat/escape lifetime below must not accidentally
inherit ordinary entity fear's visible-source movement lock.

Reuse existing saves, condition immunity and removal. On success, emit
the real successful save with no transient Frightened application. On failure,
apply the source-owned fear and resolve the retreat below. Do not
apply then remove it solely to demonstrate a successful save.

**User correction during implementation:** dread blood attempts to make the entrant
move back to its previous cell, paying the normal movement cost. Exiting the pool
in that retreat direction removes its fear. If the creature cannot make/pay for
that retreat, it remains in the pool frightened; later available movement must
still permit that escape. This supersedes the proposed one-round generic lock.

Retain the actual entry origin/direction as native condition context, along with
the residue source. A failed save interrupts the requested forward path. Resolve
the retreat and its cost through the existing movement owners, with events parented
to that entry/save response, then remove fear on the actual exit. No position
patch, free shove or animation-only recoil can stand in for this movement.
The original forward movement must retain the interruption after the retreat
removes fear and must report the actual settled position. A nested Move inside
ENTER is insufficient by itself: the outer action currently assumes its requested
step destination afterward and may continue. Settle the entering leg's cost before
evaluating retreat affordability, and charge neither leg twice.

Ordinary entity-sourced `Frightened` currently caps movement at zero; preserve that
behavior. The pool-specific rule must permit its paid retreat rather than reusing
that cap unchanged and making escape impossible. Study the existing modifier and
movement context before choosing the bounded condition-owned implementation; do
not introduce a second movement executor or hardcoded spell branches. A distant
teleport arrival supplies no adjacent return step. The user selected one paid
adjacent step toward the actual departure point on a failed save; this is ordinary
movement with its usual budget and blockers, not a free teleport back.
Same-cell landing likewise needs its causal movement origin, not the landing
ENTER's equal before/after XY alone. Keep automatic retreat orchestration above
the existing action/condition owners in the import DAG; importing Move into
conditions.py would create a cycle. Later escape controls and the retreat's
reaction policy remain content choices, separate from this native wiring.

Acceptance includes a failed save followed by paid retreat and removal, insufficient
movement followed by later escape, blocked retreat, successful save, immunity,
source removal, and a pool whose donor is already gone. Fear is scheduled after
the damage residue path so this source extension does not hold up baseline blood,
bone and corrosive mechanics. It remains part of the requested planned unit.

## 6. Skeleton and demon assets

### Preserve both skeleton paths

1. Modular Body 2 remains the rig for composable skeletons and changeable gear.
   Use the native skeleton factory and real equipment state; bone response is
   installed by creature composition, not by checking `NakedBody2`.
2. Retain the imported fixed `5Archer` rig and its real `QuickShot` mapping.
3. Add selected `6Warrior` sheets to a separate fixed-rig binding for the existing
   authored Skeleton Warrior when its baked weapon/armor fit. Review the visual
   match before choosing that binding; do not pretend baked weapons are modular.
4. Treat `8Necromancer` / `9Wizard` and native Skeleton Warlock as a later roster
   extension within the same import path, not a prerequisite for bone releases.

Source supplied and verified present:
`C:\Users\tommaso\Documents\assets\smallscale\2D HD Undead pack 1.zip`
(`/mnt/c/Users/tommaso/Documents/assets/smallscale/2D HD Undead pack 1.zip`).
The archive lists nine body groups. `6Warrior` includes Idle, Run, TakeDamage, Die,
Attack1/2/3, block, casting and other clips. Clip names are source inventory, not
proof of correct gameplay mapping. No named blood/bone/shatter effect was found
in the member-name scan; inspect art before claiming those effects are supplied.

### Expand the demon package deliberately

Keep the existing Demon Beast 1/Dretch binding. Choose one additional compatible
Beast/Spawn appearance for corrosive content and another for dread content after
visual inspection. The package has Beast, Elite, Spawn and Imp families with
different available clips. This unit does not import every body or invent native
stats to match every image.

Source: `C:\Users\tommaso\Downloads\2D Demons - TopDown assetpack v1.1.zip`.
Selected sheets retain their body/shadow separation. Review facings, meaningful
frame counts, support origin, dimensions, attack contact and held death frame.
Extend the existing per-rig mappings and resource declarations, without changes
to the shared actor renderer for an individual skeleton or demon.

### Required release and residue art

| Asset | Current status | Planned use |
| --- | --- | --- |
| Plain/coated bloodied spike sheets and shared blood overlay | Integrated: 28 directional overlay frames | State-driven spike variant at the existing frame |
| Blood burst and ordinary floor trace | Integrated: one strip and four small-stain views | Injury burst and persistent ground mark |
| Bone-chip burst and scattered-bone ground trace | Integrated: one strip and four floor views | Same release/residue paths for skeletons |
| Distinct demonic fluid burst and ground traces | Integrated: two strips and eight floor views | Readable corrosive versus dread content |

A local `GODOT - Blood (Premium).zip` also exists in Downloads and contains Godot
blood/poison scenes. Its member listing was inspected, not its suitability or
exported appearance. It is an optional art source, not a reason to stop gameplay
work and recover an entire VFX project. Reuse authored exports when appropriate;
Godot may be an offline exporter, never the game runtime.

Request/export only the small missing art set after data contracts are stable.
Art work can proceed separately from native mechanics. Follow the existing
NeuroStudio media schema, pivots/anchors, transparency and pixel scale. Use
existing strip drawing and world drawing; do not build particle physics in Pygame.

## 7. Presentation, timing and replay

One shared release binding maps the semantic release identity to authored media.
The damage/contact timeline provides its start. Current choreography routes
generic damage children through a condition-frame anchor, so wire release timing
explicitly to the existing injury/contact anchor once; avoid offsets per spell,
creature or camera. Ordinary attacks, trap entry and standalone damage all use
that same rule with their existing parent timeline.

Transient media attaches to the actor's historical sampled body/impact anchor.
Persistent residue attaches to the authoritative support tile and its elevation.
The actor may be visually partway through movement during an opportunity attack:
do not snap it or its corpse to the legal tile center to place a splash. The
renderer illustrates the recorded deposition without using particle trajectories
to choose native tiles. Preserve the same 2.5D depth/height handling as other media.

Ground traces are visible from the same state transition as their causal deposit.
Known spikes combine their existing state/frame with Bloodied membership. Use the
delivered shared blood overlay where it reconstructs the provided variants;
poison-coated spikes keep their coating. Do not create a new timing track for
each clean/coated/bloodied combination or a backend trap-blood flag.

Subjective playback requirements:

- Only permitted release identities/locations enter a player's recorded stream.
- Late observation shows a residue snapshot without inventing an injury event.
- Hidden fixtures remain hidden even if the floor is bloodied.
- Offscreen mutation follows current world memory and re-observation semantics.
- Pause, seek and later backend turns preserve historical playback speed/state.
- A fresh process replays saved public input after native teardown, without
  creature factories, rule processors, live registries or artwork-dependent rules.
- The new passive result and recipe data remain directly representable in JSON
  for a future TypeScript consumer; no Python callable crosses that boundary.

At the recording boundary, account for these additive fields explicitly.
`game/event_record.py` checks every retained native model field, including fields
with defaults; merely adding an optional field would reject existing archives.
Use its existing `ADDITIVE_FIELDS` mechanism for genuinely absent legacy facts
(no recorded release/layer), and the ordinary player-fact defaults where relevant.
Absence in an old recording is not proof that a creature was grounded: retain
existing playback without inventing new contact facts. New layer/contact acceptance
uses newly recorded events. No general migration framework is needed.

## 8. Implementation sequence and deliverables

### A0. Close the demonstrated jump/floor-contact defect first

**Scope correction from the user:** “we are not implementing flight stuff … we
were just fixing jump.” The earlier flight/hover expansion and its demand for a
Land action, landing price or wing-dismissal policy are withdrawn. They are not
prerequisites for this repair or for body/residue work. The user also clarified
that movement lands; do not turn that clarification into a flight feature.

Requested behavior: a native Jump crosses floor traps without activating or
applying them, then makes ground contact at its actual landing cell. Walking and
Misty Step arrival retain existing ground contact. Test ready, raised and disabled
traps, a one-cell jump, interrupted jumps and real entry conditions. Preserve
intermediate sight, complete lineages and the existing reaction ordering.

Use the shared native layer facts already agreed with the user:

- Entity owns its current occupancy layer; Jump enters AIR and settles GROUND.
  Layer is relative to terrain support: standing on a hill is grounded.
- Commit XY/layer through the existing position publication path. Same-cell
  takeoff and landing publish their real before/after layers without changing
  the XY membership index twice.
- Record relevant facts in the existing root, Step, spatial and actor events.
  Passive player reduction and historical playback use those records; they do
  not query the live entity or infer contact from animation height.
- Floor effects accept GROUND. Existing spatial owners perform layer admission
  before payloads, membership changes and first-per-turn bookkeeping. An effect
  accepting both layers does not exit/re-enter on a layer-only transition.
  Same-cell landing removes an air-only membership and enters ground effects.
- If native interruption stops a Jump after a committed prefix, settle on the
  actual reached cell and publish its ground contact under the complete lineage.
  Pay each committed leg once, before entry conditions alter available movement.
- Existing ordinary movement and relocation preserve recorded state. This unit
  adds no Move-based flight/burrowing state machine, flight controls, hovering,
  falling simulation or wing-dismissal behavior. The neutral layer vocabulary
  and effect predicate are reusable; they do not constitute those features.

The native Jump/Move/MistyStep ground-contact matrix is the regression boundary.
The former extra rows asserting indefinite hover are removed because they encoded
our scope expansion, not the user's requested behavior. Generic layer-admission
cases remain where they exercise the same takeoff/landing and membership contract;
setting up an airborne actor there is not acceptance of a flight action.

Run the focused contact, movement/reaction, projection and saved-replay suites.
Record paired four-camera jump-over/landing and interrupted-jump histories from
real events. Separately flag the already documented late-Step presentation limit:
pre-takeoff reactions can leave a body at launch while the native committed prefix
lands elsewhere. Do not silently change OA rules, snap a body or accept a clip
merely because its mechanical checks pass.

Anti-slop and ECS/anti-OOP reviewers check this narrowed implementation and the
removal of the artificial flight blocker. Resume phases A–F after the jump contact
repair is validated. Future flight work is outside this unit.

### A. Resolve the small content contract

Adopt or amend the proposed qualification, entry cadence, residue persistence,
damage/DC/fear lifetime, and explicit demon variants. Record decisions at the top of
this plan. Finalize the release-result and tile-membership fields and dependency
direction before introducing code. Anti-slop and anti-OOP review the concrete
shape, not speculative future substances.

Deliverable: one agreed content table and passive wire/data shapes. No design
exercise for a generalized physiology, chemistry or particle system.

### B. Implement body response and inert tile residues

Install the shared handler through current humanoid/skeleton/demon composition.
Implement the native release result, one residue condition family, semantic tile
publication and public projection. Wire ordinary blood and bone fragments first.
Add real action-driven tests for repeat hits, resolved zero damage, lethal damage,
persistence and permitted observation. Exercise headless saved-input reduction
before raster rendering. Keep any legacy native reducer tile-owner correction
local to its actual consumers.

Deliverable: the engine and saved player stream fully describe both substances
and their persistent results without any graphics being necessary.

### C. Connect passive presentation and the two skeleton rig routes

Bind release strips and floor traces through the existing recipe/data path.
Connect bloodied spike overlays. Preserve Body 2 equipment; add the selected
fixed Warrior sheets alongside the existing Archer. Exercise melee and ranged
attacks, normal hit response and lethal death hold. Use known gaps in media as
explicit progress notes, not hand-authored fake gameplay frames.

Deliverable: ordinary blood/bone gameplay clips from saved events, plus the
original spike/lever narrative showing residue persistence.

### D. Add harmful residue and authored demon content

Use the residue condition's optional position-indexed entry handler to apply
corrosive damage through normal APIs. Use existing Damage/dice/save primitives;
do not force residue through TrapState or the Poisoned-only TrapConditionPayload.
Add the finite entry payload data needed by these actual profiles. Hazard
application/removal invalidates the existing movement cache, while inert stains
do not. Observe native hazard state through normal sensory deltas and retained
player knowledge. Connect the shared native ground-contact predicate, prove
jump-over versus landing by regression-testing the completed A0 contract, including
interruption. Do not defer its repair to this phase. Add the chosen demon rig
bindings and explicit content variants.

Deliverable: a demon is injured, leaves a real harmful pool, departs/dies, and
another creature walks in/out/back in with correct recorded damage and routing.
Optional sharp bones reuse the same entry-damage path if selected in A.

### E. Add residue-sourced fear

Extend the existing fear-origin representation/resolver only as required for a
tile condition. Author the low-DC dread profile. Test actual successful/failed
saves, paid retreat, fear removal on exit, later escape when initially unaffordable,
visibility and source persistence. Preserve
existing entity-sourced fear behavior. Keep this phase's conditional source logic
out of the renderer and out of per-demon factories.

Deliverable: the dread pool causes a real save and condition; successful saves
never briefly apply it; native movement/turns drive its visible result and expiry.

**Concrete integration finding and reviewed correction:** the prior presentation
compiler bound only root movement; it ignored a paid Move inside an effect and
used a jump's eventual post-retreat position as its arc endpoint. Reuse the
existing movement compiler/sampler as a primitive of the same causal compositor.
Consolidate its existing definitions in `game/choreography.py`, retaining
`game/motion.py` as one-way compatibility exports. One passive timed movement
cue composes the existing path, reaction, media and feedback behavior; there is
no dread-specific animation executor or new timing vocabulary. Actual incoming
Step/landing facts own the arc endpoint; the complete lineage owns final state.
Anti-slop and ECS reviewers approved this bounded dependency correction. Paired
saved-event tests must observe arrival, a walking midpoint and the final retreat
position, and preserve the separate documented interrupted-OA presentation limit.

### F. Integrated encounter, recordings and review

Add a small selectable battlefield/scenario using the existing authoring path:
clothed modular participant, skeletons, selected demon variants, flat ground,
one raised support area and a lever/spike lane. Expose real movement/attacks and
turn progression. The same native histories feed acceptance tests and the review
catalog; no scripted HP, position or condition mutations to manufacture clips.

Record the matrix below, replay it in a fresh process, inspect representative
contact/settled/death frames, and publish the saved gallery with tags and traces.
Report native mechanics, passive playback and art completeness separately.

Once implementation is authorized, work through these phases continuously.
Review checkpoints are internal self-validation, not a request for the user to
supervise each file or every asset. A genuine change to agreed gameplay is the
reason to seek guidance; routine wiring is not.

## 9. Observable acceptance and review clips

Read [HOW_TO_TEST](../HOW_TO_TEST.md). Tests follow actual actions and results,
not class layout, handler counts, string fragments or mocked internal call order.
Use controlled dice through the established harness, actual native damage and
encounter progression. Tests and clips share the same narrative helpers.

| Case | Required observable result |
| --- | --- |
| Humanoid hit twice, then moves | Two recorded releases; one Bloodied tile remains behind |
| Modular Body 2 skeleton hit | Bone release/debris, no inferred human blood; actual gear remains correct |
| Fixed Archer and Warrior | Mapped ranged/melee animation, matching bone response, correct death hold |
| No qualifying injury | No release/residue for resolved zero damage or policy-excluded injury |
| Lethal hit | Release and tile consequence remain in the damage lineage before death; no corpse snap |
| Bloodied spikes | Existing ten-action entry/re-entry/lower/safe-cross/raise-under-occupant narrative retains blood correctly |
| Concealed spikes on marked ground | Seeing the residue does not disclose the hidden mechanism |
| Mixed tile | Blood and bone coexist with spikes; same-profile redeposit does not multiply a hazard |
| Corrosive pool | Native entry damage, no exit damage, re-entry damage, donor can be gone |
| Dread pool failed save | Real save, paid retreat toward entry cell, fear removed on exit |
| Dread pool retreat unavailable | Remains frightened; later movement enables the same escape; no free displacement |
| Dread pool successful save/immunity | No transient applied condition; actual native result explains it |
| Fear source observation/removal | Current source visibility/removal affects penalties as authored; donor visibility does not substitute |
| First sight / reacquisition | Persistent traces appear from observed tile state; old bursts do not replay |
| Hidden donor | Visible tile residue does not identify an unseen creature or disclose private body configuration |
| Still observer and route | Depositing/removing a hazardous residue updates known hazards and legal route preference without moving the observer |
| Forced entry / jump landing / teleport | Ground contact uses native entry semantics and correct cause, with no hits for a merely overflown tile |
| Historical playback | Pause/seek, swap participants and change camera do not rerun mechanics or shift event speed |

Record every selected experiment from both participants' subjective viewpoints,
all four camera corners in one clip per viewpoint. Include same-side/opposing-side
entrants in the native hazard matrix and representative clips. For the completed
donor-gone case, retain the surviving walker's and a live observer's views so both
sides still witness the relevant sequence.

Start with approximately 10–12 purposeful narrative experiments (20–24 paired
clips); cover the larger balance/defense matrix in fast headless tests. Avoid
multiplying every creature, camera, damage type and save outcome into redundant
render jobs. Tags should distinguish body rig, release, residue, hazard, visibility
and narrative so review remains navigable through the existing archive.

The future pixel-difference idea remains documentation only. No new baseline
hashing, runtime source/asset validation or visual testing framework is part of
this unit. Native execution, record/projection/replay and frame drawing timings
are measured separately on the same environment; no arbitrary performance claim
or repeated full-asset scans at startup.

## 10. Likely change locations and dependency direction

These are ownership targets, not a commitment to create a file for every row.

| Owner | Work |
| --- | --- |
| Existing dependency-neutral types | Small passive response/result/residue data as needed |
| `dnd/core/events.py` | Recorded applied-damage release result and semantic tile after-values |
| Existing creature/character composition | Install the shared configured response with normal ownership |
| Native body-response processor | Decide and record release from resolved injury; apply tile residue |
| Native tile-condition implementation | Own residue, optional entry payload and normal cleanup |
| `dnd/conditions.py` and neutral fear-origin data | Bounded non-entity source support for existing Frightened |
| Existing world/sensory/path owners | Consume resulting tile; targeted hazard invalidation and observer updates |
| `game/player_facts.py`, projection/reduction | Passive permitted release and residue state; saved replay |
| `game/choreography.py`, current media/world drawing | One injury-time release binding, passive floor/spike selection |
| `game/data/rigs`, existing Studio/world JSON | Skeleton/demon mappings, burst media and residue bindings |
| Native/game scenario tests and review catalog | Real narratives, paired recordings and saved-input replay |

Imports remain a DAG. Core event/types do not import Entity, content factories or
Pygame. Body/hazard rule code composes existing data and systems; rendering never
calls it. No late imports, circularity workarounds or new entity subclasses.

## 11. Reviews and definition of done

Fresh independent reviews on September 19, requested by the user:

- Anti-slop: `residue_plan_antislop` — scope, necessary abstractions, reuse and tests.
- Correctness: `residue_plan_correctness` — native transitions, causal publication,
  membership, projection, replay and later residue/fear mechanics.
- Anti-OOP/ECS: `residue_plan_anti_oop` — authoritative owners, lifecycle, indexes,
  dependency direction and passive facts.

These reviewers received the written plan and inspected the current code without
participating in the earlier design discussion. Earlier `bloodied_data_review`
and `bloodied_native_review` feedback informed the draft; it is not substituted
for this independent review. No production changes were made during this review.

| Finding | Disposition in the revised plan |
| --- | --- |
| Phase D could defer interrupted landing beyond A0 | Corrected: D reuses/regression-tests the completed contact contract |
| Current-layer hazard bool cannot answer a different proposed route | A0 distinguishes intended-layer native queries from existing ground-route observation facts |
| Membership effects/turn allowance could run before layer admission; XY-only exit misses landing | A0 specifies ordering, old/new membership and all existing occupant trigger paths, with behavioral tests |
| Ground-targeted teleport could accidentally preserve AIR | A0 requires explicit ground arrival; touchdown/capability-loss policies remain identified product decisions |
| Same-name conditions replace after applying mechanics | B/D require distinct authored profile names and deduplication before application |
| Added native fields reject old recordings despite defaults | Existing additive-field boundary handles absent legacy facts without inventing layers |
| Body publication and fear lifetime need precise ownership | Existing unposted handler-result path; actual tile condition membership and current sight |

Final verdict: **all three reviewers approved the revised plan**, with no remaining
material findings in this review. Each independently checked the corrections after
they were incorporated. The later user correction removes flight/touchdown work and its gate from A0;
that expansion is not a prerequisite for the jump repair. Phase A still
selects the proposed injury policy and content balance; no reviewer approval is
treated as human agreement to those values.

The correctness reviewer independently reproduced **15 passed / 6 failed** in the
existing native matrix, with the same six airborne contacts. That run took 94.20s
under concurrent review on the WSL `/mnt/c` checkout; it was not a timing diagnostic
and does not replace the earlier 2.45s measurement or establish a performance cause.
There is no claim of repaired gameplay or newly validated rendering in this review.

The implementation unit is done when agreed profiles work through native turns,
both skeleton body paths and selected demon rigs draw correctly, residues persist
and interact as authored, and saved subjective inputs reproduce the resulting
clips in a fresh process. Report any optional profile/art still deferred explicitly.
Update the recovery checkpoint with the gallery, exact tests and remaining limits.

## 12. A0 implementation checkpoint

The contact layer now has one native owner on Entity. Position/layer commits
publish recorded before/after values through the existing spatial event path;
same-cell changes leave XY membership intact. Jump records takeoff, airborne
crossings and actual settlement. Supported Misty Step arrivals explicitly commit
GROUND. Connector steps retain
their known unchanged layer. The later scope correction removes the added
Move-based flight/hover transitions and the Land-before-walking gate.

Existing spatial handlers now apply authored layer admission before continuous
membership or turn-trigger bookkeeping. Spikes use GROUND for both entry and
lever activation. Moving/appearing fields, periodic effects and same-cell exits
use the same admission owners. Explicit native hazard queries accept a contact layer; ordinary route and sensory
hazard queries keep their existing ground-contact meaning. No traversal mode is
automatically interpreted as a new flight/burrowing state.

Passive actor/movement/spatial facts retain permitted layer state. New tests cover
both observers, hidden teleport endpoints, old archives with unknown layers, and
recorded state. Historical takeoff, teleport release and landing use recorded facts on the existing timeline. Landing
damage uses existing choreography; a root-owned interrupted landing is included.

Real Web spell tests found two additional contact-boundary defects: takeoff could
apply restraint after the budget check, and Jump charged a landing leg after
restraint removed available movement. Jump now rechecks after takeoff;
Jump charges its committed leg before entry effects, matching ordinary movement.
These are reproduced native cases, not hypothetical rollback requirements.

Narrowed validation: **195 integrated tests pass in 47.11s** in the WSL uv
environment with source on `/mnt/c`. This includes 19 jump/walk/Misty Step contact
cases and 11 generic layer-admission cases, plus movement/interruption/forced
movement, traps, teleport, observer projection, saved replay and sorcerer
progression. Real jump interruption, overhead Web restraint and landing cost
remain covered. The seven removed native flight expectations and four removed
flight replay cases belonged to the withdrawn hover expansion; no Jump expectation
was weakened. A separate focused replay run passed 68 tests. The prior 206-test
count is historical and is superseded by this scoped run.

The three existing architecture failures recorded in the recovery plan (retired
server SenseMode import and duplicate EquipmentSlot ownership assertion) remain
outside this change. Focused replay/new-test Pyright is clean; native changed-file
checking still reports existing diagnostics, so no claim of a clean whole-repository
run.

The narrowed [capture gallery](http://127.0.0.1:8767/runs/20260919T011614Z-e12cbf/index.html)
contains two real histories, each from both observers with four camera views:
jump over/onto spikes, and late opportunity-attack paralysis during a jump.
The unused flight-only lever and spell setup is removed. All four
[fresh-process replay clips](http://127.0.0.1:8767/runs/20260919T011700Z-43319b/index.html)
match saved input/video bytes and semantic trace sections directly, without native
execution or hashing. All recorder checks pass across 387 four-camera frames with
no reported binding gaps. The replay process has no native entities, history,
scenario modules or content runtime. Evidence and exported manual verdicts are in
that run's `inspection/replay-verification.json` and `inspection/manual-review.json`.
Old runs and inputs remain intact; the new galleries appear in the main archive.

**Two ordinary jump views are visually accepted for contact behavior. The two
late interrupted-jump views are not visually accepted.** At 2500ms, the native actor
has settled on the trap at (5,3), while the existing aborted-jump presentation
holds its body at launch (3,3), so trap damage looks remote. This follows the
already documented [September 11 jump policy](ANIMATION_COMPOSITION_AUDIT.md#jump-correction--september-11):
all reactions play before visual takeoff, while native reactions still resolve
per Step and can retain a committed prefix. The new clips expose a further
consequence of that policy; passing native/replay checks does not accept it.
Both cards carry `known-reach-presentation` and `needs-review` tags with explicit
manual-review descriptions. No native reaction rule, rollback, midair freeze or
body snap was introduced to conceal the discrepancy.

The narrowed implementation was independently approved for scope by
`residue_plan_antislop`, and reviewed for native ownership and movement scope by
`residue_plan_anti_oop` and `residue_plan_antislop`. `residue_plan_correctness`
implemented and tested passive replay/playback; the root reviews integration and
the clip owner checks the rendered evidence. This distinguishes implementation
testing from the independent plan reviews above.

The user has resolved the scope: **no flight feature in this work**. The earlier
landing question and A0/phase A–F blocker were an assistant-created expansion and
are withdrawn. Keep the jump contact repair and its reusable recorded layer facts.
The paid-retreat dread-blood correction remains phase E work, without a generic
fear lock or one-round default.

## 13. Body/residue implementation and review

September 19 continuation; this section supersedes earlier pending B–F wording.
The selected native/presentation unit and live workshop are connected. Remaining
visual and content limits are explicit below; this is not completion of the wider
recovery plan or every optional residue variation.

### Authoritative mechanics

- `dnd/body_responses.py` owns one configured, target-filtered response per body.
  Positive normal-HP loss with a positive post-affinity physical damage component
  records `DamageAppliedEvent.body_release`. Repeat injuries produce repeat
  occurrences. The processor uses the ordinary handler result path.
- `dnd/residues.py` owns tile conditions: inert blood/bone, entry-only 1d4 corrosive
  acid and Wisdom DC 10 dread. Same-profile deposition retains one membership;
  different profiles coexist. Hazard changes invalidate native movement queries
  and publish the existing local sensory delta. AIR injury does not deposit.
- Authored humanoid/skeleton compositions install the response. Corrosive/Dread
  Demon are explicit Dretch-derived content variants; canonical Dretch is unchanged.
  Sprite identity never selects a body's response or a pool's mechanics.
- Residue fear refers to the actual tile condition. The paid reverse Move uses
  native discovery/costs and clears fear on the correct exit. Unaffordable or
  blocked retreat leaves fear in place; later legal escape remains possible.
  Misty Step selects an adjacent paid step toward departure, as requested.
- Movement owners settle entry effects before carrying out the return. The
  integration covers Move, Jump, Shove, Misty Step, Gust, Thunderwave,
  TelekinesisMove and Eyebite's panicked movement. The return is parented to a
  still-live containing action, not an already-completed Spatial ENTER. Fear's
  application is parented to actual entry, not the completed saving-throw request.
  Complete lineages therefore contain both arrival and the resulting retreat.

### Subjective replay and presentation

Permitted damage facts carry the release; permitted tile after-values carry
residue. Hidden injuries do not disclose their donor. First sight reveals the
current floor trace without replaying an old burst. Own Spatial ENTER retains
its historical position even when a later sensory batch coalesces arrival and
return into one final observer update.

The existing movement compiler/sampler now lives in `game/choreography.py`;
`game/motion.py` keeps one-way compatibility exports. A passive movement cue lets
that same compositor process a native return inside another action. Jump arcs
end at the incoming last Step; the entire lineage still ends at the post-retreat
position. No fear-specific animation interpreter or second playback clock exists.
The redundant post-return observation dwell was removed.

`body-release-assets.json` uses NeuroClient's `neuroclient.actionMediaAssets` v1
records. `body-release-bindings.json` maps four semantic release IDs to existing
Studio media-track data. `game/action_media.py` resolves/samples their selected
one-shot body-strip subset. Timing comes from the injury anchor, and the strip
uses the held historical contact—including a reaction partway through movement,
body lift and support height. The native result contains no artwork/timing fields.
Blood/bone/demonic floors use shared world bindings; known spikes combine their
existing frame with Bloodied tile membership. A transparent overlay frame draws
nothing. Mechanical state never depends on a visible particle or sprite frame.

### Selected content and artwork

The delivery came from the existing sprite task's `body-residue-v2` core manifest.
Selected imports are 16 floor PNGs (four directions for each profile), four release
strips, and the previously delivered 28 bloodied spike overlay frames. Floors are
256px canvases at pivot (128,208). Body strips use 128px cells at 24 fps; blood has
18 frames, the other releases 12, with transparent terminal frames. See
[asset provenance and binding](../game/data/neuroclient/README.md#body-releases-and-selected-workshop-rigs--september-19).

Demon Beast 2 and 3 use existing packaged body/shadow rigs. The skeleton archer
retains fixed Undead `5Archer`. The warrior uses the root modular `NakedBody2` rig
and its real armor scraps, longsword and wooden shield. Fourteen Body2 sheets
and 42 original Legs9/Chest15/Shield7 sheets complete its selected body/gear clips.
`bindings.json.root_creature_content_refs` maps this authored warrior explicitly
to the root rig. No appearance fallback or per-monster drawing code was added.
The optional fixed `6Warrior` art has a baked spear; it was not substituted for
this creature's longsword.

`encounter.residue_workshop` uses the existing battlefield/encounter assembler.
The Pygame composition replaces its controller placeholders through the existing
public API and uses its authored AI policy, deployment, senses and initiative.
Run `uv run --no-sync python -m game --encounter encounter.residue_workshop`.
The default Goblin session remains available without the option.

### Validation and review

All commands use WSL uv with the Linux environment at
`/home/tommaso/.cache/dnd-engine/venv`; source remains on `/mnt/c`.
These are test durations, not startup or rendering benchmarks.

| Evidence | Result |
| --- | --- |
| Native residue/fear/workshop/contact + saved replay, movement, conditions, body actions and placement integration | 193 passed, 2 existing stair-occlusion xfails, 83.28s |
| Expanded body-strip suite, including real nonlethal/lethal OA midpoint contacts | 11 passed, 7.03s; overlaps the integration run |
| Live session and actual Pygame frame-loop suite, including workshop lever plus enemy round | 4 passed, 8.95s |
| Focused type checking of 11 presentation/session/new-test files | 0 errors |

Native tests cover mitigation/zero damage, repeated/mixed deposition, hazard
removal and routing, successful/failed/immunity saves, blocked/paid/later retreat,
layer admission, jump landing and teleport. Saved-player tests cover hidden
actors, first sight, arrival/return positions, one-shot timing, pause/absolute
sampling and retained body placement. Four-camera strip geometry checks use the
same drawing boundary, not copied offset arithmetic.

The first art-integrated gallery has 22 passing clips: 11 native experiments,
each from two subjective viewpoints, with all four camera corners in each video.
Experiments include walk/jump/teleport dread entry, both demon variants, the full
plain/coated spike narrative, mixed blood/bone, repeated corrosive entry, hidden
donor and later first sight. Inputs are saved player-event sequences; rendering
does not execute the engine or the scenario helpers. Runtime evidence records
zero native entities/events and an uninstalled content runtime.

Final [22-clip replay gallery](http://127.0.0.1:8767/runs/20260919T021723Z-83290f/index.html):
all 4,121 four-camera frames reproduce the first integrated art run
`20260919T020936Z-43ab3c`. Direct comparisons find identical saved inputs and video
bytes for all 22 clips, with unchanged semantic trace sections. The comparison
excludes only the existing process-salted initial sensory cache fingerprint;
actual sense modes are compared. It uses no hashes or runtime source audits.
Evidence is in the gallery's `inspection/replay-runtime.json`,
`inspection/replay-verification.json` and `inspection/manual-review.json`.
The latter contains representative frame notes and a real workshop startup image.
The intervening `021327Z-6d7fdc` run retains two loader failures because the running
process read the newly extended rig JSON before loading the corresponding Python
schema; the final fresh-process replay above resolves that mixed-version run.

Independent `release_binding_review` inspected the original NeuroClient media
schema/anchors and the implemented strip binding, then the live workshop
composition and modular gear mapping. No blocking findings. Earlier anti-slop
and ECS reviews cover the native ownership and shared movement composition;
these reviews are distinct from root-run tests and visual inspection.

### Remaining limits and next decisions

- The two late interrupted-jump A0 clips in section 12 still expose the existing
  pre-takeoff-reaction/partial-native-landing mismatch. They remain unaccepted;
  neither this unit's passing clips nor its native tests resolve that policy.
- Ordinary humanoid blood currently selects the small floor asset. Delivered
  medium/pool art is available, but injury-to-amount and accumulation rules remain
  unselected. The amount must become recorded tile state when that content is
  authored, not random display scaling or duplicate hazard handlers.
- Connector/transport entry is not wired to the paid retreat integration above.
  This limit does not affect the tested walk, jump and teleport entry paths.
- Fixed `6Warrior` remains unimported because of its weapon mismatch. Optional
  smoke, poison/sharp bones, connected spreading floors, wall splashes and the
  separate fireball/scorch queue are not part of the selected implementation.
- Artwork is available for human review. Representative impact/floor/hidden-donor
  frames were inspected; this is not a claim that every frame is visually final.
- Existing retired-server/EquipmentSlot architecture failures and two stair
  occlusion xfails remain separately documented. No whole-repository green claim.

Resume the parent gameplay/environment plan after review of this unit. An art
queue entry is not a request to change the active mechanics objective.
