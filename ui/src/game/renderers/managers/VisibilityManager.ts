import { Container } from 'pixi.js';
import { battlemapStore } from '../../../store';
import { EntitySummary, Position } from '../../../types/common';
import { SensesCalculationUtils } from '../utils/SensesCalculationUtils';

/**
 * VisibilityManager - Specialized manager for entity visibility
 * 
 * RESPONSIBILITIES:
 * ✅ Calculate entity visibility based on senses
 * ✅ Manage container alpha and renderable states
 * ✅ Cache visibility states for performance
 * ✅ Handle visibility enable/disable transitions
 * 
 * EXTRACTED FROM: IsometricEntityRenderer visibility logic
 * FOLLOWS: Clean architecture principles from state management guide
 */
export class VisibilityManager {
  // Simple visibility state caching (back to original approach)
  private lastVisibilityStates: Map<string, { 
    targetAlpha: number; 
    shouldBeRenderable: boolean 
  }> = new Map();
  
  // Cached senses data during movement to prevent visibility flickering
  private cachedSensesData: Map<string, { 
    visible: Record<string, boolean>; 
    seen: readonly Position[] 
  }> = new Map();
  
  // Track last logged position for each entity to reduce console spam
  private lastLoggedPositions: Map<string, { x: number; y: number }> = new Map();
  
  /**
   * Update entity visibility alpha based on selected entity's senses
   * REVERTED: Back to simple approach that works
   */
  updateEntityVisibilityAlpha(entityContainers: Map<string, Container>): void {
    const snap = battlemapStore;
    const selectedEntity = SensesCalculationUtils.getSelectedEntity();
    
    if (!selectedEntity || !snap.controls.isVisibilityEnabled) {
      // No selected entity or visibility disabled - make all entities fully visible
      this.setAllEntitiesVisible(entityContainers);
      return;
    }
    
    const sensesData = SensesCalculationUtils.getSensesData(
      selectedEntity,
      this.cachedSensesData,
      this.lastLoggedPositions
    );
    if (!sensesData) return;
    
    // Update visibility for each entity
    Object.values(snap.entities.summaries).forEach((entity: EntitySummary) => {
      this.updateSingleEntityVisibility(
        entity, 
        selectedEntity, 
        sensesData, 
        entityContainers
      );
    });
  }
  
  /**
   * Set all entities to fully visible (when visibility is disabled)
   */
  private setAllEntitiesVisible(entityContainers: Map<string, Container>): void {
    entityContainers.forEach((container, entityId) => {
      container.alpha = 1.0;
      container.renderable = true;
    });
  }
  
  /**
   * Update visibility for a single entity (simplified)
   */
  private updateSingleEntityVisibility(
    entity: EntitySummary, 
    selectedEntity: EntitySummary, 
    sensesData: any, 
    entityContainers: Map<string, Container>
  ): void {
    const container = entityContainers.get(entity.uuid);
    if (!container) return;
    
    const visibility = SensesCalculationUtils.calculateEntityVisibility(entity, selectedEntity, sensesData);
    const lastState = this.lastVisibilityStates.get(entity.uuid);
    
    // Only update if visibility state changed (performance optimization)
    if (!lastState || 
        lastState.targetAlpha !== visibility.targetAlpha || 
        lastState.shouldBeRenderable !== visibility.shouldBeRenderable) {
      
      // Update alpha for fog effect (seen but not visible)
      container.alpha = visibility.targetAlpha;
      
      // Update renderable for complete invisibility (unseen entities)
      container.renderable = visibility.shouldBeRenderable;
      
      // Cache the new state
      this.lastVisibilityStates.set(entity.uuid, {
        targetAlpha: visibility.targetAlpha,
        shouldBeRenderable: visibility.shouldBeRenderable
      });
    }
  }
  
  /**
   * Cache senses data for a specific entity (called before movement starts)
   */
  cacheSensesDataForEntity(entityId: string, sensesData: { 
    visible: Record<string, boolean>; 
    seen: readonly Position[] 
  }): void {
    this.cachedSensesData.set(entityId, sensesData);
    console.log(`[VisibilityManager] Cached senses data for entity ${entityId}`);
  }
  
  /**
   * Handle movement animation changes to cache senses data
   */
  handleMovementAnimationChanges(): void {
    SensesCalculationUtils.handleMovementAnimationChanges(this.cachedSensesData);
  }
  
  /**
   * Clean up visibility state for a removed entity
   */
  cleanupEntityVisibilityState(entityId: string): void {
    this.lastVisibilityStates.delete(entityId);
    this.cachedSensesData.delete(entityId);
    this.lastLoggedPositions.delete(entityId);
  }
  
  /**
   * Clean up all visibility states
   */
  destroy(): void {
    this.lastVisibilityStates.clear();
    this.cachedSensesData.clear();
    this.lastLoggedPositions.clear();
    console.log('[VisibilityManager] Destroyed');
  }
} 