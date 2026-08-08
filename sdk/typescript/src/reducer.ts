import type {
  APIEntitySummary,
  APITile,
  EntityVisualLoadout,
  SubjectiveEncounter,
  SubjectiveFloorObject,
  APITraversalConnector,
  SubjectivePerspective,
  SubjectiveReplicatedWorld,
  SubjectiveWorldPatch,
} from "./generated/contracts.generated.js";
import { ContractValidationError } from "./validation.js";

/** Apply one complete observation-frame patch transaction. */
export function reduceSubjectiveWorld(
  world: SubjectiveReplicatedWorld,
  patches: ReadonlyArray<SubjectiveWorldPatch>,
): SubjectiveReplicatedWorld {
  const entities = keyed(world.state.entities, (entity) => entity.uuid);
  const tiles = keyed(world.state.grid.tiles, tileKey);
  let connectors = world.state.grid.connectors;
  const floorObjects = keyed(world.state.floor_objects, (object) => object.uuid);
  const visibility = { ...world.visibility };
  const equipment = { ...world.equipment_by_entity };
  const visualLoadouts = { ...world.visual_loadout_by_entity };
  let encounter = world.state.encounter;

  for (const patch of patches) {
    assertSubjectiveWorldPatch(patch);
    switch (patch.kind) {
      case "entity_upsert":
        entities.set(patch.entity.uuid, patch.entity);
        break;
      case "entity_remove":
        entities.delete(patch.entity_uuid);
        delete equipment[patch.entity_uuid];
        delete visualLoadouts[patch.entity_uuid];
        break;
      case "tile_upsert":
        assertTileInsideGrid(patch.tile, world);
        tiles.set(tileKey(patch.tile), patch.tile);
        break;
      case "connector_set_replace":
        connectors = patch.connectors;
        break;
      case "floor_object_upsert":
        floorObjects.set(patch.object.uuid, patch.object);
        break;
      case "floor_object_remove":
        floorObjects.delete(patch.object_uuid);
        break;
      case "encounter_replace":
        encounter = patch.encounter;
        break;
      case "observer_visibility_replace":
        visibility[patch.observer_uuid] = patch.visibility;
        break;
      case "observer_visibility_remove":
        delete visibility[patch.observer_uuid];
        break;
      case "controlled_equipment_replace":
        equipment[patch.entity_uuid] = patch.equipment;
        break;
      case "visual_loadout_replace":
        visualLoadouts[patch.loadout.entity_uuid] = patch.loadout;
        break;
      case "door_state":
        applyDoorState(floorObjects, patch);
        break;
      default:
        assertNever(patch);
    }
  }

  const reduced = {
    state: {
      ...world.state,
      entities: [...entities.values()],
      grid: { ...world.state.grid, tiles: [...tiles.values()], connectors: [...connectors] },
      encounter,
      floor_objects: [...floorObjects.values()],
    },
    visibility,
    equipment_by_entity: equipment,
    visual_loadout_by_entity: visualLoadouts,
  };
  assertGridConnectorIntegrity(reduced, "$subjective.world.state.grid");
  return reduced;
}

/** Validate the cross-field invariants needed by every renderer seed. */
export function assertSubjectiveWorld(
  world: SubjectiveReplicatedWorld,
  perspective: SubjectivePerspective,
  path = "$subjective.world",
): void {
  const entities = uniqueValues(
    world.state.entities.map((entity) => entity.uuid),
    `${path}.state.entities`,
  );
  uniqueValues(
    world.state.floor_objects.map((object) => object.uuid),
    `${path}.state.floor_objects`,
  );
  world.state.floor_objects.forEach((object, index) => {
    assertSubjectiveFloorObject(object, `${path}.state.floor_objects[${index}]`);
  });
  if (world.state.encounter !== null) {
    assertSubjectiveEncounter(world.state.encounter, `${path}.state.encounter`);
  }
  uniqueValues(
    world.state.grid.tiles.map(tileKey),
    `${path}.state.grid.tiles`,
  );

  const controlled = uniqueValues(
    perspective.controlled_entity_uuids,
    "$subjective.perspective.controlled_entity_uuids",
  );
  const observers = uniqueValues(
    perspective.observer_entity_uuids,
    "$subjective.perspective.observer_entity_uuids",
  );
  if (observers.size === 0 || !observers.has(perspective.active_observer_uuid)) {
    throw new ContractValidationError(
      "$subjective.perspective.active_observer_uuid",
      "active observer must belong to a non-empty observer union",
    );
  }
  if (perspective.kind === "controlled_knowledge_union") {
    if (controlled.size === 0 || !sameSet(controlled, observers)) {
      throw new ContractValidationError(
        "$subjective.perspective",
        "controlled knowledge requires identical non-empty controlled and observer sets",
      );
    }
  } else if (controlled.size !== 0) {
    throw new ContractValidationError(
      "$subjective.perspective.controlled_entity_uuids",
      "spectator knowledge cannot control entities",
    );
  }
  if (!isSubset(controlled, entities) || !isSubset(observers, entities)) {
    throw new ContractValidationError(
      path,
      "controlled and observer entities must exist in projected state",
    );
  }
  assertExactKeys(world.visibility, observers, `${path}.visibility`);
  assertExactKeys(world.equipment_by_entity, controlled, `${path}.equipment_by_entity`);
  assertExactKeys(world.visual_loadout_by_entity, entities, `${path}.visual_loadout_by_entity`);

  for (const [entityUuid, loadout] of Object.entries(world.visual_loadout_by_entity)) {
    if (loadout.entity_uuid !== entityUuid) {
      throw new ContractValidationError(
        `${path}.visual_loadout_by_entity.${entityUuid}.entity_uuid`,
        "visual loadout key and entity UUID differ",
      );
    }
    assertEntityVisualLoadout(loadout, `${path}.visual_loadout_by_entity.${entityUuid}`);
  }

  const grid = world.state.grid;
  if (grid.min_x > grid.max_x || grid.min_y > grid.max_y) {
    throw new ContractValidationError(`${path}.state.grid`, "grid bounds are reversed");
  }
  for (const tile of grid.tiles) {
    assertTileInsideGrid(tile, world, `${path}.state.grid.tiles`);
  }
  assertGridConnectorIntegrity(world, `${path}.state.grid`);
  for (const [observerUuid, row] of Object.entries(world.visibility)) {
    const visibleKeys = new Set(row.visible_cells.map(([x, y]) => `${x},${y}`));
    assertExactKeys(
      row.effective_light_levels,
      visibleKeys,
      `${path}.visibility.${observerUuid}.effective_light_levels`,
    );
  }
}

/** Validate nested model semantics before a frame is accepted or reduced. */
export function assertSubjectiveWorldPatch(
  patch: SubjectiveWorldPatch,
  path = "$subjective.patch",
): void {
  switch (patch.kind) {
    case "floor_object_upsert":
      assertSubjectiveFloorObject(patch.object, `${path}.object`);
      return;
    case "encounter_replace":
      if (patch.encounter !== null) assertSubjectiveEncounter(patch.encounter, `${path}.encounter`);
      return;
    case "observer_visibility_replace": {
      const visible = new Set(
        patch.visibility.visible_cells.map(([x, y]) => `${x},${y}`),
      );
      assertExactKeys(
        patch.visibility.effective_light_levels,
        visible,
        `${path}.visibility.effective_light_levels`,
      );
      return;
    }
    case "visual_loadout_replace":
      assertEntityVisualLoadout(patch.loadout, `${path}.loadout`);
      return;
    case "connector_set_replace":
      assertConnectorSetIdentity(patch.connectors, `${path}.connectors`);
      return;
    case "entity_upsert":
    case "entity_remove":
    case "tile_upsert":
    case "floor_object_remove":
    case "observer_visibility_remove":
    case "controlled_equipment_replace":
    case "door_state":
      return;
    default:
      assertNever(patch);
  }
}

function assertConnectorSetIdentity(
  connectors: ReadonlyArray<APITraversalConnector>,
  path: string,
): void {
  uniqueValues(connectors.map((connector) => connector.uuid), `${path}.uuid`);
  uniqueValues(
    connectors.map((connector) => connector.authored_id),
    `${path}.authored_id`,
  );
}

function assertGridConnectorIntegrity(
  world: SubjectiveReplicatedWorld,
  path: string,
): void {
  const grid = world.state.grid;
  assertConnectorSetIdentity(grid.connectors, `${path}.connectors`);
  const tiles = keyed(grid.tiles, tileKey);
  const currentlyVisibleCells = new Set(
    Object.values(world.visibility).flatMap((row) => (
      row.visible_cells.map(([x, y]) => `${x},${y}`)
    )),
  );
  grid.tiles.forEach((tile, tileIndex) => {
    const isCurrentlyVisible = currentlyVisibleCells.has(tileKey(tile));
    if (tile.visible !== isCurrentlyVisible) {
      throw new ContractValidationError(
        `${path}.tiles[${tileIndex}].visible`,
        "tile visibility must equal the current observer-union visibility",
      );
    }
  });
  for (const visibleCell of currentlyVisibleCells) {
    const tile = tiles.get(visibleCell);
    if (tile === undefined || !tile.visible) {
      throw new ContractValidationError(
        `${path}.tiles`,
        "every current observer-union cell requires a projected visible tile",
      );
    }
  }
  grid.connectors.forEach((connector, connectorIndex) => {
    if (
      connector.endpoints[0].position[0] === connector.endpoints[1].position[0]
      && connector.endpoints[0].position[1] === connector.endpoints[1].position[1]
    ) {
      throw new ContractValidationError(
        `${path}.connectors[${connectorIndex}].endpoints`,
        "connector endpoints must occupy two distinct positions",
      );
    }
    connector.endpoints.forEach((endpoint, endpointIndex) => {
      const endpointPath = (
        `${path}.connectors[${connectorIndex}].endpoints[${endpointIndex}]`
      );
      const [x, y] = endpoint.position;
      if (x < grid.min_x || x > grid.max_x || y < grid.min_y || y > grid.max_y) {
        throw new ContractValidationError(
          `${endpointPath}.position`,
          "connector endpoint lies outside projected grid bounds",
        );
      }
      const tile = tiles.get(`${x},${y}`);
      if (tile === undefined) {
        throw new ContractValidationError(
          `${endpointPath}.position`,
          "connector endpoint requires an authorized projected support tile",
        );
      }
      if (!tile.visible) {
        throw new ContractValidationError(
          `${endpointPath}.position`,
          "connector endpoint requires a currently visible support tile",
        );
      }
      if (!currentlyVisibleCells.has(`${x},${y}`)) {
        throw new ContractValidationError(
          `${endpointPath}.position`,
          "connector endpoint requires current observer-union authorization",
        );
      }
      if (endpoint.elevation_feet !== tile.elevation_steps * 5) {
        throw new ContractValidationError(
          `${endpointPath}.elevation_feet`,
          "connector endpoint elevation differs from its projected support tile",
        );
      }
      // APITile intentionally exposes no objective tile UUID. The endpoint's
      // support_tile_uuid therefore remains an opaque identity carried from
      // the server; coordinate authorization and elevation agreement are the
      // complete client-enforceable relation.
    });
  });
}

export function assertSubjectiveFloorObject(
  object: SubjectiveFloorObject,
  path = "$subjective.floor_object",
): void {
  uniqueValues(object.blocked_directions, `${path}.blocked_directions`);
  uniqueValues(object.blocked_channels, `${path}.blocked_channels`);
  const hasDirections = object.blocked_directions.length > 0;
  const hasChannels = object.blocked_channels.length > 0;
  if (hasDirections !== hasChannels) {
    throw new ContractValidationError(path, "directional state requires directions and channels together");
  }
  if (object.object_kind === "directional_structure") {
    if (!hasDirections) {
      throw new ContractValidationError(path, "directional structure requires blocking state");
    }
  } else if (object.object_kind !== "door" && hasDirections) {
    throw new ContractValidationError(path, "directional state belongs only to doors and structures");
  }
  if (object.object_kind === "door") {
    if (object.is_open === null) {
      throw new ContractValidationError(`${path}.is_open`, "door requires explicit open state");
    }
  } else if (object.is_open !== null) {
    throw new ContractValidationError(`${path}.is_open`, "open state belongs only to doors");
  }
  const radii = [
    object.very_bright_radius_feet,
    object.bright_radius_feet,
    object.dim_radius_feet,
  ];
  if (object.object_kind === "light_source") {
    if (object.is_lit === null || radii.some((radius) => radius === null)) {
      throw new ContractValidationError(path, "light source requires lit state and all radii");
    }
  } else if (object.is_lit !== null || radii.some((radius) => radius !== null)) {
    throw new ContractValidationError(path, "light state belongs only to light sources");
  }
}

export function assertSubjectiveEncounter(
  encounter: SubjectiveEncounter,
  path = "$subjective.encounter",
): void {
  const combatants = encounter.initiative_order.map((combatant) => combatant.uuid);
  uniqueValues(combatants, `${path}.initiative_order`);
  if (encounter.current_entity_uuid === null) {
    if (encounter.current_turn_index !== null) {
      throw new ContractValidationError(
        `${path}.current_turn_index`,
        "hidden current combatant cannot expose a turn index",
      );
    }
    return;
  }
  const expected = combatants.indexOf(encounter.current_entity_uuid);
  if (expected < 0 || encounter.current_turn_index !== expected) {
    throw new ContractValidationError(path, "current turn must address the visible current combatant");
  }
}

function assertEntityVisualLoadout(loadout: EntityVisualLoadout, path: string): void {
  uniqueValues(loadout.layers.map((layer) => layer.slot), `${path}.layers`);
}

function applyDoorState(
  objects: Map<string, SubjectiveFloorObject>,
  patch: Extract<SubjectiveWorldPatch, { readonly kind: "door_state" }>,
): void {
  const existing = objects.get(patch.object_uuid);
  if (existing === undefined || existing.object_kind !== "door") {
    throw new ContractValidationError(
      "$subjective.patch.door_state.object_uuid",
      "door-state patch must address an existing projected door",
    );
  }
  if (existing.position[0] !== patch.position[0] || existing.position[1] !== patch.position[1]) {
    throw new ContractValidationError(
      "$subjective.patch.door_state.position",
      "door-state patch position differs from the projected door",
    );
  }
  objects.set(patch.object_uuid, {
    ...existing,
    is_open: patch.is_open,
    blocks_movement: patch.blocks_movement,
    blocks_vision: patch.blocks_vision,
  });
}

function assertTileInsideGrid(
  tile: APITile,
  world: SubjectiveReplicatedWorld,
  path = "$subjective.patch.tile_upsert.tile",
): void {
  const grid = world.state.grid;
  if (tile.x < grid.min_x || tile.x > grid.max_x || tile.y < grid.min_y || tile.y > grid.max_y) {
    throw new ContractValidationError(path, "tile lies outside projected grid bounds");
  }
}

function keyed<Value>(
  values: ReadonlyArray<Value>,
  key: (value: Value) => string,
): Map<string, Value> {
  return new Map(values.map((value) => [key(value), value]));
}

function tileKey(tile: Pick<APITile, "x" | "y">): string {
  return `${tile.x},${tile.y}`;
}

function uniqueValues(values: ReadonlyArray<string>, path: string): Set<string> {
  const result = new Set(values);
  if (result.size !== values.length) {
    throw new ContractValidationError(path, "values must be unique");
  }
  return result;
}

function assertExactKeys(
  record: Readonly<Record<string, unknown>>,
  expected: ReadonlySet<string>,
  path: string,
): void {
  const actual = new Set(Object.keys(record));
  if (!sameSet(actual, expected)) {
    throw new ContractValidationError(path, "record keys do not match the required entity set");
  }
}

function sameSet(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
  return left.size === right.size && isSubset(left, right);
}

function isSubset(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
  for (const value of left) {
    if (!right.has(value)) return false;
  }
  return true;
}

function assertNever(value: never): never {
  throw new ContractValidationError("$subjective.patch.kind", `unsupported patch ${String(value)}`);
}

export type { APIEntitySummary, SubjectiveReplicatedWorld };
