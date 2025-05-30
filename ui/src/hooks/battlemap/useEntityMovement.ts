import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../store/battlemapStore';
import { EntitySummary, Position } from '../../types/common';
import { Direction } from '../../types/battlemap_types';
// NEW: Use the pure service that both React and PixiJS can share
import { EntityMovementService } from '../../game/services/EntityMovementService';

/**
 * React hook wrapper around EntityMovementService
 * Provides reactive updates while using the same pure logic as PixiJS interactions
 * 
 * This maintains the separation of concerns:
 * - battlemapStore: Server data only (actual positions, summaries)
 * - animationStore: All visual animations with proper adoption flow
 */
export const useEntityMovement = () => {
  const snap = useSnapshot(battlemapStore);
  
  /**
   * Check if a position is walkable
   */
  const isPositionWalkable = useCallback((x: number, y: number): boolean => {
    return EntityMovementService.isPositionWalkable(x, y);
  }, []);
  
  /**
   * Check if an entity can move to a position (only requires existing path in senses)
   */
  const canEntityMoveTo = useCallback((entityId: string, x: number, y: number): boolean => {
    return EntityMovementService.canEntityMoveTo(entityId, x, y);
  }, []);
  
  /**
   * Get movement path from entity senses
   */
  const getMovementPath = useCallback((entityId: string, targetPosition: Position): Position[] | null => {
    return EntityMovementService.getMovementPath(entityId, targetPosition);
  }, []);
  
  /**
   * Move entity to a new position with proper client prediction → server adoption flow
   */
  const moveEntityTo = useCallback(async (entityId: string, position: Position): Promise<EntitySummary | undefined> => {
    return EntityMovementService.moveEntityTo(entityId, position);
  }, []);
  
  /**
   * Check if entity is currently moving (check animation store)
   */
  const isEntityMoving = useCallback((entityId: string): boolean => {
    return EntityMovementService.isEntityMoving(entityId);
  }, []);
  
  /**
   * Force cancel entity movement
   */
  const cancelEntityMovement = useCallback((entityId: string) => {
    EntityMovementService.cancelEntityMovement(entityId);
  }, []);
  
  /**
   * Get entity direction from sprite mapping (fallback to server data)
   */
  const getEntityDirection = useCallback((entityId: string): Direction => {
    return EntityMovementService.getEntityDirection(entityId);
  }, []);
  
  /**
   * Set entity direction (for attacks, manual facing)
   */
  const setEntityDirection = useCallback((entityId: string, direction: Direction) => {
    EntityMovementService.setEntityDirection(entityId, direction);
  }, []);
  
  /**
   * Compute direction from one position to another
   */
  const computeDirection = useCallback((fromPos: Position, toPos: Position): Direction => {
    return EntityMovementService.computeDirection(fromPos, toPos);
  }, []);
  
  return {
    // Position queries
    isPositionWalkable,
    canEntityMoveTo,
    getMovementPath,
    
    // Movement actions (Using shared service)
    moveEntityTo,          // Main movement function with adoption flow
    cancelEntityMovement,  // Force cancel
    
    // State queries (Using shared service)
    isEntityMoving,        // Check if moving
    
    // Direction management
    getEntityDirection,
    setEntityDirection,
    
    // Utilities
    computeDirection,
  };
}; 