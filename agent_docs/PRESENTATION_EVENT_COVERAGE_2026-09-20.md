# Presentation event coverage and ownership

Date: 2026-09-20. Branch: `codex/recovery-design`.
Read-only review of runtime; this document is the only file changed by this review.

This is a source-backed inventory for the [graphics cleanup plan](GRAPHICS_CLEANUP_PLAN_2026-09-20.md), not another runtime registry. It covers every current native `EventType` category, every public `PlayerFact` variant, the exact retained-model allowlist, and the current spell-catalog/draft join. It does **not** claim that every registered behavior or every possible lineage has been exercised or visually approved.

The unit of playback remains the complete subjective lineage. A cause, a resolved roll, a child after-value and the parent's contact animation can all describe different parts of the same action. Counting them as four missing independent animations would be wrong. Likewise, `fact=None` can mean a correctly undisclosed event, a causal/log node, or a result carried through an observation/world update. It does not establish a defect.

## Scope and evidence

The counts are different inventories, not numerator/denominator pairs:

| Inventory | Current count | Actual owner |
| --- | ---: | --- |
| Native event categories | 70 | `dnd/core/events.py:155`, `EventType` |
| Exact retained payload classes | 52 | `game/event_record.py:39`, `EVENT_MODELS` |
| Public fact variants | 19 | `game/player_facts.py:305`, discriminated `PlayerFact` union |
| Registered spell catalog entries | 115 | `dnd/content_system/spell_catalog_composition.py:151` |
| Catalog spell identities with a selected spell draft | 14 | Join `declaration.ref.content_id` to loaded `AnimationData.drafts` |
| Additional selected effect draft | 1 | `spell.ice_knife.burst`; this is not a fifteenth catalog spell |

The category/model/fact counts were checked against the current declarations. The spell join used the existing Python metadata imports and `load_animation_data()`; it did not initialize an encounter, run mechanics, decode images, hash files or inspect an external source checkout. The catalog's `delivery` field below is metadata, not proof that a particular renderer path executes it. Chill Touch, for example, still has catalog delivery `single_projectile` while its selected presentation has authored direct contact.

No tests or video recaptures were run during this documentation review. Existing regression and gallery results remain those documented in `RECOVERY_PLAN.md`; a code-supported row below does not silently inherit human approval or exhaustive scenario coverage.

The cleanup baseline is the final composed result from code, data, selected media and post-processing together. The user approved rendered clips, not raw JSON values. These ownership classifications must not turn stored numbers into untouchable requirements: their encoding can change when necessary to preserve approved output. Current captures, user-approved clips and known defects remain separate evidence.

## How to read the matrices

- **Typed retained**: the concrete payload has a current recording contract and is selected by the applicable capture path. This is detached data, not an executable event restored into the live engine.
- **Header**: event identity, type, phase, causal relations, permitted log and grant metadata are retained; the native custom payload is not. A header can correctly carry technical causality.
- **Side fact**: capture deliberately stores the result separately, as with condition after-values or actor admissions.
- **State**: player state, initialization, observation or world after-values own the visible result. No independent animation is required merely because the cause has an enum value.
- **Parent**: a causal action/contact owns the animation or timing. Child after-values remain independently reducible.
- **Own timeline**: a shared binder can produce an animation from the selected recipe and permitted facts.
- **Partial / unsupported**: a concrete implementation boundary is identified. Whether it is required in a selected scenario is a separate question.
- **Unassessed**: the needed behavior or visual expectation was not established. This is never automatically converted into “no visual needed.”

Common source anchors used below:

| Reference | Source |
| --- | --- |
| Capture | `game/presentation.py:570` (`_retained_event`), `:661` (`_condition_fact`), `:782` (complete-lineage capture) |
| Record | `game/event_record.py:39`, `:76`, `:96` (model map, encoding, passive decoding) |
| Projection | `game/player_projection.py:108` (`_project_fact`), `:445` (observations/world reduction and node projection) |
| Reduction | `game/player_reduction.py:26`, `:66`, `:143` (world updates, facts, source ordering) |
| Composition | `game/choreography.py:188` (causal visit), `:509` (child joins), `:549` (compile timed states once) |
| World reduction | `dnd/world_facts.py:111`; `game/presentation.py:345`; permitted update projection at `game/player_projection.py:418` |
| World animation | `game/world_animation.py:64`, `:80`; finite prop transitions and ordinary received state |
| Permitted logs | `game/encounter_play.py:72`; only projected combat-log text reaches this display |

## All 70 native event categories

Every member appears in exactly one row below. Concrete subclasses within a category can differ; the exceptions after the table matter.

| Native categories | Retention / admitted representation | Reduction and presentation owner | Present support / limits |
| --- | --- | --- | --- |
| `BASE_ACTION` | Exact `ActionEvent` is typed; identified source becomes `ActionFact` (projection `:322`). Explicitly selected `ShoveEvent` becomes `ShoveFact` (`:198`). Other custom subclass caveats below. | Own body action when a selected recipe/alias exists; shove has its shared body/contest feedback; actual children own results. | Loaded body-action maps and `bind_body_action` support authored contact, facing, gear scope and recovery. Missing generic action recipe can yield no body cue without a `gaps` entry (`game/body_action.py:48`). It is not automatic approval of a state-only action. |
| `ATTACK` | `AttackEvent` → permitted `AttackFact` (`:159`). | Own attack timeline; child damage/conditions at contact, ranged delivery and equipment selection from retained slot/item identity. | Shared `game/attack.py`, loaded authored attack profiles. Outcome is on the attack fact; no extra HIT/MISS event is needed. Bound cardinality is discussed below. |
| `CAST_SPELL` | `SpellEvent` → permitted `SpellFact` (`:166`), including application identity, effect identity and granted area geometry. | Root cast/body timeline; repeated application children use the root delivery anchors; nested casts keep their own subtree. | Per-behavior recipe required. 14/115 catalog identities have a selected draft; see full identity grouping below. This is not universal spell presentation. |
| `MOVEMENT` | `MovementEvent` and `JumpEvent` typed → `MovementFact`; actual edges are `StepFact` children (`:137`). | Own shared movement timeline; sensory/spatial children own accepted state. | Walk and jump paths exist. Jump prelaunch reactions, one-cycle air-time sampling and interrupted visual positions are working requirements, not missing legacy features. `TraverseConnectorEvent` is a separate root exception below. |
| `STEP_MOVEMENT` | `StepMovementEvent` → granted `StepFact` (`:128`). | Parent movement consumes accepted edges and child reactions. | Not an obligation to animate every step as a separate queued root. Partial visibility uses disclosed edges, not inferred hidden paths. |
| `FORCED_MOVEMENT` | `ForcedMovementEvent` → permitted `ForcedMovementFact` (`:203`). | Own displacement timeline; reached-cell children anchored along it (`choreography.py:295`). | Existing forced-movement primitive; shove parent is represented separately as the source gesture. No flight feature inferred. |
| `SAVING_THROW`, `SKILL_CHECK` | Concrete saving/check subclasses of retained `D20Event`; no dedicated public roll fact. | Causal/log representation; accepted damage or condition children own observable consequences. | Existing technical/log use requires no new body animation. Rich dice UI beyond the permitted log is unassessed. |
| `D20_ROLL_RESULT`, `ATTACK_D20_ROLL_RESULT`, `SAVE_D20_ROLL_RESULT`, `CHECK_D20_ROLL_RESULT`, `DAMAGE_ROLL_RESULT`, `HEAL_ROLL_RESULT` | Exact result classes typed and detached; projection does not expose a separate public numeric-roll fact. | Permitted combat log and lineage; actual attack, HP or condition after-values own rendering. | Correct distinction between evidence/cause and effect. Do not infer a missing hit, save or heal animation from `fact=None` here. |
| `TAKE_DAMAGE` | `TakeDamageEvent` → `DamageFact(stage="taken")` (`:208`). | Parent attack/cast contact, or standalone shared damage binder (`choreography.py:304`). | Damage declaration and committed packet are separate. Standalone damage supports received trap/environment damage without a fake attacking actor. |
| `DAMAGE_APPLIED` | `DamageAppliedEvent` → `DamageFact(stage="applied")` with exact HP/temp HP and disclosed `body_release` (`:210`). | State reduction; parent's hit timing; body-release particles/floor growth from the native release geometry. | Covered result primitive. It must not get a second independent hit animation simply because it has an event type. |
| `HEAL` | `HealEvent` → `HealFact` (`:258`). | Exact accepted HP after-values; generic healing number; parent causal contact when nested. | Partial timing support: compositor explicitly reports nested HP-at-entry timing as unbound (`choreography.py:389`). Current context requests no body clip/media, so those dormant optional fields are not new requirements. |
| `TEMPORARY_HIT_POINTS_CHANGED` | Typed → `TemporaryHitPointsFact` (`:262`). | Exact state update (`player_reduction.py:114`). | No dedicated body cue in current compositor. A new animation expectation is unassessed; absence alone is not a defect. |
| `CONDITION_APPLICATION`, `CONDITION_REMOVAL` | Causal header **plus detached `ConditionFact`**; permitted non-internal actor conditions become `ConditionChangeFact` (`:319`). Tile/item after-values go through world reduction. | Membership/state, condition transition/persistent appearance; often parent-owned timing. | Condition retention is deliberate, not missing serialization. Recipe-specific support varies; populated weapon modifiers/rig layers remain concrete unbound features. INTERNAL membership does not become public graphics. |
| `WEAPON_EQUIP`, `WEAPON_UNEQUIP`, `ARMOR_EQUIP`, `ARMOR_UNEQUIP`, `SHIELD_EQUIP`, `SHIELD_UNEQUIP` | Exact equipment subclasses → `EquipmentFact` (`:277`). | Visible loadout/AC; own equipment gesture only when visible layers/stance change. | `game/combat.py:191` explicitly makes unchanged visual loadouts gesture-free. Observer-private inventory is not disclosed to other actors. |
| `ITEM_LOCATION_STATE` | Exact typed location state; owner equipment/inventory → `EquipmentFact`; floor changes → permitted world updates. | Equipment state or floor-object state; interaction parent may supply the action gesture. | State-owned support. Taking/dropping an item is not required to create two gestures for one accepted interaction. |
| `ITEM_CHARGE_CONSUMPTION` | Typed; `ItemChargeFact` only for the controlled actor (`:273`); recorded floor-object after-state can also update the world. | Charge/stack/destruction state; causal item-use body action owns drinking/contact. | State-only charge decrement is correct. User-accepted omission of potion/source strips does not remove the existing drink/effect timing. |
| `WORLD_INITIALIZED` | Typed initialization record; `begin_projection` requires it (`:516`). | `PlayerInitialization`, permitted tiles/objects/connectors and observations. | Event-driven initial world is implemented. No separate initialization animation is required. |
| `WORLD_MODIFIED` | Typed world edit; observed tile/object after-values become `WorldUpdate`, not a direct player fact. | Ordinary world state and supported prop transitions. | Tile/object path exists. Dynamic connector after-state is a concrete projection limitation below; do not call all world edits fully covered. |
| `ENTITY_CREATED` | Typed in initialization capture; later lineage admission uses captured `ActorAdmission` values, while the creation node can be a header. | Permitted `PlayerObservation` builds/reacquires the actor; no objective actor query in playback. | Appearance/identity is observation-owned. This matrix makes no claim about a distinct authored summon/spawn animation. |
| `ENTITY_LEVEL_ADDED`, `ENTITY_LEVEL_REMOVED` | Concrete native level fact exists, but these payload classes are outside retained map and become headers. | No corresponding public level/stat reduction branch. | Payload/projection not implemented for these events. A level-up visual or live progression use case is unassessed; this is not a demand to add one during graphics cleanup. |
| `TRIGGER_EVENT` | Known `CounterspellReactionEvent` custom action root becomes header. | Child causes/outcomes can remain; no dedicated retained counterspell action binding. | Concrete custom-root limitation. Existing imported Counterspell recipe is not selected by current action loader. See below; no invented rollback semantics. |
| `SPATIAL_ENTITY_ENTERED`, `SPATIAL_ENTITY_LEFT`, `SPATIAL_PERCEIVABILITY_CHANGED`, `MOVEMENT_COLLISION` | Typed `SpatialChangeEvent`; granted position/identity → `SpatialFact` (`:284`). | Occupancy/contact state, sensory deltas and parent movement timing. | Collision or visibility cause does not need a second movement animation. Correctly undisclosed geometry remains absent. |
| `SPATIAL_TILE_CHANGED` | Typed `SpatialChangeEvent` and `TileElevationChangeEvent`; no direct player fact for tile changes. | Recorded tile after-values → visible `WorldUpdate`; ground/height rendering consumes state. | State path exists (`world_facts.py:183`, `:191`). Separate terrain morph animation is unassessed. |
| `SPATIAL_OBJECT_PLACED`, `SPATIAL_OBJECT_REMOVED`, `SPATIAL_OBJECT_CHANGED` | Typed spatial payload; observed object after-values → `WorldUpdate`. | World object state; shared open/engaged transitions and parent interaction contact. | Finite registered prop animations are selected by identity/state, not an obligatory placement animation. |
| `SPATIAL_LIGHT_CHANGED` | Typed spatial payload and own `SensoryUpdateEvent`; no independent light player fact. | Retained tile light and permitted sensory/light deltas. | State-owned illumination/visibility. An extra flash or switching animation is only required by its actual action/prop recipe. |
| `TRAVERSAL_CONNECTOR_CHANGED` | Concrete declaration payload becomes header; authored world-edit wrapper can also carry typed connector after-state. | Initial visible connectors exist; dynamic connector projection is incomplete. | See precise connector limitation below. Missing custom payload and missing rendering are not assumed equivalent. |
| `SENSORY_UPDATE` | Typed; only this observer's delta → `SensoryFact` (`:126`). | Exact sensory reduction, admissions, reveal/occlusion and world updates. | Core shared state path. Foreign sensory data is deliberately excluded. No independently invented “spot actor” cue is required. |
| `SPATIAL_EFFECT_CHANGED` | Typed `SpatialEffectChangeEvent`; observed trap transition → `SpatialEffectStateFact` (`:115`). General perceived spatial effects arrive through `SensoryFact`. | Trap transition plus persistent received sensory/world state. | Trap transition geometry restricted to granted visible cells. Non-trap effects lacking this particular fact are not thereby absent from state. Their recipe-specific visuals require separate content assessment. |
| `SPATIAL_EFFECT_INTERACTION` | Native interaction payload currently becomes header. | Subsequent native condition/damage/spatial/sensory result children retain their normal owners. | Specific interaction payload/own visual not implemented. Whether an additional independent effect is required is unassessed; not a blanket claim that environmental outcomes disappear. |
| `FIRE_EXPOSURE`, `EXPOSED_FLAME_IGNITED`, `WIND_EXPOSURE` | Native exposure/flame payload classes currently become headers. | Committed child/world/sensory results use their own paths. | Dedicated exposure presentation unassessed. Exposure is not itself proof of accepted ignition, damage, displacement or a required particle effect. |
| `ENCOUNTER_START`, `ENCOUNTER_END`, `ROUND_START`, `ROUND_END`, `TURN_START`, `TURN_END` | Exact subclasses typed → `TurnFact` (`:312`). | Round/current actor state and game UI; permitted logs. | Technical/game-state representation. Not six missing independent animations. |
| `LIFE_STATE_CHANGE` | Typed → `LifeFact` (`:266`). | Exact life/HP state; parent-owned lethal result or standalone lifecycle/death presentation (`choreography.py:398`). | Shared lifecycle support; causal owner prevents duplicate death animation. |
| `DEATH_SAVE` | Typed → `DeathSaveFact` (`:270`). | Authored success/failure/critical feedback; life change remains its own result. | Supported lifecycle feedback, not inferred death from the roll alone. |
| `REVIVE`, `INSTANT_DEATH`, `DEATH` | Typed cause payloads; no separate public cause fact. | Actual `LifeStateChangeEvent` and accepted condition/HP results own the change. | Existing child ownership is correct. Do not animate a cause and its committed result twice. Native references: `dnd/entity.py:1980`, `:2064`, `:2256`, `:3165`. |
| `ABILITY_CHECK`, `INFLICT_DAMAGE`, `ATTACK_MISS`, `ATTACK_HIT`, `ATTACK_CRITICAL`, `DICE_ROLL`, `ENEMY_SPOTTED`, `ENEMY_KILLED`, `ENEMY_ENGAGED` | Enum categories exist. This review found no concrete producer using these categories outside their declaration in the inspected native source. Generic headers can preserve a category. | Not independently assessed. Actual attack outcomes, resolved rolls, sensory admissions and life results use the concrete families above. | **Unassessed labels, not nine proved rendering bugs.** Do not manufacture parallel event types or visual implementations to make the enum look covered. |

### Exact retained payload catalogue

For clarity, these are the **52 exact classes** in `EVENT_MODELS`, grouped without adding classes inferred from inheritance:

- Base/action: `Event`, `ActionEvent`, `AttackEvent`, `SpellEvent`, `MovementEvent`, `JumpEvent`, `ShoveEvent`.
- Initialization/world: `WorldInitializedEvent`, `WorldModifiedEvent`, `EntityCreatedEvent`, `SensoryUpdateEvent`, `SpatialChangeEvent`, `TileElevationChangeEvent`, `SpatialEffectChangeEvent`, `StepMovementEvent`, `ForcedMovementEvent`.
- Equipment/items: `EquipmentEvent`, `WeaponEquipEvent`, `WeaponUnequipEvent`, `ArmorEquipEvent`, `ArmorUnequipEvent`, `ShieldEquipEvent`, `ShieldUnequipEvent`, `ItemLocationStateEvent`, `ItemChargeConsumptionEvent`.
- Rolls: `D20Event`, `SavingThrowEvent`, `SkillCheckEvent`, `D20RollResultEvent`, `AttackD20RollResultEvent`, `SavingThrowD20RollResultEvent`, `SkillCheckD20RollResultEvent`, `DamageRollResultEvent`, `HealRollResultEvent`.
- Damage/life: `TakeDamageEvent`, `DamageAppliedEvent`, `HealEvent`, `TemporaryHitPointsChangedEvent`, `DeathEvent`, `DeathSaveEvent`, `InstantDeathEvent`, `ReviveEvent`, `LifeStateChangeEvent`.
- Encounter: `EncounterEvent`, `EncounterStartEvent`, `EncounterEndEvent`, `RoundEvent`, `RoundStartEvent`, `RoundEndEvent`, `TurnEvent`, `TurnStartEvent`, `TurnEndEvent`.

Condition payloads deliberately use their side-fact contract. Actor creation/admission has separate initialization and lineage paths (`presentation.py:203`, `:283`, `:680`). A raw native class being absent from this exact-class map is only a reason to inspect capture, not immediate proof that its needed result is lost.

## All 19 public fact variants

All these facts are passive serializable data. Projection admission still depends on the observer; “has a branch” does not mean every observer receives it.

| Fact kind | Direct player reduction | Animation/state owner |
| --- | --- | --- |
| `attack` | Active weapon set from actual retained slot (`player_reduction.py:99`). | Attack binder, authored weapon/damage profile; child outcomes at contact. |
| `spell` | No independent state mutation. | Cast/body binder, application delivery, nested effect recipe. Actual child facts change state. |
| `movement` | No speculative position mutation. | Walk/jump compositor; actual spatial/sensory children own state. |
| `step` | No independent state mutation. | Parent motion edge, accepted continuation/reaction timing. |
| `forced_movement` | No speculative position mutation. | Forced displacement with reached-cell child effects. |
| `shove` | No speculative HP/position/prone mutation. | Shove body/feedback; actual forced movement/condition children. |
| `damage` | Applied stage commits exact HP/temp HP; taken stage does not. | Parent hit or standalone damage, plus disclosed material release. |
| `heal` | Exact HP/temp HP when accepted. | Healing feedback; nested HP timing remains explicitly partial. |
| `temporary_hit_points` | Exact temp HP. | State; independent visual expectation unassessed. |
| `life` | Exact life state/HP. | Parent lethal result or shared lifecycle/death cue. |
| `death_save` | No speculative life mutation. | Authored outcome feedback; accepted child life transition. |
| `equipment` | Visible loadout, AC, owner-only inventory. | Equipment gesture when appearance changes; otherwise state. |
| `condition` | Membership/max HP/AC after-values. | Shared transition and persistent appearance; selected recipe may be partial. |
| `spatial` | Occupancy layer and own accepted entry position. | State and movement/displacement/contact timing. |
| `turn` | Round and current actor. | Game UI/log; technical representation. |
| `action` | No independent outcome mutation. | Selected body recipe/alias and actual children. Absence of a body recipe is not currently always reported. |
| `sensory` | Own exact sensory delta and last visual positions. | Visibility/contact/light/world-state presentation at causal time. |
| `item_charge` | Controlled inventory charges, stacks, removal and visual-item removal. | State at parent effect; does not infer a separate consuming animation. |
| `spatial_effect_state` | No second persistent trap-state reducer; sensory state owns retained effect state. | Finite observed trap transition (`choreography.py:216`). |

Initialization, `PlayerObservation` and `WorldUpdate` are additional received records, not missing variants in this union (`player_facts.py:68`, `player_reduction.py:26`, `:34`, `:166`). Complete lineage nodes remain when their permitted fact is empty; entirely undisclosed lineages may be omitted (`player_projection.py:497`, `:542`).

## Concrete limits worth keeping visible

These are source-supported implementation boundaries. They are not authorization to broaden the cleanup into all native mechanics or to generate new effects for every cause.

### Custom action roots lose their specialized payload at capture

`presentation.py:615` retains **exact** `ActionEvent`; unknown subclasses fall through to a header. Known examples:

- `TraverseConnectorEvent`, `dnd/actions.py:1030`, uses `MOVEMENT` but is not `MovementEvent`/`JumpEvent`. It does not reach their root geometry binder through its category alone.
- `DragonbornBreathWeaponEvent`, `dnd/origins/dragonborn.py:36`, inherits `BASE_ACTION`. Its root behavior/geometry is not projected as an `ActionFact`, even though an authored action record exists (`game/data/neuroclient/source/src/render/data/animation/contentActionPresentationRecipes.json:2890`). Children still retain their independently supported outcomes.
- `CounterspellReactionEvent`, `dnd/spells/abjuration.py:89`, uses `TRIGGER_EVENT` and carries triggering-event/lineage identity. Its special root facts are not retained. The imported Counterspell recipe (`contentActionPresentationRecipes.json:3744`, cue kind `counterspell`) is also outside the loader's selected `attack`/`shove`/`action`/`item_action` families (`animation_data.py:260`).

These are concrete “not yet bound as this root” entries, rather than an allegation that the native action failed. A future chosen root needs its retained/public data contract assessed before adding a body animation. Do not expose objective trigger metadata merely to make a visual possible.

### Dynamic connector state is not the same as initial connector support

`TraversalConnectorChangeEvent` (`dnd/core/events.py:4238`) is not retained as a typed payload. Native authoring can already wrap it in `WorldModifiedEvent` with a connector after-value (`dnd/world_authoring.py:397`, `:416`), and `dnd/world_facts.py:145` knows how to reduce that value. Therefore enum/class absence alone is insufficient analysis.

The actual presentation boundary still has a limitation: `game/presentation.py:347` creates temporary `WorldFacts` from world/tiles/objects and returns only those three fields. Its updated connector map is not retained there. `_world_update` reads `world.world.connectors` from initialization (`player_projection.py:430`). Thus this path does not propagate dynamic connector edits into the public connector list. Initial known connectors remain supported. No failing recorded scenario was run here; a chosen dynamic-connector feature needs a real after-value/replay example, not a generic terrain animation project.

### Level facts have no retained/projected update contract

`EntityLevelAddedEvent` and `EntityLevelRemovedEvent` (`dnd/core/events.py:1056`, `:1066`) have native producers (`dnd/content/characters/progression.py:224`, `:253`). They are absent from the exact recording map and from actor fact reduction (`dnd/actor_projection.py:36`, `:56`). This is a payload/state coverage limit, independent of whether a level-up animation is desired. Live progression presentation remains unassessed in the current encounter scope.

### Loaded records are not proof that all authored tracks execute

- Condition alpha/body color and composition operate, but persistent strip, equipment-modifier and rig-layer tracks are explicitly reported unsupported (`game/condition_animation.py:88`). Selected populated weapon modifiers and the Dragon Wings appearance layer therefore remain partial. Missing condition recipe is also reported (`:64`).
- Generic healing feedback operates; nested healing explicitly reports HP-at-entry timing unbound (`choreography.py:389`). Current healing body/media values are `none`/empty, so they do not create a requested missing feature.
- Attack/cast/standalone damage bindings currently accept a limited packet/lifecycle shape (`game/attack.py:284`, `game/combat.py:153`, `game/damage.py:49`). This is a declared capability limit, not a claim that a demonstrated weapon currently violates it. Selected real lineages establish whether it matters.
- `bind_body_action` returns `None` when no selected body recipe exists (`game/body_action.py:48`); the generic-action path does not automatically append an unsupported entry. Conversely, spell binding explicitly rejects an unknown draft (`game/animation.py:773`) and choreography reports binding failure (`game/choreography.py:262`). Therefore `BoundChoreography.gaps == ()` cannot by itself certify completeness.
- Current world animation interpolates `is_open`, `is_engaged` and observed `trap_state`; other received world properties still draw as state (`game/world_animation.py:49`, `:80`). State changes are not intrinsically missing transitions.

Potion/source strips are an **accepted omission**, not a cleanup task. Empty optional movement media/recovery are **inactive legacy data**, not unfinished walk/jump behavior. Do not put them back into the plan by classifying every unused field as a defect.

## Registered spell identities versus selected cast drafts

Each identity below is `spell.` plus the listed suffix. Membership is explicit and exhaustive for the **115 current catalog rows**. Grouping uses the existing catalog's `metadata.delivery`, not a newly inferred delivery system.

### Draft selected: 14 catalog rows

| Catalog delivery | Count | Identities |
| --- | ---: | --- |
| `aoe_projectile` | 2 | `fireball`, `ice_knife` |
| `missile_volley` | 3 | `acid_splash`, `eldritch_blast`, `magic_missile` |
| `ray` | 1 | `ray_of_frost` |
| `self` | 2 | `misty_step`, `see_invisibility` |
| `single_projectile` | 3 | `chill_touch`, `fire_bolt`, `guiding_bolt` |
| `touch` | 3 | `greater_invisibility`, `invisibility`, `true_seeing` |

`spell.ice_knife.burst` is the additional selected child-effect key. Selected draft means an authored record resolves, not that every optional field executes or every combination has been reviewed.

### No selected cast draft: 101 catalog rows

| Catalog delivery | Count | Identities |
| --- | ---: | --- |
| `aoe` | 26 | `antimagic_field`, `burning_hands`, `color_spray`, `cone_of_cold`, `darkness`, `daylight`, `fear`, `fog_cloud`, `globe_of_invulnerability`, `grease`, `guardian_of_faith`, `gust_of_wind`, `incendiary_cloud`, `lightning_bolt`, `mass_cure_wounds`, `prismatic_spray`, `silence`, `sleep`, `sleet_storm`, `slow`, `spike_growth`, `spirit_guardians`, `stinking_cloud`, `sunburst`, `thunderwave`, `web` |
| `aoe_projectile` | 7 | `circle_of_death`, `cloudkill`, `flame_strike`, `hypnotic_pattern`, `ice_storm`, `insect_plague`, `shatter` |
| `beam` | 1 | `sunbeam` |
| `none` | 29 | `aegis_spark`, `aid`, `bane`, `banishment`, `beacon_of_hope`, `bless`, `blindness_deafness`, `charm_person`, `command`, `counterspell`, `dimension_door`, `divine_word`, `enlarge_reduce`, `haste`, `heal`, `healing_word`, `hellish_rebuke`, `heroes_feast`, `hold_monster`, `hold_person`, `mass_heal`, `mass_healing_word`, `necrotic_bless`, `power_word_kill`, `power_word_stun`, `prayer_of_healing`, `sanctuary`, `shield_of_faith`, `thaumaturgy` |
| `ray` | 6 | `blight`, `disintegrate`, `eyebite`, `finger_of_death`, `scorching_ray`, `telekinesis` |
| `self` | 5 | `blur`, `expeditious_retreat`, `false_life`, `mirror_image`, `shield` |
| `single_projectile` | 4 | `call_lightning`, `chain_lightning`, `poison_spray`, `sacred_flame` |
| `touch` | 23 | `bestow_curse`, `continual_flame`, `cure_wounds`, `darkvision`, `death_ward`, `enhance_ability`, `freedom_of_movement`, `greater_restoration`, `guidance`, `harm`, `inflict_wounds`, `jump`, `lesser_restoration`, `light`, `mage_armor`, `protection_from_energy`, `protection_from_poison`, `regenerate`, `remove_curse`, `resistance`, `shocking_grasp`, `stoneskin`, `true_strike` |

This is a binding inventory, **not “101 spells have no graphics.”** A Haste condition and movement under Haste can be represented while the Haste casting gesture has no selected draft. A reaction's actual runtime root may need a different contract from `SpellEvent`. A cloud's native condition/sensory state can reach the player while its cast and persistent artwork still need individual assessment. Do not label these effects completely supported or completely absent using only this join.

## Lean initialization and observed coverage

The smallest useful connection is a view over owners that already exist:

1. Enumerate the loaded category definitions, exact `EVENT_MODELS`, public fact tags, selected content declarations and `AnimationData` dictionaries. Keep their identity kinds distinct. `EventQueue` is an instance/handler registry (`dnd/core/events.py:1413`), not a serializer or animation catalogue.
2. Let existing binder/reducer owners expose small passive capability descriptions where the ownership is otherwise unavailable. A description says what that owner can execute and represent; it is not another event dispatcher, a recipe copy or a rule expression language.
3. Join actual loaded recipe/rig/media metadata to those descriptions with normal IDs and dictionary lookups. Classify selected fields using the relevant owner's declared capabilities. Do not infer correctness just because Pydantic accepted a record.
4. Keep **expected representation**, **declared implementation**, **selected binding**, **observed exercise**, and **human visual review** separate. Technical/log or parent/state ownership needs an explicit reason; unknown support must remain unassessed. An accepted omission is a product decision, not automatically inferred from lack of a cue.
5. During actual lineage binding/replay, use the existing bound result, source identity, perspective and `BoundChoreography.gaps`. Structured owner/reason values can improve this existing evidence; avoid parsing diagnostic prose into a new rules engine. Collect at binding, not every frame. A hidden actor is not a missing actor animation.
6. Registry-wide inspection can use an explicit developer entry point to import the existing catalog composition, as this review did. Ordinary presentation initialization should use already selected/loaded content and must not start importing every unused native module just to build a dashboard.

`devtools/generate_event_contract.py:162` already has an offline subclass-discovery helper, and `:187` deliberately imports native modules to build a manifest. Do **not** move that import-all discovery into game startup or make its output a second hand-maintained presentation authority. The existing exact recording map and initialized content bindings are sufficient inputs for this work; the dynamic observed result fills the cases static declarations cannot decide.

The diagnostic output can be ordinary passive JSON. It must not gate gameplay with SHA checks, source provenance validation, directory scans, image audits, per-frame event traversal or extra serialization of every native event. Nothing in this document proposes a new runtime native registry.

## Bounded next use of this inventory

Use this snapshot to implement the cleanup plan's initialized support view and connect it to the existing review gallery. Then a selected feature can show, for example, “condition membership implemented; weapon coating track unsupported; no visual review yet,” rather than one misleading green badge.

Keep the proven lineage, sensory and jump behavior intact. Custom root/connector/level limitations above belong in honest coverage rows; only a selected gameplay requirement makes one an implementation unit. Missing spell content should be grouped by its shared delivery and effect needs when authorized, rather than become 101 unrelated executors. This inventory neither silently expands the plan nor excuses leaving an already selected requirement unfinished.

## ECS / anti-OOP review of the cleanup plan

The revised `GRAPHICS_CLEANUP_PLAN_2026-09-20.md` is approved as a bounded sequence. Unit 1 makes effective passive authoring authoritative while preserving composed output; it does not make entities responsible for drawing or introduce a recipe hierarchy. Units 4–5 distinguish instance registry, recording models, public facts, registered content, selected bindings and observed evidence. Their proposed capability descriptions remain beside the existing owners and do not replace dispatch or native subjectivity.

The explicit output baseline resolves the earlier risk of preserving JSON while changing its interpreted effect. Keep the same saved inputs and selected actual frames/contact traces for that comparison. Imported old TS behavior must not overwrite corrected prelaunch jump reactions or interrupted sub-tile visual positions. No additional framework or runtime change is required by this review; the concrete limits above are inventory entries rather than a new automatic mechanics backlog.
