import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { moveEntity } from '../../api/battlemap/battlemapApi';
import { EntitySummary, Position } from '../../types/common';
import { Direction, MovementAnimation, MovementState, AnimationState, toVisualPosition } from '../../types/battlemap_types';

/**
 * Hook for entity movement operations with decoupled animation/position system
 */
export const useEntityMovement = () => {
  const snap = useSnapshot(battlemapStore);
  
  /**
   * Check if a position is walkable
   */
  const isPositionWalkable = useCallback((x: number, y: number): boolean => {
    const posKey = `${x},${y}`;
    return snap.grid.tiles[posKey]?.walkable ?? false;
  }, [snap.grid.tiles]);
  
  /**
   * Check if an entity can move to a position (only requires existing path in senses)
   */
  const canEntityMoveTo = useCallback((entityId: string, x: number, y: number): boolean => {
    const entity = snap.entities.summaries[entityId];
    if (!entity) return false;
    
    const posKey = `${x},${y}`;
    // Only requirement: path must exist in senses (no movement cost restrictions)
    return !!entity.senses.paths[posKey];
  }, [snap.entities.summaries]);
  
  /**
   * Get movement path from entity senses
   */
  const getMovementPath = useCallback((entityId: string, targetPosition: Position): Position[] | null => {
    const entity = snap.entities.summaries[entityId];
    if (!entity) return null;
    
    const posKey = `${targetPosition[0]},${targetPosition[1]}`;
    const path = entity.senses.paths[posKey];
    
    if (!path || path.length === 0) return null;
    
    // Return full path including current position
    return [entity.position, ...path];
  }, [snap.entities.summaries]);
  
  /**
   * Start visual movement animation for entity
   */
  const startEntityMovement = useCallback((entityId: string, targetPosition: Position): boolean => {
    const entity = snap.entities.summaries[entityId];
    if (!entity) return false;
    
    // Get path from senses
    const path = getMovementPath(entityId, targetPosition);
    if (!path) return false;
    
    // Check if entity is already moving
    const existingMovement = snap.entities.movementAnimations[entityId];
    if (existingMovement) {
      console.log(`[useEntityMovement] Entity ${entity.name} is already moving, ignoring new movement`);
      return false;
    }
    
    // Get movement speed from sprite mapping (use animation duration as movement speed)
    const spriteMapping = snap.entities.spriteMappings[entityId];
    const movementSpeed = spriteMapping?.animationDurationSeconds ? (1.0 / spriteMapping.animationDurationSeconds) : 1.0; // tiles per second
    
    // Create movement animation
    const movementAnimation: MovementAnimation = {
      entityId,
      path,
      currentPathIndex: 0,
      startTime: Date.now(),
      movementSpeed,
      targetPosition,
      isServerApproved: undefined, // Will be set when server responds
    };
    
    console.log(`[useEntityMovement] Starting movement for ${entity.name} to ${targetPosition} with ${path.length} waypoints at ${movementSpeed} tiles/sec`);
    
    // Start movement in store
    battlemapActions.startEntityMovement(entityId, movementAnimation);
    
    return true;
  }, [snap.entities.summaries, snap.entities.movementAnimations, snap.entities.spriteMappings, getMovementPath]);
  
  /**
   * Move entity to a new position (triggers visual movement + server call)
   */
  const moveEntityTo = useCallback(async (entityId: string, position: Position): Promise<EntitySummary | undefined> => {
    const entity = snap.entities.summaries[entityId];
    if (!entity) return undefined;
    
    console.log(`[useEntityMovement] Moving entity ${entity.name} to position ${position}`);
    
    // Start visual movement immediately
    const movementStarted = startEntityMovement(entityId, position);
    if (!movementStarted) {
      console.warn(`[useEntityMovement] Could not start movement for ${entity.name}`);
      return undefined;
    }
    
    // Compute and update direction based on first movement step
    const path = getMovementPath(entityId, position);
    if (path && path.length > 1) {
      const direction = computeDirection(path[0], path[1]);
      battlemapActions.setEntityDirectionFromMapping(entityId, direction);
    }
    
    try {
      // Send movement to server (don't wait for response to start animation)
      const updatedEntity = await moveEntity(entityId, position);
      
      // Mark movement as server-approved
      battlemapActions.updateEntityMovementAnimation(entityId, { isServerApproved: true });
      
      // Refresh entities to get updated server state
      await battlemapActions.fetchEntitySummaries();
      
      console.log(`[useEntityMovement] Server approved movement for ${entity.name}`);
      return updatedEntity;
    } catch (error) {
      console.error(`[useEntityMovement] Server rejected movement for ${entity.name}:`, error);
      
      // Mark movement as server-rejected
      battlemapActions.updateEntityMovementAnimation(entityId, { isServerApproved: false });
      
      // Movement animation will continue and then snap back on completion
      return undefined;
    }
  }, [snap.entities.summaries, startEntityMovement, getMovementPath]);
  
  /**
   * Compute direction from one position to another
   */
  const computeDirection = useCallback((fromPos: Position, toPos: Position): Direction => {
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
  }, []);
  
  /**
   * Get the current movement state of an entity
   */
  const getEntityMovementState = useCallback((entityId: string): MovementState => {
    const spriteMapping = snap.entities.spriteMappings[entityId];
    return spriteMapping?.movementState || MovementState.IDLE;
  }, [snap.entities.spriteMappings]);
  
  /**
   * Check if entity is currently moving
   */
  const isEntityMoving = useCallback((entityId: string): boolean => {
    return getEntityMovementState(entityId) === MovementState.MOVING;
  }, [getEntityMovementState]);
  
  /**
   * Check if entity's visual position is synced with server position
   */
  const isEntityPositionSynced = useCallback((entityId: string): boolean => {
    const spriteMapping = snap.entities.spriteMappings[entityId];
    return spriteMapping?.isPositionSynced ?? true;
  }, [snap.entities.spriteMappings]);
  
  /**
   * Force resync entity position with server
   */
  const resyncEntityPosition = useCallback((entityId: string) => {
    console.log(`[useEntityMovement] Force resyncing position for entity ${entityId}`);
    battlemapActions.resyncEntityPosition(entityId);
  }, []);
  
  /**
   * Get the direction of an entity
   */
  const getEntityDirection = useCallback((entityId: string): Direction => {
    const spriteMapping = snap.entities.spriteMappings[entityId];
    return spriteMapping?.currentDirection || Direction.S;
  }, [snap.entities.spriteMappings]);
  
  /**
   * Set the direction of an entity
   */
  const setEntityDirection = useCallback((entityId: string, direction: Direction) => {
    battlemapActions.setEntityDirectionFromMapping(entityId, direction);
  }, []);
  
  return {
    // Position queries
    isPositionWalkable,
    canEntityMoveTo,
    getMovementPath,
    
    // Movement actions
    moveEntityTo,
    startEntityMovement,
    computeDirection,
    
    // State queries
    getEntityMovementState,
    isEntityMoving,
    isEntityPositionSynced,
    
    // Direction management
    getEntityDirection,
    setEntityDirection,
    
    // Utility actions
    resyncEntityPosition,
  };
}; 