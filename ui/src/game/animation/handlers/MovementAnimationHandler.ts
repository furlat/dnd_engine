import { Ticker } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../../../store';
import { animationStore, animationActions, animationEventBus, AnimationLifecycleEvents } from '../../../store/animationStore';
import { 
  Direction, 
  VisualPosition, 
  toVisualPosition,
  AnimationState
} from '../../../types/battlemap_types';
import { EntitySummary, Position } from '../../../types/common';
import { computeDirection, calculateDistance } from '../../../utils/combatUtils';

/**
 * Precomputed movement data to avoid recalculation
 */
interface PrecomputedMovementData {
  directions: Direction[]; // Direction for each path segment
  distances: number[];     // Distance for each path segment
  totalDistance: number;   // Total path distance
}

/**
 * Local entity state for direction optimization - avoids store spam during movement
 */
interface LocalEntityState {
  currentDirection: Direction;
  pendingStoreDirection?: Direction; // Only set when we need to update store at the end
  lastStoreUpdateTime: number;
}

/**
 * MovementAnimationHandler with OPTIMISTIC ANIMATION + ADOPTION pattern
 * 
 * NEW PATTERN:
 * 1. Listen for 'MOVEMENT_STARTED' events → start optimistic animation
 * 2. Listen for 'MOVEMENT_ADOPTED' events → adopt server data into ongoing animation  
 * 3. Listen for 'MOVEMENT_REJECTED' events → handle rejection/rollback
 * 
 * This replaces the old direct animationStore integration
 */
export class MovementAnimationHandler {
  // Animation system integration
  private onUpdateEntityVisualPosition?: (entityId: string, visualPosition: VisualPosition) => void;
  private onUpdateSpriteDirection?: (entityId: string, direction: Direction) => void;
  private onSetLocalZOrder?: (entityId: string, zIndex: number) => void;
  private onClearLocalZOrder?: (entityId: string) => void;
  
  // Local state management (three-tier pattern)
  private localEntityStates: Map<string, LocalEntityState> = new Map();
  private precomputedMovementData: Map<string, PrecomputedMovementData> = new Map();
  private localZOrderStates: Map<string, number> = new Map();
  
  // Track movement segments to avoid redundant direction updates
  private currentMovementSegment: Map<string, number> = new Map();
  
  // Event unsubscribers
  private unsubscribers: (() => void)[] = [];
  
  /**
   * Initialize the handler and set up event listeners
   */
  initialize(callbacks: {
    onUpdateEntityVisualPosition: (entityId: string, visualPosition: VisualPosition) => void;
    onUpdateSpriteDirection: (entityId: string, direction: Direction) => void;
    onSetLocalZOrder: (entityId: string, zIndex: number) => void;
    onClearLocalZOrder: (entityId: string) => void;
  }): void {
    this.onUpdateEntityVisualPosition = callbacks.onUpdateEntityVisualPosition;
    this.onUpdateSpriteDirection = callbacks.onUpdateSpriteDirection;
    this.onSetLocalZOrder = callbacks.onSetLocalZOrder;
    this.onClearLocalZOrder = callbacks.onClearLocalZOrder;
    
    // Listen for movement events from EntityMovementService
    this.unsubscribers.push(
      animationEventBus.on('MOVEMENT_STARTED', this.handleMovementStarted.bind(this))
    );
    this.unsubscribers.push(
      animationEventBus.on('MOVEMENT_ADOPTED', this.handleMovementAdopted.bind(this))
    );
    this.unsubscribers.push(
      animationEventBus.on('MOVEMENT_REJECTED', this.handleMovementRejected.bind(this))
    );
    
    console.log('[MovementAnimationHandler] Initialized with event-driven adoption pattern');
  }
  
  /**
   * Handle MOVEMENT_STARTED event - start optimistic animation
   */
  private handleMovementStarted(data: any): void {
    const { entityId, targetPosition, optimisticPath, startTime } = data;
    
    console.log(`[MovementAnimationHandler] Starting optimistic movement for ${entityId} to [${targetPosition}]`);
    
    // FIXED: Use the optimistic path directly - it's already the full path from senses
    const fullPath = optimisticPath;
    
    // CRITICAL: Cache senses data for movement visibility
    const entity = battlemapStore.entities.summaries[entityId];
    if (entity && entity.senses) {
      console.log(`[MovementAnimationHandler] Caching senses data for ${entityId} during movement`);
      // The renderer will use this cached data during movement for visibility
    }
    
    // Create animation in animationStore with optimistic data
    const animationId = animationActions.createAnimation(
      entityId,
      AnimationState.WALK,
      fullPath.length * 500, // 500ms per tile
      {
        path: fullPath,
        currentSegment: 0,
        fromPosition: fullPath[0],
        toPosition: targetPosition,
        status: 'optimistic', // Will be updated to 'adopted' or 'rejected'
        optimisticStartTime: startTime,
        // Store senses for visibility during movement
        pathSenses: entity?.senses
      },
      true // CLIENT INITIATED
    );
    
    // Precompute movement data for smooth animation
    this.precomputeMovementData(entityId, fullPath);
    
    // Set initial direction and z-order
    const initialDirection = this.getInitialDirection(fullPath);
    this.updateLocalEntityDirection(entityId, initialDirection);
    this.setLocalZOrder(entityId, 100); // Moving entities above static ones
    
    console.log(`[MovementAnimationHandler] Started optimistic animation ${animationId} for ${entityId} with ${fullPath.length} path segments`);
  }
  
  /**
   * Handle MOVEMENT_ADOPTED event - adopt server data into ongoing animation
   * THIS IS THE CRITICAL PIECE - REAL ADOPTION
   */
  private handleMovementAdopted(data: any): void {
    const { entityId, updatedEntity, adoptionTime } = data;
    
    console.log(`[MovementAnimationHandler] ADOPTING server data for ${entityId}`);
    
    const animation = animationActions.getActiveAnimation(entityId);
    if (!animation) {
      console.warn(`[MovementAnimationHandler] No active animation to adopt for ${entityId}`);
      return;
    }
    
    // FIXED: Extract server path from path_senses structure
    // The path_senses keys ARE the path positions in sequence
    const snap = battlemapStore;
    const pathSenses = snap.entities.pathSenses[entityId];
    
    if (pathSenses && Object.keys(pathSenses).length > 0) {
      // Convert path_senses keys back to Position array
      // Keys are in format "x,y" and represent the actual path taken
      const serverPathPositions = Object.keys(pathSenses)
        .map(key => {
          const [x, y] = key.split(',').map(Number);
          return [x, y] as Position;
        })
        .sort((a, b) => {
          // Sort by distance from start position to maintain order
          const startPos = animation.data.fromPosition;
          const distA = Math.abs(a[0] - startPos[0]) + Math.abs(a[1] - startPos[1]);
          const distB = Math.abs(b[0] - startPos[0]) + Math.abs(b[1] - startPos[1]);
          return distA - distB;
        });
      
      console.log(`[MovementAnimationHandler] Server path extracted from path_senses:`, serverPathPositions);
      
      // Compare with current optimistic path
      if (JSON.stringify(serverPathPositions) !== JSON.stringify(animation.data.path)) {
        console.log(`[MovementAnimationHandler] SERVER PATH DIFFERS - adopting new path for ${entityId}`);
        console.log(`[MovementAnimationHandler] Old path:`, animation.data.path);
        console.log(`[MovementAnimationHandler] New path:`, serverPathPositions);
        
        // Update the ongoing animation with new server path
        animation.data.path = serverPathPositions;
        animation.data.status = 'adopted';
        animation.data.adoptionTime = adoptionTime;
        animation.data.serverEntity = updatedEntity;
        
        // Recompute movement data with new path
        this.precomputeMovementData(entityId, serverPathPositions);
        
        console.log(`[MovementAnimationHandler] Successfully adopted new server path for ${entityId}: ${serverPathPositions.length} segments`);
      } else {
        // Path is the same, just mark as adopted and update senses
        animation.data.status = 'adopted';
        animation.data.adoptionTime = adoptionTime;
        animation.data.serverEntity = updatedEntity;
        
        console.log(`[MovementAnimationHandler] Server path matches optimistic path for ${entityId} - marked as adopted`);
      }
    } else {
      console.warn(`[MovementAnimationHandler] No path_senses data available for adoption for ${entityId}`);
      // Just mark as adopted without path changes
      animation.data.status = 'adopted';
      animation.data.adoptionTime = adoptionTime;
      animation.data.serverEntity = updatedEntity;
    }
    
    // Update battlemap store with server data (for senses during movement)
    battlemapActions.fetchEntitySummaries();
  }
  
  /**
   * Handle MOVEMENT_REJECTED event - handle server rejection
   */
  private handleMovementRejected(data: any): void {
    const { entityId, error, rejectionTime } = data;
    
    console.log(`[MovementAnimationHandler] REJECTING movement for ${entityId}:`, error);
    
    const animation = animationActions.getActiveAnimation(entityId);
    if (!animation) {
      console.warn(`[MovementAnimationHandler] No active animation to reject for ${entityId}`);
      return;
    }
    
    // Update animation status to rejected
    const updatedData = {
      ...animation.data,
      status: 'rejected',
      rejectionTime: rejectionTime,
      rejectionReason: error
    };
    
    // Rejection will cause animation to snap back to original position
    console.log(`[MovementAnimationHandler] Movement rejected for ${entityId}, will snap back`);
  }
  
  /**
   * Precompute movement data when movement starts
   */
  private precomputeMovementData(entityId: string, path: Position[]): void {
    const directions: Direction[] = [];
    const distances: number[] = [];
    let totalDistance = 0;
    
    // Compute direction and distance for each path segment
    for (let i = 0; i < path.length - 1; i++) {
      const fromPos = path[i];
      const toPos = path[i + 1];
      
      // Compute direction (grid-based)
      const direction = computeDirection(fromPos, toPos);
      directions.push(direction);
      
      // Compute distance
      const distance = calculateDistance(fromPos, toPos);
      distances.push(distance);
      totalDistance += distance;
    }
    
    this.precomputedMovementData.set(entityId, { directions, distances, totalDistance });
    console.log(`[MovementAnimationHandler] Precomputed movement data for ${entityId}: ${directions.length} segments`);
  }
  
  /**
   * Update local direction state (immediate, no store update) - same pattern as position
   */
  private updateLocalEntityDirection(entityId: string, gridDirection: Direction): void {
    let localState = this.localEntityStates.get(entityId);
    if (!localState) {
      localState = {
        currentDirection: gridDirection,
        lastStoreUpdateTime: 0
      };
      this.localEntityStates.set(entityId, localState);
    }
    
    // OPTIMIZED: Only update if direction actually changed
    if (localState.currentDirection === gridDirection) {
      return; // No change needed
    }
    
    console.log(`[MovementAnimationHandler] updateLocalDirection for ${entityId}: ${localState.currentDirection} -> ${gridDirection}`);
    
    // Update local direction immediately (store grid direction, not isometric)
    localState.currentDirection = gridDirection;
    
    // Mark for store update at the end (same pattern as position)
    localState.pendingStoreDirection = gridDirection;
    
    // Update sprite direction immediately for smooth animation via callback
    this.onUpdateSpriteDirection?.(entityId, gridDirection);
  }
  
  /**
   * NEW: Set local z-order for an entity (immediate, no store update)
   */
  private setLocalZOrder(entityId: string, zIndex: number): void {
    const currentZOrder = this.localZOrderStates.get(entityId);
    if (currentZOrder !== zIndex) {
      this.localZOrderStates.set(entityId, zIndex);
      console.log(`[MovementAnimationHandler] Set local z-order for ${entityId}: ${zIndex}`);
      // Trigger container re-ordering via callback
      this.onSetLocalZOrder?.(entityId, zIndex);
    }
  }
  
  /**
   * NEW: Clear local z-order for an entity
   */
  private clearLocalZOrder(entityId: string): void {
    if (this.localZOrderStates.has(entityId)) {
      this.localZOrderStates.delete(entityId);
      console.log(`[MovementAnimationHandler] Cleared local z-order for entity ${entityId}`);
      // Trigger container re-ordering via callback
      this.onClearLocalZOrder?.(entityId);
    }
  }
  
  /**
   * Public method to clear local direction state for an entity
   * Called by InteractionsManager before setting attack direction
   */
  clearLocalDirectionState(entityId: string): void {
    if (this.localEntityStates.has(entityId)) {
      this.localEntityStates.delete(entityId);
      console.log(`[MovementAnimationHandler] Cleared local direction state for entity ${entityId}`);
    }
  }
  
  /**
   * Get current local z-order state (for renderer integration)
   */
  getLocalZOrderStates(): Map<string, number> {
    return new Map(this.localZOrderStates);
  }
  
  /**
   * Get current direction for an entity (for renderer integration)
   * Returns local direction if entity is moving, otherwise falls back to store
   */
  getCurrentDirection(entityId: string): Direction | undefined {
    const localState = this.localEntityStates.get(entityId);
    if (localState) {
      // Entity has local direction state (is moving)
      return localState.currentDirection;
    }
    
    // No local state - entity is not moving, renderer should use store direction
    return undefined;
  }
  
  /**
   * Get initial direction from path
   */
  private getInitialDirection(path: Position[]): Direction {
    if (path.length < 2) return Direction.S;
    return computeDirection(path[0], path[1]);
  }
  
  /**
   * CRITICAL: Update all movement animations frame-by-frame
   * This is the missing piece that makes entities actually move smoothly
   */
  updateAnimations(deltaTime: number): void {
    // Get all active movement animations
    const activeAnimations = Object.values(animationStore.activeAnimations);
    
    console.log(`[MovementAnimationHandler] updateAnimations called - ${activeAnimations.length} total animations`);
    
    // FIXED: Process movement animations with ORPHAN or PLAYING status
    // Client-initiated movements start as ORPHAN and should still animate
    const movementAnimations = activeAnimations.filter(animation => 
      (animation.type === AnimationState.WALK || animation.type === AnimationState.RUN) &&
      (animation.status === 'orphan' || animation.status === 'playing' || animation.status === 'adopted')
    );
    
    console.log(`[MovementAnimationHandler] Found ${movementAnimations.length} movement animations:`, 
      movementAnimations.map(a => `${a.entityId}: ${a.type}, status: ${a.status}`));
    
    if (movementAnimations.length === 0) {
      // No movement animations to update - don't interfere with idle sprites
      return;
    }
    
    movementAnimations.forEach(animation => {
      console.log(`[MovementAnimationHandler] Processing animation for ${animation.entityId}: ${animation.type}, status: ${animation.status}`);
      this.updateMovementAnimation(animation, deltaTime);
    });
  }
  
  /**
   * Update a single movement animation
   */
  private updateMovementAnimation(animation: any, deltaTime: number): void {
    const { entityId, data } = animation;
    console.log(`[MovementAnimationHandler] updateMovementAnimation START for ${entityId}:`, { data, entityId });

    const { path, currentSegment } = data;
    console.log(`[MovementAnimationHandler] Animation data for ${entityId}:`, { path, currentSegment, pathLength: path?.length });

    // FIXED: Handle path validation properly
    if (!path || path.length === 0) {
      console.warn(`[MovementAnimationHandler] No path data for ${entityId} - completing animation`);
      animationActions.completeAnimation(entityId);
      return;
    }

    // FIXED: Handle single-position path (entity already at target)
    if (path.length === 1) {
      console.log(`[MovementAnimationHandler] Single-position path for ${entityId} - entity already at target, completing immediately`);
      
      // Sync to the single position and complete
      const finalPosition = path[0];
      const finalVisualPosition = toVisualPosition(finalPosition);
      
      // Update visual position
      this.onUpdateEntityVisualPosition?.(entityId, finalVisualPosition);
      
      // Sync back to server state
      battlemapActions.resyncEntityPosition(entityId);
      
      // Clear local states
      this.localEntityStates.delete(entityId);
      this.precomputedMovementData.delete(entityId);
      this.clearLocalZOrder(entityId);
      
      // Complete the animation
      animationActions.completeAnimation(entityId);
      return;
    }

    // Normal multi-position path animation
    // Calculate animation progress (0.0 to 1.0)
    const elapsed = Date.now() - animation.startTime;
    const progress = Math.min(elapsed / animation.duration, 1.0);

    console.log(`[MovementAnimationHandler] Animation progress for ${entityId}: ${Math.round(progress * 100)}% (${elapsed}ms/${animation.duration}ms)`);

    // Calculate current position along the path
    const pathProgress = progress * (path.length - 1);
    const segmentIndex = Math.floor(pathProgress);
    const segmentProgress = pathProgress - segmentIndex;

    console.log(`[MovementAnimationHandler] Path calculation for ${entityId}: pathProgress=${pathProgress.toFixed(2)}, segmentIndex=${segmentIndex}, segmentProgress=${segmentProgress.toFixed(2)}`);

    // Ensure we don't go past the end of the path
    if (segmentIndex >= path.length - 1) {
      // Animation complete - snap to final position
      const finalPosition = path[path.length - 1];
      const finalVisualPosition = toVisualPosition(finalPosition);

      console.log(`[MovementAnimationHandler] Animation COMPLETE for ${entityId} - final position:`, finalPosition);

      // FIXED: Only use callback system like attack animations - no store conflicts
      this.onUpdateEntityVisualPosition?.(entityId, finalVisualPosition);

      // CRITICAL: Sync back to server state on completion
      console.log(`[MovementAnimationHandler] Movement completed for ${entityId} - syncing to server state`);

      // CRITICAL: Sync final direction back to store before clearing local state
      const localState = this.localEntityStates.get(entityId);
      if (localState && localState.currentDirection) {
        console.log(`[MovementAnimationHandler] Syncing final direction for ${entityId}: ${localState.currentDirection}`);
        this.onUpdateSpriteDirection?.(entityId, localState.currentDirection);
        // CRITICAL: Must sync direction to store since server doesn't send final direction  
        // Without this, direction becomes undefined and sprite rendering breaks
        battlemapActions.setEntityDirectionFromMapping(entityId, localState.currentDirection);
      }

      // CRITICAL: Sync final position back to server position when animation completes
      // This ensures the entity doesn't get stuck at the visual position
      battlemapActions.resyncEntityPosition(entityId);
      console.log(`[MovementAnimationHandler] Resynced ${entityId} to server position`);

      // NEW: Update senses after movement completion to ensure proper visibility
      // This ensures the entity has correct senses data at the final position
      const entity = battlemapStore.entities.summaries[entityId];
      if (entity) {
        // Trigger a senses refresh for the entity at its new position
        console.log(`[MovementAnimationHandler] Triggering senses update for ${entityId} at final position`);
        import('../../../api/battlemap/battlemapApi').then(({ updateEntitySenses }) => {
          updateEntitySenses(entityId).catch(error => {
            console.warn(`[MovementAnimationHandler] Failed to update senses for ${entityId}:`, error);
          });
        });
      }

      // Clear local states AFTER syncing direction and position
      this.localEntityStates.delete(entityId);
      this.precomputedMovementData.delete(entityId);
      this.clearLocalZOrder(entityId);

      // Complete the animation - let the system handle final position sync
      animationActions.completeAnimation(entityId);
      return;
    }

    // Get current segment positions
    const fromPos = path[segmentIndex];
    const toPos = path[segmentIndex + 1];

    console.log(`[MovementAnimationHandler] Current segment for ${entityId}: ${segmentIndex}->${segmentIndex + 1}, from [${fromPos}] to [${toPos}]`);

    // Interpolate between current segment positions
    const currentX = fromPos[0] + (toPos[0] - fromPos[0]) * segmentProgress;
    const currentY = fromPos[1] + (toPos[1] - fromPos[1]) * segmentProgress;

    const currentVisualPosition: VisualPosition = { x: currentX, y: currentY };

    // FIXED: Only use callback system like attack animations - avoid store conflicts
    console.log(`[MovementAnimationHandler] Updated ${entityId} movement: segment ${segmentIndex}->${segmentIndex + 1}, progress ${Math.round(segmentProgress * 100)}%, pos (${currentX.toFixed(2)}, ${currentY.toFixed(2)})`);

    // ONLY use callback - no direct store updates during animation
    this.onUpdateEntityVisualPosition?.(entityId, currentVisualPosition);

    // NEW: Update sprite mapping visual position for dynamic senses during movement
    // This allows SensesCalculationUtils to detect the current animated position
    // and lookup the correct path_senses data for dynamic visibility
    battlemapActions.updateEntityVisualPosition(entityId, currentVisualPosition);

    // Update direction if moving to new segment
    if (segmentProgress < 0.1 || this.currentMovementSegment.get(entityId) !== segmentIndex) {
      this.currentMovementSegment.set(entityId, segmentIndex);
      const direction = computeDirection(fromPos, toPos);
      this.updateLocalEntityDirection(entityId, direction);
    }
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    // Unsubscribe from all events
    this.unsubscribers.forEach(unsubscribe => unsubscribe());
    this.unsubscribers = [];

    this.localEntityStates.clear();
    this.precomputedMovementData.clear();
    this.localZOrderStates.clear();

    console.log('[MovementAnimationHandler] Destroyed');
  }
}