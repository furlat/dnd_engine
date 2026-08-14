import assert from "node:assert/strict";
import test from "node:test";
import { DndEngineClient } from "../client.js";
import { GameDirectoryClient } from "../directoryClient.js";
import { SubjectiveReplicationClient } from "../subjectiveClient.js";
import { ContractValidationError } from "../validation.js";
import { bootstrap } from "./fixtures.js";
test("server capability probe distinguishes hosted and standalone topology", async () => {
    const urls = [];
    const fetchImplementation = async (input) => {
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
    const urls = [];
    const fetchImplementation = async (input) => {
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
    const urls = [];
    const fetchImplementation = async (input) => {
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
    assert.equal(actions.self_actions[0]?.binding_subject.kind === "public_definition"
        && actions.self_actions[0].binding_subject.ref.content_id, "action.dash");
    assert.equal(actions.execution_authorization, "not_active_turn");
    assert.equal(actions.handler_details[0]?.binding_subject.kind === "public_definition"
        && actions.handler_details[0].binding_subject.ref.content_id, "reaction.lucky");
    assert.equal(handlers.handlers[0]?.binding_subject.kind === "public_definition"
        && handlers.handlers[0].binding_subject.ref.content_id, "reaction.lucky");
    assert.deepEqual(urls, [
        "/api/entity/entity%2Fa/available-actions?session_id=session%2Fa+b",
        "/api/entity/entity%2Fa/equippable-items?session_id=session%2Fa+b",
        "/api/entity/entity%2Fa/handlers?session_id=session%2Fa+b",
    ]);
});
test("affordance decoders accept only exact tagged binding subjects", async () => {
    const action = availableAction();
    const handler = availableHandler();
    const { binding_subject: _actionBinding, source_item_fact: _sourceItem, ...oldActionBody } = action;
    const oldAction = {
        ...oldActionBody,
        behavior_attribution: behaviorAttribution("action", "action.dash"),
        configured_action_ref: null,
    };
    const mixedAction = {
        ...action,
        behavior_attribution: behaviorAttribution("action", "action.dash"),
        configured_action_ref: null,
    };
    for (const row of [oldAction, mixedAction]) {
        const client = engineClientReturning(availableActionsPayload([row]));
        await assert.rejects(client.getAvailableActions("entity-a", "session-a"), ContractValidationError);
    }
    const { binding_subject: _handlerBinding, ...oldHandlerBody } = handler;
    const oldHandler = {
        ...oldHandlerBody,
        behavior_attribution: behaviorAttribution("reaction", "reaction.lucky"),
    };
    const mixedHandler = {
        ...handler,
        behavior_attribution: behaviorAttribution("reaction", "reaction.lucky"),
    };
    for (const row of [oldHandler, mixedHandler]) {
        const availableActionsClient = engineClientReturning(availableActionsPayload([], [row]));
        await assert.rejects(availableActionsClient.getAvailableActions("entity-a", "session-a"), ContractValidationError);
        const handlersClient = engineClientReturning({ entity_uuid: "entity-a", handlers: [row] });
        await assert.rejects(handlersClient.getEntityHandlers("entity-a", "session-a"), ContractValidationError);
    }
});
test("game-scoped subjective client uses the one unversioned bootstrap route", async () => {
    const requests = [];
    const fetchImplementation = async (input, init) => {
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
    const urls = [];
    const fetchImplementation = async (input) => {
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
    const urls = [];
    const fetchImplementation = async (input) => {
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
    const fetchImplementation = async (input) => {
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
    };
    await assert.rejects(() => client.frames("session-a", { ...identity, fromObservationCursor: 0 }), ContractValidationError);
    await assert.rejects(() => client.combatLog("session-a", { ...identity, fromCombatLogCursor: 3 }), ContractValidationError);
});
test("general engine client has no player or legacy objective replication methods", () => {
    const client = new DndEngineClient("/api");
    assert.equal("bootstrap" in client, false);
    assert.equal("getState" in client, false);
    assert.equal("getVisibility" in client, false);
    assert.equal("getEquipment" in client, false);
    assert.equal("getItem" in client, false);
});
test("terminal summary route accepts exact worker V3 evidence and rejects real V1/V2 summaries", async () => {
    const urls = [];
    const evidence = workerSummaryEvidence();
    const fetchImplementation = async (input) => {
        urls.push(String(input));
        return new Response(JSON.stringify(evidence), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    };
    const client = new DndEngineClient("/api", { fetchImplementation });
    const decoded = await client.getTerminalSummary();
    assert.equal(decoded.summary.schema_version, 3);
    assert.deepEqual(urls, ["/api/game/evidence/summary"]);
    for (const version of [1, 2]) {
        const legacy = {
            ...evidence,
            summary: legacySummary(version),
        };
        await assert.rejects(engineClientReturning(legacy).getTerminalSummary(), ContractValidationError);
    }
});
test("directory summary route accepts exact FinalSummaryRecord V3 and rejects real V1/V2 records", async () => {
    const record = finalSummaryRecord();
    const credential = {
        principalId: "principal-a",
        principalCapability: "directory-secret",
    };
    const decoded = await directoryClientReturning(record).getSummary("game/a", credential);
    assert.equal(decoded.schema_version, "dnd.game-summary.v3");
    assert.equal(decoded.summary.schema_version, 3);
    for (const version of [1, 2]) {
        const legacy = {
            ...record,
            schema_version: `dnd.game-summary.v${version}`,
            summary: legacySummary(version),
        };
        await assert.rejects(directoryClientReturning(legacy).getSummary("game/a", credential), ContractValidationError);
    }
});
test("directory discovery keeps principal capability out of the URL", async () => {
    const requests = [];
    const fetchImplementation = async (input, init) => {
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
    const requests = [];
    const fetchImplementation = async (input, init) => {
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
    const requests = [];
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
    const fetchImplementation = async (input, init) => {
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
    const body = new ReadableStream({
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
    for (const callback of ["connection", "envelope"]) {
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
        await assert.rejects(() => directory.followGames({
            initialReconnectDelayMs: 0,
            maximumReconnectDelayMs: 0,
            onConnectionState: async (state) => {
                if (callback === "connection" && state === "connected")
                    throw failure;
            },
            onEnvelope: async () => {
                if (callback === "envelope")
                    throw failure;
            },
        }), (error) => error === failure);
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
    const fetchImplementation = async () => new Response(streamBody, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
    });
    const directory = new GameDirectoryClient("/gateway-api", { fetchImplementation });
    const controller = new AbortController();
    const seen = [];
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
        binding_subject: bindingSubject("action", "action.dash"),
        source_item_fact: null,
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
        item_stack_count: null,
        item_charge_cost: 0,
        fixed_healing: null,
        connector_traversal: null,
    };
}
function availableHandler() {
    return {
        name: "Lucky",
        binding_subject: bindingSubject("reaction", "reaction.lucky"),
        uuid: "handler-lucky",
        enabled: true,
        trigger_event: "d20_roll_result",
    };
}
function bindingSubject(definitionKind, contentId) {
    return {
        kind: "public_definition",
        use: "behavior",
        ref: behaviorAttribution(definitionKind, contentId).definition_ref,
    };
}
function behaviorAttribution(definitionKind, contentId) {
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
function engineClientReturning(payload) {
    return new DndEngineClient("/api", {
        fetchImplementation: async () => new Response(JSON.stringify(payload), {
            headers: { "Content-Type": "application/json" },
        }),
    });
}
function directoryClientReturning(payload) {
    return new GameDirectoryClient("/gateway-api", {
        fetchImplementation: async () => new Response(JSON.stringify(payload), {
            headers: { "Content-Type": "application/json" },
        }),
    });
}
function availableActionsPayload(actions = [], handlers = []) {
    return {
        entity_uuid: "entity-a",
        execution_authorization: "authorized",
        entity_actions: actions,
        position_actions: [],
        self_actions: [],
        object_actions: [],
        remaining_movement: 0,
        handler_details: handlers,
        actions_remaining: 1,
        bonus_actions_remaining: 1,
        reactions_remaining: 1,
        extra_attacks_remaining: 0,
        spell_slots: {},
        resources: {},
    };
}
function zeroAttackStatistics() {
    return {
        attempted: 0,
        resolved: 0,
        hits: 0,
        misses: 0,
        critical_hits: 0,
        critical_misses: 0,
        canceled: 0,
        opportunity_attacks: null,
    };
}
function zeroDamageStatisticsV1() {
    return {
        incoming_raw: 0,
        applied: 0,
        normal_hit_point_damage: 0,
        temporary_hit_point_damage: 0,
        unapplied_remainder: 0,
        incoming_packets: 0,
        applied_packets: 0,
        blocked_packets: 0,
        applied_by_type: {},
    };
}
function zeroDamageStatisticsV2() {
    return {
        ...zeroDamageStatisticsV1(),
        effective_normal_hit_point_damage: 0,
        overkill_damage: 0,
        prevention: {
            event_prevented: 0,
            resistance_prevented: 0,
            immunity_prevented: 0,
            flat_reduction_prevented: 0,
            survival_cap_prevented: 0,
            blocked_damage: 0,
            vulnerability_bonus: 0,
            event_amplification: 0,
        },
        incoming_by_type: {},
        after_affinity_by_type: {},
        applied_by_counterparty: {},
        applied_by_effect: {},
    };
}
function zeroResolutionStatistics() {
    return { attempted: 0, resolved: 0, successes: 0, failures: 0, by_kind: {} };
}
function zeroRollLuckStatistics() {
    return {
        roll_events: 0,
        outcome_samples: 0,
        random_faces_rolled: 0,
        observed_total: 0,
        expected_total: 0,
        variance_total: 0,
        average_observed: null,
        average_expected: null,
        luck_delta: 0,
        luck_z_score: null,
        natural_ones: 0,
        natural_twenties: 0,
        advantage_events: 0,
        disadvantage_events: 0,
        modified_events: 0,
    };
}
function zeroDiceStatistics() {
    return {
        all_d20: zeroRollLuckStatistics(),
        attack_d20: zeroRollLuckStatistics(),
        saving_throw_d20: zeroRollLuckStatistics(),
        skill_check_d20: zeroRollLuckStatistics(),
        damage: zeroRollLuckStatistics(),
        healing: zeroRollLuckStatistics(),
    };
}
function zeroStatisticsV1() {
    return {
        turns_started: 0,
        turns_ended: 0,
        attacks: zeroAttackStatistics(),
        damage_dealt: zeroDamageStatisticsV1(),
        damage_taken: zeroDamageStatisticsV1(),
        healing_done: { requested: 0, applied: 0, events: 0, blocked_events: 0 },
        healing_received: { requested: 0, applied: 0, events: 0, blocked_events: 0 },
        movement: {
            voluntary_events: 0,
            voluntary_feet: 0,
            jump_events: 0,
            jump_feet: 0,
            forced_events: 0,
            forced_feet: 0,
        },
        action_usage: {},
        item_action_usage: {},
        spell_usage: {},
        item_charges_spent: {},
        action_economy_spent: {},
        resources_spent: {},
        conditions_applied: {},
        conditions_removed: {},
        kills: 0,
        deaths: 0,
    };
}
function zeroStatisticsV2() {
    return {
        ...zeroStatisticsV1(),
        damage_dealt: zeroDamageStatisticsV2(),
        damage_taken: zeroDamageStatisticsV2(),
        saving_throws: zeroResolutionStatistics(),
        skill_checks: zeroResolutionStatistics(),
        dice: zeroDiceStatistics(),
    };
}
function zeroStatisticsV3() {
    const { applied_by_effect: _dealtEffect, ...damageDealt } = zeroDamageStatisticsV2();
    const { applied_by_effect: _takenEffect, ...damageTaken } = zeroDamageStatisticsV2();
    return {
        ...zeroStatisticsV2(),
        damage_dealt: {
            ...damageDealt,
            applied_by_action_subject: [],
            applied_without_action_subject: 0,
        },
        damage_taken: {
            ...damageTaken,
            applied_by_action_subject: [],
            applied_without_action_subject: 0,
        },
        action_usage: [],
        item_action_usage: [],
        spell_usage: [],
    };
}
function summaryCommon(reducerId) {
    return {
        schema_name: "dnd.game-summary",
        game_id: "game-a",
        encounter_uuid: "00000000-0000-4000-8000-000000000001",
        started_at: null,
        ended_at: "2026-08-14T12:00:00Z",
        duration_seconds: null,
        rounds_started: 1,
        terminal_cursor: { event_cursor: 4, combat_log_cursor: 2 },
        outcome: {
            terminal_event_observed: true,
            resolution: "indeterminate",
            reason: "complete",
            winning_side_ids: [],
            losing_side_ids: [],
            surviving_side_ids: [],
        },
        entities: [],
        sides: [],
        completeness: { status: "complete", issues: [] },
        provenance: {
            reducer_id: reducerId,
            event_model: "dnd.core.events.Event",
            combat_log_model: "dnd.core.combat_log.CombatLogEntry",
            initial_snapshot_count: 0,
            final_snapshot_count: 0,
            event_versions_seen: 4,
            event_lineages_seen: 2,
            terminal_lineages_reduced: 2,
            top_level_combat_logs_seen: 2,
            structured_combat_logs_seen: 2,
            metric_provenance: [],
        },
        canonical_sha256: "0".repeat(64),
    };
}
function summaryV3() {
    return {
        ...summaryCommon("dnd.analytics.game_summary.v3"),
        schema_version: 3,
        unattributed_statistics: zeroStatisticsV3(),
    };
}
function legacySummary(version) {
    return {
        ...summaryCommon(`dnd.analytics.game_summary.v${version}`),
        schema_version: version,
        unattributed_statistics: version === 1 ? zeroStatisticsV1() : zeroStatisticsV2(),
    };
}
function workerSummaryEvidence() {
    return {
        generation_id: "00000000-0000-4000-8000-000000000002",
        summary: summaryV3(),
        source_event_digest: "e".repeat(64),
        source_combat_log_digest: "c".repeat(64),
    };
}
function finalSummaryRecord() {
    return {
        summary_id: "00000000-0000-4000-8000-000000000003",
        game_id: "game-a",
        schema_version: "dnd.game-summary.v3",
        summary_revision: 1,
        summary: summaryV3(),
        summary_digest: "d".repeat(64),
        winner_side_id: null,
        terminal_reason: "complete",
        round_count: 1,
        turn_count: 2,
        duration_ms: 1000,
        source_event_digest: "e".repeat(64),
        source_combat_log_digest: "c".repeat(64),
        created_at: "2026-08-14T12:00:00Z",
        supersedes_summary_id: null,
        is_current: true,
    };
}
function directoryEventStreamBody() {
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
//# sourceMappingURL=gameRouting.test.js.map