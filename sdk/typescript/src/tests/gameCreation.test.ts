import assert from "node:assert/strict";
import test from "node:test";

import {
  ContractValidationError,
  type CreateHostedGameRequest,
  DndEngineClient,
  GameDirectoryClient,
  type EncounterRecipe,
  type GameCreationActivateRequest,
  type GameCreationCatalogResponse,
  type GameCreationComposeRequest,
  type GameCreationPreviewRequest,
  type GameCreationStartRequest,
} from "../index.js";
import type { DirectoryPrincipalCredential } from "../directoryClient.js";

const digest = "a".repeat(64);
const firstCharacterId = "00000000-0000-0000-0000-000000000001";
const secondCharacterId = "00000000-0000-0000-0000-000000000002";
const credential: DirectoryPrincipalCredential = {
  principalId: "00000000-0000-0000-0000-000000000003",
  principalCapability: "directory-secret",
};

const catalog: GameCreationCatalogResponse = {
  schema_version: 3,
  controllers: ["human", "ai", "codex"],
  ai_policies: [],
  roster_recipes: [],
  encounter_recipes: [],
  battlefields: [],
  deployments: [],
};

const composeRequest = {
  title: "Two heroes versus goblins",
  roster_slots: [
    {
      roster_slot_id: "party",
      roster: {
        kind: "owned_characters",
        title: "Adventuring Party",
        character_ids: [firstCharacterId, secondCharacterId],
        member_controller_overrides: [
          {
            character_id: secondCharacterId,
            controller: "codex",
            policy_id: null,
          },
        ],
      },
      faction_id: "heroes",
      deployment_zone_id: "west",
      controller_defaults: {
        controller: "human",
        participant_name: "Player",
        policy_id: null,
        member_overrides: [],
      },
    },
    {
      roster_slot_id: "opposition",
      roster: {
        kind: "authored_roster",
        roster_id: "roster.monsters.goblin_water_cell",
      },
      faction_id: "monsters",
      deployment_zone_id: "east",
      controller_defaults: {
        controller: "ai",
        participant_name: "Opposition",
        policy_id: "builtin.basic",
        member_overrides: [],
      },
    },
  ],
  battlefield_id: "battlefield.standard_hazards_closed",
  deployment_id: "deployment.standard.opposed",
  opening_policy: { kind: "initiative" },
} satisfies GameCreationComposeRequest;

const savedRosterComposeRequest = {
  ...composeRequest,
  roster_slots: [
    {
      ...composeRequest.roster_slots[0]!,
      roster: {
        kind: "saved_roster",
        saved_roster_id: "saved.roster.adventuring-party",
        expected_revision: 4,
        expected_recipe_digest: digest,
      },
    },
    composeRequest.roster_slots[1]!,
  ],
} satisfies GameCreationComposeRequest;

// Preview and start accept the exact opaque recipe returned by composition.
// The handwritten client must neither reconstruct nor normalize it.
const normalizedRecipe = {
  encounter_id: "encounter.normalized",
  recipe_digest: digest,
} as unknown as EncounterRecipe;
const previewRequest = {
  expected_content_set_digest: digest,
  expected_ruleset_digest: digest,
  recipe: normalizedRecipe,
} satisfies GameCreationPreviewRequest;
const startRequest = {
  ...previewRequest,
  codex_lease_seconds: 600,
} satisfies GameCreationStartRequest;

test("game creation client exposes only catalog, compose, preview, and exact start", async () => {
  const calls: Array<{ path: string; method: string; body: unknown }> = [];
  const client = new DndEngineClient("http://engine.test", {
    fetchImplementation: async (input, init) => {
      const url = new URL(String(input));
      calls.push({
        path: url.pathname,
        method: init?.method ?? "GET",
        body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
      });
      return jsonResponse(
        url.pathname === "/game-creation/catalog" ? catalog : {},
      );
    },
  });

  assert.deepEqual(await client.getGameCreationCatalog(), catalog);
  await assert.rejects(
    () => client.composeGameCreation(composeRequest),
    ContractValidationError,
  );
  await assert.rejects(
    () => client.previewGameCreation(previewRequest),
    ContractValidationError,
  );
  await assert.rejects(
    () => client.startGameCreation(startRequest),
    ContractValidationError,
  );

  assert.deepEqual(calls, [
    {
      path: "/game-creation/catalog",
      method: "GET",
      body: null,
    },
    {
      path: "/game-creation/compose",
      method: "POST",
      body: composeRequest,
    },
    {
      path: "/game-creation/preview",
      method: "POST",
      body: previewRequest,
    },
    {
      path: "/game-creation/start",
      method: "POST",
      body: startRequest,
    },
  ]);

  const retired = client as unknown as Record<string, unknown>;
  assert.equal(retired.preflightGameCreation, undefined);
  assert.equal(retired.getGameCreationConfigurationVisualPreview, undefined);
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

test("hosted composition and preview carry exact directory ownership", async () => {
  const calls: Array<{
    path: string;
    principalId: string | null;
    principalCapability: string | null;
    body: unknown;
  }> = [];
  const client = new GameDirectoryClient("http://gateway.test", {
    fetchImplementation: async (input, init) => {
      const headers = new Headers(init?.headers);
      calls.push({
        path: new URL(String(input)).pathname,
        principalId: headers.get("x-dnd-principal-id"),
        principalCapability: headers.get("x-dnd-principal-capability"),
        body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
      });
      return jsonResponse({});
    },
  });

  await assert.rejects(
    () => client.composeGameCreation(credential, composeRequest),
    ContractValidationError,
  );
  await assert.rejects(
    () => client.previewGameCreation(credential, previewRequest),
    ContractValidationError,
  );

  assert.deepEqual(calls, [
    {
      path: "/game-creation/compose",
      principalId: credential.principalId,
      principalCapability: credential.principalCapability,
      body: composeRequest,
    },
    {
      path: "/game-creation/preview",
      principalId: credential.principalId,
      principalCapability: credential.principalCapability,
      body: previewRequest,
    },
  ]);
});

test("saved roster selection preserves the exact CAS identity in composition", async () => {
  let captured: { path: string; body: unknown } | null = null;
  const client = new GameDirectoryClient("http://gateway.test", {
    fetchImplementation: async (input, init) => {
      captured = {
        path: new URL(String(input)).pathname,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
      };
      return jsonResponse({});
    },
  });

  await assert.rejects(
    () => client.composeGameCreation(credential, savedRosterComposeRequest),
    ContractValidationError,
  );
  assert.deepEqual(captured, {
    path: "/game-creation/compose",
    body: savedRosterComposeRequest,
  });
});

test("hosted start embeds the same normalized recipe without another request", async () => {
  const request = {
    principal_id: credential.principalId,
    principal_capability: "directory-secret-capability-000000",
    display_name: "Exact hosted encounter",
    creation: startRequest,
    owner_roster_slot_id: "party",
    visibility_policy: "private",
    observer_policy: "disabled",
    client_kind: "neuroclient",
    client_instance_id: "browser-1",
  } satisfies CreateHostedGameRequest;
  const calls: Array<{ path: string; body: unknown }> = [];
  const client = new GameDirectoryClient("http://gateway.test", {
    fetchImplementation: async (input, init) => {
      calls.push({
        path: new URL(String(input)).pathname,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
      });
      return jsonResponse({});
    },
  });

  await assert.rejects(
    () => client.createGame(request),
    ContractValidationError,
  );
  assert.deepEqual(calls, [{
    path: "/games",
    body: request,
  }]);
  assert.strictEqual(request.creation.recipe, normalizedRecipe);
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
