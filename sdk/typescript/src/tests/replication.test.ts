import assert from "node:assert/strict";
import test from "node:test";

import {
  ContractValidationError,
  SUBJECTIVE_DUPLICATE_RETENTION_LIMIT,
  SubjectiveReplicationClient,
  SubjectiveReplicationJournal,
  SubjectiveSseDecoder,
  SubjectiveStreamFollower,
  assertSubjectiveReplicationBootstrap,
  decodeAlias,
  decodeSubjectiveEnvelope,
  parseJson,
  type SubjectiveReplicationBootstrap,
  type SubjectiveReplicationJournalState,
} from "../index.js";
import {
  bootstrap,
  frameDelivery,
  hiddenLogDelivery,
  replicationFrame,
  syncDelivery,
  watermarks,
} from "./fixtures.js";

function heroPosition(journal: SubjectiveReplicationJournal, view: "authoritative" | "presentation") {
  const replica = journal.state()[view];
  assert.notEqual(replica, null);
  return replica?.world.state.entities.find((entity) => entity.uuid === "hero")?.position;
}

test("typed observation patches outrun presentation without exposing engine events", () => {
  const journal = new SubjectiveReplicationJournal();
  assert.equal(journal.bootstrap(bootstrap()).health, "ready");
  const delivery = frameDelivery();

  const result = journal.ingest({
    event: "frame",
    id: "s=1;o=1;p=1;l=0",
    data: delivery,
  });

  assert.equal(result.status, "applied");
  assert.deepEqual(heroPosition(journal, "authoritative"), [1, 0]);
  assert.deepEqual(heroPosition(journal, "presentation"), [0, 0]);
  assert.equal(journal.peekPresentationFrame()?.presentation[0]?.kind, "movement");
  journal.commitPresentationFrame(1);
  assert.deepEqual(heroPosition(journal, "presentation"), [1, 0]);
});

test("nullable subjective log slots wait behind the presentation source barrier", () => {
  const journal = new SubjectiveReplicationJournal();
  journal.bootstrap(bootstrap());

  journal.ingest({
    event: "frame",
    id: "s=1;o=1;p=1;l=0",
    data: frameDelivery(),
  });
  journal.ingest({
    event: "combat_log",
    id: "s=1;o=1;p=1;l=1",
    data: hiddenLogDelivery(),
  });
  assert.equal(journal.state().authoritative?.watermarks.combat_log_cursor, 1);
  assert.equal(journal.state().presentation?.watermarks.combat_log_cursor, 0);

  journal.commitPresentationFrame(1);
  assert.equal(journal.state().presentation?.watermarks.combat_log_cursor, 1);
  assert.deepEqual(journal.state().presentation?.combatLog, []);
});

test("subjective SSE accepts exactly sync, frame, and narrow combat-log deliveries", () => {
  const decoder = new SubjectiveSseDecoder();
  const messages = [
    encode("sync", "s=1;o=1;p=1;l=0", syncDelivery()),
    encode("frame", "s=1;o=1;p=1;l=0", frameDelivery()),
    encode("combat_log", "s=1;o=1;p=1;l=1", hiddenLogDelivery()),
  ].join("");
  const envelopes = decoder.feed(messages);

  assert.deepEqual(envelopes.map((envelope) => envelope.event), ["sync", "frame", "combat_log"]);
  assert.equal(envelopes[2]?.data.kind, "combat_log");
  assert.throws(
    () => decodeSubjectiveEnvelope({ event: "game_event", id: "s=0;o=0;p=0;l=0", data: {} }),
    ContractValidationError,
  );
  assert.throws(
    () => decodeSubjectiveEnvelope({
      event: "sync",
      id: "s=9;o=9;p=9;l=9",
      data: parseJson(JSON.stringify(syncDelivery())),
    }),
    ContractValidationError,
  );
});

test("reconnect follower accepts exact interleaved frame and log backfill", () => {
  const follower = new SubjectiveStreamFollower({
    sourceStreamId: "stream-a",
    generationId: "generation-a",
    perspectiveEpochId: "perspective-a",
    sourceEventCursor: 0,
    observationCursor: 0,
    presentationCursor: 0,
    combatLogCursor: 0,
  });
  const secondFrame = replicationFrame(2);
  const envelopes = [
    {
      event: "sync" as const,
      id: "s=2;o=2;p=2;l=2",
      data: { ...syncDelivery(2), watermarks: watermarks(2, 2, 2, 2) },
    },
    {
      event: "frame" as const,
      id: "s=1;o=1;p=1;l=0",
      data: frameDelivery(1),
    },
    {
      event: "combat_log" as const,
      id: "s=1;o=1;p=1;l=1",
      data: hiddenLogDelivery(1, 1),
    },
    {
      event: "frame" as const,
      id: "s=2;o=2;p=2;l=1",
      data: {
        kind: "frame" as const,
        frame: {
          ...secondFrame,
          watermarks: watermarks(2, 2, 2, 1),
        },
      },
    },
    {
      event: "combat_log" as const,
      id: "s=2;o=2;p=2;l=2",
      data: hiddenLogDelivery(2, 2),
    },
  ];

  for (const envelope of envelopes) follower.ingest(envelope);

  assert.deepEqual(follower.position(), {
    sourceStreamId: "stream-a",
    generationId: "generation-a",
    perspectiveEpochId: "perspective-a",
    sourceEventCursor: 2,
    observationCursor: 2,
    presentationCursor: 2,
    combatLogCursor: 2,
  });
});

test("presentation IDs cannot be reused across observation frames", () => {
  const journal = new SubjectiveReplicationJournal();
  journal.bootstrap(bootstrap());
  journal.ingest({ event: "frame", id: "s=1;o=1;p=1;l=0", data: frameDelivery() });
  const second = replicationFrame(2);
  const reused = {
    ...second,
    presentation: [{ ...second.presentation[0]!, presentation_id: "presentation-1" }],
  };

  const result = journal.ingest({
    event: "frame",
    id: "s=2;o=2;p=2;l=0",
    data: { kind: "frame", frame: reused },
  });

  assert.equal(result.state.health, "resync_required");
  assert.equal(result.state.resyncReason, "presentation_id_reused");
});

test("runtime alias decoder rejects opaque or undiscriminated patches", () => {
  assert.equal(decodeAlias("SubjectiveWorldPatch", {
    kind: "entity_remove",
    entity_uuid: "hero",
  }).kind, "entity_remove");
  assert.throws(
    () => decodeAlias("SubjectiveWorldPatch", { kind: "mystery", data: {} }),
    ContractValidationError,
  );
});

test("frame delivery cannot silently advance the combat-log cursor", () => {
  const journal = new SubjectiveReplicationJournal();
  journal.bootstrap(bootstrap());
  const frame = replicationFrame();
  const result = journal.ingest({
    event: "frame",
    id: "s=1;o=1;p=1;l=1",
    data: {
      kind: "frame",
      frame: { ...frame, watermarks: { ...frame.watermarks, combat_log_cursor: 1 } },
    },
  });
  assert.equal(result.state.health, "resync_required");
  assert.equal(result.state.resyncReason, "observation_cursor_gap");
});

test("combat-log delivery may advance only its own independent cursor", () => {
  const journal = new SubjectiveReplicationJournal();
  journal.bootstrap(bootstrap());
  journal.ingest({ event: "frame", id: "s=1;o=1;p=1;l=0", data: frameDelivery() });
  const delivery = hiddenLogDelivery();
  const result = journal.ingest({
    event: "combat_log",
    id: "s=2;o=1;p=1;l=1",
    data: {
      ...delivery,
      watermarks: { ...delivery.watermarks, source_event_cursor: 2 },
    },
  });
  assert.equal(result.state.health, "resync_required");
  assert.equal(result.state.resyncReason, "combat_log_cursor_gap");
});

test("REST frame pages are audit-only and cannot become a second journal reducer path", () => {
  const journal = new SubjectiveReplicationJournal();
  assert.equal("ingestFramesPage" in journal, false);
});

test("bootstrap wire semantics reject invalid floor objects, turns, coverage, and barriers", () => {
  const seed = bootstrap();
  const hero = seed.world.state.entities[0];
  const tile = seed.world.state.grid.tiles[0];
  const encounter = seed.world.state.encounter;
  const visibility = seed.world.visibility.hero;
  assert.ok(hero !== undefined && tile !== undefined && encounter !== null && visibility !== undefined);
  const cases: ReadonlyArray<readonly [string, SubjectiveReplicationBootstrap]> = [
    ["door-only state on an item", {
      ...seed,
      world: {
        ...seed.world,
        state: {
          ...seed.world.state,
          floor_objects: [{
            uuid: "item",
            name: "Potion",
            position: [0, 0],
            map_char: "!",
            object_kind: "item",
            safe_presentation_ref: {
              presentation_contract_hash: "a".repeat(64),
            },
            visual_item_name: "potion",
            visual_variant_id: null,
            blocks_movement: false,
            blocks_vision: false,
            is_open: true,
            blocked_directions: [],
            blocked_channels: [],
            is_lit: null,
            very_bright_radius_feet: null,
            bright_radius_feet: null,
            dim_radius_feet: null,
          }],
        },
      },
    }],
    ["turn index does not identify current entity", {
      ...seed,
      world: {
        ...seed.world,
        state: {
          ...seed.world.state,
          encounter: { ...encounter, current_entity_uuid: "monster", current_turn_index: 0 },
        },
      },
    }],
    ["duplicate entity UUID", {
      ...seed,
      world: {
        ...seed.world,
        state: { ...seed.world.state, entities: [...seed.world.state.entities, hero] },
      },
    }],
    ["effective light does not cover visible cells", {
      ...seed,
      world: {
        ...seed.world,
        visibility: { hero: { ...visibility, effective_light_levels: {} } },
      },
    }],
    ["duplicate grid position", {
      ...seed,
      world: {
        ...seed.world,
        state: {
          ...seed.world.state,
          grid: { ...seed.world.state.grid, tiles: [tile, tile] },
        },
      },
    }],
    ["bootstrap log exceeds source watermark", {
      ...seed,
      combat_log_frames: {
        ...seed.combat_log_frames,
        through_cursor: 1,
        total: 1,
        frames: [{
          source_stream_id: "stream-a",
          generation_id: "generation-a",
          perspective_epoch_id: "perspective-a",
          projection: "subjective",
          combat_log_cursor: 1,
          event_cursor: 1,
          entry: null,
        }],
      },
      watermarks: { ...seed.watermarks, combat_log_cursor: 1 },
    }],
  ];

  for (const [name, invalid] of cases) {
    assert.throws(() => assertSubjectiveReplicationBootstrap(invalid), ContractValidationError, name);
  }
});

test("frame wire semantics reject invalid nested world patches before reduction", () => {
  const seed = bootstrap();
  const visibility = seed.world.visibility.hero;
  const encounter = seed.world.state.encounter;
  assert.ok(visibility !== undefined && encounter !== null);
  const badVisibility = {
    ...replicationFrame(),
    patches: [{
      kind: "observer_visibility_replace",
      observer_uuid: "hero",
      visibility: { ...visibility, effective_light_levels: {} },
    }],
  };
  const badEncounter = {
    ...replicationFrame(),
    patches: [{
      kind: "encounter_replace",
      encounter: { ...encounter, current_entity_uuid: "monster", current_turn_index: 0 },
    }],
  };

  for (const frame of [badVisibility, badEncounter]) {
    assert.throws(
      () => decodeSubjectiveEnvelope({
        event: "frame",
        id: "s=1;o=1;p=1;l=0",
        data: parseJson(JSON.stringify({ kind: "frame", frame })),
      }),
      ContractValidationError,
    );
  }
});

test("follow reset publishes the exact single-fetch bootstrap passed to the journal", async () => {
  const controller = new AbortController();
  const journal = new RecordingJournal();
  let bootstrapRequests = 0;
  const seed = bootstrap();
  const sparseBootstrap: SubjectiveReplicationBootstrap = {
    ...seed,
    watermarks: watermarks(1, 0, 0, 1),
    combat_log_frames: {
      ...seed.combat_log_frames,
      through_cursor: 1,
      frames: [hiddenLogDelivery(1, 1).frame],
      total: 1,
    },
  };
  const resets: Array<{
    readonly reason: string;
    readonly bootstrap: SubjectiveReplicationBootstrap;
    readonly state: SubjectiveReplicationJournalState;
  }> = [];
  const client = new SubjectiveReplicationClient("/api", {
    fetchImplementation: async (input) => {
      const url = String(input);
      if (url.includes("/replication/bootstrap")) {
        bootstrapRequests += 1;
        return jsonResponse(sparseBootstrap);
      }
      return new Response(encode(
        "sync",
        "s=1;o=0;p=0;l=1",
        { ...syncDelivery(0), watermarks: watermarks(1, 0, 0, 1) },
      ), {
        headers: { "Content-Type": "text/event-stream" },
      });
    },
  });

  await client.follow(journal, {
    sessionId: "session-a",
    signal: controller.signal,
    onReplicaReset: (value) => { resets.push(value); },
    onUpdate: () => { controller.abort(); },
    initialReconnectDelayMs: 0,
    maximumReconnectDelayMs: 0,
  });

  const reset = resets[0];
  assert.equal(bootstrapRequests, 1);
  assert.equal(reset?.reason, "initial_bootstrap");
  assert.equal(reset?.bootstrap, journal.lastBootstrap);
  assert.equal(reset?.bootstrap.combat_log_frames.frames.length, 1);
  assert.equal(reset?.bootstrap.combat_log_frames.frames[0]?.entry, null);
  assert.equal(reset?.state.authoritative?.watermarks.combat_log_cursor, 1);
  assert.deepEqual(reset?.state.authoritative?.combatLog, []);
  assert.equal(reset?.state.health, "ready");
});

test("follow consumes the caller's exact initial bootstrap without a second HTTP seed", async () => {
  const controller = new AbortController();
  const journal = new RecordingJournal();
  const seed = bootstrap();
  let bootstrapRequests = 0;
  const resets: Array<{
    readonly reason: string;
    readonly bootstrap: SubjectiveReplicationBootstrap;
  }> = [];
  const client = new SubjectiveReplicationClient("/api", {
    fetchImplementation: async (input) => {
      if (String(input).includes("/replication/bootstrap")) {
        bootstrapRequests += 1;
        throw new Error("follow must not refetch its caller-owned seed");
      }
      return new Response(encode(
        "sync",
        "s=0;o=0;p=0;l=0",
        syncDelivery(0),
      ), {
        headers: { "Content-Type": "text/event-stream" },
      });
    },
  });

  await client.follow(journal, {
    sessionId: "session-a",
    initialBootstrap: seed,
    signal: controller.signal,
    onReplicaReset: (reset) => {
      resets.push(reset);
    },
    onUpdate: () => {
      controller.abort();
    },
    initialReconnectDelayMs: 0,
    maximumReconnectDelayMs: 0,
  });

  assert.equal(bootstrapRequests, 0);
  assert.equal(resets.length, 1);
  assert.equal(resets[0]?.reason, "initial_bootstrap");
  assert.equal(resets[0]?.bootstrap, seed);
  assert.equal(resets[0]?.bootstrap, journal.lastBootstrap);
});

test("follow labels only a truly uninitialized journal as initial bootstrap", async () => {
  const controller = new AbortController();
  const resets: string[] = [];
  const client = new SubjectiveReplicationClient("/api", {
    fetchImplementation: async () => jsonResponse(bootstrap()),
  });

  await client.follow(new SubjectiveReplicationJournal(), {
    sessionId: "session-a",
    signal: controller.signal,
    onReplicaReset: (reset) => {
      resets.push(reset.reason);
      controller.abort();
    },
    initialReconnectDelayMs: 0,
    maximumReconnectDelayMs: 0,
  });

  assert.deepEqual(resets, ["initial_bootstrap"]);
});

test("follow preserves an explicit journal invalidation reason on reentry", async () => {
  const controller = new AbortController();
  const journal = new SubjectiveReplicationJournal();
  journal.bootstrap(bootstrap());
  journal.invalidate("perspective_epoch_changed");
  const resets: string[] = [];
  let bootstrapRequests = 0;
  const client = new SubjectiveReplicationClient("/api", {
    fetchImplementation: async () => {
      bootstrapRequests += 1;
      return jsonResponse(bootstrap());
    },
  });

  await client.follow(journal, {
    sessionId: "session-a",
    signal: controller.signal,
    onReplicaReset: (reset) => {
      resets.push(reset.reason);
      controller.abort();
    },
    initialReconnectDelayMs: 0,
    maximumReconnectDelayMs: 0,
  });

  assert.equal(bootstrapRequests, 1);
  assert.deepEqual(resets, ["perspective_epoch_changed"]);
});

test("subjective client invokes fetch with the global receiver", async () => {
  let receiver: unknown = null;
  const fetchImplementation = async function (this: unknown): Promise<Response> {
    receiver = this;
    return jsonResponse(bootstrap());
  } as typeof fetch;
  const client = new SubjectiveReplicationClient("/api", { fetchImplementation });

  await client.bootstrap("session-a");

  assert.equal(receiver, globalThis);
});

test("follow resync fetches one new seed after consuming the exact initial bootstrap", async () => {
  const controller = new AbortController();
  const journal = new RecordingJournal();
  let bootstrapRequests = 0;
  const initialSeed = bootstrap("generation-a");
  const resets: Array<{ readonly reason: string; readonly bootstrap: SubjectiveReplicationBootstrap }> = [];
  const client = new SubjectiveReplicationClient("/api", {
    fetchImplementation: async (input) => {
      const url = String(input);
      if (url.includes("/replication/bootstrap")) {
        bootstrapRequests += 1;
        return jsonResponse(bootstrap("generation-b"));
      }
      return new Response(encode("sync", "s=9;o=9;p=9;l=9", syncDelivery(0)), {
        headers: { "Content-Type": "text/event-stream" },
      });
    },
  });

  await client.follow(journal, {
    sessionId: "session-a",
    initialBootstrap: initialSeed,
    signal: controller.signal,
    onReplicaReset: (value) => {
      resets.push(value);
      if (value.reason !== "initial_bootstrap") controller.abort();
    },
    initialReconnectDelayMs: 0,
    maximumReconnectDelayMs: 0,
  });

  assert.equal(bootstrapRequests, 1);
  assert.deepEqual(resets.map((value) => value.reason), ["initial_bootstrap", "contract_mismatch"]);
  assert.equal(resets[0]?.bootstrap, initialSeed);
  assert.equal(resets[1]?.bootstrap, journal.lastBootstrap);
  assert.equal(resets[1]?.bootstrap.protocol.generation_id, "generation-b");
});

test("follow retries a transient resync-bootstrap failure without using a cleared journal", async () => {
  const controller = new AbortController();
  const journal = new RecordingJournal();
  let bootstrapRequests = 0;
  const resets: string[] = [];
  const client = new SubjectiveReplicationClient("/api", {
    fetchImplementation: async (input) => {
      const url = String(input);
      if (url.includes("/replication/bootstrap")) {
        bootstrapRequests += 1;
        if (bootstrapRequests === 2) {
          return jsonResponse({ detail: "temporary" }, 503);
        }
        return jsonResponse(bootstrap());
      }
      return new Response(encode("sync", "s=9;o=9;p=9;l=9", syncDelivery(0)), {
        headers: { "Content-Type": "text/event-stream" },
      });
    },
  });

  await client.follow(journal, {
    sessionId: "session-a",
    signal: controller.signal,
    onReplicaReset: (value) => {
      resets.push(value.reason);
      if (value.reason !== "initial_bootstrap") controller.abort();
    },
    initialReconnectDelayMs: 0,
    maximumReconnectDelayMs: 0,
  });

  assert.equal(bootstrapRequests, 3);
  assert.deepEqual(resets, ["initial_bootstrap", "contract_mismatch"]);
  assert.equal(journal.state().health, "ready");
});

test("follow propagates onUpdate failures without reconnecting from an advanced cursor", async () => {
  for (const failure of callbackFailures()) {
    const journal = new SubjectiveReplicationJournal();
    let bootstrapRequests = 0;
    let subscribeRequests = 0;
    const client = new SubjectiveReplicationClient("/api", {
      fetchImplementation: async (input) => {
        if (String(input).includes("/replication/bootstrap")) {
          bootstrapRequests += 1;
          return jsonResponse(bootstrap());
        }
        subscribeRequests += 1;
        return new Response([
          encode("sync", "s=1;o=1;p=1;l=0", syncDelivery(1)),
          encode("frame", "s=1;o=1;p=1;l=0", frameDelivery()),
        ].join(""), {
          headers: { "Content-Type": "text/event-stream" },
        });
      },
    });

    await assert.rejects(
      () => client.follow(journal, {
        sessionId: "session-a",
        onUpdate: async ({ envelope }) => {
          if (envelope.event === "frame") throw failure;
        },
        initialReconnectDelayMs: 0,
        maximumReconnectDelayMs: 0,
      }),
      (error: unknown) => error === failure,
    );

    assert.equal(bootstrapRequests, 1);
    assert.equal(subscribeRequests, 1);
    assert.equal(journal.state().authoritative?.watermarks.observation_cursor, 1);
  }
});

test("follow propagates onReplicaReset failures before opening a stream", async () => {
  for (const failure of callbackFailures()) {
    let bootstrapRequests = 0;
    let subscribeRequests = 0;
    const client = new SubjectiveReplicationClient("/api", {
      fetchImplementation: async (input) => {
        if (String(input).includes("/replication/bootstrap")) {
          bootstrapRequests += 1;
          return jsonResponse(bootstrap());
        }
        subscribeRequests += 1;
        return new Response(null, { status: 204 });
      },
    });

    await assert.rejects(
      () => client.follow(new SubjectiveReplicationJournal(), {
        sessionId: "session-a",
        onReplicaReset: async () => { throw failure; },
        initialReconnectDelayMs: 0,
        maximumReconnectDelayMs: 0,
      }),
      (error: unknown) => error === failure,
    );

    assert.equal(bootstrapRequests, 1);
    assert.equal(subscribeRequests, 0);
  }
});

test("duplicate payload storage is retention-bounded while presentation IDs remain epoch-global", () => {
  const journal = new SubjectiveReplicationJournal();
  journal.bootstrap(bootstrap());
  const internals = journal as unknown as {
    readonly knownFrames: Map<number, string>;
    readonly knownLogs: Map<number, string>;
    readonly presentationIds: ReadonlySet<string>;
  };
  // Seed only the private duplicate caches so this unit tests the 4,096-entry
  // resource boundary without performing thousands of unrelated world reduces.
  for (let index = 1; index <= SUBJECTIVE_DUPLICATE_RETENTION_LIMIT; index += 1) {
    internals.knownFrames.set(-index, `old-frame-${index}`);
    internals.knownLogs.set(-index, `old-log-${index}`);
  }

  const frame = boundedReplicationFrame(1, 0);
  assert.equal(journal.ingest({
    event: "frame",
    id: "first-frame",
    data: { kind: "frame", frame },
  }).status, "applied");
  const log = hiddenLogDelivery(1, 1);
  assert.equal(journal.ingest({
    event: "combat_log",
    id: "first-log",
    data: log,
  }).status, "applied");

  assert.equal(internals.knownFrames.size, SUBJECTIVE_DUPLICATE_RETENTION_LIMIT);
  assert.equal(internals.knownLogs.size, SUBJECTIVE_DUPLICATE_RETENTION_LIMIT);
  assert.equal(internals.knownFrames.has(-1), false);
  assert.equal(internals.knownLogs.has(-1), false);
  assert.equal(internals.knownFrames.has(1), true);
  assert.equal(internals.knownLogs.has(1), true);
  assert.equal(internals.presentationIds.size, 1);

  assert.equal(journal.ingest({
    event: "frame",
    id: "duplicate-frame",
    data: { kind: "frame", frame },
  }).status, "duplicate");
  assert.equal(journal.ingest({
    event: "combat_log",
    id: "duplicate-log",
    data: log,
  }).status, "duplicate");

  const reuse = journal.ingest({
    event: "frame",
    id: "reused-presentation-id",
    data: {
      kind: "frame",
      frame: boundedReplicationFrame(
        2,
        1,
        "bounded-presentation-1",
      ),
    },
  });
  assert.equal(reuse.state.health, "resync_required");
  assert.equal(reuse.state.resyncReason, "presentation_id_reused");
});

test("the subjective wire gate accepts every canonical presentation and area kind", () => {
  const validGraphs = [
    [movementCue()],
    movementReactionGraph(),
    movementReactionGraph({
      movement: { endpoint_outcome: "not_committed" },
    }),
    [actionCue()],
    actionConditionGraph(),
    reactiveActionTriggerGraph(),
    [attackCue()],
    [spellCue()],
    [itemCue()],
    [counterspellCue()],
    [damageCue("damage", 1, null)],
    [healCue("heal", 1, null)],
    [conditionCue("condition", 1, null)],
    [doorCue()],
    [lightCue()],
    [spatialEffectCue()],
    [equipmentCue()],
    [encounterCue()],
    forcedMovementGraph(),
    lifecycleGraph(),
    ...areaGeometries().map((area) => [spellCue({ delivery: "aoe", area })]),
  ];

  for (const graph of validGraphs) {
    assert.doesNotThrow(() => decodePresentationGraph(graph));
  }
});

test("generated field constraints reject invalid presentation scalars at the wire gate", () => {
  const cases: ReadonlyArray<readonly [string, ReadonlyArray<Record<string, unknown>>]> = [
    ["empty ID", [{ ...movementCue(), presentation_id: "" }]],
    ["zero source cursor", [{ ...movementCue(), source_event_cursor: 0 }]],
    ["fractional integer", [{ ...movementCue(), path_start_index: 0.5 }]],
    ["short trajectory", [{ ...movementCue(), trajectory: [[0, 0]] }]],
    ["spell level above nine", [{ ...spellCue(), spell_level: 10 }]],
    ["nonpositive area", [spellCue({ delivery: "aoe", area: { shape: "sphere", center: [0, 0], radius_feet: 0 } })]],
    ["nonpositive playback", [{ ...itemCue(), playback_speed: 0 }]],
    ["negative damage", [{ ...damageCue("damage", 1, null), applied_amount: -1 }]],
    ["negative light", [{ ...lightCue(), cells: [{ position: [0, 0], light_level: -1 }] }]],
    ["negative round", [{ ...encounterCue(), round_number: -1 }]],
  ];

  for (const [name, graph] of cases) {
    assert.throws(() => decodePresentationGraph(graph), ContractValidationError, name);
  }
});

test("local presentation semantics reject malformed renderer transactions", () => {
  const duplicateSpellEffect = spellDamageGraph();
  duplicateSpellEffect[0] = {
    ...duplicateSpellEffect[0],
    targets: [
      spellTarget(0, "application-0", ["damage"]),
      spellTarget(1, "application-1", ["damage"]),
    ],
  };
  const cases: ReadonlyArray<readonly [string, ReadonlyArray<Record<string, unknown>>]> = [
    ["movement path overflow", [{ ...movementCue(), path_start_index: 2, path_total_steps: 2 }]],
    ["uncommitted movement without reaction", [{ ...movementCue(), endpoint_outcome: "not_committed" }]],
    ["uncommitted multi-edge movement", movementReactionGraph({
      movement: {
        endpoint_outcome: "not_committed",
        trajectory: [[0, 0], [1, 0], [2, 0]],
        path_total_steps: 2,
      },
    })],
    ["duplicate action target", [{ ...actionCue(), target_uuids: ["hero", "hero"] }]],
    ["action child mismatch", [{ ...actionCue(), effect_presentation_ids: ["missing"] }]],
    ["action self trigger", [{ ...actionCue(), trigger_presentation_id: "action" }]],
    ["action without exact behavior", [{ ...actionCue(), content_attributions: [] }]],
    ["duplicate attack damage types", [{ ...attackCue(), damage_types: ["Fire", "Fire"] }]],
    ["projectile attack without projectile", [{ ...attackCue(), delivery: "projectile", projectile_type: null }]],
    ["melee attack with projectile", [{ ...attackCue(), projectile_type: "bolt" }]],
    ["attack impact mismatch", [{ ...attackCue(), impact_effect_presentation_ids: ["missing"] }]],
    ["zero cone direction", [spellCue({ delivery: "aoe", area: { shape: "cone", origin: [0, 0], direction: [0, 0], length_feet: 15, angle_degrees: 90 } })]],
    ["zero line direction", [spellCue({ delivery: "aoe", area: { shape: "line", origin: [0, 0], direction: [0, 0], length_feet: 15, width_feet: 5 } })]],
    ["centered cube direction", [spellCue({ delivery: "aoe", area: { shape: "cube", origin: [0, 0], direction: [1, 0], size_feet: 10, centered: true } })]],
    ["directionless cube", [spellCue({ delivery: "aoe", area: { shape: "cube", origin: [0, 0], direction: null, size_feet: 10, centered: false } })]],
    ["target without entity or position", [spellCue({ targets: [{ ...spellTarget(), target_uuid: null, position: null }] })]],
    ["position target with entity effects", [spellCue({ targets: [{ ...spellTarget(), target_uuid: null, position: [1, 1], effect_presentation_ids: ["effect"] }], child_presentation_ids: ["effect"] })]],
    ["duplicate application effects", [spellCue({ targets: [{ ...spellTarget(), effect_presentation_ids: ["effect", "effect"] }], child_presentation_ids: ["effect", "effect"] })]],
    ["noncontiguous applications", [spellCue({ targets: [spellTarget(0, "a"), spellTarget(2, "b")] })]],
    ["duplicate application IDs", [spellCue({ targets: [spellTarget(0, "same"), spellTarget(1, "same")] })]],
    ["projectile spell without projectile", [spellCue({ delivery: "projectile", projectile_type: null })]],
    ["AOE without geometry", [spellCue({ delivery: "aoe", area: null })]],
    ["non-AOE with geometry", [spellCue({ area: areaGeometries()[0] })]],
    ["effect shared by applications", duplicateSpellEffect],
    ["spell child mismatch", [spellCue({ targets: [spellTarget(0, "a", ["missing"])] })]],
    ["duplicate item hidden slots", [{ ...itemCue(), hidden_slots: ["weapon", "weapon"] }]],
    ["item child mismatch", [{ ...itemCue(), effect_presentation_ids: ["missing"] }]],
    ["Counterspell without both behavior roles", [{
      ...counterspellCue(),
      content_attributions: counterspellAttributions().slice(0, 1),
    }]],
    ["automatic Counterspell with an insufficient slot", [{
      ...counterspellCue(),
      incoming_spell_level: 5,
    }]],
    ["movement child is not reactive", movementReactionGraph({
      child: damageCue("reaction", 2, "movement"),
    })],
    ["movement reaction resolves too late", movementReactionGraph({
      childSourceEventCursor: 2,
    })],
    ["forced movement does not move", forcedMovementGraph({ start_position: [1, 0], end_position: [1, 0] })],
    ["forced movement parent mismatch", forcedMovementGraph({ actor_action_presentation_id: "wrong" })],
    ["push without forced child", [{ ...shoveCue(), outcome: "succeeded_push" }]],
    ["death save without outcome", lifecycleGraph({ cause_kind: "death_save", death_save_outcome: null })],
    ["life state without transition", lifecycleGraph({}, { previous: "dead", current: "dead" })],
    ["stable without stabilization", lifecycleGraph({}, { previous: "dying", current: "stable", reason: "direct_state_check" })],
    ["duplicate light cells", [{ ...lightCue(), cells: [{ position: [0, 0], light_level: 1 }, { position: [0, 0], light_level: 2 }] }]],
    ["spatial effect without geometry", [{ ...spatialEffectCue(), affected_positions: [] }]],
    ["spatial effect unsorted geometry", [{ ...spatialEffectCue(), affected_positions: [[1, 0], [0, 0]] }]],
    ["spatial effect anchor outside geometry", [{ ...spatialEffectCue(), anchor_position: [9, 9] }]],
    ["equipment owner mismatch", [{ ...equipmentCue(), visual_loadout: { entity_uuid: "monster", active_weapon_set: "none", layers: [] } }]],
    ["end without barrier", [{ ...encounterCue(), terminal_barrier: false }]],
    ["non-end terminal metadata", [{ ...encounterCue(), transition: "start", terminal_barrier: true }]],
  ];

  for (const [name, graph] of cases) {
    assert.throws(() => decodePresentationGraph(graph), ContractValidationError, name);
  }
});

test("cross-node presentation semantics reject mismatched actors, targets, and effect types", () => {
  const attackWrongTarget = attackDamageGraph();
  attackWrongTarget[1] = { ...attackWrongTarget[1], target_uuid: "other" };
  const attackWrongSource = attackDamageGraph();
  attackWrongSource[1] = { ...attackWrongSource[1], source_uuid: "other" };
  const spellWrongTarget = spellDamageGraph();
  spellWrongTarget[1] = { ...spellWrongTarget[1], target_uuid: "other" };
  const spellWrongSource = spellDamageGraph();
  spellWrongSource[1] = { ...spellWrongSource[1], source_uuid: "other" };
  const forcedWrongActor = forcedMovementGraph({ source_uuid: "other" });
  const lifecycleWrongEntity = lifecycleGraph({}, { entity_uuid: "other" });
  const actionWrongTarget = actionConditionGraph();
  actionWrongTarget[1] = { ...actionWrongTarget[1], target_uuid: "other" };
  const actionWrongNestedAttack = [
    actionCue({
      ...cueBase("action", "action", 1, null, ["attack"]),
      content_attributions: actionCue().content_attributions,
      target_uuids: ["hero"],
      effect_presentation_ids: ["attack"],
    }),
    attackCue({
      ...cueBase("attack", "attack", 2, "action"),
      target_uuid: "monster",
    }),
  ];
  const actionDanglingTrigger = reactiveActionTriggerGraph();
  actionDanglingTrigger[0] = {
    ...actionDanglingTrigger[0],
    trigger_presentation_id: "missing",
  };
  const actionWrongTriggerTarget = reactiveActionTriggerGraph();
  actionWrongTriggerTarget[1] = {
    ...actionWrongTriggerTarget[1],
    target_uuid: "other",
  };
  const cases: ReadonlyArray<readonly [string, ReadonlyArray<Record<string, unknown>>]> = [
    ["action target", actionWrongTarget],
    ["nested attack target", actionWrongNestedAttack],
    ["dangling action trigger", actionDanglingTrigger],
    ["action trigger participant", actionWrongTriggerTarget],
    ["attack target", attackWrongTarget],
    ["attack source", attackWrongSource],
    ["spell target", spellWrongTarget],
    ["spell source", spellWrongSource],
    ["forced movement source", forcedWrongActor],
    ["lifecycle entity", lifecycleWrongEntity],
  ];

  for (const [name, graph] of cases) {
    assert.throws(() => decodePresentationGraph(graph), ContractValidationError, name);
  }
});

type CueOverrides = Readonly<Record<string, unknown>>;

function cueBase(
  kind: string,
  id: string,
  cursor = 1,
  parent: string | null = null,
  children: ReadonlyArray<string> = [],
): Record<string, unknown> {
  return {
    presentation_cursor: cursor,
    presentation_id: id,
    parent_presentation_id: parent,
    child_presentation_ids: [...children],
    source_event_cursor: 1,
    source_event_uuid: `event-${id}`,
    content_attributions: [],
    kind,
  };
}

function movementCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("movement", "movement"),
    entity_uuid: "hero",
    movement_kind: "walk",
    movement_sequence_id: "movement-sequence-a",
    trajectory: [[0, 0], [1, 0]],
    path_start_index: 0,
    path_total_steps: 1,
    endpoint_outcome: "committed",
    perception_commit: "observation_frame",
    ...overrides,
  };
}

function actionCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("action", "action"),
    content_attributions: [{
      kind: "unrooted_behavior",
      role: "behavior",
      definition_ref: contentRef("action.rage", "action"),
      provided_by_ref: contentRef("action.rage", "action"),
    }],
    actor_uuid: "hero",
    action_name: "Rage",
    target_uuids: ["hero"],
    trigger_presentation_id: null,
    effect_presentation_ids: [],
    ...overrides,
  };
}

function attackCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("attack", "attack"),
    actor_uuid: "hero",
    target_uuid: "monster",
    action_name: "Strike",
    outcome: "miss",
    delivery: "melee",
    weapon_slot: "MELEE_MAIN",
    damage_types: ["Slashing"],
    projectile_type: null,
    impact_effect_presentation_ids: [],
    ...overrides,
  };
}

function spellTarget(
  applicationIndex = 0,
  applicationId = "application-0",
  effects: ReadonlyArray<string> = [],
): Record<string, unknown> {
  return {
    application_index: applicationIndex,
    application_id: applicationId,
    outcome: "automatic",
    target_uuid: "monster",
    position: null,
    effect_presentation_ids: [...effects],
  };
}

function spellCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("spell", "spell"),
    actor_uuid: "hero",
    spell_id: "magic_missile",
    spell_name: "Magic Missile",
    spell_school: "evocation",
    spell_level: 1,
    delivery: "direct",
    targets: [],
    projectile_type: null,
    area: null,
    ...overrides,
  };
}

function itemCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("item_action", "item"),
    actor_uuid: "hero",
    item_uuid: "potion",
    item_kind: "usable",
    action_kind: "drink",
    actor_clip: "Taunt",
    effect_frame: 2,
    playback_speed: 1,
    hidden_slots: ["weapon"],
    effect_presentation_ids: [],
    ...overrides,
  };
}

function counterspellCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("counterspell", "counterspell"),
    content_attributions: counterspellAttributions(),
    reactor_uuid: "hero",
    incoming_caster_uuid: "monster",
    incoming_spell_level: 3,
    counterspell_slot_level: 3,
    resolution: { kind: "automatic_success" },
    ...overrides,
  };
}

function counterspellAttributions(): ReadonlyArray<Record<string, unknown>> {
  return [
    {
      kind: "unrooted_behavior",
      role: "behavior",
      definition_ref: contentRef("reaction.spell.counterspell", "reaction"),
      provided_by_ref: contentRef("reaction.spell.counterspell", "reaction"),
    },
    {
      kind: "unrooted_behavior",
      role: "trigger_behavior",
      definition_ref: contentRef("spell.fireball", "spell"),
      provided_by_ref: contentRef("spell.fireball", "spell"),
    },
  ];
}

function spatialEffectCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("spatial_effect", "spatial-effect"),
    effect_uuid: "effect",
    content_ref: contentRef(
      "spatial_effect.spell.entangle",
      "spatial_effect",
    ),
    operation: "created",
    layer: "field",
    anchor_position: [0, 0],
    affected_positions: [[0, 0], [0, 1]],
    previous_positions: [],
    ...overrides,
  };
}

function contentRef(
  contentId: string,
  definitionKind: "action" | "reaction" | "spell" | "spatial_effect",
): Record<string, unknown> {
  return {
    pack_id: "content.srd_5_1_cc",
    definition_kind: definitionKind,
    content_id: contentId,
    content_version: 1,
    definition_contract_hash: "a".repeat(64),
  };
}

function shoveCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("shove", "shove"),
    actor_uuid: "hero",
    target_uuid: "monster",
    outcome: "resisted",
    actor_clip: "Kick",
    contact_frame: 2,
    playback_speed: 1,
    forced_movement_presentation_id: null,
    prone_condition_presentation_id: null,
    ...overrides,
  };
}

function damageCue(id: string, cursor: number, parent: string | null): Record<string, unknown> {
  return {
    ...cueBase("damage", id, cursor, parent),
    source_uuid: "hero",
    target_uuid: "monster",
    applied_amount: 3,
    resulting_hp: 7,
    damage_types: ["Slashing"],
  };
}

function healCue(id: string, cursor: number, parent: string | null): Record<string, unknown> {
  return {
    ...cueBase("heal", id, cursor, parent),
    source_uuid: "hero",
    target_uuid: "hero",
    amount: 3,
    resulting_hp: 10,
  };
}

function conditionCue(id: string, cursor: number, parent: string | null): Record<string, unknown> {
  return {
    ...cueBase("condition", id, cursor, parent),
    target_uuid: "monster",
    condition_semantic_key: "prone",
    condition_name: "Prone",
    condition_category: "condition",
    operation: "applied",
  };
}

function doorCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("door", "door"),
    object_uuid: "door-1",
    position: [1, 1],
    is_open: true,
    ...overrides,
  };
}

function lightCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("light", "light"),
    observer_uuid: "hero",
    mode: "replacement",
    cells: [{ position: [0, 0], light_level: 3 }],
    ...overrides,
  };
}

function equipmentCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("equipment", "equipment"),
    entity_uuid: "hero",
    visual_loadout: { entity_uuid: "hero", active_weapon_set: "none", layers: [] },
    ...overrides,
  };
}

function encounterCue(overrides: CueOverrides = {}): Record<string, unknown> {
  return {
    ...cueBase("encounter", "encounter"),
    encounter_uuid: "encounter",
    transition: "end",
    round_number: 1,
    acting_entity_uuid: null,
    reason: "finished",
    terminal_barrier: true,
    projected_combatant_uuids: ["hero", "monster"],
    ...overrides,
  };
}

function forcedMovementGraph(overrides: CueOverrides = {}): Array<Record<string, unknown>> {
  return [
    shoveCue({
      ...cueBase("shove", "shove", 1, null, ["forced"]),
      outcome: "succeeded_push",
      forced_movement_presentation_id: "forced",
    }),
    {
      ...cueBase("forced_movement", "forced", 2, "shove"),
      entity_uuid: "monster",
      source_uuid: "hero",
      cause: "shove",
      actor_action_presentation_id: "shove",
      start_position: [0, 0],
      end_position: [1, 0],
      duration_ms: 100,
      target_clip: "TakeDamage",
      brace_frame: 1,
      playback_speed: 1,
      ...overrides,
    },
  ];
}

function lifecycleGraph(
  causeOverrides: CueOverrides = {},
  lifeOverrides: CueOverrides = {},
): Array<Record<string, unknown>> {
  return [
    {
      ...cueBase("lifecycle_cause", "cause", 1, null, ["life"]),
      entity_uuid: "monster",
      cause_kind: "revive",
      source_uuid: "hero",
      death_save_outcome: null,
      ...causeOverrides,
    },
    {
      ...cueBase("life_state", "life", 2, "cause"),
      entity_uuid: "monster",
      previous: "dead",
      current: "alive",
      reason: "revival",
      causing_effect_presentation_id: "cause",
      ...lifeOverrides,
    },
  ];
}

function attackDamageGraph(): Array<Record<string, unknown>> {
  return [
    attackCue({
      ...cueBase("attack", "attack", 1, null, ["damage"]),
      outcome: "hit",
      impact_effect_presentation_ids: ["damage"],
    }),
    damageCue("damage", 2, "attack"),
  ];
}

function movementReactionGraph(
  options: {
    readonly child?: Record<string, unknown>;
    readonly childSourceEventCursor?: number;
    readonly movement?: Record<string, unknown>;
  } = {},
): Array<Record<string, unknown>> {
  const child = options.child ?? attackCue({
    ...cueBase("attack", "reaction", 2, "movement"),
    source_event_cursor: options.childSourceEventCursor ?? 1,
  });
  return [
    movementCue({
      ...cueBase("movement", "movement", 1, null, ["reaction"]),
      source_event_cursor: 2,
      ...options.movement,
    }),
    child,
  ];
}

function spellDamageGraph(): Array<Record<string, unknown>> {
  return [
    spellCue({
      ...cueBase("spell", "spell", 1, null, ["damage"]),
      targets: [spellTarget(0, "application-0", ["damage"])],
    }),
    damageCue("damage", 2, "spell"),
  ];
}

function actionConditionGraph(): Array<Record<string, unknown>> {
  return [
    actionCue({
      ...cueBase("action", "action", 1, null, ["condition"]),
      content_attributions: actionCue().content_attributions,
      effect_presentation_ids: ["condition"],
    }),
    {
      ...conditionCue("condition", 2, "action"),
      target_uuid: "hero",
    },
  ];
}

function reactiveActionTriggerGraph(): Array<Record<string, unknown>> {
  return [
    actionCue({
      ...cueBase("action", "reaction", 1),
      content_attributions: actionCue().content_attributions,
      action_name: "Shield",
      target_uuids: ["hero"],
      trigger_presentation_id: "incoming-attack",
    }),
    attackCue({
      ...cueBase("attack", "incoming-attack", 2),
      actor_uuid: "monster",
      target_uuid: "hero",
    }),
  ];
}

function areaGeometries(): ReadonlyArray<Record<string, unknown>> {
  return [
    { shape: "sphere", center: [0, 0], radius_feet: 10 },
    { shape: "cone", origin: [0, 0], direction: [1, 0], length_feet: 15, angle_degrees: 90 },
    { shape: "line", origin: [0, 0], direction: [1, 0], length_feet: 30, width_feet: 5 },
    { shape: "cube", origin: [0, 0], direction: null, size_feet: 10, centered: true },
    { shape: "cylinder", center: [0, 0], radius_feet: 10, height_feet: 20 },
  ];
}

function decodePresentationGraph(presentation: ReadonlyArray<Record<string, unknown>>): void {
  const count = presentation.length;
  const sourceEventCursor = Math.max(
    1,
    ...presentation.map((cue) => (
      typeof cue.source_event_cursor === "number"
        ? cue.source_event_cursor
        : 1
    )),
  );
  decodeSubjectiveEnvelope({
    event: "frame",
    id: `s=${sourceEventCursor};o=1;p=${count};l=0`,
    data: parseJson(JSON.stringify({
      kind: "frame",
      frame: {
        source_stream_id: "stream-a",
        generation_id: "generation-a",
        perspective_epoch_id: "perspective-a",
        watermarks: {
          source_event_cursor: sourceEventCursor,
          observation_cursor: 1,
          presentation_cursor: count,
          combat_log_cursor: 0,
        },
        presentation_from_cursor: 0,
        patches: [],
        presentation,
      },
    })),
  });
}

function encode(event: string, id: string, data: unknown): string {
  return `id: ${id}\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function boundedReplicationFrame(
  cursor: number,
  combatLogCursor: number,
  presentationId = `bounded-presentation-${cursor}`,
) {
  const template = replicationFrame();
  const cue = template.presentation[0];
  assert.ok(cue !== undefined && cue.kind === "movement");
  return {
    ...template,
    watermarks: watermarks(cursor, cursor, cursor, combatLogCursor),
    presentation_from_cursor: cursor - 1,
    patches: [],
    presentation: [{
      ...cue,
      presentation_cursor: cursor,
      presentation_id: presentationId,
      source_event_cursor: cursor,
      source_event_uuid: `bounded-event-${cursor}`,
      trajectory: [[0, 0], [1, 0]] as [[number, number], [number, number]],
      path_start_index: 0,
      path_total_steps: 1,
    }],
  };
}

function callbackFailures(): ReadonlyArray<Error> {
  return [
    new TypeError("callback type failure"),
    new SyntaxError("callback syntax failure"),
    new ContractValidationError("$callback", "callback contract failure"),
  ];
}

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

class RecordingJournal extends SubjectiveReplicationJournal {
  lastBootstrap: SubjectiveReplicationBootstrap | null = null;

  override bootstrap(seed: SubjectiveReplicationBootstrap): SubjectiveReplicationJournalState {
    this.lastBootstrap = seed;
    return super.bootstrap(seed);
  }
}
