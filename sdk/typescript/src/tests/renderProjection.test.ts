import assert from "node:assert/strict";
import test from "node:test";

import {
  ContractValidationError,
  decodeModel,
  deriveVisualLoadout,
  projectObjectiveRenderWorld,
  projectStructuralEdges,
  projectSubjectiveRenderWorld,
  type APIEntityVisibility,
  type APIEquipmentOverview,
  type APIItemSummary,
  type APITile,
  type ObjectiveReplicatedWorld,
  type SubjectivePerspective,
  type SubjectiveReplicatedWorld,
} from "../index.js";
import { bootstrap } from "./fixtures.js";

const safePresentationRef = {
  presentation_contract_hash: "a".repeat(64),
};

test("structural edge wire model rejects malformed or identity-bearing rows", () => {
  const base = required(bootstrap().world.state.grid.tiles[0]);
  assert.throws(
    () => projectStructuralEdges([{
      ...base,
      directional_structural_edges: {
        ...base.directional_structural_edges,
        east: { kind: "door", is_open: null },
      },
    } as unknown as APITile]),
    ContractValidationError,
  );
  assert.throws(
    () => projectStructuralEdges([{
      ...base,
      directional_structural_edges: {
        ...base.directional_structural_edges,
        east: { kind: "wall", is_open: true },
      },
    } as unknown as APITile]),
    ContractValidationError,
  );
  assert.throws(
    () => decodeModel("StructuralEdgeAppearance", {
      kind: "door",
      is_open: false,
      uuid: "hidden-object",
    }),
    ContractValidationError,
  );
});

test("subjective render projection unions every observer while active observer is focus only", () => {
  const seed = bootstrap();
  const tile = required(seed.world.state.grid.tiles[0]);
  const perspective: SubjectivePerspective = {
    projection: "subjective",
    perspective_epoch_id: "spectator-union",
    kind: "spectator_knowledge_union",
    controlled_entity_uuids: [],
    observer_entity_uuids: ["hero", "monster"],
    active_observer_uuid: "monster",
  };
  const heroVisibility: APIEntityVisibility = {
    name: "Hero",
    position: [0, 0],
    visible_cells: [[2, 0], [0, 0]],
    visible_entities: ["monster"],
    visible_objects: ["torch"],
    seen_cells: [[1, 0], [0, 0]],
    sense_modes: [{ sense_type: "Darkvision", range_feet: 60 }],
    effective_light_levels: { "2,0": 2, "0,0": 3 },
  };
  const monsterVisibility: APIEntityVisibility = {
    name: "Monster",
    position: [4, 0],
    visible_cells: [[4, 0], [2, 0]],
    visible_entities: ["hero"],
    visible_objects: ["door"],
    seen_cells: [[4, 0], [3, 0]],
    sense_modes: [],
    effective_light_levels: { "4,0": 3, "2,0": 4 },
  };
  const world: SubjectiveReplicatedWorld = {
    ...seed.world,
    state: {
      ...seed.world.state,
      grid: {
        ...seed.world.state.grid,
        tiles: [
          tile,
          copyTile(tile, 1, 0),
          copyTile(tile, 2, 0),
          copyTile(tile, 3, 0),
          copyTile(tile, 4, 0),
        ],
      },
    },
    visibility: {
      monster: monsterVisibility,
      hero: heroVisibility,
    },
    equipment_by_entity: {},
  };

  const rendered = projectSubjectiveRenderWorld(world, perspective);

  assert.equal(rendered.projection, "subjective");
  assert.equal(rendered.perspective.active_observer_uuid, "monster");
  assert.deepEqual(rendered.perspective.observer_entity_uuids, ["hero", "monster"]);
  assert.deepEqual(rendered.knowledge.visible_cells, [[0, 0], [2, 0], [4, 0]]);
  assert.deepEqual(rendered.knowledge.seen_cells, [[0, 0], [1, 0], [3, 0], [4, 0]]);
  assert.deepEqual(rendered.knowledge.visible_entity_uuids, ["hero", "monster"]);
  assert.deepEqual(rendered.knowledge.visible_object_uuids, ["door", "torch"]);
  assert.deepEqual(rendered.knowledge.effective_light_levels, {
    "0,0": 3,
    "2,0": 4,
    "4,0": 3,
  });
  assert.ok(rendered.knowledge.visible_cells.length > 0);
  assert.ok(rendered.knowledge.visible_entity_uuids.length > 0);
});

test("structural edges retain the visible half of a hidden-neighbor vision wall", () => {
  const seed = bootstrap();
  const base = required(seed.world.state.grid.tiles[0]);
  const tile: APITile = {
    ...base,
    directional_blocks_vision: {
      ...base.directional_blocks_vision,
      east: true,
    },
    directional_structural_edges: {
      ...base.directional_structural_edges,
      east: { kind: "wall", is_open: null },
    },
  };

  const edges = projectStructuralEdges([tile]);
  const rendered = projectSubjectiveRenderWorld({
    ...seed.world,
    state: {
      ...seed.world.state,
      grid: { ...seed.world.state.grid, tiles: [tile] },
    },
  }, seed.perspective);

  assert.deepEqual(edges, [{
    position: [0, 0],
    direction: "east",
    kind: "wall",
    is_open: null,
    blocked_channels: ["vision"],
  }]);
  assert.deepEqual(rendered.state.grid.structural_edges, edges);
  assert.ok(rendered.state.grid.structural_edges.length > 0);
});

test("all tile-local directions normalize to deterministic undirected ownership", () => {
  const base = required(bootstrap().world.state.grid.tiles[0]);
  const cases = [
    { direction: "north", position: [5, 5], owned: [5, 5], ownedDirection: "north" },
    { direction: "south", position: [5, 5], owned: [5, 4], ownedDirection: "north" },
    { direction: "east", position: [5, 5], owned: [5, 5], ownedDirection: "east" },
    { direction: "west", position: [5, 5], owned: [4, 5], ownedDirection: "east" },
  ] as const;

  for (const row of cases) {
    const tile = tileWithEdge(
      copyTile(base, row.position[0], row.position[1]),
      row.direction,
      { kind: "door", is_open: false },
      ["vision"],
    );
    assert.deepEqual(projectStructuralEdges([tile]), [{
      position: row.owned,
      direction: row.ownedDirection,
      kind: "door",
      is_open: false,
      blocked_channels: ["vision"],
    }]);
  }
});

test("known doors suppress reciprocal generic duplicates and stale blocker channels", () => {
  const base = required(bootstrap().world.state.grid.tiles[0]);
  const visibleDoor = tileWithEdge(
    copyTile(base, 0, 0),
    "east",
    { kind: "door", is_open: false },
    ["vision"],
  );
  const rememberedGeneric = tileWithEdge(
    { ...copyTile(base, 1, 0), visible: false },
    "west",
    null,
    ["movement", "vision", "light", "propagation"],
  );
  const expected = [{
    position: [0, 0] as [number, number],
    direction: "east" as const,
    kind: "door" as const,
    is_open: false,
    blocked_channels: ["vision"] as Array<"vision">,
  }];

  assert.deepEqual(
    projectStructuralEdges([visibleDoor, rememberedGeneric]),
    expected,
  );
  assert.deepEqual(
    projectStructuralEdges([rememberedGeneric, visibleDoor]),
    expected,
  );
});

test("authorized open door remains one structural edge with no blocked channels", () => {
  const base = required(bootstrap().world.state.grid.tiles[0]);
  const openDoor = tileWithEdge(
    copyTile(base, 0, 0),
    "east",
    { kind: "door", is_open: true },
    [],
  );
  const staleReciprocal = tileWithEdge(
    { ...copyTile(base, 1, 0), visible: false },
    "west",
    null,
    ["movement", "vision"],
  );

  assert.deepEqual(projectStructuralEdges([openDoor, staleReciprocal]), [{
    position: [0, 0],
    direction: "east",
    kind: "door",
    is_open: true,
    blocked_channels: [],
  }]);
});

test("controlled equipment detail remains separate from safe actor loadouts", () => {
  const seed = bootstrap();
  const heroEquipment: APIEquipmentOverview = {
    slots: [{
      slot: "weapon_melee_main",
      slot_type: "weapon",
      item: item("hero-private-sword", "Hero Private Sword", "Hero Sword"),
    }],
    active_weapon_set: "melee",
    ac: 17,
    inventory: [item("hero-private-potion", "Private Potion", "Potion")],
  };
  const world: SubjectiveReplicatedWorld = {
    ...seed.world,
    equipment_by_entity: { hero: heroEquipment },
    visual_loadout_by_entity: {
      monster: {
        entity_uuid: "monster",
        active_weapon_set: "ranged",
        layers: [{
          slot: "weapon_ranged_main",
          item_kind: "weapon",
          safe_presentation_ref: safePresentationRef,
          visual_item_name: "Enemy Bow",
          visual_variant_id: "bow-a",
          equipped_visual_policy: "visible",
        }],
      },
      hero: {
        entity_uuid: "hero",
        active_weapon_set: "melee",
        layers: [{
          slot: "weapon_melee_main",
          item_kind: "weapon",
          safe_presentation_ref: safePresentationRef,
          visual_item_name: "Hero Sword",
          visual_variant_id: null,
          equipped_visual_policy: "visible",
        }],
      },
    },
  };

  const rendered = projectSubjectiveRenderWorld(world, seed.perspective);

  assert.equal(rendered.equipment.detail_scope, "controlled");
  assert.deepEqual(Object.keys(rendered.equipment.details_by_entity), ["hero"]);
  assert.equal(rendered.equipment.details_by_entity.monster, undefined);
  assert.deepEqual(
    Object.keys(rendered.equipment.visual_loadout_by_entity),
    ["hero", "monster"],
  );
  assert.equal(
    rendered.equipment.visual_loadout_by_entity.monster?.layers[0]?.visual_item_name,
    "Enemy Bow",
  );
  assert.deepEqual(
    rendered.equipment.visual_loadout_by_entity.monster?.layers[0]?.safe_presentation_ref,
    safePresentationRef,
  );
  assert.ok(rendered.equipment.details_by_entity.hero?.inventory.length);
});

test("projection is deterministic under equivalent source ordering", () => {
  const seed = bootstrap();
  const perspective: SubjectivePerspective = {
    projection: "subjective",
    perspective_epoch_id: "spectator-order",
    kind: "spectator_knowledge_union",
    controlled_entity_uuids: [],
    observer_entity_uuids: ["hero", "monster"],
    active_observer_uuid: "hero",
  };
  const heroRow = required(seed.world.visibility.hero);
  const monsterRow: APIEntityVisibility = {
    ...heroRow,
    name: "Monster",
    position: [4, 0],
    visible_entities: ["hero"],
  };
  const first: SubjectiveReplicatedWorld = {
    ...seed.world,
    state: {
      ...seed.world.state,
      entities: [...seed.world.state.entities],
    },
    visibility: { hero: heroRow, monster: monsterRow },
    equipment_by_entity: {},
  };
  const second: SubjectiveReplicatedWorld = {
    ...first,
    state: {
      ...first.state,
      entities: [...first.state.entities].reverse(),
      grid: {
        ...first.state.grid,
        tiles: [...first.state.grid.tiles].reverse(),
      },
    },
    visibility: { monster: monsterRow, hero: heroRow },
    visual_loadout_by_entity: {
      monster: required(first.visual_loadout_by_entity.monster),
      hero: required(first.visual_loadout_by_entity.hero),
    },
  };
  const reversedPerspective: SubjectivePerspective = {
    ...perspective,
    observer_entity_uuids: [...perspective.observer_entity_uuids].reverse(),
  };

  assert.deepEqual(
    projectSubjectiveRenderWorld(first, perspective),
    projectSubjectiveRenderWorld(second, reversedPerspective),
  );
});

test("objective diagnostics normalize into the same render structure", () => {
  const seed = bootstrap();
  const baseTile = required(seed.world.state.grid.tiles[0]);
  const tile: APITile = {
    ...baseTile,
    directional_blocks_movement: {
      ...baseTile.directional_blocks_movement,
      north: true,
    },
    directional_blocks_vision: {
      ...baseTile.directional_blocks_vision,
      north: true,
    },
  };
  const heroEquipment: APIEquipmentOverview = {
    slots: [{
      slot: "weapon_ranged_main",
      slot_type: "weapon",
      item: item("bow", "Longbow", "Longbow"),
    }],
    active_weapon_set: "ranged",
    ac: 15,
    inventory: [],
  };
  const objective: ObjectiveReplicatedWorld = {
    state: {
      grid: { ...seed.world.state.grid, tiles: [tile] },
      entities: [...seed.world.state.entities].reverse(),
      encounter: {
        ...required(seed.world.state.encounter),
        current_turn_index: required(
          required(seed.world.state.encounter).current_turn_index,
        ),
      },
      floor_objects: [{
        uuid: "door",
        name: "Door",
        position: [0, 0],
        map_char: "D",
        state: {
          is_open: false,
          blocked_directions: ["west"],
          blocked_channels: ["movement", "vision"],
          blocks_movement: false,
          blocks_vision_field: false,
          visual_item_name: "DirectionalDoor",
          visual_variant_id: null,
          safe_presentation_ref: safePresentationRef,
        },
      }],
    },
    visibility: seed.world.visibility,
    equipment_by_entity: {
      monster: {
        slots: [],
        active_weapon_set: "none",
        ac: 15,
        inventory: [],
      },
      hero: heroEquipment,
    },
  };

  const rendered = projectObjectiveRenderWorld(objective, {
    observer_entity_uuids: ["hero"],
    active_observer_uuid: "hero",
  });

  assert.equal(rendered.projection, "objective");
  assert.equal(rendered.equipment.detail_scope, "objective");
  assert.deepEqual(Object.keys(rendered.equipment.details_by_entity), ["hero", "monster"]);
  assert.deepEqual(Object.keys(rendered.equipment.visual_loadout_by_entity), ["hero", "monster"]);
  assert.equal(
    rendered.equipment.visual_loadout_by_entity.hero?.active_weapon_set,
    "ranged",
  );
  assert.deepEqual(rendered.state.grid.structural_edges, [{
    position: [0, 0],
    direction: "north",
    kind: "generic",
    is_open: null,
    blocked_channels: ["movement", "vision"],
  }]);
  assert.deepEqual(rendered.state.floor_objects[0], {
    uuid: "door",
    name: "Door",
    position: [0, 0],
    map_char: "D",
    object_kind: "door",
    safe_presentation_ref: safePresentationRef,
    visual_item_name: "DirectionalDoor",
    visual_variant_id: null,
    blocks_movement: false,
    blocks_vision: false,
    is_open: false,
    blocked_directions: ["west"],
    blocked_channels: ["movement", "vision"],
    is_lit: null,
    very_bright_radius_feet: null,
    bright_radius_feet: null,
    dim_radius_feet: null,
  });
  assert.ok(rendered.state.entities.length > 0);
  assert.ok(rendered.state.grid.structural_edges.length > 0);
});

test("objective loadout derivation preserves the authoritative selected stance", () => {
  const equipment: APIEquipmentOverview = {
    slots: [
      {
        slot: "weapon_ranged_main",
        slot_type: "weapon",
        item: item("bow", "Bow", "Bow"),
      },
      {
        slot: "weapon_melee_main",
        slot_type: "weapon",
        item: item("sword", "Sword", "Sword"),
      },
    ],
    active_weapon_set: "ranged",
    ac: 15,
    inventory: [],
  };

  const loadout = deriveVisualLoadout("hero", equipment);

  assert.equal(loadout.active_weapon_set, "ranged");
  assert.deepEqual(
    loadout.layers.map((layer) => layer.slot),
    ["weapon_melee_main", "weapon_ranged_main"],
  );
});

function copyTile(tile: APITile, x: number, y: number): APITile {
  return { ...tile, x, y };
}

function tileWithEdge(
  tile: APITile,
  direction: "north" | "south" | "east" | "west",
  appearance: APITile["directional_structural_edges"]["north"],
  channels: ReadonlyArray<"movement" | "vision" | "light" | "propagation">,
): APITile {
  return {
    ...tile,
    directional_blocks_movement: {
      ...tile.directional_blocks_movement,
      [direction]: channels.includes("movement"),
    },
    directional_blocks_vision: {
      ...tile.directional_blocks_vision,
      [direction]: channels.includes("vision"),
    },
    directional_blocks_light: {
      ...tile.directional_blocks_light,
      [direction]: channels.includes("light"),
    },
    directional_blocks_propagation: {
      ...tile.directional_blocks_propagation,
      [direction]: channels.includes("propagation"),
    },
    directional_structural_edges: {
      ...tile.directional_structural_edges,
      [direction]: appearance,
    },
  };
}

function item(
  uuid: string,
  name: string,
  visualItemName: string,
): APIItemSummary {
  return {
    uuid,
    content_ref: {
      pack_id: "content.test",
      definition_kind: "item",
      content_id: `item.${uuid}`,
      content_version: 1,
      definition_contract_hash: "b".repeat(64),
    },
    recipe_ref: {
      recipe_digest: "c".repeat(64),
      preset_ref: null,
    },
    safe_presentation_ref: safePresentationRef,
    name,
    description: `${name} details`,
    item_type: "weapon",
    rarity: "common",
    weight: 1,
    is_equipped: true,
    equipped_slot: "weapon_melee_main",
    visual_item_name: visualItemName,
    visual_variant_id: null,
    equipped_visual_policy: "visible",
    damage_dice: "1d8",
    damage_type: "slashing",
    weapon_properties: [],
    armor_type: null,
    armor_ac: null,
    shield_ac_bonus: null,
    charges: null,
    max_charges: null,
    stack_count: null,
    is_consumable: false,
  };
}

function required<Value>(value: Value | null | undefined): Value {
  assert.notEqual(value, undefined);
  assert.notEqual(value, null);
  return value as Value;
}
