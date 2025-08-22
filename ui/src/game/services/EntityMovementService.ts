import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { animationActions } from '../../store/animationStore';
import { animationEventBus } from '../animation/AnimationEventBus';
import { moveEntity } from '../../api/battlemap/battlemapApi';
import { EntitySummary, Position } from '../../types/common';
import { Direction, AnimationState } from '../../types/battlemap_types';

/**
 * Pure EntityMovementService - No React, no PixiJS, just movement logic
 * Used by both useEntityMovement hook and IsometricInteractionsManager
 * 
 * Implements OPTIMISTIC ANIMATION with ADOPTION pattern:
 * 1. Start animation immediately with local senses data
 * 2. Make API call in parallel
 * 3. When server responds, ADOPT real data into ongoing animation
 * 4. All communication via AnimationEventBus events
 */
export class EntityMovementService {
  
  /**
   * Check if a position is walkable
   */
  static isPositionWalkable(x: number, y: number): boolean {
    const snap = battlemapStore;
    const posKey = `${x},${y}`;
    return snap.grid.tiles[posKey]?.walkable ?? false;
  }
  
  /**
   * Check if an entity can move to a position (only requires existing path in senses)
   */
  static canEntityMoveTo(entityId: string, x: number, y: number): boolean {
    const snap = battlemapStore;
    const entity = snap.entities.summaries[entityId];
    if (!entity) return false;
    
    const posKey = `${x},${y}`;
    // Only requirement: path must exist in senses (no movement cost restrictions)
    return !!entity.senses.paths[posKey];
  }
  
  /**
   * Get movement path from entity senses
   */
  static getMovementPath(entityId: string, targetPosition: Position): Position[] | null {
    const snap = battlemapStore;
    const entity = snap.entities.summaries[entityId];
    if (!entity) return null;
    
    const posKey = `${targetPosition[0]},${targetPosition[1]}`;
    const path = entity.senses.paths[posKey];
    
    if (!path || path.length === 0) return null;
    
    // Return full path including current position
    return [entity.position, ...path];
  }
  
  /**
   * Check if entity is currently moving (check animation store)
   */
  static isEntityMoving(entityId: string): boolean {
    const animation = animationActions.getActiveAnimation(entityId);
    return animation?.type === AnimationState.WALK || animation?.type === AnimationState.RUN;
  }
  
  /**
   * Start movement with optimistic animation + adoption pattern
   */
  static async moveEntityTo(entityId: string, targetPosition: Position): Promise<boolean> {
    const entity = battlemapStore.entities.summaries[entityId];
    if (!entity) {
      console.warn(`[EntityMovementService] Entity ${entityId} not found`);
      return false;
    }

    // Check if entity is ready for movement
    const existingAnimation = animationActions.getActiveAnimation(entityId);
    if (existingAnimation) {
      console.log(`[EntityMovementService] Entity ${entity.name} is already animating, ignoring new movement`);
      return false;
    }

    console.log(`[EntityMovementService] Starting optimistic movement for ${entity.name} to [${targetPosition}]`);

    // STEP 1: Get the stored path (this is the FULL path from current to target)
    const storedPath = entity.senses.paths[`${targetPosition[0]},${targetPosition[1]}`];
    if (!storedPath || storedPath.length === 0) {
      console.warn(`[EntityMovementService] No path found in senses for ${entity.name} to [${targetPosition}]`);
      return false;
    }

    // STEP 2: Fire event to start optimistic animation with the full stored path
    animationEventBus.emit('MOVEMENT_STARTED', {
      entityId: entityId,
      targetPosition: targetPosition,
      optimisticPath: storedPath, // This is already the full path
      startTime: Date.now(),
      status: 'optimistic' // Will become 'adopted' or 'rejected' based on server response
    });

    // STEP 3: Make API call in parallel (don't await - this is the key!)
    moveEntity(entityId, targetPosition, true) // includePathSenses = true
      .then((updatedEntity: EntitySummary) => {
        console.log(`[EntityMovementService] Server approved movement for ${entity.name}`);
        
        // Fire adoption event with server data
        animationEventBus.emit('MOVEMENT_ADOPTED', {
          entityId: entityId,
          updatedEntity: updatedEntity,
          serverApproved: true,
          adoptionTime: Date.now()
        });
      })
      .catch((error: any) => {
        console.error(`[EntityMovementService] Server rejected movement for ${entity.name}:`, error);
        
        // Fire rejection event
        animationEventBus.emit('MOVEMENT_REJECTED', {
          entityId: entityId,
          error: error,
          rejectionTime: Date.now()
        });
      });

    // STEP 4: Return immediately - animation is already started optimistically
    return true;
  }
  
  /**
   * Check if entity is ready for movement input
   */
  static isEntityReadyForInput(entityId: string): boolean {
    // Entity is ready if not currently animating
    const isAnimating = !!animationActions.getActiveAnimation(entityId);
    return !isAnimating;
  }
  
  /**
   * Force cancel entity movement
   */
  static cancelEntityMovement(entityId: string): void {
    console.log(`[EntityMovementService] Cancelling movement for entity ${entityId}`);
    
    // Remove from animation store
    animationActions.completeAnimation(entityId);
    
    // Resync position to server
    battlemapActions.resyncEntityPosition(entityId);
  }
  
  /**
   * Get entity direction from sprite mapping (fallback to server data)
   */
  static getEntityDirection(entityId: string): Direction {
    const spriteMapping = battlemapStore.entities.spriteMappings[entityId];
    if (spriteMapping) {
      return spriteMapping.currentDirection;
    }
    
    // Fallback to stored direction
    return battlemapStore.entities.directions[entityId] || Direction.S;
  }
  
  /**
   * Set entity direction (for attacks, manual facing)
   */
  static setEntityDirection(entityId: string, direction: Direction): void {
    console.log(`[EntityMovementService] Setting direction for ${entityId}: ${direction}`);
    
    // Update sprite mapping direction
    battlemapActions.setEntityDirectionFromMapping(entityId, direction);
    
    // Also update stored direction
    battlemapActions.setEntityDirection(entityId, direction);
  }
  
  /**
   * Compute direction between two positions
   */
  static computeDirection(fromPos: Position, toPos: Position): Direction {
    const [fromX, fromY] = fromPos;
    const [toX, toY] = toPos;
    
    const dx = toX - fromX;
    const dy = toY - fromY;
    
    if (dx > 0 && dy > 0) return Direction.SE;
    if (dx > 0 && dy < 0) return Direction.NE;
    if (dx < 0 && dy > 0) return Direction.SW;
    if (dx < 0 && dy < 0) return Direction.NW;
    if (dx === 0 && dy > 0) return Direction.S;
    if (dx === 0 && dy < 0) return Direction.N;
    if (dx > 0 && dy === 0) return Direction.E;
    if (dx < 0 && dy === 0) return Direction.W;
    
    return Direction.S; // Default
  }
  
  /**
   * Start attack with optimistic animation + adoption pattern
   */
  static async executeAttack(attackerId: string, targetId: string): Promise<boolean> {
    // TODO: Implement similar optimistic + adoption pattern for attacks
    // 1. Fire 'ATTACK_STARTED' event with optimistic data
    // 2. Make API call in parallel
    // 3. Fire 'ATTACK_ADOPTED' or 'ATTACK_REJECTED' based on response
    console.log(`[EntityMovementService] Attack system not yet implemented with adoption pattern`);
    return false;
  }
} 