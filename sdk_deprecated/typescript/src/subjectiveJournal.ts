import type {
  CombatLogEntry,
  PlayerReplicationProtocolIdentity,
  PlayerReplicationWatermarks,
  SubjectiveCombatLogDelivery,
  SubjectiveCombatLogFrame,
  SubjectiveFramesResponse,
  SubjectivePerspective,
  SubjectiveReplicatedWorld,
  SubjectiveReplicationBootstrap,
  SubjectiveReplicationFrame,
} from "./generated/contracts.generated.js";
import { assertSubjectiveWorld, reduceSubjectiveWorld } from "./reducer.js";
import {
  assertDominates,
  assertPerspective,
  assertProtocol,
  assertSubjectiveCombatLogDelivery,
  assertSubjectiveFrame,
  assertWatermarks,
  type SubjectiveSseEnvelope,
  type SubjectiveStreamPosition,
} from "./subjectiveSse.js";
import { ContractValidationError } from "./validation.js";

export type SubjectiveReplicationHealth = "uninitialized" | "ready" | "resync_required";
export type SubjectiveResyncReason =
  | "contract_mismatch"
  | "source_stream_changed"
  | "generation_changed"
  | "perspective_epoch_changed"
  | "observation_cursor_gap"
  | "combat_log_cursor_gap"
  | "replay_conflict"
  | "presentation_id_reused"
  | "presentation_queue_overflow";

export interface SubjectiveCombatLogRecord {
  readonly cursor: number;
  readonly eventCursor: number;
  readonly entry: CombatLogEntry;
}

export interface SubjectiveReplicaView {
  readonly protocol: PlayerReplicationProtocolIdentity;
  readonly perspective: SubjectivePerspective;
  readonly watermarks: PlayerReplicationWatermarks;
  readonly world: SubjectiveReplicatedWorld;
  readonly combatLog: ReadonlyArray<SubjectiveCombatLogRecord>;
}

export interface SubjectiveReplicationJournalState {
  readonly health: SubjectiveReplicationHealth;
  readonly resyncReason: SubjectiveResyncReason | null;
  readonly authoritative: SubjectiveReplicaView | null;
  readonly presentation: SubjectiveReplicaView | null;
  readonly capturedWatermarks: PlayerReplicationWatermarks | null;
  readonly presentationBacklog: number;
  readonly pendingResetFrames: number;
}

export interface SubjectiveJournalIngestResult {
  readonly status: "applied" | "duplicate" | "metadata" | "resync_required";
  readonly state: SubjectiveReplicationJournalState;
}

export interface SubjectiveReplicationJournalOptions {
  readonly presentationQueueLimit?: number;
}

declare const normalHeadTokenBrand: unique symbol;
declare const resetHeadTokenBrand: unique symbol;

/** Opaque authority for committing one exact immutable NORMAL queue head. */
export interface PresentationHeadPreviewToken {
  readonly [normalHeadTokenBrand]: "normal";
}

/** Opaque authority for applying one exact immutable RESET_REQUIRED queue head. */
export interface PresentationResetHeadToken {
  readonly [resetHeadTokenBrand]: "reset";
}

export interface SubjectivePresentationFramePreview {
  readonly token: PresentationHeadPreviewToken;
  readonly frame: SubjectiveReplicationFrame;
  readonly candidatePresentation: SubjectiveReplicaView;
}

export interface ExactResetPresentationHead {
  readonly token: PresentationResetHeadToken;
  readonly frame: SubjectiveReplicationFrame;
}

class NormalHeadToken implements PresentationHeadPreviewToken {
  declare readonly [normalHeadTokenBrand]: "normal";

  toJSON(): never {
    throw new TypeError("presentation head tokens are not serializable");
  }
}

class ResetHeadToken implements PresentationResetHeadToken {
  declare readonly [resetHeadTokenBrand]: "reset";

  toJSON(): never {
    throw new TypeError("presentation reset tokens are not serializable");
  }
}

type PresentationHeadSlot =
  | {
    readonly kind: "normal";
    readonly incarnation: number;
    readonly basePresentation: SubjectiveReplicaView;
    readonly baseDigest: string;
    readonly headDigest: string;
    readonly observationCursor: number;
    readonly token: NormalHeadToken;
    readonly preview: SubjectivePresentationFramePreview;
  }
  | {
    readonly kind: "reset";
    readonly incarnation: number;
    readonly basePresentation: SubjectiveReplicaView;
    readonly baseDigest: string;
    readonly headDigest: string;
    readonly observationCursor: number;
    readonly token: ResetHeadToken;
    readonly head: ExactResetPresentationHead;
  };

const DEFAULT_PRESENTATION_QUEUE_LIMIT = 16_384;
/**
 * Duplicate payloads are retained for the same 4,096 slots as the canonical
 * server journal's default observation and combat-log retention windows.
 */
export const SUBJECTIVE_DUPLICATE_RETENTION_LIMIT = 4_096;

/** Canonical player replica. It consumes patches and safe cues, never engine events. */
export class SubjectiveReplicationJournal {
  private healthValue: SubjectiveReplicationHealth = "uninitialized";
  private resyncReasonValue: SubjectiveResyncReason | null = null;
  private authoritativeValue: SubjectiveReplicaView | null = null;
  private presentationValue: SubjectiveReplicaView | null = null;
  private capturedWatermarksValue: PlayerReplicationWatermarks | null = null;
  private readonly pendingFrames: SubjectiveReplicationFrame[] = [];
  private readonly pendingLogs: SubjectiveCombatLogFrame[] = [];
  private pendingFrameHead = 0;
  private pendingLogHead = 0;
  private readonly knownFrames = new Map<number, string>();
  private readonly knownLogs = new Map<number, string>();
  private readonly presentationIds = new Set<string>();
  private presentationHeadSlot: PresentationHeadSlot | null = null;
  private pendingResetFrameCount = 0;
  private incarnation = 0;
  private lastLogEventCursor = 0;
  private readonly presentationQueueLimit: number;

  constructor(options: SubjectiveReplicationJournalOptions = {}) {
    const limit = options.presentationQueueLimit ?? DEFAULT_PRESENTATION_QUEUE_LIMIT;
    if (!Number.isSafeInteger(limit) || limit < 1) {
      throw new RangeError("presentationQueueLimit must be a positive safe integer");
    }
    this.presentationQueueLimit = limit;
  }

  bootstrap(seed: SubjectiveReplicationBootstrap): SubjectiveReplicationJournalState {
    this.clear();
    try {
      assertSubjectiveReplicationBootstrap(seed);
    } catch (error) {
      if (!(error instanceof ContractValidationError)) throw error;
      this.requireResync("contract_mismatch", true);
      return this.state();
    }

    const combatLog: SubjectiveCombatLogRecord[] = [];
    for (const frame of seed.combat_log_frames.frames) {
      this.lastLogEventCursor = frame.event_cursor;
      if (frame.entry !== null) {
        combatLog.push({
          cursor: frame.combat_log_cursor,
          eventCursor: frame.event_cursor,
          entry: frame.entry,
        });
      }
    }
    const view = cloneFrozen<SubjectiveReplicaView>({
      protocol: seed.protocol,
      perspective: seed.perspective,
      watermarks: seed.watermarks,
      world: seed.world,
      combatLog,
    });
    this.authoritativeValue = view;
    this.presentationValue = view;
    this.capturedWatermarksValue = cloneFrozen(seed.watermarks);
    this.healthValue = "ready";
    return this.state();
  }

  ingest(envelope: SubjectiveSseEnvelope): SubjectiveJournalIngestResult {
    if (this.healthValue !== "ready") return this.result("resync_required");
    try {
      switch (envelope.event) {
        case "sync":
          return this.ingestSync(envelope.data);
        case "frame":
          return this.ingestFrame(envelope.data.frame);
        case "combat_log":
          return this.ingestLog(envelope.data);
      }
    } catch (error) {
      if (!(error instanceof ContractValidationError)) throw error;
      this.requireResync("contract_mismatch", true);
      return this.result("resync_required");
    }
  }

  peekPresentationFrame(): SubjectiveReplicationFrame | null {
    return this.pendingFrames[this.pendingFrameHead] ?? null;
  }

  pendingPresentationFrames(): ReadonlyArray<SubjectiveReplicationFrame> {
    return this.pendingFrames.slice(this.pendingFrameHead);
  }

  previewPresentationFrame(observationCursor: number): SubjectivePresentationFramePreview {
    if (this.healthValue !== "ready") throw new Error("replication requires resynchronization");
    const frame = this.pendingFrames[this.pendingFrameHead];
    if (frame === undefined) throw new Error("no presentation frame is pending");
    if (frame.watermarks.observation_cursor !== observationCursor) {
      throw new Error(
        `presentation preview ${observationCursor} does not match ${frame.watermarks.observation_cursor}`,
      );
    }
    if (frame.presentation_delivery !== "normal") {
      throw new Error("the presentation queue head requires reset handling");
    }
    const presentation = this.requirePresentation();
    const headDigest = stableJson(frame);
    const baseDigest = stableJson(presentation);
    const existing = this.presentationHeadSlot;
    if (
      existing?.kind === "normal"
      && existing.incarnation === this.incarnation
      && existing.basePresentation === presentation
      && existing.baseDigest === baseDigest
      && existing.headDigest === headDigest
      && existing.observationCursor === observationCursor
    ) {
      return existing.preview;
    }
    const world = reduceSubjectiveWorld(presentation.world, frame.patches);
    assertSubjectiveWorld(world, presentation.perspective);
    const candidate = cloneFrozen<SubjectiveReplicaView>({
      ...presentation,
      watermarks: {
        ...frame.watermarks,
        combat_log_cursor: presentation.watermarks.combat_log_cursor,
      },
      world,
    });
    const frozenFrame = cloneFrozen(frame);
    const token = Object.freeze(new NormalHeadToken());
    const preview = Object.freeze({
      token,
      frame: frozenFrame,
      candidatePresentation: candidate,
    });
    this.presentationHeadSlot = {
      kind: "normal",
      incarnation: this.incarnation,
      basePresentation: presentation,
      baseDigest,
      headDigest,
      observationCursor,
      token,
      preview,
    };
    return preview;
  }

  commitPresentationFrame(token: PresentationHeadPreviewToken): SubjectiveReplicaView {
    const slot = this.requireHeadSlot("normal", token);
    const frame = this.pendingFrames[this.pendingFrameHead];
    const presentation = this.requirePresentation();
    if (
      frame === undefined
      || frame.presentation_delivery !== "normal"
      || frame.watermarks.observation_cursor !== slot.observationCursor
      || stableJson(frame) !== slot.headDigest
      || presentation !== slot.basePresentation
      || stableJson(presentation) !== slot.baseDigest
    ) {
      this.presentationHeadSlot = null;
      throw new Error("presentation head token is stale");
    }
    this.presentationValue = slot.preview.candidatePresentation;
    this.pendingFrameHead += 1;
    this.presentationHeadSlot = null;
    this.compactPendingFrames();
    this.flushPresentationLogs();
    return this.requirePresentation();
  }

  inspectResetPresentationHead(observationCursor: number): ExactResetPresentationHead {
    if (this.healthValue !== "ready") throw new Error("replication requires resynchronization");
    const frame = this.pendingFrames[this.pendingFrameHead];
    if (frame === undefined) throw new Error("no presentation frame is pending");
    if (frame.watermarks.observation_cursor !== observationCursor) {
      throw new Error(
        `presentation reset ${observationCursor} does not match ${frame.watermarks.observation_cursor}`,
      );
    }
    if (frame.presentation_delivery !== "presentation_reset_required") {
      throw new Error("the presentation queue head requires normal preview handling");
    }
    const presentation = this.requirePresentation();
    const headDigest = stableJson(frame);
    const baseDigest = stableJson(presentation);
    const existing = this.presentationHeadSlot;
    if (
      existing?.kind === "reset"
      && existing.incarnation === this.incarnation
      && existing.basePresentation === presentation
      && existing.baseDigest === baseDigest
      && existing.headDigest === headDigest
      && existing.observationCursor === observationCursor
    ) {
      return existing.head;
    }
    const token = Object.freeze(new ResetHeadToken());
    const head = Object.freeze({ token, frame: cloneFrozen(frame) });
    this.presentationHeadSlot = {
      kind: "reset",
      incarnation: this.incarnation,
      basePresentation: presentation,
      baseDigest,
      headDigest,
      observationCursor,
      token,
      head,
    };
    return head;
  }

  resetPresentationFrame(token: PresentationResetHeadToken): SubjectiveReplicaView {
    const slot = this.requireHeadSlot("reset", token);
    const frame = this.pendingFrames[this.pendingFrameHead];
    const presentation = this.requirePresentation();
    if (
      frame === undefined
      || frame.presentation_delivery !== "presentation_reset_required"
      || frame.watermarks.observation_cursor !== slot.observationCursor
      || stableJson(frame) !== slot.headDigest
      || presentation !== slot.basePresentation
      || stableJson(presentation) !== slot.baseDigest
    ) {
      this.presentationHeadSlot = null;
      throw new Error("presentation reset token is stale");
    }
    const world = reduceSubjectiveWorld(presentation.world, frame.patches);
    assertSubjectiveWorld(world, presentation.perspective);
    const candidate = cloneFrozen<SubjectiveReplicaView>({
      ...presentation,
      watermarks: {
        ...frame.watermarks,
        combat_log_cursor: presentation.watermarks.combat_log_cursor,
      },
      world,
    });
    this.presentationValue = candidate;
    this.pendingFrameHead += 1;
    this.pendingResetFrameCount -= 1;
    this.presentationHeadSlot = null;
    this.compactPendingFrames();
    this.flushPresentationLogs();
    return this.requirePresentation();
  }

  streamPosition(): SubjectiveStreamPosition {
    const view = this.requireAuthoritative();
    return {
      sourceStreamId: view.protocol.source_stream_id,
      generationId: view.protocol.generation_id,
      perspectiveEpochId: view.perspective.perspective_epoch_id,
      sourceEventCursor: view.watermarks.source_event_cursor,
      observationCursor: view.watermarks.observation_cursor,
      presentationCursor: view.watermarks.presentation_cursor,
      combatLogCursor: view.watermarks.combat_log_cursor,
    };
  }

  state(): SubjectiveReplicationJournalState {
    return {
      health: this.healthValue,
      resyncReason: this.resyncReasonValue,
      authoritative: this.authoritativeValue,
      presentation: this.presentationValue,
      capturedWatermarks: this.capturedWatermarksValue,
      presentationBacklog: this.pendingFrames.length - this.pendingFrameHead,
      pendingResetFrames: this.pendingResetFrameCount,
    };
  }

  invalidate(reason: SubjectiveResyncReason): SubjectiveReplicationJournalState {
    this.requireResync(reason, true);
    return this.state();
  }

  private ingestSync(
    delivery: Extract<SubjectiveSseEnvelope, { readonly event: "sync" }>["data"],
  ): SubjectiveJournalIngestResult {
    const authoritative = this.requireAuthoritative();
    assertProtocol(delivery.protocol);
    assertPerspective(delivery.perspective);
    const reason = identityReason(
      {
        source_stream_id: delivery.protocol.source_stream_id,
        generation_id: delivery.protocol.generation_id,
        perspective_epoch_id: delivery.perspective.perspective_epoch_id,
      },
      authoritative,
    );
    if (reason !== "contract_mismatch") {
      this.requireResync(reason, true);
      return this.result("resync_required");
    }
    if (stableJson(delivery.perspective) !== stableJson(authoritative.perspective)) {
      this.requireResync("perspective_epoch_changed", true);
      return this.result("resync_required");
    }
    assertDominates(delivery.watermarks, authoritative.watermarks, "$subjective.sync.watermarks");
    this.capturedWatermarksValue = cloneFrozen(delivery.watermarks);
    return this.result("metadata");
  }

  private ingestFrame(frame: SubjectiveReplicationFrame): SubjectiveJournalIngestResult {
    const authoritative = this.requireAuthoritative();
    const reason = identityReason(frame, authoritative);
    if (reason !== "contract_mismatch") {
      this.requireResync(reason, true);
      return this.result("resync_required");
    }
    assertSubjectiveFrame(frame);
    frame = cloneFrozen(frame);
    const cursor = frame.watermarks.observation_cursor;
    if (cursor <= authoritative.watermarks.observation_cursor) {
      return this.knownFrames.get(cursor) === stableJson(frame)
        ? this.result("duplicate")
        : this.resyncResult("replay_conflict");
    }
    if (
      cursor !== authoritative.watermarks.observation_cursor + 1
      || frame.presentation_from_cursor !== authoritative.watermarks.presentation_cursor
      || frame.watermarks.source_event_cursor < authoritative.watermarks.source_event_cursor
      || frame.watermarks.combat_log_cursor !== authoritative.watermarks.combat_log_cursor
    ) {
      return this.resyncResult("observation_cursor_gap");
    }
    for (const cue of frame.presentation) {
      if (this.presentationIds.has(cue.presentation_id)) {
        return this.resyncResult("presentation_id_reused");
      }
    }
    const world = reduceSubjectiveWorld(authoritative.world, frame.patches);
    assertSubjectiveWorld(world, authoritative.perspective);
    // Presentation IDs remain partition-global even after duplicate payloads
    // age out; an old ID may never identify a different renderer transaction.
    for (const cue of frame.presentation) this.presentationIds.add(cue.presentation_id);
    rememberRecent(this.knownFrames, cursor, stableJson(frame));
    this.authoritativeValue = cloneFrozen<SubjectiveReplicaView>({
      ...authoritative,
      watermarks: {
        ...frame.watermarks,
        combat_log_cursor: authoritative.watermarks.combat_log_cursor,
      },
      world,
    });
    this.pendingFrames.push(frame);
    if (frame.presentation_delivery === "presentation_reset_required") {
      this.pendingResetFrameCount += 1;
    }
    return this.checkQueueLimit();
  }

  private ingestLog(delivery: SubjectiveCombatLogDelivery): SubjectiveJournalIngestResult {
    const authoritative = this.requireAuthoritative();
    assertSubjectiveCombatLogDelivery(delivery);
    delivery = cloneFrozen(delivery);
    const frame = delivery.frame;
    const reason = identityReason(frame, authoritative);
    if (reason !== "contract_mismatch") {
      this.requireResync(reason, true);
      return this.result("resync_required");
    }
    if (frame.combat_log_cursor <= authoritative.watermarks.combat_log_cursor) {
      return this.knownLogs.get(frame.combat_log_cursor) === stableJson(delivery)
        ? this.result("duplicate")
        : this.resyncResult("replay_conflict");
    }
    if (
      frame.combat_log_cursor !== authoritative.watermarks.combat_log_cursor + 1
      || frame.event_cursor < this.lastLogEventCursor
      || !equalWatermarks(delivery.watermarks, {
        ...authoritative.watermarks,
        combat_log_cursor: frame.combat_log_cursor,
      })
    ) {
      return this.resyncResult("combat_log_cursor_gap");
    }
    const record = frame.entry === null ? null : {
      cursor: frame.combat_log_cursor,
      eventCursor: frame.event_cursor,
      entry: frame.entry,
    };
    this.authoritativeValue = cloneFrozen<SubjectiveReplicaView>({
      ...authoritative,
      watermarks: {
        ...authoritative.watermarks,
        combat_log_cursor: frame.combat_log_cursor,
      },
      combatLog: record === null ? authoritative.combatLog : [...authoritative.combatLog, record],
    });
    this.lastLogEventCursor = frame.event_cursor;
    rememberRecent(this.knownLogs, frame.combat_log_cursor, stableJson(delivery));
    this.pendingLogs.push(frame);
    this.flushPresentationLogs();
    return this.checkQueueLimit();
  }

  private flushPresentationLogs(): void {
    // An issued presentation-head token is an exact authority over the current
    // presentation base plus one immutable world frame. Legal combat-log
    // delivery is an independent stream and must not replace that base object
    // (or the frozen candidate) while the token is live. Retain eligible logs
    // behind the active head; commit/reset installs the candidate exactly once,
    // clears the slot, then calls this method to attach every now-eligible log.
    if (this.presentationHeadSlot !== null) return;
    let presentation = this.requirePresentation();
    while (
      this.pendingLogHead < this.pendingLogs.length
      && (this.pendingLogs[this.pendingLogHead]?.event_cursor ?? Number.POSITIVE_INFINITY)
        <= presentation.watermarks.source_event_cursor
    ) {
      const frame = this.pendingLogs[this.pendingLogHead];
      this.pendingLogHead += 1;
      if (frame === undefined) break;
      const record = frame.entry === null ? null : {
        cursor: frame.combat_log_cursor,
        eventCursor: frame.event_cursor,
        entry: frame.entry,
      };
      presentation = {
        ...presentation,
        watermarks: { ...presentation.watermarks, combat_log_cursor: frame.combat_log_cursor },
        combatLog: record === null ? presentation.combatLog : [...presentation.combatLog, record],
      };
    }
    this.compactPendingLogs();
    this.presentationValue = cloneFrozen(presentation);
  }

  private checkQueueLimit(): SubjectiveJournalIngestResult {
    const queuedFrames = this.pendingFrames.length - this.pendingFrameHead;
    const queuedLogs = this.pendingLogs.length - this.pendingLogHead;
    if (queuedFrames + queuedLogs > this.presentationQueueLimit) {
      return this.resyncResult("presentation_queue_overflow");
    }
    return this.result("applied");
  }

  private resyncResult(reason: SubjectiveResyncReason): SubjectiveJournalIngestResult {
    this.requireResync(reason, true);
    return this.result("resync_required");
  }

  private requireResync(reason: SubjectiveResyncReason, clearReplica: boolean): void {
    this.incarnation += 1;
    this.healthValue = "resync_required";
    this.resyncReasonValue = reason;
    this.pendingFrames.length = 0;
    this.pendingLogs.length = 0;
    this.pendingFrameHead = 0;
    this.pendingLogHead = 0;
    this.pendingResetFrameCount = 0;
    this.presentationHeadSlot = null;
    if (clearReplica) {
      this.authoritativeValue = null;
      this.presentationValue = null;
      this.capturedWatermarksValue = null;
    }
  }

  private clear(): void {
    this.incarnation += 1;
    this.authoritativeValue = null;
    this.presentationValue = null;
    this.capturedWatermarksValue = null;
    this.pendingFrames.length = 0;
    this.pendingLogs.length = 0;
    this.pendingFrameHead = 0;
    this.pendingLogHead = 0;
    this.pendingResetFrameCount = 0;
    this.presentationHeadSlot = null;
    this.knownFrames.clear();
    this.knownLogs.clear();
    this.presentationIds.clear();
    this.lastLogEventCursor = 0;
    this.healthValue = "uninitialized";
    this.resyncReasonValue = null;
  }

  private compactPendingFrames(): void {
    if (this.pendingFrameHead >= 1_024 && this.pendingFrameHead * 2 >= this.pendingFrames.length) {
      this.pendingFrames.splice(0, this.pendingFrameHead);
      this.pendingFrameHead = 0;
    }
  }

  private compactPendingLogs(): void {
    if (this.pendingLogHead >= 1_024 && this.pendingLogHead * 2 >= this.pendingLogs.length) {
      this.pendingLogs.splice(0, this.pendingLogHead);
      this.pendingLogHead = 0;
    }
  }

  private requireAuthoritative(): SubjectiveReplicaView {
    if (this.authoritativeValue === null) throw new Error("journal has not been bootstrapped");
    return this.authoritativeValue;
  }

  private requirePresentation(): SubjectiveReplicaView {
    if (this.presentationValue === null) throw new Error("journal has not been bootstrapped");
    return this.presentationValue;
  }

  private requireHeadSlot(
    kind: "normal",
    token: PresentationHeadPreviewToken,
  ): Extract<PresentationHeadSlot, { readonly kind: "normal" }>;
  private requireHeadSlot(
    kind: "reset",
    token: PresentationResetHeadToken,
  ): Extract<PresentationHeadSlot, { readonly kind: "reset" }>;
  private requireHeadSlot(
    kind: PresentationHeadSlot["kind"],
    token: PresentationHeadPreviewToken | PresentationResetHeadToken,
  ): PresentationHeadSlot {
    if (this.healthValue !== "ready") throw new Error("replication requires resynchronization");
    const slot = this.presentationHeadSlot;
    if (
      slot === null
      || slot.kind !== kind
      || slot.incarnation !== this.incarnation
      || slot.token !== token
    ) {
      throw new Error("presentation head token does not identify the exact current head");
    }
    return slot;
  }

  private result(status: SubjectiveJournalIngestResult["status"]): SubjectiveJournalIngestResult {
    return { status, state: this.state() };
  }
}

function cloneFrozen<T>(value: T): T {
  return deepFreeze(JSON.parse(JSON.stringify(value)) as T);
}

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Readonly<Record<string, unknown>>)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

export function assertCombatLogWindow(
  window: SubjectiveReplicationBootstrap["combat_log_frames"],
): void {
  for (const [name, value] of Object.entries({
    retained_from_cursor: window.retained_from_cursor,
    from_cursor: window.from_cursor,
    through_cursor: window.through_cursor,
    total: window.total,
  })) {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new ContractValidationError(`$subjective.combat_log.${name}`, "invalid cursor");
    }
  }
  if (
    window.projection !== "subjective"
    || window.retained_from_cursor > window.from_cursor
    || window.from_cursor > window.through_cursor
    || window.through_cursor > window.total
    || window.frames.length !== window.through_cursor - window.from_cursor
  ) {
    throw new ContractValidationError("$subjective.combat_log", "invalid exact window");
  }
  let previousEventCursor = -1;
  window.frames.forEach((frame, index) => {
    if (
      frame.source_stream_id !== window.source_stream_id
      || frame.generation_id !== window.generation_id
      || frame.perspective_epoch_id !== window.perspective_epoch_id
      || frame.projection !== "subjective"
      || frame.combat_log_cursor !== window.from_cursor + index + 1
      || frame.event_cursor < previousEventCursor
    ) {
      throw new ContractValidationError("$subjective.combat_log.frames", "invalid exact frame");
    }
    previousEventCursor = frame.event_cursor;
  });
}

/** Validate one atomic player reset exactly as the Python bootstrap model does. */
export function assertSubjectiveReplicationBootstrap(
  seed: SubjectiveReplicationBootstrap,
): void {
  assertProtocol(seed.protocol);
  assertPerspective(seed.perspective);
  assertWatermarks(seed.watermarks, "$subjective.bootstrap.watermarks");
  assertSubjectiveWorld(seed.world, seed.perspective);
  assertCombatLogWindow(seed.combat_log_frames);
  const logs = seed.combat_log_frames;
  if (
    logs.source_stream_id !== seed.protocol.source_stream_id
    || logs.generation_id !== seed.protocol.generation_id
    || logs.perspective_epoch_id !== seed.perspective.perspective_epoch_id
    || logs.from_cursor !== logs.retained_from_cursor
    || logs.through_cursor !== logs.total
    || logs.total !== seed.watermarks.combat_log_cursor
  ) {
    throw new ContractValidationError(
      "$subjective.bootstrap",
      "bootstrap identities or windows differ",
    );
  }
  if (logs.frames.some((frame) => frame.event_cursor > seed.watermarks.source_event_cursor)) {
    throw new ContractValidationError(
      "$subjective.bootstrap.combat_log_frames",
      "combat-log barrier exceeds bootstrap source watermark",
    );
  }
}

export function assertSubjectiveFramesPage(page: SubjectiveFramesResponse): void {
  if (page.retained_from_observation_cursor > page.from_watermarks.observation_cursor) {
    throw new ContractValidationError(
      "$subjective.frames.retained_from_observation_cursor",
      "requested cursor precedes retained history",
    );
  }
  assertDominates(page.through_watermarks, page.from_watermarks, "$subjective.frames.through");
  assertDominates(page.captured_watermarks, page.through_watermarks, "$subjective.frames.captured");
  if (
    page.frames.length
    !== page.through_watermarks.observation_cursor - page.from_watermarks.observation_cursor
  ) {
    throw new ContractValidationError("$subjective.frames.frames", "page does not cover an exact window");
  }

  let previous = page.from_watermarks;
  const presentationIds = new Set<string>();
  page.frames.forEach((frame, index) => {
    assertSubjectiveFrame(frame);
    if (
      frame.source_stream_id !== page.source_stream_id
      || frame.generation_id !== page.generation_id
      || frame.perspective_epoch_id !== page.perspective_epoch_id
      || frame.watermarks.observation_cursor !== page.from_watermarks.observation_cursor + index + 1
      || frame.presentation_from_cursor !== previous.presentation_cursor
    ) {
      throw new ContractValidationError("$subjective.frames.frames", "frame identity or window differs from page");
    }
    assertDominates(frame.watermarks, previous, `$subjective.frames.frames[${index}].watermarks`);
    for (const cue of frame.presentation) {
      if (presentationIds.has(cue.presentation_id)) {
        throw new ContractValidationError(
          "$subjective.frames.frames.presentation",
          "presentation ID is reused within the page",
        );
      }
      presentationIds.add(cue.presentation_id);
    }
    previous = frame.watermarks;
  });
  if (!equalWatermarks(previous, page.through_watermarks)) {
    throw new ContractValidationError(
      "$subjective.frames.through_watermarks",
      "through boundary does not equal the final frame",
    );
  }
}

function identityReason(
  value: { readonly source_stream_id: string; readonly generation_id: string; readonly perspective_epoch_id: string },
  view: SubjectiveReplicaView,
): SubjectiveResyncReason {
  if (value.source_stream_id !== view.protocol.source_stream_id) return "source_stream_changed";
  if (value.generation_id !== view.protocol.generation_id) return "generation_changed";
  if (value.perspective_epoch_id !== view.perspective.perspective_epoch_id) {
    return "perspective_epoch_changed";
  }
  return "contract_mismatch";
}

function stableJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  const record = value as Readonly<Record<string, unknown>>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${stableJson(record[key])}`).join(",")}}`;
}

function rememberRecent(
  known: Map<number, string>,
  cursor: number,
  payload: string,
): void {
  known.set(cursor, payload);
  while (known.size > SUBJECTIVE_DUPLICATE_RETENTION_LIMIT) {
    const oldest = known.keys().next().value;
    if (oldest === undefined) return;
    known.delete(oldest);
  }
}

function equalWatermarks(
  left: PlayerReplicationWatermarks,
  right: PlayerReplicationWatermarks,
): boolean {
  return left.source_event_cursor === right.source_event_cursor
    && left.observation_cursor === right.observation_cursor
    && left.presentation_cursor === right.presentation_cursor
    && left.combat_log_cursor === right.combat_log_cursor;
}
