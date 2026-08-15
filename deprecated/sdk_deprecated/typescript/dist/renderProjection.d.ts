import type { APICombatant, APIEntitySummary, APIEquipmentOverview, APITile, APITraversalConnector, APIVisibilityResponse, EntityVisualLoadout, FloorObjectBlockingChannel, FloorObjectDirection, FloorObjectProjectionKind, ObjectiveReplicatedWorld, PerspectiveKind, SafeContentPresentationRef, SenseMode, StructuralEdgeKind, SubjectivePerspective, SubjectiveReplicatedWorld } from "./generated/contracts.generated.js";
export type RenderProjection = "subjective" | "objective";
export type RenderPerspectiveKind = PerspectiveKind | "objective";
export interface RenderPerspective {
    readonly kind: RenderPerspectiveKind;
    readonly controlled_entity_uuids: Array<string>;
    readonly observer_entity_uuids: Array<string>;
    readonly active_observer_uuid: string | null;
}
export interface RenderObserver {
    readonly uuid: string;
    readonly name: string;
    readonly position: [number, number];
    readonly sense_modes: Array<SenseMode>;
}
/**
 * Canonical knowledge-union mask for rendering.
 *
 * `active_observer_uuid` is deliberately absent: changing UI focus must never
 * narrow these unioned facts.
 */
export interface RenderKnowledgeUnion {
    readonly observers: Array<RenderObserver>;
    readonly visible_cells: Array<[number, number]>;
    readonly seen_cells: Array<[number, number]>;
    readonly visible_entity_uuids: Array<string>;
    readonly visible_object_uuids: Array<string>;
    readonly effective_light_levels: Record<string, number>;
}
export type RenderOwnedEdgeDirection = "north" | "east";
export type RenderStructuralEdgeKind = StructuralEdgeKind | "generic";
declare const renderStructuralEdgeKeyBrand: unique symbol;
export type RenderStructuralEdgeKey = string & {
    readonly [renderStructuralEdgeKeyBrand]: true;
};
export interface RenderStructuralEdge {
    readonly edge_key: RenderStructuralEdgeKey;
    readonly position: [number, number];
    readonly direction: RenderOwnedEdgeDirection;
    readonly kind: RenderStructuralEdgeKind;
    readonly is_open: boolean | null;
    readonly blocked_channels: Array<FloorObjectBlockingChannel>;
}
export interface RenderTraversalConnectorEndpoint {
    readonly position: readonly [number, number];
    readonly elevation_feet: number;
}
export interface RenderTraversalConnector {
    readonly uuid: string;
    readonly authored_id: string;
    readonly kind: APITraversalConnector["kind"];
    readonly presentation_key: string;
    readonly endpoints: readonly [
        RenderTraversalConnectorEndpoint,
        RenderTraversalConnectorEndpoint
    ];
    readonly enabled: boolean;
}
/**
 * Projection-neutral floor-object row.
 *
 * Subjective rows are copied only from their closed flattened contract.
 * Objective rows adapt the equivalent concrete state fields retained in the
 * diagnostic `state` record.
 */
export interface RenderFloorObject {
    readonly uuid: string;
    readonly name: string;
    readonly position: [number, number];
    readonly map_char: string;
    readonly object_kind: FloorObjectProjectionKind;
    readonly safe_presentation_ref: SafeContentPresentationRef | null;
    readonly visual_item_name: string;
    readonly visual_variant_id: string | null;
    readonly blocks_movement: boolean | null;
    readonly blocks_vision: boolean | null;
    readonly is_open: boolean | null;
    readonly blocked_directions: Array<FloorObjectDirection>;
    readonly blocked_channels: Array<FloorObjectBlockingChannel>;
    readonly is_lit: boolean | null;
    readonly very_bright_radius_feet: number | null;
    readonly bright_radius_feet: number | null;
    readonly dim_radius_feet: number | null;
}
export interface RenderCombatant {
    readonly uuid: string;
    readonly name: string;
    readonly initiative: number;
    readonly life_state: APICombatant["life_state"];
}
export interface RenderEncounter {
    readonly uuid: string;
    readonly name: string;
    readonly state: string;
    readonly round_number: number;
    readonly current_turn_index: number | null;
    readonly current_entity_uuid: string | null;
    readonly initiative_order: Array<RenderCombatant>;
}
export interface RenderGrid {
    readonly min_x: number;
    readonly min_y: number;
    readonly max_x: number;
    readonly max_y: number;
    readonly tiles: Array<APITile>;
    readonly connectors: ReadonlyArray<RenderTraversalConnector>;
    readonly structural_edges: Array<RenderStructuralEdge>;
}
export interface RenderGameState {
    readonly grid: RenderGrid;
    readonly entities: Array<APIEntitySummary>;
    readonly encounter: RenderEncounter | null;
    readonly floor_objects: Array<RenderFloorObject>;
}
export interface RenderEquipment {
    /**
     * Subjective worlds contain detail only for controlled actors. Objective
     * diagnostics contain the complete authorized diagnostic rows.
     */
    readonly detail_scope: "controlled" | "objective";
    readonly details_by_entity: Record<string, APIEquipmentOverview>;
    /** Safe appearance-only rows, independent from detailed equipment access. */
    readonly visual_loadout_by_entity: Record<string, EntityVisualLoadout>;
}
/** One deterministic, frontend-neutral input to a renderer. */
export interface ReplicatedRenderWorld {
    readonly projection: RenderProjection;
    readonly perspective: RenderPerspective;
    readonly state: RenderGameState;
    readonly knowledge: RenderKnowledgeUnion;
    readonly equipment: RenderEquipment;
}
export interface ObjectiveRenderProjectionOptions {
    /**
     * Objective diagnostics default to all observer rows. Tests may select the
     * same observer set as a subjective perspective without mutating the world.
     */
    readonly observer_entity_uuids?: ReadonlyArray<string>;
    readonly active_observer_uuid?: string | null;
}
/** Build the only render projection needed by a subjective player client. */
export declare function projectSubjectiveRenderWorld(world: SubjectiveReplicatedWorld, perspective: SubjectivePerspective): ReplicatedRenderWorld;
/** Normalize an objective diagnostic world for debug UI and parity oracles. */
export declare function projectObjectiveRenderWorld(world: ObjectiveReplicatedWorld, options?: ObjectiveRenderProjectionOptions): ReplicatedRenderWorld;
/**
 * Union every selected observer row. Shared-cell effective light uses the
 * brightest perceived value (the maximum engine LightLevel integer), making
 * the result independent of observer ordering.
 */
export declare function mergeObserverVisibility(visibility: APIVisibilityResponse, observerEntityUuids: ReadonlyArray<string>, activeObserverUuid?: string | null): RenderKnowledgeUnion;
/**
 * Normalize tile-local halves into deterministic undirected structural edges.
 *
 * South and west halves are re-owned by the adjacent canonical anchor as north
 * and east respectively. A visible structural appearance supersedes a
 * remembered reciprocal half, and any known structure suppresses a generic
 * blocker on the same physical edge.
 */
export declare function projectStructuralEdges(tiles: ReadonlyArray<APITile>): Array<RenderStructuralEdge>;
/** Return the sole stable identity for one reciprocal physical boundary. */
export declare function canonicalRenderStructuralEdgeKey(position: readonly [number, number], direction: FloorObjectDirection): RenderStructuralEdgeKey;
/** Project the privacy-safe connector field subset in deterministic order. */
export declare function projectTraversalConnectors(connectors: ReadonlyArray<APITraversalConnector>): Array<RenderTraversalConnector>;
/** Derive the safe appearance layer used by the objective debug projection. */
export declare function deriveVisualLoadout(entityUuid: string, equipment: APIEquipmentOverview | undefined): EntityVisualLoadout;
export {};
//# sourceMappingURL=renderProjection.d.ts.map