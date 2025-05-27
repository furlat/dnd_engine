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

// NEW: Movement response from backend with optional path senses
export interface MovementResponse {
  readonly event: any; // EventSnapshot - TODO: Define proper event type
  readonly entity: EntitySummary;
  readonly path_senses?: Readonly<Record<string, SensesSnapshot>>; // Optional path senses data keyed by "x,y"
}

// NEW: Attack response types to match backend AttackMetadata and AttackResponse
export interface AttackMetadata {
  readonly weapon_slot: string;
  readonly attack_roll?: number; // The d20 roll result
  readonly attack_total?: number; // Total attack bonus + roll
  readonly target_ac?: number; // Target's AC
  readonly attack_outcome?: string; // Hit/Miss/Crit/etc
  readonly damage_rolls?: readonly number[]; // Individual damage roll totals
  readonly total_damage?: number; // Sum of all damage
  readonly damage_types?: readonly string[]; // Types of damage dealt
}

export interface AttackResponse {
  readonly event: any; // EventSnapshot - TODO: Define proper event type
  readonly metadata: AttackMetadata;
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

// NEW: Effect system types
export enum EffectType {
  // Temporary effects (play once and disappear)
  BLOOD_SPLAT = 'blood_splat',
  SPARKS = 'sparks-sheet',
  SPLASH = 'splash-sheet',
  SMOKE_SIMPLE_1 = 'smoke_simple_1',
  SMOKE_SIMPLE_2 = 'smoke_simple_2',
  SMOKE_SIMPLE_3 = 'smoke_simple_3',
  ROCK_BREAK = 'rock_break',
  LIGHT_SPARK = 'light_spark',
  
  // Permanent/looping effects (stay until removed)
  DARK_AURA = 'dark_aura',
  HOLY_LIGHT_AURA = 'holy_light_aura',
  BUBBLE_SHIELD = 'bubble_shield',
  ROTATING_SHIELD = 'rotating_shield',
  CONFUSE1 = 'confuse1',
  CONFUSE2 = 'confuse2',
  REGEN = 'regen',
  ELECTRIC_AURA = 'eletric_aura',
  FIRE_AURA = 'bonfire-sheet',
  POISON_CLOUD = 'poison_cloud-sheet',
}

export enum EffectCategory {
  TEMPORARY = 'temporary',    // Play once and disappear
  PERMANENT = 'permanent',    // Loop until removed
  ATTACHED = 'attached'       // Attached to entity, moves with it
}

export interface EffectAnimation {
  readonly effectId: string;           // Unique ID for this effect instance
  readonly effectType: EffectType;     // Type of effect
  readonly category: EffectCategory;   // How the effect behaves
  readonly position: VisualPosition;   // World position of the effect
  readonly startTime: number;          // When the effect started
  readonly duration?: number;          // Duration in ms (for temporary effects)
  readonly scale?: number;             // Scale multiplier
  readonly alpha?: number;             // Alpha transparency
  readonly attachedToEntityId?: string; // If attached to an entity
  readonly offsetX?: number;           // Offset from entity position (if attached)
  readonly offsetY?: number;           // Offset from entity position (if attached)
  readonly triggerCallback?: () => void; // Callback when effect completes
  // For blood effects: positions needed for isometric layer determination
  readonly attackerPosition?: readonly [number, number]; // Position of attacker
  readonly defenderPosition?: readonly [number, number]; // Position of defender
}

export interface EffectMetadata {
  readonly name: string;
  readonly normalized_name: string;
  readonly total_frames: number;
  readonly sprite_size: {
    readonly width: number;
    readonly height: number;
  };
  readonly files: {
    readonly json: string;
    readonly png: string;
  };
}

/**
 * Helper function to get effect path
 */
export function getEffectPath(effectType: EffectType): string {
  return `/assets/effects/${effectType}.json`;
}

/**
 * Helper function to determine if an effect should loop
 */
export function shouldEffectLoop(effectType: EffectType): boolean {
  switch (effectType) {
    case EffectType.DARK_AURA:
    case EffectType.HOLY_LIGHT_AURA:
    case EffectType.BUBBLE_SHIELD:
    case EffectType.ROTATING_SHIELD:
    case EffectType.CONFUSE1:
    case EffectType.CONFUSE2:
    case EffectType.REGEN:
    case EffectType.ELECTRIC_AURA:
    case EffectType.FIRE_AURA:
    case EffectType.POISON_CLOUD:
      return true;
    default:
      return false;
  }
}

/**
 * Helper function to get effect category
 */
export function getEffectCategory(effectType: EffectType): EffectCategory {
  if (shouldEffectLoop(effectType)) {
    return EffectCategory.PERMANENT;
  }
  return EffectCategory.TEMPORARY;
}

/**
 * Helper function to get default effect duration (for temporary effects)
 */
export function getDefaultEffectDuration(effectType: EffectType): number {
  switch (effectType) {
    case EffectType.BLOOD_SPLAT:
      return 800; // 0.8 seconds
    case EffectType.SPARKS:
    case EffectType.SPLASH:
      return 600; // 0.6 seconds
    case EffectType.SMOKE_SIMPLE_1:
    case EffectType.SMOKE_SIMPLE_2:
    case EffectType.SMOKE_SIMPLE_3:
      return 1000; // 1 second
    case EffectType.ROCK_BREAK:
    case EffectType.LIGHT_SPARK:
      return 500; // 0.5 seconds
    default:
      return 1000; // 1 second default
  }
} 