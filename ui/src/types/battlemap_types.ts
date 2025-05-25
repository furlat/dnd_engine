import { UUID, SensesType, Position, DeepReadonly, EntitySummary } from './common';

// Tile related types
export interface TileSummary {
  readonly uuid: string;
  readonly name: string;
  readonly position: Position;
  readonly walkable: boolean;
  readonly visible: boolean;
  readonly sprite_name: string | null;
}

// Response types
export interface GridSnapshot {
  readonly width: number;
  readonly height: number;
  readonly tiles: Readonly<Record<string, TileSummary>>;
}

// Senses interfaces
export interface SensesSnapshot {
  readonly entities: Readonly<Record<UUID, Position>>;
  readonly visible: Readonly<Record<string, boolean>>;
  readonly walkable: Readonly<Record<string, boolean>>;
  readonly paths: Readonly<Record<string, readonly Position[]>>;
  readonly extra_senses: readonly SensesType[];
  readonly position: Position;
  readonly seen: readonly Position[];
}

// Attack results
export interface AttackResult {
  readonly event: { // TODO: Define proper event type instead of any
    readonly type: string;
    readonly source_entity_uuid: string;
    readonly target_entity_uuid: string;
    readonly roll_results: any; // TODO: Define proper roll results type
  };
  readonly attacker: EntitySummary;
}

// Animation and sprite types
export enum AnimationState {
  IDLE = 'Idle',
  IDLE2 = 'Idle2', 
  WALK = 'Walk',
  RUN = 'Run',
  RUN_BACKWARDS = 'RunBackwards',
  CROUCH_RUN = 'CrouchRun',
  ATTACK1 = 'Attack1',
  ATTACK2 = 'Attack2', 
  ATTACK3 = 'Attack3',
  TAKE_DAMAGE = 'TakeDamage',
  DIE = 'Die'
}

export enum Direction {
  N = 'N',   // North
  NE = 'NE', // Northeast  
  E = 'E',   // East
  SE = 'SE', // Southeast
  S = 'S',   // South
  SW = 'SW', // Southwest
  W = 'W',   // West
  NW = 'NW'  // Northwest
}

// Movement state for tracking entity movement animations
export enum MovementState {
  IDLE = 'idle',           // Entity is not moving
  MOVING = 'moving',       // Entity is currently moving (animation in progress)
  RESYNCING = 'resyncing'  // Entity is resyncing visual position with server position
}

// Visual position that can be decoupled from server position
export interface VisualPosition {
  readonly x: number;
  readonly y: number;
}

// Movement animation data
export interface MovementAnimation {
  readonly entityId: string;
  readonly path: readonly Position[];           // Full path from senses
  readonly currentPathIndex: number;            // Current position in path
  readonly startTime: number;                   // Animation start timestamp
  readonly movementSpeed: number;               // Movement speed (tiles per second)
  readonly targetPosition: Position;            // Final target position
  readonly isServerApproved?: boolean;          // Whether server approved the movement
}

// NEW: Movement request interface to match backend
export interface MoveRequest {
  readonly position: Position;
  readonly include_paths_senses?: boolean;
}

// NEW: Movement response interface to match backend
export interface MovementResponse {
  readonly event: any; // EventSnapshot - TODO: Define proper event type
  readonly entity: EntitySummary;
  readonly path_senses: readonly SensesSnapshot[];
}

// Entity sprite association with decoupled animation states
export interface EntitySpriteMapping {
  readonly entityId: string;
  readonly spriteFolder: string;
  
  // Separate idle vs current animation
  readonly idleAnimation: AnimationState;       // Default animation when not moving/acting
  readonly currentAnimation: AnimationState;    // Currently playing animation
  readonly currentDirection: Direction;
  
  // Visual properties
  readonly scale?: number;                      // Optional scale multiplier, defaults to 1.0
  readonly animationDurationSeconds?: number;   // Optional animation duration in seconds, defaults to 1.0
  
  // Movement state
  readonly movementState: MovementState;
  readonly visualPosition?: VisualPosition;     // Decoupled visual position (if different from server)
  readonly isPositionSynced: boolean;           // Whether visual position matches server position
}

// Available sprite folders (read from assets/entities)
export type SpriteFolderName = string; // Will be dynamically loaded

/**
 * Helper function to create a visual position from a regular position
 */
export function toVisualPosition(position: Position): VisualPosition {
  return { x: position[0], y: position[1] };
}

/**
 * Helper function to create a regular position from a visual position
 */
export function fromVisualPosition(visualPos: VisualPosition): Position {
  return [visualPos.x, visualPos.y] as const;
}

/**
 * Helper function to check if two positions are equal
 */
export function positionsEqual(pos1: Position, pos2: Position): boolean {
  return pos1[0] === pos2[0] && pos1[1] === pos2[1];
}

/**
 * Helper function to check if visual position matches server position
 */
export function isVisualPositionSynced(visualPos: VisualPosition, serverPos: Position): boolean {
  return Math.abs(visualPos.x - serverPos[0]) < 0.01 && Math.abs(visualPos.y - serverPos[1]) < 0.01;
}

/**
 * Helper function to make a position mutable if needed for API calls
 * Only use when specifically required for API calls that need mutable arrays
 */
export function toMutablePosition(position: Position): [number, number] {
  return [...position];
}

/**
 * Helper function to make a readonly record mutable if needed for API calls
 * Only use when specifically required for API calls that need mutable data
 */
export function toMutableRecord<K extends string | number | symbol, V>(
  record: Readonly<Record<K, V>>
): Record<K, V> {
  return { ...record };
} 