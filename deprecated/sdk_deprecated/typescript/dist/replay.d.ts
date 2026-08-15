import { type ObjectiveReplayBundle, type SubjectivePlayerReplayBundle, type SubjectiveReplaySegment } from "./generated/contracts.generated.js";
/** Decode and semantically authenticate one ended objective replay. */
export declare function decodeObjectiveReplay(value: unknown): ObjectiveReplayBundle;
/** Decode one membership-scoped replay; objective/raw event payloads are not in its schema. */
export declare function decodeSubjectivePlayerReplay(value: unknown): SubjectivePlayerReplayBundle;
export declare function assertObjectiveReplay(replay: ObjectiveReplayBundle): void;
export declare function assertSubjectivePlayerReplay(replay: SubjectivePlayerReplayBundle): void;
export declare function assertSubjectiveReplaySegment(segment: SubjectiveReplaySegment, path?: string): void;
//# sourceMappingURL=replay.d.ts.map