import { Position, EntitySummary } from './common';
import { AnimationState, Direction, AttackMetadata } from './battlemap_types';

// Animation status lifecycle
export enum AnimationStatus {
  PENDING = 'pending',       // Queued, not started
  PLAYING = 'playing',       // Currently animating
  COMPLETED = 'completed',   // Finished successfully
  CANCELLED = 'cancelled',   // Interrupted
  ORPHAN = 'orphan',        // Client-initiated, no server confirmation
  ADOPTED = 'adopted',      // Server confirmed
  REJECTED = 'rejected'     // Server rejected
}

// Base animation event
export interface AnimationEvent {
  id: string;                          // Unique identifier
  entityId: string;                    // Entity performing animation
  type: AnimationState;                // What animation to play
  status: AnimationStatus;             // Current status
  startTime: number;                   // When animation started
  duration: number;                    // Expected duration in ms
  progress: number;                    // 0-1 progress
  
  // Server reconciliation
  serverEventId?: string;              // Link to server event
  clientInitiated: boolean;            // Was this predicted?
  
  // Animation data
  data: Record<string, any>;           // Type-specific data
}

// Specific animation event types
export interface MovementAnimationEvent extends AnimationEvent {
  type: AnimationState.WALK | AnimationState.RUN;
  data: {
    path: Position[];                  // Full movement path
    currentSegment: number;            // Current path segment
    fromPosition: Position;            // Start position
    toPosition: Position;              // End position
    direction: Direction;              // Facing direction
  };
}

export interface AttackAnimationEvent extends AnimationEvent {
  type: AnimationState.ATTACK1 | AnimationState.ATTACK2 | AnimationState.ATTACK3;
  data: {
    targetId: string;                  // Target entity
    weaponSlot: string;                // Which weapon
    metadata?: AttackMetadata;         // Server response data
    impactFrame?: number;              // When to trigger damage
    direction: Direction;              // Attack direction
  };
}

export interface DamageAnimationEvent extends AnimationEvent {
  type: AnimationState.TAKE_DAMAGE;
  data: {
    attackerId: string;                // Who caused damage
    damage: number;                    // Amount of damage
    damageType: string;                // Type of damage
    direction: Direction;              // Direction to face attacker
  };
}

// Animation lifecycle events
export const AnimationLifecycleEvents = {
  // Animation state changes
  ANIMATION_QUEUED: 'animation.queued',
  ANIMATION_STARTED: 'animation.started',
  ANIMATION_PROGRESS: 'animation.progress',
  ANIMATION_COMPLETED: 'animation.completed',
  ANIMATION_CANCELLED: 'animation.cancelled',
  
  // Server reconciliation
  ANIMATION_ORPHANED: 'animation.orphaned',
  ANIMATION_ADOPTED: 'animation.adopted',
  ANIMATION_REJECTED: 'animation.rejected',
  
  // Combat specific events
  ATTACK_STARTED: 'combat.attack.started',
  ATTACK_IMPACT_FRAME: 'combat.attack.impact',    // Key moment for damage
  ATTACK_COMPLETED: 'combat.attack.completed',
  DAMAGE_STARTED: 'combat.damage.started',
  DAMAGE_COMPLETED: 'combat.damage.completed',
  
  // Movement specific events
  MOVEMENT_STARTED: 'movement.started',
  MOVEMENT_SEGMENT_COMPLETED: 'movement.segment.completed',
  MOVEMENT_DIRECTION_CHANGE: 'movement.direction.change',
  MOVEMENT_COMPLETED: 'movement.completed',
  
  // Effect events
  EFFECT_TRIGGERED: 'effect.triggered',
  SOUND_TRIGGERED: 'sound.triggered',
  ZORDER_CHANGE_REQUESTED: 'zorder.change.requested'
} as const;

// Helper type for event data
export type AnimationEventType = MovementAnimationEvent | AttackAnimationEvent | DamageAnimationEvent;

// Store state
export interface AnimationStoreState {
  // Active animations by entity ID
  activeAnimations: Record<string, AnimationEvent>;
  
  // Queue of pending animations
  animationQueue: AnimationEvent[];
  
  // History for debugging (last 50)
  animationHistory: AnimationEvent[];
  
  // Settings
  config: {
    maxHistorySize: number;
    allowClientPrediction: boolean;
    animationSpeed: number;  // Global speed multiplier
  };
} 