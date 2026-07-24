import assert from "node:assert/strict";
import test from "node:test";

import {
  ContractValidationError,
  EVENT_CONTRACT_HASH,
  EVENT_CONTRACT_VERSION,
  ObjectiveDiagnosticsClient,
  ObjectiveDiagnosticsFollower,
  ObjectiveDiagnosticsSseDecoder,
  TIMELINE_CONTRACT_HASH,
  TIMELINE_CONTRACT_VERSION,
  assertSubjectiveRenderParityDiagnostics,
  decodeModel,
  type CombatLogEntry,
  type GameEventFrame,
  type GameEventFramesResponse,
  type ObjectiveDiagnosticsBootstrap,
  type ObjectiveDiagnosticsSync,
  type ObjectiveCombatLogFrame,
  type ObjectiveCombatLogFramesResponse,
  type SubjectiveRenderParityDiagnosticsResponse,
} from "../index.js";
import { bootstrap as subjectiveBootstrap, objectiveStepFrame } from "./fixtures.js";

const protocol = {
  timeline_contract_version: TIMELINE_CONTRACT_VERSION,
  timeline_contract_hash: TIMELINE_CONTRACT_HASH,
  event_contract_version: EVENT_CONTRACT_VERSION,
  event_contract_hash: EVENT_CONTRACT_HASH,
};

function objectiveBootstrap(): ObjectiveDiagnosticsBootstrap {
  const subjective = subjectiveBootstrap();
  return {
    projection: "objective",
    protocol,
    source_stream_id: "encounter",
    generation_id: "generation-a",
    event_cursor: 1,
    combat_log_cursor: 1,
    world: {
      state: {
        ...subjective.world.state,
        encounter: subjective.world.state.encounter === null
          ? null
          : {
              ...subjective.world.state.encounter,
              current_turn_index: subjective.world.state.encounter.current_turn_index ?? 0,
            },
        floor_objects: [],
      },
      visibility: subjective.world.visibility,
      equipment_by_entity: {},
    },
  };
}

function objectiveSync(): ObjectiveDiagnosticsSync {
  return {
    projection: "objective",
    protocol,
    source_stream_id: "encounter",
    generation_id: "generation-a",
    event_cursor: 1,
    combat_log_cursor: 1,
  };
}

function objectiveEventFrame(cursor = 1): GameEventFrame {
  return objectiveStepFrame(cursor);
}

function combatLogEntry(): CombatLogEntry {
  return {
    entry_type: "action",
    source_name: "Hero",
    source_uuid: "hero",
    target_name: null,
    target_uuid: null,
    compact: "Hero acts",
    verbose: "Hero acts",
    detailed: "Hero acts",
    data: {},
    success: true,
    sub_entries: [],
    perceiver_uuids: ["hero"],
    revealed_entity_uuids: [],
  };
}

function objectiveCombatLogFrame(cursor = 1): ObjectiveCombatLogFrame {
  return {
    source_stream_id: "encounter",
    generation_id: "generation-a",
    perspective_epoch_id: "objective",
    projection: "objective",
    combat_log_cursor: cursor,
    event_cursor: cursor,
    entry: combatLogEntry(),
  };
}

function objectiveEvents(): GameEventFramesResponse {
  return {
    source_stream_id: "encounter",
    generation_id: "generation-a",
    retained_from_cursor: 0,
    from_cursor: 0,
    through_cursor: 1,
    frames: [objectiveEventFrame()],
    total: 1,
  };
}

function objectiveCombatLog(): ObjectiveCombatLogFramesResponse {
  return {
    source_stream_id: "encounter",
    generation_id: "generation-a",
    perspective_epoch_id: "objective",
    projection: "objective",
    retained_from_cursor: 0,
    from_cursor: 0,
    through_cursor: 1,
    frames: [objectiveCombatLogFrame()],
    total: 1,
  };
}

function subjectiveParity(): SubjectiveRenderParityDiagnosticsResponse {
  return {
    projection: "subjective_parity",
    source_stream_id: "encounter",
    generation_id: "generation-a",
    perspective_epoch_id: "perspective-a",
    source_event_cursor: 1,
    observation_cursor: 1,
    presentation_cursor: 1,
    combat_log_cursor: 1,
    expected_digest: "a".repeat(64),
    actual_digest: "a".repeat(64),
    matches: true,
    compared_path_count: 42,
    visible_tile_count: 4,
    structural_edge_count: 2,
    door_edge_count: 1,
    non_empty_structural_edges: true,
    mismatches: [],
  };
}

test("objective diagnostics client polls typed live subjective parity", async () => {
  const requests: string[] = [];
  const fetchImplementation: typeof fetch = async (input) => {
    requests.push(String(input));
    return new Response(JSON.stringify(subjectiveParity()), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new ObjectiveDiagnosticsClient("/api/games/game-a/runtime", {
    fetchImplementation,
  });

  const report = await client.subjectiveParity("session-a");

  assert.equal(report.matches, true);
  assert.equal(report.structural_edge_count, 2);
  assert.deepEqual(requests, [
    "/api/games/game-a/runtime/diagnostics/subjective-parity?session_id=session-a",
  ]);
});

test("subjective parity validation rejects vacuous or inconsistent reports", () => {
  assert.throws(
    () => decodeModel("SubjectiveRenderParityDiagnosticsResponse", {
      ...subjectiveParity(),
      compared_path_count: 0,
    }),
    ContractValidationError,
  );
  assert.throws(
    () => assertSubjectiveRenderParityDiagnostics({
      ...subjectiveParity(),
      matches: false,
    }),
    ContractValidationError,
  );
});

test("objective HTTP client uses only the canonical diagnostics route family", async () => {
  const requests: Array<{ url: string; authorization: string | null }> = [];
  const fetchImplementation: typeof fetch = async (input, init) => {
    const url = String(input);
    requests.push({
      url,
      authorization: new Headers(init?.headers).get("authorization"),
    });
    const payload = url.includes("/bootstrap")
      ? objectiveBootstrap()
      : url.includes("/events?")
        ? objectiveEvents()
        : objectiveCombatLog();
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new ObjectiveDiagnosticsClient("/api/games/game-a/runtime/", {
    fetchImplementation,
    headers: { Authorization: "Bearer administer-secret" },
  });

  const seed = await client.bootstrap();
  const events = await client.events({
    fromCursor: 0,
    throughCursor: 1,
    limit: 2,
    expectedSourceStreamId: "encounter",
    expectedGenerationId: "generation-a",
  });
  const logs = await client.combatLog({
    fromCursor: 0,
    throughCursor: 1,
    expectedSourceStreamId: "encounter",
    expectedGenerationId: "generation-a",
  });

  assert.equal(seed.world.state.encounter?.uuid, "encounter");
  assert.equal(events.frames[0]?.event.wire_type, "dnd.core.events.StepMovementEvent");
  assert.equal(logs.frames[0]?.entry.compact, "Hero acts");
  assert.deepEqual(requests, [
    {
      url: "/api/games/game-a/runtime/diagnostics/objective/bootstrap",
      authorization: "Bearer administer-secret",
    },
    {
      url: "/api/games/game-a/runtime/diagnostics/objective/events?from_cursor=0&through_cursor=1&limit=2&expected_source_stream_id=encounter&expected_generation_id=generation-a",
      authorization: "Bearer administer-secret",
    },
    {
      url: "/api/games/game-a/runtime/diagnostics/objective/combat-log?from_cursor=0&through_cursor=1&expected_source_stream_id=encounter&expected_generation_id=generation-a",
      authorization: "Bearer administer-secret",
    },
  ]);
});

test("objective diagnostics client invokes fetch with the global receiver", async () => {
  let receiver: unknown = null;
  const fetchImplementation = async function (this: unknown): Promise<Response> {
    receiver = this;
    return new Response(JSON.stringify(objectiveBootstrap()), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } as typeof fetch;
  const client = new ObjectiveDiagnosticsClient("/api", { fetchImplementation });

  await client.bootstrap();

  assert.equal(receiver, globalThis);
});

test("objective SSE decoder accepts only sync, cold event, and non-null objective log frames", () => {
  const decoder = new ObjectiveDiagnosticsSseDecoder();
  const encoded = [
    encodeSse("sync", objectiveSync()),
    encodeSse("game_event", objectiveEventFrame()),
    encodeSse("combat_log", objectiveCombatLogFrame()),
  ].join("");
  const envelopes = decoder.feed(encoded);

  assert.deepEqual(envelopes.map((envelope) => envelope.event), [
    "sync",
    "game_event",
    "combat_log",
  ]);
  assert.throws(
    () => new ObjectiveDiagnosticsSseDecoder().feed(encodeSse("heartbeat", {})),
    ContractValidationError,
  );
  assert.throws(
    () => new ObjectiveDiagnosticsSseDecoder().feed(encodeSse("combat_log", {
      ...objectiveCombatLogFrame(),
      entry: null,
    })),
    ContractValidationError,
  );
  assert.throws(
    () => new ObjectiveDiagnosticsSseDecoder().feed(encodeSse("combat_log", {
      ...objectiveCombatLogFrame(),
      projection: "subjective",
      perspective_epoch_id: "perspective-a",
    })),
    ContractValidationError,
  );
});

test("objective follower advances consumed cursors without treating sync as replay", () => {
  const follower = new ObjectiveDiagnosticsFollower({
    expectedSourceStreamId: "encounter",
    expectedGenerationId: "generation-a",
  });
  follower.ingest({ event: "sync", id: "e=1;l=1", data: objectiveSync() });
  assert.deepEqual(follower.cursor(), {
    sourceStreamId: "encounter",
    generationId: "generation-a",
    eventCursor: 0,
    combatLogCursor: 0,
  });

  follower.ingest({ event: "game_event", id: "e=1;l=0", data: objectiveEventFrame() });
  follower.ingest({ event: "combat_log", id: "e=1;l=1", data: {
    ...objectiveCombatLogFrame(),
    entry: combatLogEntry(),
  } });
  assert.equal(follower.cursor().eventCursor, 1);
  assert.equal(follower.cursor().combatLogCursor, 1);

  assert.throws(
    () => follower.ingest({
      event: "game_event",
      id: null,
      data: objectiveEventFrame(3),
    }),
    /expected contiguous cursor 2/,
  );
  assert.throws(
    () => follower.ingest({
      event: "combat_log",
      id: null,
      data: {
        ...objectiveCombatLogFrame(2),
        source_stream_id: "different-encounter",
        entry: combatLogEntry(),
      },
    }),
    /objective source stream changed/,
  );
});

test("objective event frame validation uses the exhaustive generated event contract", () => {
  assert.equal(
    decodeModel("GameEventFrame", objectiveEventFrame()).event.wire_type,
    "dnd.core.events.StepMovementEvent",
  );
  assert.throws(
    () => decodeModel("GameEventFrame", {
      ...objectiveEventFrame(),
      event: {
        wire_type: "dnd.core.events.StepMovementEvent",
        event_type: "step_movement",
      },
    }),
    ContractValidationError,
  );
  assert.equal(
    decodeModel("WireEvent", objectiveEventFrame().event).wire_type,
    "dnd.core.events.StepMovementEvent",
  );
});

test("objective subscribe sends exact independent cursors and decodes its own stream", async () => {
  const requests: Array<{ url: string; accept: string | null }> = [];
  const stream = [
    encodeSse("sync", objectiveSync()),
    encodeSse("game_event", objectiveEventFrame()),
    encodeSse("combat_log", objectiveCombatLogFrame()),
  ].join("");
  const fetchImplementation: typeof fetch = async (input, init) => {
    requests.push({
      url: String(input),
      accept: new Headers(init?.headers).get("accept"),
    });
    return new Response(stream, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
  };
  const client = new ObjectiveDiagnosticsClient("/api", { fetchImplementation });
  const events = [];
  for await (const envelope of client.subscribe({
    eventCursor: 0,
    combatLogCursor: 0,
    expectedSourceStreamId: "encounter",
    expectedGenerationId: "generation-a",
  })) {
    events.push(envelope.event);
  }

  assert.deepEqual(events, ["sync", "game_event", "combat_log"]);
  assert.deepEqual(requests, [{
    url: "/api/diagnostics/objective/subscribe?since_event=0&since_log=0&expected_source_stream_id=encounter&expected_generation_id=generation-a",
    accept: "text/event-stream",
  }]);
});

function encodeSse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}
