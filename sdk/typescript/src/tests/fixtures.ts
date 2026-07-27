import {
  PLAYER_REPLICATION_CONTRACT_HASH,
  PLAYER_REPLICATION_CONTRACT_VERSION,
  type APIAppearance,
  type APIEntitySummary,
  type GameEventFrame,
  type StepMovementEvent,
  type SubjectiveCombatLogDelivery,
  type SubjectiveFrameDelivery,
  type SubjectiveReplicationBootstrap,
  type SubjectiveReplicationFrame,
  type SubjectiveSyncDelivery,
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

export function entity(
  uuid: string,
  name: string,
  position: [number, number],
): APIEntitySummary {
  return {
    uuid,
    name,
    position,
    hp: 20,
    max_hp: 20,
    ac: 15,
    conditions: [],
    condition_details: [],
    life_state: "alive",
    is_dead: false,
    faction: uuid === "hero" ? "heroes" : "monsters",
    creature_type: "humanoid",
    size: "Medium",
    appearance,
  };
}

export function bootstrap(generationId = "generation-a"): SubjectiveReplicationBootstrap {
  return {
    protocol: {
      player_replication_contract_version: PLAYER_REPLICATION_CONTRACT_VERSION,
      player_replication_contract_hash: PLAYER_REPLICATION_CONTRACT_HASH,
      source_stream_id: "stream-a",
      generation_id: generationId,
    },
    perspective: {
      projection: "subjective",
      perspective_epoch_id: "perspective-a",
      kind: "controlled_knowledge_union",
      controlled_entity_uuids: ["hero"],
      observer_entity_uuids: ["hero"],
      active_observer_uuid: "hero",
    },
    watermarks: watermarks(),
    world: {
      state: {
        grid: {
          min_x: 0,
          min_y: 0,
          max_x: 9,
          max_y: 9,
          tiles: [{
            x: 0,
            y: 0,
            visual_key: "floor",
            walkable: true,
            visible: true,
            name: "Floor",
            walking_cost: 1,
            is_hazardous: false,
            conditions: [],
            condition_details: [],
            light_level: 3,
            directional_blocks_movement: directions(),
            directional_blocks_vision: directions(),
            directional_blocks_light: directions(),
            directional_blocks_propagation: directions(),
            directional_structural_edges: structuralEdges(),
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
            { uuid: "hero", name: "Hero", initiative: 15, life_state: "alive", is_dead: false },
            { uuid: "monster", name: "Monster", initiative: 10, life_state: "alive", is_dead: false },
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
      equipment_by_entity: {
        hero: {
          slots: [],
          active_weapon_set: "none",
          ac: 15,
          inventory: [],
        },
      },
      visual_loadout_by_entity: {
        hero: { entity_uuid: "hero", active_weapon_set: "none", layers: [] },
        monster: { entity_uuid: "monster", active_weapon_set: "none", layers: [] },
      },
    },
    combat_log_frames: {
      source_stream_id: "stream-a",
      generation_id: generationId,
      perspective_epoch_id: "perspective-a",
      projection: "subjective",
      retained_from_cursor: 0,
      from_cursor: 0,
      through_cursor: 0,
      frames: [],
      total: 0,
    },
  };
}

export function replicationFrame(cursor = 1): SubjectiveReplicationFrame {
  return {
    source_stream_id: "stream-a",
    generation_id: "generation-a",
    perspective_epoch_id: "perspective-a",
    watermarks: watermarks(cursor, cursor, cursor, 0),
    presentation_from_cursor: cursor - 1,
    patches: [{ kind: "entity_upsert", entity: entity("hero", "Hero", [cursor, 0]) }],
    presentation: [{
      kind: "movement",
      presentation_cursor: cursor,
      presentation_id: `presentation-${cursor}`,
      parent_presentation_id: null,
      child_presentation_ids: [],
      source_event_cursor: cursor,
      source_event_uuid: `event-${cursor}`,
      content_attributions: [],
      entity_uuid: "hero",
      movement_kind: "walk",
      trajectory: [[cursor - 1, 0], [cursor, 0]],
      path_start_index: cursor - 1,
      path_total_steps: cursor,
      perception_commit: "observation_frame",
    }],
  };
}

export function syncDelivery(captured = 1): SubjectiveSyncDelivery {
  const seed = bootstrap();
  return {
    kind: "sync",
    protocol: seed.protocol,
    perspective: seed.perspective,
    watermarks: watermarks(captured, captured, captured, 0),
  };
}

export function frameDelivery(cursor = 1): SubjectiveFrameDelivery {
  return { kind: "frame", frame: replicationFrame(cursor) };
}

export function hiddenLogDelivery(cursor = 1, eventCursor = 1): SubjectiveCombatLogDelivery {
  return {
    kind: "combat_log",
    watermarks: watermarks(eventCursor, eventCursor, eventCursor, cursor),
    frame: {
      source_stream_id: "stream-a",
      generation_id: "generation-a",
      perspective_epoch_id: "perspective-a",
      projection: "subjective",
      combat_log_cursor: cursor,
      event_cursor: eventCursor,
      entry: null,
    },
  };
}

export function objectiveStepFrame(cursor = 1): GameEventFrame {
  const event: StepMovementEvent = {
    name: "Step",
    uuid: `step-${cursor}`,
    source_entity_uuid: "hero",
    source_entity_name: "Hero",
    target_entity_uuid: null,
    target_entity_name: null,
    context: null,
    use_register: true,
    lineage_uuid: `lineage-${cursor}`,
    turn_execution_id: null,
    timestamp: "2026-07-20T12:00:00",
    phase: "completion",
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
    wire_type: "dnd.core.events.StepMovementEvent",
    event_type: "step_movement",
    from_position: [cursor - 1, 0],
    to_position: [cursor, 0],
    path_index: cursor,
    total_path_length: cursor,
    movement_cost: 5,
    trajectory: "path",
    committed: true,
  };
  return {
    source_stream_id: "encounter",
    generation_id: "generation-a",
    event_index: cursor - 1,
    event_cursor: cursor,
    combat_log_cursor: 0,
    event,
  };
}

export function watermarks(
  source = 0,
  observation = 0,
  presentation = 0,
  log = 0,
) {
  return {
    source_event_cursor: source,
    observation_cursor: observation,
    presentation_cursor: presentation,
    combat_log_cursor: log,
  };
}

function directions() {
  return { north: false, south: false, east: false, west: false };
}

function structuralEdges() {
  return { north: null, south: null, east: null, west: null };
}
