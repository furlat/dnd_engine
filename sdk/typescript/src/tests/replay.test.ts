import assert from "node:assert/strict";
import test from "node:test";

import {
  EVENT_CONTRACT_HASH,
  EVENT_CONTRACT_VERSION,
  OBJECTIVE_REPLAY_CONTRACT_HASH,
  OBJECTIVE_REPLAY_CONTRACT_VERSION,
  PLAYER_REPLAY_CONTRACT_HASH,
  PLAYER_REPLAY_CONTRACT_VERSION,
  TIMELINE_CONTRACT_HASH,
  TIMELINE_CONTRACT_VERSION,
  ContractValidationError,
  GameDirectoryClient,
  decodeObjectiveReplay,
  decodeSubjectivePlayerReplay,
  type EncounterEndEvent,
  type ObjectiveCombatLogFramesResponse,
  type ObjectiveReplayBundle,
  type SubjectivePlayerReplayBundle,
  type SubjectiveReplicationFrame,
} from "../index.js";
import { bootstrap, watermarks } from "./fixtures.js";

test("replay decoders accept only complete reducer-native objective and subjective bundles", () => {
  const objective = objectiveReplay();
  const subjective = subjectiveReplay();
  const objectiveLogs: ObjectiveCombatLogFramesResponse = objective.combat_log_frames;

  assert.equal(decodeObjectiveReplay(objective), objective);
  assert.equal(decodeSubjectivePlayerReplay(subjective), subjective);
  assert.equal(objectiveLogs.projection, "objective");
});

test("objective replay decoder rejects non-completion and false terminal input", () => {
  const nonCompletion = structuredClone(objectiveReplay()) as {
    events: Array<{ event: { phase: string } }>;
  };
  const falseTerminal = structuredClone(objectiveReplay()) as {
    events: Array<{ event: { event_type: string } }>;
  };
  const event = nonCompletion.events[0];
  const terminal = falseTerminal.events[0];
  assert.ok(event !== undefined && terminal !== undefined);
  event.event.phase = "execution";
  terminal.event.event_type = "encounter_start";

  assert.throws(() => decodeObjectiveReplay(nonCompletion), ContractValidationError);
  assert.throws(() => decodeObjectiveReplay(falseTerminal), ContractValidationError);
});

test("objective replay decoder rejects a source namespace other than its encounter", () => {
  const mismatched = structuredClone(objectiveReplay()) as {
    source_stream_id: string;
    combat_log_frames: { source_stream_id: string };
    events: Array<{ source_stream_id: string }>;
  };
  mismatched.source_stream_id = "other-source";
  mismatched.combat_log_frames.source_stream_id = "other-source";
  for (const frame of mismatched.events) {
    frame.source_stream_id = "other-source";
  }

  assert.throws(() => decodeObjectiveReplay(mismatched), ContractValidationError);
});

test("player replay decoder rejects objective, raw-event, and malformed presentation input", () => {
  const objectiveLog = structuredClone(subjectiveReplay()) as {
    segments: Array<{ bootstrap: { combat_log_frames: { projection: string } } }>;
  };
  const malformedGraph = structuredClone(subjectiveReplay()) as {
    segments: Array<{
      deliveries: Array<{
        kind: string;
        frame: { presentation: Array<{ child_presentation_ids: string[] }> };
      }>;
    }>;
  };
  const firstSegment = objectiveLog.segments[0];
  const malformedSegment = malformedGraph.segments[0];
  assert.ok(firstSegment !== undefined && malformedSegment !== undefined);
  firstSegment.bootstrap.combat_log_frames.projection = "objective";
  const delivery = malformedSegment.deliveries[0];
  const cue = delivery?.frame.presentation[0];
  assert.ok(delivery !== undefined && cue !== undefined);
  cue.child_presentation_ids.push("hidden-raw-lineage");

  assert.throws(() => decodeSubjectivePlayerReplay(objectiveLog), ContractValidationError);
  assert.throws(
    () => decodeSubjectivePlayerReplay({ ...subjectiveReplay(), raw_events: [] }),
    ContractValidationError,
  );
  assert.throws(() => decodeSubjectivePlayerReplay(malformedGraph), ContractValidationError);
});

test("directory replay methods use exact routes and principal headers", async () => {
  const objective = objectiveReplay();
  const subjective = subjectiveReplay();
  const requests: Array<{
    readonly url: string;
    readonly principalId: string | null;
    readonly principalCapability: string | null;
  }> = [];
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

function objectiveReplay(): ObjectiveReplayBundle {
  const event: EncounterEndEvent = {
    wire_type: "dnd.core.events.EncounterEndEvent",
    name: "Encounter End",
    uuid: "event-1",
    source_entity_uuid: "system",
    source_entity_name: null,
    target_entity_uuid: null,
    target_entity_name: null,
    context: null,
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
          grid: { min_x: 0, min_y: 0, max_x: 0, max_y: 0, tiles: [] },
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

function subjectiveReplay(): SubjectivePlayerReplayBundle {
  const liveSeed = bootstrap();
  const replayBootstrap = {
    ...liveSeed,
    protocol: { ...liveSeed.protocol, source_stream_id: "encounter" },
    combat_log_frames: { ...liveSeed.combat_log_frames, source_stream_id: "encounter" },
  };
  const encounter = replayBootstrap.world.state.encounter;
  assert.ok(encounter !== null);
  const frame: SubjectiveReplicationFrame = {
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
      content_attributions: [],
      kind: "encounter",
      encounter_uuid: "encounter",
      transition: "end",
      round_number: 1,
      acting_entity_uuid: null,
      reason: "complete",
      terminal_barrier: true,
      projected_combatant_uuids: ["hero", "monster"],
    }],
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

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
