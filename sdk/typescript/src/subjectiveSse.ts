import {
  PLAYER_REPLICATION_CONTRACT_HASH,
  PLAYER_REPLICATION_CONTRACT_VERSION,
  type PlayerReplicationProtocolIdentity,
  type PlayerReplicationWatermarks,
  type SubjectiveCombatLogDelivery,
  type SubjectivePerspective,
  type SubjectivePresentationCue,
  type SubjectiveReplicationFrame,
  type SubjectiveStreamDelivery,
} from "./generated/contracts.generated.js";
import { SseDecoder, type SseMessage } from "./sse.js";
import { assertSubjectiveWorldPatch } from "./reducer.js";
import { ContractValidationError, decodeAlias } from "./validation.js";

export type SubjectiveSseEnvelope =
  | { readonly event: "sync"; readonly id: string; readonly data: Extract<SubjectiveStreamDelivery, { readonly kind: "sync" }> }
  | { readonly event: "frame"; readonly id: string; readonly data: Extract<SubjectiveStreamDelivery, { readonly kind: "frame" }> }
  | { readonly event: "combat_log"; readonly id: string; readonly data: Extract<SubjectiveStreamDelivery, { readonly kind: "combat_log" }> };

export interface SubjectiveStreamPosition {
  readonly sourceStreamId: string;
  readonly generationId: string;
  readonly perspectiveEpochId: string;
  readonly sourceEventCursor: number;
  readonly observationCursor: number;
  readonly presentationCursor: number;
  readonly combatLogCursor: number;
}

export class SubjectiveSseDecoder {
  private readonly syntax = new SseDecoder();

  feed(chunk: string): SubjectiveSseEnvelope[] {
    return this.syntax.feed(chunk).map(decodeSubjectiveEnvelope);
  }

  finish(): SubjectiveSseEnvelope[] {
    return this.syntax.finish().map(decodeSubjectiveEnvelope);
  }
}

/** Stateful ordering check used by reconnecting stream consumers. */
export class SubjectiveStreamFollower {
  private positionValue: SubjectiveStreamPosition;
  private synchronized = false;

  constructor(position: SubjectiveStreamPosition) {
    assertStreamPosition(position);
    this.positionValue = { ...position };
  }

  position(): SubjectiveStreamPosition {
    return { ...this.positionValue };
  }

  ingest(envelope: SubjectiveSseEnvelope): SubjectiveStreamPosition {
    const watermarks = deliveryWatermarks(envelope.data);
    assertSseId(envelope.id, watermarks);
    if (envelope.event === "sync") {
      if (this.synchronized) {
        throw new ContractValidationError("$subjective.sse.sync", "stream emitted more than one sync");
      }
      assertProtocol(envelope.data.protocol);
      assertPerspective(envelope.data.perspective);
      this.assertIdentity(
        envelope.data.protocol.source_stream_id,
        envelope.data.protocol.generation_id,
        envelope.data.perspective.perspective_epoch_id,
        "$subjective.sse.sync",
      );
      assertDominates(watermarks, positionWatermarks(this.positionValue), "$subjective.sse.sync.watermarks");
      this.synchronized = true;
      return this.position();
    }
    if (!this.synchronized) {
      throw new ContractValidationError("$subjective.sse", "sync must be the first delivery");
    }

    if (envelope.event === "frame") {
      const frame = envelope.data.frame;
      this.assertIdentity(
        frame.source_stream_id,
        frame.generation_id,
        frame.perspective_epoch_id,
        "$subjective.sse.frame",
      );
      assertSubjectiveFrame(frame);
      if (frame.watermarks.observation_cursor !== this.positionValue.observationCursor + 1) {
        throw new ContractValidationError(
          "$subjective.sse.frame.watermarks.observation_cursor",
          `expected contiguous cursor ${this.positionValue.observationCursor + 1}`,
        );
      }
      if (frame.presentation_from_cursor !== this.positionValue.presentationCursor) {
        throw new ContractValidationError(
          "$subjective.sse.frame.presentation_from_cursor",
          "presentation window is not contiguous",
        );
      }
      if (frame.watermarks.source_event_cursor < this.positionValue.sourceEventCursor) {
        throw new ContractValidationError("$subjective.sse.frame.watermarks", "source cursor moved backwards");
      }
      if (frame.watermarks.combat_log_cursor !== this.positionValue.combatLogCursor) {
        throw new ContractValidationError(
          "$subjective.sse.frame.watermarks.combat_log_cursor",
          "frame delivery cannot advance the combat-log cursor",
        );
      }
      this.positionValue = {
        ...this.positionValue,
        sourceEventCursor: frame.watermarks.source_event_cursor,
        observationCursor: frame.watermarks.observation_cursor,
        presentationCursor: frame.watermarks.presentation_cursor,
      };
    } else {
      assertSubjectiveCombatLogDelivery(envelope.data);
      const frame = envelope.data.frame;
      this.assertIdentity(
        frame.source_stream_id,
        frame.generation_id,
        frame.perspective_epoch_id,
        "$subjective.sse.combat_log",
      );
      if (frame.combat_log_cursor !== this.positionValue.combatLogCursor + 1) {
        throw new ContractValidationError(
          "$subjective.sse.combat_log.frame.combat_log_cursor",
          `expected contiguous cursor ${this.positionValue.combatLogCursor + 1}`,
        );
      }
      if (
        envelope.data.watermarks.source_event_cursor !== this.positionValue.sourceEventCursor
        || envelope.data.watermarks.observation_cursor !== this.positionValue.observationCursor
        || envelope.data.watermarks.presentation_cursor !== this.positionValue.presentationCursor
        || envelope.data.watermarks.combat_log_cursor !== frame.combat_log_cursor
      ) {
        throw new ContractValidationError(
          "$subjective.sse.combat_log.watermarks",
          "combat-log delivery may advance only its own cursor",
        );
      }
      this.positionValue = {
        ...this.positionValue,
        combatLogCursor: frame.combat_log_cursor,
      };
    }
    return this.position();
  }

  private assertIdentity(source: string, generation: string, perspective: string, path: string): void {
    if (source !== this.positionValue.sourceStreamId) {
      throw new ContractValidationError(`${path}.source_stream_id`, "source stream changed");
    }
    if (generation !== this.positionValue.generationId) {
      throw new ContractValidationError(`${path}.generation_id`, "generation changed");
    }
    if (perspective !== this.positionValue.perspectiveEpochId) {
      throw new ContractValidationError(`${path}.perspective_epoch_id`, "perspective epoch changed");
    }
  }
}

export function decodeSubjectiveEnvelope(message: SseMessage): SubjectiveSseEnvelope {
  if (message.event !== "sync" && message.event !== "frame" && message.event !== "combat_log") {
    throw new ContractValidationError(
      "$subjective.sse.event",
      `unsupported subjective event ${message.event}`,
    );
  }
  if (message.id === null) {
    throw new ContractValidationError("$subjective.sse.id", "subjective delivery requires an ID");
  }
  const data = decodeAlias("SubjectiveStreamDelivery", message.data);
  if (data.kind !== message.event) {
    throw new ContractValidationError("$subjective.sse.data.kind", "event name and delivery kind differ");
  }
  if (data.kind === "sync") {
    assertProtocol(data.protocol);
    assertPerspective(data.perspective);
  } else if (data.kind === "frame") {
    assertSubjectiveFrame(data.frame);
  } else {
    assertSubjectiveCombatLogDelivery(data);
  }
  assertSseId(message.id, deliveryWatermarks(data));
  return { event: data.kind, id: message.id, data } as SubjectiveSseEnvelope;
}

export function assertProtocol(protocol: PlayerReplicationProtocolIdentity): void {
  if (protocol.player_replication_contract_version !== PLAYER_REPLICATION_CONTRACT_VERSION) {
    throw new ContractValidationError(
      "$subjective.protocol.player_replication_contract_version",
      "unsupported player replication contract version",
    );
  }
  if (protocol.player_replication_contract_hash !== PLAYER_REPLICATION_CONTRACT_HASH) {
    throw new ContractValidationError(
      "$subjective.protocol.player_replication_contract_hash",
      "player replication contract hash mismatch",
    );
  }
  requireNonEmpty(protocol.source_stream_id, "$subjective.protocol.source_stream_id");
  requireNonEmpty(protocol.generation_id, "$subjective.protocol.generation_id");
}

export function assertPerspective(perspective: SubjectivePerspective): void {
  requireNonEmpty(perspective.perspective_epoch_id, "$subjective.perspective.perspective_epoch_id");
  const controlled = new Set(perspective.controlled_entity_uuids);
  const observers = new Set(perspective.observer_entity_uuids);
  if (
    controlled.size !== perspective.controlled_entity_uuids.length
    || observers.size !== perspective.observer_entity_uuids.length
    || observers.size === 0
    || !observers.has(perspective.active_observer_uuid)
  ) {
    throw new ContractValidationError("$subjective.perspective", "invalid observer union");
  }
  if (perspective.kind === "controlled_knowledge_union") {
    if (controlled.size === 0 || !sameSet(controlled, observers)) {
      throw new ContractValidationError("$subjective.perspective", "invalid controlled observer union");
    }
  } else if (controlled.size !== 0) {
    throw new ContractValidationError("$subjective.perspective", "spectator cannot control entities");
  }
}

export function assertSubjectiveFrame(frame: SubjectiveReplicationFrame): void {
  assertWatermarks(frame.watermarks, "$subjective.frame.watermarks");
  requirePositiveCursor(frame.watermarks.observation_cursor, "$subjective.frame.watermarks.observation_cursor");
  requireCursor(frame.presentation_from_cursor, "$subjective.frame.presentation_from_cursor");
  if (
    frame.presentation.length
    !== frame.watermarks.presentation_cursor - frame.presentation_from_cursor
  ) {
    throw new ContractValidationError("$subjective.frame.presentation", "presentation window is not exact");
  }
  frame.patches.forEach((patch, index) => {
    assertSubjectiveWorldPatch(patch, `$subjective.frame.patches[${index}]`);
  });
  const byId = new Map<string, SubjectivePresentationCue>();
  frame.presentation.forEach((cue, index) => {
    const path = `$subjective.frame.presentation[${index}]`;
    const expected = frame.presentation_from_cursor + index + 1;
    if (cue.presentation_cursor !== expected) {
      throw new ContractValidationError(path, "cues are not contiguous");
    }
    if (cue.source_event_cursor > frame.watermarks.source_event_cursor || byId.has(cue.presentation_id)) {
      throw new ContractValidationError(path, "invalid cue source or duplicate ID");
    }
    assertPresentationCueSemantics(cue, path);
    byId.set(cue.presentation_id, cue);
  });
  frame.presentation.forEach((cue, index) => {
    const path = `$subjective.frame.presentation[${index}]`;
    if (new Set(cue.child_presentation_ids).size !== cue.child_presentation_ids.length) {
      throw new ContractValidationError(path, "duplicate child ID");
    }
    if (cue.child_presentation_ids.includes(cue.presentation_id)) {
      throw new ContractValidationError(path, "cue cannot be its own child");
    }
    if (cue.parent_presentation_id !== null) {
      const parent = byId.get(cue.parent_presentation_id);
      if (parent === undefined || !parent.child_presentation_ids.includes(cue.presentation_id)) {
        throw new ContractValidationError(path, "dangling parent edge");
      }
    }
    let previousChildCursor = -1;
    for (const childId of cue.child_presentation_ids) {
      const child = byId.get(childId);
      if (
        child === undefined
        || child.parent_presentation_id !== cue.presentation_id
        || child.presentation_cursor <= cue.presentation_cursor
        || child.presentation_cursor <= previousChildCursor
      ) {
        throw new ContractValidationError(path, "invalid closed graph edge");
      }
      previousChildCursor = child.presentation_cursor;
    }
    assertPresentationGraphSemantics(cue, byId, path);
  });
}

function assertPresentationCueSemantics(cue: SubjectivePresentationCue, path: string): void {
  switch (cue.kind) {
    case "movement": {
      const representedSteps = cue.trajectory.length - 1;
      if (cue.path_start_index + representedSteps > cue.path_total_steps) {
        throw new ContractValidationError(path, "movement trajectory exceeds declared path order");
      }
      return;
    }
    case "attack":
      if (new Set(cue.damage_types).size !== cue.damage_types.length) {
        throw new ContractValidationError(path, "attack damage types must be unique");
      }
      if (cue.delivery === "projectile" && cue.projectile_type === null) {
        throw new ContractValidationError(path, "projectile attack requires a projectile type");
      }
      if (cue.delivery === "melee" && cue.projectile_type !== null) {
        throw new ContractValidationError(path, "melee attack cannot carry a projectile type");
      }
      if (!sameOrderedValues(cue.impact_effect_presentation_ids, cue.child_presentation_ids)) {
        throw new ContractValidationError(path, "attack impacts must exactly equal ordered children");
      }
      return;
    case "spell": {
      const indexes = cue.targets.map((target) => target.application_index);
      if (!indexes.every((value, index) => value === index)) {
        throw new ContractValidationError(path, "spell applications must be contiguous and ordered");
      }
      const applicationIds = cue.targets.map((target) => target.application_id);
      if (new Set(applicationIds).size !== applicationIds.length) {
        throw new ContractValidationError(path, "spell application IDs must be unique");
      }
      for (const [index, target] of cue.targets.entries()) {
        assertSpellTargetSemantics(target, `${path}.targets[${index}]`);
      }
      if (
        (cue.delivery === "projectile" || cue.delivery === "missile_volley")
        && cue.projectile_type === null
      ) {
        throw new ContractValidationError(path, "projectile spell route requires a projectile type");
      }
      if (cue.delivery === "aoe" && cue.area === null) {
        throw new ContractValidationError(path, "AOE spell route requires typed area geometry");
      }
      if (cue.delivery !== "aoe" && cue.area !== null) {
        throw new ContractValidationError(path, "non-AOE spell route cannot carry area geometry");
      }
      if (cue.area !== null) assertAreaGeometrySemantics(cue.area, `${path}.area`);
      const effects = cue.targets.flatMap((target) => target.effect_presentation_ids);
      if (new Set(effects).size !== effects.length) {
        throw new ContractValidationError(path, "one spell effect cannot belong to multiple applications");
      }
      if (!sameOrderedValues(effects, cue.child_presentation_ids)) {
        throw new ContractValidationError(path, "spell effects must exactly equal ordered children");
      }
      return;
    }
    case "item_action":
      if (new Set(cue.hidden_slots).size !== cue.hidden_slots.length) {
        throw new ContractValidationError(path, "item hidden slots must be unique");
      }
      if (!sameOrderedValues(cue.effect_presentation_ids, cue.child_presentation_ids)) {
        throw new ContractValidationError(path, "item effects must exactly equal ordered children");
      }
      return;
    case "forced_movement":
      if (cue.parent_presentation_id !== cue.actor_action_presentation_id) {
        throw new ContractValidationError(path, "forced movement must attach to its actor action");
      }
      if (samePosition(cue.start_position, cue.end_position)) {
        throw new ContractValidationError(path, "forced movement must change position");
      }
      if (cue.child_presentation_ids.length !== 0) {
        throw new ContractValidationError(path, "forced movement must be a leaf");
      }
      return;
    case "shove":
      assertShoveSemantics(cue, path);
      return;
    case "lifecycle_cause":
      if (cue.cause_kind === "death_save") {
        if (cue.death_save_outcome === null) {
          throw new ContractValidationError(path, "death-save cause requires an outcome");
        }
      } else if (cue.death_save_outcome !== null) {
        throw new ContractValidationError(path, "death-save outcome belongs only to a death-save cause");
      }
      if (cue.child_presentation_ids.length !== 1) {
        throw new ContractValidationError(path, "lifecycle cause must own exactly one life-state child");
      }
      return;
    case "life_state":
      if (cue.previous === cue.current) {
        throw new ContractValidationError(path, "life-state cue requires a real transition");
      }
      if (cue.parent_presentation_id !== cue.causing_effect_presentation_id) {
        throw new ContractValidationError(path, "life-state transition must attach to its cause");
      }
      if (cue.current === "stable" && cue.reason !== "stabilization") {
        throw new ContractValidationError(path, "stable transition requires stabilization");
      }
      if (cue.previous === "dead" && cue.current === "alive" && cue.reason !== "revival") {
        throw new ContractValidationError(path, "dead-to-alive transition requires revival");
      }
      if (
        (cue.previous === "dying" || cue.previous === "stable")
        && cue.current === "alive"
        && cue.reason !== "healing"
        && cue.reason !== "direct_state_check"
      ) {
        throw new ContractValidationError(path, "recovery to alive requires healing or direct correction");
      }
      return;
    case "light": {
      const positions = cue.cells.map((cell) => positionKey(cell.position));
      if (new Set(positions).size !== positions.length) {
        throw new ContractValidationError(path, "light replacement positions must be unique");
      }
      return;
    }
    case "equipment":
      if (cue.visual_loadout.entity_uuid !== cue.entity_uuid) {
        throw new ContractValidationError(path, "equipment loadout must belong to its entity");
      }
      assertVisualLoadoutSemantics(cue.visual_loadout, `${path}.visual_loadout`);
      return;
    case "encounter":
      if (new Set(cue.projected_combatant_uuids).size !== cue.projected_combatant_uuids.length) {
        throw new ContractValidationError(path, "terminal combatants must be unique");
      }
      if (cue.transition === "end") {
        if (!cue.terminal_barrier) {
          throw new ContractValidationError(path, "encounter end requires a terminal barrier");
        }
      } else if (cue.terminal_barrier || cue.projected_combatant_uuids.length !== 0) {
        throw new ContractValidationError(path, "terminal metadata belongs only to encounter end");
      }
      return;
    case "damage":
    case "heal":
    case "condition":
    case "door":
      return;
    default:
      assertNever(cue);
  }
}

function assertSpellTargetSemantics(
  target: Extract<SubjectivePresentationCue, { readonly kind: "spell" }>["targets"][number],
  path: string,
): void {
  if (target.target_uuid === null && target.position === null) {
    throw new ContractValidationError(path, "spell application requires an entity or position");
  }
  if (target.effect_presentation_ids.length !== 0 && target.target_uuid === null) {
    throw new ContractValidationError(path, "spell entity effects require an entity target");
  }
  if (new Set(target.effect_presentation_ids).size !== target.effect_presentation_ids.length) {
    throw new ContractValidationError(path, "spell application effect IDs must be unique");
  }
}

function assertAreaGeometrySemantics(
  area: NonNullable<Extract<SubjectivePresentationCue, { readonly kind: "spell" }>["area"]>,
  path: string,
): void {
  switch (area.shape) {
    case "sphere":
    case "cylinder":
      return;
    case "cone":
    case "line":
      if (samePosition(area.direction, [0, 0])) {
        throw new ContractValidationError(path, `${area.shape} direction must be nonzero`);
      }
      return;
    case "cube":
      if (area.centered && area.direction !== null) {
        throw new ContractValidationError(path, "centered cube cannot carry a direction");
      }
      if (!area.centered && area.direction === null) {
        throw new ContractValidationError(path, "directional cube requires a direction");
      }
      if (area.direction !== null && samePosition(area.direction, [0, 0])) {
        throw new ContractValidationError(path, "cube direction must be nonzero");
      }
      return;
    default:
      assertNever(area);
  }
}

function assertShoveSemantics(
  cue: Extract<SubjectivePresentationCue, { readonly kind: "shove" }>,
  path: string,
): void {
  if (cue.outcome === "succeeded_push") {
    if (
      cue.forced_movement_presentation_id === null
      || cue.prone_condition_presentation_id !== null
      || !sameOrderedValues(cue.child_presentation_ids, [cue.forced_movement_presentation_id])
    ) {
      throw new ContractValidationError(path, "successful push requires exactly its forced-movement child");
    }
    return;
  }
  if (cue.outcome === "succeeded_prone") {
    if (
      cue.prone_condition_presentation_id === null
      || cue.forced_movement_presentation_id !== null
      || !sameOrderedValues(cue.child_presentation_ids, [cue.prone_condition_presentation_id])
    ) {
      throw new ContractValidationError(path, "successful prone shove requires exactly its condition child");
    }
    return;
  }
  if (
    cue.forced_movement_presentation_id !== null
    || cue.prone_condition_presentation_id !== null
    || cue.child_presentation_ids.length !== 0
  ) {
    throw new ContractValidationError(path, "resisted or blocked shove cannot carry effects");
  }
}

function assertVisualLoadoutSemantics(
  loadout: Extract<SubjectivePresentationCue, { readonly kind: "equipment" }>["visual_loadout"],
  path: string,
): void {
  const slots = loadout.layers.map((layer) => layer.slot);
  if (new Set(slots).size !== slots.length) {
    throw new ContractValidationError(path, "visual loadout slots must be unique");
  }
}

function assertPresentationGraphSemantics(
  cue: SubjectivePresentationCue,
  byId: ReadonlyMap<string, SubjectivePresentationCue>,
  path: string,
): void {
  switch (cue.kind) {
    case "movement":
      for (const childId of cue.child_presentation_ids) {
        const child = requirePresentationCue(childId, byId, path);
        if (
          child.kind !== "attack"
          && child.kind !== "spell"
          && child.kind !== "shove"
        ) {
          throw new ContractValidationError(
            path,
            "movement child is not a pre-motion attack, spell, or shove reaction",
          );
        }
        if (child.source_event_cursor >= cue.source_event_cursor) {
          throw new ContractValidationError(
            path,
            "movement reaction must resolve before its owning segment",
          );
        }
      }
      return;
    case "shove":
      if (cue.outcome === "succeeded_push") {
        const forced = requirePresentationCue(cue.forced_movement_presentation_id, byId, path);
        if (
          forced.kind !== "forced_movement"
          || forced.cause !== "shove"
          || forced.source_uuid !== cue.actor_uuid
          || forced.entity_uuid !== cue.target_uuid
        ) {
          throw new ContractValidationError(path, "shove forced movement has the wrong actor or target");
        }
      } else if (cue.outcome === "succeeded_prone") {
        const condition = requirePresentationCue(cue.prone_condition_presentation_id, byId, path);
        if (
          condition.kind !== "condition"
          || condition.target_uuid !== cue.target_uuid
          || condition.condition_name !== "Prone"
          || condition.operation !== "applied"
        ) {
          throw new ContractValidationError(path, "prone shove must apply Prone to its target");
        }
      }
      return;
    case "forced_movement": {
      const parent = requirePresentationCue(cue.actor_action_presentation_id, byId, path);
      if (cue.cause === "shove" && parent.kind !== "shove") {
        throw new ContractValidationError(path, "shove movement must attach to a shove action");
      }
      if (cue.cause === "spell" && parent.kind !== "spell") {
        throw new ContractValidationError(path, "spell movement must attach to a spell action");
      }
      return;
    }
    case "attack":
      for (const childId of cue.child_presentation_ids) {
        const child = requirePresentationCue(childId, byId, path);
        if (child.kind !== "damage" && child.kind !== "heal" && child.kind !== "condition") {
          throw new ContractValidationError(path, "attack child is not an impact effect");
        }
        if (child.target_uuid !== cue.target_uuid) {
          throw new ContractValidationError(path, "attack impact target differs from attack target");
        }
        if ((child.kind === "damage" || child.kind === "heal") && child.source_uuid !== cue.actor_uuid) {
          throw new ContractValidationError(path, "attack impact source differs from attack actor");
        }
      }
      return;
    case "item_action":
      for (const childId of cue.child_presentation_ids) {
        const child = requirePresentationCue(childId, byId, path);
        if (child.kind !== "damage" && child.kind !== "heal" && child.kind !== "condition") {
          throw new ContractValidationError(path, "item child is not an impact effect");
        }
        if (child.target_uuid !== cue.actor_uuid) {
          throw new ContractValidationError(path, "item impact target differs from actor");
        }
        if ((child.kind === "damage" || child.kind === "heal") && child.source_uuid !== cue.actor_uuid) {
          throw new ContractValidationError(path, "item impact source differs from actor");
        }
      }
      return;
    case "spell":
      for (const target of cue.targets) {
        for (const effectId of target.effect_presentation_ids) {
          const effect = requirePresentationCue(effectId, byId, path);
          if (
            effect.kind !== "damage"
            && effect.kind !== "heal"
            && effect.kind !== "condition"
            && effect.kind !== "forced_movement"
          ) {
            throw new ContractValidationError(path, "spell child is not an impact effect");
          }
          const effectTarget = effect.kind === "forced_movement" ? effect.entity_uuid : effect.target_uuid;
          if (effectTarget !== target.target_uuid) {
            throw new ContractValidationError(path, "spell effect target differs from its application");
          }
          if (
            (effect.kind === "damage" || effect.kind === "heal" || effect.kind === "forced_movement")
            && effect.source_uuid !== cue.actor_uuid
          ) {
            throw new ContractValidationError(path, "spell effect source differs from caster");
          }
        }
      }
      return;
    case "lifecycle_cause": {
      const child = requirePresentationCue(cue.child_presentation_ids[0] ?? null, byId, path);
      if (child.kind !== "life_state" || child.entity_uuid !== cue.entity_uuid) {
        throw new ContractValidationError(path, "lifecycle cause must own a matching life-state transition");
      }
      if (cue.cause_kind === "death_save") {
        if (child.reason !== "stabilization" && child.reason !== "death_save_failures") {
          throw new ContractValidationError(path, "death-save cause has an incompatible life-state reason");
        }
        if (child.reason === "stabilization" && cue.death_save_outcome !== "success") {
          throw new ContractValidationError(path, "stabilization requires a successful death save");
        }
        if (
          child.reason === "death_save_failures"
          && cue.death_save_outcome !== "failure"
          && cue.death_save_outcome !== "critical_failure"
        ) {
          throw new ContractValidationError(path, "death requires a failed death save");
        }
      } else if (cue.cause_kind === "revive" && child.reason !== "revival") {
        throw new ContractValidationError(path, "revive cause requires revival reason");
      } else if (cue.cause_kind === "instant_death" && child.reason !== "instant_death") {
        throw new ContractValidationError(path, "instant-death cause requires instant-death reason");
      } else if (cue.cause_kind === "direct_state_check" && child.reason !== "direct_state_check") {
        throw new ContractValidationError(path, "direct cause requires direct-state-check reason");
      }
      return;
    }
    case "life_state": {
      const cause = requirePresentationCue(cue.causing_effect_presentation_id, byId, path);
      if (cause.kind !== "damage" && cause.kind !== "heal" && cause.kind !== "lifecycle_cause") {
        throw new ContractValidationError(path, "life-state cause must be damage, heal, or lifecycle");
      }
      const causeEntity = cause.kind === "lifecycle_cause" ? cause.entity_uuid : cause.target_uuid;
      if (causeEntity !== cue.entity_uuid) {
        throw new ContractValidationError(path, "life-state cause affects a different entity");
      }
      if (
        cause.kind === "damage"
        && cue.reason !== "damage"
        && cue.reason !== "massive_damage"
      ) {
        throw new ContractValidationError(path, "damage cause requires a damage reason");
      }
      if (cause.kind === "heal" && cue.reason !== "healing") {
        throw new ContractValidationError(path, "heal cause requires healing reason");
      }
      return;
    }
    case "movement":
    case "damage":
    case "heal":
    case "condition":
    case "door":
    case "light":
    case "equipment":
    case "encounter":
      return;
    default:
      assertNever(cue);
  }
}

function requirePresentationCue(
  presentationId: string | null,
  byId: ReadonlyMap<string, SubjectivePresentationCue>,
  path: string,
): SubjectivePresentationCue {
  const cue = presentationId === null ? undefined : byId.get(presentationId);
  if (cue === undefined) throw new ContractValidationError(path, "presentation reference is not delivered");
  return cue;
}

function sameOrderedValues(left: ReadonlyArray<string>, right: ReadonlyArray<string>): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function samePosition(left: readonly [number, number], right: readonly [number, number]): boolean {
  return left[0] === right[0] && left[1] === right[1];
}

function positionKey(position: readonly [number, number]): string {
  return `${position[0]},${position[1]}`;
}

function assertNever(value: never): never {
  throw new ContractValidationError("$subjective.presentation.kind", `unsupported cue ${String(value)}`);
}

export function assertSubjectiveCombatLogDelivery(delivery: SubjectiveCombatLogDelivery): void {
  assertWatermarks(delivery.watermarks, "$subjective.combat_log.watermarks");
  const frame = delivery.frame;
  requirePositiveCursor(frame.combat_log_cursor, "$subjective.combat_log.frame.combat_log_cursor");
  requireCursor(frame.event_cursor, "$subjective.combat_log.frame.event_cursor");
  if (
    frame.combat_log_cursor > delivery.watermarks.combat_log_cursor
    || frame.event_cursor > delivery.watermarks.source_event_cursor
  ) {
    throw new ContractValidationError("$subjective.combat_log", "frame exceeds delivery watermarks");
  }
}

export function assertWatermarks(watermarks: PlayerReplicationWatermarks, path: string): void {
  requireCursor(watermarks.source_event_cursor, `${path}.source_event_cursor`);
  requireCursor(watermarks.observation_cursor, `${path}.observation_cursor`);
  requireCursor(watermarks.presentation_cursor, `${path}.presentation_cursor`);
  requireCursor(watermarks.combat_log_cursor, `${path}.combat_log_cursor`);
}

export function assertDominates(
  later: PlayerReplicationWatermarks,
  earlier: PlayerReplicationWatermarks,
  path: string,
): void {
  assertWatermarks(later, path);
  if (
    later.source_event_cursor < earlier.source_event_cursor
    || later.observation_cursor < earlier.observation_cursor
    || later.presentation_cursor < earlier.presentation_cursor
    || later.combat_log_cursor < earlier.combat_log_cursor
  ) {
    throw new ContractValidationError(path, "watermarks moved backwards");
  }
}

export function deliveryWatermarks(delivery: SubjectiveStreamDelivery): PlayerReplicationWatermarks {
  return delivery.kind === "frame" ? delivery.frame.watermarks : delivery.watermarks;
}

function assertSseId(id: string, watermarks: PlayerReplicationWatermarks): void {
  const expected = `s=${watermarks.source_event_cursor};o=${watermarks.observation_cursor};p=${watermarks.presentation_cursor};l=${watermarks.combat_log_cursor}`;
  if (id !== expected) {
    throw new ContractValidationError("$subjective.sse.id", `expected ${expected}`);
  }
}

function positionWatermarks(position: SubjectiveStreamPosition): PlayerReplicationWatermarks {
  return {
    source_event_cursor: position.sourceEventCursor,
    observation_cursor: position.observationCursor,
    presentation_cursor: position.presentationCursor,
    combat_log_cursor: position.combatLogCursor,
  };
}

function assertStreamPosition(position: SubjectiveStreamPosition): void {
  requireNonEmpty(position.sourceStreamId, "$subjective.position.sourceStreamId");
  requireNonEmpty(position.generationId, "$subjective.position.generationId");
  requireNonEmpty(position.perspectiveEpochId, "$subjective.position.perspectiveEpochId");
  assertWatermarks(positionWatermarks(position), "$subjective.position");
}

function requireCursor(value: number, path: string): number {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new ContractValidationError(path, "expected a non-negative safe integer cursor");
  }
  return value;
}

function requirePositiveCursor(value: number, path: string): number {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new ContractValidationError(path, "expected a positive safe integer cursor");
  }
  return value;
}

function requireNonEmpty(value: string, path: string): string {
  if (value.trim().length === 0) throw new ContractValidationError(path, "expected non-empty string");
  return value;
}

function sameSet(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
  if (left.size !== right.size) return false;
  for (const value of left) if (!right.has(value)) return false;
  return true;
}
