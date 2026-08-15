import { PLAYER_REPLICATION_CONTRACT_HASH, PLAYER_REPLICATION_CONTRACT_VERSION, } from "./generated/contracts.generated.js";
import { SseDecoder } from "./sse.js";
import { assertSubjectiveWorldPatch } from "./reducer.js";
import { ContractValidationError, decodeAlias } from "./validation.js";
export class SubjectiveSseDecoder {
    syntax = new SseDecoder();
    feed(chunk) {
        return this.syntax.feed(chunk).map(decodeSubjectiveEnvelope);
    }
    finish() {
        return this.syntax.finish().map(decodeSubjectiveEnvelope);
    }
}
/** Stateful ordering check used by reconnecting stream consumers. */
export class SubjectiveStreamFollower {
    positionValue;
    synchronized = false;
    constructor(position) {
        assertStreamPosition(position);
        this.positionValue = { ...position };
    }
    position() {
        return { ...this.positionValue };
    }
    ingest(envelope) {
        const watermarks = deliveryWatermarks(envelope.data);
        assertSseId(envelope.id, watermarks);
        if (envelope.event === "sync") {
            if (this.synchronized) {
                throw new ContractValidationError("$subjective.sse.sync", "stream emitted more than one sync");
            }
            assertProtocol(envelope.data.protocol);
            assertPerspective(envelope.data.perspective);
            this.assertIdentity(envelope.data.protocol.source_stream_id, envelope.data.protocol.generation_id, envelope.data.perspective.perspective_epoch_id, "$subjective.sse.sync");
            assertDominates(watermarks, positionWatermarks(this.positionValue), "$subjective.sse.sync.watermarks");
            this.synchronized = true;
            return this.position();
        }
        if (!this.synchronized) {
            throw new ContractValidationError("$subjective.sse", "sync must be the first delivery");
        }
        if (envelope.event === "frame") {
            const frame = envelope.data.frame;
            this.assertIdentity(frame.source_stream_id, frame.generation_id, frame.perspective_epoch_id, "$subjective.sse.frame");
            assertSubjectiveFrame(frame);
            if (frame.watermarks.observation_cursor !== this.positionValue.observationCursor + 1) {
                throw new ContractValidationError("$subjective.sse.frame.watermarks.observation_cursor", `expected contiguous cursor ${this.positionValue.observationCursor + 1}`);
            }
            if (frame.presentation_from_cursor !== this.positionValue.presentationCursor) {
                throw new ContractValidationError("$subjective.sse.frame.presentation_from_cursor", "presentation window is not contiguous");
            }
            if (frame.watermarks.source_event_cursor < this.positionValue.sourceEventCursor) {
                throw new ContractValidationError("$subjective.sse.frame.watermarks", "source cursor moved backwards");
            }
            if (frame.watermarks.combat_log_cursor !== this.positionValue.combatLogCursor) {
                throw new ContractValidationError("$subjective.sse.frame.watermarks.combat_log_cursor", "frame delivery cannot advance the combat-log cursor");
            }
            this.positionValue = {
                ...this.positionValue,
                sourceEventCursor: frame.watermarks.source_event_cursor,
                observationCursor: frame.watermarks.observation_cursor,
                presentationCursor: frame.watermarks.presentation_cursor,
            };
        }
        else {
            assertSubjectiveCombatLogDelivery(envelope.data);
            const frame = envelope.data.frame;
            this.assertIdentity(frame.source_stream_id, frame.generation_id, frame.perspective_epoch_id, "$subjective.sse.combat_log");
            if (frame.combat_log_cursor !== this.positionValue.combatLogCursor + 1) {
                throw new ContractValidationError("$subjective.sse.combat_log.frame.combat_log_cursor", `expected contiguous cursor ${this.positionValue.combatLogCursor + 1}`);
            }
            if (envelope.data.watermarks.source_event_cursor !== this.positionValue.sourceEventCursor
                || envelope.data.watermarks.observation_cursor !== this.positionValue.observationCursor
                || envelope.data.watermarks.presentation_cursor !== this.positionValue.presentationCursor
                || envelope.data.watermarks.combat_log_cursor !== frame.combat_log_cursor) {
                throw new ContractValidationError("$subjective.sse.combat_log.watermarks", "combat-log delivery may advance only its own cursor");
            }
            this.positionValue = {
                ...this.positionValue,
                combatLogCursor: frame.combat_log_cursor,
            };
        }
        return this.position();
    }
    assertIdentity(source, generation, perspective, path) {
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
export function decodeSubjectiveEnvelope(message) {
    if (message.event !== "sync" && message.event !== "frame" && message.event !== "combat_log") {
        throw new ContractValidationError("$subjective.sse.event", `unsupported subjective event ${message.event}`);
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
    }
    else if (data.kind === "frame") {
        assertSubjectiveFrame(data.frame);
    }
    else {
        assertSubjectiveCombatLogDelivery(data);
    }
    assertSseId(message.id, deliveryWatermarks(data));
    return { event: data.kind, id: message.id, data };
}
export function assertProtocol(protocol) {
    if (protocol.player_replication_contract_version !== PLAYER_REPLICATION_CONTRACT_VERSION) {
        throw new ContractValidationError("$subjective.protocol.player_replication_contract_version", "unsupported player replication contract version");
    }
    if (protocol.player_replication_contract_hash !== PLAYER_REPLICATION_CONTRACT_HASH) {
        throw new ContractValidationError("$subjective.protocol.player_replication_contract_hash", "player replication contract hash mismatch");
    }
    requireNonEmpty(protocol.source_stream_id, "$subjective.protocol.source_stream_id");
    requireNonEmpty(protocol.generation_id, "$subjective.protocol.generation_id");
}
export function assertPerspective(perspective) {
    requireNonEmpty(perspective.perspective_epoch_id, "$subjective.perspective.perspective_epoch_id");
    const controlled = new Set(perspective.controlled_entity_uuids);
    const observers = new Set(perspective.observer_entity_uuids);
    if (controlled.size !== perspective.controlled_entity_uuids.length
        || observers.size !== perspective.observer_entity_uuids.length
        || observers.size === 0
        || !observers.has(perspective.active_observer_uuid)) {
        throw new ContractValidationError("$subjective.perspective", "invalid observer union");
    }
    if (perspective.kind === "controlled_knowledge_union") {
        if (controlled.size === 0 || !sameSet(controlled, observers)) {
            throw new ContractValidationError("$subjective.perspective", "invalid controlled observer union");
        }
    }
    else if (controlled.size !== 0) {
        throw new ContractValidationError("$subjective.perspective", "spectator cannot control entities");
    }
}
export function assertSubjectiveFrame(frame) {
    assertWatermarks(frame.watermarks, "$subjective.frame.watermarks");
    requirePositiveCursor(frame.watermarks.observation_cursor, "$subjective.frame.watermarks.observation_cursor");
    requireCursor(frame.presentation_from_cursor, "$subjective.frame.presentation_from_cursor");
    if (frame.presentation_delivery === "normal") {
        if (frame.presentation_reset_reason !== null || frame.encounter_terminal !== null) {
            throw new ContractValidationError("$subjective.frame.presentation_delivery", "normal presentation cannot carry reset authority");
        }
        if (frame.presentation.length
            !== frame.watermarks.presentation_cursor - frame.presentation_from_cursor) {
            throw new ContractValidationError("$subjective.frame.presentation", "presentation window is not exact");
        }
    }
    else {
        if (frame.presentation_reset_reason !== "source_presentation_discontinuity"
            || frame.presentation.length !== 0
            || frame.watermarks.presentation_cursor !== frame.presentation_from_cursor) {
            throw new ContractValidationError("$subjective.frame.presentation_delivery", "reset presentation requires its closed reason, no cues, and no cue-cursor advance");
        }
        assertResetTerminalSemantics(frame);
    }
    frame.patches.forEach((patch, index) => {
        assertSubjectiveWorldPatch(patch, `$subjective.frame.patches[${index}]`);
    });
    const byId = new Map();
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
            if (child === undefined
                || child.parent_presentation_id !== cue.presentation_id
                || child.presentation_cursor <= cue.presentation_cursor
                || child.presentation_cursor <= previousChildCursor) {
                throw new ContractValidationError(path, "invalid closed graph edge");
            }
            previousChildCursor = child.presentation_cursor;
        }
        assertPresentationGraphSemantics(cue, byId, path);
        if (cue.kind === "movement"
            && cue.endpoint_outcome === "not_committed"
            && frame.patches.some((patch) => (patch.kind === "entity_upsert"
                && patch.entity.uuid === cue.entity_uuid
                && samePosition(patch.entity.position, cue.anchors[cue.anchors.length - 1].position)))) {
            throw new ContractValidationError(path, "not-committed movement cannot project destination occupancy");
        }
    });
    if (frame.presentation_delivery === "normal") {
        assertNormalTerminalSemantics(frame);
    }
}
function assertPresentationCueSemantics(cue, path) {
    assertActionBindingSemantics(cue, path);
    switch (cue.kind) {
        case "movement": {
            if (cue.anchors.length < 2) {
                throw new ContractValidationError(path, "movement requires at least two authorized anchors");
            }
            for (const anchor of cue.anchors) {
                if (!Number.isSafeInteger(anchor.elevation_feet) || anchor.elevation_feet % 5 !== 0) {
                    throw new ContractValidationError(path, "movement elevation must use exact five-foot steps");
                }
            }
            if (cue.locomotion_family === "walk"
                || cue.locomotion_family === "swim"
                || cue.locomotion_family === "fly"
                || cue.locomotion_family === "burrow") {
                if (cue.trajectory_family !== "path" || cue.connector !== null) {
                    throw new ContractValidationError(path, "path locomotion requires PATH with no connector");
                }
            }
            else if (cue.locomotion_family === "jump") {
                if (cue.trajectory_family !== "direct_arc" || cue.anchors.length !== 2 || cue.connector !== null) {
                    throw new ContractValidationError(path, "jump requires one direct-arc leg with no connector");
                }
            }
            else if (cue.trajectory_family !== "connector_transfer"
                || cue.anchors.length !== 2
                || cue.connector === null) {
                throw new ContractValidationError(path, "connector locomotion requires one typed transfer leg");
            }
            if (cue.endpoint_outcome === "not_committed"
                && (cue.anchors.length !== 2 || cue.child_presentation_ids.length === 0)) {
                throw new ContractValidationError(path, "not-committed movement requires one intended edge and a pre-edge reaction");
            }
            return;
        }
        case "action": {
            if (new Set(cue.target_uuids).size !== cue.target_uuids.length) {
                throw new ContractValidationError(path, "action targets must be unique");
            }
            if (!sameOrderedValues(cue.effect_presentation_ids, cue.child_presentation_ids)) {
                throw new ContractValidationError(path, "action effects must exactly equal ordered children");
            }
            if (cue.trigger_presentation_id === cue.presentation_id) {
                throw new ContractValidationError(path, "action cannot cite itself as its trigger");
            }
            if (cue.trigger_presentation_id !== null
                && cue.child_presentation_ids.includes(cue.trigger_presentation_id)) {
                throw new ContractValidationError(path, "action trigger cannot also be one of its effects");
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
            const indexes = cue.targets.map((target) => target.disclosed_index);
            if (!indexes.every((value, index) => value === index)) {
                throw new ContractValidationError(path, "spell applications must be contiguous and ordered");
            }
            const applicationIds = cue.targets.flatMap((target) => (target.application_id === null ? [] : [target.application_id]));
            if (new Set(applicationIds).size !== applicationIds.length) {
                throw new ContractValidationError(path, "spell application IDs must be unique");
            }
            for (const [index, target] of cue.targets.entries()) {
                assertSpellTargetSemantics(target, `${path}.targets[${index}]`);
            }
            if ((cue.delivery === "projectile" || cue.delivery === "missile_volley")
                && cue.projectile_type === null) {
                throw new ContractValidationError(path, "projectile spell route requires a projectile type");
            }
            if (cue.delivery === "aoe" && cue.area === null) {
                throw new ContractValidationError(path, "AOE spell route requires typed area geometry");
            }
            if (cue.delivery !== "aoe" && cue.area !== null) {
                throw new ContractValidationError(path, "non-AOE spell route cannot carry area geometry");
            }
            if (cue.area !== null)
                assertAreaGeometrySemantics(cue.area, `${path}.area`);
            const effects = cue.targets.flatMap((target) => target.effect_presentation_ids);
            if (new Set(effects).size !== effects.length) {
                throw new ContractValidationError(path, "one spell effect cannot belong to multiple applications");
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
        case "counterspell": {
            if (cue.child_presentation_ids.length !== 0) {
                throw new ContractValidationError(path, "Counterspell presentation must be a leaf");
            }
            if (cue.trigger_binding_subject === null) {
                throw new ContractValidationError(path, "Counterspell requires exact incoming-spell trigger binding evidence");
            }
            if (cue.source_item_fact !== null) {
                throw new ContractValidationError(path, "Counterspell cannot carry source-item attribution");
            }
            if (cue.resolution.kind === "automatic_success") {
                if (cue.counterspell_slot_level < cue.incoming_spell_level) {
                    throw new ContractValidationError(path, "automatic Counterspell requires a sufficient slot level");
                }
            }
            else {
                if (cue.counterspell_slot_level >= cue.incoming_spell_level) {
                    throw new ContractValidationError(path, "checked Counterspell requires a lower slot than the incoming spell");
                }
                if (cue.resolution.check_dc !== 10 + cue.incoming_spell_level) {
                    throw new ContractValidationError(path, "Counterspell check DC is inconsistent");
                }
                if (cue.resolution.kind === "check_success"
                    && cue.resolution.check_total < cue.resolution.check_dc) {
                    throw new ContractValidationError(path, "successful Counterspell check is below its DC");
                }
                if (cue.resolution.kind === "check_failure"
                    && cue.resolution.check_total >= cue.resolution.check_dc) {
                    throw new ContractValidationError(path, "failed Counterspell check meets its DC");
                }
            }
            return;
        }
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
            }
            else if (cue.death_save_outcome !== null) {
                throw new ContractValidationError(path, "death-save outcome belongs only to a death-save cause");
            }
            if (cue.child_presentation_ids.length > 1
                || (cue.cause_kind === "death_save"
                    && cue.child_presentation_ids.length !== 1)) {
                throw new ContractValidationError(path, "lifecycle cause may own at most one life-state child and a death save requires one");
            }
            return;
        case "life_state":
            if (cue.previous === cue.current
                && (cue.previous !== "alive" || cue.current !== "alive")) {
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
            if ((cue.previous === "dying" || cue.previous === "stable")
                && cue.current === "alive"
                && cue.reason !== "healing"
                && cue.reason !== "direct_state_check") {
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
        case "spatial_effect": {
            if (cue.content_ref.definition_kind !== "spatial_effect") {
                throw new ContractValidationError(path, "spatial effect requires exact spatial-effect content");
            }
            if (cue.child_presentation_ids.length !== 0) {
                throw new ContractValidationError(path, "spatial-effect lifecycle cue must be a leaf");
            }
            assertSortedUniquePositions(cue.affected_positions, `${path}.affected_positions`);
            assertSortedUniquePositions(cue.previous_positions, `${path}.previous_positions`);
            const disclosed = [...cue.affected_positions, ...cue.previous_positions];
            if (disclosed.length === 0) {
                throw new ContractValidationError(path, "spatial effect requires disclosed geometry");
            }
            if (cue.anchor_position !== null
                && !disclosed.some((position) => samePosition(position, cue.anchor_position))) {
                throw new ContractValidationError(path, "spatial-effect anchor must belong to disclosed geometry");
            }
            if ((cue.operation === "created" || cue.operation === "revealed")
                && cue.affected_positions.length === 0) {
                throw new ContractValidationError(path, "created or revealed effect requires current geometry");
            }
            if (cue.operation === "removed" && cue.previous_positions.length === 0) {
                throw new ContractValidationError(path, "removed effect requires former geometry");
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
            }
            else if (cue.terminal_barrier || cue.projected_combatant_uuids.length !== 0) {
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
function assertActionBindingSemantics(cue, path) {
    const actionable = (cue.kind === "movement"
        || cue.kind === "action"
        || cue.kind === "attack"
        || cue.kind === "spell"
        || cue.kind === "item_action"
        || cue.kind === "shove"
        || cue.kind === "counterspell");
    if (!actionable) {
        if (cue.binding_subject !== null) {
            throw new ContractValidationError(`${path}.binding_subject`, "result and state cues cannot carry a primary action binding subject");
        }
        return;
    }
    const subject = cue.binding_subject;
    if (subject === null || subject.use !== "behavior") {
        throw new ContractValidationError(`${path}.binding_subject`, "actionable root requires exact primary behavior binding evidence");
    }
    if (subject.kind === "public_configured_action" && cue.kind !== "action") {
        throw new ContractValidationError(`${path}.binding_subject`, "configured-action binding is valid only for an action cue");
    }
    if (subject.kind === "systemic"
        && !((subject.domain === "item_action" && cue.kind === "spell")
            || (subject.domain === "reaction" && cue.kind === "action"))) {
        throw new ContractValidationError(`${path}.binding_subject`, "unsupported systemic primary binding for cue kind");
    }
    const trigger = cue.trigger_binding_subject;
    if (trigger !== null && trigger.use !== "trigger_behavior") {
        throw new ContractValidationError(`${path}.trigger_binding_subject`, "trigger binding evidence must use trigger_behavior");
    }
}
function assertResetTerminalSemantics(frame) {
    const ended = frame.patches.flatMap((patch) => (patch.kind === "encounter_replace"
        && patch.encounter !== null
        && patch.encounter.state === "ended"
        ? [patch.encounter]
        : []));
    const fact = frame.encounter_terminal;
    if (fact === null) {
        if (ended.length !== 0) {
            throw new ContractValidationError("$subjective.frame.encounter_terminal", "ended encounter patch requires terminal reset authority");
        }
        return;
    }
    assertTerminalResultingEncounter(frame, fact.encounter_uuid, "$subjective.frame.encounter_terminal");
    const expectedAuthority = (`${frame.perspective_epoch_id}:${frame.watermarks.observation_cursor}`
        + `:reset-terminal:${fact.source_event_uuid}`);
    if (fact.terminal_barrier !== true
        || !UUID_PATTERN.test(fact.source_event_uuid)
        || !Number.isSafeInteger(fact.source_event_cursor)
        || fact.source_event_cursor < 1
        || fact.source_event_cursor !== frame.watermarks.source_event_cursor
        || fact.terminal_authority_id !== expectedAuthority
        || fact.encounter_uuid.length === 0
        || fact.projected_combatant_uuids.some((uuid) => uuid.length === 0)
        || new Set(fact.projected_combatant_uuids).size !== fact.projected_combatant_uuids.length) {
        throw new ContractValidationError("$subjective.frame.encounter_terminal", "terminal reset authority does not exactly match the final source slot and ended encounter");
    }
}
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function assertNormalTerminalSemantics(frame) {
    const terminalCues = frame.presentation.flatMap((cue) => (cue.kind === "encounter" && cue.transition === "end" ? [cue] : []));
    const ended = frame.patches.flatMap((patch) => (patch.kind === "encounter_replace"
        && patch.encounter !== null
        && patch.encounter.state === "ended"
        ? [patch.encounter]
        : []));
    if (terminalCues.length === 0 && ended.length === 0)
        return;
    const cue = terminalCues.length === 1 ? terminalCues[0] : null;
    if (cue === null
        || cue.source_event_cursor !== frame.watermarks.source_event_cursor) {
        throw new ContractValidationError("$subjective.frame.presentation", "normal encounter end requires one matching final-source cue and ended encounter patch");
    }
    assertTerminalResultingEncounter(frame, cue.encounter_uuid, "$subjective.frame.presentation");
}
function assertTerminalResultingEncounter(frame, encounterUuid, path) {
    const replacements = frame.patches.flatMap((patch) => (patch.kind === "encounter_replace" ? [patch.encounter] : []));
    const ended = replacements.filter((encounter) => encounter?.state === "ended");
    const finalEncounter = replacements.at(-1);
    if (ended.length !== 1
        || replacements.some((encounter) => (encounter !== null && encounter.uuid !== encounterUuid))
        || finalEncounter === undefined
        || finalEncounter === null
        || finalEncounter.uuid !== encounterUuid
        || finalEncounter.state !== "ended") {
        throw new ContractValidationError(path, "terminal authority must leave one matching ended encounter as the final replacement");
    }
}
function assertSpellTargetSemantics(target, path) {
    if (target.target_uuid === null && target.position === null) {
        throw new ContractValidationError(path, "spell application requires an entity or position");
    }
    if (new Set(target.effect_presentation_ids).size !== target.effect_presentation_ids.length) {
        throw new ContractValidationError(path, "spell application effect IDs must be unique");
    }
}
function assertAreaGeometrySemantics(area, path) {
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
function assertShoveSemantics(cue, path) {
    if (cue.outcome === "succeeded_push") {
        if (cue.forced_movement_presentation_id === null
            || cue.prone_condition_presentation_id !== null
            || !sameOrderedValues(cue.child_presentation_ids, [cue.forced_movement_presentation_id])) {
            throw new ContractValidationError(path, "successful push requires exactly its forced-movement child");
        }
        return;
    }
    if (cue.outcome === "succeeded_prone") {
        if (cue.prone_condition_presentation_id === null
            || cue.forced_movement_presentation_id !== null
            || !sameOrderedValues(cue.child_presentation_ids, [cue.prone_condition_presentation_id])) {
            throw new ContractValidationError(path, "successful prone shove requires exactly its condition child");
        }
        return;
    }
    if (cue.forced_movement_presentation_id !== null
        || cue.prone_condition_presentation_id !== null
        || cue.child_presentation_ids.length !== 0) {
        throw new ContractValidationError(path, "resisted or blocked shove cannot carry effects");
    }
}
function assertVisualLoadoutSemantics(loadout, path) {
    const slots = loadout.layers.map((layer) => layer.slot);
    if (new Set(slots).size !== slots.length) {
        throw new ContractValidationError(path, "visual loadout slots must be unique");
    }
}
function assertPresentationGraphSemantics(cue, byId, path) {
    switch (cue.kind) {
        case "movement":
            for (const childId of cue.child_presentation_ids) {
                const child = requirePresentationCue(childId, byId, path);
                if (child.kind !== "attack"
                    && child.kind !== "spell"
                    && child.kind !== "shove") {
                    throw new ContractValidationError(path, "movement child is not a pre-motion attack, spell, or shove reaction");
                }
                if (child.source_event_cursor >= cue.source_event_cursor) {
                    throw new ContractValidationError(path, "movement reaction must resolve before its owning segment");
                }
            }
            return;
        case "action": {
            const allowedTargets = new Set([
                cue.actor_uuid,
                ...cue.target_uuids,
            ]);
            if (cue.trigger_presentation_id !== null) {
                const trigger = requirePresentationCue(cue.trigger_presentation_id, byId, path);
                if (trigger.kind !== "movement"
                    && trigger.kind !== "action"
                    && trigger.kind !== "attack"
                    && trigger.kind !== "spell"
                    && trigger.kind !== "shove") {
                    throw new ContractValidationError(path, "action trigger is not a delivered action-like cue");
                }
                const triggerTargets = new Set();
                if (trigger.kind === "movement") {
                    triggerTargets.add(trigger.entity_uuid);
                }
                else if (trigger.kind === "action") {
                    for (const targetUuid of trigger.target_uuids)
                        triggerTargets.add(targetUuid);
                }
                else if (trigger.kind === "attack" || trigger.kind === "shove") {
                    triggerTargets.add(trigger.target_uuid);
                }
                else {
                    for (const target of trigger.targets) {
                        if (target.target_uuid !== null)
                            triggerTargets.add(target.target_uuid);
                    }
                }
                if (triggerTargets.size !== 0
                    && ![...triggerTargets].some((targetUuid) => allowedTargets.has(targetUuid))) {
                    throw new ContractValidationError(path, "action trigger shares no authorized action participant");
                }
            }
            for (const childId of cue.child_presentation_ids) {
                const child = requirePresentationCue(childId, byId, path);
                if (child.kind !== "attack"
                    && child.kind !== "spell"
                    && child.kind !== "shove"
                    && child.kind !== "forced_movement"
                    && child.kind !== "damage"
                    && child.kind !== "heal"
                    && child.kind !== "condition"
                    && child.kind !== "door"
                    && child.kind !== "light"
                    && child.kind !== "equipment") {
                    throw new ContractValidationError(path, "action child is not a typed delivered action effect");
                }
                if ((child.kind === "attack"
                    || child.kind === "spell"
                    || child.kind === "shove")
                    && child.actor_uuid !== cue.actor_uuid) {
                    throw new ContractValidationError(path, "nested action actor differs from owning action");
                }
                if (child.kind === "attack"
                    && !allowedTargets.has(child.target_uuid)) {
                    throw new ContractValidationError(path, "nested attack target differs from owning action");
                }
                if (child.kind === "shove"
                    && !allowedTargets.has(child.target_uuid)) {
                    throw new ContractValidationError(path, "nested shove target differs from owning action");
                }
                if (child.kind === "spell"
                    && child.targets.some((target) => (target.target_uuid !== null
                        && !allowedTargets.has(target.target_uuid)))) {
                    throw new ContractValidationError(path, "nested spell target differs from owning action");
                }
                if ((child.kind === "damage" || child.kind === "heal")
                    && (child.source_uuid !== cue.actor_uuid
                        || !allowedTargets.has(child.target_uuid))) {
                    throw new ContractValidationError(path, "action impact source or target differs from its action");
                }
                if (child.kind === "condition"
                    && !allowedTargets.has(child.target_uuid)) {
                    throw new ContractValidationError(path, "action condition target differs from its action");
                }
                if (child.kind === "forced_movement"
                    && (child.source_uuid !== cue.actor_uuid
                        || !allowedTargets.has(child.entity_uuid))) {
                    throw new ContractValidationError(path, "action forced movement differs from its action");
                }
            }
            return;
        }
        case "shove":
            if (cue.outcome === "succeeded_push") {
                const forced = requirePresentationCue(cue.forced_movement_presentation_id, byId, path);
                if (forced.kind !== "forced_movement"
                    || forced.cause !== "shove"
                    || forced.source_uuid !== cue.actor_uuid
                    || forced.entity_uuid !== cue.target_uuid) {
                    throw new ContractValidationError(path, "shove forced movement has the wrong actor or target");
                }
            }
            else if (cue.outcome === "succeeded_prone") {
                const condition = requirePresentationCue(cue.prone_condition_presentation_id, byId, path);
                if (condition.kind !== "condition"
                    || condition.target_uuid !== cue.target_uuid
                    || condition.condition_name !== "Prone"
                    || condition.operation !== "applied") {
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
                    if (effect.owner_application_id !== target.application_id) {
                        throw new ContractValidationError(path, "spell target and referenced cue must have identical nullable application membership");
                    }
                    if (effect.kind !== "damage"
                        && effect.kind !== "heal"
                        && effect.kind !== "condition"
                        && effect.kind !== "forced_movement"
                        && effect.kind !== "spatial_effect") {
                        throw new ContractValidationError(path, "spell child is not an impact effect");
                    }
                    if (effect.kind === "spatial_effect") {
                        if (target.target_uuid !== null) {
                            throw new ContractValidationError(path, "spell spatial effect cannot have an entity target");
                        }
                        const targetPosition = target.position;
                        if (targetPosition === null) {
                            throw new ContractValidationError(path, "spell spatial effect requires a position target");
                        }
                        if (!effect.affected_positions.some((position) => samePosition(position, targetPosition))
                            && !effect.previous_positions.some((position) => samePosition(position, targetPosition))) {
                            throw new ContractValidationError(path, "spell spatial effect does not contain its application position");
                        }
                        continue;
                    }
                    if (target.target_uuid === null) {
                        throw new ContractValidationError(path, "spell entity effects require an entity target");
                    }
                    const effectTarget = effect.kind === "forced_movement" ? effect.entity_uuid : effect.target_uuid;
                    if (effectTarget !== target.target_uuid) {
                        throw new ContractValidationError(path, "spell effect target differs from its application");
                    }
                    if ((effect.kind === "damage" || effect.kind === "heal" || effect.kind === "forced_movement")
                        && effect.source_uuid !== cue.actor_uuid) {
                        throw new ContractValidationError(path, "spell effect source differs from caster");
                    }
                }
            }
            return;
        case "lifecycle_cause": {
            if (cue.child_presentation_ids.length === 0)
                return;
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
                if (child.reason === "death_save_failures"
                    && cue.death_save_outcome !== "failure"
                    && cue.death_save_outcome !== "critical_failure") {
                    throw new ContractValidationError(path, "death requires a failed death save");
                }
            }
            else if (cue.cause_kind === "revive" && child.reason !== "revival") {
                throw new ContractValidationError(path, "revive cause requires revival reason");
            }
            else if (cue.cause_kind === "instant_death" && child.reason !== "instant_death") {
                throw new ContractValidationError(path, "instant-death cause requires instant-death reason");
            }
            else if (cue.cause_kind === "direct_state_check" && child.reason !== "direct_state_check") {
                throw new ContractValidationError(path, "direct cause requires direct-state-check reason");
            }
            return;
        }
        case "life_state": {
            if (cue.causing_effect_presentation_id === null)
                return;
            const cause = requirePresentationCue(cue.causing_effect_presentation_id, byId, path);
            if (cause.kind !== "damage" && cause.kind !== "heal" && cause.kind !== "lifecycle_cause") {
                throw new ContractValidationError(path, "life-state cause must be damage, heal, or lifecycle");
            }
            const causeEntity = cause.kind === "lifecycle_cause" ? cause.entity_uuid : cause.target_uuid;
            if (causeEntity !== cue.entity_uuid) {
                throw new ContractValidationError(path, "life-state cause affects a different entity");
            }
            if (cause.kind === "damage"
                && cue.reason !== "damage"
                && cue.reason !== "massive_damage") {
                throw new ContractValidationError(path, "damage cause requires a damage reason");
            }
            if (cause.kind === "heal" && cue.reason !== "healing") {
                throw new ContractValidationError(path, "heal cause requires healing reason");
            }
            return;
        }
        case "counterspell":
        case "damage":
        case "heal":
        case "condition":
        case "door":
        case "light":
        case "spatial_effect":
        case "equipment":
        case "encounter":
            return;
        default:
            assertNever(cue);
    }
}
function requirePresentationCue(presentationId, byId, path) {
    const cue = presentationId === null ? undefined : byId.get(presentationId);
    if (cue === undefined)
        throw new ContractValidationError(path, "presentation reference is not delivered");
    return cue;
}
function sameOrderedValues(left, right) {
    return left.length === right.length && left.every((value, index) => value === right[index]);
}
function samePosition(left, right) {
    return left[0] === right[0] && left[1] === right[1];
}
function assertSortedUniquePositions(positions, path) {
    for (let index = 1; index < positions.length; index += 1) {
        const previous = positions[index - 1];
        const current = positions[index];
        if (previous[0] > current[0]
            || (previous[0] === current[0] && previous[1] >= current[1])) {
            throw new ContractValidationError(path, "positions must be unique and sorted");
        }
    }
}
function positionKey(position) {
    return `${position[0]},${position[1]}`;
}
function assertNever(value) {
    throw new ContractValidationError("$subjective.presentation.kind", `unsupported cue ${String(value)}`);
}
export function assertSubjectiveCombatLogDelivery(delivery) {
    assertWatermarks(delivery.watermarks, "$subjective.combat_log.watermarks");
    const frame = delivery.frame;
    requirePositiveCursor(frame.combat_log_cursor, "$subjective.combat_log.frame.combat_log_cursor");
    requireCursor(frame.event_cursor, "$subjective.combat_log.frame.event_cursor");
    if (frame.combat_log_cursor > delivery.watermarks.combat_log_cursor
        || frame.event_cursor > delivery.watermarks.source_event_cursor) {
        throw new ContractValidationError("$subjective.combat_log", "frame exceeds delivery watermarks");
    }
}
export function assertWatermarks(watermarks, path) {
    requireCursor(watermarks.source_event_cursor, `${path}.source_event_cursor`);
    requireCursor(watermarks.observation_cursor, `${path}.observation_cursor`);
    requireCursor(watermarks.presentation_cursor, `${path}.presentation_cursor`);
    requireCursor(watermarks.combat_log_cursor, `${path}.combat_log_cursor`);
}
export function assertDominates(later, earlier, path) {
    assertWatermarks(later, path);
    if (later.source_event_cursor < earlier.source_event_cursor
        || later.observation_cursor < earlier.observation_cursor
        || later.presentation_cursor < earlier.presentation_cursor
        || later.combat_log_cursor < earlier.combat_log_cursor) {
        throw new ContractValidationError(path, "watermarks moved backwards");
    }
}
export function deliveryWatermarks(delivery) {
    return delivery.kind === "frame" ? delivery.frame.watermarks : delivery.watermarks;
}
function assertSseId(id, watermarks) {
    const expected = `s=${watermarks.source_event_cursor};o=${watermarks.observation_cursor};p=${watermarks.presentation_cursor};l=${watermarks.combat_log_cursor}`;
    if (id !== expected) {
        throw new ContractValidationError("$subjective.sse.id", `expected ${expected}`);
    }
}
function positionWatermarks(position) {
    return {
        source_event_cursor: position.sourceEventCursor,
        observation_cursor: position.observationCursor,
        presentation_cursor: position.presentationCursor,
        combat_log_cursor: position.combatLogCursor,
    };
}
function assertStreamPosition(position) {
    requireNonEmpty(position.sourceStreamId, "$subjective.position.sourceStreamId");
    requireNonEmpty(position.generationId, "$subjective.position.generationId");
    requireNonEmpty(position.perspectiveEpochId, "$subjective.position.perspectiveEpochId");
    assertWatermarks(positionWatermarks(position), "$subjective.position");
}
function requireCursor(value, path) {
    if (!Number.isSafeInteger(value) || value < 0) {
        throw new ContractValidationError(path, "expected a non-negative safe integer cursor");
    }
    return value;
}
function requirePositiveCursor(value, path) {
    if (!Number.isSafeInteger(value) || value < 1) {
        throw new ContractValidationError(path, "expected a positive safe integer cursor");
    }
    return value;
}
function requireNonEmpty(value, path) {
    if (value.trim().length === 0)
        throw new ContractValidationError(path, "expected non-empty string");
    return value;
}
function sameSet(left, right) {
    if (left.size !== right.size)
        return false;
    for (const value of left)
        if (!right.has(value))
            return false;
    return true;
}
//# sourceMappingURL=subjectiveSse.js.map