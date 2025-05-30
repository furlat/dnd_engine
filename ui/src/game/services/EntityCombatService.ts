import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { animationActions } from '../../store/animationStore';
import { animationEventBus } from '../animation/AnimationEventBus';
import { executeAttack } from '../../api/battlemap/battlemapApi';
import { EntitySummary, Position } from '../../types/common';
import { Direction, AnimationState } from '../../types/battlemap_types';

/**
 * Pure EntityCombatService - No React, no PixiJS, just combat logic
 * Used by IsometricInteractionsManager
 * 
 * Implements OPTIMISTIC ANIMATION with ADOPTION pattern:
 * 1. Start attack animation immediately
 * 2. Make API call in parallel
 * 3. When server responds, process combat results via handlers
 * 4. All communication via AnimationEventBus events
 */
export class EntityCombatService {
  
  /**
   * Check if two entities are adjacent (within attack range)
   */
  static isAdjacentToTarget(entityPosition: Position, targetPosition: Position): boolean {
    const [entityX, entityY] = entityPosition;
    const [targetX, targetY] = targetPosition;
    
    const dx = Math.abs(entityX - targetX);
    const dy = Math.abs(entityY - targetY);
    
    // Adjacent means within 1 tile in any direction (including diagonals)
    return dx <= 1 && dy <= 1 && (dx > 0 || dy > 0);
  }
  
  /**
   * Check if an entity is ready for attack input
   */
  static isEntityReadyForAttack(entityId: string): boolean {
    // Entity is ready if not currently animating
    const isAnimating = !!animationActions.getActiveAnimation(entityId);
    const isAttacking = !!battlemapStore.entities.attackAnimations[entityId];
    return !isAnimating && !isAttacking;
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
   * Execute attack with optimistic animation + adoption pattern
   */
  static async executeAttack(
    attackerId: string, 
    targetId: string, 
    weaponSlot: 'MAIN_HAND' | 'OFF_HAND' = 'MAIN_HAND'
  ): Promise<boolean> {
    const attacker = battlemapStore.entities.summaries[attackerId];
    const target = battlemapStore.entities.summaries[targetId];
    
    if (!attacker || !target) {
      console.warn(`[EntityCombatService] Attacker or target not found: ${attackerId}, ${targetId}`);
      return false;
    }

    // Check if attacker is ready for combat
    if (!this.isEntityReadyForAttack(attackerId)) {
      console.log(`[EntityCombatService] Entity ${attacker.name} is not ready for attack`);
      return false;
    }

    console.log(`[EntityCombatService] Starting optimistic attack: ${attacker.name} -> ${target.name}`);

    // STEP 1: Calculate attack direction and set it immediately
    const attackDirection = this.computeDirection(attacker.position, target.position);
    
    // Set direction before starting animation (prevents direction conflicts)
    battlemapActions.setEntityDirectionFromMapping(attackerId, attackDirection);
    console.log(`[EntityCombatService] Set attack direction for ${attacker.name}: ${attackDirection}`);

    // STEP 2: Start optimistic attack animation in battlemap store
    battlemapActions.startEntityAttack(attackerId, targetId);
    console.log(`[EntityCombatService] Started optimistic attack animation for ${attacker.name}`);

    // STEP 3: Fire event to notify animation system
    animationEventBus.emit('ATTACK_STARTED', {
      entityId: attackerId,
      targetId: targetId,
      attackDirection: attackDirection,
      startTime: Date.now(),
      status: 'optimistic', // Will become 'adopted' or 'rejected' based on server response
      weaponSlot: weaponSlot
    });

    // STEP 4: Make API call in parallel (don't await - this is the key!)
    executeAttack(attackerId, targetId, weaponSlot)
      .then((attackResponse) => {
        console.log(`[EntityCombatService] Server processed attack from ${attacker.name}:`, {
          outcome: attackResponse.metadata.attack_outcome,
          damage: attackResponse.metadata.total_damage
        });
        
        // Update attack metadata from server response
        battlemapActions.updateEntityAttackMetadata(attackerId, attackResponse.metadata);
        
        // Fire adoption event with server data
        animationEventBus.emit('ATTACK_ADOPTED', {
          entityId: attackerId,
          targetId: targetId,
          attackResponse: attackResponse,
          serverApproved: true,
          adoptionTime: Date.now()
        });
        
        // Refresh entity summaries to get updated health/status
        battlemapActions.fetchEntitySummaries();
      })
      .catch((error) => {
        console.error(`[EntityCombatService] Server rejected attack from ${attacker.name}:`, error);
        
        // Fire rejection event
        animationEventBus.emit('ATTACK_REJECTED', {
          entityId: attackerId,
          targetId: targetId,
          error: error,
          rejectionTime: Date.now()
        });
        
        // ROLLBACK: Complete attack immediately on failure (returns to idle)
        battlemapActions.completeEntityAttack(attackerId);
      });

    // STEP 5: Return immediately - animation is already started optimistically
    return true;
  }
  
  /**
   * Force cancel entity attack
   */
  static cancelEntityAttack(entityId: string): void {
    console.log(`[EntityCombatService] Cancelling attack for entity ${entityId}`);
    
    // Complete attack in battlemap store
    battlemapActions.completeEntityAttack(entityId);
    
    // Remove from animation store if exists
    const activeAnimation = animationActions.getActiveAnimation(entityId);
    if (activeAnimation) {
      animationActions.completeAnimation(entityId);
    }
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
   * Set entity direction (for manual facing before attacks)
   */
  static setEntityDirection(entityId: string, direction: Direction): void {
    console.log(`[EntityCombatService] Setting direction for ${entityId}: ${direction}`);
    
    // Update sprite mapping direction
    battlemapActions.setEntityDirectionFromMapping(entityId, direction);
    
    // Also update stored direction
    battlemapActions.setEntityDirection(entityId, direction);
  }
  
  /**
   * Check if entity is currently attacking
   */
  static isEntityAttacking(entityId: string): boolean {
    return !!battlemapStore.entities.attackAnimations[entityId];
  }
  
  /**
   * Get current attack metadata for an entity
   */
  static getAttackMetadata(entityId: string): any | null {
    const attackAnimation = battlemapStore.entities.attackAnimations[entityId];
    return attackAnimation?.metadata || null;
  }
} 