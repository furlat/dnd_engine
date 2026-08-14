import assert from "node:assert/strict";
import test from "node:test";
import { EVENT_CONTRACT_HASH, EVENT_CONTRACT_VERSION, OBJECTIVE_REPLAY_CONTRACT_HASH, OBJECTIVE_REPLAY_CONTRACT_VERSION, PLAYER_REPLAY_CONTRACT_HASH, PLAYER_REPLAY_CONTRACT_VERSION, TIMELINE_CONTRACT_HASH, TIMELINE_CONTRACT_VERSION, ContractValidationError, GameDirectoryClient, decodeObjectiveReplay, decodeSubjectivePlayerReplay, } from "../index.js";
import { bootstrap, watermarks } from "./fixtures.js";
test("replay decoders accept only complete reducer-native objective and subjective bundles", () => {
    const objective = objectiveReplay();
    const subjective = subjectiveReplay();
    const objectiveLogs = objective.combat_log_frames;
    assert.equal(decodeObjectiveReplay(objective), objective);
    assert.equal(decodeSubjectivePlayerReplay(subjective), subjective);
    assert.equal(objectiveLogs.projection, "objective");
});
test("objective replay accepts one ordered completion/cancel/completion sequence", () => {
    const replay = objectiveReplayWithPhases(["completion", "cancel", "completion"]);
    assert.equal(decodeObjectiveReplay(replay), replay);
});
test("objective replay rejects every nonterminal phase", () => {
    for (const phase of ["declaration", "execution", "effect"]) {
        const replay = objectiveReplayWithPhases([phase, "completion"]);
        assert.throws(() => decodeObjectiveReplay(replay), ContractValidationError, phase);
    }
});
test("objective replay rejects duplicate terminal lineage across completion and cancel", () => {
    const source = objectiveReplayWithPhases(["completion", "cancel", "completion"]);
    const replay = {
        ...source,
        events: source.events.map((frame, index) => index === 1 ? {
            ...frame,
            event: { ...frame.event, lineage_uuid: source.events[0].event.lineage_uuid },
        } : frame),
    };
    assert.throws(() => decodeObjectiveReplay(replay), ContractValidationError);
});
test("objective replay rejects cursor order, exact log-barrier drift, and a final cancel", () => {
    const outOfOrder = structuredClone(objectiveReplayWithPhases(["completion", "cancel", "completion"]));
    [outOfOrder.events[0], outOfOrder.events[1]] = [outOfOrder.events[1], outOfOrder.events[0]];
    const logSource = objectiveReplay();
    const logDrift = {
        ...logSource,
        events: [{ ...logSource.events[0], combat_log_cursor: 1 }],
    };
    const finalCancel = objectiveReplayWithPhases(["completion", "cancel"]);
    assert.throws(() => decodeObjectiveReplay(outOfOrder), ContractValidationError);
    assert.throws(() => decodeObjectiveReplay(logDrift), ContractValidationError);
    assert.throws(() => decodeObjectiveReplay(finalCancel), ContractValidationError);
});
test("objective replay rejects a structurally complete v1 archive identity", () => {
    const legacy = {
        ...objectiveReplay(),
        replay_contract_version: 1,
        replay_contract_hash: "1435866d271439a3602ce8b48266fb7922e829e90e35146816b619d2a4ba6717",
        protocol: {
            timeline_contract_version: 1,
            timeline_contract_hash: "4ffc77662322fc81d4b6246c015c5ea4a079b456f26b4dbd6e6d3bbde879996b",
            event_contract_version: 1,
            event_contract_hash: "c9a6e51b3718d8c89ea0446db95ee19ca3edf4d5edb7dd854daa521dee691169",
        },
    };
    assert.throws(() => decodeObjectiveReplay(legacy), ContractValidationError);
});
test("objective replay decoder rejects a source namespace other than its encounter", () => {
    const mismatched = structuredClone(objectiveReplay());
    mismatched.source_stream_id = "other-source";
    mismatched.combat_log_frames.source_stream_id = "other-source";
    for (const frame of mismatched.events) {
        frame.source_stream_id = "other-source";
    }
    assert.throws(() => decodeObjectiveReplay(mismatched), ContractValidationError);
});
test("player replay decoder rejects objective, raw-event, and malformed presentation input", () => {
    const objectiveLog = structuredClone(subjectiveReplay());
    const malformedGraph = structuredClone(subjectiveReplay());
    const firstSegment = objectiveLog.segments[0];
    const malformedSegment = malformedGraph.segments[0];
    assert.ok(firstSegment !== undefined && malformedSegment !== undefined);
    firstSegment.bootstrap.combat_log_frames.projection = "objective";
    const delivery = malformedSegment.deliveries[0];
    const cue = delivery?.frame.presentation[0];
    assert.ok(delivery !== undefined && cue !== undefined);
    cue.child_presentation_ids.push("hidden-raw-lineage");
    assert.throws(() => decodeSubjectivePlayerReplay(objectiveLog), ContractValidationError);
    assert.throws(() => decodeSubjectivePlayerReplay({ ...subjectiveReplay(), raw_events: [] }), ContractValidationError);
    assert.throws(() => decodeSubjectivePlayerReplay(malformedGraph), ContractValidationError);
});
test("player replay identity preflight rejects V1 and unknown hashes before nested V2 decode", () => {
    let nestedReads = 0;
    const legacy = Object.defineProperty({
        replay_contract_version: 1,
        replay_contract_hash: "legacy",
    }, "segments", {
        enumerable: true,
        get: () => {
            nestedReads += 1;
            throw new Error("nested V2 decoder must not run");
        },
    });
    assert.throws(() => decodeSubjectivePlayerReplay(legacy), (error) => (error instanceof ContractValidationError
        && error.path === "$subjective_replay.replay_contract_version"));
    assert.equal(nestedReads, 0);
    const unknownHash = Object.defineProperty({
        replay_contract_version: PLAYER_REPLAY_CONTRACT_VERSION,
        replay_contract_hash: "0".repeat(64),
    }, "segments", {
        enumerable: true,
        get: () => {
            nestedReads += 1;
            throw new Error("nested V2 decoder must not run");
        },
    });
    assert.throws(() => decodeSubjectivePlayerReplay(unknownHash), (error) => (error instanceof ContractValidationError
        && error.path === "$subjective_replay.replay_contract_hash"));
    assert.equal(nestedReads, 0);
});
test("player replay preserves exact reset-terminal authority and finalized trailing logs", () => {
    const replay = resetTerminalSubjectiveReplay();
    const decoded = decodeSubjectivePlayerReplay(replay);
    const delivery = decoded.segments[0]?.deliveries[0];
    assert.equal(delivery?.kind, "frame");
    assert.equal(delivery?.kind === "frame"
        ? delivery.frame.encounter_terminal?.terminal_authority_id
        : null, "perspective-a:1:reset-terminal:00000000-0000-4000-8000-000000000001");
    const segment = replay.segments[0];
    const firstLogWatermarks = { ...segment.through_watermarks, combat_log_cursor: 1 };
    const trailingWatermarks = { ...segment.through_watermarks, combat_log_cursor: 2 };
    const withTrailingLog = {
        ...replay,
        terminal_combat_log_cursor: 2,
        segments: [{
                ...segment,
                deliveries: [
                    ...segment.deliveries,
                    {
                        kind: "combat_log",
                        watermarks: firstLogWatermarks,
                        frame: {
                            source_stream_id: "encounter",
                            generation_id: segment.bootstrap.protocol.generation_id,
                            perspective_epoch_id: segment.bootstrap.perspective.perspective_epoch_id,
                            projection: "subjective",
                            combat_log_cursor: 1,
                            event_cursor: 1,
                            entry: null,
                        },
                    },
                    {
                        kind: "combat_log",
                        watermarks: trailingWatermarks,
                        frame: {
                            source_stream_id: "encounter",
                            generation_id: segment.bootstrap.protocol.generation_id,
                            perspective_epoch_id: segment.bootstrap.perspective.perspective_epoch_id,
                            projection: "subjective",
                            combat_log_cursor: 2,
                            event_cursor: 1,
                            entry: null,
                        },
                    },
                ],
                through_watermarks: trailingWatermarks,
            }],
    };
    assert.doesNotThrow(() => decodeSubjectivePlayerReplay(withTrailingLog));
    const decreasing = structuredClone(withTrailingLog);
    const finalDelivery = decreasing.segments[0]?.deliveries.at(-1);
    assert.equal(finalDelivery?.kind, "combat_log");
    if (finalDelivery?.frame.event_cursor === undefined) {
        throw new Error("expected trailing combat-log delivery");
    }
    finalDelivery.frame.event_cursor = 0;
    assert.throws(() => decodeSubjectivePlayerReplay(decreasing), (error) => (error instanceof ContractValidationError
        && error.message.includes("event barriers moved backwards")));
});
test("player replay carries source and combat-log history across perspective segments", () => {
    const lawful = rotatedSubjectiveReplay();
    assert.doesNotThrow(() => decodeSubjectivePlayerReplay(lawful));
    assert.doesNotThrow(() => decodeSubjectivePlayerReplay(threeSegmentSubjectiveReplay()));
    const sourceRegression = structuredClone(lawful);
    sourceRegression.segments[1].bootstrap.watermarks.source_event_cursor = 3;
    for (const frame of sourceRegression.segments[1]
        .bootstrap.combat_log_frames.frames) {
        frame.event_cursor = 3;
    }
    assert.throws(() => decodeSubjectivePlayerReplay(sourceRegression), (error) => (error instanceof ContractValidationError
        && error.message.includes("source history regressed")));
    const logRegression = structuredClone(lawful);
    logRegression.segments[1].bootstrap.watermarks.combat_log_cursor = 1;
    logRegression.segments[1].bootstrap.combat_log_frames.through_cursor = 1;
    logRegression.segments[1].bootstrap.combat_log_frames.total = 1;
    logRegression.segments[1].bootstrap.combat_log_frames.frames.splice(1);
    const terminalAfterRegression = logRegression.segments[1].deliveries[0];
    if (terminalAfterRegression?.kind !== "frame" || terminalAfterRegression.frame.watermarks === undefined) {
        throw new Error("expected terminal frame");
    }
    terminalAfterRegression.frame.watermarks.combat_log_cursor = 1;
    logRegression.segments[1].through_watermarks.combat_log_cursor = 1;
    assert.throws(() => decodeSubjectivePlayerReplay(logRegression), (error) => (error instanceof ContractValidationError
        && error.message.includes("combat-log history regressed")));
    const barrierRegression = structuredClone(lawful);
    barrierRegression.segments[1]
        .bootstrap.combat_log_frames.frames[0].event_cursor = 4;
    assert.throws(() => decodeSubjectivePlayerReplay(barrierRegression), (error) => (error instanceof ContractValidationError
        && error.message.includes("canonical event barrier")));
    const hiddenGapRegression = structuredClone(lawful);
    const hiddenGapSegment = hiddenGapRegression.segments[1];
    const retained = hiddenGapSegment.bootstrap.combat_log_frames;
    const hiddenGapFrame = {
        ...retained.frames[1],
        combat_log_cursor: 3,
        event_cursor: 4,
    };
    hiddenGapSegment.bootstrap.watermarks.combat_log_cursor = 3;
    retained.retained_from_cursor = 2;
    retained.from_cursor = 2;
    retained.through_cursor = 3;
    retained.total = 3;
    retained.frames = [hiddenGapFrame];
    const hiddenGapTerminal = hiddenGapSegment.deliveries[0];
    if (hiddenGapTerminal.kind !== "frame")
        throw new Error("expected terminal frame");
    hiddenGapTerminal.frame.watermarks.combat_log_cursor = 3;
    hiddenGapSegment.through_watermarks.combat_log_cursor = 3;
    hiddenGapRegression.terminal_combat_log_cursor = 3;
    assert.throws(() => decodeSubjectivePlayerReplay(hiddenGapRegression), (error) => (error instanceof ContractValidationError
        && error.message.includes("across replay segments")));
    const emptyRetainedRegression = structuredClone(lawful);
    const emptySegment = emptyRetainedRegression.segments[1];
    emptySegment.bootstrap.combat_log_frames.retained_from_cursor = 2;
    emptySegment.bootstrap.combat_log_frames.from_cursor = 2;
    emptySegment.bootstrap.combat_log_frames.through_cursor = 2;
    emptySegment.bootstrap.combat_log_frames.total = 2;
    emptySegment.bootstrap.combat_log_frames.frames = [];
    const emptyTerminal = emptySegment.deliveries[0];
    if (emptyTerminal.kind !== "frame")
        throw new Error("expected terminal frame");
    const trailingWatermarks = {
        ...emptyTerminal.frame.watermarks,
        combat_log_cursor: 3,
    };
    emptySegment.deliveries.push({
        kind: "combat_log",
        watermarks: trailingWatermarks,
        frame: {
            source_stream_id: emptyTerminal.frame.source_stream_id,
            generation_id: emptyTerminal.frame.generation_id,
            perspective_epoch_id: emptyTerminal.frame.perspective_epoch_id,
            projection: "subjective",
            combat_log_cursor: 3,
            event_cursor: 4,
            entry: null,
        },
    });
    emptySegment.through_watermarks = trailingWatermarks;
    emptyRetainedRegression.terminal_combat_log_cursor = 3;
    assert.throws(() => decodeSubjectivePlayerReplay(emptyRetainedRegression), (error) => (error instanceof ContractValidationError
        && error.message.includes("across replay segments")));
});
test("parallel replay perspectives are sibling runtime-session branches", () => {
    const base = rotatedSubjectiveReplay();
    const baseFirst = base.segments[0];
    const baseSecond = base.segments[1];
    const first = {
        ...baseFirst,
        runtime_session_id: "parallel-runtime-a",
        deliveries: baseFirst.deliveries.map((delivery) => (delivery.kind === "frame"
            ? {
                ...delivery,
                frame: {
                    ...delivery.frame,
                    watermarks: {
                        ...delivery.frame.watermarks,
                        source_event_cursor: 6,
                    },
                },
            }
            : {
                ...delivery,
                watermarks: {
                    ...delivery.watermarks,
                    source_event_cursor: 6,
                },
            })),
        through_watermarks: {
            ...baseFirst.through_watermarks,
            source_event_cursor: 6,
        },
    };
    const second = {
        ...baseSecond,
        runtime_session_id: "parallel-runtime-b",
    };
    const siblings = {
        ...base,
        segments: [first, second],
    };
    assert.equal(second.bootstrap.watermarks.source_event_cursor, 5);
    assert.doesNotThrow(() => decodeSubjectivePlayerReplay(siblings));
    const falseSuccessor = {
        ...siblings,
        segments: [
            first,
            { ...second, runtime_session_id: first.runtime_session_id },
        ],
    };
    assert.throws(() => decodeSubjectivePlayerReplay(falseSuccessor), (error) => (error instanceof ContractValidationError
        && error.message.includes("source history regressed")));
    const terminalSiblingEpoch = "terminal-perspective-a";
    const terminalSibling = {
        ...baseSecond,
        segment_index: 0,
        runtime_session_id: "terminal-runtime-a",
        bootstrap: {
            ...baseSecond.bootstrap,
            perspective: {
                ...baseSecond.bootstrap.perspective,
                perspective_epoch_id: terminalSiblingEpoch,
            },
            combat_log_frames: {
                ...baseSecond.bootstrap.combat_log_frames,
                perspective_epoch_id: terminalSiblingEpoch,
                frames: baseSecond.bootstrap.combat_log_frames.frames.map((frame) => ({
                    ...frame,
                    perspective_epoch_id: terminalSiblingEpoch,
                })),
            },
        },
        deliveries: baseSecond.deliveries.map((delivery) => (delivery.kind === "frame"
            ? {
                ...delivery,
                frame: {
                    ...delivery.frame,
                    perspective_epoch_id: terminalSiblingEpoch,
                },
            }
            : {
                ...delivery,
                frame: {
                    ...delivery.frame,
                    perspective_epoch_id: terminalSiblingEpoch,
                },
            })),
    };
    const terminalBranches = {
        ...base,
        segments: [
            terminalSibling,
            { ...baseSecond, runtime_session_id: "terminal-runtime-b" },
        ],
    };
    assert.doesNotThrow(() => decodeSubjectivePlayerReplay(terminalBranches));
});
test("player replay starts fresh cursor authority at an exact new generation", () => {
    const reset = generationResetSubjectiveReplay();
    assert.doesNotThrow(() => decodeSubjectivePlayerReplay(reset));
    const postTerminalSeed = structuredClone(reset.segments[0].bootstrap);
    const postTerminalBootstrap = {
        ...postTerminalSeed,
        protocol: {
            ...postTerminalSeed.protocol,
            generation_id: "post-terminal-generation",
        },
        perspective: {
            ...postTerminalSeed.perspective,
            perspective_epoch_id: "post-terminal-epoch",
        },
        combat_log_frames: {
            ...postTerminalSeed.combat_log_frames,
            generation_id: "post-terminal-generation",
            perspective_epoch_id: "post-terminal-epoch",
            frames: postTerminalSeed.combat_log_frames.frames.map((frame) => ({
                ...frame,
                generation_id: "post-terminal-generation",
                perspective_epoch_id: "post-terminal-epoch",
            })),
        },
    };
    const postTerminal = {
        ...reset,
        segments: [
            ...reset.segments,
            {
                ...structuredClone(reset.segments[0]),
                segment_index: 2,
                runtime_session_id: "post-terminal-runtime",
                bootstrap: postTerminalBootstrap,
                deliveries: [],
                through_watermarks: postTerminalBootstrap.watermarks,
                end_reason: "perspective_retired",
            },
        ],
    };
    assert.throws(() => decodeSubjectivePlayerReplay(postTerminal), (error) => (error instanceof ContractValidationError
        && error.message.includes("terminal generation")));
    const sameGeneration = structuredClone(reset);
    const firstGeneration = sameGeneration.segments[0].bootstrap.protocol.generation_id;
    const second = sameGeneration.segments[1];
    second.bootstrap.protocol.generation_id = firstGeneration;
    second.bootstrap.combat_log_frames.generation_id = firstGeneration;
    for (const frame of second.bootstrap.combat_log_frames.frames) {
        frame.generation_id = firstGeneration;
    }
    for (const delivery of second.deliveries) {
        if (delivery.kind === "frame")
            delivery.frame.generation_id = firstGeneration;
        else
            delivery.frame.generation_id = firstGeneration;
    }
    assert.throws(() => decodeSubjectivePlayerReplay(sameGeneration), ContractValidationError);
});
test("player replay generations are contiguous while parallel siblings remain lawful", () => {
    const base = rotatedSubjectiveReplay();
    const template = base.segments[1];
    const identifiedSegment = (generationId, perspectiveEpochId, runtimeSessionId, terminal) => {
        const bootstrap = {
            ...structuredClone(template.bootstrap),
            protocol: {
                ...template.bootstrap.protocol,
                generation_id: generationId,
            },
            perspective: {
                ...template.bootstrap.perspective,
                perspective_epoch_id: perspectiveEpochId,
            },
            combat_log_frames: {
                ...template.bootstrap.combat_log_frames,
                generation_id: generationId,
                perspective_epoch_id: perspectiveEpochId,
                frames: template.bootstrap.combat_log_frames.frames.map((frame) => ({
                    ...frame,
                    generation_id: generationId,
                    perspective_epoch_id: perspectiveEpochId,
                })),
            },
        };
        return {
            ...structuredClone(template),
            runtime_session_id: runtimeSessionId,
            bootstrap,
            deliveries: terminal
                ? template.deliveries.map((delivery) => (delivery.kind === "frame"
                    ? {
                        ...delivery,
                        frame: {
                            ...delivery.frame,
                            generation_id: generationId,
                            perspective_epoch_id: perspectiveEpochId,
                        },
                    }
                    : {
                        ...delivery,
                        frame: {
                            ...delivery.frame,
                            generation_id: generationId,
                            perspective_epoch_id: perspectiveEpochId,
                        },
                    }))
                : [],
            through_watermarks: terminal
                ? template.through_watermarks
                : bootstrap.watermarks,
            end_reason: terminal ? "encounter_ended" : "perspective_retired",
        };
    };
    const a0 = identifiedSegment("generation-a", "a-epoch-0", "a-runtime-0", false);
    const a1 = identifiedSegment("generation-a", "a-epoch-1", "a-runtime-1", false);
    const b0 = identifiedSegment("generation-b", "b-epoch-0", "b-runtime-0", true);
    const b1 = identifiedSegment("generation-b", "b-epoch-1", "b-runtime-1", true);
    const lawful = {
        ...base,
        segments: [a0, a1, b0, b1].map((segment, segment_index) => ({
            ...segment,
            segment_index,
        })),
    };
    assert.doesNotThrow(() => decodeSubjectivePlayerReplay(lawful));
    const resurrected = {
        ...lawful,
        segments: [a0, b0, a1, b1].map((segment, segment_index) => ({
            ...segment,
            segment_index,
        })),
    };
    assert.throws(() => decodeSubjectivePlayerReplay(resurrected), (error) => (error instanceof ContractValidationError
        && error.message.includes("contiguous segment runs")));
    const withTerminalConflict = (updates) => ({
        ...lawful,
        segments: lawful.segments.map((segment, index) => (index !== 3
            ? segment
            : {
                ...segment,
                deliveries: segment.deliveries.map((delivery) => (delivery.kind !== "frame"
                    ? delivery
                    : {
                        ...delivery,
                        frame: {
                            ...delivery.frame,
                            presentation: delivery.frame.presentation.map((cue) => (cue.kind === "encounter" && cue.transition === "end"
                                ? { ...cue, ...updates }
                                : cue)),
                        },
                    })),
            })),
    });
    for (const updates of [
        { source_event_uuid: "conflicting-terminal-event" },
        { reason: "conflicting terminal reason" },
    ]) {
        assert.throws(() => decodeSubjectivePlayerReplay(withTerminalConflict(updates)), (error) => (error instanceof ContractValidationError
            && error.message.includes("terminal event identity")));
    }
    const sharedTerminalEventUuid = "00000000-0000-4000-8000-000000000099";
    const withOrdinarySource = (segment) => ({
        ...segment,
        deliveries: segment.deliveries.map((delivery) => (delivery.kind !== "frame"
            ? delivery
            : {
                ...delivery,
                frame: {
                    ...delivery.frame,
                    presentation: delivery.frame.presentation.map((cue) => (cue.kind === "encounter" && cue.transition === "end"
                        ? { ...cue, source_event_uuid: sharedTerminalEventUuid }
                        : cue)),
                },
            })),
    });
    const ordinaryB0 = withOrdinarySource(b0);
    const b1TerminalDelivery = b1.deliveries.find((delivery) => (delivery.kind === "frame"
        && delivery.frame.presentation.some((cue) => cue.kind === "encounter" && cue.transition === "end")));
    assert.ok(b1TerminalDelivery?.kind === "frame");
    const b1TerminalCue = b1TerminalDelivery.frame.presentation.find((cue) => (cue.kind === "encounter" && cue.transition === "end"));
    assert.ok(b1TerminalCue !== undefined);
    const resetWatermarks = {
        ...b1TerminalDelivery.frame.watermarks,
        presentation_cursor: b1TerminalDelivery.frame.presentation_from_cursor,
    };
    const resetB1 = {
        ...b1,
        deliveries: b1.deliveries.map((delivery) => (delivery !== b1TerminalDelivery
            ? delivery
            : {
                ...delivery,
                frame: {
                    ...delivery.frame,
                    watermarks: resetWatermarks,
                    presentation: [],
                    presentation_delivery: "presentation_reset_required",
                    presentation_reset_reason: "source_presentation_discontinuity",
                    encounter_terminal: {
                        encounter_uuid: b1TerminalCue.encounter_uuid,
                        source_event_uuid: sharedTerminalEventUuid,
                        source_event_cursor: b1TerminalCue.source_event_cursor,
                        terminal_authority_id: (`b-epoch-1:${resetWatermarks.observation_cursor}:reset-terminal:${sharedTerminalEventUuid}`),
                        reason: b1TerminalCue.reason,
                        projected_combatant_uuids: b1TerminalCue.projected_combatant_uuids,
                        terminal_barrier: true,
                    },
                },
            })),
        through_watermarks: resetWatermarks,
    };
    const mixedMode = {
        ...lawful,
        segments: [a0, a1, ordinaryB0, resetB1].map((segment, segment_index) => ({
            ...segment,
            segment_index,
        })),
    };
    assert.throws(() => decodeSubjectivePlayerReplay(mixedMode), (error) => (error instanceof ContractValidationError
        && error.message.includes("terminal event identity")));
    const withForeignTerminalEncounter = (replay) => ({
        ...replay,
        segments: replay.segments.map((segment) => ({
            ...segment,
            deliveries: segment.deliveries.map((delivery) => (delivery.kind !== "frame"
                ? delivery
                : {
                    ...delivery,
                    frame: {
                        ...delivery.frame,
                        patches: delivery.frame.patches.map((patch) => (patch.kind === "encounter_replace"
                            && patch.encounter?.state === "ended"
                            ? {
                                ...patch,
                                encounter: { ...patch.encounter, uuid: "foreign-encounter" },
                            }
                            : patch)),
                        presentation: delivery.frame.presentation.map((cue) => (cue.kind === "encounter" && cue.transition === "end"
                            ? { ...cue, encounter_uuid: "foreign-encounter" }
                            : cue)),
                        encounter_terminal: delivery.frame.encounter_terminal === null
                            ? null
                            : {
                                ...delivery.frame.encounter_terminal,
                                encounter_uuid: "foreign-encounter",
                            },
                    },
                })),
        })),
    });
    for (const foreign of [subjectiveReplay(), lawful]) {
        assert.throws(() => decodeSubjectivePlayerReplay(withForeignTerminalEncounter(foreign)), (error) => (error instanceof ContractValidationError
            && error.message.includes("another encounter")));
    }
});
test("player replay rejects observation or invalid resulting state after reset terminal", () => {
    const replay = resetTerminalSubjectiveReplay();
    const segment = replay.segments[0];
    const resetDelivery = segment.deliveries[0];
    assert.equal(resetDelivery.kind, "frame");
    if (resetDelivery.kind !== "frame")
        throw new Error("expected reset frame");
    const laterFrame = {
        ...resetDelivery.frame,
        watermarks: {
            ...resetDelivery.frame.watermarks,
            source_event_cursor: 2,
            observation_cursor: 2,
        },
        patches: [],
        presentation_delivery: "normal",
        presentation_reset_reason: null,
        encounter_terminal: null,
    };
    assert.throws(() => decodeSubjectivePlayerReplay({
        ...replay,
        terminal_source_event_cursor: 2,
        segments: [{
                ...segment,
                deliveries: [...segment.deliveries, { kind: "frame", frame: laterFrame }],
                through_watermarks: laterFrame.watermarks,
            }],
    }), ContractValidationError);
    const endedPatch = resetDelivery.frame.patches[0];
    assert.ok(endedPatch?.kind === "encounter_replace" && endedPatch.encounter !== null);
    for (const finalEncounter of [
        { ...endedPatch.encounter, state: "active" },
        null,
    ]) {
        assert.throws(() => decodeSubjectivePlayerReplay({
            ...replay,
            segments: [{
                    ...segment,
                    deliveries: [{
                            kind: "frame",
                            frame: {
                                ...resetDelivery.frame,
                                patches: [
                                    ...resetDelivery.frame.patches,
                                    { kind: "encounter_replace", encounter: finalEncounter },
                                ],
                            },
                        }],
                }],
        }), ContractValidationError);
    }
});
test("directory replay methods use exact routes and principal headers", async () => {
    const objective = objectiveReplay();
    const subjective = subjectiveReplay();
    const requests = [];
    const client = new GameDirectoryClient("/gateway/", {
        fetchImplementation: async (input, init) => {
            const url = String(input);
            const headers = new Headers(init?.headers);
            requests.push({
                url,
                principalId: headers.get("x-dnd-principal-id"),
                principalCapability: headers.get("x-dnd-principal-capability"),
            });
            return jsonResponse(url.includes("/diagnostics/objective-replay") ? objective : subjective);
        },
    });
    const credential = {
        principalId: "principal/id",
        principalCapability: "principal-secret",
    };
    await client.getObjectiveReplay("game/id", credential);
    await client.getSubjectiveReplay("game/id", "membership/id", credential);
    assert.deepEqual(requests, [
        {
            url: "/gateway/games/game%2Fid/diagnostics/objective-replay",
            principalId: "principal/id",
            principalCapability: "principal-secret",
        },
        {
            url: "/gateway/games/game%2Fid/memberships/membership%2Fid/replay",
            principalId: "principal/id",
            principalCapability: "principal-secret",
        },
    ]);
});
function objectiveReplayWithPhases(phases) {
    const replay = objectiveReplay();
    const template = replay.events[0];
    const events = phases.map((phase, index) => ({
        ...template,
        event_index: index,
        event_cursor: index + 1,
        event: {
            ...template.event,
            uuid: `event-${index + 1}`,
            lineage_uuid: `lineage-${index + 1}`,
            phase,
            canceled: phase === "cancel",
            canceled_from_phase: phase === "cancel" ? "execution" : null,
            is_first: index === 0,
            is_last: index === phases.length - 1,
        },
    }));
    return {
        ...replay,
        terminal_event_cursor: phases.length,
        events,
    };
}
function objectiveReplay() {
    const event = {
        wire_type: "dnd.core.events.EncounterEndEvent",
        name: "Encounter End",
        uuid: "event-1",
        source_entity_uuid: "system",
        source_entity_name: null,
        target_entity_uuid: null,
        target_entity_name: null,
        use_register: true,
        lineage_uuid: "lineage-1",
        turn_execution_id: null,
        timestamp: "2026-07-23T12:00:00Z",
        event_type: "encounter_end",
        phase: "completion",
        modified: false,
        canceled: false,
        canceled_from_phase: null,
        parent_event: null,
        status_message: null,
        outcome_code: null,
        outcome_source_entity_uuid: null,
        is_first: true,
        is_last: true,
        lineage_children_events: [],
        children_events: [],
        parent_lineage: null,
        children_lineages: [],
        encounter_uuid: "encounter",
        combatant_uuids: [],
        reason: "complete",
    };
    return {
        replay_contract_version: OBJECTIVE_REPLAY_CONTRACT_VERSION,
        replay_contract_hash: OBJECTIVE_REPLAY_CONTRACT_HASH,
        protocol: {
            timeline_contract_version: TIMELINE_CONTRACT_VERSION,
            timeline_contract_hash: TIMELINE_CONTRACT_HASH,
            event_contract_version: EVENT_CONTRACT_VERSION,
            event_contract_hash: EVENT_CONTRACT_HASH,
        },
        game_id: "game",
        encounter_uuid: "encounter",
        source_stream_id: "encounter",
        generation_id: "generation-a",
        seed: {
            event_cursor: 0,
            combat_log_cursor: 0,
            world: {
                state: {
                    grid: {
                        min_x: 0,
                        min_y: 0,
                        max_x: 0,
                        max_y: 0,
                        connectors: [],
                        tiles: [],
                    },
                    entities: [],
                    encounter: {
                        uuid: "encounter",
                        name: "Test",
                        state: "active",
                        round_number: 1,
                        current_turn_index: 0,
                        current_entity_uuid: null,
                        initiative_order: [],
                    },
                    floor_objects: [],
                },
                visibility: {},
                equipment_by_entity: {},
            },
        },
        terminal_event_cursor: 1,
        terminal_combat_log_cursor: 0,
        events: [{
                source_stream_id: "encounter",
                generation_id: "generation-a",
                event_index: 0,
                event_cursor: 1,
                combat_log_cursor: 0,
                event,
            }],
        combat_log_frames: {
            source_stream_id: "encounter",
            generation_id: "generation-a",
            perspective_epoch_id: "objective",
            projection: "objective",
            retained_from_cursor: 0,
            from_cursor: 0,
            through_cursor: 0,
            frames: [],
            total: 0,
        },
    };
}
function subjectiveReplay() {
    const liveSeed = bootstrap();
    const replayBootstrap = {
        ...liveSeed,
        protocol: { ...liveSeed.protocol, source_stream_id: "encounter" },
        combat_log_frames: { ...liveSeed.combat_log_frames, source_stream_id: "encounter" },
    };
    const encounter = replayBootstrap.world.state.encounter;
    assert.ok(encounter !== null);
    const frame = {
        source_stream_id: "encounter",
        generation_id: replayBootstrap.protocol.generation_id,
        perspective_epoch_id: replayBootstrap.perspective.perspective_epoch_id,
        watermarks: watermarks(1, 1, 1, 0),
        presentation_from_cursor: 0,
        patches: [{
                kind: "encounter_replace",
                encounter: { ...encounter, state: "ended" },
            }],
        presentation: [{
                presentation_cursor: 1,
                presentation_id: "encounter-end-1",
                parent_presentation_id: null,
                child_presentation_ids: [],
                source_event_cursor: 1,
                source_event_uuid: "event-1",
                binding_subject: null,
                trigger_binding_subject: null,
                source_item_fact: null,
                owner_application_id: null,
                kind: "encounter",
                encounter_uuid: "encounter",
                transition: "end",
                round_number: 1,
                acting_entity_uuid: null,
                reason: "complete",
                terminal_barrier: true,
                projected_combatant_uuids: ["hero", "monster"],
            }],
        presentation_delivery: "normal",
        presentation_reset_reason: null,
        encounter_terminal: null,
    };
    return {
        replay_contract_version: PLAYER_REPLAY_CONTRACT_VERSION,
        replay_contract_hash: PLAYER_REPLAY_CONTRACT_HASH,
        game_id: "game",
        encounter_uuid: "encounter",
        membership_id: "membership",
        terminal_source_event_cursor: 1,
        terminal_combat_log_cursor: 0,
        segments: [{
                segment_index: 0,
                membership_id: "membership",
                runtime_session_id: "runtime-session",
                bootstrap: replayBootstrap,
                deliveries: [{ kind: "frame", frame }],
                through_watermarks: frame.watermarks,
                end_reason: "encounter_ended",
            }],
    };
}
function resetTerminalSubjectiveReplay() {
    const replay = subjectiveReplay();
    const segment = replay.segments[0];
    const delivery = segment.deliveries[0];
    if (delivery.kind !== "frame")
        throw new Error("expected terminal frame");
    const cue = delivery.frame.presentation[0];
    if (cue?.kind !== "encounter")
        throw new Error("expected terminal encounter cue");
    const sourceEventUuid = "00000000-0000-4000-8000-000000000001";
    const watermarks = {
        ...delivery.frame.watermarks,
        presentation_cursor: 0,
    };
    const frame = {
        ...delivery.frame,
        watermarks,
        presentation_from_cursor: 0,
        presentation: [],
        presentation_delivery: "presentation_reset_required",
        presentation_reset_reason: "source_presentation_discontinuity",
        encounter_terminal: {
            encounter_uuid: cue.encounter_uuid,
            source_event_uuid: sourceEventUuid,
            source_event_cursor: 1,
            terminal_authority_id: (`perspective-a:1:reset-terminal:${sourceEventUuid}`),
            reason: cue.reason,
            projected_combatant_uuids: cue.projected_combatant_uuids,
            terminal_barrier: true,
        },
    };
    return {
        ...replay,
        segments: [{
                ...segment,
                deliveries: [{ kind: "frame", frame }],
                through_watermarks: watermarks,
            }],
    };
}
function rotatedSubjectiveReplay() {
    const terminal = subjectiveReplay();
    const terminalSegment = terminal.segments[0];
    const firstBootstrap = structuredClone(terminalSegment.bootstrap);
    const stateOnly = {
        ...terminalSegment.deliveries[0].frame,
        watermarks: watermarks(5, 1, 0, 0),
        presentation_from_cursor: 0,
        patches: [],
        presentation: [],
        presentation_delivery: "normal",
        presentation_reset_reason: null,
        encounter_terminal: null,
    };
    const firstLogWatermarks = watermarks(5, 1, 0, 1);
    const secondLogWatermarks = watermarks(5, 1, 0, 2);
    const logFrames = [
        {
            source_stream_id: "encounter",
            generation_id: "generation-a",
            perspective_epoch_id: "perspective-a",
            projection: "subjective",
            combat_log_cursor: 1,
            event_cursor: 5,
            entry: null,
        },
        {
            source_stream_id: "encounter",
            generation_id: "generation-a",
            perspective_epoch_id: "perspective-a",
            projection: "subjective",
            combat_log_cursor: 2,
            event_cursor: 5,
            entry: null,
        },
    ];
    const first = {
        ...terminalSegment,
        segment_index: 0,
        bootstrap: firstBootstrap,
        deliveries: [
            { kind: "frame", frame: stateOnly },
            { kind: "combat_log", watermarks: firstLogWatermarks, frame: logFrames[0] },
            { kind: "combat_log", watermarks: secondLogWatermarks, frame: logFrames[1] },
        ],
        through_watermarks: secondLogWatermarks,
        end_reason: "perspective_retired",
    };
    const secondBootstrap = {
        ...structuredClone(terminalSegment.bootstrap),
        protocol: {
            ...terminalSegment.bootstrap.protocol,
            generation_id: "generation-a",
        },
        perspective: {
            ...terminalSegment.bootstrap.perspective,
            perspective_epoch_id: "perspective-b",
        },
        watermarks: watermarks(5, 0, 0, 2),
        combat_log_frames: {
            source_stream_id: "encounter",
            generation_id: "generation-a",
            perspective_epoch_id: "perspective-b",
            projection: "subjective",
            retained_from_cursor: 0,
            from_cursor: 0,
            through_cursor: 2,
            frames: logFrames.map((frame) => ({
                ...frame,
                generation_id: "generation-a",
                perspective_epoch_id: "perspective-b",
            })),
            total: 2,
        },
    };
    const originalTerminal = terminalSegment.deliveries[0];
    if (originalTerminal.kind !== "frame")
        throw new Error("expected terminal frame");
    const terminalDelivery = {
        kind: "frame",
        frame: {
            ...structuredClone(originalTerminal.frame),
            generation_id: "generation-a",
            perspective_epoch_id: "perspective-b",
            watermarks: watermarks(6, 1, 1, 2),
            presentation: originalTerminal.frame.presentation.map((cue) => ({
                ...cue,
                source_event_cursor: 6,
            })),
        },
    };
    const second = {
        ...terminalSegment,
        segment_index: 1,
        runtime_session_id: first.runtime_session_id,
        bootstrap: secondBootstrap,
        deliveries: [terminalDelivery],
        through_watermarks: terminalDelivery.frame.watermarks,
    };
    return {
        ...terminal,
        terminal_source_event_cursor: 6,
        terminal_combat_log_cursor: 2,
        segments: [first, second],
    };
}
function generationResetSubjectiveReplay() {
    const replay = rotatedSubjectiveReplay();
    const first = replay.segments[0];
    const terminal = replay.segments[1];
    const generationId = "generation-reset-b";
    const terminalDelivery = terminal.deliveries[0];
    if (terminalDelivery.kind !== "frame")
        throw new Error("expected terminal frame");
    const bootstrap = {
        ...structuredClone(terminal.bootstrap),
        protocol: {
            ...terminal.bootstrap.protocol,
            generation_id: generationId,
        },
        watermarks: watermarks(0, 0, 0, 0),
        combat_log_frames: {
            ...terminal.bootstrap.combat_log_frames,
            generation_id: generationId,
            retained_from_cursor: 0,
            from_cursor: 0,
            through_cursor: 0,
            frames: [],
            total: 0,
        },
    };
    const frame = {
        ...structuredClone(terminalDelivery.frame),
        generation_id: generationId,
        watermarks: watermarks(1, 1, 1, 0),
        presentation: terminalDelivery.frame.presentation.map((cue) => ({
            ...cue,
            source_event_cursor: 1,
        })),
    };
    assert.ok(first.through_watermarks.source_event_cursor > frame.watermarks.source_event_cursor);
    assert.ok(first.through_watermarks.combat_log_cursor > frame.watermarks.combat_log_cursor);
    return {
        ...replay,
        terminal_source_event_cursor: 1,
        terminal_combat_log_cursor: 0,
        segments: [
            first,
            {
                ...terminal,
                bootstrap,
                deliveries: [{ kind: "frame", frame }],
                through_watermarks: frame.watermarks,
            },
        ],
    };
}
function threeSegmentSubjectiveReplay() {
    const two = rotatedSubjectiveReplay();
    const terminal = two.segments[1];
    const middleBootstrap = structuredClone(terminal.bootstrap);
    const middleFrame = {
        ...structuredClone(terminal.deliveries[0].frame),
        watermarks: watermarks(6, 1, 0, 2),
        presentation_from_cursor: 0,
        patches: [],
        presentation: [],
        presentation_delivery: "normal",
        presentation_reset_reason: null,
        encounter_terminal: null,
    };
    const middle = {
        ...terminal,
        segment_index: 1,
        deliveries: [{ kind: "frame", frame: middleFrame }],
        through_watermarks: middleFrame.watermarks,
        end_reason: "perspective_retired",
    };
    const finalBootstrap = {
        ...structuredClone(terminal.bootstrap),
        protocol: { ...terminal.bootstrap.protocol, generation_id: "generation-c" },
        perspective: {
            ...terminal.bootstrap.perspective,
            perspective_epoch_id: "perspective-c",
        },
        watermarks: watermarks(6, 0, 0, 2),
        combat_log_frames: {
            ...terminal.bootstrap.combat_log_frames,
            generation_id: "generation-c",
            perspective_epoch_id: "perspective-c",
            frames: terminal.bootstrap.combat_log_frames.frames.map((frame) => ({
                ...frame,
                generation_id: "generation-c",
                perspective_epoch_id: "perspective-c",
            })),
        },
    };
    const originalTerminal = terminal.deliveries[0];
    if (originalTerminal.kind !== "frame")
        throw new Error("expected terminal frame");
    const finalFrame = {
        ...structuredClone(originalTerminal.frame),
        generation_id: "generation-c",
        perspective_epoch_id: "perspective-c",
        watermarks: watermarks(7, 1, 1, 2),
        presentation: originalTerminal.frame.presentation.map((cue) => ({
            ...cue,
            source_event_cursor: 7,
        })),
    };
    return {
        ...two,
        terminal_source_event_cursor: 7,
        segments: [
            two.segments[0],
            middle,
            {
                ...terminal,
                segment_index: 2,
                runtime_session_id: middle.runtime_session_id,
                bootstrap: finalBootstrap,
                deliveries: [{ kind: "frame", frame: finalFrame }],
                through_watermarks: finalFrame.watermarks,
            },
        ],
    };
}
function jsonResponse(payload) {
    return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
    });
}
//# sourceMappingURL=replay.test.js.map