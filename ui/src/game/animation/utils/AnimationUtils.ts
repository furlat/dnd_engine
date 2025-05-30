import { Container, AnimatedSprite, Assets, Spritesheet, Ticker, Texture } from 'pixi.js';
import { AnimationState, Direction, EntitySpriteMapping } from '../../../types/battlemap_types';
import { EntitySummary } from '../../../types/common';
import { getSpriteSheetPath } from '../../../api/battlemap/battlemapApi';

/**
 * Cached sprite data using PixiJS v8 Assets cache properly
 * Key format: "spriteFolder|animation" for consistent cache management
 */
export interface CachedSpriteData {
  spritesheet: Spritesheet;
  directionTextures: Record<Direction, Texture[]>;
  cacheKey: string; // For proper cleanup
}

/**
 * Animation timing calculations for consistent behavior
 */
export class AnimationTimingUtils {
  /**
   * Calculate animation speed based on desired duration
   */
  static calculateAnimationSpeed(frameCount: number, durationSeconds: number): number {
    const framesPerSecond = frameCount / durationSeconds;
    return framesPerSecond / 60; // PixiJS expects speed relative to 60fps
  }
  
  /**
   * Calculate frame progress (0-1) for impact detection
   */
  static calculateFrameProgress(currentFrame: number, totalFrames: number): number {
    return currentFrame / Math.max(totalFrames - 1, 1);
  }
  
  /**
   * Check if impact frame reached (exactly 40% progress)
   */
  static isImpactFrame(currentFrame: number, totalFrames: number): boolean {
    const progress = this.calculateFrameProgress(currentFrame, totalFrames);
    return progress >= 0.4;
  }
  
  /**
   * Calculate remaining time from current frame
   */
  static calculateRemainingTime(
    currentFrame: number,
    totalFrames: number,
    animationSpeed: number
  ): number {
    const remainingFrames = totalFrames - currentFrame;
    return (remainingFrames / totalFrames) * (totalFrames / animationSpeed) / 60 * 1000;
  }
}

/**
 * Sprite loading utilities extracted from IsometricEntityRenderer
 * Following the exact structure from animation_refactor_guide.md
 */
export class SpriteLoadingUtils {
  private static spriteCacheByKey: Map<string, CachedSpriteData> = new Map();
  
  /**
   * Create consistent cache key for sprite data
   */
  static createCacheKey(spriteFolder: string, animation: AnimationState): string {
    return `${spriteFolder}|${animation}`;
  }
  
  /**
   * Load and cache sprite data with ALL directions preloaded using PixiJS v8 Assets
   */
  static async loadAndCacheSprite(
    spriteFolder: string, 
    animation: AnimationState
  ): Promise<CachedSpriteData | null> {
    const cacheKey = this.createCacheKey(spriteFolder, animation);
    
    // Check if already cached
    let cachedData = this.spriteCacheByKey.get(cacheKey);
    if (cachedData) {
      return cachedData;
    }
    
    try {
      const spritesheetPath = getSpriteSheetPath(spriteFolder, animation);
      
      // Use unique cache key that includes sprite folder to prevent conflicts
      const uniqueSpritesheetKey = `${spriteFolder}|${animation}|spritesheet`;
      
      // Check if already cached with our unique key
      let spritesheet: Spritesheet;
      if (Assets.cache.has(uniqueSpritesheetKey)) {
        spritesheet = Assets.cache.get(uniqueSpritesheetKey);
        console.log(`[SpriteLoadingUtils] Using cached spritesheet: ${uniqueSpritesheetKey}`);
      } else {
        // Load with unique key to prevent conflicts
        spritesheet = await Assets.load<Spritesheet>({ 
          alias: uniqueSpritesheetKey, 
          src: spritesheetPath 
        });
        console.log(`[SpriteLoadingUtils] Loaded and cached spritesheet: ${uniqueSpritesheetKey} from ${spritesheetPath}`);
      }
      
      if (!spritesheet) {
        console.error(`[SpriteLoadingUtils] Failed to load spritesheet: ${spritesheetPath}`);
        return null;
      }
      
      // Preload ALL directions
      const directionTextures: Record<Direction, Texture[]> = {} as Record<Direction, Texture[]>;
      
      for (const direction of Object.values(Direction)) {
        directionTextures[direction] = this.getDirectionTextures(spritesheet, direction);
      }
      
      cachedData = {
        spritesheet,
        directionTextures,
        cacheKey
      };
      
      this.spriteCacheByKey.set(cacheKey, cachedData);
      console.log(`[SpriteLoadingUtils] Cached sprite data for ${cacheKey} with ${Object.keys(directionTextures).length} directions`);
      
      return cachedData;
    } catch (error) {
      console.error(`[SpriteLoadingUtils] Error loading sprite data:`, error);
      return null;
    }
  }
  
  /**
   * Get textures for a specific direction from a spritesheet
   */
  static getDirectionTextures(spritesheet: Spritesheet, direction: Direction): Texture[] {
    const textures = spritesheet.textures;
    const directionTextures = [];
    
    // Look for textures with the direction pattern
    const pattern = new RegExp(`_${direction}_\\d+\\.png$`);
    
    for (const [textureName, texture] of Object.entries(textures)) {
      if (pattern.test(textureName)) {
        directionTextures.push(texture);
      }
    }
    
    // Sort by frame number
    directionTextures.sort((a, b) => {
      const aName = Object.keys(textures).find(name => textures[name] === a) || '';
      const bName = Object.keys(textures).find(name => textures[name] === b) || '';
      
      const aMatch = aName.match(/_(\d+)\.png$/);
      const bMatch = bName.match(/_(\d+)\.png$/);
      const aNum = aMatch ? parseInt(aMatch[1]) : 0;
      const bNum = bMatch ? parseInt(bMatch[1]) : 0;
      return aNum - bNum;
    });
    
    return directionTextures;
  }
  
  /**
   * Create animated sprite with proper setup
   */
  static createAnimatedSprite(
    entity: EntitySummary,
    mapping: EntitySpriteMapping,
    directionTextures: Texture[],
    cacheKey: string,
    isometricDirection: Direction
  ): AnimatedSprite {
    const animatedSprite = new AnimatedSprite(directionTextures);
    
    const spriteKey = `${cacheKey}_${isometricDirection}`;
    animatedSprite.name = spriteKey;
    animatedSprite.anchor.set(0.5, 1.0); // Bottom-center anchor for character sprites
    
    // Use PixiJS v8 API properly
    animatedSprite.autoUpdate = true;
    
    // Determine if animation should loop
    const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || 
                      SpriteLoadingUtils.shouldLoop(mapping.currentAnimation);
    animatedSprite.loop = shouldLoop;
    
    // Calculate animation speed based on desired duration
    const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
    animatedSprite.animationSpeed = AnimationTimingUtils.calculateAnimationSpeed(
      directionTextures.length, 
      desiredDurationSeconds
    );
    
    // CRITICAL FIX: Actually start playing the animation!
    animatedSprite.play();
    
    console.log(`[SpriteLoadingUtils] Created animated sprite for ${entity.name}: ${mapping.currentAnimation} (${directionTextures.length} frames, loop: ${shouldLoop}) - PLAYING`);
    
    return animatedSprite;
  }
  
  /**
   * Determine if an animation should loop
   */
  static shouldLoop(animation: AnimationState): boolean {
    switch (animation) {
      case AnimationState.IDLE:
      case AnimationState.IDLE2:
      case AnimationState.WALK:
      case AnimationState.RUN:
      case AnimationState.RUN_BACKWARDS:
      case AnimationState.CROUCH_RUN:
        return true;
        
      case AnimationState.ATTACK1:
      case AnimationState.ATTACK2:
      case AnimationState.ATTACK3:
      case AnimationState.TAKE_DAMAGE:
      case AnimationState.DIE:
        return false;
        
      default:
        return false;
    }
  }
  
  /**
   * Update sprite scale based on mapping and zoom
   */
  static updateSpriteScale(
    animatedSprite: AnimatedSprite, 
    mapping: EntitySpriteMapping,
    tileSize: number
  ): void {
    const userScaleMultiplier = mapping.scale || 1.0;
    
    if (animatedSprite.textures.length > 0 && 'frame' in animatedSprite.textures[0]) {
      const BASE_SCALE = 2.4;
      const textureWidth = animatedSprite.textures[0].frame.width;
      const textureHeight = animatedSprite.textures[0].frame.height;
      
      const zoomDependentScale = (tileSize / Math.max(textureWidth, textureHeight)) * BASE_SCALE;
      const finalScale = zoomDependentScale * userScaleMultiplier;
      animatedSprite.scale.set(finalScale);
    } else {
      animatedSprite.scale.set(userScaleMultiplier);
    }
  }
  
  /**
   * Get cached sprite data
   */
  static getCachedSprite(spriteFolder: string, animation: AnimationState): CachedSpriteData | undefined {
    const cacheKey = this.createCacheKey(spriteFolder, animation);
    return this.spriteCacheByKey.get(cacheKey);
  }
  
  /**
   * Clear sprite cache
   */
  static clearCache(): void {
    this.spriteCacheByKey.clear();
  }
}

/**
 * Sprite callback utilities for animation events
 */
export class SpriteCallbackUtils {
  /**
   * Set up optimized animation callbacks with state transition checking
   */
  static setupAnimationCallbacks(
    sprite: AnimatedSprite,
    entity: EntitySummary,
    mapping: EntitySpriteMapping,
    onImpactFrame?: (frameProgress: number) => void,
    onComplete?: () => void
  ): void {
    // Clear any existing callbacks to prevent memory leaks
    sprite.onComplete = undefined;
    sprite.onLoop = undefined;
    sprite.onFrameChange = undefined;
    
    const shouldLoop = SpriteLoadingUtils.shouldLoop(mapping.currentAnimation);
    const isAttackAnimation = mapping.currentAnimation === AnimationState.ATTACK1 || 
                             mapping.currentAnimation === AnimationState.ATTACK2 || 
                             mapping.currentAnimation === AnimationState.ATTACK3;
    
    if (!shouldLoop) {
      if (isAttackAnimation && onImpactFrame) {
        // For attack animations, use onFrameChange for precise timing
        let impactTriggered = false;
        
        sprite.onFrameChange = (currentFrame: number) => {
          const frameProgress = AnimationTimingUtils.calculateFrameProgress(
            currentFrame, 
            sprite.totalFrames
          );
          
          // Trigger impact event at 40% through attack animation
          if (!impactTriggered && AnimationTimingUtils.isImpactFrame(currentFrame, sprite.totalFrames)) {
            impactTriggered = true;
            onImpactFrame(frameProgress);
          }
        };
      }
      
      // Set up completion callback
      if (onComplete) {
        sprite.onComplete = onComplete;
      }
    }
    
    // For looping animations, no callbacks needed to prevent store updates
  }
} 