import assert from "node:assert/strict";
import test from "node:test";

import {
  ContractValidationError,
  DndEngineClient,
  ReplicationJournal,
  SseDecoder,
  decodeModel,
  decodeReplicationEnvelope,
} from "../index.js";
import {
  bootstrap,
  damageAppliedEvent,
  forcedMovementEvent,
  maxHpConditionEvent,
  sensoryUpdateEvent,
  spatialLightEvent,
  stepEvent,
} from "./fixtures.js";

function heroPosition(journal: ReplicationJournal, view: "authoritative" | "presentation") {
  const state = journal.state()[view];
  assert.notEqual(state, null);
  const hero = state?.world.state.entities.find((entity) => entity.uuid === "hero");
  assert.notEqual(hero, undefined);
  return hero?.position;
}

test("transport can outrun presentation without overwriting screen state", () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());

  journal.ingest({ event: "game_event", id: "e=1;l=0", data: stepEvent(1, [0, 0], [1, 0]) });
  journal.ingest({ event: "game_event", id: "e=2;l=0", data: stepEvent(2, [1, 0], [9, 0], false) });
  journal.ingest({ event: "game_event", id: "e=3;l=0", data: forcedMovementEvent(3) });

  assert.deepEqual(heroPosition(journal, "authoritative"), [3, 0]);
  assert.deepEqual(heroPosition(journal, "presentation"), [0, 0]);
  assert.equal(journal.state().presentationBacklog, 3);

  journal.commitPresentationEvent(1);
  assert.deepEqual(heroPosition(journal, "presentation"), [1, 0]);
  journal.commitPresentationEvent(2);
  assert.deepEqual(heroPosition(journal, "presentation"), [1, 0]);
  journal.commitPresentationEvent(3);
  assert.deepEqual(heroPosition(journal, "presentation"), [3, 0]);
  assert.equal(journal.state().presentationBacklog, 0);
});

test("presentation can acknowledge a completed visual transaction through its causal cursor", () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());

  journal.ingest({ event: "game_event", id: null, data: stepEvent(1, [0, 0], [1, 0]) });
  journal.ingest({ event: "game_event", id: null, data: stepEvent(2, [1, 0], [2, 0]) });
  journal.ingest({ event: "game_event", id: null, data: forcedMovementEvent(3) });

  assert.deepEqual(
    journal.pendingPresentationEvents().map((payload) => payload.event_cursor),
    [1, 2, 3],
  );
  const presentation = journal.commitPresentationThrough(3);
  assert.equal(presentation.eventCursor, 3);
  assert.deepEqual(heroPosition(journal, "presentation"), [3, 0]);
  assert.equal(journal.state().presentationBacklog, 0);
  assert.throws(() => journal.commitPresentationThrough(4), RangeError);
});

test("factual health events keep the replica equal to public snapshot semantics", () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());

  journal.ingest({
    event: "game_event",
    id: null,
    data: damageAppliedEvent(1, 14, 3),
  });
  const afterDamage = journal.state().authoritative?.world.state.entities.find(
    (entity) => entity.uuid === "hero",
  );
  assert.equal(afterDamage?.hp, 17);

  journal.ingest({
    event: "game_event",
    id: null,
    data: maxHpConditionEvent(2, 25),
  });
  const afterCondition = journal.state().authoritative?.world.state.entities.find(
    (entity) => entity.uuid === "hero",
  );
  assert.equal(afterCondition?.hp, 22);
  assert.equal(afterCondition?.max_hp, 25);
  assert.equal(afterCondition?.ac, 17);
  assert.deepEqual(afterCondition?.conditions, ["Fortified"]);
});

test("batched light events update every changed tile in the replica", () => {
  const journal = new ReplicationJournal();
  const base = bootstrap();
  const seedTile = base.state.grid.tiles[0];
  assert.notEqual(seedTile, undefined);
  journal.bootstrap({
    ...base,
    state: {
      ...base.state,
      grid: {
        ...base.state.grid,
        tiles: [
          seedTile!,
          { ...seedTile!, x: 1, light_level: 3 },
          { ...seedTile!, x: 2, light_level: 3 },
        ],
      },
    },
  });

  journal.ingest({
    event: "game_event",
    id: null,
    data: spatialLightEvent(1, { "0,0": 2, "1,0": 1, "2,0": 4 }),
  });

  const tiles = journal.state().authoritative?.world.state.grid.tiles ?? [];
  assert.deepEqual(
    tiles.map((tile) => [tile.x, tile.y, tile.light_level]),
    [[0, 0, 2], [1, 0, 1], [2, 0, 4]],
  );
});

test("sensory events replace observer position and backend-resolved light", () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());

  journal.ingest({
    event: "game_event",
    id: null,
    data: sensoryUpdateEvent(1, [2, 0], { "0,0": 2, "1,0": 3 }),
  });

  const visibility = journal.state().authoritative?.world.visibility.hero;
  assert.deepEqual(visibility?.position, [2, 0]);
  assert.deepEqual(visibility?.visible_cells, [[0, 0], [1, 0]]);
  assert.deepEqual(visibility?.effective_light_levels, { "0,0": 2, "1,0": 3 });
});

test("sync session state advances authoritatively and waits for its presentation basis", () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());
  const session = {
    status: "connected",
    session_id: "player-session",
    connection_status: "connected",
    is_my_turn: true,
    active_entity_uuid: "hero",
    active_entity_name: "Hero",
    controlled_entities: ["hero"],
  };

  const sync = journal.ingest({
    event: "sync",
    id: null,
    data: {
      generation_id: "generation-a",
      event_cursor: 1,
      combat_log_cursor: 0,
      session,
    },
  });
  assert.equal(sync.status, "applied");
  assert.equal(journal.state().authoritative?.session?.session_id, "player-session");
  assert.equal(journal.state().presentation?.session, null);

  journal.ingest({ event: "game_event", id: null, data: stepEvent(1, [0, 0], [1, 0]) });
  journal.commitPresentationThrough(1);
  assert.equal(journal.state().presentation?.session?.session_id, "player-session");
});

test("duplicate delivery is idempotent and a cursor gap requires resync", () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());
  const first = { event: "game_event" as const, id: null, data: stepEvent(1, [0, 0], [1, 0]) };

  assert.equal(journal.ingest(first).status, "applied");
  assert.equal(journal.ingest(first).status, "duplicate");
  assert.equal(journal.state().presentationBacklog, 1);

  const gap = journal.ingest({
    event: "game_event",
    id: null,
    data: forcedMovementEvent(3),
  });
  assert.equal(gap.status, "resync_required");
  assert.equal(gap.resyncReason, "event_cursor_gap");
});

test("a reset generation can never be mistaken for the previous game", () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());
  const event = { ...stepEvent(1, [0, 0], [1, 0]), generation_id: "generation-b" };

  const result = journal.ingest({ event: "game_event", id: null, data: event });
  assert.equal(result.status, "resync_required");
  assert.equal(result.resyncReason, "generation_changed");
  assert.deepEqual(heroPosition(journal, "authoritative"), [0, 0]);
});

test("SSE burst decoding preserves every event and validates concrete payloads", () => {
  const first = stepEvent(1, [0, 0], [1, 0]);
  const second = forcedMovementEvent(2);
  const wire = [first, second]
    .map((event) => `id: e=${event.event_cursor};l=0\nevent: game_event\ndata: ${JSON.stringify(event)}\n\n`)
    .join("");
  const decoder = new SseDecoder();
  const messages = [
    ...decoder.feed(wire.slice(0, 17)),
    ...decoder.feed(wire.slice(17, 113)),
    ...decoder.feed(wire.slice(113)),
  ];
  const envelopes = messages.map(decodeReplicationEnvelope);

  assert.equal(envelopes.length, 2);
  assert.equal(envelopes[0]?.event, "game_event");
  assert.equal(envelopes[1]?.event, "game_event");
  if (envelopes[1]?.event === "game_event") {
    assert.equal(envelopes[1].data.event.wire_type, "dnd.core.events.ForcedMovementEvent");
  }
});

test("runtime contract validation rejects incomplete backend events", () => {
  const payload = structuredClone(stepEvent(1, [0, 0], [1, 0]));
  const mutable = payload.event as { committed?: boolean };
  delete mutable.committed;

  assert.throws(
    () => decodeModel("GameEventPayload", payload),
    (error) => error instanceof ContractValidationError && error.message.includes("committed"),
  );
});

test("HTTP transport preserves the platform fetch receiver", async () => {
  let receiverWasGlobal = false;
  const fetchImplementation: typeof fetch = async function (
    this: typeof globalThis,
    _input: RequestInfo | URL,
    _init?: RequestInit,
  ): Promise<Response> {
    receiverWasGlobal = this === globalThis;
    return new Response(JSON.stringify(bootstrap()), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new DndEngineClient("http://engine.test", fetchImplementation);

  await client.bootstrap();
  assert.equal(receiverWasGlobal, true);
});

test("replication follower resyncs a cursor gap and resumes from the new base", async () => {
  const journal = new ReplicationJournal();
  journal.bootstrap(bootstrap());
  const resetBase = bootstrap();
  const resetBootstrap = {
    ...resetBase,
    event_cursor: 2,
    state: {
      ...resetBase.state,
      entities: resetBase.state.entities.map((entity) => (
        entity.uuid === "hero" ? { ...entity, position: [2, 0] as [number, number] } : entity
      )),
    },
  };
  const streamCursors: number[] = [];
  const resetReasons: string[] = [];
  const controller = new AbortController();
  const fetchImplementation: typeof fetch = async (input) => {
    const url = new URL(String(input));
    if (url.pathname === "/replication/bootstrap") {
      return new Response(JSON.stringify(resetBootstrap), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.pathname === "/events/subscribe") {
      const cursor = Number(url.searchParams.get("since_event"));
      streamCursors.push(cursor);
      const payload = cursor === 0
        ? stepEvent(2, [0, 0], [2, 0])
        : stepEvent(3, [2, 0], [3, 0]);
      return new Response(
        `id: e=${payload.event_cursor};l=0\nevent: game_event\ndata: ${JSON.stringify(payload)}\n\n`,
        { status: 200, headers: { "Content-Type": "text/event-stream" } },
      );
    }
    throw new Error(`unexpected request ${url}`);
  };
  const client = new DndEngineClient("http://engine.test", fetchImplementation);

  await client.followReplication(journal, {
    sessionId: "player-session",
    signal: controller.signal,
    initialReconnectDelayMs: 0,
    onReplicaReset: ({ reason }) => {
      resetReasons.push(reason);
    },
    onUpdate: ({ result }) => {
      if (result.status === "applied" && result.eventCursor === 3) {
        controller.abort();
      }
    },
  });

  assert.deepEqual(streamCursors, [0, 2]);
  assert.deepEqual(resetReasons, ["event_cursor_gap"]);
  assert.equal(journal.state().health, "ready");
  assert.equal(journal.state().authoritative?.eventCursor, 3);
  assert.deepEqual(heroPosition(journal, "authoritative"), [3, 0]);
});
