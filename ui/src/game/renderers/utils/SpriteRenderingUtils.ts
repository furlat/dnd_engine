import { Container, AnimatedSprite } from 'pixi.js';
import { EntitySummary } from '../../../types/common';
import { EntitySpriteMapping, VisualPosition, Direction, toVisualPosition } from '../../../types/battlemap_types';
import { battlemapStore } from '../../../store';
import { IsometricRenderingUtils } from './IsometricRenderingUtils';
import { SpriteLoadingUtils, SpriteCallbackUtils, CachedSpriteData } from '../../animation/utils/AnimationUtils';
import { DirectionUtils } from '../../animation/utils/DirectionUtils';

/**
 * Sprite rendering utilities for container management and positioning
 * Works alongside AnimationUtils for sprite loading and DirectionUtils for direction handling
 * Focuses on renderer-specific concerns: containers, positioning, visibility
 */
export class SpriteRenderingUtils {
  
  /**
   * Ensure an entity has a sprite container and animated sprite properly set up
   * Returns the container and sprite, creating them if necessary
   */
  static async ensureEntitySprite(
    entity: EntitySummary,
    mapping: EntitySpriteMapping,
    entityContainers: Map<string, Container>,
    animatedSprites: Map<string, AnimatedSprite>,
    parentContainer: Container,
    engine: any,
    getCurrentDirection?: (entityId: string) => Direction | undefined
  ): Promise<{ container: Container; sprite: AnimatedSprite } | null> {
    
    // Get or create entity container
    let entityContainer = entityContainers.get(entity.uuid);
    if (!entityContainer) {
      entityContainer = new Container();
      entityContainers.set(entity.uuid, entityContainer);
      parentContainer.addChild(entityContainer);
      console.log(`[SpriteRenderingUtils] Created new container for entity ${entity.name}`);
    }
    
    // Load sprite data using AnimationUtils
    const cachedData = await SpriteLoadingUtils.loadAndCacheSprite(mapping.spriteFolder, mapping.currentAnimation);
    if (!cachedData) return null;
    
    // Get current direction (check local state first, fall back to mapping)
    const localDirection = getCurrentDirection?.(entity.uuid);
    const gridDirection = localDirection || mapping.currentDirection;
    const isometricDirection = DirectionUtils.convertToIsometricDirection(gridDirection);
    
    // Get textures for current direction
    const directionTextures = cachedData.directionTextures[isometricDirection];
    if (!directionTextures || directionTextures.length === 0) {
      console.warn(`[SpriteRenderingUtils] No textures found for direction ${isometricDirection} in ${cachedData.cacheKey}`);
      return null;
    }
    
    // Get or create animated sprite
    let animatedSprite = animatedSprites.get(entity.uuid);
    
    if (!animatedSprite) {
      // Create new sprite using AnimationUtils
      animatedSprite = SpriteLoadingUtils.createAnimatedSprite(
        entity, mapping, directionTextures, cachedData.cacheKey, isometricDirection
      );
      entityContainer.addChild(animatedSprite);
      animatedSprites.set(entity.uuid, animatedSprite);
      console.log(`[SpriteRenderingUtils] Created new sprite for ${entity.name}`);
    } else {
      // Update existing sprite if needed
      this.updateExistingSpriteIfNeeded(entity, mapping, animatedSprite, cachedData, isometricDirection);
    }
    
    // Update position
    this.updateEntityContainerPosition(entity, entityContainer, engine);
    
    // Update scale
    this.updateSpriteScale(animatedSprite, mapping);
    
    return { container: entityContainer, sprite: animatedSprite };
  }
  
  /**
   * Update existing sprite only if animation or direction changed
   * Prevents unnecessary updates and animation restarts
   */
  static updateExistingSpriteIfNeeded(
    entity: EntitySummary,
    mapping: EntitySpriteMapping,
    animatedSprite: AnimatedSprite,
    cachedData: CachedSpriteData,
    currentDirection: Direction
  ): boolean {
    const expectedCacheKey = SpriteLoadingUtils.createCacheKey(mapping.spriteFolder, mapping.currentAnimation);
    const spriteKey = `${expectedCacheKey}_${currentDirection}`;
    
    // Parse current sprite key
    const currentSpriteKey = animatedSprite.name || '';
    const currentParts = currentSpriteKey.split('_');
    const currentCacheKey = currentParts.slice(0, -1).join('_');
    const currentDirectionFromKey = currentParts[currentParts.length - 1];
    
    // Check what changed
    const animationChanged = currentCacheKey !== expectedCacheKey;
    const directionChanged = currentDirectionFromKey !== currentDirection;
    
    if (animationChanged) {
      console.log(`[SpriteRenderingUtils] Animation changed for ${entity.name}: ${currentCacheKey} -> ${expectedCacheKey}`);
      return this.updateSpriteAnimation(animatedSprite, mapping, cachedData, currentDirection, spriteKey);
    } else if (directionChanged) {
      console.log(`[SpriteRenderingUtils] Direction changed for ${entity.name}: ${currentDirectionFromKey} -> ${currentDirection}`);
      return this.updateSpriteDirection(animatedSprite, cachedData, currentDirection, spriteKey);
    }
    
    // No changes needed
    return false;
  }
  
  /**
   * Update sprite animation (restart with new textures)
   */
  private static updateSpriteAnimation(
    animatedSprite: AnimatedSprite,
    mapping: EntitySpriteMapping,
    cachedData: CachedSpriteData,
    currentDirection: Direction,
    spriteKey: string
  ): boolean {
    const directionTextures = cachedData.directionTextures[currentDirection];
    if (!directionTextures || directionTextures.length === 0) return false;
    
    // Stop and update
    animatedSprite.stop();
    animatedSprite.textures = directionTextures;
    animatedSprite.name = spriteKey;
    
    // Update animation properties
    const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || 
                      SpriteLoadingUtils.shouldLoop(mapping.currentAnimation);
    animatedSprite.loop = shouldLoop;
    
    const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
    const framesPerSecond = directionTextures.length / desiredDurationSeconds;
    animatedSprite.animationSpeed = framesPerSecond / 60;
    
    animatedSprite.play();
    return true;
  }
  
  /**
   * Update sprite direction (smooth transition without restart)
   */
  private static updateSpriteDirection(
    animatedSprite: AnimatedSprite,
    cachedData: CachedSpriteData,
    currentDirection: Direction,
    spriteKey: string
  ): boolean {
    const directionTextures = cachedData.directionTextures[currentDirection];
    if (!directionTextures || directionTextures.length === 0) return false;
    
    // Smooth direction change
    const wasPlaying = animatedSprite.playing;
    const currentFrame = animatedSprite.currentFrame;
    
    animatedSprite.textures = directionTextures;
    animatedSprite.name = spriteKey;
    
    if (wasPlaying) {
      animatedSprite.gotoAndPlay(Math.min(currentFrame, directionTextures.length - 1));
    }
    
    return true;
  }
  
  /**
   * Update entity container position using visual or server position
   * FIXED: Never use server position during animation - only use visual position
   */
  static updateEntityContainerPosition(
    entity: EntitySummary,
    entityContainer: Container,
    engine: any
  ): void {
    const snap = battlemapStore;
    const spriteMapping = snap.entities.spriteMappings[entity.uuid];
    
    // CRITICAL FIX: During animation, ALWAYS use visual position, never server position
    // This prevents disgusting duplication where entities appear at both positions
    let positionToUse: VisualPosition;
    if (spriteMapping?.visualPosition) {
      // Always use visual position if available (whether synced or not)
      positionToUse = spriteMapping.visualPosition;
    } else {
      // Only fall back to server position if no visual position exists
      positionToUse = toVisualPosition(entity.position);
    }
    
    this.updateContainerPosition(entityContainer, positionToUse, engine);
  }
  
  /**
   * Update container position with isometric conversion
   */
  static updateContainerPosition(
    container: Container,
    visualPosition: VisualPosition,
    engine: any
  ): void {
    const snap = battlemapStore;
    const isometricOffset = IsometricRenderingUtils.calculateIsometricGridOffset(engine);
    
    // Convert grid position to isometric coordinates
    const { isoX, isoY } = gridToIsometric(visualPosition.x, visualPosition.y);
    
    // Apply scale factor and positioning
    const scaledIsoX = isoX * isometricOffset.tileSize;
    const scaledIsoY = isoY * isometricOffset.tileSize;
    
    const screenX = isometricOffset.offsetX + scaledIsoX;
    const screenY = isometricOffset.offsetY + scaledIsoY + (snap.view.tileSize * 0.7);
    
    container.x = screenX;
    container.y = screenY;
  }
  
  /**
   * Update sprite scale based on mapping and current tile size
   */
  static updateSpriteScale(
    animatedSprite: AnimatedSprite,
    mapping: EntitySpriteMapping
  ): void {
    const snap = battlemapStore;
    SpriteLoadingUtils.updateSpriteScale(animatedSprite, mapping, snap.view.tileSize);
  }
  
  /**
   * Set up sprite animation callbacks using SpriteCallbackUtils
   */
  static setupSpriteCallbacks(
    animatedSprite: AnimatedSprite,
    entity: EntitySummary,
    mapping: EntitySpriteMapping,
    onImpactFrame?: (frameProgress: number) => void,
    onComplete?: () => void
  ): void {
    SpriteCallbackUtils.setupAnimationCallbacks(
      animatedSprite,
      entity,
      mapping,
      onImpactFrame,
      onComplete
    );
  }
  
  /**
   * Remove entity sprite and container completely
   */
  static removeEntitySprite(
    entityId: string,
    entityContainers: Map<string, Container>,
    animatedSprites: Map<string, AnimatedSprite>,
    parentContainer: Container
  ): void {
    const entityContainer = entityContainers.get(entityId);
    const animatedSprite = animatedSprites.get(entityId);
    
    if (entityContainer) {
      parentContainer.removeChild(entityContainer);
      entityContainer.destroy();
      entityContainers.delete(entityId);
    }
    
    if (animatedSprite) {
      animatedSprite.destroy();
      animatedSprites.delete(entityId);
    }
  }
  
  /**
   * Update all entity container positions (called on view changes)
   */
  static updateAllEntityPositions(
    entities: EntitySummary[],
    entityContainers: Map<string, Container>,
    animatedSprites: Map<string, AnimatedSprite>,
    engine: any
  ): void {
    entities.forEach(entity => {
      const container = entityContainers.get(entity.uuid);
      if (container) {
        this.updateEntityContainerPosition(entity, container, engine);
        
        // Also update sprite scale
        const sprite = animatedSprites.get(entity.uuid);
        const spriteMapping = battlemapStore.entities.spriteMappings[entity.uuid];
        if (sprite && spriteMapping) {
          this.updateSpriteScale(sprite, spriteMapping);
        }
      }
    });
  }
}

// Import function needed for isometric conversion
import { gridToIsometric } from '../../../utils/isometricUtils'; 