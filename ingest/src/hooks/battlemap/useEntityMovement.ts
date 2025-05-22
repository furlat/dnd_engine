import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { moveEntity } from '../../api/battlemap/battlemapApi';
import { EntitySummary, Position } from '../../types/common';
import { Direction } from '../../components/battlemap/DirectionalEntitySprite';

/**
 * Hook for entity movement operations
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
   * Check if an entity can move to a position
   */
  const canEntityMoveTo = useCallback((entityId: string, x: number, y: number): boolean => {
    // Get the entity
    const entity = snap.entities.summaries[entityId];
    if (!entity) return false;
    
    // First check if the position is walkable
    if (!isPositionWalkable(x, y)) return false;
    
    // If movement highlighting is enabled, check if the position is within range
    if (snap.controls.isMovementHighlightEnabled) {
      const posKey = `${x},${y}`;
      // Check if path exists and is within 6 steps (30ft)
      return entity.senses.paths[posKey] && entity.senses.paths[posKey].length <= 6;
    }
    
    // If movement highlighting is disabled, any walkable position is valid
    return true;
  }, [snap.entities.summaries, snap.controls.isMovementHighlightEnabled, isPositionWalkable]);
  
  /**
   * Move entity to a new position
   */
  const moveEntityTo = useCallback(async (entityId: string, position: Position): Promise<EntitySummary | undefined> => {
    try {
      battlemapActions.setLoading(true);
      
      // Check if position is valid
      if (!isPositionWalkable(position[0], position[1])) {
        return undefined;
      }
      
      // If movement highlighting is enabled, check if within range
      if (snap.controls.isMovementHighlightEnabled) {
        const entity = snap.entities.summaries[entityId];
        if (!entity) return undefined;
        
        const posKey = `${position[0]},${position[1]}`;
        if (!entity.senses.paths[posKey] || entity.senses.paths[posKey].length > 6) {
          return undefined;
        }
      }
      
      // Compute the direction based on the movement
      const entity = snap.entities.summaries[entityId];
      if (entity) {
        const direction = computeDirection(
          entity.position,
          position
        );
        battlemapActions.setEntityDirection(entityId, direction);
      }
      
      // Execute the move
      const updatedEntity = await moveEntity(entityId, position);
      
      // Refresh entities
      await battlemapActions.fetchEntitySummaries();
      
      return updatedEntity;
    } catch (error) {
      console.error('Error moving entity:', error);
      battlemapActions.setError(error instanceof Error ? error.message : 'Failed to move entity');
      return undefined;
    } finally {
      battlemapActions.setLoading(false);
    }
  }, [snap.entities.summaries, snap.controls.isMovementHighlightEnabled, isPositionWalkable]);
  
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
   * Get the direction of an entity
   */
  const getEntityDirection = useCallback((entityId: string): Direction => {
    return snap.entities.directions[entityId] || Direction.S;
  }, [snap.entities.directions]);
  
  /**
   * Set the direction of an entity
   */
  const setEntityDirection = useCallback((entityId: string, direction: Direction) => {
    battlemapActions.setEntityDirection(entityId, direction);
  }, []);
  
  return {
    // Methods
    isPositionWalkable,
    canEntityMoveTo,
    moveEntityTo,
    computeDirection,
    getEntityDirection,
    setEntityDirection
  };
}; 