import type {
  APICombatant,
  APIEncounter,
  APIEntitySummary,
  APIEntityVisibility,
  APIEquipmentOverview,
  APIFloorObject,
  APIGrid,
  APIItemSummary,
  APITile,
  APITraversalConnector,
  APIVisibilityResponse,
  EntityVisualLoadout,
  FloorObjectBlockingChannel,
  FloorObjectDirection,
  FloorObjectProjectionKind,
  ItemPresentationKind,
  ObjectiveReplicatedWorld,
  PerspectiveKind,
  SafeContentPresentationRef,
  SenseMode,
  StructuralEdgeAppearance,
  StructuralEdgeKind,
  SubjectiveCombatant,
  SubjectiveEncounter,
  SubjectiveFloorObject,
  SubjectivePerspective,
  SubjectiveReplicatedWorld,
  VisualEquipmentLayer,
  VisualLoadoutSlot,
} from "./generated/contracts.generated.js";
import {
  assertGridConnectorStructure,
  assertSubjectiveWorld,
} from "./reducer.js";
import { ContractValidationError, decodeModel } from "./validation.js";

export type RenderProjection = "subjective" | "objective";
export type RenderPerspectiveKind = PerspectiveKind | "objective";

export interface RenderPerspective {
  readonly kind: RenderPerspectiveKind;
  readonly controlled_entity_uuids: Array<string>;
  readonly observer_entity_uuids: Array<string>;
  readonly active_observer_uuid: string | null;
}

export interface RenderObserver {
  readonly uuid: string;
  readonly name: string;
  readonly position: [number, number];
  readonly sense_modes: Array<SenseMode>;
}

/**
 * Canonical knowledge-union mask for rendering.
 *
 * `active_observer_uuid` is deliberately absent: changing UI focus must never
 * narrow these unioned facts.
 */
export interface RenderKnowledgeUnion {
  readonly observers: Array<RenderObserver>;
  readonly visible_cells: Array<[number, number]>;
  readonly seen_cells: Array<[number, number]>;
  readonly visible_entity_uuids: Array<string>;
  readonly visible_object_uuids: Array<string>;
  readonly effective_light_levels: Record<string, number>;
}

export type RenderOwnedEdgeDirection = "north" | "east";
export type RenderStructuralEdgeKind = StructuralEdgeKind | "generic";

declare const renderStructuralEdgeKeyBrand: unique symbol;
export type RenderStructuralEdgeKey = string & {
  readonly [renderStructuralEdgeKeyBrand]: true;
};

export interface RenderStructuralEdge {
  readonly edge_key: RenderStructuralEdgeKey;
  readonly position: [number, number];
  readonly direction: RenderOwnedEdgeDirection;
  readonly kind: RenderStructuralEdgeKind;
  readonly is_open: boolean | null;
  readonly blocked_channels: Array<FloorObjectBlockingChannel>;
}

export interface RenderTraversalConnectorEndpoint {
  readonly position: readonly [number, number];
  readonly elevation_feet: number;
}

export interface RenderTraversalConnector {
  readonly uuid: string;
  readonly authored_id: string;
  readonly kind: APITraversalConnector["kind"];
  readonly presentation_key: string;
  readonly endpoints: readonly [
    RenderTraversalConnectorEndpoint,
    RenderTraversalConnectorEndpoint,
  ];
  readonly enabled: boolean;
}

/**
 * Projection-neutral floor-object row.
 *
 * Subjective rows are copied only from their closed flattened contract.
 * Objective rows adapt the equivalent concrete state fields retained in the
 * diagnostic `state` record.
 */
export interface RenderFloorObject {
  readonly uuid: string;
  readonly name: string;
  readonly position: [number, number];
  readonly map_char: string;
  readonly object_kind: FloorObjectProjectionKind;
  readonly safe_presentation_ref: SafeContentPresentationRef | null;
  readonly visual_item_name: string;
  readonly visual_variant_id: string | null;
  readonly blocks_movement: boolean | null;
  readonly blocks_vision: boolean | null;
  readonly is_open: boolean | null;
  readonly blocked_directions: Array<FloorObjectDirection>;
  readonly blocked_channels: Array<FloorObjectBlockingChannel>;
  readonly is_lit: boolean | null;
  readonly very_bright_radius_feet: number | null;
  readonly bright_radius_feet: number | null;
  readonly dim_radius_feet: number | null;
}

export interface RenderCombatant {
  readonly uuid: string;
  readonly name: string;
  readonly initiative: number;
  readonly life_state: APICombatant["life_state"];
}

export interface RenderEncounter {
  readonly uuid: string;
  readonly name: string;
  readonly state: string;
  readonly round_number: number;
  readonly current_turn_index: number | null;
  readonly current_entity_uuid: string | null;
  readonly initiative_order: Array<RenderCombatant>;
}

export interface RenderGrid {
  readonly min_x: number;
  readonly min_y: number;
  readonly max_x: number;
  readonly max_y: number;
  readonly tiles: Array<APITile>;
  readonly connectors: ReadonlyArray<RenderTraversalConnector>;
  readonly structural_edges: Array<RenderStructuralEdge>;
}

export interface RenderGameState {
  readonly grid: RenderGrid;
  readonly entities: Array<APIEntitySummary>;
  readonly encounter: RenderEncounter | null;
  readonly floor_objects: Array<RenderFloorObject>;
}

export interface RenderEquipment {
  /**
   * Subjective worlds contain detail only for controlled actors. Objective
   * diagnostics contain the complete authorized diagnostic rows.
   */
  readonly detail_scope: "controlled" | "objective";
  readonly details_by_entity: Record<string, APIEquipmentOverview>;
  /** Safe appearance-only rows, independent from detailed equipment access. */
  readonly visual_loadout_by_entity: Record<string, EntityVisualLoadout>;
}

/** One deterministic, frontend-neutral input to a renderer. */
export interface ReplicatedRenderWorld {
  readonly projection: RenderProjection;
  readonly perspective: RenderPerspective;
  readonly state: RenderGameState;
  readonly knowledge: RenderKnowledgeUnion;
  readonly equipment: RenderEquipment;
}

export interface ObjectiveRenderProjectionOptions {
  /**
   * Objective diagnostics default to all observer rows. Tests may select the
   * same observer set as a subjective perspective without mutating the world.
   */
  readonly observer_entity_uuids?: ReadonlyArray<string>;
  readonly active_observer_uuid?: string | null;
}

const DIRECTIONS: ReadonlyArray<FloorObjectDirection> = [
  "north",
  "east",
  "south",
  "west",
];
const OWNED_EDGE_DIRECTIONS: ReadonlyArray<RenderOwnedEdgeDirection> = [
  "north",
  "east",
];
const CHANNELS: ReadonlyArray<FloorObjectBlockingChannel> = [
  "movement",
  "vision",
  "light",
  "propagation",
];
const VISUAL_SLOTS: ReadonlyArray<VisualLoadoutSlot> = [
  "weapon_melee_main",
  "weapon_melee_off",
  "weapon_ranged_main",
  "weapon_ranged_off",
  "helmet",
  "body_armor",
  "gauntlets",
  "greaves",
  "boots",
  "amulet",
  "cloak",
  "ring_left",
  "ring_right",
];
const FLOOR_OBJECT_KINDS: ReadonlySet<string> = new Set<FloorObjectProjectionKind>([
  "item",
  "interactable",
  "container",
  "hazard",
  "door",
  "directional_structure",
  "light_source",
  "generic",
]);
const VISUAL_SLOT_SET: ReadonlySet<string> = new Set(VISUAL_SLOTS);
const DIRECTION_SET: ReadonlySet<string> = new Set(DIRECTIONS);
const CHANNEL_SET: ReadonlySet<string> = new Set(CHANNELS);
const ITEM_KINDS: ReadonlySet<string> = new Set<ItemPresentationKind>([
  "item",
  "usable",
  "weapon",
  "armor",
  "shield",
]);

/** Build the only render projection needed by a subjective player client. */
export function projectSubjectiveRenderWorld(
  world: SubjectiveReplicatedWorld,
  perspective: SubjectivePerspective,
): ReplicatedRenderWorld {
  decodeModel("SubjectiveReplicatedWorld", world);
  decodeModel("SubjectivePerspective", perspective);
  assertSubjectiveWorld(world, perspective);

  const observerUuids = sortedUnique(
    perspective.observer_entity_uuids,
    "$render.subjective.observer_entity_uuids",
  );
  return {
    projection: "subjective",
    perspective: {
      kind: perspective.kind,
      controlled_entity_uuids: sortedUnique(
        perspective.controlled_entity_uuids,
        "$render.subjective.controlled_entity_uuids",
      ),
      observer_entity_uuids: observerUuids,
      active_observer_uuid: perspective.active_observer_uuid,
    },
    state: {
      grid: projectGrid(world.state.grid),
      entities: [...world.state.entities].sort(compareUuid),
      encounter: projectEncounter(world.state.encounter),
      floor_objects: world.state.floor_objects
        .map(projectSubjectiveFloorObject)
        .sort(compareUuid),
    },
    knowledge: mergeObserverVisibility(
      world.visibility,
      observerUuids,
      perspective.active_observer_uuid,
    ),
    equipment: {
      detail_scope: "controlled",
      details_by_entity: projectEquipmentDetails(world.equipment_by_entity),
      visual_loadout_by_entity: projectVisualLoadouts(
        world.visual_loadout_by_entity,
      ),
    },
  };
}

/** Normalize an objective diagnostic world for debug UI and parity oracles. */
export function projectObjectiveRenderWorld(
  world: ObjectiveReplicatedWorld,
  options: ObjectiveRenderProjectionOptions = {},
): ReplicatedRenderWorld {
  decodeModel("ObjectiveReplicatedWorld", world);
  assertObjectiveWorld(world);

  const requestedObservers = options.observer_entity_uuids
    ?? Object.keys(world.visibility);
  const observerUuids = sortedUnique(
    requestedObservers,
    "$render.objective.observer_entity_uuids",
  );
  const activeObserverUuid = options.active_observer_uuid ?? null;
  const details = projectEquipmentDetails(world.equipment_by_entity);
  const visualLoadouts: Record<string, EntityVisualLoadout> = {};
  for (const entity of [...world.state.entities].sort(compareUuid)) {
    visualLoadouts[entity.uuid] = deriveVisualLoadout(
      entity.uuid,
      world.equipment_by_entity[entity.uuid],
    );
  }

  return {
    projection: "objective",
    perspective: {
      kind: "objective",
      controlled_entity_uuids: [],
      observer_entity_uuids: observerUuids,
      active_observer_uuid: activeObserverUuid,
    },
    state: {
      grid: projectGrid(world.state.grid),
      entities: [...world.state.entities].sort(compareUuid),
      encounter: projectEncounter(world.state.encounter),
      floor_objects: world.state.floor_objects
        .map(projectObjectiveFloorObject)
        .sort(compareUuid),
    },
    knowledge: mergeObserverVisibility(
      world.visibility,
      observerUuids,
      activeObserverUuid,
    ),
    equipment: {
      detail_scope: "objective",
      details_by_entity: details,
      visual_loadout_by_entity: visualLoadouts,
    },
  };
}

/**
 * Union every selected observer row. Shared-cell effective light uses the
 * brightest perceived value (the maximum engine LightLevel integer), making
 * the result independent of observer ordering.
 */
export function mergeObserverVisibility(
  visibility: APIVisibilityResponse,
  observerEntityUuids: ReadonlyArray<string>,
  activeObserverUuid: string | null = null,
): RenderKnowledgeUnion {
  const observerUuids = sortedUnique(
    observerEntityUuids,
    "$render.visibility.observer_entity_uuids",
  );
  if (
    activeObserverUuid !== null
    && !observerUuids.includes(activeObserverUuid)
  ) {
    throw new ContractValidationError(
      "$render.visibility.active_observer_uuid",
      "active observer must belong to the selected observer union",
    );
  }

  const observers: RenderObserver[] = [];
  const visibleCells = new Map<string, [number, number]>();
  const seenCells = new Map<string, [number, number]>();
  const visibleEntities = new Set<string>();
  const visibleObjects = new Set<string>();
  const effectiveLight = new Map<string, number>();

  for (const observerUuid of observerUuids) {
    const row = visibility[observerUuid];
    if (row === undefined) {
      throw new ContractValidationError(
        `$render.visibility.${observerUuid}`,
        "selected observer has no visibility row",
      );
    }
    assertVisibilityLightCoverage(row, `$render.visibility.${observerUuid}`);
    observers.push({
      uuid: observerUuid,
      name: row.name,
      position: copyPosition(row.position),
      sense_modes: [...row.sense_modes].sort(compareSenseMode),
    });
    for (const cell of row.visible_cells) {
      const key = cellKey(cell);
      visibleCells.set(key, copyPosition(cell));
      const light = row.effective_light_levels[key];
      if (light === undefined) {
        throw new ContractValidationError(
          `$render.visibility.${observerUuid}.effective_light_levels.${key}`,
          "visible cell has no effective-light value",
        );
      }
      const previous = effectiveLight.get(key);
      if (previous === undefined || light > previous) {
        effectiveLight.set(key, light);
      }
    }
    for (const cell of row.seen_cells) {
      seenCells.set(cellKey(cell), copyPosition(cell));
    }
    row.visible_entities.forEach((uuid) => visibleEntities.add(uuid));
    row.visible_objects.forEach((uuid) => visibleObjects.add(uuid));
  }

  const sortedVisibleCells = [...visibleCells.values()].sort(comparePosition);
  const sortedLight: Record<string, number> = {};
  for (const position of sortedVisibleCells) {
    const key = cellKey(position);
    const value = effectiveLight.get(key);
    if (value === undefined) {
      throw new ContractValidationError(
        `$render.visibility.effective_light_levels.${key}`,
        "unioned visible cell has no effective-light value",
      );
    }
    sortedLight[key] = value;
  }

  return {
    observers,
    visible_cells: sortedVisibleCells,
    seen_cells: [...seenCells.values()].sort(comparePosition),
    visible_entity_uuids: [...visibleEntities].sort(compareString),
    visible_object_uuids: [...visibleObjects].sort(compareString),
    effective_light_levels: sortedLight,
  };
}

/**
 * Normalize tile-local halves into deterministic undirected structural edges.
 *
 * South and west halves are re-owned by the adjacent canonical anchor as north
 * and east respectively. A visible structural appearance supersedes a
 * remembered reciprocal half, and any known structure suppresses a generic
 * blocker on the same physical edge.
 */
export function projectStructuralEdges(
  tiles: ReadonlyArray<APITile>,
): Array<RenderStructuralEdge> {
  const candidates = new Map<RenderStructuralEdgeKey, {
    readonly owner: CanonicalEdgeOwner;
    readonly rows: Array<StructuralEdgeCandidate>;
  }>();
  for (const tile of [...tiles].sort(compareTile)) {
    for (const direction of DIRECTIONS) {
      const blockedChannels = CHANNELS.filter((channel) => (
        tileBlocks(tile, channel, direction)
      ));
      const appearance = tile.directional_structural_edges[direction];
      if (appearance !== null) {
        assertStructuralEdgeAppearance(
          appearance,
          `$render.tile[${tile.x},${tile.y}].directional_structural_edges.${direction}`,
        );
      }
      if (blockedChannels.length === 0 && appearance === null) continue;
      const owned = canonicalEdgeOwner([tile.x, tile.y], direction);
      const key = canonicalRenderStructuralEdgeKey(
        owned.position,
        owned.direction,
      );
      const group = candidates.get(key) ?? { owner: owned, rows: [] };
      group.rows.push({
        source_visible: tile.visible,
        appearance,
        blocked_channels: blockedChannels,
      });
      candidates.set(key, group);
    }
  }
  const edges: RenderStructuralEdge[] = [];
  for (const [key, group] of candidates) {
    edges.push(mergeStructuralEdge(key, group.owner, group.rows));
  }
  return edges.sort(compareStructuralEdge);
}

/** Return the sole stable identity for one reciprocal physical boundary. */
export function canonicalRenderStructuralEdgeKey(
  position: readonly [number, number],
  direction: FloorObjectDirection,
): RenderStructuralEdgeKey {
  const owner = canonicalEdgeOwner(position, direction);
  const key = `edge:${owner.position[0]},${owner.position[1]}:${owner.direction}`;
  return key as RenderStructuralEdgeKey;
}

/** Project the privacy-safe connector field subset in deterministic order. */
export function projectTraversalConnectors(
  connectors: ReadonlyArray<APITraversalConnector>,
): Array<RenderTraversalConnector> {
  return connectors.map((connector) => ({
    uuid: connector.uuid,
    authored_id: connector.authored_id,
    kind: connector.kind,
    presentation_key: connector.presentation_key,
    endpoints: [
      {
        position: copyPosition(connector.endpoints[0].position),
        elevation_feet: connector.endpoints[0].elevation_feet,
      },
      {
        position: copyPosition(connector.endpoints[1].position),
        elevation_feet: connector.endpoints[1].elevation_feet,
      },
    ] as const,
    enabled: connector.enabled,
  })).sort((left, right) => (
    compareString(left.authored_id, right.authored_id)
    || compareString(left.uuid, right.uuid)
  ));
}

/** Derive the safe appearance layer used by the objective debug projection. */
export function deriveVisualLoadout(
  entityUuid: string,
  equipment: APIEquipmentOverview | undefined,
): EntityVisualLoadout {
  const layers: VisualEquipmentLayer[] = [];
  for (const slot of equipment?.slots ?? []) {
    if (slot.item === null || !VISUAL_SLOT_SET.has(slot.slot)) continue;
    const item = slot.item;
    layers.push({
      slot: slot.slot as VisualLoadoutSlot,
      item_kind: ITEM_KINDS.has(item.item_type)
        ? item.item_type as ItemPresentationKind
        : "item",
      safe_presentation_ref: item.safe_presentation_ref,
      visual_item_name: item.visual_item_name,
      visual_variant_id: item.visual_variant_id,
      equipped_visual_policy: item.equipped_visual_policy,
    });
  }
  layers.sort(compareVisualLayer);
  return {
    entity_uuid: entityUuid,
    active_weapon_set: (
      equipment === undefined ? "none" : equipment.active_weapon_set
    ),
    layers,
  };
}

function projectGrid(grid: APIGrid): RenderGrid {
  assertGridConnectorStructure(grid);
  const tiles = [...grid.tiles].sort(compareTile);
  return {
    min_x: grid.min_x,
    min_y: grid.min_y,
    max_x: grid.max_x,
    max_y: grid.max_y,
    tiles,
    connectors: projectTraversalConnectors(grid.connectors),
    structural_edges: projectStructuralEdges(tiles),
  };
}

function projectEncounter(
  encounter: APIEncounter | SubjectiveEncounter | null,
): RenderEncounter | null {
  if (encounter === null) return null;
  return {
    uuid: encounter.uuid,
    name: encounter.name,
    state: encounter.state,
    round_number: encounter.round_number,
    current_turn_index: encounter.current_turn_index,
    current_entity_uuid: encounter.current_entity_uuid,
    initiative_order: encounter.initiative_order.map(projectCombatant),
  };
}

function projectCombatant(
  combatant: APICombatant | SubjectiveCombatant,
): RenderCombatant {
  return {
    uuid: combatant.uuid,
    name: combatant.name,
    initiative: combatant.initiative,
    life_state: combatant.life_state,
  };
}

function projectSubjectiveFloorObject(
  object: SubjectiveFloorObject,
): RenderFloorObject {
  return {
    uuid: object.uuid,
    name: object.name,
    position: copyPosition(object.position),
    map_char: object.map_char,
    object_kind: object.object_kind,
    safe_presentation_ref: object.safe_presentation_ref,
    visual_item_name: object.visual_item_name,
    visual_variant_id: object.visual_variant_id,
    blocks_movement: object.blocks_movement,
    blocks_vision: object.blocks_vision,
    is_open: object.is_open,
    blocked_directions: sortDirections(object.blocked_directions),
    blocked_channels: sortChannels(object.blocked_channels),
    is_lit: object.is_lit,
    very_bright_radius_feet: object.very_bright_radius_feet,
    bright_radius_feet: object.bright_radius_feet,
    dim_radius_feet: object.dim_radius_feet,
  };
}

function projectObjectiveFloorObject(object: APIFloorObject): RenderFloorObject {
  const state = object.state;
  const directions = readEnumArray(
    state.blocked_directions,
    DIRECTION_SET,
    "$render.objective.floor_object.blocked_directions",
  ) as Array<FloorObjectDirection>;
  const channels = readEnumArray(
    state.blocked_channels,
    CHANNEL_SET,
    "$render.objective.floor_object.blocked_channels",
  ) as Array<FloorObjectBlockingChannel>;
  return {
    uuid: object.uuid,
    name: object.name,
    position: copyPosition(object.position),
    map_char: object.map_char,
    object_kind: objectiveObjectKind(state, directions, channels),
    safe_presentation_ref: readSafePresentationRef(
      state.safe_presentation_ref,
    ),
    visual_item_name: readString(state.visual_item_name) ?? object.name,
    visual_variant_id: readString(state.visual_variant_id),
    blocks_movement: readBoolean(state.blocks_movement),
    blocks_vision: (
      readBoolean(state.blocks_vision)
      ?? readBoolean(state.blocks_vision_field)
    ),
    is_open: readBoolean(state.is_open),
    blocked_directions: sortDirections(directions),
    blocked_channels: sortChannels(channels),
    is_lit: readBoolean(state.is_lit),
    very_bright_radius_feet: readNumber(state.very_bright_radius_feet),
    bright_radius_feet: readNumber(state.bright_radius_feet),
    dim_radius_feet: readNumber(state.dim_radius_feet),
  };
}

function objectiveObjectKind(
  state: APIFloorObject["state"],
  directions: ReadonlyArray<FloorObjectDirection>,
  channels: ReadonlyArray<FloorObjectBlockingChannel>,
): FloorObjectProjectionKind {
  const explicit = readString(state.object_kind);
  if (explicit !== null && FLOOR_OBJECT_KINDS.has(explicit)) {
    return explicit as FloorObjectProjectionKind;
  }
  if (readBoolean(state.is_open) !== null) return "door";
  if (
    readBoolean(state.is_lit) !== null
    && readNumber(state.very_bright_radius_feet) !== null
    && readNumber(state.bright_radius_feet) !== null
    && readNumber(state.dim_radius_feet) !== null
  ) {
    return "light_source";
  }
  if (directions.length > 0 && channels.length > 0) {
    return "directional_structure";
  }
  if (readBoolean(state.is_container) === true) return "container";
  if (readStringArray(state.tags).includes("hazard")) return "hazard";
  const isUsable = readBoolean(state.is_usable) === true;
  const isPickable = readBoolean(state.is_pickable) === true;
  if (isUsable && !isPickable) return "interactable";
  if (isPickable) return "item";
  return "generic";
}

function projectEquipmentDetails(
  details: Readonly<Record<string, APIEquipmentOverview>>,
): Record<string, APIEquipmentOverview> {
  const result: Record<string, APIEquipmentOverview> = {};
  for (const entityUuid of Object.keys(details).sort(compareString)) {
    const equipment = details[entityUuid];
    if (equipment === undefined) continue;
    result[entityUuid] = {
      slots: [...equipment.slots].sort((left, right) => (
        compareVisualSlot(left.slot, right.slot)
      )),
      active_weapon_set: equipment.active_weapon_set,
      ac: equipment.ac,
      inventory: [...equipment.inventory].sort(compareUuid),
    };
  }
  return result;
}

function projectVisualLoadouts(
  loadouts: Readonly<Record<string, EntityVisualLoadout>>,
): Record<string, EntityVisualLoadout> {
  const result: Record<string, EntityVisualLoadout> = {};
  for (const entityUuid of Object.keys(loadouts).sort(compareString)) {
    const loadout = loadouts[entityUuid];
    if (loadout === undefined) continue;
    result[entityUuid] = {
      entity_uuid: loadout.entity_uuid,
      active_weapon_set: loadout.active_weapon_set,
      layers: [...loadout.layers].sort(compareVisualLayer),
    };
  }
  return result;
}

function assertObjectiveWorld(world: ObjectiveReplicatedWorld): void {
  const grid = world.state.grid;
  if (grid.min_x > grid.max_x || grid.min_y > grid.max_y) {
    throw new ContractValidationError(
      "$render.objective.state.grid",
      "grid bounds are reversed",
    );
  }
  const tileKeys = new Set<string>();
  for (const tile of grid.tiles) {
    const key = `${tile.x},${tile.y}`;
    if (tileKeys.has(key)) {
      throw new ContractValidationError(
        "$render.objective.state.grid.tiles",
        "grid tile positions must be unique",
      );
    }
    tileKeys.add(key);
    if (
      tile.x < grid.min_x
      || tile.x > grid.max_x
      || tile.y < grid.min_y
      || tile.y > grid.max_y
    ) {
      throw new ContractValidationError(
        "$render.objective.state.grid.tiles",
        "grid tile lies outside declared bounds",
      );
    }
  }
  const entityUuids = new Set<string>();
  for (const entity of world.state.entities) {
    if (entityUuids.has(entity.uuid)) {
      throw new ContractValidationError(
        "$render.objective.state.entities",
        "entity UUIDs must be unique",
      );
    }
    entityUuids.add(entity.uuid);
  }
  const objectUuids = new Set<string>();
  for (const object of world.state.floor_objects) {
    if (objectUuids.has(object.uuid)) {
      throw new ContractValidationError(
        "$render.objective.state.floor_objects",
        "floor-object UUIDs must be unique",
      );
    }
    objectUuids.add(object.uuid);
  }
  for (const entityUuid of Object.keys(world.equipment_by_entity)) {
    if (!entityUuids.has(entityUuid)) {
      throw new ContractValidationError(
        "$render.objective.equipment_by_entity",
        "equipment row references an absent entity",
      );
    }
  }
}

function assertVisibilityLightCoverage(
  row: APIEntityVisibility,
  path: string,
): void {
  const visibleKeys = new Set(row.visible_cells.map(cellKey));
  const lightKeys = new Set(Object.keys(row.effective_light_levels));
  if (!sameSet(visibleKeys, lightKeys)) {
    throw new ContractValidationError(
      `${path}.effective_light_levels`,
      "effective-light keys must exactly cover visible cells",
    );
  }
}

interface StructuralEdgeCandidate {
  readonly source_visible: boolean;
  readonly appearance: StructuralEdgeAppearance | null;
  readonly blocked_channels: Array<FloorObjectBlockingChannel>;
}

interface CanonicalEdgeOwner {
  readonly position: [number, number];
  readonly direction: RenderOwnedEdgeDirection;
}

function canonicalEdgeOwner(
  position: readonly [number, number],
  direction: FloorObjectDirection,
): CanonicalEdgeOwner {
  switch (direction) {
    case "north":
      return { position: copyPosition(position), direction: "north" };
    case "east":
      return { position: copyPosition(position), direction: "east" };
    case "south":
      return { position: [position[0], position[1] - 1], direction: "north" };
    case "west":
      return { position: [position[0] - 1, position[1]], direction: "east" };
  }
}

function mergeStructuralEdge(
  edgeKey: RenderStructuralEdgeKey,
  owner: CanonicalEdgeOwner,
  candidates: ReadonlyArray<StructuralEdgeCandidate>,
): RenderStructuralEdge {
  const position = owner.position;
  const direction = owner.direction;
  const specific = candidates.filter((candidate) => candidate.appearance !== null);
  if (specific.length === 0) {
    return {
      edge_key: edgeKey,
      position,
      direction,
      kind: "generic",
      is_open: null,
      blocked_channels: mergedCandidateChannels(candidates),
    };
  }

  const visibleSpecific = specific.filter((candidate) => candidate.source_visible);
  const current = visibleSpecific.length > 0 ? visibleSpecific : specific;
  const appearances = new Map<string, StructuralEdgeAppearance>();
  for (const candidate of current) {
    const appearance = candidate.appearance;
    if (appearance === null) continue;
    appearances.set(
      `${appearance.kind}:${String(appearance.is_open)}`,
      appearance,
    );
  }
  if (appearances.size !== 1) {
    throw new ContractValidationError(
      `$render.structural_edges.${position[0]},${position[1]}:${direction}`,
      "equally current structural-edge appearances conflict",
    );
  }
  const appearance = appearances.values().next().value;
  if (appearance === undefined) {
    throw new ContractValidationError(
      "$render.structural_edges",
      "specific structural edge has no appearance",
    );
  }
  return {
    edge_key: edgeKey,
    position,
    direction,
    kind: appearance.kind,
    is_open: appearance.is_open,
    blocked_channels: appearance.kind === "door" && appearance.is_open
      ? []
      : mergedCandidateChannels(current),
  };
}

function mergedCandidateChannels(
  candidates: ReadonlyArray<StructuralEdgeCandidate>,
): Array<FloorObjectBlockingChannel> {
  const channels = new Set<FloorObjectBlockingChannel>();
  for (const candidate of candidates) {
    candidate.blocked_channels.forEach((channel) => channels.add(channel));
  }
  return CHANNELS.filter((channel) => channels.has(channel));
}

function assertStructuralEdgeAppearance(
  appearance: StructuralEdgeAppearance,
  path: string,
): void {
  if (appearance.kind === "door") {
    if (appearance.is_open === null) {
      throw new ContractValidationError(
        `${path}.is_open`,
        "door structural edge requires explicit open state",
      );
    }
    return;
  }
  if (appearance.is_open !== null) {
    throw new ContractValidationError(
      `${path}.is_open`,
      "wall structural edge cannot carry open state",
    );
  }
}

function tileBlocks(
  tile: APITile,
  channel: FloorObjectBlockingChannel,
  direction: FloorObjectDirection,
): boolean {
  switch (channel) {
    case "movement":
      return tile.directional_blocks_movement[direction];
    case "vision":
      return tile.directional_blocks_vision[direction];
    case "light":
      return tile.directional_blocks_light[direction];
    case "propagation":
      return tile.directional_blocks_propagation[direction];
  }
}

function readEnumArray(
  value: unknown,
  allowed: ReadonlySet<string>,
  path: string,
): Array<string> {
  if (value === undefined || value === null) return [];
  if (
    !Array.isArray(value)
    || value.some((item) => typeof item !== "string" || !allowed.has(item))
  ) {
    throw new ContractValidationError(path, "contains an unsupported value");
  }
  return sortedUnique(value as Array<string>, path);
}

function readStringArray(value: unknown): Array<string> {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function readString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function readBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readSafePresentationRef(
  value: unknown,
): SafeContentPresentationRef | null {
  if (value === undefined || value === null) return null;
  return decodeModel("SafeContentPresentationRef", value);
}

function sortDirections(
  values: ReadonlyArray<FloorObjectDirection>,
): Array<FloorObjectDirection> {
  return [...values].sort((left, right) => (
    DIRECTIONS.indexOf(left) - DIRECTIONS.indexOf(right)
  ));
}

function sortChannels(
  values: ReadonlyArray<FloorObjectBlockingChannel>,
): Array<FloorObjectBlockingChannel> {
  return [...values].sort((left, right) => (
    CHANNELS.indexOf(left) - CHANNELS.indexOf(right)
  ));
}

function sortedUnique(values: ReadonlyArray<string>, path: string): Array<string> {
  const result = [...values].sort(compareString);
  if (new Set(result).size !== result.length) {
    throw new ContractValidationError(path, "values must be unique");
  }
  return result;
}

function copyPosition(position: readonly [number, number]): [number, number] {
  return [position[0], position[1]];
}

function cellKey(position: readonly [number, number]): string {
  return `${position[0]},${position[1]}`;
}

function comparePosition(
  left: readonly [number, number],
  right: readonly [number, number],
): number {
  return left[1] - right[1] || left[0] - right[0];
}

function compareTile(left: APITile, right: APITile): number {
  return left.y - right.y || left.x - right.x;
}

function compareStructuralEdge(
  left: RenderStructuralEdge,
  right: RenderStructuralEdge,
): number {
  return comparePosition(left.position, right.position)
    || OWNED_EDGE_DIRECTIONS.indexOf(left.direction)
      - OWNED_EDGE_DIRECTIONS.indexOf(right.direction);
}

function compareUuid(
  left: { readonly uuid: string },
  right: { readonly uuid: string },
): number {
  return compareString(left.uuid, right.uuid);
}

function compareString(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function compareSenseMode(left: SenseMode, right: SenseMode): number {
  return compareString(left.sense_type, right.sense_type)
    || left.range_feet - right.range_feet;
}

function compareVisualLayer(
  left: VisualEquipmentLayer,
  right: VisualEquipmentLayer,
): number {
  return compareVisualSlot(left.slot, right.slot);
}

function compareVisualSlot(left: string, right: string): number {
  const leftIndex = VISUAL_SLOTS.indexOf(left as VisualLoadoutSlot);
  const rightIndex = VISUAL_SLOTS.indexOf(right as VisualLoadoutSlot);
  const normalizedLeft = leftIndex < 0 ? VISUAL_SLOTS.length : leftIndex;
  const normalizedRight = rightIndex < 0 ? VISUAL_SLOTS.length : rightIndex;
  return normalizedLeft - normalizedRight || compareString(left, right);
}

function sameSet(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
  if (left.size !== right.size) return false;
  for (const value of left) {
    if (!right.has(value)) return false;
  }
  return true;
}
