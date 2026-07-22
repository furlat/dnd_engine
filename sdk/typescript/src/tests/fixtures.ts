import {
  EVENT_CONTRACT_HASH,
  EVENT_CONTRACT_VERSION,
  type APIAppearance,
  type APIEntitySummary,
  type BaseCondition,
  type ConditionApplicationEvent,
  type DamageAppliedEvent,
  type ForcedMovementEvent,
  type GameEventPayload,
  type ReplicationBootstrapResponse,
  type SensoryUpdateEvent,
  type SpatialChangeEvent,
  type StepMovementEvent,
} from "../index.js";

const appearance: APIAppearance = {
  portrait_key: null,
  presentation_kind: "layered",
  visual_scale: 1,
  placeholder_tint: 0x00ff00,
  body_category: "NakedBody",
  skin_tint: 0xffccaa,
  head_category: "Head1",
  hair_tint: 0x332211,
  has_beard: false,
  beard_tint: 0x332211,
};

function entity(uuid: string, name: string, position: [number, number]): APIEntitySummary {
  return {
    uuid,
    name,
    position,
    hp: 20,
    max_hp: 20,
    ac: 15,
    conditions: [],
    condition_details: [],
    is_dead: false,
    faction: uuid === "hero" ? "heroes" : "monsters",
    creature_type: "humanoid",
    size: "Medium",
    appearance,
  };
}

export function bootstrap(generationId = "generation-a"): ReplicationBootstrapResponse {
  return {
    protocol: {
      generation_id: generationId,
      event_contract_version: EVENT_CONTRACT_VERSION,
      event_contract_hash: EVENT_CONTRACT_HASH,
    },
    event_cursor: 0,
    combat_log_cursor: 0,
    state: {
      grid: {
        min_x: 0,
        min_y: 0,
        max_x: 9,
        max_y: 9,
        tiles: [{
          x: 0,
          y: 0,
          walkable: true,
          visible: true,
          name: "Floor",
          walking_cost: 1,
          is_hazardous: false,
          conditions: [],
          light_level: 3,
          directional_blocks_movement: { north: false, south: false, east: false, west: false },
          directional_blocks_vision: { north: false, south: false, east: false, west: false },
          directional_blocks_light: { north: false, south: false, east: false, west: false },
          directional_blocks_propagation: { north: false, south: false, east: false, west: false },
        }],
      },
      entities: [entity("hero", "Hero", [0, 0]), entity("monster", "Monster", [4, 0])],
      encounter: {
        uuid: "encounter",
        name: "Test",
        state: "active",
        round_number: 1,
        current_turn_index: 0,
        current_entity_uuid: "hero",
        initiative_order: [
          { uuid: "hero", name: "Hero", initiative: 15, is_dead: false },
          { uuid: "monster", name: "Monster", initiative: 10, is_dead: false },
        ],
      },
      floor_objects: [],
    },
    visibility: {
      hero: {
        name: "Hero",
        position: [0, 0],
        visible_cells: [[0, 0]],
        visible_entities: ["hero"],
        visible_objects: [],
        seen_cells: [[0, 0]],
        sense_modes: [],
        effective_light_levels: { "0,0": 3 },
      },
    },
    combat_log: [],
    session: null,
  };
}

function commonEvent(sourceEntityUuid: string, lineage: string) {
  return {
    name: "Event",
    uuid: `${lineage}-completion`,
    source_entity_uuid: sourceEntityUuid,
    source_entity_name: sourceEntityUuid,
    target_entity_uuid: null,
    target_entity_name: null,
    context: null,
    use_register: true,
    lineage_uuid: lineage,
    timestamp: "2026-07-20T12:00:00",
    phase: "completion" as const,
    modified: false,
    canceled: false,
    canceled_from_phase: null,
    parent_event: null,
    status_message: null,
    outcome_code: null,
    outcome_source_entity_uuid: null,
    is_first: true,
    is_last: true,
    lineage_children_events: [],
    children_events: [],
    parent_lineage: null,
    children_lineages: [],
  };
}

export function stepEvent(
  cursor: number,
  from: [number, number],
  to: [number, number],
  committed = true,
): GameEventPayload {
  const event: StepMovementEvent = {
    ...commonEvent("hero", `step-${cursor}`),
    wire_type: "dnd.core.events.StepMovementEvent",
    event_type: "step_movement",
    from_position: from,
    to_position: to,
    path_index: cursor,
    total_path_length: 3,
    movement_cost: 5,
    trajectory: "path",
    committed,
  };
  return {
    generation_id: "generation-a",
    event_index: cursor - 1,
    event_cursor: cursor,
    combat_log_cursor: 0,
    event,
  };
}

export function forcedMovementEvent(cursor: number): GameEventPayload {
  const event: ForcedMovementEvent = {
    ...commonEvent("monster", `forced-${cursor}`),
    wire_type: "dnd.core.events.ForcedMovementEvent",
    event_type: "forced_movement",
    target_entity_uuid: "hero",
    target_entity_name: "Hero",
    start_position: [1, 0],
    end_position: [3, 0],
    direction: [1, 0],
    intended_distance: 10,
    actual_distance: 10,
    blocked_by_obstacle: false,
    blocked_by: null,
    cause: "Shove",
  };
  return {
    generation_id: "generation-a",
    event_index: cursor - 1,
    event_cursor: cursor,
    combat_log_cursor: 0,
    event,
  };
}

export function spatialLightEvent(
  cursor: number,
  lightLevelMap: Record<string, number>,
): GameEventPayload {
  const representative = Object.keys(lightLevelMap)[0] ?? "0,0";
  const [x, y] = representative.split(",").map(Number);
  const event: SpatialChangeEvent = {
    ...commonEvent("hero", `light-${cursor}`),
    wire_type: "dnd.core.events.SpatialChangeEvent",
    event_type: "spatial_light_changed",
    change_type: "light_changed",
    position: [x ?? 0, y ?? 0],
    entity_uuid: null,
    object_uuid: null,
    old_position: null,
    tile_walkable: null,
    tile_visible: null,
    senses_hint: null,
    new_light_level: lightLevelMap[representative] ?? null,
    light_level_map: lightLevelMap,
    object_name: null,
    object_map_char: null,
    object_blocks_movement: null,
    object_blocks_vision: null,
    object_is_open: null,
    directional_position: null,
    directional_directions: null,
    directional_channels: null,
    directional_blocks_movement: null,
    directional_blocks_vision: null,
    directional_blocks_light: null,
    directional_blocks_propagation: null,
    transition_from: null,
    transition_to: null,
  };
  return {
    generation_id: "generation-a",
    event_index: cursor - 1,
    event_cursor: cursor,
    combat_log_cursor: 0,
    event,
  };
}

export function sensoryUpdateEvent(
  cursor: number,
  observerPosition: [number, number],
  effectiveLightLevels: Record<string, number>,
): GameEventPayload {
  const event: SensoryUpdateEvent = {
    ...commonEvent("hero", `sensory-${cursor}`),
    wire_type: "dnd.core.events.SensoryUpdateEvent",
    event_type: "sensory_update",
    target_entity_uuid: "hero",
    target_entity_name: "Hero",
    observer_uuid: "hero",
    observer_position: observerPosition,
    observer_position_changed: true,
    effective_light_levels: effectiveLightLevels,
    cause_event_uuid: `cause-${cursor}`,
    update_reason: "self_movement",
    visible_cells_added: [[1, 0]],
    visible_cells_removed: [],
    seen_cells_added: [[1, 0]],
    visible_entities_added: {},
    visible_entities_removed: {},
    visible_entities_moved: {},
    visible_objects_added: {},
    visible_objects_removed: {},
    visible_objects_moved: {},
    sense_modes_changed: false,
    sense_modes: null,
    passive_perception_changed: false,
    passive_perception: null,
    paths_dirty: true,
  };
  return {
    generation_id: "generation-a",
    event_index: cursor - 1,
    event_cursor: cursor,
    combat_log_cursor: 0,
    event,
  };
}

export function damageAppliedEvent(
  cursor: number,
  resultingNormalHp: number,
  resultingTemporaryHp: number,
): GameEventPayload {
  const event: DamageAppliedEvent = {
    ...commonEvent("monster", `damage-${cursor}`),
    wire_type: "dnd.core.events.DamageAppliedEvent",
    event_type: "damage_applied",
    target_entity_uuid: "hero",
    target_entity_name: "Hero",
    applied_damage: 4,
    normal_hit_point_damage: 2,
    temporary_hit_point_damage: 2,
    resulting_normal_hp: resultingNormalHp,
    resulting_temporary_hp: resultingTemporaryHp,
    damage_type: "Force",
    damages: [],
    effect_id: "fixture.damage",
    resolution: null,
  };
  return {
    generation_id: "generation-a",
    event_index: cursor - 1,
    event_cursor: cursor,
    combat_log_cursor: 0,
    event,
  };
}

function fixtureCondition(name: string): BaseCondition {
  return {
    name,
    uuid: `condition-${name}`,
    source_entity_uuid: "hero",
    source_entity_name: "Hero",
    target_entity_uuid: "hero",
    target_entity_name: "Hero",
    context: null,
    use_register: true,
    semantic_key: `fixture.${name}`,
    content_kind: "condition",
    condition_category: "condition",
    duration: {
      name: null,
      uuid: `duration-${name}`,
      source_entity_uuid: "hero",
      source_entity_name: "Hero",
      target_entity_uuid: "hero",
      target_entity_name: "Hero",
      context: null,
      use_register: true,
      duration: null,
      duration_type: "permanent",
      long_rested: false,
      owned_by_condition: null,
      is_expired: false,
    },
    application_saving_throw: null,
    removal_saving_throw: null,
    applied: true,
    modifers_uuids: {},
    parent_condition: null,
    sub_conditions: [],
    event_handlers_uuids: [],
    spatial_handler_uuids: [],
    linked_conditions: [],
    parent_link: null,
    child_removal_policy: "none",
    hazard_filter: null,
    condition_stealth_dc: null,
    tags: [],
    outcome_protections: [],
    removal_triggers: [],
    agency_denial: "none",
    applied_source_event_cursor: null,
  };
}

export function maxHpConditionEvent(
  cursor: number,
  resultingMaxHp: number,
): GameEventPayload {
  const event: ConditionApplicationEvent = {
    ...commonEvent("hero", `condition-${cursor}`),
    wire_type: "dnd.core.base_conditions.ConditionApplicationEvent",
    event_type: "condition_application",
    target_entity_uuid: "hero",
    target_entity_name: "Hero",
    condition: fixtureCondition("Fortified"),
    resulting_ac: 17,
    resulting_max_hp: resultingMaxHp,
  };
  return {
    generation_id: "generation-a",
    event_index: cursor - 1,
    event_cursor: cursor,
    combat_log_cursor: 0,
    event,
  };
}
