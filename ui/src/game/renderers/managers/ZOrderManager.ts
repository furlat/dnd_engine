import { Container } from 'pixi.js';
import { battlemapStore } from '../../../store';
import { animationActions } from '../../../store/animationStore';
import { EntitySummary } from '../../../types/common';

/**
 * ZOrderManager - Specialized manager for entity layering and container ordering
 * 
 * RESPONSIBILITIES:
 * ✅ Manage local z-order overrides during animations
 * ✅ Calculate default z-order based on isometric depth
 * ✅ Handle container ordering in PixiJS display list
 * ✅ Coordinate between local and global z-order states
 * 
 * EXTRACTED FROM: IsometricEntityRenderer z-order logic
 * FOLLOWS: Clean architecture principles from state management guide
 */
export class ZOrderManager {
  // Local z-order state to avoid store spam during animations
  private localZOrderStates: Map<string, number> = new Map();
  
  /**
   * Set local z-order for an entity (immediate, no store update)
   */
  setLocalZOrder(entityId: string, zIndex: number): void {
    const currentZOrder = this.localZOrderStates.get(entityId);
    if (currentZOrder !== zIndex) {
      this.localZOrderStates.set(entityId, zIndex);
      console.log(`[ZOrderManager] Set local z-order for ${entityId}: ${zIndex}`);
    }
  }
  
  /**
   * Clear local z-order for an entity
   */
  clearLocalZOrder(entityId: string): void {
    if (this.localZOrderStates.has(entityId)) {
      this.localZOrderStates.delete(entityId);
      console.log(`[ZOrderManager] Cleared local z-order for entity ${entityId}`);
    }
  }
  
  /**
   * Update entity container order based on local and global z-order states
   * This reorders the containers in the PixiJS display list for proper layering
   */
  updateEntityContainerOrder(
    entityContainers: Map<string, Container>, 
    mainContainer: Container
  ): void {
    const snap = battlemapStore;
    const entities = Object.values(snap.entities.summaries) as EntitySummary[];
    
    // Create array of entities with their effective z-order
    const entitiesWithZOrder = entities
      .filter(entity => entityContainers.has(entity.uuid))
      .map(entity => {
        const zOrder = this.calculateEffectiveZOrder(entity);
        return { entity, zOrder };
      })
      .sort((a, b) => a.zOrder - b.zOrder); // Sort by z-order (lower first)
    
    // Re-order containers in the main container
    entitiesWithZOrder.forEach(({ entity }) => {
      const container = entityContainers.get(entity.uuid);
      if (container) {
        // Remove and re-add to put it at the end (on top)
        mainContainer.removeChild(container);
        mainContainer.addChild(container);
      }
    });
    
    console.log(`[ZOrderManager] Updated container order for ${entitiesWithZOrder.length} entities:`, 
      entitiesWithZOrder.map(({ entity, zOrder }) => {
        const pos = entity.position;
        const depth = pos[0] + pos[1];
        return `${entity.name}:(${pos[0]},${pos[1]})=depth${depth}→z${zOrder}`;
      }));
  }
  
  /**
   * Calculate effective z-order for an entity
   * Priority: local override > global override > calculated default
   */
  private calculateEffectiveZOrder(entity: EntitySummary): number {
    const snap = battlemapStore;
    
    // 1. Use local z-order if available (during animations)
    let zOrder = this.localZOrderStates.get(entity.uuid);
    if (zOrder !== undefined) {
      return zOrder;
    }
    
    // 2. Use global z-order override if available
    zOrder = snap.entities.zOrderOverrides[entity.uuid];
    if (zOrder !== undefined) {
      return zOrder;
    }
    
    // 3. Calculate default z-order based on isometric depth and dynamic state
    return this.calculateDefaultZOrder(entity);
  }
  
  /**
   * Calculate default z-order based on isometric depth and entity state
   */
  private calculateDefaultZOrder(entity: EntitySummary): number {
    const snap = battlemapStore;
    const isMoving = !!animationActions.getActiveAnimation(entity.uuid);
    const isAttacking = !!snap.entities.attackAnimations[entity.uuid];
    
    // Get entity position (use visual position if available during movement)
    const spriteMapping = snap.entities.spriteMappings[entity.uuid];
    let entityPosition: readonly [number, number];
    if (spriteMapping?.visualPosition && !spriteMapping.isPositionSynced) {
      // Use visual position during movement
      entityPosition = [spriteMapping.visualPosition.x, spriteMapping.visualPosition.y];
    } else {
      // Use server position
      entityPosition = entity.position;
    }
    
    // Calculate isometric depth: entities further "down" on screen (higher Y + X) should render on top
    // In isometric view, depth increases as we go toward bottom-right (+X, +Y)
    const isometricDepth = entityPosition[0] + entityPosition[1];
    
    if (isMoving || isAttacking) {
      // Dynamic entities: base 1000 + depth (ensures they're always above static entities)
      return 1000 + isometricDepth;
    } else {
      // Static entities: just use depth for proper layering
      return isometricDepth;
    }
  }
  
  /**
   * Clean up z-order state for a removed entity
   */
  cleanupEntityZOrderState(entityId: string): void {
    this.localZOrderStates.delete(entityId);
  }
  
  /**
   * Clean up all z-order states
   */
  destroy(): void {
    this.localZOrderStates.clear();
    console.log('[ZOrderManager] Destroyed');
  }
} 