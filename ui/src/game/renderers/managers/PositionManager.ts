import { Container, AnimatedSprite } from 'pixi.js';
import { battlemapStore } from '../../../store';
import { animationActions } from '../../../store/animationStore';
import { EntitySummary } from '../../../types/common';
import { VisualPosition, EntitySpriteMapping } from '../../../types/battlemap_types';
import { gridToIsometric } from '../../../utils/isometricUtils';
import { IsometricRenderingUtils } from '../utils/IsometricRenderingUtils';
import { SpriteLoadingUtils } from '../../animation/utils/AnimationUtils';

/**
 * PositionManager - Specialized manager for entity position updates
 * 
 * RESPONSIBILITIES:
 * ✅ Update entity visual positions on screen
 * ✅ Convert grid coordinates to screen coordinates
 * ✅ Handle batch position updates (view changes)
 * ✅ Skip position updates for animating entities
 * 
 * EXTRACTED FROM: IsometricEntityRenderer position logic
 * FOLLOWS: Clean architecture principles from state management guide
 */
export class PositionManager {
  /**
   * Update entity visual position on screen
   * Converts grid position to isometric screen coordinates
   */
  updateEntityVisualPosition(
    entityId: string, 
    visualPosition: VisualPosition,
    entityContainers: Map<string, Container>,
    engine: any
  ): void {
    const entityContainer = entityContainers.get(entityId);
    if (!entityContainer) return;

    const snap = battlemapStore;
    const isometricOffset = IsometricRenderingUtils.calculateIsometricGridOffset(engine);
    
    // Convert grid position to isometric coordinates
    const { isoX, isoY } = gridToIsometric(visualPosition.x, visualPosition.y);
    
    // Apply scale factor to isometric coordinates (tileSize is the scale factor)
    const scaledIsoX = isoX * isometricOffset.tileSize;
    const scaledIsoY = isoY * isometricOffset.tileSize;
    
    // Convert isometric coordinates to screen coordinates with proper centering
    const screenX = isometricOffset.offsetX + scaledIsoX; // Center horizontally in isometric space
    const screenY = isometricOffset.offsetY + scaledIsoY + (snap.view.tileSize * 0.7); // Position half a tile north (less south offset)
    
    entityContainer.x = screenX;
    entityContainer.y = screenY;
  }
  
  /**
   * Update all entity positions (called on view changes)
   * PERFORMANCE: Skips entities that are currently animating to prevent position conflicts
   * FIXED: Also updates sprite scaling for zoom responsiveness
   */
  updateAllEntityPositions(
    entityContainers: Map<string, Container>,
    animatedSprites: Map<string, AnimatedSprite>,
    engine: any
  ): void {
    const snap = battlemapStore;
    const entities = Object.values(snap.entities.summaries) as EntitySummary[];
    
    // Filter out entities that are currently animating - their positions are handled by animation system
    const entitiesToUpdate = entities.filter(entity => {
      const isAnimating = !!animationActions.getActiveAnimation(entity.uuid);
      if (isAnimating) {
        // Skip animating entities - their positions are managed by MovementAnimationHandler
        return false;
      }
      return true;
    });
    
    if (entitiesToUpdate.length < entities.length) {
      console.log(`[PositionManager] Skipping position update for ${entities.length - entitiesToUpdate.length} animating entities`);
    }
    
    // Update positions AND scaling for all non-animating entities
    entitiesToUpdate.forEach(entity => {
      this.updateSingleEntityPosition(entity, entityContainers, engine);
      
      // CRITICAL FIX: Also update sprite scaling when tile size changes (zoom)
      const animatedSprite = animatedSprites.get(entity.uuid);
      const spriteMapping = snap.entities.spriteMappings[entity.uuid];
      if (animatedSprite && spriteMapping) {
        this.updateSpriteScaling(animatedSprite, spriteMapping);
      }
    });
    
    console.log(`[PositionManager] Updated positions and scaling for ${entitiesToUpdate.length} entities`);
  }
  
  /**
   * Update sprite scaling for an entity
   * FIXED: Use the existing SpriteLoadingUtils method for proper scaling
   */
  private updateSpriteScaling(animatedSprite: AnimatedSprite, spriteMapping: EntitySpriteMapping): void {
    const snap = battlemapStore;
    
    // Use the existing, properly tested scaling method from SpriteLoadingUtils
    SpriteLoadingUtils.updateSpriteScale(animatedSprite, spriteMapping, snap.view.tileSize);
  }
  
  /**
   * Update position for a single entity
   */
  private updateSingleEntityPosition(
    entity: EntitySummary,
    entityContainers: Map<string, Container>,
    engine: any
  ): void {
    const snap = battlemapStore;
    const entityContainer = entityContainers.get(entity.uuid);
    if (!entityContainer) return;
    
    // Use sprite mapping visual position if available, otherwise server position
    const spriteMapping = snap.entities.spriteMappings[entity.uuid];
    let visualPosition: VisualPosition;
    
    if (spriteMapping?.visualPosition) {
      visualPosition = spriteMapping.visualPosition;
    } else {
      // Convert server position to visual position
      visualPosition = { x: entity.position[0], y: entity.position[1] };
    }
    
    this.updateEntityVisualPosition(entity.uuid, visualPosition, entityContainers, engine);
  }
  
  /**
   * Get screen coordinates for a grid position
   * Utility method for coordinate conversion
   */
  gridToScreenCoordinates(
    gridX: number, 
    gridY: number, 
    engine: any
  ): { screenX: number; screenY: number } {
    const snap = battlemapStore;
    const isometricOffset = IsometricRenderingUtils.calculateIsometricGridOffset(engine);
    
    // Convert grid position to isometric coordinates
    const { isoX, isoY } = gridToIsometric(gridX, gridY);
    
    // Apply scale factor to isometric coordinates
    const scaledIsoX = isoX * isometricOffset.tileSize;
    const scaledIsoY = isoY * isometricOffset.tileSize;
    
    // Convert to screen coordinates
    const screenX = isometricOffset.offsetX + scaledIsoX;
    const screenY = isometricOffset.offsetY + scaledIsoY + (snap.view.tileSize * 0.7);
    
    return { screenX, screenY };
  }
  
  /**
   * No cleanup needed for position manager
   */
  destroy(): void {
    console.log('[PositionManager] Destroyed');
  }
} 