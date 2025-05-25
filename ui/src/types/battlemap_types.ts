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

// Entity sprite association
export interface EntitySpriteMapping {
  readonly entityId: string;
  readonly spriteFolder: string;
  readonly currentAnimation: AnimationState;
  readonly currentDirection: Direction;
  readonly scale?: number; // Optional scale multiplier, defaults to 1.0
  readonly animationDurationSeconds?: number; // Optional animation duration in seconds, defaults to 2.0 (2 seconds for full cycle)
}

// Available sprite folders (read from assets/entities)
export type SpriteFolderName = string; // Will be dynamically loaded

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