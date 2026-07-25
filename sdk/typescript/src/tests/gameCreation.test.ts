import assert from "node:assert/strict";
import test from "node:test";

import {
  DndEngineClient,
  type GameCreationActivateRequest,
  type GameCreationCatalogResponse,
  type GameCreationStartRequest,
} from "../index.js";

const compatibility = {
  hero_configuration_id: "hero.barbarian_l5_berserker_torch",
  monster_configuration_id: "monsters.goblin_water_cell",
  battlefield_id: "battlefield.standard_hazards_closed",
  deployment_id: "neutral.battlefield.standard_hazards_closed",
  phase: "static" as const,
  issues: [],
  admitted: true,
};

const catalog: GameCreationCatalogResponse = {
  schema_version: 1,
  controllers: ["human", "ai", "codex"],
  ai_policies: [{
    descriptor: {
      policy_id: "builtin.basic",
      version: "1",
      display_name: "Basic",
      description: "Bundled deterministic native policy.",
      deterministic: true,
    },
    execution: "in_process",
    provider_id: null,
    capacity: null,
    active_assignments: null,
    available_capacity: null,
  }],
  opening_sides: ["initiative", "side_a", "side_b"],
  hero_configurations: [{
    configuration_id: "hero.barbarian_l5_berserker_torch",
    title: "Berserker",
    side_kind: "hero",
    members: [{
      actor_id: "hero",
      deployment_role: "hero",
      augmentations: [{
        kind: "apparel_grant",
        item_id: "costume",
        visual_variant_id: "85000004",
        display_name: "Pit Fighter's Wrap",
      }],
      kind: "barbarian",
      level: 5,
      primal_path: "berserker",
      equipment_preset: "greataxe",
      asi_4: [["strength", 2]],
      asi_8: [],
    }],
    tags: [],
    rating_eligible: true,
    portable: true,
    exclusion_reason: null,
    diagnostic_warnings: [],
    source_arena_ids: [],
    required_battlefield_capabilities: [],
    forbidden_battlefield_capabilities: [],
    mechanical_hash: "hero-hash",
  }],
  monster_configurations: [],
  battlefields: [],
  deployments: [],
  presets: [],
};

const startRequest: GameCreationStartRequest = {
  scenario: {
    kind: "composed",
    hero_configuration_id: compatibility.hero_configuration_id,
    monster_configuration_id: compatibility.monster_configuration_id,
    battlefield_id: compatibility.battlefield_id,
    deployment_id: compatibility.deployment_id,
  },
  side_a: { controller: "human", name: "Player", policy_id: null },
  side_b: { controller: "ai", name: "Opposition", policy_id: "builtin.basic" },
  opening_side: "side_a",
  codex_lease_seconds: 600,
};

test("game creation client uses the typed catalog and preflight routes", async () => {
  const calls: Array<{ path: string; init?: RequestInit }> = [];
  const client = new DndEngineClient("http://engine.test", {
    fetchImplementation: async (input, init) => {
      const url = new URL(String(input));
      calls.push({ path: url.pathname, ...(init === undefined ? {} : { init }) });
      const payload = url.pathname.endsWith("/catalog") ? catalog : compatibility;
      return jsonResponse(payload);
    },
  });

  assert.deepEqual(await client.getGameCreationCatalog(), catalog);
  assert.deepEqual(await client.preflightGameCreation(compatibility), compatibility);
  assert.deepEqual(calls.map((call) => call.path), [
    "/game-creation/catalog",
    "/game-creation/preflight",
  ]);
  assert.equal(calls[1]?.init?.method, "POST");
  assert.deepEqual(JSON.parse(String(calls[1]?.init?.body)), compatibility);
});

test("game creation client sends the exact atomic start request", async () => {
  let captured: { path: string; body: unknown } | null = null;
  const response = {
    schema_version: 1,
    scenario_kind: "composed" as const,
    preset_arena_id: null,
    encounter_uuid: "encounter",
    game_id: "game",
    encounter_name: "Composed Encounter",
    opening_side: "side_a" as const,
    compatibility,
    side_a: sideResult("side_a", "human"),
    side_b: sideResult("side_b", "ai"),
    status: "prepared",
  };
  const client = new DndEngineClient("http://engine.test", {
    fetchImplementation: async (input, init) => {
      captured = {
        path: new URL(String(input)).pathname,
        body: JSON.parse(String(init?.body)),
      };
      return jsonResponse(response);
    },
  });

  assert.deepEqual(await client.startGameCreation(startRequest), response);
  assert.deepEqual(captured, {
    path: "/game-creation/start",
    body: startRequest,
  });
});

test("game creation activation sends the exact bootstrap identity", async () => {
  const request: GameCreationActivateRequest = {
    session_id: "session",
    expected_source_stream_id: "source",
    expected_generation_id: "generation",
    expected_perspective_epoch_id: "perspective",
  };
  const response = {
    status: "activated" as const,
    game_id: "game",
    encounter_uuid: "encounter",
  };
  let captured: { path: string; body: unknown } | null = null;
  const client = new DndEngineClient("http://engine.test", {
    fetchImplementation: async (input, init) => {
      captured = {
        path: new URL(String(input)).pathname,
        body: JSON.parse(String(init?.body)),
      };
      return jsonResponse(response);
    },
  });

  assert.deepEqual(await client.activateGameCreation(request), response);
  assert.deepEqual(captured, {
    path: "/game-creation/activate",
    body: request,
  });
});

function sideResult(sideId: "side_a" | "side_b", controller: "human" | "ai") {
  return {
    side_id: sideId,
    title: sideId === "side_a" ? "Berserker" : "Goblins",
    controller,
    participant_name: sideId === "side_a" ? "Player" : "Opposition",
    entity_assignments: [{
      entity_uuid: sideId === "side_a" ? "hero" : "goblin",
      entity_name: sideId === "side_a" ? "Hero" : "Goblin",
      faction: sideId === "side_a" ? "heroes" : "monsters",
    }],
    policy_id: sideId === "side_b" ? "builtin.basic" : null,
    policy_execution: sideId === "side_b" ? "in_process" : null,
    provider_id: null,
    codex_session_id: null,
    takeover_claim_id: null,
    takeover_expires_at: null,
  };
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
