# Complete fixed-art roster port

Status: full-roster port plan, October 2, revised to the human's explicit scope: all 150 retained characters; no pilot/subset delivery. No new native creature,
artwork or presentation schema is installed by this document. Wall artwork waits
for the complete batch. Windows and accepted spell rendering stay outside this lane.

## Evidence and scope

Item prerequisites are now implemented. Their next content phase follows the
[updated item content plan](ITEM_CONTENT_IMPLEMENTATION_PLAN_2026-10-02.md),
consuming the original bible thread's completed matching work before authoring.
This parent's broader animation/character port remains subsequent work.

Source: `.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/`
(`bible.html`, `data/artist-review.json`, `data/package-validation.json`). The
[renderer handoff](audits/FIXED_CHARACTER_RENDERER_INTEGRATION_2026-10-01.md)
and [animation mapping study](audits/FIXED_CHARACTER_ANIMATION_MAPPINGS_2026-10-01.md)
remain source evidence, not an approved runtime contract.

| Pack | Retained characters |
| --- | ---: |
| Orcs/Goblins | 29 |
| Demons (proposed Devil faction) | 34 |
| Undead | 9 |
| Enemy | 12 |
| HDZ | 21 |
| Top | 27 |
| Barbarian | 9 |
| Character | 9 |

150 characters provide 1,034 selected clips: 600 basic, 422 combat and 12 extra.
All 1,034 have null FPS/pivots and unapproved native bindings/layer policy.
The review includes all eight sheet rows, but broad combat/basic visual inspection
was row 0; Idle frame zero was checked across directions. Thirty-nine directional
sets have stronger byte-verification evidence. Do not claim full directional review.
The rules proposals are 91 loadout changes, 26 adaptations and 33 authored profiles;
15 rows target core SRD coverage and 135 individual special roles. Source names,
flavour names, colored pixels and semantic candidates are not native rules.
The reference illustrations are private review references, never production art.

Seven fixed rigs are currently registered: Goblin01, Orc01, SkeletonArcher05,
GreyWolf and three DemonBeast variants. The wolf is outside this nonanimal bible
but remains a natural-attack regression. They already use the same BodyRig,
BodyClip, timeline sampler and compositor as modular actors.
Scenario redesign is deferred by the human. Existing encounter/recording harnesses
may exercise content, but no new scenario, story, encounter or map redesign is
part of this port.

## Contract to implement first

1. **Disclosed appearance selection.** Extend the existing passive appearance
   data with an optional stable authored visual-variant identity. It is distinct
   from creature content identity and from file paths/rig IDs. Retain it through
   creation, admitted observations, snapshots and replay. Existing content-ref
   rig bindings remain explicit defaults; an unbound explicit variant reports
   a coverage gap and never guesses from name, class or installed files. Validate
   allowed combinations against a public presentation binding, not native species
   mutations. Recipe materialization and encounter authoring must set this data
   before deployment; historical appearance never comes from a live entity.
   Extend both AppearanceConfig and Appearance, plus Entity's explicitly selected
   birth fields; preserve the identity through actor_from_birth, subjective
   observations, projection and cold replay. Use an optional inert visual_identity
   string on EncounterMemberPresentation as the initial scenario insertion point.
   The assembler applies it to provisional appearance data before compose_entity
   commits birth, updating the owned appearance block through its composer.
   Both premade and creature sources already return provisional entities here.
   Include this field in canonical encounter digest/serialization, defining an
   explicit backward-compatible absent-field encoding before migrating catalogs.
   Do not silently regenerate unrelated frozen recipe evidence.
   A creature's default identity remains its authored composition data. No core
   schema imports game bindings, and no post-birth renderer roster override exists.
2. **Resolve semantic body actions once.** Reuse BodyRig/BodyClip and the existing
   action recipe system. Select native attack/cast/action recipe from retained
   facts as today; resolve its body gesture through passive family data before
   compiling its timeline. The result owns actual clip, layer selection, contact
   or release time, recovery and attachment registration. It is a typed data
   result consumed by attack, cast, movement, reactions, death, rest and equipment
   presentation; no family-specific executors or creature renderer hierarchy.
   Resolver precedence is exact visual identity + semantic-action override, then
   explicitly declared family defaults, then a typed unsupported result; ties fail authoring validation. Recipe
   enabled/disabled recovery, delivery, outcomes and equipment policies remain
   authoritative. Family data substitutes body clip/clock, markers, registration
   and layers without re-enabling disabled tracks or replacing projectile rules.
   Contact/release, preparation/FX markers and sockets resolve against their
   actual selected body track once at timeline binding; recovery may have its own
   explicitly selected clip and clock, keeping recipe enablement authoritative; frame sampling performs no resolution. Preserve
   modular last-index settlement: (frames - 1) / effective_fps.
   Modular data must reproduce accepted output exactly before changing fixed rigs.
   Replace cross-family assumptions about Attack1/Attack3 and root contact frames;
   do not merely add vendor filename aliases. Keep source clip names local.
3. **Timing and spatial registration.** Calibrate selected source clips with an
   explicit authored frame rate, loop/hold behavior, support pivot, body attachment
   and contact/release markers. Validate markers against that clip's actual frame
   count and time; six-frame guards cannot inherit a frame-seven contact. Runtime
   haste/slow rates continue applying to the resolved authored clock. Keep native
   action economy, damage, projectile outcomes and rules independent of calibration.
   Extend existing bounded frame types only where inspected clips require it.
4. **Layers and effects.** Author body/shadow/independent-effects/baked-effects
   explicitly in existing rig data. Keep ground shadow registered to support while
   the body rises; preserve true effects omitted by Shadowless exports. Prefer
   vendor separated sheets; derive a missing shadow only from verified paired
   sources, keeping originals. Never apply a second shadow or double opacity.
   Baked trails/emissions do not also receive the modular effect by default;
   existing condition recoloring/attachments and wall occlusion remain shared.
5. **Supported states.** Record genuine gear/hands/shield and state coverage.
   Planned fixed native loadouts must match depicted gear. Runtime disarm, drops,
   shield loss, unarmed attacks and externally imposed states remain legal native
   events: never suppress them to hide missing art. Report missing coverage
   consistently while preserving the received outcome. Use one typed resolution
   result: a supported resolved body program, or an unsupported result carrying
   visual identity, semantic action and a declared reason (unknown identity,
   missing clip, incompatible equipment/state). All consumers preserve received
   outcome/history and expose that same coverage result. An explicit unknown
   identity never falls through to the default content rig. Diagnostic playback
   can advance existing event timelines with body presentation absent and a
   labeled gap; it is not admitted playable visual coverage. The agreed production
   representation for forced gear loss remains a human decision. Do not certify Idle or a
   baked armed body as an accurate unequipped state. Production admission for
   such states needs a separately agreed honest visual policy or matching art.
6. **Private, reproducible imports.** Generate runtime binding data only from
   calibrated selections. Reuse the fixed importer and private production/art
   installer paths in ASSETS.md; preserve source archives/hashes, all admitted
   directions, offsets and clocks. Keep sheets packed; no loose frame explosion,
   preview reference art imports or runtime directory scan. Sheet geometry must
   match declared cell/frame/direction dimensions exactly.

Concrete owners: `dnd/blocks/appearance.py`, creature composition/recipe data,
`dnd/core/events.py`, player projection/reduction, `game/animation_types.py`,
`animation_data.py`, `combat.py`, `attack.py` and shared cast/body consumers.
Extend their typed data; no second gameplay catalog from the artist JSON.
The exact retained-appearance path and existing recipes need a dependency audit
before edits; preserve the domain-to-presentation import DAG.

## Modular and custom sheets: one presentation system

| Concern | Modular family | Custom-sheet family | Shared owner |
| --- | --- | --- | --- |
| Body identity | Authored body/head choices | Authored fixed visual identity | Retained Appearance data and public identity binding |
| Equipment pixels | Separate equipped layers | Already baked into body; optional real alternate-state sheets | Recorded native loadout plus authored visual-state coverage |
| Source layout | Existing root rows/cells | Per-sheet cells, rows and actual frame counts | BodyRig/BodyClip and common media loader |
| Actions | Semantic action resolves existing root gesture | Same semantic action resolves reviewed vendor gesture | Shared passive body-program resolver |
| Clock | Accepted root marker/recovery data | Explicitly calibrated custom marker/recovery data | Existing timeline compiler/sampler |
| Shadow/effects | Authored separate tracks | Separated or verified paired-derived tracks; explicit baked effects | Shared layer composition and support/body transforms |
| Game behavior | Native content/actions | Same native content/actions | Engine ECS systems; no rules in sheets |

A custom actor is not a modular actor with guessed Attack1 aliases. Its family
owns its real clips and presentation markers. Conversely, modular actors are not
an unrelated alternate renderer: the existing modular composition becomes one
explicit visual-family data configuration under the same resolution contract.
Replace demonstrated root/non-root composition assumptions with passive layout,
layer and capability data, preserving the current accepted modular result.

Resolution happens in this order:

1. Received native identity, equipment, action, outcome and state facts.
2. Received visual identity selects the authored family and appearance variant.
3. Existing native-action presentation recipe selects delivery and cue policy.
4. Family data resolves body gesture, exact source clip/layers, markers and sockets.
5. Existing timelines sample those resolved tracks into the common world drawer.

No native creature imports a rig, atlas or rendering recipe. No historical
renderer reads a live creature or changes native actions to suit installed art.
Mechanical size/footprint, visual scale and source-cell dimensions remain distinct.
The future TypeScript client receives the same portable typed records; no Python
class names, callbacks or pack-name branches are part of the public data contract.

## Full-roster work packages and completion gates

Implementation can follow dependencies, but the delivery scope is the entire
roster. A four-character demonstration is not acceptance of this work.

### 1. Reconcile all 150 identities and proposed content

Expand the offline intake into one row for every stable review key. Each row must
record source pack/variant/hash, visible gear and shields, source rules profile,
full selected native kit, deviations, proposed signature, optional alternatives,
and existing/native-to-author target identities. Every proposal is explicitly
selected, awaiting a decision, or deliberately deferred with a reason; no ability
silently disappears and no source trait is silently dropped.

Bind unchanged profiles to canonical SRD content. Loadout/mechanical adaptations
and authored profiles have explicit variant content identities and ordinary ECS
composition, without mutating global canonical definitions. Cosmetic variants
can share native content with different visual identities. Do not create a new
species to select an atlas. Preserve freely equipped modular humanoids/skeletons
alongside the fixed artwork-driven characters. Existing three DemonBeast native
bindings are regressions, not automatic approval of the proposed Devil profiles.

The current source splits are 91 loadout/26 adapted/33 authored; classify every
row into actual reusable items, weapons/natural attacks, spells, traits, action
costs, resources/recharge, defenses, proficiencies and size. Check full source
profile, not just HP/weapon and not an optional prose suggestion. Recalculate
changed combat benchmarks with the source authority before declaring CR final.
Missing native capabilities become an explicit shared-engine implementation list;
reuse common attack, Multiattack, saving throw, concentration, reaction and action
budget systems. Add special abilities only with their approved rule specification.

### 2. Inventory all required body actions and visual states

For each of 150 rows, match the selected native kit to actual source actions and
all eight direction rows. The existing 1,034 selections are evidence, not a limit
on inspection: inspect further available source clips whenever the chosen kit or
state requires them. Unused source actions remain archived with an explicit
unselected disposition; do not import every optional clip simply because it exists.

Coverage includes idle, walk/run, every declared attack/hand/delivery, casts,
recovery, reactions, damage, dying/death, prone/rest, standing recovery, dodge,
condition attachments and equipment states. A running/jumping source attack is
not a default stationary strike; a bow swing is not a shot; colored FX does not
supply damage rules. Hand contact/release and intrinsic displacements are authored
per clip, while world movement remains driven by received native movement facts.

Each selected clip receives authored FPS, loop/hold/settlement, marker windows,
support/body pivot, rest registration, optional sockets, facing map and visual
scale. Record the evidence and calibration status, including row-specific issues.
No assumed FPS or bounding-box footpoint gets certified as vendor metadata.

### 3. Implement the shared contract across both families

Implement the appearance and body-program contract above for modular and all
custom families. Update every body consumer, not only basic attacks: casting,
projectile release, movement, opportunities, reactions, canceled actions,
damage/death, rest/conditions and equipment transitions. Keep native action economy,
Extra Attack/Multiattack, haste/slow, bonuses and reactions unchanged.

Eliminate root-clock and modular-slot leakage into custom timelines. The resolved body program keeps body/contact/release/FX/socket sampling coherent;
recovery can select a different calibrated clip while preserving recipe policy. Explicit
baked effect policy prevents duplicate slash, aura or emission tracks. Existing
condition recoloring, blood/material responses, shadow support, visibility,
actor/wall occlusion and camera composition remain common owners.

Validate authoring deterministically: unknown variants, ambiguous family binding,
unsupported equipment, incomplete directional sheets, invalid markers, missing
required layers and source geometry mismatches produce typed coverage results.
Preserve existing mechanical events and projection even when media is missing;
never silently substitute an armed Idle for an unarmed attack. Full production
acceptance requires a chosen honest presentation for all admitted states.

### 4. Preserve, pack and import the entire approved roster

For each admitted entry, preserve complete originals privately before selecting
production. Reuse the current fixed importer, extend only required typed metadata,
and pack sheets/directions/layers through the existing production installer.
Keep actual lower authored clocks rather than force actor sheets to32FPS. Avoid
loose per-frame files, reference-art imports and runtime scans. Shadowless and
with-shadow pairs are checked individually; use vendor separated layers whenever
available, and do not discard real trails/effects during shadow extraction.

Produce per-entry installed provenance/receipt, retained source paths, selected
clips/frames/layers and byte costs. All150 rows must be accounted for, including
explicit decisions resolving state/rules gaps before marking the full port done.
An audit reports totals by pack, native registrations, unresolved rules, missing
states and production bytes; it is not a second runtime rule registry.

### 5. Gear, abilities and derived conditions must fit the artwork

The human selected dependency order: first the complete item list, existing-item
matching and modular visual candidates; next the selected ability-derived
conditions/effects and their shared presentation; finally the full 150 character
definitions. Scenario redesign stays deferred. The [item inventory and composition
study](GEAR_INVENTORY_AND_COMPOSITION_2026-10-02.md) records catalog integrity gaps
and the proposed bounded gear lane; it does not itself implement or approve new
mechanics. Ability selection supplies condition requirements before character
registration, rather than inventing a free-standing condition catalog.

Artwork is the fixed roster's authoring constraint. Each character's actual
weapon shape/hands/shield, armor/body protection, visible emissions and reviewed
motion select compatible native gear and ability candidates. The original vendor
name or an unchanged source monster loadout cannot override the observed picture.
A missing source weapon/action requires an explicit adapted native kit, not a
renderer trick. Preserve canonical SRD definitions and author clear variants.
Modular characters retain their independently equipped layers and flexible kits.

For every item: exact native identity/type, damage, range/reach, light/heavy or
hand requirements, armor/shield mechanics, visual identity, projectile and baked
attachment state. Reuse identical ordinary items; author genuinely different
items through current content owners. Colored blades do not automatically gain
magic damage; actual chosen magic properties are explicit native data/behavior.
No invisible spare sword, bow or shield is granted merely to fill source actions.

For every selected ability: source native identity or new authored identity,
activation/trigger, action or reaction budget, target/range/shape, attack or save,
damage packets, resource/recharge, duration, concentration, dependencies and
cleanup. Map its actual required cast/strike/emission to observed source clips
and effect layers. Optional bible ideas are proposed choices, not automatically
approved powers. Every row records the chosen signature and disposition of
alternatives; source profile traits and spell lists remain fully accounted for.

For each applied condition/effect: reuse exact existing behavior where equivalent
(Poisoned, Frightened, Restrained, Grappled, Stunned, etc.). Keep poison damage and
Poisoned separate; a tint is not a status. Record source ownership, DC, immunity,
repeat save timing, duration, stacking/reapplication, removal and source expiry.
A new condition is admitted only for selected behavior not represented already,
through existing native registration/events and typed observer facts. Abilities
use shared effect composers, not one bespoke condition per character.

Each derived condition also has public presentation coverage: application,
maintenance, recovery/removal and altered body pose or attachment, with actual
source body geometry and common condition media. Do not couple game mechanics
to pixel colors, bake an always-active aura into rules, or duplicate a source
baked VFX with a generic effect. Unsupported layer/pose states are explicit
full-port decisions. Conditions must behave and replay correctly on both custom
and modular bodies, including when applied by an opponent.

### Normal action coverage for every identity

| Received action/state | Custom-sheet processing under shared systems |
| --- | --- |
| Idle, movement, walking/running | Select family locomotion/idle clip with its own loop/clock; native path controls world translation; shadow remains on support. |
| Melee/ranged/natural attacks, chosen hand, bonus/opportunity/Multiattack | Shared attack recipe plus exact identity gesture, contact/release and projectile/socket; preserve ordinary budgets, damage/outcome and grouping. |
| Casts, channels, maintained effects, counters/cancellation | Shared cast recipe with compatible source pose/effect tracks; respect native interruption phase and expenditure. |
| Dodge/Disengage/Hide, shove/grapple, item use and interactions | Authored actual compatible body gesture or explicit gesture-free presentation for that action; no native rule inferred from roll/guard/taunt filenames. |
| Damage, dying, death, healing | Shared native life/damage facts, exact reviewed reactions/rest clips and synchronized blood/effects; a death clip is not automatically dying/unconscious. |
| Prone/get-up, restraint/stun/fear, other conditions | Shared condition owner and selected family body-state/attachment mapping; validate opponent-imposed states too. |
| Jump/crawl/climb, falling/teleport | Shared existing motion semantics with measured family body/registration; never relabel an unrelated pose as supported traversal. |
| Equip/drop/disarm/shield loss/unarmed | Native loadout stays authoritative; modular layers update directly, custom family requires matching state art or agreed honest missing-state disposition. |
| Turn/end-turn/resource actions without a body gesture | Preserve native progression; retain ordinary body state, using explicitly authored non-body cues where appropriate. |

Native action facts select semantics; per-identity passive data supplies the
body/effect tracks. This covers normal actions as well as signatures. Missing
body coverage does not remove actions from discovery or falsify native outcomes.

### 6. Validate the complete port

For every row, native recipe materialization must match declared kit, traits,
abilities, costs and defenses; appearance must survive birth, observations,
persistence where supported and cold replay. Every registered selected clip/state
must load and sample each admitted direction with valid dimensions/layers/markers.
Shared timing regression covers hit/miss/critical, hand choice, natural attacks,
Multiattack, opportunity, haste/slow, cancelled casts, projectiles and damage/death.

Produce actual event-driven in-game review coverage for the entire roster,
grouped by pack/identity/ability. Include four camera quadrants and paired observers,
visibility loss, conditions, blood, ground shadows and gear/state transitions.
Check native occupancy versus apparent size and source contact/release versus
projectile/target reactions. Do not substitute sprite viewers for gameplay proof.
Show focused pack/character action clips, avoiding one unreadable giant gallery.
Use existing native recording harnesses; scenario redesign remains out of scope.

Run full engine tests after native registration/system changes, relevant
presentation/cold-replay tests, typing and dependency checks. Preserve accepted
modular behavior. Record unrelated failures rather than weakening frozen evidence.
Final acceptance is a complete150-entry character/gear/ability/condition and
animation coverage ledger with installed, event-tested content, not a selected
subset or silently deferred troublesome rows.

## Decisions that need explicit disposition in the full plan

- Every selected native adaptation/signature and optional alternative needs an
  explicit decision. Whole-roster port scope does not turn a speculative prose
  ability into an approved rule. Present proposed profiles grouped by faction so
  the human can review coherent teams rather than150 disconnected stat blocks.
- Forced baked equipment loss, arbitrary gear changes and imposed body states
  need an agreed honest visual policy or matching assets. Native rules remain
  active. Do not replace nonhumanoid bodies with modular humanoids or claim
  baked weapon pixels were removed. The ledger exposes every affected row.
- Source animation clocks and artwork-matched native kits remain authored
  decisions across all rows. Scenario/team/map redesign is explicitly deferred.
  No unresolved entry is silently removed from this full-port scope.

## Required independent reviews

Anti-slop reviewer: validate scope, exact evidence/readiness distinctions,
semantic resolution coverage, missing-state handling, no speculative powers or
silent fallbacks, and complete150-entry character/gear/ability/condition delivery rather than an endless art preview lane or a pilot substitute.
Anti-OOP/ECS reviewer: validate data ownership/import DAG, retained appearance
and action facts, shared systems/compositor, ordinary recipe materialization and
absence of per-pack executors or a parallel native content registry.

The roster owner confirmed this package is current. No vendor FPS/loop/pivot or
release declarations were established. Existing 12 FPS rigs are authored
adaptations, not vendor certification. Representative calibration evidence is Goblin01
Attack1 frames6–9, Goblin03 Attack1 frames10–12, Goblin02 Attack2 flash frame6,
and ZombieMale1 Attack1 frames6–8; these windows still require event calibration.
Goblin03 Attack2 is a melee bow swing and Attack3 has no established release.
Four SkeletonArcher05 body/shadow pairs were exactly recomposed in the earlier
audit; that evidence is specific to those pairs. Source archives are in
`/mnt/c/Users/tommaso/Downloads/`, with private preservation required before import.
An [offline intake](../.runtime/fixed-assets-intake-20261002.json) tracks all150
rows with proposed kits/source profiles/signatures, source constraints and1,034
selected clip evidence records, plus explicit pending implementation requirements. Six bible rows overlap exact source members of
existing fixed rigs; this does not approve their native proposals or timings.

Implementation is not claimed here.

October2 final independent reviews approve this exact scope:
- Anti-slop: all150 characters, artwork-matched gear, selected abilities, derived
  conditions and normal action/animation coverage; scenario redesign deferred.
  Counts and pending intake verified. No additional planning blockers.
- Anti-OOP/ECS: approved shared modular/custom data and systems, native effect
  ownership, retained facts, per-identity resolver precedence, separate recovery
  clocks and typed unsupported-state coverage. No additional planning amendments.

These reviews approve the port design, not speculative native ability choices,
uncalibrated art or unresolved baked-gear state handling as production-ready.
