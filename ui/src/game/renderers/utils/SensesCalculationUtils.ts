import { EntitySummary, Position } from '../../../types/common';
import { VisualPosition, toVisualPosition } from '../../../types/battlemap_types';
import { battlemapStore } from '../../../store';
import { animationActions } from '../../../store/animationStore';

/**
 * Interface for senses data used in visibility calculations
 */
export interface SensesData {
  visible: Record<string, boolean>;
  seen: readonly Position[];
}

/**
 * Interface for visibility calculation result
 */
export interface VisibilityResult {
  visible: boolean;
  seen: boolean;
  targetAlpha: number;
  shouldBeRenderable: boolean;
}

/**
 * Senses calculation utilities extracted from IsometricEntityRenderer
 * Handles the complex three-tier state management: server -> animation -> private
 * Provides clean separation for dynamic visibility during movement
 */
export class SensesCalculationUtils {
  
  /**
   * Get senses data for visibility calculations using dynamic path senses
   * Implements the three-tier system:
   * 1. Dynamic senses when observer is moving (uses path senses)
   * 2. Cached static senses when others are moving (prevents flickering)
   * 3. Current senses as fallback
   */
  static getSensesData(
    observerEntity: EntitySummary,
    cachedSensesData: Map<string, SensesData>,
    lastLoggedPositions: Map<string, { x: number; y: number }>
  ): SensesData {
    const snap = battlemapStore;
    
    // Check if the OBSERVER entity is currently moving
    const observerMovementAnimation = animationActions.getActiveAnimation(observerEntity.uuid);
    
    if (observerMovementAnimation) {
      // Observer is moving - use dynamic path senses based on their current animated position
      const pathSenses = snap.entities.pathSenses[observerEntity.uuid];
      
      if (pathSenses) {
        const spriteMapping = snap.entities.spriteMappings[observerEntity.uuid];
        if (spriteMapping?.visualPosition) {
          // Use anticipation: switch to next cell's senses when we're at the center of the sprite
          const anticipationThreshold = 0.5;
          const currentX = Math.floor(spriteMapping.visualPosition.x + anticipationThreshold);
          const currentY = Math.floor(spriteMapping.visualPosition.y + anticipationThreshold);
          const posKey = `${currentX},${currentY}`;
          
          // Use senses data for the current animated position
          const currentPositionSenses = pathSenses[posKey];
          if (currentPositionSenses) {
            // Only log when position changes to reduce spam
            const lastLoggedPos = lastLoggedPositions.get(observerEntity.uuid);
            if (!lastLoggedPos || lastLoggedPos.x !== currentX || lastLoggedPos.y !== currentY) {
              console.log(`[SensesCalculationUtils] Using dynamic path senses for ${observerEntity.name} at position (${currentX}, ${currentY})`);
              lastLoggedPositions.set(observerEntity.uuid, { x: currentX, y: currentY });
            }
            return {
              visible: currentPositionSenses.visible,
              seen: currentPositionSenses.seen
            };
          } else {
            // Path senses available but no data for current position - use entity's current senses
            return {
              visible: observerEntity.senses.visible,
              seen: observerEntity.senses.seen
            };
          }
        }
      } else {
        // Path senses not yet available - use entity's current senses as fallback
        return {
          visible: observerEntity.senses.visible,
          seen: observerEntity.senses.seen
        };
      }
    }
    
    // Check if ANY OTHER entity is currently moving (but not the observer)
    const hasOtherMovements = this.hasOtherActiveMovements(observerEntity.uuid);
    
    if (hasOtherMovements) {
      // Other entities are moving but not the observer - use cached static perspective
      const cached = cachedSensesData.get(observerEntity.uuid);
      if (cached) {
        console.log(`[SensesCalculationUtils] Using cached static senses for observer ${observerEntity.name} while other entities move`);
        return cached;
      }
      
      console.warn(`[SensesCalculationUtils] No cached senses data for observer ${observerEntity.name} during other movements - using current data`);
    }
    
    // No movements or fallback - use current data
    return {
      visible: observerEntity.senses.visible,
      seen: observerEntity.senses.seen
    };
  }
  
  /**
   * Calculate visibility state and target alpha for an entity
   * Handles moving entities by using their visual position for calculations
   */
  static calculateEntityVisibility(
    entity: EntitySummary,
    observerEntity: EntitySummary,
    sensesData: SensesData
  ): VisibilityResult {
    // Self is always fully visible
    if (entity.uuid === observerEntity.uuid) {
      return { visible: true, seen: true, targetAlpha: 1.0, shouldBeRenderable: true };
    }
    
    // Use entity's visual position if it's moving, otherwise use server position
    const snap = battlemapStore;
    const spriteMapping = snap.entities.spriteMappings[entity.uuid];
    const isEntityMoving = !spriteMapping?.isPositionSynced;
    
    let entityX: number, entityY: number;
    
    if (isEntityMoving && spriteMapping?.visualPosition) {
      // Entity is moving - use its current animated position for visibility calculation
      entityX = Math.floor(spriteMapping.visualPosition.x);
      entityY = Math.floor(spriteMapping.visualPosition.y);
    } else {
      // Entity is not moving - use server position
      [entityX, entityY] = entity.position;
    }
    
    const posKey = `${entityX},${entityY}`;
    
    // Check if entity position is visible
    const visible = !!sensesData.visible[posKey];
    
    // Check if entity position has been seen before
    const seen = sensesData.seen.some(([seenX, seenY]) => seenX === entityX && seenY === entityY);
    
    if (visible) {
      // Entity is in a visible cell - fully visible
      return { visible: true, seen: true, targetAlpha: 1.0, shouldBeRenderable: true };
    } else {
      // Entity is NOT in a visible cell - completely invisible (regardless of seen status)
      return { visible: false, seen, targetAlpha: 1.0, shouldBeRenderable: false };
    }
  }
  
  /**
   * Cache senses data for an entity to prevent flickering during movement
   * Called when movement starts or entity selection changes
   */
  static cacheSensesDataForEntity(
    entityId: string,
    entitySummary: EntitySummary,
    cachedSensesData: Map<string, SensesData>
  ): void {
    if (!cachedSensesData.has(entityId)) {
      const sensesData: SensesData = {
        visible: entitySummary.senses.visible,
        seen: entitySummary.senses.seen
      };
      cachedSensesData.set(entityId, sensesData);
      console.log(`[SensesCalculationUtils] Cached senses data for entity ${entitySummary.name}`);
    }
  }
  
  /**
   * Clear cached senses data for an entity
   * Called when movement completes or entity is removed
   */
  static clearCachedSensesData(
    entityId: string,
    cachedSensesData: Map<string, SensesData>
  ): void {
    if (cachedSensesData.has(entityId)) {
      cachedSensesData.delete(entityId);
      console.log(`[SensesCalculationUtils] Cleared cached senses data for entity ${entityId}`);
    }
  }
  
  /**
   * Clear all cached senses data
   * Called when all movements complete or renderer is destroyed
   */
  static clearAllCachedSensesData(cachedSensesData: Map<string, SensesData>): void {
    if (cachedSensesData.size > 0) {
      console.log(`[SensesCalculationUtils] Clearing all cached senses data - ${cachedSensesData.size} entries`);
      cachedSensesData.clear();
    }
  }
  
  /**
   * Check if there are active movements that might affect visibility
   */
  static hasActiveMovements(): boolean {
    const allEntities = Object.keys(battlemapStore.entities.summaries);
    return allEntities.some(entityId => !!animationActions.getActiveAnimation(entityId));
  }
  
  /**
   * Check if there are other entities moving (excluding the observer)
   */
  static hasOtherActiveMovements(observerEntityId: string): boolean {
    const allEntities = Object.keys(battlemapStore.entities.summaries);
    return allEntities.some(entityId => 
      entityId !== observerEntityId && !!animationActions.getActiveAnimation(entityId)
    );
  }
  
  /**
   * Check if a specific entity is currently moving
   */
  static isEntityMoving(entityId: string): boolean {
    return !!animationActions.getActiveAnimation(entityId);
  }
  
  /**
   * Get the currently selected entity for visibility calculations
   */
  static getSelectedEntity(): EntitySummary | null {
    const snap = battlemapStore;
    if (!snap.entities.selectedEntityId) return null;
    return snap.entities.summaries[snap.entities.selectedEntityId] || null;
  }
  
  /**
   * Handle movement animation changes - cache senses data when needed
   * This implements the caching strategy to prevent visibility flickering
   */
  static handleMovementAnimationChanges(
    cachedSensesData: Map<string, SensesData>
  ): void {
    const snap = battlemapStore;
    const selectedEntity = this.getSelectedEntity();
    
    if (!selectedEntity || !snap.controls.isVisibilityEnabled) {
      return;
    }
    
    if (this.hasActiveMovements()) {
      // There are active movements - ensure we have cached data for the current viewing entity
      this.cacheSensesDataForEntity(selectedEntity.uuid, selectedEntity, cachedSensesData);
    } else {
      // No active movements - clear all cached senses data
      this.clearAllCachedSensesData(cachedSensesData);
    }
  }
  
  /**
   * Handle entity selection change during movement
   * Cache senses data for newly selected entity if movements are active
   */
  static handleEntitySelectionChange(
    cachedSensesData: Map<string, SensesData>
  ): void {
    const selectedEntity = this.getSelectedEntity();
    
    if (!selectedEntity || !battlemapStore.controls.isVisibilityEnabled) {
      return;
    }
    
    if (this.hasActiveMovements()) {
      // There are active movements and user changed perspective
      this.cacheSensesDataForEntity(selectedEntity.uuid, selectedEntity, cachedSensesData);
    }
  }
} 