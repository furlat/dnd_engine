import type { CombatLogEntry, PlayerReplicationProtocolIdentity, PlayerReplicationWatermarks, SubjectiveFramesResponse, SubjectivePerspective, SubjectiveReplicatedWorld, SubjectiveReplicationBootstrap, SubjectiveReplicationFrame } from "./generated/contracts.generated.js";
import { type SubjectiveSseEnvelope, type SubjectiveStreamPosition } from "./subjectiveSse.js";
export type SubjectiveReplicationHealth = "uninitialized" | "ready" | "resync_required";
export type SubjectiveResyncReason = "contract_mismatch" | "source_stream_changed" | "generation_changed" | "perspective_epoch_changed" | "observation_cursor_gap" | "combat_log_cursor_gap" | "replay_conflict" | "presentation_id_reused" | "presentation_queue_overflow";
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
/**
 * Duplicate payloads are retained for the same 4,096 slots as the canonical
 * server journal's default observation and combat-log retention windows.
 */
export declare const SUBJECTIVE_DUPLICATE_RETENTION_LIMIT = 4096;
/** Canonical player replica. It consumes patches and safe cues, never engine events. */
export declare class SubjectiveReplicationJournal {
    private healthValue;
    private resyncReasonValue;
    private authoritativeValue;
    private presentationValue;
    private capturedWatermarksValue;
    private readonly pendingFrames;
    private readonly pendingLogs;
    private pendingFrameHead;
    private pendingLogHead;
    private readonly knownFrames;
    private readonly knownLogs;
    private readonly presentationIds;
    private presentationHeadSlot;
    private pendingResetFrameCount;
    private incarnation;
    private lastLogEventCursor;
    private readonly presentationQueueLimit;
    constructor(options?: SubjectiveReplicationJournalOptions);
    bootstrap(seed: SubjectiveReplicationBootstrap): SubjectiveReplicationJournalState;
    ingest(envelope: SubjectiveSseEnvelope): SubjectiveJournalIngestResult;
    peekPresentationFrame(): SubjectiveReplicationFrame | null;
    pendingPresentationFrames(): ReadonlyArray<SubjectiveReplicationFrame>;
    previewPresentationFrame(observationCursor: number): SubjectivePresentationFramePreview;
    commitPresentationFrame(token: PresentationHeadPreviewToken): SubjectiveReplicaView;
    inspectResetPresentationHead(observationCursor: number): ExactResetPresentationHead;
    resetPresentationFrame(token: PresentationResetHeadToken): SubjectiveReplicaView;
    streamPosition(): SubjectiveStreamPosition;
    state(): SubjectiveReplicationJournalState;
    invalidate(reason: SubjectiveResyncReason): SubjectiveReplicationJournalState;
    private ingestSync;
    private ingestFrame;
    private ingestLog;
    private flushPresentationLogs;
    private checkQueueLimit;
    private resyncResult;
    private requireResync;
    private clear;
    private compactPendingFrames;
    private compactPendingLogs;
    private requireAuthoritative;
    private requirePresentation;
    private requireHeadSlot;
    private result;
}
export declare function assertCombatLogWindow(window: SubjectiveReplicationBootstrap["combat_log_frames"]): void;
/** Validate one atomic player reset exactly as the Python bootstrap model does. */
export declare function assertSubjectiveReplicationBootstrap(seed: SubjectiveReplicationBootstrap): void;
export declare function assertSubjectiveFramesPage(page: SubjectiveFramesResponse): void;
export {};
//# sourceMappingURL=subjectiveJournal.d.ts.map