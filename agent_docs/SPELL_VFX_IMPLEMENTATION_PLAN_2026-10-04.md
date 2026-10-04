# Complete the available spell handoffs

Status: human-approved implementation, started October4. Independent
decisions and exact reviewed revision are recorded in the
[review receipt](audits/SPELL_VFX_PLAN_REVIEWS_2026-10-04.md).
The human approved implementation after the reviews and supplied the final
Telekinesis damage profile below. No further balance validation is required.
Baseline: `95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`, October 4, 2026.

## What completion means

Deliver the selected spells through their real native actions, retained events,
subjective projection and existing game presentation. Each spell must obey its
declared rules, including necessary backend repairs. An installed animation is
not a completed spell. Missing mechanics must not be replaced by visual effects,
silently ignored, or left as an unspecified future investigation.

The human accepted **all delivered Godot artwork** after the intake audit. This
includes the Restrained/Petrified and Disintegrate outcome supplements. Earlier
audit statements that those candidates need acceptance are historical and are
superseded here. Acceptance does not fill missing camera banks or validate a
production adapter which has not been implemented.

The [intake ranking](SPELL_VFX_INTEGRATION_RANKING_2026-10-04.md) and its four
linked source audits pin available packages and current code evidence. The
[missing-assets handoff](SPELL_VFX_MISSING_ASSETS_HANDOFF_2026-10-04.md) remains
for the human to forward. There is no communication with the artwork chat.

## Scope and rules

**28 first integrations:** Darkvision, Longstrider, Shillelagh, Barkskin,
Produce Flame, Fire Shield, Blight, Circle of Death, Harm, Eyebite, Finger of
Death, Disintegrate, Power Word Stun, Power Word Kill, Lightning Bolt, Chain
Lightning, Sunbeam, Sunburst, Spirit Guardians, Guardian of Faith, Heroes'
Feast, Wall of Force, Ice Storm, Sleet Storm, Banishment, Dimension Door,
Telekinesis and Antimagic Field.

**Six existing selections to finish:** See Invisibility, True Seeing, Hold
Monster, Continual Flame, Wall of Stone and Wall of Ice. Also finish available
straight Thorns/module Wind composition, shared conditions and existing surface
ignition/quench. Their specifically missing deliveries remain separately open.

The accepted 21 class presentation sets are an explicit final packet, using
existing class mechanics. They are not permission to author new classes,
creatures, attack rules or weapons. Their missing event provenance is backend
work in that packet.

Default mechanical baseline is **SRD 5.1**, using the official
[CC source](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf).
Keep content provenance and fidelity metadata accurate. Do not combine an SRD
damage rule, BG3 duration and an invented trigger without documenting a chosen
adaptation. Call Lightning retains its previously selected BG3 implementation;
this plan does not change it or install its incomplete replacement.

Established exceptions remain:

- Heroes' Feast: the human chose quick cast/eat interaction, all applicable
  benefits, **10 turns of benefit**, not SRD's long preparation/24-hour duration.
- Existing grounded wall forms and ordered points remain as approved in the
  [wall plan](REMAINING_SRD_WALLS_PLAN_2026-10-01.md). No floating panels, full
  spheres, bridges, stacked construction or general multi-Z world expansion.
- Ice stays transparent. Its dome has one **120-HP** pool; destruction breaks
  the whole dome. Flat panels retain their own integrity and local breaches.
- Fly remains ground-to-ground, with no hovering. It is already accepted and
  is a regression dependency, not another integration task.
- Finger of Death is damage-only: the human explicitly removed its zombie
  outcome. No reanimation, permanent control or undead content work belongs here.
- Telekinesis moves creatures to a landing within one action; no maintained
  airborne hold, Stunned or Restrained effect. Allied placement is safe. The
  human requested spell-owned enemy impact damage and a save against Prone.
- Actual ledge falls use the human-selected tabletop damage rule: **1d6
  bludgeoning per full10 feet, capped at20d6**. Add shared landing handling for
  existing movement producers; this does not introduce hovering or stacked maps.
- Retain the game's general spell-component abstraction. This packet does not
  introduce component shopping, ammunition or a monetary reagent subsystem.
  Ordinary slot/action/concentration requirements still apply.

The following adaptations are included in the human-approved plan:
Spirit Guardians retains selectable radiant/necrotic variants rather than
introducing an alignment subsystem; the actual affected/excluded creatures and
timing are native rules. Telekinesis's human-selected enemy-impact balance and
landing policy appear in packet6. Its movement-only adaptation and
Finger's omitted zombie outcome must not be labeled full SRD fidelity. The
previous forced-suspension and zombie-creation proposals are withdrawn.

## Architecture and ownership

Keep one chain:

`native action/condition → committed typed facts → subjective projection →
 existing presentation compiler → shared draw operators + authored data`.

Native code decides targets, damage, state, effect ownership, shape, light,
movement and removal. The client decides sampled appearance and timing of
already-resolved consequences. It never asks the live Entity registry to infer
a result. No new spell executor, parallel timeline, moment resolver, second
world state or per-spell renderer dispatch is allowed.

### Where changes belong

| Responsibility | Existing owner / bounded extension |
| --- | --- |
| Spell rules and granted actions | Existing school modules in `dnd/spells/`; wall rules in `walls.py`, `wall_fields.py`, `wall_constructions.py`. Keep spell-specific conditions there; extract only a demonstrated shared operation. |
| Health and exact damage/HP outcomes | `dnd/blocks/health.py`, public Entity operations and existing `DamageAppliedEvent`/condition state commits. Reuse the existing nonlethal normal-HP damage cap for Harm. |
| Physical movement, occupancy, suppression and light | Existing `dnd/spatial/`, spatial effect system, `dnd/types/spell_suppression.py`, sensory/light owners. A light or obstruction belongs here, never in a shader. |
| Passive facts | `dnd/core/events.py`, `dnd/types/actor.py`, `dnd/core/item_types.py` and appropriate existing passive type modules. Add only data absent from an existing causal fact; do not publish the same state twice. |
| Client observation/reduction | `game/player_facts.py`, `game/player_projection.py` and current reducers; serialize exact source/application/result links. |
| Selection and recipe data | Existing `game/data/*/bindings.json`, content/condition/action recipes and `world_bindings.json`; explicit bundle selection in `game/animation_data.py`. |
| Shared schemas/operators | `game/animation_types.py`, `condition_types.py`, `world_binding_types.py`; `body_effects.py`, `body_presentation.py`, `condition_sampling.py`, `spatial_media_draw.py`, `construction_media.py`. Extend these capabilities, not a `spell_support.py` catch-all. |
| Timing/lifetimes | Existing `choreography.py`, `presentation.py`, `presentation_group.py`, condition/construction lifetime owners. One existing causal schedule. |

Passive native types may be consumed by native systems and client projection.
Native code must not import `game`. Types must not import concrete spell
implementations. Composition chooses content; content does not discover itself
through late imports. No `getattr`, runtime type tricks or global caches of live
entities to cross these boundaries. Ordinary explicit dispatch on a closed
typed variant is preferable to a new framework or an inheritance hierarchy.

### Exact facts needed

Use the existing application/cause/owner identities throughout. Extend their
typed payloads only where the audit found missing meaning:

- Chain Lightning: primary target and each admitted secondary edge, endpoint
  snapshots and linked application IDs. Edges originate at the **primary**;
  the renderer must not calculate another graph from recipient distances.
- Fire Shield: warm/chill through the native energy discriminator. Shillelagh
  and Continual Flame: the actual affected item UUID and effect owner, including
  item transfer/drop/equipment snapshots. Do not infer items from a sprite slot.
- Teleport/absence: committed participants, original/destination positions,
  successful transfer versus mishap, return/disposition reason. Draw portals
  from these facts; never schedule a return from a guessed visual duration.
- Death/destruction: distinguish ordinary death and disintegration. Preserve
  affected object/section and surviving items; no Finger zombie birth event.
- Displacement/landing: native admitted path, support elevations, actual drop,
  controlled placement versus fall, and linked landing consequences. The client
  neither invents damage from its animation arc nor infers height from pixels.
- Persistent effects: exact owner, chosen form/energy, remaining lifetime and
  source-turn expiry where required. Do not put a timeout on the entire
  Concentrating condition and accidentally remove unrelated concentration slots.
- Class packet: actual feature intervention/success and preparation mode where
  missing. A final miss, successful save or 1 HP is not proof of which feature
  caused it.

No event contains PNG names, shader names, asset directories or camera choices.
No new event duplicates a damage, movement, item transition or condition commit
that already carries the necessary identity. A new passive field must have a
named producer, observation policy, replay consumer and test before it is added.

### Concrete native extensions (introduced with their consumers)

These are implementation designs, not a request for a generic replacement ECS.

| Consumer | Data and transaction | Modules |
| --- | --- | --- |
| Chain Lightning | Frozen `EffectPropagationLink` attached to each existing application: source/target typed identity, resolved positions/base heights, application ID. Existing extra-target contracts admit secondary choices once, without convolution creating extra paid casts. | `dnd/spells/evocation.py`, `dnd/core/base_actions.py`, `dnd/actions.py`; passive link in `dnd/core/effect_types.py`; normal facts/projection and directed delivery. |
| Shillelagh | Optional `ConditionState.affected_item_uuid`, explicitly set by the existing actor-owned condition. Resolve only against disclosed equipment/item identity; no second item-owned condition. | `dnd/types/actor.py`, `dnd/spells/transmutation.py`, existing condition snapshot/projection and `game/item_effects.py`/body material sampling. |
| Fire Shield | Explicit snapshot into existing `ConditionState.energy_type`; use existing `whenEnergyType` selector. Retaliation keeps original attack/result causality. | `dnd/spells/evocation.py`, normal condition and damage projection. No duplicate warm/chill enum. |
| Harm / Feast HP changes | Existing modifier UUIDs and committed `resulting_stats`; preserve normal HP when changing maximum unless the rule explicitly grants current HP too. Expose `normal_hit_point_damage_cap` through `Entity.receive_damage`. | `dnd/blocks/health.py`, `dnd/entity.py`, spell condition owners. No second damage computation. |
| Exact source-turn expiry | Source UUID, application turn identity, start/end boundary and exact child UUID; existing handlers advance it. Ice terrain arms on next caster start then expires at that turn end; Sunbeam blindness expires at next caster start. | Existing spell conditions/markers; small shared helper in `dnd/spells/spell_utils.py` only for these concrete consumers, importing passive types, not school modules. |
| Sunlight and darkness cleanup | Sunlight property on existing light data feeds current sunlight-sensitive attack/Perception queries; shared optical-zone removal takes admitted cells and level policy. | `dnd/core/gridmap.py`, current sensory/attack contexts; narrow darkness operation below both school modules, not a school cross-import or separate registry. |
| Banishment | Authored `native_plane_id` and map `plane_id`; one caster-owned ten-interval clock, exact children and typed early/complete removal cause. Explicit return policy reserves nearest free destinations together. | Identity/world leaf types and current builders, `dnd/spells/abjuration.py`, existing prepared return in `dnd/entity.py`. Reuse suspension/presence events. |
| Dimension Door | Optional willing companion and companion landing cell adjacent to caster endpoint. Immutable transfer group retains origins/destinations/heights and arrived/mishap result. Prepare both, commit both, then publish/resolve arrival effects. | `dnd/spells/conjuration.py`, current targeting and spatial commits. Do not fabricate a Portal object/UUID for an incompatible portal event. |
| Disintegrate | Zero-HP aftermath policy on existing damage/death transaction; retained dust disposition and exact surviving items. Larger-object cut is a native 10-foot volume and residual placement bands on the same object. | `dnd/core/effect_types.py`, damage/death events, `dnd/entity.py`, `dnd/blocks/base_item.py`, `dnd/types/world_placement.py`, grid bands and wall sections. |
| Telekinesis | One creature/destination selection per use, completed forced movement, initial/repeat action accounting and spell-owned landing impact. No persistent held victim. | `dnd/spells/transmutation.py`, existing targeting, concentration marker, forced movement and ordinary damage/Prone operations. |
| Ledge descent / landing | Support-height-aware admission and a single recorded landing. Shared actual-fall damage/Prone for Shove, existing push/pull effects and downward movement, with controlled transport distinguished explicitly. | `dnd/core/gridmap.py` and spatial queries; existing movement commits in `dnd/actions.py`; passive movement payloads in `dnd/types/event_facts.py`, `ForcedMovementEvent`/fact and existing causal presentation. Detailed boundaries in packet6. |
| Antimagic | Independent suppressor tokens retain effect identity/clock; suspend/resume contributions without repeating one-time application. Typed protection kind and origin exceptions distinguish field, Globe, artifact/deity. | Existing condition lifecycle, `dnd/types/spell_suppression.py`/`EffectOrigin`, protection registry, `dnd/spells/abjuration.py`, item and presence consumers. |
| Class interventions | Passive feature-intervention payload on existing resolution only if ordinary reaction fact lacks it; closed metamagic/presence mode fields and existing energy type. | Existing class handlers, dependency-leaf actor/effect types and normal projection. No invented action just to play a cue. |

Explicit world limits: Dimension Door selects unseen **loaded-map** coordinates
and supported elevations, not another unloaded map. Telekinesis and falls use
existing support elevations and finite traversals, not persistent suspended
actors, navigable stacked floors or unspecified bottomless pits. Disintegrate
subtracts representable object/section bands, not mesh CSG or terrain excavation.
These are declared game coverage decisions proposed for approval; do not call
them full unbounded SRD spatial capability. Unsupported shapes must be exposed
before selection, not silently destroyed whole.

### Shared presentation changes

1. **Materials and attachments:** add the supplied bark, weapon-glint and
   petrified/cold treatments as bounded typed operators over current body or
   equipment alpha. Preserve source shadows. Palette replacement, controlled
   glow and existing approved shader math are allowed; no multiplied tint,
   painted replacement weapons or new creature sheets. Item effects stay on
   the actual item wherever the rules say they persist.
2. **Directed effects:** use actual launch sockets, recorded endpoints and
   reusable line/ribbon/arc sampling. Supplied browser scenes are reference math
   and data, not a runtime to transplant. Clip a beam to native area geometry;
   moving the origin to a hand must not lengthen or shift the damaging corridor.
3. **Moving areas and objects:** Spirit Guardians uses owner-local orbits and
   supplied components; Guardian/Feast use ordinary world-object presentation.
   Their particles/blades do not run gameplay collision checks.
4. **Dome construction:** extend the existing construction union/consumer for
   the already-native dome, reusing spherical surface projection/occlusion.
   A dome is a hollow shell, not a filled gameplay disk. Preserve independent
   sight, physical passage and subjective surface disclosure.
5. **Loops and retirement:** repeat accepted hold phases while their owner
   exists; retire on the actual removal. Reuse the supplied overlap/fade law.
   Freeze an event pose only when that event specifies it, not a final-state
   visibility mask during movement.

Finite impacts reveal their associated damage/condition/death at contact using
the existing result linkage. Creation precedes formation damage presentation.
Members of one simultaneous application share a contact barrier; distinct
creature-turn damage remains separate. Injury/blood and fallen-to-dead behavior
remain connected to the actual native result, not skipped for fancy spell art.

## Packet 1 — source intake and low-dependency conditions

Pin selected source revisions/hashes before import; copy only selected pages and
transitive dependencies. Do not import whole preview projects. Keep existing
content identities, recorded dimensions, frame rate, original alpha and
direction conventions. Add strict schema admission for new operators and
explicit package selections. Maintain one shared copy of reused condition art.

| Spell / source | Required rules and work | Observable acceptance |
| --- | --- | --- |
| Darkvision; `sensory-fps32-delivery` | Touch, 60-foot darkvision, 8 hours; native sight capability and exact owner removal. Bind head/ground application and sustain without changing normal darkvision restrictions. | Ordinary/magical darkness, prior darkvision, removal, blind target and hidden observer; no extra reveal from VFX. |
| See Invisibility; same | Self, 1 hour; see invisible creatures/objects and Ethereal perception through current sense channels. No wall penetration or automatic attack permission. Finish accepted cues. | Invisible/visible and blocked targets, independent sense owners, expiry. |
| True Seeing; same | Touch, 1 hour, truesight/Ethereal sight 120 feet through existing perception facts. Preserve established game targeting restrictions under blindness. | Illusion/invisibility/darkness within and outside range, observer isolation, removal. |
| Hold Monster; control-binding production handoff | Visible creature within90 feet, undead excluded; WIS save or Paralyzed, concentration1 minute, repeat WIS at each target turn end. Upcast adds one target/slot; chosen targets within30 feet of one another. Retain ordinary paralysis mechanics and source-owned cleanup. | Delivered Ogre/large-body attachment and quiet hold pose, exact shared Paralyzed owner. Large/modular/fixed rig, save/immune/multiple targets, repeat save, concentration loss and another paralysis source remaining. No separate giant-only spell implementation. |
| Longstrider; `nature-utility-batch`, compact-palm-v7 | +10-foot speed for 1 hour, no concentration; one additional target per higher slot. Preserve modifiers and movement-cost ownership. | Multiple targets/upcast, different movement types, expiry with another speed effect active. |
| Power Word Stun; necrotic V2 + Stunned V1 | Visible creature within 60 feet; 150-or-fewer HP gate, no initial save; CON repeat save at each target turn end. No damage. | 150/151 boundary, first/repeated save, independent Stunned owner; no generic hit blood. |
| Power Word Kill; necrotic V2 | Visible creature within 60 feet; 100-or-fewer HP instant-death attempt through existing prevention/life pipeline, no save or invented damage packet. | 100/101, protection prevents death, ordinary death versus prone death, correct corpse/items. |

The packet also selects shared Stunned, Incapacitated, Sickened, Restrained and
Petrified cues and exact aliases for existing Asleep/Frightened/Paralyzed/
Blinded/Deafened. Applying an existing condition remains one common mechanic;
there is no separate condition implementation for each spell. A candidate cold
coating does not create a new gameplay Frozen condition by itself.

## Packet 2 — item/body utility and fire

| Spell | Backend completion | Presentation / required checks |
| --- | --- | --- |
| Shillelagh | Bonus-action cast on the caster's held wooden club/quarterstaff; 1 minute, d8, casting ability option, magical weapon; ends on recast or letting go. Keep modifiers local to that item. | Supplied item treatment on the real weapon; switch hands/loadouts, drop, pickup, expiry and other weapon attack prove no modifier/material leak. It must **not** inherit coating's drop-persistence rule. |
| Barkskin | Touch, concentration up to 1 hour; minimum AC16 rather than +16/additive stacking. | Bark operator over supported current silhouette/equipment; different rig, prone, injury and removal preserve alpha/shadows. |
| Produce Flame | 10-minute held flame, bright10/dim10, action dismissal; initial or later hurl within30 feet uses ranged spell attack and ends held flame. d8 cantrip scaling at5/11/17; no damage to holder/gear. | Hand socket/light follow owner; fire travels before damage; hit/miss, initial versus later throw, cancellation/removal, no fixture +X trajectory. |
| Fire Shield | Warm/chill choice, 10 minutes, no concentration; opposing fire/cold resistance, bright10/dim10; qualifying melee hit by attacker within5 feet causes2d8 chosen energy, not a reaction cost. | Retain actual energy choice; contact on the admitted attacker only. Miss/ranged/distant melee don't retaliate; both variants, existing resistance, two owners and removal. |
| Continual Flame | Touch an actual object, persistent magical light, bright20/dim20, no heat/oxygen use. Replace position-created fake object path with existing item selection and a source-owned light/effect on that object. | Carry/equip/drop/loot/cover/uncover/destroy the real item. Flame/light share owner but optical cover can hide light; never ignite terrain merely because the shader looks fiery. |

Item-owned presentation uses existing item effect snapshots and normal item
events. Do not add a third inventory, special ground-item model or separate
object-attack action. Fixed-sheet equipment may have disclosed visual limits;
do not manufacture modular geometry to conceal them.

## Packet 3 — directed damage and necrotic outcomes

| Spell | Native rule completion | Existing source / acceptance |
| --- | --- | --- |
| Lightning Bolt | 100×5-foot line,8d6 lightning,DEX half,+1d6/slot. Native obstruction/coverage and ignition of eligible unattended flammables; no automatic water-electrification subsystem. | heavy-line-v1: sockets, all relative headings/four cameras, exact endpoint, front/back obstacles, save and multiple victims. |
| Chain Lightning | Visible primary creature/object within150 feet; up to3 distinct secondaries within30 feet of primary,10d8 lightning,DEX half. Higher slots add a secondary each, **not damage dice**. Correct current nearest-any-previous selection; ordinary discovery exposes the choices. | hand-socket-v3: primary contact then parallel admitted branches, no sequential fake bouncing or client graph search. Tests cover object targets, duplicate rejection, primary-range vs secondary-range, slot6–9 and no eligible secondaries. |
| Blight | 30 feet,8d8 necrotic,CON half,+1d8/slot; undead/construct unaffected; plant disadvantage/max damage and ordinary nonmagical plant withering where represented. | native-colored-aim-v4; target fitted material from current alpha, survivor/death/immunity/save and quadruped/large body. No persistent disease invented. |
| Circle of Death | 150-foot cast,60-foot sphere,8d6 necrotic,CON half,+2d6/slot; actual admitted creatures, one resolution. | native-fissure-smoke-v9 components; production-resolution acceptance, area blocked cells and simultaneous recipients. No damaging smoke zone afterward. |
| Harm | 60 feet,14d6 necrotic,CON half; damage cannot reduce normal HP below1. Failed save reduces maximum HP by damage taken for1 hour; magical disease removal ends reduction. No upcast bonus. | native-family-v3. Expose existing damage cap through normal damage call; apply max-HP modifier without double-damaging current HP or healing on expiry. Tests include resistance/immunity/temp HP/low HP/save/disease cleanup and restore. |
| Eyebite | Concentration1 minute; one action including initial cast chooses a visible target within60 feet, WIS save. Successful savers cannot be retargeted by this cast. Asleep wakes on damage/another's action; Panicked uses existing Frightened plus prescribed Dash-away and ends on permitted distance/out-of-sight; Sickened disadvantages attacks/checks and retries at turn end. | Caster-eye owner plus directed strike adapter. Shared condition owns ongoing visual after contact. Initial cast and granted repeat cost exactly once; verify all three modes and concentration cleanup. |
| Finger of Death | 60 feet,7d8+30 necrotic,CON half, **no extra damage on upcast**. Human-selected damage-only adaptation: no zombie outcome. | Accepted normal discharge and Counterspell cameo plus directed adapter. Save/survive/dying/death/prevented-death through ordinary health and corpse/item handling; no delayed birth, control grant or copied equipment. |
| Disintegrate | 60 feet,DEX negates,10d6+40 force,+3d6/slot. A target reduced to0 by this spell disintegrates through the real death outcome. Nonmagical carried/worn gear is destroyed; magical items survive. Nonmagical objects/force creations use their actual size/section rules; larger ones lose a10-foot cube; Wall of Force's own rule removes its full owner. | Accepted projectile plus accepted outcome supplement. Hit/survive/save/protected death/dust/item survivor/partial-object/Force cases; no ordinary intact corpse beneath dust. Add explicit retained affected section data rather than destroying an entire large prop as a shortcut. |

Harm, Finger and Disintegrate share existing health, death and item transitions;
they do not receive private health engines. A disintegration outcome must be
authoritative and saved. Preserve any magical item survivors exactly once.
Finger uses ordinary death and corpse handling without a creation/AI extension.

For Harm, failed-save reduction uses accepted damage (including temporary HP
consumed) and disease/max-HP-reduction tags for ordinary cure/restoration.
Overlapping same-spell reductions do not add: strongest applies, latest wins
ties; still-live weaker contributions remain eligible after the stronger expires.
Preserve each cast's source and duration through existing ownership; no second
condition manager and no removal of all sources by a display name.
Current `BaseBlock.prepare_condition_application` replaces same-name owners,
so it cannot satisfy this as-is. For Harm and Feast, retain separate per-cast
source conditions with stable internal identities/independent clocks and one
public effect child through existing `add_shared_subcondition`/parent links.
Their bounded effect owner selects the strongest/latest live, unsuppressed
contribution and updates its single modifier plus resulting stats. Do not
replay application, healing or removal when the winner changes. Test weaker
expiry, stronger expiry revealing weaker, ties, suppression and exact-source
cleanup. Do not add a generic stacking manager for unrelated conditions.

Disintegrate accepts dust only after the cancellable death transaction succeeds,
preserves magical items even inside consumed nonmagical containers, and prevents
ordinary revival of dust. It does not add unrequested resurrection spells.
Residual placement updates collision, sight and rendering together; tests cover
repeated cuts, remaining obstruction and no duplicated item release.

## Packet 4 — weather and solar

| Spell | Backend completion | Presentation / checks |
| --- | --- | --- |
| Ice Storm | Correct range60→300 feet; radius20/height40 cylinder;2d8 bludgeoning+4d6 cold,DEX half,+1d8 bludgeoning/slot. Difficult terrain expires at **end of caster's next turn**, not a generic round tick. | textured-fracture-v3 independent modules, contact before damage; separate terrain owner. Native area, mixed damage, different initiative positions and caster removal. |
| Sleet Storm | Range150,40-foot radius,20-foot height; concentration1 minute. Heavily obscure, extinguish exposed flames, difficult terrain; DEX/Prone on entry or turn start, concentration save against spell DC on turn start. No damage and no enemy-only safety filter. | soft-ground-contact-v5 back/front/ground; moving observers, repeated entry, allies, overlapping owners, source death and timeout. |
| Sunbeam | Concentration1 minute; initial and action-cost repeat60×5 beams,6d8 radiant,CON half; blindness until caster's next turn on failed save; undead/oozes disadvantaged. Hand emits bright30/dim30 as sunlight. | solar-lifecycle-v1; correct measured socket overshoot without enlarging native corridor. Maintained hand and each shot have separate owners; light/sunlight, repeat, save, expiry and Counterspell. |
| Sunburst | Range150/radius60,12d6 radiant,CON half; undead/oozes disadvantage. Failed-save blindness1 minute with target turn-end CON repeat; dispel darkness created by spells in area. Duration persists independently of caster presence. | ground-coverage-v2 finite expansion, simultaneous recipients, separate Blinded lifetime. Validate darkness cleanup, absent caster, survivor/death and all cameras. |

Reuse source-turn cleanup wiring where it already exists. If duplicate wiring
must be shared for Ice Storm/Sunbeam, the shared type is only an exact owner,
source UUID and start/end-next-turn deadline; it is not a general task scheduler.
Area movement refreshes current disclosure; never reuse a final black mask.
Sleet's first-entry gate must not suppress a separate required turn-start save;
an already-Prone creature still receives applicable saves. Sunbeam's initial
strike retains its parent cast and uses the structured spell/action event;
repeats each retain an independent resolution. Sunburst removes actual spell-
created darkness once at area finalization, including an empty target area. It
does not remove ordinary night, unlit terrain or unrelated fog.

## Packet 5 — holy areas and interactable feast

**Spirit Guardians.** Use the existing caster-anchored15-foot area and halve
affected creatures' speed through its membership modifier.
Concentration lasts100 rounds, base3d8 with+1d8/slot, WIS half. Retain an explicit
cast-time set of visible excluded creatures rather than the current permanent
enemy-only filter; friend/neutral status must not replace that set. Keep
radiant/necrotic selection as the declared game adaptation. Entry and start-turn
rules belong to native trigger admission: forming/moving the aura over someone
does not count as that creature entering under the selected SRD5.1 behavior.
Slow membership still updates immediately. Pin the distinction in tests.

Render accepted relaxed-flow-v5 using owner-local orbits, haze and component
trails. Independent recipient contact follows actual applications; orbiting
spirits do not select victims. Test cast, caster movement, creature entry/start,
exclusions, both variants, repeated entry and owner loss.

**Guardian of Faith.** Keep an ordinary anchored spell object/zone,8-hour
duration, no concentration. Place in an unoccupied visible space within30 feet;
honor its Large occupied space using existing footprint support. Use the shared
10-foot distance query from that space, not a private visual square or different
distance metric. A hostile creature moving within range first time on a turn
makes DEX save for20/10 radiant. Count resolved dealt damage from committed
damage facts, including temporary-HP absorption, not manual before/after normal
HP guesses. Retire when the accumulated damage reaches60. Do not add a new
per-hit damage cap merely to make the total exactly60. Creation/standing nearby
does not fabricate an entry attack. A nonconcentration guardian continues when
its caster disappears; retain attribution/faction facts needed for that.
The current object blocks one anchor and its handler depends on a live caster:
both need correction. Materialize the Large footprint before admission and
retain DC/faction attribution on the owner. Subscribe to qualifying movement
within the area as well as boundary entry; moving inside-to-inside on a later
turn can trigger the guardian. Standing still cannot.

Bind lean-horned-v3 idle/strike/recovery through existing object animation;
strike frame13 is contact. Native admission precedes the visual and cannot be
decided by blade overlap. The final finite strike may finish while the retired
owner has no further gameplay effects. Test resistant/immune/temp-HP victims,
threshold crossing, multiple opponents, occupied placement and source removal.

**Heroes' Feast — explicit October4 human adaptation.** Keep quick creation and
adjacent Eat action. Add disease and poison cleanup, poison-damage immunity,
Poisoned/Frightened immunity, Wisdom-save advantage, and2d10 increased maximum
HP with the same current-HP gain. These last **10 turns**, using the existing
recipient condition clock: `Duration(ROUNDS, 10)`, advanced at native turn start,
not a new turn-end counter or animation timer. Tests pin the first and tenth
post-application ticks. Max-HP expiry clamps current HP only if needed; it
does not apply another damage/heal event. Same-spell overlapping bonuses do not
stack, and removing this owner preserves other immunity/advantage sources.

Use the existing object and item-use route. Preserve a once-per-creature receipt
and finite serving budget (caster plus up to12 other creatures, matching the
source's wording). A duplicate/invalid use cannot reroll or consume a serving.
Proposed quick-game prop lifetime:10 encounter rounds or exhaustion of servings,
owned by an ordinary world-object spatial lifetime rather than caster presence.
This separate prop limit is a proposal, not part of the human's benefit-duration
answer or an SRD claim. Caster absence cannot make the feast/buffs permanent.
Use spectral-material-v2 table/blessing and a reusable existing-rig interaction
pose; no new actor sheet. Test full benefits, heal/max-HP bookkeeping, capacity,
expiry, stacked immunity owners, feast destruction and saved replay.

## Packet 6 — absence, teleport, force manipulation and suppression

These are the most substantial backend packets; finish their native acceptance
before calling their available artwork an end-to-end integration.

**Banishment:** CHA save,60 feet, concentration1 minute, +1 target/slot above4.
An actor native to this plane is suspended/incapacitated and returns on ending.
A nonnative actor returns home; early concentration loss returns it, full minute
does not. Add only authored native-plane/current-plane identity and committed
disposition needed for this decision, not a planar simulator. Preserve items,
concentration/life rules and initiative bookkeeping while absent. Returning
actor takes original or nearest unoccupied valid position; do not displace the
current occupant. Duration advances during absence. departure-echo-return-v1
draws actual absence, echo and return facts; never shows a scheduled return for
a permanently banished actor.
Only the temporary demiplane branch applies Incapacitated; the foreign native-
plane branch must not do so automatically. If no legal return space exists,
retain a pending return obligation for occupancy changes instead of losing the
actor or evicting somebody. Multiple returning actors reserve destinations
together.

**Dimension Door:**500-foot destination need not be visible; optional willing
creature within5 feet, caster's size or smaller, with admitted carried gear.
Expose companion and destination through the existing target-selection route.
Successful participants move atomically; an occupied/invalid destination causes
the actual4d6 force mishap with neither actor moved. Distinguish invalid client
input from a legal cast at an unseen but physically obstructed destination; do
not reveal occupancy or refund every failed teleport as prevalidation. Use
existing support elevations, not guessed flat-floor walkability. simultaneous-v2
portals consume the shared committed transfer and reveal both participants at
one milestone. Test lone/passenger, unwilling/too-large/too-far, unseen space,
occupied space, mishap death, carried items and observer disclosure.

**Telekinesis — completed movement, not maintained suspension.** The earlier
proposal followed [SRD5.1 Telekinesis](https://www.dndbeyond.com/spells/2273-telekinesis):
it can hold a creature aloft and Restrained, not Stunned. The human clarified
movement-only use, then requested that real ledge falls also be planned.
[BG3 Telekinesis](https://bg3.wiki/wiki/Telekinesis) provides a contrasting model:
throw, STR save, concentration-backed repeat use. This is inspiration, not a
claim to reproduce all BG3 object throwing, weight damage or bugs.

Human decisions are movement-only, safe allied placement, enemy spell-owned
impact with a save against Prone, and no Finger zombie. Approved spell profile:

- Keep level5,60-foot caster range, up to30-foot displacement and10-minute
  concentration from this plan. Target and destination remain within caster
  range, using existing support-height distance. No extra upcast damage.
- Select a creature and a visible legal landing before committing one action.
  The initial cast spends its slot/action once and includes movement; each
  repeat spends one action and no slot. Existing action-economy rules decide
  availability. A resisted initial attempt still leaves repeat permission;
  do not reproduce BG3's initial-save/grant quirk.
- Huge-or-smaller enemy: STR save against the originating caster's spell DC
  negates movement and its landing effects. Willing allies need no resistance
  roll. Eligibility/willingness uses existing relationship/target policy,
  retained at resolution, not a client inference.
- Human-selected hostile landing: **4d8 force plus2d6 bludgeoning landing
  damage**, plus actual falling damage when dropped to lower ground; **DEX save
  against the spell DC to avoid Prone**. This is our game adaptation, not an
  SRD/BG3 damage profile. Resisted, canceled or zero-distance
  use causes no damage. Willing allies take no spell damage/forced Prone,
  including controlled descent. Ordinary destination hazards still work.
- Each use finishes on support. Concentration retains repeat permission only;
  its loss/expiry cannot drop an imaginary held victim. Remove the spell's
  Restrain branch and stale free Grab/Move follow-ups. Keep one native action
  transaction per use; preserve shared Restrained for other spells.
- Creature relocation only: no inventory theft, thrown-object collision damage,
  remote lock manipulation or using one body as ammunition in this packet.

**Shared ledge falls — newly requested backend work.** Existing support heights,
Jump/Fly traversals and `ForcedMovementEvent` are foundations, not a working fall
system. Shove currently calls `grid.can_transition`; its shared forced commit
advances ground cells. Forced-movement facts retain only XY endpoints/distance.
No native fall-damage resolver was found.

The human chose the tabletop rule after comparing
[BG3 falling](https://bg3.wiki/wiki/Falling_damage), whose community-documented
height/max-HP formula is described as experimentally derived. Use **1d6
bludgeoning per full10 feet actually fallen, capped at20d6**, then ordinary
Prone if damage was taken. There is no save for this ordinary fall; the save
above belongs to our Telekinesis adaptation. Ordinary defenses, health,
concentration checks and death processing retain their existing owners.
No separate fall HP, copied conditions or physics simulation.

Implementation boundaries:

1. Extend existing spatial admission to distinguish a ground step, an
   unobstructed downward ledge with valid lower support, and a blocked edge.
   Reuse support heights/boundary data; do not mark every ledge walkable to
   permit pushing. Stop at walls/rails/occupied landings; do not invent a
   nearest-free landing sideways. Missing map tiles remain unsupported, not
   secretly lethal chasms. No stacked floors or new terrain art are needed.
2. Extend movement commits in `dnd/actions.py` with one bounded landing
   operation used by Shove, existing push/pull producers and actual downward
   Jump/movement. Telekinesis supplies an admitted finite traversal and landing
   profile. A fall terminates the pushed leg on lower support; subsequent
   motion requires its normal producer. Controlled Fly/teleport arrive safely.
   Reuse collision/trajectory queries conservatively: unsupported obstacle
   clearance is rejected, never justified by a cosmetic arc.
3. Record path, source/landing support elevations, native drop distance and
   landing kind on the existing movement event. Passive records/enums belong
   in `dnd/types/event_facts.py`. Spatial query leaves return data; they do not
   import `Entity`, spells or actions upward. No persistent airborne actor
   state is needed: this is a completed traversal using existing support
   endpoints, not a new global Z model.
4. The landing operation prepares path/occupancy, commits the actual endpoint
   and resolves one linked damage/Prone outcome. Ground entry occurs at actual
   contact, not each XY cell below an airborne leg. Canceled/shortened movement
   retains actual results. Preserve causative actor/parent action through
   damage, death, loot and observer disclosure. Forced travel does not trigger
   opportunity attacks; voluntary approach retains normal checks. Interrupted
   approach cannot execute its canceled landing.
5. Human-selected Telekinesis/ledge combination: the landing applies4d8 force
   and2d6 bludgeoning, plus1d6 per full10 feet of actual lower-ground drop
   (that extra fall component capped at20d6). Replace the earlier larger-of
   proposal. Use the spell's Prone save for that telekinetic landing. Ordinary
   Shove falls use only tabletop damage/Prone. Cosmetic lift is not native drop
   distance and cannot add more fall damage. Distinct destination
   hazards retain their own existing damage/application events.

**Representation and artwork:** grounded-layering-v2 provides accepted hand,
grab/release components in four cameras. Play them during the finite transfer,
without an indefinite hover loop. Extend `ForcedMovementFact` and projection
with admitted movement data; `game/forced_movement.py` and `game/choreography.py`
consume that record through the existing schedule. Departure, travel/descent,
contact and recovery/death are phases of one motion, not spell-specific event
types. Damage/blood/Prone/death appear at contact through actual linked results.
Keep ground shadow, sampled body height and cliff/wall occlusion consistent in
four cameras. Use shared rig capabilities for airborne, injury and fallen/death
poses; never replay a standing death wind-up from Prone.

A dedicated tumble pose or dust burst is **not established as missing**. First
verify current poses/accepted impact media. If insufficient, record the precise
body family/pose or isolated landing cue in the human-forwarded
[art handoff](SPELL_VFX_MISSING_ASSETS_HANDOFF_2026-10-04.md). No new artwork
commission or chat message is authorized here.

Acceptance: initial/repeat/resistance; ally placement; enemy impact and both
Prone save outcomes; flat/10/20/over200-foot drops; rails/walls, occupied landing
and map edge; landing hazards; Shove and one existing spell push sharing fall
handling; safe Fly/teleport; downward Jump; interrupted approach; current/temp
HP, defenses/lethal fall; concentration loss between uses; four cameras/partial
observers/saved replay. Damage never depends on camera or cosmetic arc height.

**Antimagic Field:** concentration1 hour, caster-following10-foot sphere. Existing
source-scoped suppression must cover spells crossing/targeting the field,
active areas, magical item properties, magical transport, magically created
creatures/objects and restoration after leaving. Duration keeps elapsing while
suppressed; overlapping fields keep independent tokens. Expired or removed
effects never return. Suppressing an item leaves its ordinary physical item;
an ordinary arrow fired through is not erased with its magical bonus. Respect
artifact/deity exceptions when declared by content and fields not canceling one
another. Wall of Force is suppressed here; immunity to damage/Dispel Magic is
not immunity to Antimagic. Extend existing effect-origin/suppression
data only for these distinctions; no name checks or kill/recreate surrogate.
Use grounded-layering-v2 field and exact suppression/restoration facts. Test
movement across boundary, partial area, durations, summoned absence/return,
item ownership, teleport rejection and two overlapping fields.

Implement this using **additive provider-UUID tokens on the same retained
condition**, preserving its modifier/handler UUIDs, child links and duration.
`StaticValue`/`ContextualValue` aggregation, `EventQueue` and spatial handler
dispatch gate the contributions owned by that condition. Duration and final
cleanup handlers remain active. Do not reuse an `enabled` player-toggle flag
and later restore a stale saved boolean. Exact-source gates also cover direct
contributions outside those arrays: Shillelagh attack overrides, immunity
sources, granted actions, lights and area providers. Expiry/removal tears down
once; releasing the last suppressor resumes only still-live contributions.
Replace the current `AntimagicSuppression` remove/clear/re-add path; do not keep
it as a second restoration mechanism. This shared lifecycle change requires its
own native review before the Antimagic visual is bound.

## Packet 7 — wall forms, local removal and existing surfaces

**Wall of Force:** preserve native panel/dome dimensions, physical obstruction,
invisibility/sight policy, concentration10 minutes, immunity to all damage and
Dispel Magic, and whole-owner Disintegrate removal. Source ForceV2 includes
panels and dome. Add dome consumption without changing Globe's protection rules.
Push creatures to the declared side on formation where native rules require it;
placement cannot embed them in a solid barrier. Test inside/inside versus shell
crossing, observers, all supported headings, cancellation and owner retirement.

**Wall of Ice:** source static dome plus solid modules and quiet residual air.
Preserve formation damage/save/displacement, local flat-panel AC12/30HP and fire
vulnerability, approved whole-dome120HP, frigid-air CON/cold damage after actual
breach, upcasting and concentration cleanup. Breach footprint is native; a
decorative shard cannot create a hazard tile. Shared dome HP produces one
destruction. Quiet air passes sight. Test inside/outside, two panel breaches,
all-dome break, expiry before breach and removal of remaining child hazards.

**Wall of Stone:** preserve two section sizes/HP, supported connected shapes,
formation displacement and enclosure reaction escape. Concentrating10 minutes
turns remaining stone permanent; early concentration loss removes it. The stone
material is nonmagical from creation; permanence ends the maintained spell's
existence dependency and makes remaining stone non-dispellable. Keep that
material fact separate from ongoing spell-origin/suppression ownership. Use
accepted0.85-second intact retirement (sink/fade/floor clip) for magical removal;
actual destruction uses the destruction bank. Never replay a full intact wall
beneath its break. Neighbor sections keep their own clocks/identities.

**Thorns/Wind available work:** integrate local Thorns contact and Wind
joins/loop/removal against current native paths and recipient facts. Preserve
Thorns opacity/movement cost and Wind's transparent selective passage. Wind's
existing `projectile_deflection_position` is authoritative; do not create a
second interception event. Ring Thorns and missing isolated Wind gust are the
explicit later deliveries below, not silently completed by stretching media.

**Existing surface ignition and quench:** connect `dnd/spatial/ignition.py` and
environmental-condition IGNITE/DOUSE transitions to the accepted growth/hold/
retirement media. Oil→Fire and Web→Burning Web have native owners. Use their
admitted cells, not neighboring-pixel spread. Reuse the two-second hold overlap
law,0.65-second removal and finite2.5-second quench wisp. A quench wisp is not a
maintained SteamCloud or permission to implement electrified water. Existing
Oil/Water art need not be replaced. Test overlapping owners, douse cause,
multi-cell footprint, visibility during movement, and no fake damage from VFX.

## Packet 8 — accepted class presentation (separate acceptance group)

All use `class-action-vfx-proposals/live/HANDOFF.md`, roar-cast-v5. Preserve
existing class mechanics, attack economy and actual equipment/rig recipes.

| Group | Exact sets | Integration requirement |
| --- | --- | --- |
| C1 (4) | Second Wind; Action Surge; Survivor; Dragon Wings | Bind committed healing/action grant and owned wing application/removal. Compatible Bag8 already works; only add accepted finite manifestation. |
| C2 (5) | Rage/End Rage; Frenzy; Reckless/exposed; Mindless Rage cleanse; Intimidating Presence/refresh | Source-owned status and actual cleanse/refresh; reuse Frightened. One combined Rage/Frenzy treatment, no double tint. |
| C3 (2) | Font of Magic slot→points; points→slot | Actual resource transactions and direction; no parsing ranks from action names. |
| C4 (7) | Relentless Rage; Indomitable; Protection; Quickened; Twinned; Distant; Elemental Affinity | Add missing typed intervention/mode/energy facts at existing native resolution. Preparation consumption/removal follows true owner lifecycle. |
| C5 (3) | Equipped Frenzied Strike/Retaliation/extra/critical treatment; Draconic Presence Awe; Draconic Presence Fear | Derive blade path from actual equipped attack animation. Modes and admitted recipients come from native facts. No one-weapon preview path generalized to every loadout. |

No isolated critical, Frenzy or extra-attack animation may consume additional
actions. Test normal/extra/haste/Action Surge/Slow/off-hand/reaction budgets on the
unchanged attack route when binding these consumers. Feature visuals do not
authorize another gameplay rewrite.

## Ordered delivery and review gates

Implement packets1–2 first; then3–5; packet6's native gaps before its integration;
packet7 alongside compatible primitive work; packet8 last as a separate group.
Introduce each common operator with its first two actual consumers where there
are two. Do not build an abstract VFX engine first. Large native subcases can be
implemented/reviewed separately without declaring the whole plan complete.

Every packet closes with:

1. Native public-boundary tests for rules/input→committed result, including
   cancellation and action/slot use. Inspect existing assertions before adding
   behavior tests; follow `HOW_TO_TEST.md`.
2. Serialized native event replay through subjective projection and presentation
   with exact ownership/contact/removal. No fabricated event transcripts.
3. Focused client tests of the shared operator, plus a real recorded spell
   example. Tests use the production selected asset set, not obsolete subsets.
4. Independent anti-slop and anti-OOP/ECS/import-DAG review of that packet and its
   event boundary. Resolve findings before using it as the next packet's base.

Final acceptance requires the complete active native, game and architecture
suites, active typing, and explicit reconciliation of every failure. Paused
server coverage remains separately identified. Do not discard failures as old,
change expected rules to pass a test, or equate a few clips with whole-game proof.

## In-engine visual acceptance matrix

Use the familiar engine gallery, genuine floor tiles with readable boundaries,
saved native input/event lineage, four cameras and independent subjective
observers. Include actual modular and fixed-sheet rigs, current shadows,
injury/blood, prone/death and item ownership. Do not resize actors, reopen
accepted character art or replace scenes with an unrelated HTML effect demo.

For **every one of the34 named spell entries**, record at least a normal action
and the distinguishing variation/lifetime/outcome named in its row. Shared
matrix coverage must additionally include:

- Launch socket and contact frames, front/back and near-camera-perpendicular
  line directions; maximum dimensions and multiple recipients.
- Hit/save/miss/immune/death/prevented-death where applicable; no blood before
  impact and no standing up to die from an already fallen pose.
- Initial cast versus granted repeat, Counterspell/interruption, concentration
  loss, timed expiry, overlapping sources and restoration/suppression.
- Moving caster/recipient, walls/windows, map edge, supported elevation, partial
  observation and hidden observers; no final-state masks during motion.
- Telekinesis ally/enemy placement and shared ledge falls, including actual
  descent before impact, safe Fly arrival and fallen-to-dead continuity.
- Drop/equip/loot/destroy where item effects are involved; no residual duplicate
  floor items or effect transfer to unrelated equipment.
- All admitted wall forms, local destruction versus intact retirement, real
  occupancy and shared HP. Full spheres/unsupported forms are not shown as if
  available.

Clips show useful action plus aftermath with normal presentation timing, not
one-second flashes or artificial slow motion. Long native durations are tested
through legitimate turn advancement; a short visual excerpt must label its
time jump. Freeze final receipts by code/data hashes and retain failed runs.
No fixed small clip count is declared conclusive; the matrix is the acceptance
contract and each cell needs a recorded case or a justified shared test.

## Later artwork dependencies, not reasons to stall this work

| Delivery | What stays open | What can proceed now |
| --- | --- | --- |
| G1 Cone of Cold | Relative-heading/production geometry delivery beyond q0/+X | Existing rules/material audit; no claim of complete general cone presentation. |
| G2 Call Lightning V5 | Full native strike coverage/valid relative-camera adapter | Preserve current selected effect and chosen BG3 backend; no replacement mash-up. |
| G3 Wind block gust | Isolated incoming-direction/contact effect | Native interception and available wall/module/join/lifetime work. |
| G4 Thorns ring | Correct20-foot native geometry contract versus delivered10-foot art | Straight wall and shared local contact work. No silent height change. |

Delivered Restrained/Petrified/Disintegrate supplements are **accepted**, not
additional art requests. Single-view ingredients require concrete camera reuse
validation; request a new bank only if that adapter demonstrably cannot preserve
the accepted appearance. Do not commission unrelated art, creature sheets or
blanket XYZ maps.

## Completion report

Maintain one implementation ledger with per-packet native, event, art and review
status. Final report must separate completed spells/forms, real delivery-blocked
forms and deliberately unsupported rules variants. Link full-suite receipts,
coverage matrix and independent approvals. Until implementation and these checks
finish, this document is a plan, not a claim that the28 spells work already.

### Implementation clarification — Eyebite and shared checks

Preserve the existing generic Frightened movement lock (prior approved rule).
Eyebite's Panicked child explicitly permits retreat and forbids approaching its
visible source; its owning effect uses ordinary Dash/Move with ordinary costs.
A check-only contribution in the existing Ability block supports Sickened raw
ability checks without contaminating saving throws or attack ability modifiers.
No separate condition or movement/action-economy system is introduced.
