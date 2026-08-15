import { type APIEntitySummary, type GameEventFrame, type SubjectiveCombatLogDelivery, type SubjectiveFrameDelivery, type SubjectiveReplicationBootstrap, type SubjectiveReplicationFrame, type SubjectiveSyncDelivery } from "../index.js";
export declare function entity(uuid: string, name: string, position: [number, number]): APIEntitySummary;
export declare function bootstrap(generationId?: string): SubjectiveReplicationBootstrap;
export declare function replicationFrame(cursor?: number): SubjectiveReplicationFrame;
export declare function syncDelivery(captured?: number): SubjectiveSyncDelivery;
export declare function frameDelivery(cursor?: number): SubjectiveFrameDelivery;
export declare function hiddenLogDelivery(cursor?: number, eventCursor?: number): SubjectiveCombatLogDelivery;
export declare function objectiveStepFrame(cursor?: number): GameEventFrame;
export declare function watermarks(source?: number, observation?: number, presentation?: number, log?: number): {
    source_event_cursor: number;
    observation_cursor: number;
    presentation_cursor: number;
    combat_log_cursor: number;
};
//# sourceMappingURL=fixtures.d.ts.map