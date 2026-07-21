import {
  EVENT_CONTRACT_HASH,
  EVENT_CONTRACT_VERSION,
  type CombatLogEntry,
  type GameEventPayload,
  type ReplicationBootstrapResponse,
  type SessionPingResponse,
} from "./generated/contracts.generated.js";
import { reduceWorld, type ReplicatedWorld } from "./reducer.js";
import type { ReplicationSseEnvelope } from "./sse.js";

export type ReplicationHealth = "uninitialized" | "ready" | "resync_required";
export type ResyncReason =
  | "generation_changed"
  | "event_cursor_gap"
  | "combat_log_cursor_gap"
  | "subscriber_evicted"
  | "presentation_queue_overflow"
  | "contract_mismatch";

export interface ReplicaView {
  readonly generationId: string;
  readonly eventCursor: number;
  readonly combatLogCursor: number;
  readonly world: ReplicatedWorld;
  readonly session: SessionPingResponse | null;
  readonly combatLog: ReadonlyArray<CombatLogEntry>;
}

export interface ReplicationJournalState {
  readonly health: ReplicationHealth;
  readonly resyncReason: ResyncReason | null;
  readonly authoritative: ReplicaView | null;
  readonly presentation: ReplicaView | null;
  readonly presentationBacklog: number;
}

export type IngestStatus = "applied" | "duplicate" | "metadata" | "resync_required";

export interface IngestResult {
  readonly status: IngestStatus;
  readonly health: ReplicationHealth;
  readonly resyncReason: ResyncReason | null;
  readonly eventCursor: number | null;
  readonly combatLogCursor: number | null;
  readonly presentationBacklog: number;
}

interface PendingSession {
  readonly eventCursor: number;
  readonly session: SessionPingResponse;
}

interface PendingCombatLog {
  readonly eventCursor: number;
  readonly combatLogCursor: number;
  readonly entry: CombatLogEntry;
}

const DEFAULT_PRESENTATION_QUEUE_LIMIT = 16_384;

export class ReplicationJournal {
  private healthValue: ReplicationHealth = "uninitialized";
  private resyncReasonValue: ResyncReason | null = null;
  private authoritativeValue: ReplicaView | null = null;
  private presentationValue: ReplicaView | null = null;
  private readonly presentationEvents: GameEventPayload[] = [];
  private readonly pendingSessions: PendingSession[] = [];
  private readonly pendingCombatLogs: PendingCombatLog[] = [];
  private readonly presentationQueueLimit: number;

  constructor(presentationQueueLimit = DEFAULT_PRESENTATION_QUEUE_LIMIT) {
    if (!Number.isInteger(presentationQueueLimit) || presentationQueueLimit < 1) {
      throw new RangeError("presentationQueueLimit must be a positive integer");
    }
    this.presentationQueueLimit = presentationQueueLimit;
  }

  bootstrap(bootstrap: ReplicationBootstrapResponse): ReplicationJournalState {
    if (
      bootstrap.protocol.event_contract_version !== EVENT_CONTRACT_VERSION
      || bootstrap.protocol.event_contract_hash !== EVENT_CONTRACT_HASH
    ) {
      this.requireResync("contract_mismatch");
      return this.state();
    }
    const base: ReplicaView = {
      generationId: bootstrap.protocol.generation_id,
      eventCursor: bootstrap.event_cursor,
      combatLogCursor: bootstrap.combat_log_cursor,
      world: {
        state: bootstrap.state,
        visibility: bootstrap.visibility,
      },
      session: bootstrap.session,
      combatLog: bootstrap.combat_log,
    };
    this.authoritativeValue = base;
    this.presentationValue = base;
    this.presentationEvents.length = 0;
    this.pendingSessions.length = 0;
    this.pendingCombatLogs.length = 0;
    this.healthValue = "ready";
    this.resyncReasonValue = null;
    return this.state();
  }

  ingest(envelope: ReplicationSseEnvelope): IngestResult {
    if (this.healthValue !== "ready") {
      return this.result("resync_required");
    }
    const authoritative = this.requireAuthoritative();
    switch (envelope.event) {
      case "sync":
      case "heartbeat":
        if (envelope.data.generation_id !== authoritative.generationId) {
          this.requireResync("generation_changed");
          return this.result("resync_required");
        }
        if (envelope.data.session !== null) {
          this.authoritativeValue = { ...authoritative, session: envelope.data.session };
          this.queuePendingSession(envelope.data.event_cursor, envelope.data.session);
          this.flushPresentationMetadata();
          return this.result("applied");
        }
        return this.result("metadata");
      case "evicted":
        this.requireResync("subscriber_evicted");
        return this.result("resync_required");
      case "session":
        this.authoritativeValue = { ...authoritative, session: envelope.data };
        this.queuePendingSession(authoritative.eventCursor, envelope.data);
        this.flushPresentationMetadata();
        return this.result("applied");
      case "game_event":
        return this.ingestGameEvent(envelope.data);
      case "combat_log":
        return this.ingestCombatLog(envelope.data);
    }
  }

  peekPresentationEvent(): GameEventPayload | null {
    return this.presentationEvents[0] ?? null;
  }

  pendingPresentationEvents(): ReadonlyArray<GameEventPayload> {
    return [...this.presentationEvents];
  }

  commitPresentationEvent(eventCursor: number): ReplicaView {
    if (this.healthValue !== "ready") {
      throw new Error("cannot advance presentation while replication requires resync");
    }
    const next = this.presentationEvents[0];
    if (next === undefined) {
      throw new Error("no presentation event is pending");
    }
    if (next.event_cursor !== eventCursor) {
      throw new Error(
        `presentation acknowledgement ${eventCursor} does not match next cursor ${next.event_cursor}`,
      );
    }
    const presentation = this.requirePresentation();
    this.presentationEvents.shift();
    this.presentationValue = {
      ...presentation,
      eventCursor: next.event_cursor,
      world: reduceWorld(presentation.world, next.event),
    };
    this.flushPresentationMetadata();
    return this.requirePresentation();
  }

  commitNextPresentationEvent(): ReplicaView | null {
    const next = this.peekPresentationEvent();
    return next === null ? null : this.commitPresentationEvent(next.event_cursor);
  }

  commitPresentationThrough(eventCursor: number): ReplicaView {
    if (!Number.isInteger(eventCursor) || eventCursor < 0) {
      throw new RangeError("eventCursor must be a non-negative integer");
    }
    const authoritative = this.requireAuthoritative();
    if (eventCursor > authoritative.eventCursor) {
      throw new RangeError(
        `presentation cursor ${eventCursor} exceeds authoritative cursor ${authoritative.eventCursor}`,
      );
    }
    while (
      this.presentationEvents.length > 0
      && (this.presentationEvents[0]?.event_cursor ?? Number.POSITIVE_INFINITY) <= eventCursor
    ) {
      this.commitNextPresentationEvent();
    }
    return this.requirePresentation();
  }

  state(): ReplicationJournalState {
    return {
      health: this.healthValue,
      resyncReason: this.resyncReasonValue,
      authoritative: this.authoritativeValue,
      presentation: this.presentationValue,
      presentationBacklog: this.presentationEvents.length,
    };
  }

  private ingestGameEvent(payload: GameEventPayload): IngestResult {
    const authoritative = this.requireAuthoritative();
    if (payload.generation_id !== authoritative.generationId) {
      this.requireResync("generation_changed");
      return this.result("resync_required");
    }
    if (payload.event_cursor <= authoritative.eventCursor) {
      return this.result("duplicate");
    }
    if (
      payload.event_cursor !== authoritative.eventCursor + 1
      || payload.event_index !== payload.event_cursor - 1
    ) {
      this.requireResync("event_cursor_gap");
      return this.result("resync_required");
    }

    this.authoritativeValue = {
      ...authoritative,
      eventCursor: payload.event_cursor,
      world: reduceWorld(authoritative.world, payload.event),
    };
    this.presentationEvents.push(payload);
    if (this.presentationEvents.length > this.presentationQueueLimit) {
      this.requireResync("presentation_queue_overflow");
      return this.result("resync_required");
    }
    return this.result("applied");
  }

  private ingestCombatLog(
    payload: Extract<ReplicationSseEnvelope, { event: "combat_log" }>["data"],
  ): IngestResult {
    const authoritative = this.requireAuthoritative();
    if (payload.generation_id !== authoritative.generationId) {
      this.requireResync("generation_changed");
      return this.result("resync_required");
    }
    if (payload.combat_log_cursor <= authoritative.combatLogCursor) {
      return this.result("duplicate");
    }
    if (
      payload.combat_log_cursor !== authoritative.combatLogCursor + 1
      || payload.log_index !== payload.combat_log_cursor - 1
    ) {
      this.requireResync("combat_log_cursor_gap");
      return this.result("resync_required");
    }
    this.authoritativeValue = {
      ...authoritative,
      combatLogCursor: payload.combat_log_cursor,
      combatLog: [...authoritative.combatLog, payload.entry],
    };
    this.pendingCombatLogs.push({
      eventCursor: payload.event_cursor,
      combatLogCursor: payload.combat_log_cursor,
      entry: payload.entry,
    });
    this.flushPresentationMetadata();
    return this.result("applied");
  }

  private flushPresentationMetadata(): void {
    let presentation = this.requirePresentation();
    while (
      this.pendingSessions.length > 0
      && (this.pendingSessions[0]?.eventCursor ?? Number.POSITIVE_INFINITY) <= presentation.eventCursor
    ) {
      const pending = this.pendingSessions.shift();
      if (pending !== undefined) {
        presentation = { ...presentation, session: pending.session };
      }
    }
    while (
      this.pendingCombatLogs.length > 0
      && (this.pendingCombatLogs[0]?.eventCursor ?? Number.POSITIVE_INFINITY) <= presentation.eventCursor
    ) {
      const pending = this.pendingCombatLogs.shift();
      if (pending !== undefined) {
        presentation = {
          ...presentation,
          combatLogCursor: pending.combatLogCursor,
          combatLog: [...presentation.combatLog, pending.entry],
        };
      }
    }
    this.presentationValue = presentation;
  }

  private queuePendingSession(eventCursor: number, session: SessionPingResponse): void {
    const lastIndex = this.pendingSessions.length - 1;
    const last = this.pendingSessions[lastIndex];
    if (last !== undefined && last.eventCursor === eventCursor) {
      this.pendingSessions[lastIndex] = { eventCursor, session };
      return;
    }
    this.pendingSessions.push({ eventCursor, session });
  }

  private requireResync(reason: ResyncReason): void {
    this.healthValue = "resync_required";
    this.resyncReasonValue = reason;
  }

  private requireAuthoritative(): ReplicaView {
    if (this.authoritativeValue === null) {
      throw new Error("replication journal has not been bootstrapped");
    }
    return this.authoritativeValue;
  }

  private requirePresentation(): ReplicaView {
    if (this.presentationValue === null) {
      throw new Error("replication journal has not been bootstrapped");
    }
    return this.presentationValue;
  }

  private result(status: IngestStatus): IngestResult {
    return {
      status,
      health: this.healthValue,
      resyncReason: this.resyncReasonValue,
      eventCursor: this.authoritativeValue?.eventCursor ?? null,
      combatLogCursor: this.authoritativeValue?.combatLogCursor ?? null,
      presentationBacklog: this.presentationEvents.length,
    };
  }
}
