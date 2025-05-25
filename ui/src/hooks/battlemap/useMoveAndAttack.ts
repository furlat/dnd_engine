import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { executeAttack } from '../../api/battlemap/battlemapApi';
import { EntitySummary, Position } from '../../types/common';
import { Direction, AnimationState } from '../../types/battlemap_types';
import { useEntityMovement } from './useEntityMovement';

/**
 * Hook for combined move-and-attack operations
 */
export const useMoveAndAttack = () => {
  const snap = useSnapshot(battlemapStore);
  const { moveEntityTo, canEntityMoveTo, getMovementPath } = useEntityMovement();
  
  /**
   * Find the nearest adjacent cell to a target that the entity can move to
   */
  const findNearestAttackPosition = useCallback((entityId: string, targetPosition: Position): Position | null => {
    const entity = snap.entities.summaries[entityId];
    if (!entity) return null;
    
    const [targetX, targetY] = targetPosition;
    
    // Check all 8 adjacent positions around the target
    const adjacentPositions: Position[] = [
      [targetX - 1, targetY - 1], // NW
      [targetX, targetY - 1],     // N
      [targetX + 1, targetY - 1], // NE
      [targetX + 1, targetY],     // E
      [targetX + 1, targetY + 1], // SE
      [targetX, targetY + 1],     // S
      [targetX - 1, targetY + 1], // SW
      [targetX - 1, targetY]      // W
    ];
    
    // Filter positions that the entity can move to
    const validPositions = adjacentPositions.filter(pos => 
      canEntityMoveTo(entityId, pos[0], pos[1])
    );
    
    if (validPositions.length === 0) return null;
    
    // Find the position with the shortest path
    let bestPosition: Position | null = null;
    let shortestPathLength = Infinity;
    
    for (const position of validPositions) {
      const path = getMovementPath(entityId, position);
      if (path && path.length < shortestPathLength) {
        shortestPathLength = path.length;
        bestPosition = position;
      }
    }
    
    return bestPosition;
  }, [snap.entities.summaries, canEntityMoveTo, getMovementPath]);
  
  /**
   * Check if an entity is adjacent to a target position
   */
  const isAdjacentToTarget = useCallback((entityPosition: Position, targetPosition: Position): boolean => {
    const [entityX, entityY] = entityPosition;
    const [targetX, targetY] = targetPosition;
    
    const dx = Math.abs(entityX - targetX);
    const dy = Math.abs(entityY - targetY);
    
    // Adjacent means within 1 tile in any direction (including diagonals)
    return dx <= 1 && dy <= 1 && (dx > 0 || dy > 0);
  }, []);
  
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
   * Execute an attack on a target entity
   */
  const executeEntityAttack = useCallback(async (
    attackerId: string, 
    targetId: string, 
    weaponSlot: 'MAIN_HAND' | 'OFF_HAND' = 'MAIN_HAND'
  ): Promise<boolean> => {
    const attacker = snap.entities.summaries[attackerId];
    const target = snap.entities.summaries[targetId];
    
    if (!attacker || !target) {
      console.warn('[useMoveAndAttack] Attacker or target not found');
      return false;
    }
    
    console.log(`[useMoveAndAttack] ${attacker.name} attacking ${target.name} with ${weaponSlot}`);
    
    try {
      // IMMEDIATELY mark entity as out-of-sync to block further inputs
      const spriteMapping = snap.entities.spriteMappings[attackerId];
      if (spriteMapping) {
        battlemapActions.updateEntityVisualPosition(attackerId, spriteMapping.visualPosition || { x: attacker.position[0], y: attacker.position[1] });
      }
      
      // Set direction to face the target before attacking
      const direction = computeDirection(attacker.position, target.position);
      battlemapActions.setEntityDirectionFromMapping(attackerId, direction);
      
      // Trigger attack animation
      battlemapActions.setEntityAnimation(attackerId, AnimationState.ATTACK1);
      
      // Execute the attack
      const attackResult = await executeAttack(attackerId, targetId, weaponSlot);
      
      console.log(`[useMoveAndAttack] Attack successful:`, attackResult);
      
      // Refresh entity summaries to get updated health/status
      await battlemapActions.fetchEntitySummaries();
      
      return true;
    } catch (error) {
      console.error(`[useMoveAndAttack] Attack failed:`, error);
      
      // Return to idle animation on failure
      const spriteMapping = snap.entities.spriteMappings[attackerId];
      if (spriteMapping) {
        battlemapActions.setEntityAnimation(attackerId, spriteMapping.idleAnimation);
      }
      
      return false;
    }
  }, [snap.entities.summaries, snap.entities.spriteMappings, computeDirection]);
  
  /**
   * Move to attack range and then attack a target
   */
  const moveAndAttack = useCallback(async (
    attackerId: string, 
    targetId: string, 
    weaponSlot: 'MAIN_HAND' | 'OFF_HAND' = 'MAIN_HAND'
  ): Promise<boolean> => {
    const attacker = snap.entities.summaries[attackerId];
    const target = snap.entities.summaries[targetId];
    
    if (!attacker || !target) {
      console.warn('[useMoveAndAttack] Attacker or target not found');
      return false;
    }
    
    console.log(`[useMoveAndAttack] ${attacker.name} attempting move-and-attack on ${target.name}`);
    
    // Check if already adjacent to target
    if (isAdjacentToTarget(attacker.position, target.position)) {
      console.log(`[useMoveAndAttack] ${attacker.name} is already adjacent to ${target.name}, attacking directly`);
      return await executeEntityAttack(attackerId, targetId, weaponSlot);
    }
    
    // Find the nearest attack position
    const attackPosition = findNearestAttackPosition(attackerId, target.position);
    if (!attackPosition) {
      console.warn(`[useMoveAndAttack] No valid attack position found for ${attacker.name} to reach ${target.name}`);
      return false;
    }
    
    console.log(`[useMoveAndAttack] ${attacker.name} moving to attack position ${attackPosition} to reach ${target.name}`);
    
    try {
      // Move to attack position
      const moveResult = await moveEntityTo(attackerId, attackPosition);
      if (!moveResult) {
        console.warn(`[useMoveAndAttack] Movement failed for ${attacker.name}`);
        return false;
      }
      
      // Set up a listener for when movement completes
      const checkMovementComplete = () => {
        const currentMovement = battlemapStore.entities.movementAnimations[attackerId];
        const spriteMapping = battlemapStore.entities.spriteMappings[attackerId];
        
        // Check if movement is complete (no active movement and back to idle)
        if (!currentMovement && spriteMapping?.movementState === 'idle') {
          console.log(`[useMoveAndAttack] Movement completed for ${attacker.name}, executing attack`);
          
          // Execute the attack after movement completes
          executeEntityAttack(attackerId, targetId, weaponSlot);
          
          // Stop checking
          clearInterval(movementCheckInterval);
        }
      };
      
      // Check every 100ms for movement completion
      const movementCheckInterval = setInterval(checkMovementComplete, 100);
      
      // Safety timeout - stop checking after 10 seconds
      setTimeout(() => {
        clearInterval(movementCheckInterval);
        console.warn(`[useMoveAndAttack] Movement timeout for ${attacker.name}, attack cancelled`);
      }, 10000);
      
      return true;
    } catch (error) {
      console.error(`[useMoveAndAttack] Move-and-attack failed:`, error);
      return false;
    }
  }, [snap.entities.summaries, isAdjacentToTarget, findNearestAttackPosition, moveEntityTo, executeEntityAttack]);
  
  /**
   * Attack a target directly (must be adjacent)
   */
  const attackTarget = useCallback(async (
    attackerId: string, 
    targetId: string, 
    weaponSlot: 'MAIN_HAND' | 'OFF_HAND' = 'MAIN_HAND'
  ): Promise<boolean> => {
    const attacker = snap.entities.summaries[attackerId];
    const target = snap.entities.summaries[targetId];
    
    if (!attacker || !target) {
      console.warn('[useMoveAndAttack] Attacker or target not found');
      return false;
    }
    
    // Check if adjacent
    if (!isAdjacentToTarget(attacker.position, target.position)) {
      console.warn(`[useMoveAndAttack] ${attacker.name} is not adjacent to ${target.name} for direct attack`);
      return false;
    }
    
    return await executeEntityAttack(attackerId, targetId, weaponSlot);
  }, [snap.entities.summaries, isAdjacentToTarget, executeEntityAttack]);
  
  return {
    // Position queries
    findNearestAttackPosition,
    isAdjacentToTarget,
    computeDirection,
    
    // Attack actions
    executeEntityAttack,
    moveAndAttack,
    attackTarget,
  };
}; 