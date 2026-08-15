import { OBJECTIVE_REPLAY_CONTRACT_HASH, OBJECTIVE_REPLAY_CONTRACT_VERSION, PLAYER_REPLAY_CONTRACT_HASH, PLAYER_REPLAY_CONTRACT_VERSION, } from "./generated/contracts.generated.js";
import { assertObjectiveCombatLogWindow, } from "./objectiveDiagnostics.js";
import { assertObjectiveGameEventFrame, assertObjectiveProtocolIdentity, } from "./objectiveSse.js";
import { assertSubjectiveReplicationBootstrap, } from "./subjectiveJournal.js";
import { assertDominates, assertSubjectiveCombatLogDelivery, assertSubjectiveFrame, } from "./subjectiveSse.js";
import { ContractValidationError, decodeModel } from "./validation.js";
/** Decode and semantically authenticate one ended objective replay. */
export function decodeObjectiveReplay(value) {
    const replay = decodeModel("ObjectiveReplayBundle", value);
    assertObjectiveReplay(replay);
    return replay;
}
/** Decode one membership-scoped replay; objective/raw event payloads are not in its schema. */
export function decodeSubjectivePlayerReplay(value) {
    preflightSubjectivePlayerReplayIdentity(value);
    const replay = decodeModel("SubjectivePlayerReplayBundle", value);
    assertSubjectivePlayerReplay(replay);
    return replay;
}
export function assertObjectiveReplay(replay) {
    if (replay.replay_contract_version !== OBJECTIVE_REPLAY_CONTRACT_VERSION) {
        fail("$objective_replay.replay_contract_version", "unsupported objective replay contract version");
    }
    if (replay.replay_contract_hash !== OBJECTIVE_REPLAY_CONTRACT_HASH) {
        fail("$objective_replay.replay_contract_hash", "objective replay contract hash mismatch");
    }
    assertObjectiveProtocolIdentity(replay.protocol, "$objective_replay.protocol");
    const encounter = replay.seed.world.state.encounter;
    if (encounter === null || encounter.uuid !== replay.encounter_uuid) {
        fail("$objective_replay.seed.world.state.encounter", "seed does not describe the replay encounter");
    }
    if (replay.source_stream_id !== replay.encounter_uuid) {
        fail("$objective_replay.source_stream_id", "source stream must equal the encounter UUID");
    }
    assertObjectiveWorld(replay);
    if (replay.seed.event_cursor >= replay.terminal_event_cursor) {
        fail("$objective_replay.seed.event_cursor", "seed must precede the terminal event cursor");
    }
    if (replay.seed.combat_log_cursor > replay.terminal_combat_log_cursor) {
        fail("$objective_replay.seed.combat_log_cursor", "seed exceeds the terminal log cursor");
    }
    const logs = replay.combat_log_frames;
    assertObjectiveCombatLogWindow(logs);
    if (logs.source_stream_id !== replay.source_stream_id) {
        fail("$objective_replay.combat_log_frames.source_stream_id", "source stream differs from replay");
    }
    if (logs.generation_id !== replay.generation_id) {
        fail("$objective_replay.combat_log_frames.generation_id", "generation differs from replay");
    }
    if (logs.retained_from_cursor !== 0 || logs.from_cursor !== 0) {
        fail("$objective_replay.combat_log_frames", "replay logs must be retained from cursor zero");
    }
    if (logs.through_cursor !== logs.total || logs.total !== replay.terminal_combat_log_cursor) {
        fail("$objective_replay.combat_log_frames", "replay log window is not terminal and complete");
    }
    if (replay.seed.combat_log_cursor > logs.total) {
        fail("$objective_replay.seed.combat_log_cursor", "seed log cursor exceeds retained replay logs");
    }
    if (logs.frames
        .slice(0, replay.seed.combat_log_cursor)
        .some((frame) => frame.event_cursor > replay.seed.event_cursor)) {
        fail("$objective_replay.seed", "seed includes a log beyond its event barrier");
    }
    const logEventCursors = logs.frames.map((frame) => frame.event_cursor);
    let previousEventCursor = replay.seed.event_cursor;
    let previousLogCursor = replay.seed.combat_log_cursor;
    const retainedLineages = new Set();
    replay.events.forEach((frame, index) => {
        const path = `$objective_replay.events[${index}]`;
        assertObjectiveGameEventFrame(frame, path);
        if (frame.source_stream_id !== replay.source_stream_id) {
            fail(`${path}.source_stream_id`, "source stream differs from replay");
        }
        if (frame.generation_id !== replay.generation_id) {
            fail(`${path}.generation_id`, "generation differs from replay");
        }
        if (frame.event_cursor <= previousEventCursor) {
            fail(`${path}.event_cursor`, "retained events must be strictly ordered");
        }
        if (frame.event_cursor > replay.terminal_event_cursor) {
            fail(`${path}.event_cursor`, "event exceeds terminal cursor");
        }
        if (frame.event.phase !== "completion" && frame.event.phase !== "cancel") {
            fail(`${path}.event.phase`, "replay may contain only completion or cancel events");
        }
        if (retainedLineages.has(frame.event.lineage_uuid)) {
            fail(`${path}.event.lineage_uuid`, "replay contains duplicate terminal lineage UUID");
        }
        retainedLineages.add(frame.event.lineage_uuid);
        const exactLogCursor = upperBound(logEventCursors, frame.event_cursor);
        if (frame.combat_log_cursor !== exactLogCursor) {
            fail(`${path}.combat_log_cursor`, "event does not carry its exact combat-log barrier");
        }
        if (frame.combat_log_cursor < previousLogCursor) {
            fail(`${path}.combat_log_cursor`, "event log barriers moved backwards");
        }
        previousEventCursor = frame.event_cursor;
        previousLogCursor = frame.combat_log_cursor;
    });
    const terminal = replay.events.at(-1);
    if (terminal === undefined) {
        fail("$objective_replay.events", "ended replay requires a terminal completion event");
    }
    if (terminal.event_cursor !== replay.terminal_event_cursor) {
        fail("$objective_replay.events", "last retained event is not the terminal event cursor");
    }
    if (terminal.event.phase !== "completion" || terminal.event.event_type !== "encounter_end") {
        fail("$objective_replay.events", "last completion must end the encounter");
    }
    if (logs.frames.some((frame) => frame.event_cursor > replay.terminal_event_cursor)) {
        fail("$objective_replay.combat_log_frames", "combat log exceeds terminal event cursor");
    }
}
export function assertSubjectivePlayerReplay(replay) {
    if (replay.replay_contract_version !== PLAYER_REPLAY_CONTRACT_VERSION) {
        fail("$subjective_replay.replay_contract_version", "unsupported player replay contract version");
    }
    if (replay.replay_contract_hash !== PLAYER_REPLAY_CONTRACT_HASH) {
        fail("$subjective_replay.replay_contract_hash", "player replay contract hash mismatch");
    }
    const partitions = new Set();
    const ended = [];
    const previousThroughByBranch = new Map();
    const combatLogEventBarriersByGeneration = new Map();
    const combatLogFrontierCursorByGeneration = new Map();
    const combatLogFrontierEventCursorByGeneration = new Map();
    const terminalGenerationIds = new Set(replay.segments
        .filter((segment) => segment.end_reason === "encounter_ended")
        .map((segment) => segment.bootstrap.protocol.generation_id));
    if (terminalGenerationIds.size === 0) {
        fail("$subjective_replay.segments", "ended replay has no encounter-ended branch");
    }
    if (terminalGenerationIds.size !== 1) {
        fail("$subjective_replay.segments", "terminal branches use different generations");
    }
    const terminalGenerationId = [...terminalGenerationIds][0];
    const endedBranches = new Set();
    let terminalGenerationStarted = false;
    let activeGenerationId = null;
    const departedGenerationIds = new Set();
    replay.segments.forEach((segment, index) => {
        const path = `$subjective_replay.segments[${index}]`;
        if (segment.segment_index !== index) {
            fail(`${path}.segment_index`, "segments must be contiguous and ordered");
        }
        if (segment.membership_id !== replay.membership_id) {
            fail(`${path}.membership_id`, "segment belongs to another membership");
        }
        assertSubjectiveReplaySegment(segment, path);
        const { protocol } = segment.bootstrap;
        const { perspective } = segment.bootstrap;
        if (protocol.source_stream_id !== replay.encounter_uuid) {
            fail(`${path}.bootstrap.protocol.source_stream_id`, "segment belongs to another encounter stream");
        }
        const encounter = segment.bootstrap.world.state.encounter;
        if (encounter === null || encounter.uuid !== replay.encounter_uuid) {
            fail(`${path}.bootstrap.world.state.encounter`, "segment does not describe the replay encounter");
        }
        const partition = JSON.stringify([
            protocol.generation_id,
            perspective.perspective_epoch_id,
        ]);
        if (partitions.has(partition)) {
            fail(path, "generation-and-perspective partition is repeated");
        }
        partitions.add(partition);
        const opening = segment.bootstrap.watermarks;
        const generationId = protocol.generation_id;
        if (generationId !== activeGenerationId) {
            if (departedGenerationIds.has(generationId)) {
                fail(path, "replay generations must form contiguous segment runs");
            }
            if (activeGenerationId !== null) {
                departedGenerationIds.add(activeGenerationId);
            }
            activeGenerationId = generationId;
        }
        if (generationId === terminalGenerationId) {
            terminalGenerationStarted = true;
        }
        else if (terminalGenerationStarted) {
            fail(path, "no replay generation may follow the terminal generation");
        }
        const branchId = JSON.stringify([generationId, segment.runtime_session_id]);
        if (endedBranches.has(branchId)) {
            fail(path, "replay branch continued after encounter end");
        }
        const previousThrough = previousThroughByBranch.get(branchId) ?? null;
        if (previousThrough !== null
            && opening.source_event_cursor < previousThrough.source_event_cursor) {
            fail(`${path}.bootstrap.watermarks.source_event_cursor`, "segment source history regressed");
        }
        if (previousThrough !== null
            && opening.combat_log_cursor < previousThrough.combat_log_cursor) {
            fail(`${path}.bootstrap.watermarks.combat_log_cursor`, "segment combat-log history regressed");
        }
        const combatLogEventBarrierByCursor = combatLogEventBarriersByGeneration.get(generationId) ?? new Map();
        combatLogEventBarriersByGeneration.set(generationId, combatLogEventBarrierByCursor);
        let combatLogFrontierCursor = combatLogFrontierCursorByGeneration.get(generationId) ?? -1;
        let combatLogFrontierEventCursor = combatLogFrontierEventCursorByGeneration.get(generationId) ?? 0;
        for (const frame of segment.bootstrap.combat_log_frames.frames) {
            [combatLogFrontierCursor, combatLogFrontierEventCursor] = rememberCombatLogEventBarrier(combatLogEventBarrierByCursor, frame.combat_log_cursor, frame.event_cursor, `${path}.bootstrap.combat_log_frames`, combatLogFrontierCursor, combatLogFrontierEventCursor);
        }
        for (const [deliveryIndex, delivery] of segment.deliveries.entries()) {
            if (delivery.kind !== "combat_log")
                continue;
            [combatLogFrontierCursor, combatLogFrontierEventCursor] = rememberCombatLogEventBarrier(combatLogEventBarrierByCursor, delivery.frame.combat_log_cursor, delivery.frame.event_cursor, `${path}.deliveries[${deliveryIndex}].frame`, combatLogFrontierCursor, combatLogFrontierEventCursor);
        }
        previousThroughByBranch.set(branchId, segment.through_watermarks);
        combatLogFrontierCursorByGeneration.set(generationId, combatLogFrontierCursor);
        combatLogFrontierEventCursorByGeneration.set(generationId, combatLogFrontierEventCursor);
        if (generationId === terminalGenerationId
            && segment.through_watermarks.source_event_cursor
                > replay.terminal_source_event_cursor) {
            fail(`${path}.through_watermarks.source_event_cursor`, "segment exceeds terminal source cursor");
        }
        if (generationId === terminalGenerationId
            && segment.through_watermarks.combat_log_cursor
                > replay.terminal_combat_log_cursor) {
            fail(`${path}.through_watermarks.combat_log_cursor`, "segment exceeds terminal log cursor");
        }
        if (segment.end_reason === "encounter_ended") {
            ended.push(index);
            endedBranches.add(branchId);
        }
    });
    for (const endedIndex of ended) {
        const terminal = replay.segments[endedIndex].through_watermarks;
        if (terminal.source_event_cursor !== replay.terminal_source_event_cursor) {
            fail("$subjective_replay.terminal_source_event_cursor", "terminal branch source cursor is incomplete");
        }
        if (terminal.combat_log_cursor !== replay.terminal_combat_log_cursor) {
            fail("$subjective_replay.terminal_combat_log_cursor", "terminal branch log cursor is incomplete");
        }
    }
    const identities = ended.map((index) => (replaySegmentTerminalEventIdentity(replay.segments[index])));
    if (identities.some((identity) => (identity !== null && identity.encounterUuid !== replay.encounter_uuid))) {
        fail("$subjective_replay.segments", "terminal replay branch belongs to another encounter");
    }
    if (ended.length > 1) {
        const first = identities[0];
        if (first === null
            || identities.some((identity) => (identity === null
                || identity.mode !== first.mode
                || identity.sourceEventUuid !== first.sourceEventUuid
                || identity.encounterUuid !== first.encounterUuid
                || identity.reason !== first.reason))) {
            fail("$subjective_replay.segments", "terminal replay branches disagree on terminal event identity");
        }
    }
}
function replaySegmentTerminalEventIdentity(segment) {
    for (const delivery of segment.deliveries) {
        if (delivery.kind !== "frame")
            continue;
        const cue = delivery.frame.presentation.find((candidate) => (candidate.kind === "encounter" && candidate.transition === "end"));
        const authority = cue ?? delivery.frame.encounter_terminal;
        if (authority !== undefined && authority !== null) {
            return {
                mode: cue === undefined ? "reset" : "ordinary",
                sourceEventUuid: authority.source_event_uuid,
                encounterUuid: authority.encounter_uuid,
                reason: authority.reason,
            };
        }
    }
    return null;
}
export function assertSubjectiveReplaySegment(segment, path = "$subjective_replay.segment") {
    assertSubjectiveReplicationBootstrap(segment.bootstrap);
    const { protocol, perspective } = segment.bootstrap;
    let previous = segment.bootstrap.watermarks;
    let previousCombatLogEventCursor = (segment.bootstrap.combat_log_frames.frames.at(-1)?.event_cursor ?? 0);
    const presentationIds = new Set();
    let encounterEndSeen = segment.bootstrap.world.state.encounter?.state === "ended";
    let terminalSourceEventCursor = null;
    segment.deliveries.forEach((delivery, index) => {
        const deliveryPath = `${path}.deliveries[${index}]`;
        if (delivery.kind === "frame") {
            if (encounterEndSeen) {
                fail(deliveryPath, "observation frame follows encounter end");
            }
            const frame = delivery.frame;
            assertSubjectiveFrame(frame);
            assertSubjectiveIdentity(frame, protocol.source_stream_id, protocol.generation_id, perspective.perspective_epoch_id, deliveryPath);
            if (frame.watermarks.observation_cursor !== previous.observation_cursor + 1) {
                fail(`${deliveryPath}.frame.watermarks.observation_cursor`, "observation frames are not contiguous");
            }
            if (frame.presentation_from_cursor !== previous.presentation_cursor) {
                fail(`${deliveryPath}.frame.presentation_from_cursor`, "presentation windows are not contiguous");
            }
            if (frame.watermarks.combat_log_cursor !== previous.combat_log_cursor) {
                fail(`${deliveryPath}.frame.watermarks.combat_log_cursor`, "frame advanced the log cursor");
            }
            assertDominates(frame.watermarks, previous, `${deliveryPath}.frame.watermarks`);
            for (const cue of frame.presentation) {
                if (presentationIds.has(cue.presentation_id)) {
                    fail(deliveryPath, "presentation ID is reused across replay frames");
                }
                presentationIds.add(cue.presentation_id);
            }
            const terminalCursor = assertReplayTerminalAuthority(frame, deliveryPath);
            if (terminalCursor !== null) {
                encounterEndSeen = true;
                terminalSourceEventCursor = terminalCursor;
            }
            previous = frame.watermarks;
            return;
        }
        assertSubjectiveCombatLogDelivery(delivery);
        const frame = delivery.frame;
        assertSubjectiveIdentity(frame, protocol.source_stream_id, protocol.generation_id, perspective.perspective_epoch_id, deliveryPath);
        if (frame.combat_log_cursor !== previous.combat_log_cursor + 1) {
            fail(`${deliveryPath}.frame.combat_log_cursor`, "combat-log frames are not contiguous");
        }
        if (frame.event_cursor > previous.source_event_cursor) {
            fail(`${deliveryPath}.frame.event_cursor`, "combat-log barrier exceeds consumed source events");
        }
        if (frame.event_cursor < previousCombatLogEventCursor) {
            fail(`${deliveryPath}.frame.event_cursor`, "combat-log event barriers moved backwards");
        }
        if (terminalSourceEventCursor !== null
            && frame.event_cursor > terminalSourceEventCursor) {
            fail(`${deliveryPath}.frame.event_cursor`, "combat-log barrier exceeds encounter terminal authority");
        }
        const expected = { ...previous, combat_log_cursor: frame.combat_log_cursor };
        if (!equalWatermarks(delivery.watermarks, expected)) {
            fail(`${deliveryPath}.watermarks`, "combat-log delivery does not match its exact slot");
        }
        previous = delivery.watermarks;
        previousCombatLogEventCursor = frame.event_cursor;
    });
    if (!equalWatermarks(previous, segment.through_watermarks)) {
        fail(`${path}.through_watermarks`, "through watermarks differ from delivery stream");
    }
    if (segment.end_reason === "encounter_ended" && !encounterEndSeen) {
        fail(`${path}.end_reason`, "encounter-ended segment has no terminal bootstrap, cue, or reset fact");
    }
    if (segment.end_reason === "perspective_retired" && encounterEndSeen) {
        fail(`${path}.end_reason`, "terminal segment is labeled perspective-retired");
    }
}
function rememberCombatLogEventBarrier(known, combatLogCursor, eventCursor, path, frontierCursor, frontierEventCursor) {
    const previous = known.get(combatLogCursor);
    if (previous !== undefined && previous !== eventCursor) {
        fail(`${path}.event_cursor`, "retained combat-log cursor changed its canonical event barrier");
    }
    known.set(combatLogCursor, eventCursor);
    if (combatLogCursor > frontierCursor) {
        if (frontierCursor >= 0 && eventCursor < frontierEventCursor) {
            fail(`${path}.event_cursor`, "combat-log event barriers moved backwards across replay segments");
        }
        return [combatLogCursor, eventCursor];
    }
    return [frontierCursor, frontierEventCursor];
}
function preflightSubjectivePlayerReplayIdentity(value) {
    if (!isRecord(value)) {
        fail("$subjective_replay", "player replay envelope must be an object");
    }
    if (value.replay_contract_version !== PLAYER_REPLAY_CONTRACT_VERSION) {
        fail("$subjective_replay.replay_contract_version", "unsupported player replay contract version");
    }
    if (value.replay_contract_hash !== PLAYER_REPLAY_CONTRACT_HASH) {
        fail("$subjective_replay.replay_contract_hash", "player replay contract hash mismatch");
    }
}
function assertReplayTerminalAuthority(frame, path) {
    const terminalCues = frame.presentation.filter((cue) => (cue.kind === "encounter" && cue.transition === "end"));
    const resetFact = frame.encounter_terminal;
    if (terminalCues.length > 1) {
        fail(path, "one frame cannot end the encounter twice");
    }
    if (terminalCues.length === 1 && resetFact !== null) {
        fail(path, "ordinary cue and reset fact terminal authority are mutually exclusive");
    }
    const endedPatches = frame.patches.filter((patch) => patch.kind === "encounter_replace"
        && patch.encounter !== null
        && patch.encounter.state === "ended");
    const cue = terminalCues[0];
    const authority = cue ?? resetFact;
    if (authority === undefined || authority === null) {
        if (endedPatches.length !== 0) {
            fail(path, "ended encounter patch requires matching terminal authority");
        }
        return null;
    }
    if (authority.source_event_cursor !== frame.watermarks.source_event_cursor) {
        fail(path, "encounter terminal authority must occupy the final source event slot");
    }
    if (endedPatches.length !== 1
        || endedPatches[0]?.encounter?.uuid !== authority.encounter_uuid) {
        fail(path, "encounter terminal authority requires exactly one matching ended patch");
    }
    return authority.source_event_cursor;
}
function assertObjectiveWorld(replay) {
    const entities = new Set(replay.seed.world.state.entities.map((entity) => entity.uuid));
    for (const entityUuid of Object.keys(replay.seed.world.equipment_by_entity)) {
        if (!entities.has(entityUuid)) {
            fail("$objective_replay.seed.world.equipment_by_entity", "equipment references an absent entity");
        }
    }
}
function assertSubjectiveIdentity(value, sourceStreamId, generationId, perspectiveEpochId, path) {
    if (value.source_stream_id !== sourceStreamId
        || value.generation_id !== generationId
        || value.perspective_epoch_id !== perspectiveEpochId) {
        fail(path, "delivery identity differs from segment bootstrap");
    }
}
function equalWatermarks(left, right) {
    return left.source_event_cursor === right.source_event_cursor
        && left.observation_cursor === right.observation_cursor
        && left.presentation_cursor === right.presentation_cursor
        && left.combat_log_cursor === right.combat_log_cursor;
}
function upperBound(sorted, value) {
    let low = 0;
    let high = sorted.length;
    while (low < high) {
        const middle = low + Math.floor((high - low) / 2);
        if ((sorted[middle] ?? Number.POSITIVE_INFINITY) <= value)
            low = middle + 1;
        else
            high = middle;
    }
    return low;
}
function isRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function fail(path, message) {
    throw new ContractValidationError(path, message);
}
//# sourceMappingURL=replay.js.map