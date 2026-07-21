import type {
  APIDirectionalBlockMap,
  APIEntitySummary,
  APIEntityVisibility,
  APIFloorObject,
  APIGameState,
  APITile,
  APIVisibilityResponse,
  ServerEvent,
} from "./generated/contracts.generated.js";

export interface ReplicatedWorld {
  readonly state: APIGameState;
  readonly visibility: APIVisibilityResponse;
}

function terminalEffect(event: ServerEvent): boolean {
  return event.phase === "completion" && !event.canceled;
}

function replaceEntity(
  state: APIGameState,
  entityUuid: string | null,
  update: (entity: APIEntitySummary) => APIEntitySummary,
): APIGameState {
  if (entityUuid === null) {
    return state;
  }
  let changed = false;
  const entities = state.entities.map((entity) => {
    if (entity.uuid !== entityUuid) {
      return entity;
    }
    changed = true;
    return update(entity);
  });
  return changed ? { ...state, entities } : state;
}

function replaceTile(
  state: APIGameState,
  position: readonly [number, number],
  update: (tile: APITile) => APITile,
): APIGameState {
  let changed = false;
  const tiles = state.grid.tiles.map((tile) => {
    if (tile.x !== position[0] || tile.y !== position[1]) {
      return tile;
    }
    changed = true;
    return update(tile);
  });
  return changed ? { ...state, grid: { ...state.grid, tiles } } : state;
}

function replaceTileLightLevels(
  state: APIGameState,
  lightLevels: Readonly<Record<string, number>>,
): APIGameState {
  let changed = false;
  const tiles = state.grid.tiles.map((tile) => {
    const lightLevel = lightLevels[`${tile.x},${tile.y}`];
    if (lightLevel === undefined || lightLevel === tile.light_level) {
      return tile;
    }
    changed = true;
    return { ...tile, light_level: lightLevel };
  });
  return changed ? { ...state, grid: { ...state.grid, tiles } } : state;
}

function mergeDirectionalMap(
  current: APIDirectionalBlockMap,
  patch: Readonly<Record<string, boolean>> | null,
): APIDirectionalBlockMap {
  if (patch === null) {
    return current;
  }
  return {
    north: patch.north ?? current.north,
    south: patch.south ?? current.south,
    east: patch.east ?? current.east,
    west: patch.west ?? current.west,
  };
}

function reduceSpatialChange(state: APIGameState, event: Extract<ServerEvent, { wire_type: "dnd.core.events.SpatialChangeEvent" }>): APIGameState {
  if (event.event_type === "spatial_object_removed" && event.object_uuid !== null) {
    return {
      ...state,
      floor_objects: state.floor_objects.filter((object) => object.uuid !== event.object_uuid),
    };
  }
  if (event.event_type === "spatial_object_placed" && event.object_uuid !== null) {
    const floorObject: APIFloorObject = {
      uuid: event.object_uuid,
      name: event.object_name ?? "Object",
      position: [event.position[0], event.position[1]],
      map_char: event.object_map_char ?? "φ",
      state: {
        ...(event.object_blocks_movement === null ? {} : { blocks_movement: event.object_blocks_movement }),
        ...(event.object_blocks_vision === null ? {} : { blocks_vision: event.object_blocks_vision }),
        ...(event.object_is_open === null ? {} : { is_open: event.object_is_open }),
      },
    };
    return {
      ...state,
      floor_objects: [
        ...state.floor_objects.filter((object) => object.uuid !== event.object_uuid),
        floorObject,
      ],
    };
  }
  if (event.event_type === "spatial_object_changed" && event.object_uuid !== null) {
    const position: [number, number] = [event.position[0], event.position[1]];
    const floorObjects: APIFloorObject[] = state.floor_objects.map((object) => {
      if (object.uuid !== event.object_uuid) {
        return object;
      }
      return {
        ...object,
        position,
        name: event.object_name ?? object.name,
        map_char: event.object_map_char ?? object.map_char,
        state: {
          ...object.state,
          ...(event.object_blocks_movement === null ? {} : { blocks_movement: event.object_blocks_movement }),
          ...(event.object_blocks_vision === null ? {} : { blocks_vision: event.object_blocks_vision }),
          ...(event.object_is_open === null ? {} : { is_open: event.object_is_open }),
        },
      };
    });
    return { ...state, floor_objects: floorObjects };
  }
  if (
    event.event_type === "spatial_tile_changed"
    || event.event_type === "spatial_light_changed"
  ) {
    const stateWithBatchLight = event.event_type === "spatial_light_changed"
      && event.light_level_map !== null
      ? replaceTileLightLevels(state, event.light_level_map)
      : state;
    return replaceTile(stateWithBatchLight, event.position, (tile) => ({
      ...tile,
      walkable: event.tile_walkable ?? tile.walkable,
      visible: event.tile_visible ?? tile.visible,
      light_level: event.new_light_level ?? tile.light_level,
      directional_blocks_movement: mergeDirectionalMap(
        tile.directional_blocks_movement,
        event.directional_blocks_movement,
      ),
      directional_blocks_vision: mergeDirectionalMap(
        tile.directional_blocks_vision,
        event.directional_blocks_vision,
      ),
      directional_blocks_light: mergeDirectionalMap(
        tile.directional_blocks_light,
        event.directional_blocks_light,
      ),
      directional_blocks_propagation: mergeDirectionalMap(
        tile.directional_blocks_propagation,
        event.directional_blocks_propagation,
      ),
    }));
  }
  return state;
}

export function reduceGameState(state: APIGameState, event: ServerEvent): APIGameState {
  if (!terminalEffect(event)) {
    return state;
  }
  switch (event.wire_type) {
    case "dnd.core.events.StepMovementEvent":
      return event.committed
        ? replaceEntity(state, event.source_entity_uuid, (entity) => ({
            ...entity,
            position: [event.to_position[0], event.to_position[1]],
          }))
        : state;
    case "dnd.actions.MovementEvent":
    case "dnd.actions.JumpEvent":
      return replaceEntity(state, event.source_entity_uuid, (entity) => ({
        ...entity,
        position: [event.end_position[0], event.end_position[1]],
      }));
    case "dnd.core.events.ForcedMovementEvent":
      return replaceEntity(state, event.target_entity_uuid, (entity) => ({
        ...entity,
        position: [event.end_position[0], event.end_position[1]],
      }));
    case "dnd.core.events.DamageAppliedEvent":
      return replaceEntity(state, event.target_entity_uuid, (entity) => ({
        ...entity,
        hp: event.resulting_normal_hp + event.resulting_temporary_hp,
      }));
    case "dnd.core.events.HealEvent":
      return event.resulting_normal_hp === null
        ? state
        : replaceEntity(state, event.target_entity_uuid, (entity) => ({
            ...entity,
            hp: event.resulting_normal_hp ?? entity.hp,
          }));
    case "dnd.core.base_conditions.ConditionApplicationEvent": {
      const conditionName = event.condition.name;
      return replaceEntity(state, event.target_entity_uuid, (entity) => ({
        ...entity,
        hp: event.resulting_max_hp === null
          ? entity.hp
          : entity.hp + event.resulting_max_hp - entity.max_hp,
        conditions: conditionName === null || entity.conditions.includes(conditionName)
          ? entity.conditions
          : [...entity.conditions, conditionName],
        condition_details: conditionName === null || entity.condition_details.some(
          (condition) => condition.name === conditionName,
        )
          ? entity.condition_details
          : [
              ...entity.condition_details,
              {
                name: conditionName,
                category: event.condition.condition_category,
              },
            ],
        ac: event.resulting_ac ?? entity.ac,
        max_hp: event.resulting_max_hp ?? entity.max_hp,
      }));
    }
    case "dnd.core.base_conditions.ConditionRemovalEvent": {
      const conditionName = event.condition.name;
      return replaceEntity(state, event.target_entity_uuid, (entity) => ({
        ...entity,
        hp: event.resulting_max_hp === null
          ? entity.hp
          : entity.hp + event.resulting_max_hp - entity.max_hp,
        conditions: conditionName === null
          ? entity.conditions
          : entity.conditions.filter((name) => name !== conditionName),
        condition_details: entity.condition_details.filter(
          (condition) => condition.name !== conditionName,
        ),
        ac: event.resulting_ac ?? entity.ac,
        max_hp: event.resulting_max_hp ?? entity.max_hp,
      }));
    }
    case "dnd.core.events.DeathEvent": {
      let next = replaceEntity(state, event.entity_uuid, (entity) => ({
        ...entity,
        hp: event.final_hp,
        is_dead: true,
      }));
      if (next.encounter !== null) {
        next = {
          ...next,
          encounter: {
            ...next.encounter,
            initiative_order: next.encounter.initiative_order.map((combatant) =>
              combatant.uuid === event.entity_uuid
                ? { ...combatant, is_dead: true }
                : combatant,
            ),
          },
        };
      }
      return next;
    }
    case "dnd.core.events.TurnStartEvent":
      return state.encounter === null
        ? state
        : {
            ...state,
            encounter: {
              ...state.encounter,
              state: "active",
              round_number: event.round_number,
              current_turn_index: event.turn_index,
              current_entity_uuid: event.entity_uuid,
            },
          };
    case "dnd.core.events.TurnEndEvent":
      return state.encounter === null
        ? state
        : {
            ...state,
            encounter: {
              ...state.encounter,
              round_number: event.round_number,
              current_turn_index: event.turn_index,
            },
          };
    case "dnd.core.events.RoundStartEvent":
    case "dnd.core.events.RoundEndEvent":
      return state.encounter === null
        ? state
        : {
            ...state,
            encounter: { ...state.encounter, round_number: event.round_number },
          };
    case "dnd.core.events.EncounterStartEvent":
      return state.encounter === null
        ? state
        : { ...state, encounter: { ...state.encounter, state: "active" } };
    case "dnd.core.events.EncounterEndEvent":
      return state.encounter === null
        ? state
        : {
            ...state,
            encounter: {
              ...state.encounter,
              state: "ended",
              current_entity_uuid: null,
            },
          };
    case "dnd.core.events.SpatialChangeEvent":
      return reduceSpatialChange(state, event);

    // These events either describe an attempt/roll, or their state mutation is
    // carried by a factual child event handled above. Keeping every generated
    // wire class explicit makes a newly added backend event fail compilation
    // until its replication behavior is deliberately classified.
    case "dnd.actions.AttackEvent":
    case "dnd.actions.ShoveEvent":
    case "dnd.actions.SpellEvent":
    case "dnd.blocks.base_item.ItemChargeConsumptionEvent":
    case "dnd.blocks.equipment.ArmorEquipEvent":
    case "dnd.blocks.equipment.ArmorUnequipEvent":
    case "dnd.blocks.equipment.ShieldEquipEvent":
    case "dnd.blocks.equipment.ShieldUnequipEvent":
    case "dnd.blocks.equipment.WeaponEquipEvent":
    case "dnd.blocks.equipment.WeaponUnequipEvent":
    case "dnd.core.base_actions.ActionEvent":
    case "dnd.core.events.AttackD20RollResultEvent":
    case "dnd.core.events.D20RollResultEvent":
    case "dnd.core.events.DamageRollResultEvent":
    case "dnd.core.events.DamageRolledEvent":
    case "dnd.core.events.DeathSaveEvent":
    case "dnd.core.events.DiceRollResultEvent":
    case "dnd.core.events.ExposedFlameEvent":
    case "dnd.core.events.FireExposureEvent":
    case "dnd.core.events.HealRollResultEvent":
    case "dnd.core.events.InstantDeathEvent":
    case "dnd.core.events.SavingThrowD20RollResultEvent":
    case "dnd.core.events.SavingThrowEvent":
    case "dnd.core.events.SensoryUpdateEvent":
    case "dnd.core.events.SkillCheckD20RollResultEvent":
    case "dnd.core.events.SkillCheckEvent":
    case "dnd.core.events.TakeDamageEvent":
    case "dnd.core.events.WindExposureEvent":
    case "dnd.spells.abjuration.CounterspellReactionEvent":
    case "dnd.core.events.Event":
      return state;
    default: {
      const unhandledEvent: never = event;
      return unhandledEvent;
    }
  }
}

function coordinateKey(position: readonly [number, number]): string {
  return `${position[0]},${position[1]}`;
}

function updateCoordinates(
  current: ReadonlyArray<readonly [number, number]>,
  added: ReadonlyArray<readonly [number, number]>,
  removed: ReadonlyArray<readonly [number, number]>,
): Array<[number, number]> {
  const values = new Map<string, [number, number]>();
  for (const position of current) {
    values.set(coordinateKey(position), [position[0], position[1]]);
  }
  for (const position of removed) {
    values.delete(coordinateKey(position));
  }
  for (const position of added) {
    values.set(coordinateKey(position), [position[0], position[1]]);
  }
  return [...values.values()];
}

function updateIds(
  current: ReadonlyArray<string>,
  added: ReadonlyArray<string>,
  removed: ReadonlyArray<string>,
): string[] {
  const values = new Set(current);
  removed.forEach((value) => values.delete(value));
  added.forEach((value) => values.add(value));
  return [...values];
}

export function reduceVisibility(
  visibility: APIVisibilityResponse,
  event: ServerEvent,
): APIVisibilityResponse {
  if (!terminalEffect(event) || event.wire_type !== "dnd.core.events.SensoryUpdateEvent") {
    return visibility;
  }
  const observer = visibility[event.observer_uuid];
  if (observer === undefined) {
    return visibility;
  }
  const updated: APIEntityVisibility = {
    ...observer,
    position: [event.observer_position[0], event.observer_position[1]],
    visible_cells: updateCoordinates(
      observer.visible_cells,
      event.visible_cells_added,
      event.visible_cells_removed,
    ),
    seen_cells: updateCoordinates(observer.seen_cells, event.seen_cells_added, []),
    visible_entities: updateIds(
      observer.visible_entities,
      Object.keys(event.visible_entities_added),
      Object.keys(event.visible_entities_removed),
    ),
    visible_objects: updateIds(
      observer.visible_objects,
      Object.keys(event.visible_objects_added),
      Object.keys(event.visible_objects_removed),
    ),
    sense_modes: event.sense_modes_changed && event.sense_modes !== null
      ? event.sense_modes
      : observer.sense_modes,
    effective_light_levels: event.effective_light_levels,
  };
  return { ...visibility, [event.observer_uuid]: updated };
}

export function reduceWorld(world: ReplicatedWorld, event: ServerEvent): ReplicatedWorld {
  const state = reduceGameState(world.state, event);
  const visibility = reduceVisibility(world.visibility, event);
  return state === world.state && visibility === world.visibility
    ? world
    : { state, visibility };
}
