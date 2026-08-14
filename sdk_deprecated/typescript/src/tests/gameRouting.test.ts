import assert from "node:assert/strict";
import test from "node:test";

import { DndEngineClient } from "../client.js";
import { GameDirectoryClient } from "../directoryClient.js";
import { SubjectiveReplicationClient } from "../subjectiveClient.js";
import { ContractValidationError } from "../validation.js";
import { bootstrap } from "./fixtures.js";

test("server capability probe distinguishes hosted and standalone topology", async () => {
  const urls: string[] = [];
  const fetchImplementation: typeof fetch = async (input) => {
    urls.push(String(input));
    return new Response(JSON.stringify({
      server_mode: "gateway",
      game_directory_enabled: true,
      persistent_game_history: true,
      isolated_game_workers: true,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new DndEngineClient("/api", { fetchImplementation });

  const capabilities = await client.getServerCapabilities();

  assert.equal(capabilities.server_mode, "gateway");
  assert.equal(capabilities.game_directory_enabled, true);
  assert.deepEqual(urls, ["/api/server/capabilities"]);
});

test("standalone status uses the typed single-game directory route", async () => {
  const urls: string[] = [];
  const fetchImplementation: typeof fetch = async (input) => {
    urls.push(String(input));
    return new Response(JSON.stringify({
      active: false,
      game_id: null,
      encounter_active: false,
      active_entity_uuid: null,
      sessions: [],
      creation: null,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new DndEngineClient("/api", { fetchImplementation });

  const status = await client.getStandaloneGameStatus();

  assert.equal(status.active, false);
  assert.deepEqual(urls, ["/api/game/status"]);
});

test("controlled affordance reads carry the session in an encoded query", async () => {
  const urls: string[] = [];
  const fetchImplementation: typeof fetch = async (input) => {
    const url = String(input);
    urls.push(url);
    const payload = url.includes("/available-actions?")
      ? {
        entity_uuid: "entity/a",
        execution_authorization: "not_active_turn",
        entity_actions: [],
        position_actions: [],
        self_actions: [availableAction()],
        object_actions: [],
        remaining_movement: 0,
        handler_details: [availableHandler()],
        actions_remaining: 0,
        bonus_actions_remaining: 0,
        reactions_remaining: 0,
        extra_attacks_remaining: 0,
        spell_slots: {},
        resources: {},
      }
      : url.includes("/equippable-items?")
        ? { entity_uuid: "entity/a", equippable: {} }
        : { entity_uuid: "entity/a", handlers: [availableHandler()] };
    return new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new DndEngineClient("/api", { fetchImplementation });

  const actions = await client.getAvailableActions("entity/a", "session/a b");
  await client.getEquippableItems("entity/a", "session/a b");
  const handlers = await client.getEntityHandlers("entity/a", "session/a b");

  assert.equal(
    actions.self_actions[0]?.behavior_attribution.definition_ref.content_id,
    "action.dash",
  );
  assert.equal(actions.execution_authorization, "not_active_turn");
  assert.equal(
    actions.handler_details[0]?.behavior_attribution.definition_ref.content_id,
    "reaction.lucky",
  );
  assert.equal(
    handlers.handlers[0]?.behavior_attribution.definition_ref.content_id,
    "reaction.lucky",
  );
  assert.deepEqual(urls, [
    "/api/entity/entity%2Fa/available-actions?session_id=session%2Fa+b",
    "/api/entity/entity%2Fa/equippable-items?session_id=session%2Fa+b",
    "/api/entity/entity%2Fa/handlers?session_id=session%2Fa+b",
  ]);
});

test("affordance decoders reject rows without exact behavior attribution", async () => {
  const action = availableAction();
  const { behavior_attribution: _removed, ...unattributedAction } = action;
  const client = new DndEngineClient("/api", {
    fetchImplementation: async () => new Response(JSON.stringify({
      entity_uuid: "entity-a",
      execution_authorization: "authorized",
      entity_actions: [unattributedAction],
      position_actions: [],
      self_actions: [],
      object_actions: [],
      remaining_movement: 0,
      handler_details: [],
      actions_remaining: 1,
      bonus_actions_remaining: 1,
      reactions_remaining: 1,
      extra_attacks_remaining: 0,
      spell_slots: {},
      resources: {},
    }), {
      headers: { "Content-Type": "application/json" },
    }),
  });

  await assert.rejects(
    client.getAvailableActions("entity-a", "session-a"),
    ContractValidationError,
  );

  const handler = availableHandler();
  const { behavior_attribution: _handlerAttribution, ...unattributedHandler } = handler;
  const handlerClient = new DndEngineClient("/api", {
    fetchImplementation: async () => new Response(JSON.stringify({
      entity_uuid: "entity-a",
      handlers: [unattributedHandler],
    }), {
      headers: { "Content-Type": "application/json" },
    }),
  });
  await assert.rejects(
    handlerClient.getEntityHandlers("entity-a", "session-a"),
    ContractValidationError,
  );
});

test("game-scoped subjective client uses the one unversioned bootstrap route", async () => {
  const requests: Array<{ url: string; authorization: string | null }> = [];
  const fetchImplementation: typeof fetch = async (input, init) => {
    const headers = new Headers(init?.headers);
    requests.push({
      url: String(input),
      authorization: headers.get("authorization"),
    });
    return new Response(JSON.stringify(bootstrap()), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new SubjectiveReplicationClient("/api/games/game-a/runtime/", {
    fetchImplementation,
    headers: { Authorization: "Bearer runtime-secret" },
  });

  await client.bootstrap("session-a");

  assert.deepEqual(requests, [{
    url: "/api/games/game-a/runtime/replication/bootstrap?session_id=session-a",
    authorization: "Bearer runtime-secret",
  }]);
});

test("subjective frames require all three hot identities", async () => {
  const urls: string[] = [];
  const fetchImplementation: typeof fetch = async (input) => {
    urls.push(String(input));
    return new Response(JSON.stringify({
      source_stream_id: "stream-a",
      generation_id: "generation-a",
      perspective_epoch_id: "perspective-a",
      retained_from_observation_cursor: 0,
      from_watermarks: { source_event_cursor: 0, observation_cursor: 0, presentation_cursor: 0, combat_log_cursor: 0 },
      through_watermarks: { source_event_cursor: 0, observation_cursor: 0, presentation_cursor: 0, combat_log_cursor: 0 },
      captured_watermarks: { source_event_cursor: 0, observation_cursor: 0, presentation_cursor: 0, combat_log_cursor: 0 },
      frames: [],
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new SubjectiveReplicationClient("/api", { fetchImplementation });

  const history = await client.frames("session-a", {
    sourceStreamId: "stream-a",
    generationId: "generation-a",
    perspectiveEpochId: "perspective-a",
    fromObservationCursor: 0,
  });

  assert.equal(history.through_watermarks.observation_cursor, 0);
  assert.deepEqual(urls, [
    "/api/replication/frames?session_id=session-a&expected_source_stream_id=stream-a&expected_generation_id=generation-a&expected_perspective_epoch_id=perspective-a&from_observation_cursor=0",
  ]);
});

test("subjective combat-log history uses an exact cursor window", async () => {
  const urls: string[] = [];
  const fetchImplementation: typeof fetch = async (input) => {
    urls.push(String(input));
    return new Response(JSON.stringify({
      source_stream_id: "stream-a",
      generation_id: "generation-a",
      perspective_epoch_id: "perspective-a",
      projection: "subjective",
      retained_from_cursor: 0,
      from_cursor: 3,
      through_cursor: 3,
      frames: [],
      total: 3,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new SubjectiveReplicationClient("/api", { fetchImplementation });

  const history = await client.combatLog("session-a", {
    sourceStreamId: "stream-a",
    generationId: "generation-a",
    perspectiveEpochId: "perspective-a",
    fromCombatLogCursor: 3,
  });

  assert.equal(history.through_cursor, 3);
  assert.deepEqual(urls, [
    "/api/replication/combat-log?session_id=session-a&expected_source_stream_id=stream-a&expected_generation_id=generation-a&expected_perspective_epoch_id=perspective-a&from_combat_log_cursor=3",
  ]);
});

test("subjective REST pages must start at the exact requested cursor", async () => {
  const fetchImplementation: typeof fetch = async (input) => {
    const url = String(input);
    if (url.includes("/replication/frames?")) {
      return new Response(JSON.stringify({
        source_stream_id: "stream-a",
        generation_id: "generation-a",
        perspective_epoch_id: "perspective-a",
        retained_from_observation_cursor: 0,
        from_watermarks: { source_event_cursor: 1, observation_cursor: 1, presentation_cursor: 1, combat_log_cursor: 0 },
        through_watermarks: { source_event_cursor: 1, observation_cursor: 1, presentation_cursor: 1, combat_log_cursor: 0 },
        captured_watermarks: { source_event_cursor: 1, observation_cursor: 1, presentation_cursor: 1, combat_log_cursor: 0 },
        frames: [],
      }), { headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify({
      source_stream_id: "stream-a",
      generation_id: "generation-a",
      perspective_epoch_id: "perspective-a",
      projection: "subjective",
      retained_from_cursor: 0,
      from_cursor: 2,
      through_cursor: 2,
      frames: [],
      total: 2,
    }), { headers: { "Content-Type": "application/json" } });
  };
  const client = new SubjectiveReplicationClient("/api", { fetchImplementation });
  const identity = {
    sourceStreamId: "stream-a",
    generationId: "generation-a",
    perspectiveEpochId: "perspective-a",
  } as const;

  await assert.rejects(
    () => client.frames("session-a", { ...identity, fromObservationCursor: 0 }),
    ContractValidationError,
  );
  await assert.rejects(
    () => client.combatLog("session-a", { ...identity, fromCombatLogCursor: 3 }),
    ContractValidationError,
  );
});

test("general engine client has no player or legacy objective replication methods", () => {
  const client = new DndEngineClient("/api");
  assert.equal("bootstrap" in client, false);
  assert.equal("getState" in client, false);
  assert.equal("getVisibility" in client, false);
  assert.equal("getEquipment" in client, false);
  assert.equal("getItem" in client, false);
});

test("terminal summary uses the typed worker evidence route", async () => {
  const urls: string[] = [];
  const fetchImplementation: typeof fetch = async (input) => {
    urls.push(String(input));
    return new Response(JSON.stringify({}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new DndEngineClient("/api", { fetchImplementation });

  await assert.rejects(() => client.getTerminalSummary());

  assert.deepEqual(urls, ["/api/game/evidence/summary"]);
});

test("directory discovery keeps principal capability out of the URL", async () => {
  const requests: Array<{
    url: string;
    principalId: string | null;
    capability: string | null;
  }> = [];
  const fetchImplementation: typeof fetch = async (input, init) => {
    const headers = new Headers(init?.headers);
    requests.push({
      url: String(input),
      principalId: headers.get("x-dnd-principal-id"),
      capability: headers.get("x-dnd-principal-capability"),
    });
    return new Response(JSON.stringify({ games: [], count: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const directory = new GameDirectoryClient("/gateway-api/", { fetchImplementation });

  await directory.listGames({
    principalId: "principal-a",
    principalCapability: "directory-secret",
  });

  assert.deepEqual(requests, [{
    url: "/gateway-api/games",
    principalId: "principal-a",
    capability: "directory-secret",
  }]);
});

test("player identity route stays typed", async () => {
  const principal = {
    principal_id: "00000000-0000-0000-0000-000000000001",
    principal_kind: "human",
    display_name: "Tommaso",
    credential_hash: null,
    metadata: { authentication_kind: "name_only_local" },
    metadata_digest: "metadata-digest",
    created_at: "2026-07-21T18:00:00Z",
    last_seen_at: null,
    disabled_at: null,
  };
  const requests: Array<{ url: string; method: string; capability: string | null }> = [];
  const fetchImplementation: typeof fetch = async (input, init) => {
    const url = String(input);
    const headers = new Headers(init?.headers);
    requests.push({
      url,
      method: init?.method ?? "GET",
      capability: headers.get("x-dnd-principal-capability"),
    });
    return new Response(JSON.stringify({
      principal,
      credential_id: "00000000-0000-0000-0000-000000000003",
      principal_capability: "x".repeat(40),
      authentication_kind: "name_only_local",
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const directory = new GameDirectoryClient("/gateway-api", { fetchImplementation });

  const identity = await directory.identifyPlayer({
    display_name: "Tommaso",
    client_instance_id: "browser-a",
  });

  assert.equal(identity.principal.principal_id, principal.principal_id);
  assert.deepEqual(requests, [
    { url: "/gateway-api/directory/players/identify", method: "POST", capability: null },
  ]);
});

test("directory lifecycle stream is typed, resumable, and capability-scoped", async () => {
  const requests: Array<{
    url: string;
    accept: string | null;
    principalId: string | null;
    capability: string | null;
  }> = [];
  const streamBody = [
    "id: 7",
    "event: sync",
    'data: {"cursor":7}',
    "",
    "id: 6",
    "event: directory_event",
    "data: " + JSON.stringify({
      cursor: 6,
      event_id: "00000000-0000-0000-0000-000000000006",
      game_id: "00000000-0000-0000-0000-000000000001",
      event_type: "game_lifecycle_changed",
      payload: { state: "active" },
      payload_digest: "digest-6",
      created_at: "2026-07-21T18:00:00Z",
    }),
    "",
    "id: 7",
    "event: heartbeat",
    'data: {"cursor":7,"server_time":1784656800}',
    "",
    "",
  ].join("\n");
  const fetchImplementation: typeof fetch = async (input, init) => {
    const headers = new Headers(init?.headers);
    requests.push({
      url: String(input),
      accept: headers.get("accept"),
      principalId: headers.get("x-dnd-principal-id"),
      capability: headers.get("x-dnd-principal-capability"),
    });
    return new Response(streamBody, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
  };
  const directory = new GameDirectoryClient("/gateway-api", { fetchImplementation });
  const envelopes = [];

  for await (const envelope of directory.events(5, {
    principalId: "principal-a",
    principalCapability: "directory-secret",
  })) {
    envelopes.push(envelope);
  }

  assert.deepEqual(envelopes.map((envelope) => envelope.event), [
    "sync",
    "directory_event",
    "heartbeat",
  ]);
  assert.equal(envelopes[1]?.event === "directory_event" && envelopes[1].data.cursor, 6);
  assert.deepEqual(requests, [{
    url: "/gateway-api/games/subscribe?since=5",
    accept: "text/event-stream",
    principalId: "principal-a",
    capability: "directory-secret",
  }]);
});

test("directory event iteration cancels and unlocks the response body on early exit", async () => {
  let cancellations = 0;
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(directoryEventStreamBody()));
    },
    cancel() {
      cancellations += 1;
    },
  });
  const directory = new GameDirectoryClient("/gateway-api", {
    fetchImplementation: async () => new Response(body, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    }),
  });

  for await (const envelope of directory.events(0)) {
    assert.equal(envelope.event, "directory_event");
    break;
  }

  assert.equal(cancellations, 1);
  assert.equal(body.locked, false);
});

test("directory follower propagates consumer TypeErrors without retrying transport", async () => {
  for (const callback of ["connection", "envelope"] as const) {
    const failure = new TypeError(`${callback} callback failed`);
    let requests = 0;
    const directory = new GameDirectoryClient("/gateway-api", {
      fetchImplementation: async () => {
        requests += 1;
        return new Response(directoryEventStreamBody(), {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      },
    });

    await assert.rejects(
      () => directory.followGames({
        initialReconnectDelayMs: 0,
        maximumReconnectDelayMs: 0,
        onConnectionState: async (state) => {
          if (callback === "connection" && state === "connected") throw failure;
        },
        onEnvelope: async () => {
          if (callback === "envelope") throw failure;
        },
      }),
      (error: unknown) => error === failure,
    );
    assert.equal(requests, 1);
  }
});

test("directory follower stops cleanly after the caller aborts", async () => {
  const streamBody = [
    "id: 1",
    "event: directory_event",
    "data: " + JSON.stringify({
      cursor: 1,
      event_id: "00000000-0000-0000-0000-000000000001",
      game_id: null,
      event_type: "principal_created",
      payload: {},
      payload_digest: "digest-1",
      created_at: "2026-07-21T18:00:00Z",
    }),
    "",
    "",
  ].join("\n");
  const fetchImplementation: typeof fetch = async () => new Response(streamBody, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
  const directory = new GameDirectoryClient("/gateway-api", { fetchImplementation });
  const controller = new AbortController();
  const seen: string[] = [];

  await directory.followGames({
    signal: controller.signal,
    initialReconnectDelayMs: 0,
    maximumReconnectDelayMs: 0,
    onEnvelope: (envelope) => {
      seen.push(envelope.event);
      controller.abort();
    },
  });

  assert.deepEqual(seen, ["directory_event"]);
});

function availableAction() {
  return {
    template_name: "Dash",
    semantic_key: "dash",
    behavior_attribution: behaviorAttribution("action", "action.dash"),
    configured_action_ref: null,
    selection_parameter: null,
    target_type: "self",
    availability_status: "source_unaffordable",
    valid_targets: [],
    can_afford: false,
    display_name: "Dash",
    description: "Gain extra movement for this turn.",
    cost_type: "actions",
    cost_amount: 1,
    costs: [{
      name: "Action",
      cost_type: "actions",
      cost: 1,
      resource_name: null,
      resource_cost: 0,
    }],
    weapon_slot: null,
    weapon_name: null,
    damage_types: [],
    outcome_profile: null,
    self_setup_profile: null,
    target_effect_profile: null,
    world_effect_profile: null,
    action_category: "ability",
    base_template_name: null,
    spell_level: null,
    cast_at_level: null,
    is_spell_variant: false,
    requires_concentration: false,
    num_projectiles: null,
    allow_same_target: null,
    is_item_use: false,
    source_item_uuid: null,
    item_stack_count: null,
    item_charge_cost: 0,
    fixed_healing: null,
    connector_traversal: null,
  };
}

function availableHandler() {
  return {
    name: "Lucky",
    behavior_attribution: behaviorAttribution("reaction", "reaction.lucky"),
    uuid: "handler-lucky",
    enabled: true,
    trigger_event: "d20_roll_result",
  };
}

function behaviorAttribution(
  definitionKind: "action" | "reaction",
  contentId: string,
) {
  const ref = {
    pack_id: "content.srd_5_1_cc",
    definition_kind: definitionKind,
    content_id: contentId,
    content_version: 1,
    definition_contract_hash: "a".repeat(64),
  };
  return {
    definition_ref: ref,
    provided_by_ref: ref,
    origin_root_ref: null,
  };
}

function directoryEventStreamBody(): string {
  return [
    "id: 1",
    "event: directory_event",
    "data: " + JSON.stringify({
      cursor: 1,
      event_id: "00000000-0000-0000-0000-000000000001",
      game_id: null,
      event_type: "principal_created",
      payload: {},
      payload_digest: "digest-1",
      created_at: "2026-07-21T18:00:00Z",
    }),
    "",
    "",
  ].join("\n");
}
