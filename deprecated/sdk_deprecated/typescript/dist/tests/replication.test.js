import assert from "node:assert/strict";
import test from "node:test";
import { ContractValidationError, SUBJECTIVE_DUPLICATE_RETENTION_LIMIT, SubjectiveReplicationClient, SubjectiveFrameCatchupResyncError, SubjectiveReplicationHttpError, SubjectiveReplicationJournal, SubjectiveSseDecoder, SubjectiveStreamFollower, assertSubjectiveFrame, assertSubjectiveReplicationBootstrap, decodeAlias, decodeSubjectiveEnvelope, parseJson, reduceSubjectiveWorld, } from "../index.js";
import { bootstrap, frameDelivery, hiddenLogDelivery, replicationFrame, syncDelivery, watermarks, } from "./fixtures.js";
function heroPosition(journal, view) {
    const replica = journal.state()[view];
    assert.notEqual(replica, null);
    return replica?.world.state.entities.find((entity) => entity.uuid === "hero")?.position;
}
test("connector set replacement updates and clears the canonical replica", () => {
    const seedWorld = bootstrap().world;
    const firstTile = seedWorld.state.grid.tiles[0];
    assert.notEqual(firstTile, undefined);
    const world = {
        ...seedWorld,
        state: {
            ...seedWorld.state,
            grid: {
                ...seedWorld.state.grid,
                tiles: [
                    firstTile,
                    { ...firstTile, x: 1, y: 0, elevation_steps: 1 },
                ],
            },
        },
        visibility: {
            ...seedWorld.visibility,
            hero: {
                ...seedWorld.visibility.hero,
                visible_cells: [[0, 0], [1, 0]],
                effective_light_levels: { "0,0": 3, "1,0": 3 },
            },
        },
    };
    const connector = {
        uuid: "connector-1",
        authored_id: "connector.sdk.ladder",
        kind: "ladder",
        presentation_key: "traversal.ladder",
        endpoints: [
            { position: [0, 0], support_tile_uuid: "tile-a", elevation_feet: 0 },
            { position: [1, 0], support_tile_uuid: "tile-b", elevation_feet: 5 },
        ],
        movement_cost_feet: 10,
        action_cost_type: null,
        action_cost_amount: 0,
        bidirectional: true,
        enabled: true,
        provocation_policy: "provokes_source_exit",
        revision: 1,
        objective_digest: "0".repeat(64),
    };
    const installed = reduceSubjectiveWorld(world, [{
            kind: "connector_set_replace",
            connectors: [connector],
        }]);
    assert.deepEqual(installed.state.grid.connectors, [connector]);
    const removed = reduceSubjectiveWorld(installed, [{
            kind: "connector_set_replace",
            connectors: [],
        }]);
    assert.deepEqual(removed.state.grid.connectors, []);
});
test("connector replacement rejects duplicate identity and unauthorized supports", () => {
    const world = bootstrap().world;
    const connector = {
        uuid: "connector-duplicate",
        authored_id: "connector.sdk.duplicate",
        kind: "ladder",
        presentation_key: "traversal.ladder",
        endpoints: [
            { position: [99, 99], support_tile_uuid: "hidden-a", elevation_feet: 500 },
            { position: [100, 99], support_tile_uuid: "hidden-b", elevation_feet: 505 },
        ],
        movement_cost_feet: 10,
        action_cost_type: null,
        action_cost_amount: 0,
        bidirectional: true,
        enabled: true,
        provocation_policy: "provokes_source_exit",
        revision: 1,
        objective_digest: "0".repeat(64),
    };
    assert.throws(() => reduceSubjectiveWorld(world, [{
            kind: "connector_set_replace",
            connectors: [connector, connector],
        }]), ContractValidationError);
    assert.throws(() => reduceSubjectiveWorld(world, [{
            kind: "connector_set_replace",
            connectors: [connector],
        }]), ContractValidationError);
    const visibleTile = world.state.grid.tiles[0];
    assert.notEqual(visibleTile, undefined);
    const rememberedWorld = {
        ...world,
        state: {
            ...world.state,
            grid: {
                ...world.state.grid,
                tiles: [
                    visibleTile,
                    { ...visibleTile, x: 1, y: 0, visible: false, elevation_steps: 1 },
                ],
            },
        },
    };
    const rememberedConnector = {
        ...connector,
        uuid: "connector-remembered",
        authored_id: "connector.sdk.remembered",
        endpoints: [
            { position: [0, 0], support_tile_uuid: "tile-a", elevation_feet: 0 },
            { position: [1, 0], support_tile_uuid: "tile-b", elevation_feet: 5 },
        ],
    };
    assert.throws(() => reduceSubjectiveWorld(rememberedWorld, [{
            kind: "connector_set_replace",
            connectors: [rememberedConnector],
        }]), ContractValidationError);
    const unauthorizedWorld = {
        ...rememberedWorld,
        state: {
            ...rememberedWorld.state,
            grid: {
                ...rememberedWorld.state.grid,
                tiles: rememberedWorld.state.grid.tiles.map((tile) => (tile.x === 1 && tile.y === 0 ? { ...tile, visible: true } : tile)),
            },
        },
    };
    assert.throws(() => reduceSubjectiveWorld(unauthorizedWorld, [{
            kind: "connector_set_replace",
            connectors: [rememberedConnector],
        }]), ContractValidationError);
    const sameEndpointConnector = {
        ...rememberedConnector,
        uuid: "connector-same-endpoint",
        authored_id: "connector.sdk.same_endpoint",
        endpoints: [
            { position: [0, 0], support_tile_uuid: "tile-a", elevation_feet: 0 },
            { position: [0, 0], support_tile_uuid: "tile-b", elevation_feet: 0 },
        ],
    };
    assert.throws(() => reduceSubjectiveWorld(world, [{
            kind: "connector_set_replace",
            connectors: [sameEndpointConnector],
        }]), ContractValidationError);
});
test("connector support integrity is enforced by frame and bootstrap journals", () => {
    const connector = {
        uuid: "connector-hidden",
        authored_id: "connector.sdk.hidden",
        kind: "ladder",
        presentation_key: "traversal.ladder",
        endpoints: [
            { position: [0, 0], support_tile_uuid: "tile-a", elevation_feet: 0 },
            { position: [1, 0], support_tile_uuid: "hidden-b", elevation_feet: 5 },
        ],
        movement_cost_feet: 10,
        action_cost_type: null,
        action_cost_amount: 0,
        bidirectional: true,
        enabled: true,
        provocation_policy: "provokes_source_exit",
        revision: 1,
        objective_digest: "0".repeat(64),
    };
    const journal = new SubjectiveReplicationJournal();
    assert.equal(journal.bootstrap(bootstrap()).health, "ready");
    const delivery = frameDelivery();
    const firstTile = bootstrap().world.state.grid.tiles[0];
    assert.notEqual(firstTile, undefined);
    const unauthorizedTile = {
        ...firstTile,
        x: 1,
        y: 0,
        visible: true,
        elevation_steps: 1,
    };
    const decoded = decodeSubjectiveEnvelope({
        event: "frame",
        id: "s=1;o=1;p=1;l=0",
        data: parseJson(JSON.stringify({
            ...delivery,
            frame: {
                ...delivery.frame,
                patches: [
                    { kind: "tile_upsert", tile: unauthorizedTile },
                    { kind: "connector_set_replace", connectors: [connector] },
                ],
            },
        })),
    });
    const rejectedFrame = journal.ingest(decoded);
    assert.equal(rejectedFrame.status, "resync_required");
    assert.equal(rejectedFrame.state.health, "resync_required");
    const seed = bootstrap("generation-invalid-connector");
    const invalidSeed = {
        ...seed,
        world: {
            ...seed.world,
            state: {
                ...seed.world.state,
                grid: {
                    ...seed.world.state.grid,
                    tiles: [...seed.world.state.grid.tiles, unauthorizedTile],
                    connectors: [connector],
                },
            },
        },
    };
    const rejectedBootstrap = new SubjectiveReplicationJournal().bootstrap(invalidSeed);
    assert.equal(rejectedBootstrap.health, "resync_required");
    assert.equal(rejectedBootstrap.authoritative, null);
    const sameEndpointConnector = {
        ...connector,
        uuid: "connector-same-endpoint-bootstrap",
        authored_id: "connector.sdk.same_endpoint_bootstrap",
        endpoints: [
            { position: [0, 0], support_tile_uuid: "tile-a", elevation_feet: 0 },
            { position: [0, 0], support_tile_uuid: "tile-b", elevation_feet: 0 },
        ],
    };
    const sameEndpointSeed = {
        ...seed,
        world: {
            ...seed.world,
            state: {
                ...seed.world.state,
                grid: {
                    ...seed.world.state.grid,
                    connectors: [sameEndpointConnector],
                },
            },
        },
    };
    assert.equal(new SubjectiveReplicationJournal().bootstrap(sameEndpointSeed).health, "resync_required");
});
test("current observer-union visibility requires projected tile coverage", () => {
    const seed = bootstrap("generation-visible-cell-without-tile");
    const visibleWithoutTile = {
        ...seed.world.visibility.hero,
        visible_cells: [[0, 0], [1, 0]],
        effective_light_levels: { "0,0": 3, "1,0": 3 },
    };
    const journal = new SubjectiveReplicationJournal();
    assert.equal(journal.bootstrap(bootstrap()).health, "ready");
    const delivery = frameDelivery();
    const decoded = decodeSubjectiveEnvelope({
        event: "frame",
        id: "s=1;o=1;p=1;l=0",
        data: parseJson(JSON.stringify({
            ...delivery,
            frame: {
                ...delivery.frame,
                patches: [{
                        kind: "observer_visibility_replace",
                        observer_uuid: "hero",
                        visibility: visibleWithoutTile,
                    }],
            },
        })),
    });
    const rejectedFrame = journal.ingest(decoded);
    assert.equal(rejectedFrame.status, "resync_required");
    assert.equal(rejectedFrame.state.health, "resync_required");
    const invalidSeed = {
        ...seed,
        world: {
            ...seed.world,
            visibility: {
                ...seed.world.visibility,
                hero: visibleWithoutTile,
            },
        },
    };
    const rejectedBootstrap = new SubjectiveReplicationJournal().bootstrap(invalidSeed);
    assert.equal(rejectedBootstrap.health, "resync_required");
    assert.equal(rejectedBootstrap.authoritative, null);
});
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
    const preview = journal.previewPresentationFrame(1);
    assert.equal(preview.frame.presentation[0]?.kind, "movement");
    assert.deepEqual(preview.candidatePresentation.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [1, 0]);
    assert.deepEqual(heroPosition(journal, "presentation"), [0, 0]);
    journal.commitPresentationFrame(preview.token);
    assert.deepEqual(heroPosition(journal, "presentation"), [1, 0]);
});
test("NORMAL preview reduces only the exact head against presentation state, never canonical ahead", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    journal.ingest({ event: "frame", id: "normal-head-1", data: frameDelivery(1) });
    journal.ingest({ event: "frame", id: "normal-head-2", data: frameDelivery(2) });
    assert.deepEqual(heroPosition(journal, "authoritative"), [2, 0]);
    assert.deepEqual(heroPosition(journal, "presentation"), [0, 0]);
    const first = journal.previewPresentationFrame(1);
    assert.deepEqual(first.candidatePresentation.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [1, 0]);
    journal.commitPresentationFrame(first.token);
    assert.deepEqual(heroPosition(journal, "presentation"), [1, 0]);
    const second = journal.previewPresentationFrame(2);
    assert.deepEqual(second.candidatePresentation.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [2, 0]);
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
    const preview = journal.previewPresentationFrame(1);
    journal.commitPresentationFrame(preview.token);
    assert.equal(journal.state().presentation?.watermarks.combat_log_cursor, 1);
    assert.deepEqual(journal.state().presentation?.combatLog, []);
});
test("legal combat-log delivery does not stale an active NORMAL head token", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    journal.ingest({
        event: "frame",
        id: "normal-head-before-log",
        data: frameDelivery(),
    });
    const preview = journal.previewPresentationFrame(1);
    assert.equal(journal.ingest({
        event: "combat_log",
        id: "normal-head-log",
        data: hiddenLogDelivery(),
    }).status, "applied");
    assert.equal(journal.state().presentation?.watermarks.combat_log_cursor, 0);
    const committed = journal.commitPresentationFrame(preview.token);
    assert.deepEqual(committed.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [1, 0]);
    assert.equal(committed.watermarks.combat_log_cursor, 1);
    assert.deepEqual(committed.combatLog, []);
});
test("normal presentation preview is immutable, exact-head bound, and token committed once", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    journal.ingest({ event: "frame", id: "normal-1", data: frameDelivery() });
    const first = journal.previewPresentationFrame(1);
    const repeated = journal.previewPresentationFrame(1);
    assert.equal(repeated, first);
    assert.equal(Object.isFrozen(first), true);
    assert.equal(Object.isFrozen(first.frame), true);
    assert.equal(Object.isFrozen(first.candidatePresentation), true);
    assert.throws(() => first.frame.patches.push({}), TypeError);
    assert.deepEqual(heroPosition(journal, "presentation"), [0, 0]);
    journal.commitPresentationFrame(first.token);
    assert.deepEqual(heroPosition(journal, "presentation"), [1, 0]);
    assert.throws(() => journal.commitPresentationFrame(first.token), Error);
});
test("presentation head tokens are private, nonserializable, and journal-local", () => {
    const firstJournal = new SubjectiveReplicationJournal();
    const secondJournal = new SubjectiveReplicationJournal();
    firstJournal.bootstrap(bootstrap());
    secondJournal.bootstrap(bootstrap());
    firstJournal.ingest({ event: "frame", id: "first", data: frameDelivery() });
    secondJournal.ingest({ event: "frame", id: "second", data: frameDelivery() });
    const first = firstJournal.previewPresentationFrame(1);
    const second = secondJournal.previewPresentationFrame(1);
    assert.throws(() => JSON.stringify(first.token), TypeError);
    assert.throws(() => secondJournal.commitPresentationFrame(first.token), Error);
    assert.deepEqual(heroPosition(secondJournal, "presentation"), [0, 0]);
    secondJournal.commitPresentationFrame(second.token);
    assert.deepEqual(heroPosition(secondJournal, "presentation"), [1, 0]);
});
test("reset head applies only through its exact token and never advances cue cursor", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    const reset = resetFrame(1);
    assert.equal(journal.ingest({
        event: "frame",
        id: "reset-1",
        data: { kind: "frame", frame: reset },
    }).status, "applied");
    assert.equal(journal.state().pendingResetFrames, 1);
    assert.throws(() => journal.previewPresentationFrame(1), Error);
    const head = journal.inspectResetPresentationHead(1);
    assert.equal(Object.isFrozen(head), true);
    assert.equal(Object.isFrozen(head.frame), true);
    assert.throws(() => JSON.stringify(head.token), TypeError);
    assert.throws(() => journal.resetPresentationFrame({}), Error);
    assert.deepEqual(heroPosition(journal, "presentation"), [0, 0]);
    const applied = journal.resetPresentationFrame(head.token);
    assert.deepEqual(applied.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [1, 0]);
    assert.equal(applied.watermarks.presentation_cursor, 0);
    assert.equal(journal.state().pendingResetFrames, 0);
    assert.throws(() => journal.resetPresentationFrame(head.token), Error);
});
test("legal combat-log delivery does not stale an active RESET head token", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    assert.equal(journal.ingest({
        event: "frame",
        id: "reset-head-before-log",
        data: { kind: "frame", frame: resetFrame(1) },
    }).status, "applied");
    const head = journal.inspectResetPresentationHead(1);
    const resetCompatibleLog = hiddenLogDelivery();
    assert.equal(journal.ingest({
        event: "combat_log",
        id: "reset-head-log",
        data: {
            ...resetCompatibleLog,
            watermarks: {
                ...resetCompatibleLog.watermarks,
                presentation_cursor: 0,
            },
        },
    }).status, "applied");
    assert.equal(journal.state().presentation?.watermarks.combat_log_cursor, 0);
    const reset = journal.resetPresentationFrame(head.token);
    assert.deepEqual(reset.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [1, 0]);
    assert.equal(reset.watermarks.presentation_cursor, 0);
    assert.equal(reset.watermarks.combat_log_cursor, 1);
    assert.deepEqual(reset.combatLog, []);
});
test("reset backlog count remains exact across consecutive reset consumption and replacement", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    for (const cursor of [1, 2]) {
        assert.equal(journal.ingest({
            event: "frame",
            id: `reset-${cursor}`,
            data: { kind: "frame", frame: resetFrame(cursor) },
        }).status, "applied");
    }
    assert.equal(journal.state().pendingResetFrames, 2);
    const first = journal.inspectResetPresentationHead(1);
    journal.resetPresentationFrame(first.token);
    assert.equal(journal.state().pendingResetFrames, 1);
    journal.bootstrap(bootstrap("generation-b"));
    assert.equal(journal.state().pendingResetFrames, 0);
});
test("reset backlog count is duplicate-safe, compaction-safe, and invalidation-safe", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    const frames = Array.from({ length: 1_025 }, (_, index) => ({
        ...resetFrame(index + 1),
        patches: [],
    }));
    for (const frame of frames) {
        assert.equal(journal.ingest({
            event: "frame",
            id: `reset-count-${frame.watermarks.observation_cursor}`,
            data: { kind: "frame", frame },
        }).status, "applied");
    }
    assert.equal(journal.ingest({
        event: "frame",
        id: "reset-count-duplicate",
        data: { kind: "frame", frame: frames[1_024] },
    }).status, "duplicate");
    assert.equal(journal.state().pendingResetFrames, 1_025);
    for (let cursor = 1; cursor <= 1_024; cursor += 1) {
        const head = journal.inspectResetPresentationHead(cursor);
        journal.resetPresentationFrame(head.token);
    }
    assert.equal(journal.state().pendingResetFrames, 1);
    const internals = journal;
    assert.equal(internals.pendingFrameHead, 0);
    assert.equal(internals.pendingFrames.length, 1);
    journal.invalidate("generation_changed");
    assert.equal(journal.state().pendingResetFrames, 0);
});
test("frame semantics keep NORMAL and RESET_REQUIRED authorities disjoint", () => {
    const normal = replicationFrame();
    const reset = resetFrame(1);
    assert.doesNotThrow(() => assertSubjectiveFrame(normal));
    assert.doesNotThrow(() => assertSubjectiveFrame(reset));
    assert.throws(() => assertSubjectiveFrame({
        ...normal,
        presentation_reset_reason: "source_presentation_discontinuity",
    }), ContractValidationError);
    assert.throws(() => assertSubjectiveFrame({
        ...reset,
        presentation: normal.presentation,
    }), ContractValidationError);
    assert.throws(() => assertSubjectiveFrame({
        ...reset,
        watermarks: { ...reset.watermarks, presentation_cursor: 1 },
    }), ContractValidationError);
});
test("terminal reset authority exactly binds the final source slot and ended encounter", () => {
    const valid = terminalResetFrame();
    assert.doesNotThrow(() => assertSubjectiveFrame(valid));
    assert.throws(() => assertSubjectiveFrame({
        ...valid,
        encounter_terminal: {
            ...valid.encounter_terminal,
            terminal_authority_id: "forged",
        },
    }), ContractValidationError);
    assert.throws(() => assertSubjectiveFrame({
        ...valid,
        encounter_terminal: {
            ...valid.encounter_terminal,
            source_event_cursor: 2,
        },
    }), ContractValidationError);
    assert.throws(() => assertSubjectiveFrame({ ...valid, encounter_terminal: null }), ContractValidationError);
});
test("normal terminal cue exactly matches the final source and ended encounter patch", () => {
    const valid = normalTerminalFrame();
    assert.doesNotThrow(() => assertSubjectiveFrame(valid));
    assert.throws(() => assertSubjectiveFrame({
        ...valid,
        watermarks: { ...valid.watermarks, source_event_cursor: 2 },
    }), ContractValidationError);
    assert.throws(() => assertSubjectiveFrame({ ...valid, patches: [] }), ContractValidationError);
    assert.throws(() => assertSubjectiveFrame({
        ...valid,
        presentation: replicationFrame().presentation,
    }), ContractValidationError);
});
test("ordinary and reset terminal authority require the final reduced encounter to remain ended", () => {
    for (const valid of [normalTerminalFrame(), terminalResetFrame()]) {
        const ended = valid.patches.find((patch) => (patch.kind === "encounter_replace"
            && patch.encounter !== null
            && patch.encounter.state === "ended"));
        assert.ok(ended?.kind === "encounter_replace" && ended.encounter !== null);
        for (const finalEncounter of [
            { ...ended.encounter, state: "active" },
            null,
        ]) {
            assert.throws(() => assertSubjectiveFrame({
                ...valid,
                patches: [
                    ...valid.patches,
                    { kind: "encounter_replace", encounter: finalEncounter },
                ],
            }), ContractValidationError);
        }
    }
});
test("NORMAL head retains one immutable accepted frame despite caller mutation after ingest", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    const frame = replicationFrame();
    assert.equal(journal.ingest({
        event: "frame",
        id: "normal-mutable-input",
        data: { kind: "frame", frame },
    }).status, "applied");
    const mutable = frame;
    mutable.patches[0].entity.position = [99, 99];
    mutable.presentation[0].anchors[1].position = [88, 88];
    const preview = journal.previewPresentationFrame(1);
    assert.deepEqual(preview.frame.presentation[0]?.kind === "movement"
        ? preview.frame.presentation[0].anchors[1]?.position
        : null, [1, 0]);
    assert.deepEqual(preview.candidatePresentation.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [1, 0]);
});
test("RESET head retains one immutable accepted frame despite caller mutation after ingest", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    const frame = resetFrame(1);
    assert.equal(journal.ingest({
        event: "frame",
        id: "reset-mutable-input",
        data: { kind: "frame", frame },
    }).status, "applied");
    const mutable = frame;
    mutable.patches[0].entity.position = [99, 99];
    mutable.presentation_reset_reason = null;
    const head = journal.inspectResetPresentationHead(1);
    assert.equal(head.frame.presentation_reset_reason, "source_presentation_discontinuity");
    const applied = journal.resetPresentationFrame(head.token);
    assert.deepEqual(applied.world.state.entities.find((entity) => entity.uuid === "hero")?.position, [1, 0]);
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
    assert.throws(() => decodeSubjectiveEnvelope({ event: "game_event", id: "s=0;o=0;p=0;l=0", data: {} }), ContractValidationError);
    assert.throws(() => decodeSubjectiveEnvelope({
        event: "sync",
        id: "s=9;o=9;p=9;l=9",
        data: parseJson(JSON.stringify(syncDelivery())),
    }), ContractValidationError);
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
            event: "sync",
            id: "s=2;o=2;p=2;l=2",
            data: { ...syncDelivery(2), watermarks: watermarks(2, 2, 2, 2) },
        },
        {
            event: "frame",
            id: "s=1;o=1;p=1;l=0",
            data: frameDelivery(1),
        },
        {
            event: "combat_log",
            id: "s=1;o=1;p=1;l=1",
            data: hiddenLogDelivery(1, 1),
        },
        {
            event: "frame",
            id: "s=2;o=2;p=2;l=1",
            data: {
                kind: "frame",
                frame: {
                    ...secondFrame,
                    watermarks: watermarks(2, 2, 2, 1),
                },
            },
        },
        {
            event: "combat_log",
            id: "s=2;o=2;p=2;l=2",
            data: hiddenLogDelivery(2, 2),
        },
    ];
    for (const envelope of envelopes)
        follower.ingest(envelope);
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
        presentation: [{ ...second.presentation[0], presentation_id: "presentation-1" }],
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
    assert.throws(() => decodeAlias("SubjectiveWorldPatch", { kind: "mystery", data: {} }), ContractValidationError);
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
test("REST frame pages cannot reduce state outside the SDK client journal catch-up", () => {
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
    const cases = [
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
        assert.throws(() => decodeSubjectiveEnvelope({
            event: "frame",
            id: "s=1;o=1;p=1;l=0",
            data: parseJson(JSON.stringify({ kind: "frame", frame })),
        }), ContractValidationError);
    }
});
test("follow reset publishes the exact single-fetch bootstrap passed to the journal", async () => {
    const controller = new AbortController();
    const journal = new RecordingJournal();
    let bootstrapRequests = 0;
    const seed = bootstrap();
    const sparseBootstrap = {
        ...seed,
        watermarks: watermarks(1, 0, 0, 1),
        combat_log_frames: {
            ...seed.combat_log_frames,
            through_cursor: 1,
            frames: [hiddenLogDelivery(1, 1).frame],
            total: 1,
        },
    };
    const resets = [];
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async (input) => {
            const url = String(input);
            if (url.includes("/replication/bootstrap")) {
                bootstrapRequests += 1;
                return jsonResponse(sparseBootstrap);
            }
            return new Response(encode("sync", "s=1;o=0;p=0;l=1", { ...syncDelivery(0), watermarks: watermarks(1, 0, 0, 1) }), {
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
    const resets = [];
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async (input) => {
            if (String(input).includes("/replication/bootstrap")) {
                bootstrapRequests += 1;
                throw new Error("follow must not refetch its caller-owned seed");
            }
            return new Response(encode("sync", "s=0;o=0;p=0;l=0", syncDelivery(0)), {
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
    const resets = [];
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
test("follow propagates an initial generic bootstrap 409 after exactly one request", async () => {
    const controller = new AbortController();
    const payload = genericReplicationIdentityConflict();
    let bootstrapRequests = 0;
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            bootstrapRequests += 1;
            if (bootstrapRequests > 1)
                controller.abort();
            return jsonResponse(payload, 409);
        },
    });
    await assert.rejects(() => client.follow(new SubjectiveReplicationJournal(), {
        sessionId: "session-a",
        signal: controller.signal,
        initialReconnectDelayMs: 0,
        maximumReconnectDelayMs: 0,
    }), (error) => {
        if (!(error instanceof SubjectiveReplicationHttpError))
            return false;
        assert.equal(error.status, 409);
        assert.deepEqual(error.payload, payload);
        return true;
    });
    assert.equal(bootstrapRequests, 1);
});
test("follow propagates a replacement-bootstrap generic 409 without looping", async () => {
    const controller = new AbortController();
    const payload = genericReplicationIdentityConflict();
    let bootstrapRequests = 0;
    let subscribeRequests = 0;
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async (input) => {
            if (String(input).includes("/replication/bootstrap")) {
                bootstrapRequests += 1;
                if (bootstrapRequests > 1)
                    controller.abort();
            }
            else {
                subscribeRequests += 1;
            }
            return jsonResponse(payload, 409);
        },
    });
    await assert.rejects(() => client.follow(new SubjectiveReplicationJournal(), {
        sessionId: "session-a",
        initialBootstrap: bootstrap(),
        signal: controller.signal,
        initialReconnectDelayMs: 0,
        maximumReconnectDelayMs: 0,
    }), (error) => {
        if (!(error instanceof SubjectiveReplicationHttpError))
            return false;
        assert.equal(error.status, 409);
        assert.deepEqual(error.payload, payload);
        return true;
    });
    assert.equal(subscribeRequests, 1);
    assert.equal(bootstrapRequests, 1);
});
test("follow preserves an explicit journal invalidation reason on reentry", async () => {
    const controller = new AbortController();
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    journal.invalidate("perspective_epoch_changed");
    const resets = [];
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
    let receiver = null;
    const fetchImplementation = async function () {
        receiver = this;
        return jsonResponse(bootstrap());
    };
    const client = new SubjectiveReplicationClient("/api", { fetchImplementation });
    await client.bootstrap("session-a");
    assert.equal(receiver, globalThis);
});
test("follow resync fetches one new seed after consuming the exact initial bootstrap", async () => {
    const controller = new AbortController();
    const journal = new RecordingJournal();
    let bootstrapRequests = 0;
    const initialSeed = bootstrap("generation-a");
    const resets = [];
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
            if (value.reason !== "initial_bootstrap")
                controller.abort();
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
    const resets = [];
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
            if (value.reason !== "initial_bootstrap")
                controller.abort();
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
        await assert.rejects(() => client.follow(journal, {
            sessionId: "session-a",
            onUpdate: async ({ envelope }) => {
                if (envelope.event === "frame")
                    throw failure;
            },
            initialReconnectDelayMs: 0,
            maximumReconnectDelayMs: 0,
        }), (error) => error === failure);
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
        await assert.rejects(() => client.follow(new SubjectiveReplicationJournal(), {
            sessionId: "session-a",
            onReplicaReset: async () => { throw failure; },
            initialReconnectDelayMs: 0,
            maximumReconnectDelayMs: 0,
        }), (error) => error === failure);
        assert.equal(bootstrapRequests, 1);
        assert.equal(subscribeRequests, 0);
    }
});
test("duplicate payload storage is retention-bounded while presentation IDs remain epoch-global", () => {
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(bootstrap());
    const internals = journal;
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
            frame: boundedReplicationFrame(2, 1, "bounded-presentation-1"),
        },
    });
    assert.equal(reuse.state.health, "resync_required");
    assert.equal(reuse.state.resyncReason, "presentation_id_reused");
});
test("the subjective wire gate accepts every canonical presentation and area kind", () => {
    const validGraphs = [
        [movementCue()],
        [movementCue({ locomotion_family: "swim" })],
        [movementCue({ locomotion_family: "fly" })],
        [movementCue({ locomotion_family: "burrow" })],
        [movementCue({ locomotion_family: "jump", trajectory_family: "direct_arc" })],
        [movementCue({
                locomotion_family: "connector",
                trajectory_family: "connector_transfer",
                connector: {
                    uuid: "00000000-0000-4000-8000-000000000010",
                    authored_id: "connector.fixture.ladder",
                    kind: "ladder",
                    presentation_key: "traversal.ladder",
                    revision: 1,
                },
            })],
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
test("spell position application accepts a created spatial effect in current geometry", () => {
    assert.doesNotThrow(() => decodePresentationGraph(spellSpatialEffectGraph({
        operation: "created",
        anchor_position: [0, 0],
        affected_positions: [[0, 0], [0, 1]],
        previous_positions: [],
    }, { position: [0, 1] })));
});
test("spell position application accepts a removed spatial effect in previous geometry", () => {
    assert.doesNotThrow(() => decodePresentationGraph(spellSpatialEffectGraph({
        operation: "removed",
        anchor_position: [2, 0],
        affected_positions: [],
        previous_positions: [[2, 0], [2, 1]],
    }, { position: [2, 1] })));
});
test("spell applications require unique disclosed ordinals but allow repeated null ownership", () => {
    assert.doesNotThrow(() => decodePresentationGraph([spellCue({
            targets: [spellTarget(0, null), spellTarget(1, null)],
        })]));
    assert.throws(() => decodePresentationGraph([spellCue({
            targets: [spellTarget(0, null), spellTarget(0, null)],
        })]), ContractValidationError);
});
test("spell application membership is independent of causal presentation edges", () => {
    const applicationId = "00000000-0000-4000-8000-000000000001";
    const severedMember = [
        spellCue({
            targets: [spellTarget(0, applicationId, ["damage"])],
        }),
        {
            ...damageCue("damage", 2, null),
            owner_application_id: applicationId,
        },
    ];
    assert.doesNotThrow(() => decodePresentationGraph(severedMember));
    assert.throws(() => decodePresentationGraph([
        severedMember[0],
        { ...severedMember[1], owner_application_id: null },
    ]), ContractValidationError);
    assert.throws(() => decodePresentationGraph([severedMember[0]]), ContractValidationError);
});
test("spell position applications reject delivered non-spatial effect children", () => {
    const lawfulCases = [
        [
            "damage",
            spellNonSpatialEffectGraph("damage", "monster", damageCue("damage", 2, "spell")),
        ],
        [
            "heal",
            spellNonSpatialEffectGraph("heal", "hero", healCue("heal", 2, "spell")),
        ],
        [
            "condition",
            spellNonSpatialEffectGraph("condition", "monster", conditionCue("condition", 2, "spell")),
        ],
        [
            "forced movement",
            spellNonSpatialEffectGraph("forced", "monster", {
                ...cueBase("forced_movement", "forced", 2, "spell"),
                entity_uuid: "monster",
                source_uuid: "hero",
                cause: "spell",
                actor_action_presentation_id: "spell",
                start_position: [0, 0],
                end_position: [1, 0],
                duration_ms: 100,
                target_clip: "TakeDamage",
                brace_frame: 1,
                playback_speed: 1,
            }),
        ],
    ];
    for (const [name, lawfulGraph] of lawfulCases) {
        assert.doesNotThrow(() => decodePresentationGraph(lawfulGraph), `${name} lawful entity-target baseline`);
        const spell = lawfulGraph[0];
        const applications = spell.targets;
        const positionOnlyGraph = [
            {
                ...spell,
                targets: applications.map((application) => ({
                    ...application,
                    target_uuid: null,
                    position: [4, 4],
                })),
            },
            ...lawfulGraph.slice(1),
        ];
        assert.throws(() => decodePresentationGraph(positionOnlyGraph), ContractValidationError, name);
    }
});
test("spell-owned spatial effects reject entity ownership and undisclosed positions", () => {
    const cases = [
        [
            "entity-owned spatial application",
            spellSpatialEffectGraph({}, { target_uuid: "monster" }),
        ],
        [
            "spatial application outside disclosed geometry",
            spellSpatialEffectGraph({}, { position: [9, 9] }),
        ],
    ];
    for (const [name, graph] of cases) {
        assert.throws(() => decodePresentationGraph(graph), ContractValidationError, name);
    }
});
test("generated field constraints reject invalid presentation scalars at the wire gate", () => {
    const cases = [
        ["empty ID", [{ ...movementCue(), presentation_id: "" }]],
        ["zero source cursor", [{ ...movementCue(), source_event_cursor: 0 }]],
        ["fractional elevation", [{ ...movementCue(), anchors: [{ position: [0, 0], elevation_feet: 0.5 }, { position: [1, 0], elevation_feet: 0 }] }]],
        ["short anchors", [{ ...movementCue(), anchors: [{ position: [0, 0], elevation_feet: 0 }] }]],
        ["retired movement field", [{ ...movementCue(), movement_kind: "walk" }]],
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
    const cases = [
        ["path movement with direct arc", [{ ...movementCue(), trajectory_family: "direct_arc" }]],
        ["Jump with PATH", [{ ...movementCue(), locomotion_family: "jump" }]],
        ["connector without identity", [{
                    ...movementCue(),
                    locomotion_family: "connector",
                    trajectory_family: "connector_transfer",
                }]],
        ["path movement with connector identity", [{
                    ...movementCue(),
                    connector: {
                        uuid: "00000000-0000-4000-8000-000000000010",
                        authored_id: "connector.fixture.ladder",
                        kind: "ladder",
                        presentation_key: "traversal.ladder",
                        revision: 1,
                    },
                }]],
        ["uncommitted movement without reaction", [{ ...movementCue(), endpoint_outcome: "not_committed" }]],
        ["uncommitted multi-edge movement", movementReactionGraph({
                movement: {
                    endpoint_outcome: "not_committed",
                    anchors: [
                        { position: [0, 0], elevation_feet: 0 },
                        { position: [1, 0], elevation_feet: 0 },
                        { position: [2, 0], elevation_feet: 0 },
                    ],
                },
            })],
        ["duplicate action target", [{ ...actionCue(), target_uuids: ["hero", "hero"] }]],
        ["action child mismatch", [{ ...actionCue(), effect_presentation_ids: ["missing"] }]],
        ["action self trigger", [{ ...actionCue(), trigger_presentation_id: "action" }]],
        ["action without exact behavior", [{ ...actionCue(), binding_subject: null }]],
        ["duplicate attack damage types", [{ ...attackCue(), damage_types: ["Fire", "Fire"] }]],
        ["projectile attack without projectile", [{ ...attackCue(), delivery: "projectile", projectile_type: null }]],
        ["melee attack with projectile", [{ ...attackCue(), projectile_type: "bolt" }]],
        ["attack impact mismatch", [{ ...attackCue(), impact_effect_presentation_ids: ["missing"] }]],
        ["zero cone direction", [spellCue({ delivery: "aoe", area: { shape: "cone", origin: [0, 0], direction: [0, 0], length_feet: 15, angle_degrees: 90 } })]],
        ["zero line direction", [spellCue({ delivery: "aoe", area: { shape: "line", origin: [0, 0], direction: [0, 0], length_feet: 15, width_feet: 5 } })]],
        ["centered cube direction", [spellCue({ delivery: "aoe", area: { shape: "cube", origin: [0, 0], direction: [1, 0], size_feet: 10, centered: true } })]],
        ["directionless cube", [spellCue({ delivery: "aoe", area: { shape: "cube", origin: [0, 0], direction: null, size_feet: 10, centered: false } })]],
        ["target without entity or position", [spellCue({ targets: [{ ...spellTarget(), target_uuid: null, position: null }] })]],
        ["position target with dangling effect child", [spellCue({ targets: [{ ...spellTarget(), target_uuid: null, position: [1, 1], effect_presentation_ids: ["effect"] }], child_presentation_ids: ["effect"] })]],
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
                    trigger_binding_subject: null,
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
    const cases = [
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
test("alive-to-alive life-state evidence remains a valid reducer-only cue", () => {
    assert.doesNotThrow(() => decodePresentationGraph(lifecycleGraph({ cause_kind: "direct_state_check", source_uuid: null }, { previous: "alive", current: "alive", reason: "direct_state_check" })));
    assert.throws(() => decodePresentationGraph(lifecycleGraph({ cause_kind: "direct_state_check", source_uuid: null }, { previous: "stable", current: "stable", reason: "direct_state_check" })), ContractValidationError);
});
test("effectless lifecycle cause remains a valid reducer-only envelope", () => {
    assert.doesNotThrow(() => decodePresentationGraph([{
            ...cueBase("lifecycle_cause", "cause", 1, null, []),
            entity_uuid: "monster",
            cause_kind: "direct_state_check",
            source_uuid: null,
            death_save_outcome: null,
        }]));
});
test("life-state transition survives with an exactly severed nullable cause", () => {
    assert.doesNotThrow(() => decodePresentationGraph([{
            ...cueBase("life_state", "life", 1, null),
            entity_uuid: "monster",
            previous: "alive",
            current: "dying",
            reason: "damage",
            causing_effect_presentation_id: null,
        }]));
});
function cueBase(kind, id, cursor = 1, parent = null, children = []) {
    return {
        presentation_cursor: cursor,
        presentation_id: id,
        parent_presentation_id: parent,
        child_presentation_ids: [...children],
        source_event_cursor: 1,
        source_event_uuid: `event-${id}`,
        binding_subject: actionableBindingSubject(kind),
        trigger_binding_subject: null,
        source_item_fact: null,
        owner_application_id: null,
        kind,
    };
}
function movementCue(overrides = {}) {
    return {
        ...cueBase("movement", "movement"),
        entity_uuid: "hero",
        locomotion_family: "walk",
        trajectory_family: "path",
        anchors: [
            { position: [0, 0], elevation_feet: 0 },
            { position: [1, 0], elevation_feet: 0 },
        ],
        connector: null,
        endpoint_outcome: "committed",
        perception_commit: "observation_frame",
        ...overrides,
    };
}
function resetFrame(cursor) {
    return {
        ...replicationFrame(cursor),
        watermarks: watermarks(cursor, cursor, 0, 0),
        presentation_from_cursor: 0,
        presentation: [],
        presentation_delivery: "presentation_reset_required",
        presentation_reset_reason: "source_presentation_discontinuity",
        encounter_terminal: null,
    };
}
function terminalResetFrame(cursor = 1) {
    const sourceEventUuid = "00000000-0000-4000-8000-000000000001";
    const seed = bootstrap();
    const encounter = seed.world.state.encounter;
    assert.notEqual(encounter, null);
    return {
        ...resetFrame(cursor),
        patches: [{
                kind: "encounter_replace",
                encounter: { ...encounter, state: "ended" },
            }],
        encounter_terminal: {
            encounter_uuid: encounter.uuid,
            source_event_uuid: sourceEventUuid,
            source_event_cursor: cursor,
            terminal_authority_id: `perspective-a:${cursor}:reset-terminal:${sourceEventUuid}`,
            reason: "victory",
            projected_combatant_uuids: ["hero", "monster"],
            terminal_barrier: true,
        },
    };
}
function normalTerminalFrame() {
    const seedEncounter = bootstrap().world.state.encounter;
    assert.notEqual(seedEncounter, null);
    return {
        ...replicationFrame(),
        patches: [{
                kind: "encounter_replace",
                encounter: { ...seedEncounter, state: "ended" },
            }],
        presentation: [encounterCue()],
    };
}
function actionCue(overrides = {}) {
    return {
        ...cueBase("action", "action"),
        actor_uuid: "hero",
        action_name: "Rage",
        target_uuids: ["hero"],
        trigger_presentation_id: null,
        effect_presentation_ids: [],
        ...overrides,
    };
}
function attackCue(overrides = {}) {
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
function spellTarget(applicationIndex = 0, applicationId = "application-0", effects = []) {
    return {
        disclosed_index: applicationIndex,
        application_id: applicationId,
        outcome: "automatic",
        target_uuid: "monster",
        position: null,
        effect_presentation_ids: [...effects],
    };
}
function spellCue(overrides = {}) {
    return {
        ...cueBase("spell", "spell"),
        actor_uuid: "hero",
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
function itemCue(overrides = {}) {
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
function counterspellCue(overrides = {}) {
    return {
        ...cueBase("counterspell", "counterspell"),
        trigger_binding_subject: {
            kind: "public_definition",
            use: "trigger_behavior",
            ref: contentRef("spell.fireball", "spell"),
        },
        reactor_uuid: "hero",
        incoming_caster_uuid: "monster",
        incoming_spell_level: 3,
        counterspell_slot_level: 3,
        resolution: { kind: "automatic_success" },
        ...overrides,
    };
}
function spatialEffectCue(overrides = {}) {
    return {
        ...cueBase("spatial_effect", "spatial-effect"),
        effect_uuid: "effect",
        content_ref: contentRef("spatial_effect.spell.entangle", "spatial_effect"),
        operation: "created",
        layer: "field",
        anchor_position: [0, 0],
        affected_positions: [[0, 0], [0, 1]],
        previous_positions: [],
        ...overrides,
    };
}
function spellSpatialEffectGraph(effectOverrides = {}, applicationOverrides = {}) {
    return [
        spellCue({
            ...cueBase("spell", "spell", 1, null, ["spatial-effect"]),
            targets: [{
                    ...spellTarget(0, "application-0", ["spatial-effect"]),
                    target_uuid: null,
                    position: [0, 0],
                    ...applicationOverrides,
                }],
        }),
        spatialEffectCue({
            ...cueBase("spatial_effect", "spatial-effect", 2, "spell"),
            owner_application_id: "application-0",
            ...effectOverrides,
        }),
    ];
}
function spellNonSpatialEffectGraph(effectId, targetUuid, effect) {
    return [
        spellCue({
            ...cueBase("spell", "spell", 1, null, [effectId]),
            targets: [{
                    ...spellTarget(0, "application-0", [effectId]),
                    target_uuid: targetUuid,
                }],
        }),
        { ...effect, owner_application_id: "application-0" },
    ];
}
function contentRef(contentId, definitionKind) {
    return {
        pack_id: "content.srd_5_1_cc",
        definition_kind: definitionKind,
        content_id: contentId,
        content_version: 1,
        definition_contract_hash: "a".repeat(64),
    };
}
function actionableBindingSubject(kind) {
    if (kind !== "movement"
        && kind !== "action"
        && kind !== "attack"
        && kind !== "spell"
        && kind !== "item_action"
        && kind !== "shove"
        && kind !== "counterspell") {
        return null;
    }
    const definitionKind = kind === "spell" ? "spell" : kind === "counterspell" ? "reaction" : "action";
    const contentId = kind === "counterspell" ? "reaction.spell.counterspell" : `action.${kind}`;
    return {
        kind: "public_definition",
        use: "behavior",
        ref: contentRef(contentId, definitionKind),
    };
}
function shoveCue(overrides = {}) {
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
function damageCue(id, cursor, parent) {
    return {
        ...cueBase("damage", id, cursor, parent),
        source_uuid: "hero",
        target_uuid: "monster",
        applied_amount: 3,
        resulting_hp: 7,
        damage_types: ["Slashing"],
    };
}
function healCue(id, cursor, parent) {
    return {
        ...cueBase("heal", id, cursor, parent),
        source_uuid: "hero",
        target_uuid: "hero",
        amount: 3,
        resulting_hp: 10,
    };
}
function conditionCue(id, cursor, parent) {
    return {
        ...cueBase("condition", id, cursor, parent),
        target_uuid: "monster",
        condition_ref: contentRef("condition.prone", "condition"),
        condition_semantic_key: "prone",
        condition_name: "Prone",
        condition_category: "condition",
        operation: "applied",
    };
}
function doorCue(overrides = {}) {
    return {
        ...cueBase("door", "door"),
        object_uuid: "door-1",
        position: [1, 1],
        is_open: true,
        ...overrides,
    };
}
function lightCue(overrides = {}) {
    return {
        ...cueBase("light", "light"),
        observer_uuid: "hero",
        mode: "replacement",
        cells: [{ position: [0, 0], light_level: 3 }],
        ...overrides,
    };
}
function equipmentCue(overrides = {}) {
    return {
        ...cueBase("equipment", "equipment"),
        entity_uuid: "hero",
        visual_loadout: { entity_uuid: "hero", active_weapon_set: "none", layers: [] },
        ...overrides,
    };
}
function encounterCue(overrides = {}) {
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
function forcedMovementGraph(overrides = {}) {
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
function lifecycleGraph(causeOverrides = {}, lifeOverrides = {}) {
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
function attackDamageGraph() {
    return [
        attackCue({
            ...cueBase("attack", "attack", 1, null, ["damage"]),
            outcome: "hit",
            impact_effect_presentation_ids: ["damage"],
        }),
        damageCue("damage", 2, "attack"),
    ];
}
function movementReactionGraph(options = {}) {
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
function spellDamageGraph() {
    return [
        spellCue({
            ...cueBase("spell", "spell", 1, null, ["damage"]),
            targets: [spellTarget(0, "application-0", ["damage"])],
        }),
        { ...damageCue("damage", 2, "spell"), owner_application_id: "application-0" },
    ];
}
function actionConditionGraph() {
    return [
        actionCue({
            ...cueBase("action", "action", 1, null, ["condition"]),
            effect_presentation_ids: ["condition"],
        }),
        {
            ...conditionCue("condition", 2, "action"),
            target_uuid: "hero",
        },
    ];
}
function reactiveActionTriggerGraph() {
    return [
        actionCue({
            ...cueBase("action", "reaction", 1),
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
function areaGeometries() {
    return [
        { shape: "sphere", center: [0, 0], radius_feet: 10 },
        { shape: "cone", origin: [0, 0], direction: [1, 0], length_feet: 15, angle_degrees: 90 },
        { shape: "line", origin: [0, 0], direction: [1, 0], length_feet: 30, width_feet: 5 },
        { shape: "cube", origin: [0, 0], direction: null, size_feet: 10, centered: true },
        { shape: "cylinder", center: [0, 0], radius_feet: 10, height_feet: 20 },
    ];
}
function decodePresentationGraph(presentation) {
    const count = presentation.length;
    const sourceEventCursor = Math.max(1, ...presentation.map((cue) => (typeof cue.source_event_cursor === "number"
        ? cue.source_event_cursor
        : 1)));
    const terminalCue = presentation.find((cue) => (cue.kind === "encounter" && cue.transition === "end"));
    const seedEncounter = bootstrap().world.state.encounter;
    const patches = terminalCue === undefined || seedEncounter === null
        ? []
        : [{
                kind: "encounter_replace",
                encounter: { ...seedEncounter, state: "ended" },
            }];
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
                patches,
                presentation,
                presentation_delivery: "normal",
                presentation_reset_reason: null,
                encounter_terminal: null,
            },
        })),
    });
}
test("REST frame catch-up feeds the canonical journal through one frozen captured target", async () => {
    const seed = bootstrap();
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(seed);
    const requests = [];
    const updates = [];
    const page = (from, through, captured) => ({
        source_stream_id: seed.protocol.source_stream_id,
        generation_id: seed.protocol.generation_id,
        perspective_epoch_id: seed.perspective.perspective_epoch_id,
        retained_from_observation_cursor: 0,
        from_watermarks: watermarks(from, from, from, 0),
        through_watermarks: watermarks(through, through, through, 0),
        captured_watermarks: watermarks(captured, captured, captured, 0),
        frames: Array.from({ length: through - from }, (_, index) => replicationFrame(from + index + 1)),
    });
    const first = page(0, 1, 3);
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async (input) => {
            const url = String(input);
            requests.push(url);
            const from = Number(new URL(url, "https://example.invalid")
                .searchParams.get("from_observation_cursor"));
            if (from === 1)
                return jsonResponse(page(1, 2, 4));
            if (from === 2)
                return jsonResponse(page(2, 4, 5));
            throw new Error(`unexpected continuation cursor ${from}`);
        },
    });
    const state = await client.ingestFramesThrough(journal, first, {
        sessionId: "session-a",
        fixedTarget: {
            sourceEventCursor: 3,
            observationCursor: 3,
            presentationCursor: 3,
        },
        onUpdate: ({ envelope, result }) => {
            assert.equal(envelope.event, "frame");
            assert.equal(result.status, "applied");
            updates.push(envelope.data.frame.watermarks.observation_cursor);
        },
    });
    assert.deepEqual(updates, [1, 2, 3]);
    assert.equal(state.authoritative?.watermarks.observation_cursor, 3);
    assert.equal(state.presentation?.watermarks.observation_cursor, 0);
    assert.equal(state.presentationBacklog, 3);
    assert.equal(requests.length, 2);
    assert.match(requests[0] ?? "", /from_observation_cursor=1/);
    assert.match(requests[1] ?? "", /from_observation_cursor=2/);
});
test("REST frame catch-up rejects a target not authored by its first page", async () => {
    const seed = bootstrap();
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(seed);
    const first = {
        source_stream_id: seed.protocol.source_stream_id,
        generation_id: seed.protocol.generation_id,
        perspective_epoch_id: seed.perspective.perspective_epoch_id,
        retained_from_observation_cursor: 0,
        from_watermarks: watermarks(),
        through_watermarks: watermarks(1, 1, 1, 0),
        captured_watermarks: watermarks(2, 2, 2, 0),
        frames: [replicationFrame(1)],
    };
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            throw new Error("forged target must fail before continuation fetch");
        },
    });
    await assert.rejects(() => client.ingestFramesThrough(journal, first, {
        sessionId: "session-a",
        fixedTarget: {
            sourceEventCursor: 2,
            observationCursor: 2,
            presentationCursor: 1,
        },
    }), ContractValidationError);
    assert.equal(journal.state().authoritative?.watermarks.observation_cursor, 0);
    assert.equal(journal.state().presentationBacklog, 0);
});
test("REST frame catch-up accepts an exact SSE duplicate without double-applying it", async () => {
    const seed = bootstrap();
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(seed);
    const alreadyAccepted = journal.ingest({
        event: "frame",
        id: "s=1;o=1;p=1;l=0",
        data: frameDelivery(1),
    });
    assert.equal(alreadyAccepted.status, "applied");
    const first = {
        source_stream_id: seed.protocol.source_stream_id,
        generation_id: seed.protocol.generation_id,
        perspective_epoch_id: seed.perspective.perspective_epoch_id,
        retained_from_observation_cursor: 0,
        from_watermarks: watermarks(),
        through_watermarks: watermarks(2, 2, 2, 0),
        captured_watermarks: watermarks(2, 2, 2, 0),
        frames: [replicationFrame(1), replicationFrame(2)],
    };
    const statuses = [];
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            throw new Error("duplicate overlap requires no continuation fetch");
        },
    });
    const state = await client.ingestFramesThrough(journal, first, {
        sessionId: "session-a",
        fixedTarget: {
            sourceEventCursor: 2,
            observationCursor: 2,
            presentationCursor: 2,
        },
        onUpdate: ({ result }) => {
            statuses.push(result.status);
            if (result.status === "duplicate") {
                const callerOwned = first;
                const later = callerOwned.frames[1];
                if (later !== undefined)
                    later.watermarks.observation_cursor = 99;
            }
        },
    });
    assert.deepEqual(statuses, ["duplicate", "applied"]);
    assert.equal(state.authoritative?.watermarks.observation_cursor, 2);
    assert.equal(state.presentationBacklog, 2);
});
test("REST frame catch-up honors an already-aborted owner before journal mutation", async () => {
    const seed = bootstrap();
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(seed);
    const first = {
        source_stream_id: seed.protocol.source_stream_id,
        generation_id: seed.protocol.generation_id,
        perspective_epoch_id: seed.perspective.perspective_epoch_id,
        retained_from_observation_cursor: 0,
        from_watermarks: watermarks(),
        through_watermarks: watermarks(1, 1, 1, 0),
        captured_watermarks: watermarks(1, 1, 1, 0),
        frames: [replicationFrame(1)],
    };
    const controller = new AbortController();
    controller.abort(new Error("catch-up owner retired"));
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            throw new Error("aborted catch-up must not fetch");
        },
    });
    await assert.rejects(() => client.ingestFramesThrough(journal, first, {
        sessionId: "session-a",
        fixedTarget: {
            sourceEventCursor: 1,
            observationCursor: 1,
            presentationCursor: 1,
        },
        signal: controller.signal,
    }), /catch-up owner retired/);
    assert.equal(journal.state().authoritative?.watermarks.observation_cursor, 0);
    assert.equal(journal.state().presentationBacklog, 0);
});
test("REST frame catch-up reports an exact typed journal resync", async () => {
    const seed = bootstrap();
    const journal = new SubjectiveReplicationJournal();
    journal.bootstrap(seed);
    const invalidFrame = {
        ...replicationFrame(1),
        watermarks: watermarks(1, 1, 1, 1),
    };
    const first = {
        source_stream_id: seed.protocol.source_stream_id,
        generation_id: seed.protocol.generation_id,
        perspective_epoch_id: seed.perspective.perspective_epoch_id,
        retained_from_observation_cursor: 0,
        from_watermarks: watermarks(),
        through_watermarks: watermarks(1, 1, 1, 1),
        captured_watermarks: watermarks(1, 1, 1, 1),
        frames: [invalidFrame],
    };
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            throw new Error("resync must not attempt continuation fetch");
        },
    });
    let callbackHealth = "";
    await assert.rejects(() => client.ingestFramesThrough(journal, first, {
        sessionId: "session-a",
        fixedTarget: {
            sourceEventCursor: 1,
            observationCursor: 1,
            presentationCursor: 1,
        },
        onUpdate: ({ result }) => { callbackHealth = result.state.health; },
    }), (error) => (error instanceof SubjectiveFrameCatchupResyncError
        && error.reason === "observation_cursor_gap"
        && error.state.health === "resync_required"));
    assert.equal(callbackHealth, "resync_required");
    assert.equal(journal.state().health, "resync_required");
});
function encode(event, id, data) {
    return `id: ${id}\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}
function boundedReplicationFrame(cursor, combatLogCursor, presentationId = `bounded-presentation-${cursor}`) {
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
                anchors: [
                    { position: [0, 0], elevation_feet: 0 },
                    { position: [1, 0], elevation_feet: 0 },
                ],
            }],
    };
}
function callbackFailures() {
    return [
        new TypeError("callback type failure"),
        new SyntaxError("callback syntax failure"),
        new ContractValidationError("$callback", "callback contract failure"),
    ];
}
function genericReplicationIdentityConflict() {
    return {
        detail: {
            code: "replication_identity_changed",
            message: "explicit encounter is not the runtime subscribed source",
            expected_source_stream_id: null,
            expected_generation_id: null,
            expected_perspective_epoch_id: null,
        },
    };
}
function jsonResponse(value, status = 200) {
    return new Response(JSON.stringify(value), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}
class RecordingJournal extends SubjectiveReplicationJournal {
    lastBootstrap = null;
    bootstrap(seed) {
        this.lastBootstrap = seed;
        return super.bootstrap(seed);
    }
}
//# sourceMappingURL=replication.test.js.map