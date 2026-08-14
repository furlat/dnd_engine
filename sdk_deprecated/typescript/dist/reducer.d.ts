import type { APIEntitySummary, APIGrid, SubjectiveEncounter, SubjectiveFloorObject, SubjectivePerspective, SubjectiveReplicatedWorld, SubjectiveWorldPatch } from "./generated/contracts.generated.js";
/** Apply one complete observation-frame patch transaction. */
export declare function reduceSubjectiveWorld(world: SubjectiveReplicatedWorld, patches: ReadonlyArray<SubjectiveWorldPatch>): SubjectiveReplicatedWorld;
/** Validate the cross-field invariants needed by every renderer seed. */
export declare function assertSubjectiveWorld(world: SubjectiveReplicatedWorld, perspective: SubjectivePerspective, path?: string): void;
/** Validate nested model semantics before a frame is accepted or reduced. */
export declare function assertSubjectiveWorldPatch(patch: SubjectiveWorldPatch, path?: string): void;
/** Validate connector structure shared by objective and subjective projections. */
export declare function assertGridConnectorStructure(grid: APIGrid): void;
export declare function assertSubjectiveFloorObject(object: SubjectiveFloorObject, path?: string): void;
export declare function assertSubjectiveEncounter(encounter: SubjectiveEncounter, path?: string): void;
export type { APIEntitySummary, SubjectiveReplicatedWorld };
//# sourceMappingURL=reducer.d.ts.map