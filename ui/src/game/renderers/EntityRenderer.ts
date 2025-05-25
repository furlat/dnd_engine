import { Container, AnimatedSprite, Assets, Spritesheet, Ticker } from 'pixi.js';
import { battlemapStore } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { AnimationState, Direction, EntitySpriteMapping } from '../../types/battlemap_types';
import { LayerName } from '../BattlemapEngine';
import { EntitySummary } from '../../types/common';
import { getSpriteSheetPath } from '../../api/battlemap/battlemapApi';

/**
 * EntityRenderer handles rendering animated sprites for entities
 */
export class EntityRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'entities'; }
  
  // Entity management
  private entityContainers: Map<string, Container> = new Map();
  private animatedSprites: Map<string, AnimatedSprite> = new Map();
  private loadedSpritesheets: Map<string, Spritesheet> = new Map();
  
  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];
  
  // MEMOIZATION: Track last seen entity data to prevent unnecessary re-renders
  private lastEntityData: Map<string, string> = new Map(); // entityId -> JSON hash
  private lastSpriteMappingData: Map<string, string> = new Map(); // entityId -> JSON hash
  
  // Summary logging system
  private lastSummaryTime = 0;
  private renderCount = 0;
  private subscriptionFireCount = 0;
  private actualChangeCount = 0;
  
  initialize(engine: any): void {
    super.initialize(engine);
    console.log('[EntityRenderer] Initializing');
    
    // Subscribe to store changes
    this.setupSubscriptions();
  }
  
  /**
   * Set up subscriptions to store changes
   */
  private setupSubscriptions(): void {
    // Subscribe to entities state changes with memoization
    const unsubEntities = subscribe(battlemapStore.entities, () => {
      this.subscriptionFireCount++;
      // Check if entities actually changed before triggering render
      if (this.hasEntitiesActuallyChanged()) {
        this.actualChangeCount++;
        this.render();
      }
      this.logSummary();
    });
    this.unsubscribeCallbacks.push(unsubEntities);
    
    // Subscribe to view changes for positioning - just like TileRenderer and GridRenderer
    const unsubView = subscribe(battlemapStore.view, () => {
      this.updateEntityPositions();
      // Don't call render() here - position updates don't need full re-render
    });
    this.unsubscribeCallbacks.push(unsubView);
    
    // Also subscribe to grid changes in case grid size affects positioning
    const unsubGrid = subscribe(battlemapStore.grid, () => {
      this.updateEntityPositions();
      // Don't call render() here - position updates don't need full re-render
    });
    this.unsubscribeCallbacks.push(unsubGrid);
  }
  
  /**
   * Main render method - only called when entities actually change
   */
  render(): void {
    this.renderCount++;
    
    // Skip if not properly initialized
    if (!this.engine || !this.engine.app) {
      return;
    }
    
    const snap = battlemapStore;
    const entities = Object.values(snap.entities.summaries) as EntitySummary[];
    const spriteMappings = snap.entities.spriteMappings;
    
    // Process each entity
    entities.forEach(entity => {
      const mapping = spriteMappings[entity.uuid];
      
      if (mapping) {
        // Entity has a sprite mapping, ensure it's rendered
        this.ensureEntityRendered(entity, mapping);
      } else {
        // Entity has no sprite mapping, remove from rendering if exists
        this.removeEntityFromRendering(entity.uuid);
      }
    });
    
    // Clean up entities that no longer exist
    this.cleanupRemovedEntities(entities.map(e => e.uuid));
  }
  
  /**
   * Ensure an entity with sprite mapping is properly rendered
   */
  private async ensureEntityRendered(entity: EntitySummary, mapping: EntitySpriteMapping): Promise<void> {
    try {
      // Check if entity container exists
      let entityContainer = this.entityContainers.get(entity.uuid);
      
      if (!entityContainer) {
        // Create new entity container
        entityContainer = new Container();
        this.entityContainers.set(entity.uuid, entityContainer);
        this.container.addChild(entityContainer);
      }
      
      // Load sprite if not already loaded or if mapping changed
      await this.loadEntitySprite(entity, mapping);
      
      // Update entity position
      this.updateEntityPosition(entity);
      
    } catch (error) {
      console.error(`[EntityRenderer] Error ensuring entity ${entity.uuid} is rendered:`, error);
    }
  }
  
  /**
   * Load sprite for an entity - IMPROVED to reuse existing sprites
   */
  private async loadEntitySprite(entity: EntitySummary, mapping: EntitySpriteMapping): Promise<void> {
    const spriteKey = `${mapping.spriteFolder}_${mapping.currentAnimation}_${mapping.currentDirection}`;
    
    try {
      const spritesheetPath = getSpriteSheetPath(mapping.spriteFolder, mapping.currentAnimation);
      
      try {
        // Check if we already have this spritesheet loaded
        const spritesheetKey = `${mapping.spriteFolder}_${mapping.currentAnimation}`;
        let spritesheet = this.loadedSpritesheets.get(spritesheetKey);
        
        if (!spritesheet) {
          // Load the spritesheet only if not already loaded
          try {
            const loadedSpritesheet = await Assets.load<Spritesheet>(spritesheetPath);
            if (!loadedSpritesheet) {
              console.error(`[EntityRenderer] Assets.load returned undefined for ${spritesheetPath}`);
              return;
            }
            spritesheet = loadedSpritesheet;
            this.loadedSpritesheets.set(spritesheetKey, spritesheet);
          } catch (error) {
            console.error(`[EntityRenderer] Failed to load spritesheet ${spritesheetPath}:`, error);
            return;
          }
        } else {
          // Spritesheet already cached
        }
        
        // Ensure spritesheet is loaded before proceeding
        if (!spritesheet) {
          console.error(`[EntityRenderer] Spritesheet is undefined for ${spritesheetKey}`);
          return;
        }
        
        // Get the textures for the current direction (spritesheet is guaranteed to be defined here)
        // Get the textures for the current direction
        const directionTextures = this.getDirectionTextures(spritesheet, mapping.currentDirection);
        
        if (directionTextures.length === 0) {
          console.warn(`[EntityRenderer] No textures found for direction ${mapping.currentDirection} in ${spritesheetKey}`);
          return;
        }
        
        // Get or create animated sprite for this entity
        let animatedSprite = this.animatedSprites.get(entity.uuid);
        
        if (!animatedSprite) {
          // Create new animated sprite only if none exists
          console.log(`[EntityRenderer] CREATING NEW SPRITE for ${entity.name} with animation ${mapping.currentAnimation}`);
          animatedSprite = new AnimatedSprite(directionTextures);
          animatedSprite.name = spriteKey;
          animatedSprite.anchor.set(0.5, 1.0); // Bottom-center anchor for character sprites
          
          // Set initial scale from mapping with zoom-dependent scaling
          const userScaleMultiplier = mapping.scale || 1.0; // Default to 1.0
          if (directionTextures.length > 0 && 'frame' in directionTextures[0]) {
            // Calculate zoom-dependent scale like the old React component
            const BASE_SCALE = 2.4; // Same as old React component: 2.0 * 1.2 (20% larger)
            const textureWidth = directionTextures[0].frame.width;
            const textureHeight = directionTextures[0].frame.height;
            const { tileSize } = this.calculateGridOffset();
            const zoomDependentScale = (tileSize / Math.max(textureWidth, textureHeight)) * BASE_SCALE;
            const finalScale = zoomDependentScale * userScaleMultiplier;
            animatedSprite.scale.set(finalScale);
          } else {
            // Fallback scale
            animatedSprite.scale.set(userScaleMultiplier);
          }
          
          // Use PixiJS v8 API properly - simple and direct
          animatedSprite.autoUpdate = true; // Let PixiJS handle updates
          animatedSprite.loop = this.shouldLoop(mapping.currentAnimation);
          
          // Calculate animation speed based on desired duration from slider
          const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
          // animationSpeed controls how fast frames advance
          // For 15 frames to play over desiredDurationSeconds:
          // We need to advance 15 frames in desiredDurationSeconds
          // PixiJS animationSpeed is frames per second / 60fps
          const framesPerSecond = directionTextures.length / desiredDurationSeconds;
          animatedSprite.animationSpeed = framesPerSecond / 60; // PixiJS expects speed relative to 60fps
          
          console.log(`[EntityRenderer] Setting animation speed to ${animatedSprite.animationSpeed.toFixed(3)} for ${desiredDurationSeconds}s duration (${directionTextures.length} frames, ${framesPerSecond.toFixed(1)} fps)`);
          
          // Set up animation callbacks
          this.setupAnimationCallbacks(animatedSprite, entity, mapping);
          
          // Start playing
          console.log(`[EntityRenderer] STARTING ANIMATION for ${entity.name}: ${mapping.currentAnimation} (${directionTextures.length} frames)`);
          animatedSprite.play();
          
          // Add to entity container
          const entityContainer = this.entityContainers.get(entity.uuid);
          if (entityContainer) {
            entityContainer.addChild(animatedSprite);
            this.animatedSprites.set(entity.uuid, animatedSprite);
          }
        } else {
          // Reuse existing sprite - check what actually changed
          console.log(`[EntityRenderer] REUSING SPRITE for ${entity.name}, checking what changed for ${mapping.currentAnimation}`);
          
          // Check if textures actually changed (animation or direction change)
          const currentTextures = animatedSprite.textures;
          const texturesChanged = currentTextures.length !== directionTextures.length || 
            currentTextures.some((tex, i) => tex !== directionTextures[i]);
          
          // Check if this is just a duration/scale change vs animation/direction change
          const currentSpriteKey = animatedSprite.name;
          const animationOrDirectionChanged = currentSpriteKey !== spriteKey;
          
          if (texturesChanged || animationOrDirectionChanged) {
            console.log(`[EntityRenderer] ANIMATION/DIRECTION CHANGED for ${entity.name} - RESTARTING ANIMATION`);
            animatedSprite.stop(); // Stop current animation
            animatedSprite.textures = directionTextures; // Update textures
            animatedSprite.name = spriteKey; // Update name for tracking
            animatedSprite.autoUpdate = true; // Let PixiJS handle updates
            animatedSprite.loop = this.shouldLoop(mapping.currentAnimation);
            
            // Calculate animation speed based on desired duration from slider
            const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
            // animationSpeed controls how fast frames advance
            // For 15 frames to play over desiredDurationSeconds:
            // We need to advance 15 frames in desiredDurationSeconds
            // PixiJS animationSpeed is frames per second / 60fps
            const framesPerSecond = directionTextures.length / desiredDurationSeconds;
            animatedSprite.animationSpeed = framesPerSecond / 60; // PixiJS expects speed relative to 60fps
            
            console.log(`[EntityRenderer] Setting animation speed to ${animatedSprite.animationSpeed.toFixed(3)} for ${desiredDurationSeconds}s duration (${directionTextures.length} frames, ${framesPerSecond.toFixed(1)} fps)`);
            
            // Set up animation callbacks
            this.setupAnimationCallbacks(animatedSprite, entity, mapping);
            
            // Start playing
            console.log(`[EntityRenderer] STARTING ANIMATION for ${entity.name}: ${mapping.currentAnimation} (${directionTextures.length} frames)`);
            animatedSprite.play();
          } else {
            console.log(`[EntityRenderer] ONLY DURATION/SCALE CHANGED for ${entity.name} - UPDATING ANIMATION SPEED`);
            // Update animation speed based on new duration without restarting animation
            const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
            const currentFrames = animatedSprite.totalFrames;
            const framesPerSecond = currentFrames / desiredDurationSeconds;
            animatedSprite.animationSpeed = framesPerSecond / 60; // PixiJS expects speed relative to 60fps
            console.log(`[EntityRenderer] Updated animation speed to ${animatedSprite.animationSpeed.toFixed(3)} for ${desiredDurationSeconds}s duration (${currentFrames} frames, ${framesPerSecond.toFixed(1)} fps)`);
            return;
          }
        }
        
      } catch (error) {
        console.error(`[EntityRenderer] Error loading sprite for entity ${entity.uuid}:`, error);
      }
    } catch (error) {
      console.error(`[EntityRenderer] Error loading sprite for entity ${entity.uuid}:`, error);
    }
  }
  
  /**
   * Get textures for a specific direction from a spritesheet
   */
  private getDirectionTextures(spritesheet: Spritesheet, direction: Direction) {
    const textures = spritesheet.textures;
    const directionTextures = [];
    
    // Look for textures with the direction pattern
    // Pattern: AnimationName_Direction_FrameNumber.png
    const pattern = new RegExp(`_${direction}_\\d+\\.png$`);
    
    for (const [textureName, texture] of Object.entries(textures)) {
      if (pattern.test(textureName)) {
        directionTextures.push(texture);
      }
    }
    
    // Sort by frame number extracted from texture name
    directionTextures.sort((a, b) => {
      // Get the first cache ID which should be the original texture name
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
   * Determine if an animation should loop
   * FOR DEBUGGING: Making all animations loop so we can see them properly
   */
  private shouldLoop(animation: AnimationState): boolean {
    // FOR DEBUGGING: Make everything loop
    return true;
    
    // Original logic (commented out for debugging):
    // switch (animation) {
    //   case AnimationState.IDLE:
    //   case AnimationState.IDLE2:
    //   case AnimationState.WALK:
    //   case AnimationState.RUN:
    //   case AnimationState.RUN_BACKWARDS:
    //   case AnimationState.CROUCH_RUN:
    //     return true;
    //     
    //   case AnimationState.ATTACK1:
    //   case AnimationState.ATTACK2:
    //   case AnimationState.ATTACK3:
    //   case AnimationState.TAKE_DAMAGE:
    //   case AnimationState.DIE:
    //     return false;
    //     
    //   default:
    //     return false;
    // }
  }
  
  /**
   * Set up animation callbacks
   */
  private setupAnimationCallbacks(sprite: AnimatedSprite, entity: EntitySummary, mapping: EntitySpriteMapping): void {
    const startTime = Date.now();
    
    sprite.onComplete = () => {
      const totalTime = Date.now() - startTime;
      console.log(`[EntityRenderer] Animation ${mapping.currentAnimation} completed for ${entity.name} after ${totalTime}ms`);
      
      // Handle animation completion
      if (!this.shouldLoop(mapping.currentAnimation)) {
        // Non-looping animations should transition back to idle
        console.log(`[EntityRenderer] Animation ${mapping.currentAnimation} completed for ${entity.name}, transitioning to IDLE`);
        // TODO: Update the store to change animation state to IDLE
        // battlemapActions.setEntityAnimation(entity.uuid, AnimationState.IDLE);
      };
    };
    
    sprite.onLoop = () => {
      const loopTime = Date.now() - startTime;
      console.log(`[EntityRenderer] Animation ${mapping.currentAnimation} looped for ${entity.name} after ${loopTime}ms (frames: ${sprite.totalFrames}, speed: ${sprite.animationSpeed})`);
    };
  }
  
  /**
   * Update entity position on screen - FIXED positioning to align with tiles
   */
  private updateEntityPosition(entity: EntitySummary): void {
    const entityContainer = this.entityContainers.get(entity.uuid);
    if (!entityContainer) {
      console.warn(`[EntityRenderer] No container found for entity ${entity.uuid} when updating position`);
      return;
    }

    const snap = battlemapStore;
    const { offsetX, offsetY, tileSize } = this.calculateGridOffset();
    
    // Convert entity position to screen coordinates
    // Position sprite more south by adding extra offset to Y position
    // Since anchor is bottom-center (0.5, 1.0), this aligns the sprite's feet with the tile bottom
    const screenX = offsetX + (entity.position[0] * tileSize) + (tileSize / 2); // Center horizontally in tile
    const screenY = offsetY + (entity.position[1] * tileSize) + tileSize + (tileSize * 0.2); // Bottom of tile + 20% more south
    
    entityContainer.x = screenX;
    entityContainer.y = screenY;
    
    // Update sprite scale - make it zoom-dependent like the old React component
    const animatedSprite = this.animatedSprites.get(entity.uuid);
    if (animatedSprite) {
      // Get sprite mapping for user-defined scale multiplier
      const mapping = snap.entities.spriteMappings[entity.uuid];
      const userScaleMultiplier = mapping?.scale || 1.0; // Default to 1.0
      
      // Calculate zoom-dependent scale like the old React component did
      // Base scale calculation: make sprite fit within tile size
      const spriteTexture = animatedSprite.textures[0]; // Get first texture for size reference
      if (spriteTexture && 'frame' in spriteTexture) {
        // Calculate base scale to fit sprite to tile size (like old React component)
        const BASE_SCALE = 2.4; // Same as old React component: 2.0 * 1.2 (20% larger)
        // Use frame dimensions for PixiJS v8 Texture
        const textureWidth = spriteTexture.frame.width;
        const textureHeight = spriteTexture.frame.height;
        const zoomDependentScale = (tileSize / Math.max(textureWidth, textureHeight)) * BASE_SCALE;
        
        // Apply both zoom-dependent scale and user scale multiplier
        const finalScale = zoomDependentScale * userScaleMultiplier;
        animatedSprite.scale.set(finalScale);
      } else {
        // Fallback if no texture available or it's a FrameObject
        animatedSprite.scale.set(userScaleMultiplier);
      }
    }
  }
  
  /**
   * Update all entity positions (called on view changes)
   */
  private updateEntityPositions(): void {
    const snap = battlemapStore;
    const entities = Object.values(snap.entities.summaries) as EntitySummary[];
    
    entities.forEach(entity => {
      // Only update entities that have containers (are being rendered)
      if (this.entityContainers.has(entity.uuid)) {
        this.updateEntityPosition(entity);
      }
    });
  }
  
  /**
   * Calculate grid offset (same as other renderers)
   */
  private calculateGridOffset(): { offsetX: number; offsetY: number; tileSize: number } {
    const snap = battlemapStore;
    const ENTITY_PANEL_WIDTH = 250;
    
    // Get container size from engine
    const containerSize = this.engine?.containerSize || { width: 0, height: 0 };
    
    const availableWidth = containerSize.width - ENTITY_PANEL_WIDTH;
    const gridPixelWidth = snap.grid.width * snap.view.tileSize;
    const gridPixelHeight = snap.grid.height * snap.view.tileSize;
    
    // Center grid in the available space
    const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
    const baseOffsetY = (containerSize.height - gridPixelHeight) / 2;
    
    // Apply the offset from WASD controls
    const offsetX = baseOffsetX + snap.view.offset.x;
    const offsetY = baseOffsetY + snap.view.offset.y;
    
    return { offsetX, offsetY, tileSize: snap.view.tileSize };
  }
  
  /**
   * Remove entity from rendering
   */
  private removeEntityFromRendering(entityId: string): void {
    const entityContainer = this.entityContainers.get(entityId);
    const animatedSprite = this.animatedSprites.get(entityId);
    
    if (entityContainer) {
      this.container.removeChild(entityContainer);
      entityContainer.destroy();
      this.entityContainers.delete(entityId);
    }
    
    if (animatedSprite) {
      animatedSprite.destroy();
      this.animatedSprites.delete(entityId);
    }
  }
  
  /**
   * Clean up entities that no longer exist
   */
  private cleanupRemovedEntities(currentEntityIds: string[]): void {
    const renderedEntityIds = Array.from(this.entityContainers.keys());
    
    renderedEntityIds.forEach(entityId => {
      if (!currentEntityIds.includes(entityId)) {
        this.removeEntityFromRendering(entityId);
      }
    });
  }
  
  /**
   * Check if entities have actually changed by comparing JSON hashes
   * This prevents unnecessary re-renders when polling creates new objects with same data
   */
  private hasEntitiesActuallyChanged(): boolean {
    const snap = battlemapStore;
    let hasChanges = false;
    
    // Check entity summaries
    for (const [entityId, entity] of Object.entries(snap.entities.summaries)) {
      const entityHash = JSON.stringify({
        uuid: entity.uuid,
        name: entity.name,
        position: entity.position,
        // Add other relevant fields that affect rendering
      });
      
      const lastHash = this.lastEntityData.get(entityId);
      if (lastHash !== entityHash) {
        console.log(`[EntityRenderer] Entity ${entity.name} data changed (position/name/etc)`);
        this.lastEntityData.set(entityId, entityHash);
        hasChanges = true;
      }
    }
    
    // Check sprite mappings
    for (const [entityId, mapping] of Object.entries(snap.entities.spriteMappings)) {
      const mappingHash = JSON.stringify({
        spriteFolder: mapping.spriteFolder,
        currentAnimation: mapping.currentAnimation,
        currentDirection: mapping.currentDirection,
        scale: mapping.scale,
        animationDurationSeconds: mapping.animationDurationSeconds,
      });
      
      const lastMappingHash = this.lastSpriteMappingData.get(entityId);
      if (lastMappingHash !== mappingHash) {
        console.log(`[EntityRenderer] Entity ${entityId} sprite mapping changed:`, {
          animation: mapping.currentAnimation,
          direction: mapping.currentDirection,
          duration: mapping.animationDurationSeconds
        });
        this.lastSpriteMappingData.set(entityId, mappingHash);
        hasChanges = true;
      }
    }
    
    // Check for removed entities
    const currentEntityIds = new Set(Object.keys(snap.entities.summaries));
    for (const entityId of Array.from(this.lastEntityData.keys())) {
      if (!currentEntityIds.has(entityId)) {
        console.log(`[EntityRenderer] Entity ${entityId} was removed`);
        this.lastEntityData.delete(entityId);
        this.lastSpriteMappingData.delete(entityId);
        hasChanges = true;
      }
    }
    
    return hasChanges;
  }
  
  /**
   * Log summary every 10 seconds instead of spamming
   */
  private logSummary(): void {
    const now = Date.now();
    if (now - this.lastSummaryTime >= 10000) { // 10 seconds
      console.log(`[EntityRenderer] 10s Summary: ${this.renderCount} renders, ${this.subscriptionFireCount} subscription fires, ${this.actualChangeCount} actual changes`);
      this.lastSummaryTime = now;
      this.renderCount = 0;
      this.subscriptionFireCount = 0;
      this.actualChangeCount = 0;
    }
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // Clean up all entities
    this.entityContainers.forEach((container, entityId) => {
      this.removeEntityFromRendering(entityId);
    });
    
    // Clean up spritesheets
    this.loadedSpritesheets.forEach(spritesheet => {
      spritesheet.destroy();
    });
    this.loadedSpritesheets.clear();
    
    // Unsubscribe from store changes
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
    // Call parent destroy
    super.destroy();
    
    console.log('[EntityRenderer] Destroyed');
  }
} 