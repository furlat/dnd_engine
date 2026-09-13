# AI knowledge: recorded field map and implementation boundary

September 13, 2026. Source investigation for sections 2 and 3 of the
[approved repair plan](PERFORMANCE_FIX_PLAN_2026-09-12.md). This document maps
the existing output, including fields outside the Basic policy's immediate
reads. It does not introduce another rules model or authorize changed perception.
No runtime code, tests or timing jobs were run for this investigation.

## Conclusion and proposed work split

The assignment can retain its knowledge from source-ordered native records.
Current births and sensory deltas provide much of the required input. The
remaining work is not simply changing the caller of the player reducer:

1. Preserve cold condition semantics and actual health/affinity after-values at
   native commit owners. The current player condition record intentionally omits
   these AI fields and INTERNAL conditions.
2. Connect already-recorded world facts, including Tile/light/structural edits.
   Directed edge inputs are already recorded for the supported world objects;
   reuse the current pure edge calculation. Observer-dependent hazard results
   need a native recorded after-value or a shared native producer, not another
   implementation of hazard rules inside AI reduction.
3. Fold these inputs at the existing assignment owner, retaining private current
   actor/world facts for later admission and separate subjective memory. Advance
   before decisions and committed-Step continuation. The visual queue still
   receives complete lineages.

Suggested implementation ownership: root handles condition/actor producer facts;
the world/sensory lane handles missing hazard results and extraction of shared
recorded world/edge calculation; lifecycle_source_review handles the AI fold and
its focused replay checks. Agree the passive value fields before parallel edits.
This is a file division, not three new runtime services.

## Source and exposure conventions

The current output schema is
[observation.py](../dnd/ai/contracts/observation.py:360).
The actual native producer is
[state_projection.py](../dnd/ai/runtime/state_projection.py:91), which calls
[subjective_projection.py](../dnd/ai/runtime/subjective_projection.py:67).
It is a live query today. Its local observation cursor counts calls, not source
events. Assignment.start only validates ownership; it attaches no event consumer
([assignment.py](../dnd/ai/runtime/assignment.py:162)).

The following distinctions apply throughout the tables:

- **Recorded:** an existing immutable native payload contains the value. It may
  still be omitted by the finite game archive or its fold.
- **Derivable:** the recorded inputs suffice using an existing shared pure rule.
  A missing convenience field is not automatically a missing native fact.
- **Missing:** a concrete live producer changes a consumed value without its
  primitive after-value being retained. The native owner must supply it.
- **Context:** assignment configuration or current decision authority, which
  should remain an explicit input rather than masquerading as observation.

For actor exposure, controlled actors always count as known. Other actors are
visible when present in any explicitly controlled observer's entity contacts.
These are typed PerceivedContacts, so a nonvisual contact can establish the
existing AI knowledge state named VISIBLE. Do not substitute a visual-only test.
The observer list is the exact assignment list, not every entity of its faction
([subjective_projection.py](../dnd/ai/runtime/subjective_projection.py:138)).

For object exposure, use actual object contacts. The current AI does not add the
player renderer's special structural-object visibility rule to known_objects;
physical boundary effects are separately present in known_tiles. Preserve that
distinction rather than unioning player packets as the AI implementation.

## Top-level state, assignment and encounter fields

| Output fields | Current source and recorded replacement |
|---|---|
| observation_cursor | Assignment-local counter at state_projection.py:99. Keep its identity meaning explicit; maintain a separate EventQueue generation/raw source cursor for input progress. |
| session | Rebuild this small context record from the existing assignment and current actor identifier, not live world projection. |
| encounter | Current TurnContext plus retained actor identity/life and current observer contacts; no live Entity lookup is needed for its visible rows once actor facts are retained. |
| observers, known_entities, known_objects, known_tiles | Maps described below. Their contents become retained event-fed values. |
| combat_logs | Native state_projection.py:123 carries the previous list or an initially empty list. No current native AI ingestion populates it. Preserve this behavior; reconnecting the retired journal's log stream is not a prerequisite. |
| current_epoch | Set to None by world projection, then supplied by build_decision_epoch at state_projection.py:77–87. Still a native action-discovery/authority input, not a world-event replay obligation. |
| epoch_cursor | Currently follows the local observation/query counter in subjective_projection.py:106. Keep decision identity separate from source progress; a decision without a sensory delta still has its normal epoch. |

All ObservationSessionState fields are covered by
[state_projection.py](../dnd/ai/runtime/state_projection.py:129):

| Fields | Source |
|---|---|
| session_id | Existing assignment_id. |
| player_type, connection_status | Existing native constants ai and connected. |
| name | Existing AI + assignment_id display text. |
| controlled_entity_uuids | Exact sorted assignment UUID tuple. |
| active_entity_uuid, active_entity_name | Current actor context; name from retained birth. |
| is_my_turn | True at the existing active-assignment projection boundary. Do not invent remote-session authority. |

All ObservationEncounterState and ObservationCombatantState fields are covered
by [state_projection.py](../dnd/ai/runtime/state_projection.py:145):

| Fields | Source and exposure |
|---|---|
| encounter.uuid, name, state, round_number, turn_started_source_event_cursor | Current TurnContext. Native EncounterStart/End, RoundStart/End and TurnStart/End also record lifecycle facts. EncounterStart does not carry every TurnContext value, notably initiative totals; replay tests can record the legitimate context separately. |
| encounter.current_entity_uuid, current_entity_name | Current acting actor ID and retained name. |
| encounter.current_turn_index | Index of that actor within the subjective filtered initiative rows, or -1. It is not simply the objective turn index. |
| encounter.initiative_order | Filter TurnContext.initiative_order by controlled IDs or current union of contacts, preserving that order. |
| row.uuid, name, life_state, is_dead | Retained actor identity and current life; is_dead derives only from LifeState.DEAD. |
| row.initiative | TurnContext.initiative_totals for that UUID. |
| row.is_controlled, knowledge_state, observer_uuids | Exact assignment membership, existing VISIBLE value, and sorted seeing/self observer IDs. |

TurnContext is an existing execution input
([controller.py](../dnd/controller.py:33)); keeping it does not permit actor,
Senses or GridMap reads inside replay. Action-economy/target options stay in the
existing decision-epoch builder. The epoch ID embeds the observation counter
([decision_epoch.py](../dnd/ai/runtime/decision_epoch.py:168)).

## Observer fields

The entire ObservationObserverState is materializable from birth plus the
existing neutral sensory reducer:
[senses.py](../dnd/types/senses.py:129).
SensoryUpdateEvent has a real full initial form and subsequent deltas
([events.py](../dnd/core/events.py:3272)).

| Fields | Initialization and updates |
|---|---|
| observer_uuid | Exact controlled UUID; event.observer_uuid must match. |
| entity_name | EntityCreatedEvent.entity_name. No runtime renaming producer was found in this bounded native path. |
| position | Initial sensory observer_position; later observer_position_changed updates. Birth is intentionally actor composition before deployment and has no grid position. |
| passive_perception | Initial scalar and passive_perception_changed after-value. |
| sense_modes | Initial modes and sense_modes_changed after-values; preserve current order and the sense_type/range_feet dictionary shape. |
| visible_cells | Sorted reduced visible additions/removals. |
| seen_cells | Sorted monotonically accumulated seen_cells_added. |
| visible_entity_uuids, visible_object_uuids | Sorted keys of reduced typed contact maps, including their nonvisual contacts. |

The retained sensory input also carries visual_access and effective light. These
are important producer/replay inputs but are not fields of the current AI
ObservationObserverState. In particular, the AI Tile light field below currently
uses physical resolved light, not the observer-adjusted effective-light map.

## Actor fields

Birth fields are declared at
[events.py](../dnd/core/events.py:950) and captured from the finished aggregate at
[entity.py](../dnd/entity.py:820). Existing shared HP/equipment/life after-value
folding is in [actor_projection.py](../game/actor_projection.py:18).

| Fields | Initialization | Actual updates and retention |
|---|---|---|
| uuid, name | entity_uuid, entity_name | Retain stable identity; name is a birth value in the traced path. |
| knowledge_state, observer_uuids, controlled | Exact assignment membership and initial sensory contacts | Recompute only affected exposure when those contacts change. Preserve sorted observer attribution and VISIBLE/REMEMBERED semantics. |
| position | Initial deployment/observer contact; birth has none | Current typed contact position, observer origin for self, or committed movement/spatial position for controlled actor; remember last known position on loss. Never read a hidden actor's live position to update subjective memory. |
| normal_hp | maximum_hit_points minus damage_taken | DamageAppliedEvent.resulting_normal_hp; HealEvent.resulting_normal_hp; LifeStateChangeEvent.normal_hit_points. Max-HP-changing conditions and direct health writes need the additional after-values described below. |
| temporary_hp | temporary_hit_points | DamageApplied/Heal already carry resulting_temporary_hp. Direct temporary-HP grants/removal do not consistently publish this generic after-value. |
| max_hp | maximum_hit_points | Condition events have optional resulting_max_hp for the existing authored owners; retain their exact result. |
| hp | normal_hp + temporary_hp | Preserve current AI total-HP convention. A max-HP change can alter normal HP even without a DamageApplied event. |
| healing_blocked | Health.healing_blocked at birth is not currently in EntityCreatedEvent | NoHealing directly changes this boolean; record its actual initial and committed after-values. Do not infer from a condition name. |
| ac | armor_class | Owned ItemLocationStateEvent.entity_armor_class_after and condition resulting_ac. Keep native AC evaluation at the owner. |
| conditions | Active condition names, including INTERNAL | Add/remove keyed by actual condition UUID/name; source-order pre-birth condition facts must survive birth materialization. The player fold's INTERNAL exclusion cannot be reused as AI policy. |
| condition_semantic_keys | Actual BaseCondition.get_semantic_key values | Retain cold semantic identity at application; sorted keys of current conditions. behavior_id usually supplies it, but explicit legacy semantic_key/unbound fallback is also current source behavior. |
| condition_facts | Metadata table below | Apply/remove immutable condition values; do not keep or later inspect mutable BaseCondition instances. |
| effect_protections | Metadata table below | Flatten actual protections from active conditions, sorted by protection ID and supplying condition key as today. |
| is_concentrating | Actual ConditionTag.CONCENTRATION membership | Retain the tag fact with condition metadata; derive any active matching membership, not a spell-name list. |
| damage_vulnerabilities, damage_resistances, damage_immunities | Birth.damage_affinities is already captured from the effective native resistance result | Conditions such as ProtectionFromEnergy change effective values without primitive after-values today. Record the native resolved affinity tuple at its existing commit owner; preserve DamageType order when forming output lists. |
| creature_type, faction | Already in EntityCreatedEvent | Reuse birth facts; ordinary traced production creates summoned actors with their own births. No new mutable faction/type producer is proposed without an actual changing owner. |
| life_state, is_dead | Birth.life_state | LifeStateChangeEvent.new_state; is_dead is the derived equality to DEAD. |

Exact loss behavior is
[remember_entity_fact](../dnd/ai/runtime/subjective_projection.py:255): clear
HP/max/temp/healing/AC, current conditions/semantics/protections, concentration
and affinity lists. Preserve last position/name and the existing faction and
creature_type values. Preserve DEAD terminal knowledge; otherwise clear life and
is_dead. Keep this actual behavior rather than interpreting field descriptions
as a new redaction policy. Reacquisition admits the current recorded aggregate,
including changes made while hidden, at the actual contact event.

### Condition metadata and concrete producer gaps

| Nested fields | Existing native source and missing connection |
|---|---|
| ConditionFact.semantic_key | BaseCondition.get_semantic_key, base_conditions.py:377. Capture once as data; do not restore concrete classes during replay. |
| removal_triggers, agency_denial | Typed fields at base_conditions.py:462–469. Existing event.condition holds them live; game ConditionFact omits them. |
| applied_source_event_cursor | Entity.add_condition and BaseBlock.add_condition set this after publishing application COMPLETION (entity.py:1697–1700; base_block.py:1217–1220). Capture the actual application boundary deliberately; a later read from the shared mutable condition is not an immutable historical record. |
| protection.protection_id, blocked_effect_ids, source_condition_semantic_key | Actual condition.outcome_protections at base_conditions.py:458; current flattening is subjective_projection.py:349. Record those primitive rows, not a reconstructed condition-effect prediction catalog. |
| concentration membership and condition identity/category | Actual tags/name/UUID/category on BaseCondition. Player rendering may still filter its own display; AI needs the existing complete active membership. |

Concrete changes needing owner after-values:

- NoHealing sets Health.healing_blocked True/False directly
  ([necromancy.py](../dnd/spells/necromancy.py:127)).
- ProtectionFromEnergy adds an actual resistance modifier
  ([abjuration.py](../dnd/spells/abjuration.py:606)); generic removal cleans up
  that modifier. A birth affinity tuple cannot cover this later transition.
- Aid changes max HP and therefore the current normal-HP result without a
  damage/heal packet ([abjuration.py](../dnd/spells/abjuration.py:2674)). Its
  existing resulting_max_hp is useful; retaining only that field while leaving
  normal HP unchanged is insufficient for exact AI output.
- FalseLife calls Health.add_temporary_hit_points
  ([necromancy.py](../dnd/spells/necromancy.py:116)). Its custom temp_hp_gained
  attribute is neither a generic authoritative after-value nor a reason to add
  a FalseLife reducer. Health replacement rules remain native. Direct clearing
  on Health.on_long_rest is another actual owner of the same value
  ([health.py](../dnd/blocks/health.py:704)).

The bounded proposal is immutable condition metadata plus exact owner status
after-values on accepted application/removal, reusing the actual Entity health,
AC and affinity queries once at that commit. Entity.add_condition owns its
application completion. BaseBlock._commit_prepared_condition_removals owns
child-first removal completion after cleanup and index removal
([base_block.py](../dnd/core/base_block.py:967)). Maintain the import DAG through
the existing aggregate/capability boundary; core BaseBlock must not import
Entity. This is a publication hook at an existing commit, not a second rule
executor or an all-entity snapshot after every event.

Direct temporary-HP changes require the same generic health after-value at their
actual owner/caller boundary. Confirm its causal parent before implementation;
do not reinterpret a temporary-HP grant as ordinary HealEvent or replay an
unregistered arbitrary spell attribute. This is a real missing record, not an
authorization to rewrite rest or health rules.

## Object fields and the finite public state dictionary

Current object source is
[subjective_projection.py](../dnd/ai/runtime/subjective_projection.py:431).
WorldInitializedEvent.objects contains WorldObjectState with placement and a
primitive ItemPresentationState. ItemLocationStateEvent supplies replacement
item data after placement/ownership mutation; SpatialChangeEvent.OBJECT_CHANGED
supplies committed placement/structural/open/name/blocking values.

| Output fields | Recorded source and update |
|---|---|
| uuid, name, map_char | item_uuid, name, map_char from item state; actual subsequent item/spatial after-values. |
| position | Current contact position; fallback placement for a currently known object. |
| knowledge_state, observer_uuids | Union of exact controlled object contacts. On loss, retain prior object values and set REMEMBERED with no observers. |
| state.is_open | ItemPresentationState.is_open and Spatial object_is_open; omit when the native source does not expose a primitive open value. |
| state.blocks_movement | Recorded item/spatial global blocker value. |
| state.blocks_optics_field, state.blocks_propagation_field | Current native output names correspond to recorded blocks_optics/blocks_propagation primitive fields. Mapping these names is not new geometry. |
| state.is_pickable, state.is_usable, state.charges, state.stack_count | Existing ItemPresentationState. ItemChargeConsumptionEvent supplies committed counters/destruction; keep ownership placement separately. Only expose the current known object, not the private inventory of an observed actor. |
| state.blocked_channels | Current reflector exposes the provider's configured channels, not necessarily its effective BoundaryStructure channels. An open DirectionalDoor keeps configured channels while get_boundary_structure returns an empty tuple (environment.py:250,277). Exact configured channels for a door born open are not in current ItemPresentationState. If retaining this implementation-facing dictionary key, add its exact primitive source; do not equate configured and effective values. |
| state.blocked_directions | The current helper still checks this legacy attribute; no present native runtime declaration was found in the owned object classes. Do not invent an empty field or revive tile-side legacy objects. |
| state.is_hazardous, state.hazardous | The helper checks these primitive attributes, but current native blocks expose is_hazardous_for as a method; no concrete native boolean declaration was found. Preserve actual omission. Tile hazard knowledge below is the functioning native hazard projection. |

The current reflective helper examines only the thirteen listed keys
([subjective_projection.py](../dnd/ai/runtime/subjective_projection.py:592)). A
replacement should map explicit recorded fields and actual presence, rather than
copying its hasattr/getattr machinery or transmitting arbitrary object graphs.

## Tile fields, hazards and directed boundaries

Current Tile output is
[project_visible_tile_fact](../dnd/ai/runtime/subjective_projection.py:507).
Initial support data is already in WorldTileState
([events.py](../dnd/core/events.py:788)), captured by
[project_world_tile](../dnd/world_authoring.py:95).

| Output fields | Recorded or native source and update |
|---|---|
| key, position | Existing x,y key and tile coordinate. |
| knowledge_state, observer_uuids | VISIBLE from union of current visible cells; otherwise SEEN and observer attribution from seen sets. Preserve prior values when unseen, including tiles absent from a later observer set. |
| name | WorldTileState.name; WorldModifiedEvent Tile replacement is already a full after-state. |
| walking_cost, walkable | WorldTileState.walking_cost; later SpatialChangeEvent.tile_walking_cost / WorldModifiedEvent.after. walkable means walking_cost > 0 here, not occupancy or complete path legality. |
| light_level | WorldTileState.resolved_light and SpatialChangeEvent.light_level_map/new_light_level. This is physical native resolved light; do not replace it with observer-adjusted effective light. |
| conditions | Literal tile.active_conditions names in current projection. Native ConditionApplication/Removal membership can retain these by target Tile UUID. Independent AreaCondition footprints are separate and must not be renamed into this list. Cold WorldTileState currently has no initial condition-membership list. |
| is_hazardous | Native GridMap.is_position_hazardous_for for the first sorted seeing observer, covering tile conditions, placed objects and independent spatial conditions. Current records do not contain that resolved observer-dependent result. |
| directional_blocks_movement | Same first sorted seeing observer; native directed-edge reduction filters unknown boundary providers only for movement, then applies existing walking band-height rule. Inputs described below are recorded. |
| directional_blocks_vision, directional_blocks_light | Both are the physical optical edge result in current AI output. They are intentionally identical here. |
| directional_blocks_propagation | Physical propagation edge result. |
| adjacent_domain | For each existing AdjacentOffset, missing neighboring support Tile -> INVALID, existing Tile -> UNKNOWN. The current projector does not emit VALID. Recorded world support membership is sufficient; do not disclose adjacent terrain or occupancy. |

The first-observer rule is concrete existing behavior, not an averaging policy
([subjective_projection.py](../dnd/ai/runtime/subjective_projection.py:525)). If
the selected observer changes, its already-retained subjective value must be
selected; do not keep another observer's old hazard or movement-side value.

### Recorded world facts which the current game fold does not yet connect

The existing shared apply_world_fact currently handles WorldInitialized, floor
ItemLocation and OBJECT_CHANGED
([presentation.py](../game/presentation.py:333)). It does not yet apply all of:

- WorldModifiedEvent.before/after for accepted Tile/object/connector edits;
- Spatial TILE_CHANGED effective movement/blocking after-values;
- TileElevationChangeEvent height/surface/slope after-values;
- Spatial LIGHT_CHANGED map/scalar after-values;
- placement removal and floor-to-inventory/destruction facts for objective world
  membership;
- tile/independent condition membership and footprints.

Several of these already have native facts. Extend the one neutral world fold;
do not make another rules-aware AI map. The current game event codec also has a
finite explicit family set: an event class existing in dnd does not prove it is
present in today's saved game input. Add the required data family to that same
recording boundary for the new replay checks.

### Directed values are derivable, not a new native-fact requirement

Native GridMap._boundary_contributions uses provider UUID, exact recorded
placement side/base/top and BoundaryStructure.blocked_channels
([gridmap.py](../dnd/core/gridmap.py:2841)). get_world_edge adds recorded endpoint
height/surface values ([gridmap.py](../dnd/core/gridmap.py:2874)). Existing channel
reduction consumes those values; only the movement channel uses the observer's
known object IDs ([gridmap.py](../dnd/core/gridmap.py:1651)). Missing neighbors
block the four side maps. Height overlap applies to walking structural bands;
the map is not a replacement for pathfinding or elevation-transition legality.

Therefore the supported boundary calculation can be extracted intact into the
existing neutral edge owner and called by both GridMap and recorded projection.
This preserves one algorithm without looking up live providers. Recompute the
affected known sides when their source facts/contact attribution change; it
does not require another all-visible-tiles query at every decision.

### Hazard results are a real missing observer after-value

GridMap.is_position_hazardous_for checks three actual native owners
([gridmap.py](../dnd/core/gridmap.py:1397)). BaseBlock hazard rules inspect active
condition hazard_filter, stealth DC and requester/source relationships
([base_block.py](../dnd/core/base_block.py:428)); AreaCondition also resolves
concealment and source/enemy filters
([area_conditions.py](../dnd/spatial/area_conditions.py:147)).

SpatialEffectChangeEvent currently records effect identity, operation and old/new
footprints, not hazard_filter, stealth result or resolved per-observer hazardous
state ([events.py](../dnd/core/events.py:3457)). SensoryUpdateEvent also has no
hazard field. A fresh snapshot cannot reconstruct this result from those fields
alone. Replaying condition names through new hazard rules would duplicate the
engine.

Publish/reuse the native resolved hazardous result for newly known or actually
affected cells, with its observer and source boundary. Its owner should handle
existing hazard footprint/perception/relationship changes and removals. This can
be a small typed addition to existing observation facts; it must not become a
second full world projection hidden inside every sensory callback. A change to
hazard knowledge can matter even when contacts/visible cells are unchanged.
Exact hosting of this addition is the remaining small world-lane design choice.

## Smallest assignment fold

Keep the existing assignment owner and SubjectiveWorldState output. Use ordinary
records/functions with the following source order:

1. Initialize from actual WorldInitialized, EntityCreated, accepted pre-birth
   condition facts, initial SensoryUpdate for each controlled observer, and
   separate assignment/turn context. Keep pre-birth facts keyed by their actual
   owner; do not drop them because the actor dictionary is not populated yet.
2. Maintain a raw input cursor plus EventQueue generation. At each current
   decision/Step boundary, consume the fixed available source prefix through
   iter_events_since. Process actual committed facts, not a regrouping by root
   completion. No repeated full-history admission fold.
3. Apply shared cold actor/world after-values privately. Retain the reduced
   SensesSnapshot for each exact controlled observer. On actual contact
   acquisition, materialize the current recorded actor/object data; hidden
   mutations alone do not refresh a remembered subjective fact.
4. Update only affected subjective entity/object/tile entries. Contact loss
   applies existing memory rules; a later contact reacquires current recorded
   values. Apply appearance/loss in event order even between two AI decisions,
   so a brief observed actor leaves its legitimate memory.
5. Assemble the small session/encounter context at the existing call boundary,
   then let the existing action epoch builder discover/validate legal actions.
   World knowledge replay itself has no live Entity/Senses/GridMap calls.

Reuse neutral sensory reduction and extract actor/world field folds to a neutral
dependency owner as needed. Keep render-only appearance selection in game.
Do not make PlayerState the AI aggregate or import game.presentation's capture
or completed-lineage machinery into native AI. The existing AI-shaped
apply_observation_frame is a pure value reducer, but its old observer patch
shape is not today's SensoryDelta; there is no reason to manufacture old frames
and JSON round-trips merely to reach it.

EventQueue already offers raw indexed iteration and generation
([events.py](../dnd/core/events.py:1869)). Since-cursor consumption is enough for
the current native call sites. Use actual generation/reset ownership rather than
a new cache invalidation owner. If an eager consumer is later demonstrated,
existing immediate event callbacks suffice; action batching only delays the
separate batch callbacks.

### Causal boundary which implementation must preserve

Movement commits position and spatial/sensory children, completes a Step, then
calls continuation before completing the enclosing Move
([actions.py](../dnd/actions.py:851)). AI knowledge must be current there; visual
compilation still waits for the whole lineage.

Likewise a door's sensory child can precede its Spatial OBJECT_CHANGED parent's
completion. The recorded parent already carries the committed after-value, and
the existing player projector applies that value before its child senses
([player_projection.py](../game/player_projection.py:343)). Reuse the exact
causal-source rule for raw-prefix consumption: never read a future terminal
parent from a completed archive to repair a live prefix. Do not blanket-apply
all EFFECT events; only native owners which already committed the supplied
facts establish that value at the child's boundary.

No full actor/world snapshot per event, callback-driven mechanics rebuild,
observer manager, second clock, or parallel production projector is needed.
Keep the old live projector only as temporary test-oracle code during migration,
then remove it from the active path after field coverage passes.

## Focused completion evidence

Record expected observations at the actual source boundaries while running
native scenarios, then replay their saved primitive inputs with native registries
unavailable. Do not obtain expected values from the new reducer itself. Use the
existing native session and discovery/visibility/concealment producers, extending
only missing cases:

- pre-birth condition application plus actual initial Senses;
- hidden damage/equipment/status changes followed by acquisition and reacquisition;
- a brief doorway contact entirely between decisions;
- two controlled observers whose contacts and selected hazard/directional
  attribution differ, including loss by only one observer;
- actual NoHealing apply/remove, resistance apply/remove, Aid and a direct
  temporary-HP grant, checking current scalar values and cold condition metadata;
- known and remembered door changes, directed boundary height/directions,
  physical light change and actual hazard creation/removal/revelation;
- movement continuation observing the new hostile/hazard at Step completion
  while the Move root remains open, with its complete visual lineage preserved.

Current Basic policy uses healing_blocked directly
([basic.py](../dnd/ai/policies/basic.py:570)); continuation reads known hostile,
hazard and actor HP/condition changes
([movement_revalidation.py](../dnd/ai/runtime/movement_revalidation.py:68)). These
are concrete behavior checks, not an argument for reproducing old server tests.
Existing paired fixtures and neutral sensory replay checks provide current
native histories. Historical server observation tests are source evidence only.

Anti-OOP review: lifecycle_source_review. The proposed fold reuses facts at the
assignment owner and distinguishes observed data from execution authority.
Anti-slop cross-review remains root/recorded_gallery on the concrete producer and
fold diff; this map is not its own validation.

## Implementation checkpoint

The shared actor after-value fold is now in `dnd/actor_projection.py`, with cold
records in `dnd/types/actor_facts.py`. One condition membership carries its
committed `ConditionState`, evaluated stats and optional Tile after-value. The
game adapter preserves its existing exclusion of internal conditions; AI keeps
the complete native membership. `TemporaryHitPointsChangedEvent` supplies direct
grants/clear after-values; ordinary damage retains its existing HP result event.
The world lane owns `WorldFacts`, source-position selection and pure tile/object
projection. Own sensory facts carry native resolved hazard values. Legacy
open-door raw/default blocker metadata is not copied: projection uses the
recorded evaluated item and structural state.

`AIKnowledge` consumes raw source versions in order, retaining only unfinished
parent versions needed for causal sensory ordering. It updates affected actor,
observer, object and tile values and preserves observer-attributed memory when
contacts disappear. `SubjectiveAIStateProjector` advances that fold at its
existing decision/Step callers and copies publication containers without
rebuilding every value. Assignment identity and query cursor remain separate
from EventQueue generation/source position. The old live projector has no active
native/game caller; its explicit retired-server callers and the migration
oracle tests keep that legacy module outside this cutover's runtime path.

Four focused native checks pass in `tests/ai/test_event_knowledge.py`: a brief
doorway appearance remembered after loss and replay; pre-birth condition state,
unseen damage and later deployment; loss by one of two controlled observers;
and native continuation stopping at the second Step when an actual doorway
reveals a hostile while the Movement root is still open. The saved-byte checks
replay with Entity/EventQueue registries cleared. The first failed fixture used
an assumed sight range and an out-of-map coordinate; the corrected cases use
actual doorway geometry and native deployment. No perception rule was changed.

The focused run reports **4 passed in 1.47s** with WSL Python 3.13.12. Pyright on
the eleven touched actor, AI and world source/test files reports zero errors and
warnings. The completed integrated selection subsequently passes 240 tests; the
final expanded 21-file Pyright check also passes. Recorded AI projection now takes
about 0.035s across 44 calls in the existing native diagnostic, compared with
0.818s before this unit. The eight-human-turn-plus-AI activity median is 1.419s
versus 2.376s previously. These are separate measurements; nested diagnostic
costs cannot be added. Full commands, setup/import costs, GC attribution and the
two preexisting legacy-suite failures are documented in
[the completed results](PERFORMANCE_REPAIR_RESULTS_2026-09-12.md#september-13-completed-sensory-and-ai-event-consumption-unit).
