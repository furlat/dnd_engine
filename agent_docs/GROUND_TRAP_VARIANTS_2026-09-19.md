# Ground-trap content study

**Planning only.** These are twelve proposed authored trap contents, not twelve
implemented features or twelve new classes. The first useful proof is three
spike variants sharing one physical mechanism and different payload data.
The broader proposals expose which existing engine components are reusable and
which connections still need design. No runtime code or art was changed for
this study; source and existing tests were read, not executed.

The [small trap state plan](TRAP_STATE_PLAN_2026-09-19.md) defines the first unit.
This study follows [RECOVERY_PLAN.md](../RECOVERY_PLAN.md) and the paused
[environment integration unit](ENVIRONMENT_SPRITE_INTEGRATION_2026-09-19.md).

## Shared meaning before variants

The agreed spike mechanism has three mechanical states: **ready** is down and
triggerable; **activated** is up and persists; **deactivated** is down and inert.
These are native facts. Frame counts, interpolation, duration and easing belong
to presentation. The base plan preserves damage on entry into raised spikes;
returning to Ready would be a distinct reset, outside the first slice. Individual
payloads must not invent their own reset clocks from the sprite sequence.

Discovery is separate from those states. An observer can know a ready or inert
trap; a triggered trap does not become known through walls. Retain the existing
subjective disclosure and remembered-world rules. A hidden ready trap contributes
no identifying overlay to an unauthorized view. A discovered disabled trap
remains a known fixture, depicted in its inert pose; absence of a hazard boolean
must not erase its identity. A later unseen state change must not refresh that
observer's memory. Exact passive-perception rules are already native, not
something these variants redefine.

**Study baseline, before implementation:** `SpikeTrap` owned a multi-cell spatial
footprint, revealed the network on entry and dealt **2d4 piercing on each entry**. It had
no physical deployment state and no configurable payload. Its inherited
`deactivate()` retires the spatial condition. The new state/disclosure contract
was therefore implementation work even for plain spikes. The
[backend result](TRAP_STATE_PLAN_2026-09-19.md#backend-result) now implements the
first trio; rows below retain the original gap analysis for the later families.

## Twelve content proposals

All DCs, amounts, durations and footprints below are authored choices to settle
when a variant is selected. They are not asserted to be published D&D trap rules.
The named engine components are verified in this checkout. Their presence does
not mean the proposed trap already composes them.

| # | Proposed identity and trigger/result | What is different, and what is already available | Detection, disabled state and smallest art requirement |
| --- | --- | --- | --- |
| 1 | **Plain retracting spikes.** Entry while ready deploys the mechanism and applies the base piercing payload; retain the activated pose. | Baseline physical contract. Current `SpikeTrap` already supplies the shared footprint, entry handler, revelation and piercing damage, but needs the agreed persistent state contract. | Approved spike family supplies down/up poses and intervening pictures. Down cannot alone distinguish ready from disabled; known state is a separate fact/UI disclosure. |
| 2 | **Poison-damage spikes.** The same entry/deployment applies piercing plus a separately authored poison-damage component. | Same mechanism, different damage payload, not a new trap behavior class. `Damage`, `DamageType.POISON` and normal damage reception already exist; configurable trap damage rows do not. Poison resistance/immunity applies to that component, not automatically to piercing. | Reuse exactly the spike geometry. Optional coating/material detail, once perceptible, is a variant cue; no new motion is needed. Do not reveal a hidden payload just by tinting an otherwise undiscovered trap. |
| 3 | **Sickening spikes.** Same piercing trigger; a Constitution save gates a timed `Poisoned` condition. A successful save never applies that condition. | Adds a save and condition payload to the same mechanism. `Poisoned` already penalizes attacks/checks; save requests and condition durations exist. Author duration and save context; do not assume poison damage or repeat saves. Configurable save/condition trap payload is missing. | Same spike family; may share coating art with #2. Condition feedback comes from the resulting actor condition, not a permanently green actor or a trap-specific shader. Disabling the mechanism does not cure an already poisoned creature. |
| 4 | **Tripwire.** Entry crossing its authored trigger cells requests a Dexterity save; failure applies `Prone`, then leaves a spent/slack mechanism. | Direct movement disruption rather than damage. Saving throws and `Prone` are available. A native tripwire trigger/state binding is missing. Preserve normal Prone behavior, including its existing immediate stand branch; requiring the victim to remain down would be an explicit authored rule. | New taut/slack wire family with two endpoint poses; four views where direction matters. Discovered wire remains visible when slack. No falling or stumble sprite needs to be invented in the backend. |
| 5 | **Clamping snare.** A failed Dexterity save applies piercing and an exact-source `Restrained` membership; a Strength/Athletics escape action releases that source. | Combines damage, movement denial and an actionable escape. `Restrained`, spatial memberships and `EscapeSpatialRestraintAction` exist. A mundane snare membership/content binding is missing; current restraint manifestation defaults are magical and must not be copied blindly. | New open/closed jaw or rope-loop family. A sprung empty snare and a captured actor are separate facts. Disable/release must retire only this snare's restraint, preserving another restraint source. |
| 6 | **Web cartridge plate.** A pressure plate releases an anchored web footprint; affected occupants save or acquire that web's restraint. Later entry/turn-start and Escape Web follow the existing zone. | Reuses the substantive `WebZone` behavior: difficult terrain, exact-source restraint, escape and ignition transition. A trap spawning that zone with an explicit source/content identity is missing. Propose a magical web device initially, preserving the zone's existing meaning. | Reuse a generic plate/cartridge body with ready/spent states; new web ground coverage and occupied/cleared presentation. Disabling the empty cartridge does not automatically remove released webs. |
| 7 | **Grease cartridge plate.** Trigger releases an authored slick footprint; appearance/entry/turn-end saves can knock occupants prone, with difficult terrain. | `GreaseZone` already owns those triggers and first-per-turn admission. This is area-based slipping rather than #4's single trip. Its current Prone application can immediately stand a moving creature; do not silently promise IceSurface's different stay-prone behavior. Trap-to-zone binding and honest magical/mundane content identity are missing. | Same cartridge body; new slick overlay. A spent plate can remain surrounded by an active slick. Recoloring oil is insufficient if it obscures that this payload requests saves. |
| 8 | **Oil-release plate.** Trigger spills `OilSurface`; it increases movement cost and can ignite through existing environmental interactions. | `OilSurface` and oil-to-fire replacement are implemented; oil does **not** currently apply a slip save or `Prone`. This is the flammable-material branch, not a reskinned #7. Only the trap release connection/content remains missing. | Same plate/vent body; oil coverage plus burning replacement. Device disable does not clean the floor. Oil/fire coverage must follow the received footprint, including partial transformations. |
| 9 | **Flame vent.** Trigger releases burning ground; subsequent entry and occupant turn-start take the existing fire damage until extinguished or expired. | `FireSurface` already supplies 2d4 fire, light, three-round default lifetime and dousing. It has no APPEAR damage trigger: a new surface under the triggering occupant does not itself prove an immediate burst. If immediate damage is wanted, author it as an explicit payload, not a renderer effect. | Same vent body; fire surface presentation is separate. Existing torch flame art is not proof of usable area-fire coverage. Ready/disabled can share closed grate geometry; the known state must still distinguish them. |
| 10 | **Frost nozzle.** Trigger creates `IceSurface`; appearance/entry/turn-end Dexterity saves cause slipping, and the ground becomes difficult terrain. | Existing ice explicitly suppresses immediate stand for its slip application and can vaporize into steam. It does not automatically deal cold damage. Shared slippery-ground behavior with #7; distinct material/lifetime/Prone rules, not a wholly new execution path. | Same nozzle/plate body; new ice coverage, optionally sharing a ground-mask family with wet/oil. Disabling the nozzle does not melt ice. |
| 11 | **Electrified puddle plate.** Trigger energizes an authored wet footprint; `ElectrifiedWater` wets occupants and deals its existing lightning damage. | Existing appearance damage, first-per-turn entry/turn-start damage, exact Wet memberships and freeze/vaporize transitions. This combines a material and exposure rather than adding a standalone lightning-spell executor. Trap release/source binding is missing. | Same plate body plus wet/electrified surface states. Electricity-off, dry ground and disabled plate are different observations. No new hero lightning animation is required to establish the mechanics. |
| 12 | **Steam vent.** Trigger releases a short-lived `SteamCloud`, making occupants Wet and heavily obscuring the affected area. | Existing independent cloud, Wet memberships and two-round default lifetime. This changes sight and resistances rather than dealing assumed scalding damage; damage would be a separate authored addition. Trap release binding remains missing. | Same vent body plus cloud coverage. An inert vent can have a lingering cloud; visibility loss/reacquisition must come from native sensory events. This is a useful paired-observer test, not a VFX milestone. |

## What should actually be shared

Start with #1–3. One mechanism owns footprint, physical state, accepted entry
and revelation. Damage components, an optional save and an optional resulting
condition are authored payload choices using existing native operations. This
is a small extension of the actual trap owner; do not introduce a per-variant
subclass hierarchy, effect interpreter, trap manager or parallel event queue.

**Poison damage and Poisoned are distinct.** #2 changes hit points through poison
damage rules. #3 changes attack/check rules through an applied condition. A
failed save, damage immunity and condition immunity can lead to different
outcomes. Use the existing `SavingThrowContext` with the poison effect tag and
exact cause/condition identities where applicable; neither a display name nor
a green sprite is a rule tag. Passing a save means no Poisoned application,
not application followed by removal. Duration/cleansing use the ordinary
condition lifecycle, independently of later trap disable.

The later surface proposals reuse existing condition owners, not fake spell
casts from an invisible caster. Spell-authored zones such as Web/Grease carry
their own identity and magical defaults; using them unchanged is an explicitly
magical payload. A mundane counterpart needs an honest authored adaptation.

There is one concrete composition boundary to resolve when selecting #6–11:
current spikes and many surfaces all occupy the **exclusive transforming ground
layer**. Installing a second such condition on the same cell is not automatically
independent coexistence. A device's retained physical/discovery state and a
released surface's spatial lifetime are different responsibilities. Connect
them through existing ownership/transition contracts when needed; do not solve
this speculative future unit by building a universal trap framework now.

## Small art program, many contents

The approved spike sheet is
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/candidate-v1/spikes-overlay.png`.
It provides seven pictures in each E/N/S/W row, 256-square cells with shared
`[128,208]` ground pivot. That is one reusable spike family for #1–3. Optional
poison coating is a material/content variant, not another animation system.
The neighboring `blender-lever-pixel/lever.png` is the approved control art;
its measured hinge and shared pivot are useful authoring precedent, not a
reason to couple trap rules to Blender frames.

Only three additional device families are suggested: **taut/slack wire**,
**open/closed clamp**, and **common plate/vent/cartridge**. Surface/cloud visuals
are separate reusable coverage families (web, slick/oil, fire, ice/wet/electric,
steam). These were not found or approved by this bounded study. Previously
inspected flame/barrel assets do not establish complete authored ground effects.
Do not generate twelve unrelated sheets before the first shared composition
works. Down/up or empty/full pictures alone never prove a native state model.

## Review and next selection

First validate the base physical state plus the three spike payloads in the
same room: two observers with different knowledge, trigger, retained activated
pose, disable, later passage and saved public replay. The same approved spike
art and shared causal timeline should serve all three. Add a save-success case
and the relevant poison resistance/condition-immunity cases to distinguish real
payload semantics, not to multiply spell-specific demonstrations.

After that, select one contrasting composition such as a snare with an escape
action or oil that later ignites. The remaining rows are an authored-content
backlog, not authorization for twelve immediate implementations.

**Anti-slop review:** root and the native reviewer check that the first trio
actually reuses one mechanism/payload boundary, existing subjectivity survives,
and later zone names are not being advertised as implemented trap features.
**Anti-OOP review:** the timeline reviewer checks that content/art variation
does not add trap-class or presentation-dispatch hierarchies, and that timing
stays in the current data-driven presentation path. Both reviewers approved
this written study and the linked base plan on September 19, with no requested
corrections. Concrete implementation still requires its own review and checks.

## Source evidence

- [Current spike owner and material surfaces](../dnd/spatial/environmental_conditions.py):
  `SpikeTrap`, `materialize_spike_trap_condition`, `FireSurface`, `IceSurface`,
  `OilSurface`, `ElectrifiedWater`, `SteamCloud` and transition tables.
- [Spatial owner and declared triggers](../dnd/spatial/area_conditions.py):
  `SpatialCondition.is_hazard_perceived_by`, `AreaCondition` appearance,
  entry/leave/turn hooks and first-per-turn admission.
- [Conditions](../dnd/conditions.py): `Poisoned`, `Prone` and `Restrained`;
  [saving-throw context](../dnd/core/saving_throw_types.py).
- [Exact restraint and escape ownership](../dnd/spatial/restraints.py) and
  [source memberships](../dnd/spatial/memberships.py).
- [Existing Grease/Web zone implementations](../dnd/spells/conjuration.py).
- Existing behavioral evidence read in
  [spatial condition tests](../tests/engine/test_spatial_conditions.py),
  [spell-family restraint tests](../tests/engine/test_spell_families.py) and
  [spike movement tests](../tests/manual/test_spike_zone_movement_legacy_contract.py).
  No new test results are claimed by this document.
