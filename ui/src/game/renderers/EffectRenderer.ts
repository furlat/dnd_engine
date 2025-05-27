import { Container, AnimatedSprite, Assets, Spritesheet, Ticker, Texture, Graphics, Sprite } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { EffectAnimation, EffectType, EffectCategory, VisualPosition, toVisualPosition, getEffectPath, shouldEffectLoop, getEffectCategory, getDefaultEffectDuration, Direction } from '../../types/battlemap_types';
import { LayerName } from '../BattlemapEngine';
import { EntitySummary, Position } from '../../types/common';
import { calculateIsometricGridOffset, gridToIsometric } from '../../utils/isometricUtils';

/**
 * Cached effect sprite data using PixiJS v8 Assets cache properly
 * Key format: "effectType" for consistent cache management
 */
interface CachedEffectData {
  spritesheet: Spritesheet;
  textures: Texture[];
  cacheKey: string; // For proper cleanup
}

/**
 * EffectRenderer with optimized PixiJS v8 cache management and sophisticated effect handling
 * Supports both temporary effects (blood splat, sparks) and permanent effects (auras, shields)
 */
export class EffectRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to (we'll use both below_effects and above_effects)
  get layerName(): LayerName { return 'below_effects'; } // Default layer, but we'll manage both
  
  // Enable ticker updates for effect animations
  protected needsTickerUpdate: boolean = true;
  
  // Layer management for isometric perspective
  private belowEffectsLayer: Container | null = null;
  private aboveEffectsLayer: Container | null = null;
  
  // Effect management
  private effectContainers: Map<string, Container> = new Map(); // effectId -> Container
  private animatedSprites: Map<string, AnimatedSprite> = new Map(); // effectId -> AnimatedSprite
  
  // OPTIMIZED: Use PixiJS Assets cache with proper key management
  private effectCacheByKey: Map<string, CachedEffectData> = new Map(); // key: effectType
  
  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];
  
  // MEMOIZATION: Track last seen effect data to prevent unnecessary re-renders
  private lastEffectData: Map<string, string> = new Map(); // effectId -> JSON hash
  private lastPermanentEffectData: Map<string, string> = new Map(); // entityId -> JSON hash
  
  // Summary logging system
  private lastSummaryTime = 0;
  private renderCount = 0;
  private subscriptionFireCount = 0;
  private actualChangeCount = 0;
  
  initialize(engine: any): void {
    super.initialize(engine);
    console.log('[EffectRenderer] Initializing with PixiJS v8 Assets cache management and dual-layer support');
    
    // Get both effect layers for isometric perspective
    this.belowEffectsLayer = this.engine?.getLayer('below_effects') || null;
    this.aboveEffectsLayer = this.engine?.getLayer('above_effects') || null;
    
    if (!this.belowEffectsLayer || !this.aboveEffectsLayer) {
      console.error('[EffectRenderer] Failed to get effect layers');
      return;
    }
    
    console.log('[EffectRenderer] Successfully acquired both effect layers');
    
    // Subscribe to store changes
    this.setupSubscriptions();
  }
  
  /**
   * Update method called every frame by ticker for effect animations
   */
  update(ticker: Ticker): void {
    if (!this.engine || !this.engine.app) return;
    
    const snap = battlemapStore;
    const activeEffects = snap.effects.activeEffects;
    
    // Update all active temporary effects
    Object.values(activeEffects).forEach(effect => {
      if (effect.category === EffectCategory.TEMPORARY) {
        this.updateTemporaryEffect(effect, ticker.deltaTime);
      }
    });
    
    // Update attached effects positions
    this.updateAttachedEffects();
  }
  
  /**
   * Determine if defender shows front or back based on attacker position
   * From defender's perspective (defender is center):
   * - If attacker is NE, E, SE, S, SW relative to defender: defender shows FRONT
   * - If attacker is W, NW, N relative to defender: defender shows BACK
   * 
   * @param attackerPosition Position of the attacker
   * @param defenderPosition Position of the defender
   * @returns true if defender shows front, false if defender shows back
   */
  private isDefenderShowingFront(attackerPosition: readonly [number, number], defenderPosition: readonly [number, number]): boolean {
    // Calculate attacker position relative to defender (defender is center)
    const dx = attackerPosition[0] - defenderPosition[0];
    const dy = attackerPosition[1] - defenderPosition[1];
    
    // Determine attacker's direction relative to defender
    let attackerDirection: Direction;
    if (dx > 0 && dy > 0) attackerDirection = Direction.SE;
    else if (dx > 0 && dy < 0) attackerDirection = Direction.NE;
    else if (dx < 0 && dy > 0) attackerDirection = Direction.SW;
    else if (dx < 0 && dy < 0) attackerDirection = Direction.NW;
    else if (dx === 0 && dy > 0) attackerDirection = Direction.S;
    else if (dx === 0 && dy < 0) attackerDirection = Direction.N;
    else if (dx > 0 && dy === 0) attackerDirection = Direction.E;
    else if (dx < 0 && dy === 0) attackerDirection = Direction.W;
    else attackerDirection = Direction.S; // Default
    
    // Determine if defender shows front or back
    return attackerDirection === Direction.NE || 
           attackerDirection === Direction.E || 
           attackerDirection === Direction.SE || 
           attackerDirection === Direction.S || 
           attackerDirection === Direction.SW;
  }

  /**
   * Determine which layer to use for blood effects based on attacker position relative to defender
   * From defender's perspective (defender is center):
   * - If attacker is NE, E, SE, S, SW relative to defender: use BELOW layer (defender shows front)
   * - If attacker is W, NW, N relative to defender: use ABOVE layer (defender shows back to camera)
   * 
   * @param attackerPosition Position of the attacker
   * @param defenderPosition Position of the defender
   * @returns The appropriate layer container
   */
  private getBloodEffectLayer(attackerPosition: readonly [number, number], defenderPosition: readonly [number, number]): Container {
    const defenderShowsFront = this.isDefenderShowingFront(attackerPosition, defenderPosition);
    
    if (defenderShowsFront) {
      // Defender shows front -> blood goes below
      console.log(`[EffectRenderer] Defender shows front -> blood below entity (below_effects)`);
      return this.belowEffectsLayer!;
    } else {
      // Defender shows back -> blood goes above
      console.log(`[EffectRenderer] Defender shows back -> blood above entity (above_effects)`);
      return this.aboveEffectsLayer!;
    }
  }

  /**
   * Update a temporary effect animation (check for completion)
   */
  private updateTemporaryEffect(effect: EffectAnimation, deltaTime: number): void {
    const currentTime = Date.now();
    const elapsedTime = currentTime - effect.startTime;
    const duration = effect.duration || getDefaultEffectDuration(effect.effectType);
    
    // Handle movement animation for blood droplets
    if (effect.effectType === EffectType.BLOOD_SPLAT && (effect.offsetX || effect.offsetY)) {
      const progress = Math.min(elapsedTime / duration, 1.0);
      
      // Use easing for more natural falling motion (gravity effect)
      const easedProgress = progress * progress; // Quadratic easing for acceleration
      
      // Calculate current position based on progress
      const currentPosition: VisualPosition = {
        x: effect.position.x + (effect.offsetX || 0) * easedProgress,
        y: effect.position.y + (effect.offsetY || 0) * easedProgress
      };
      
      // Update the effect's visual position
      this.updateEffectVisualPosition(effect.effectId, currentPosition);
    }
    
    // Check if effect should complete
    if (elapsedTime >= duration) {
      console.log(`[EffectRenderer] Temporary effect ${effect.effectType} completed after ${elapsedTime}ms`);
      this.completeEffect(effect.effectId);
    }
  }
  
  /**
   * Update positions of effects attached to entities
   */
  private updateAttachedEffects(): void {
    const snap = battlemapStore;
    
    // Update attached effects from active effects
    Object.values(snap.effects.activeEffects).forEach(effect => {
      if (effect.attachedToEntityId) {
        this.updateAttachedEffectPosition(effect);
      }
    });
    
    // Update permanent effects attached to entities
    Object.entries(snap.entities.permanentEffects).forEach(([entityId, effectTypes]) => {
      effectTypes.forEach(effectType => {
        const effectId = `permanent_${entityId}_${effectType}`;
        const effectContainer = this.effectContainers.get(effectId);
        if (effectContainer) {
          this.updatePermanentEffectPosition(entityId, effectContainer);
        }
      });
    });
  }
  
  /**
   * Update position of an attached effect based on entity position
   */
  private updateAttachedEffectPosition(effect: EffectAnimation): void {
    if (!effect.attachedToEntityId) return;
    
    const entity = battlemapStore.entities.summaries[effect.attachedToEntityId];
    const spriteMapping = battlemapStore.entities.spriteMappings[effect.attachedToEntityId];
    const effectContainer = this.effectContainers.get(effect.effectId);
    
    if (!entity || !effectContainer) return;
    
    // Use visual position if available and not synced, otherwise use server position
    let entityPosition: VisualPosition;
    if (spriteMapping?.visualPosition && !spriteMapping.isPositionSynced) {
      entityPosition = spriteMapping.visualPosition;
    } else {
      entityPosition = toVisualPosition(entity.position);
    }
    
    // Apply offset
    const finalPosition: VisualPosition = {
      x: entityPosition.x + (effect.offsetX || 0),
      y: entityPosition.y + (effect.offsetY || 0)
    };
    
    this.updateEffectVisualPosition(effect.effectId, finalPosition);
  }
  
  /**
   * Update position of a permanent effect based on entity position
   */
  private updatePermanentEffectPosition(entityId: string, effectContainer: Container): void {
    const entity = battlemapStore.entities.summaries[entityId];
    const spriteMapping = battlemapStore.entities.spriteMappings[entityId];
    
    if (!entity) return;
    
    // Use visual position if available and not synced, otherwise use server position
    let entityPosition: VisualPosition;
    if (spriteMapping?.visualPosition && !spriteMapping.isPositionSynced) {
      entityPosition = spriteMapping.visualPosition;
    } else {
      entityPosition = toVisualPosition(entity.position);
    }
    
    this.updateEffectContainerPosition(effectContainer, entityPosition);
  }
  
  /**
   * Complete an effect animation
   */
  private completeEffect(effectId: string): void {
    console.log(`[EffectRenderer] Effect completed: ${effectId}`);
    
    // Complete effect in store (this will trigger callback and remove from active effects)
    battlemapActions.completeEffect(effectId);
  }
  
  /**
   * Set up subscriptions to store changes
   */
  private setupSubscriptions(): void {
    // Subscribe to active effects changes with memoization
    const unsubActiveEffects = subscribe(battlemapStore.effects.activeEffects, () => {
      this.subscriptionFireCount++;
      // Check if effects actually changed before triggering render
      if (this.hasActiveEffectsActuallyChanged()) {
        this.actualChangeCount++;
        this.render();
      }
      this.logSummary();
    });
    this.unsubscribeCallbacks.push(unsubActiveEffects);
    
    // Subscribe to permanent effects changes
    const unsubPermanentEffects = subscribe(battlemapStore.entities.permanentEffects, () => {
      this.subscriptionFireCount++;
      // Check if permanent effects actually changed before triggering render
      if (this.hasPermanentEffectsActuallyChanged()) {
        this.actualChangeCount++;
        this.render();
      }
      this.logSummary();
    });
    this.unsubscribeCallbacks.push(unsubPermanentEffects);
    
    // Subscribe to view changes for positioning - just like other renderers
    const unsubView = subscribe(battlemapStore.view, () => {
      this.updateEffectPositions();
      // Don't call render() here - position updates don't need full re-render
    });
    this.unsubscribeCallbacks.push(unsubView);
    
    // Also subscribe to grid changes in case grid size affects positioning
    const unsubGrid = subscribe(battlemapStore.grid, () => {
      this.updateEffectPositions();
      // Don't call render() here - position updates don't need full re-render
    });
    this.unsubscribeCallbacks.push(unsubGrid);
  }
  
  /**
   * Main render method - only called when effects actually change
   */
  render(): void {
    this.renderCount++;
    
    // Skip if not properly initialized
    if (!this.engine || !this.engine.app) {
      return;
    }
    
    const snap = battlemapStore;
    
    // Process active effects
    Object.values(snap.effects.activeEffects).forEach(effect => {
      this.ensureEffectRendered(effect);
    });
    
    // Process permanent effects attached to entities
    Object.entries(snap.entities.permanentEffects).forEach(([entityId, effectTypes]) => {
      effectTypes.forEach(effectType => {
        this.ensurePermanentEffectRendered(entityId, effectType);
      });
    });
    
    // Clean up effects that no longer exist
    this.cleanupRemovedEffects();
  }
  
  /**
   * Ensure an active effect is properly rendered
   */
  private async ensureEffectRendered(effect: EffectAnimation): Promise<void> {
    try {
      // Check if effect container exists
      let effectContainer = this.effectContainers.get(effect.effectId);
      
      if (!effectContainer) {
        // Create new effect container
        effectContainer = new Container();
        this.effectContainers.set(effect.effectId, effectContainer);
        
        // Determine which layer to add the container to
        let targetLayer: Container;
        
        if (effect.effectType === EffectType.BLOOD_SPLAT) {
          // For blood effects, we need attacker and defender positions to determine layer
          // This information should be passed in the effect metadata
          if (effect.attackerPosition && effect.defenderPosition) {
            targetLayer = this.getBloodEffectLayer(effect.attackerPosition, effect.defenderPosition);
          } else {
            // Fallback to below layer if positions not available
            console.warn(`[EffectRenderer] Blood effect ${effect.effectId} missing position data, using below layer`);
            targetLayer = this.belowEffectsLayer!;
          }
        } else {
          // Non-blood effects default to below layer
          targetLayer = this.belowEffectsLayer!;
        }
        
        targetLayer.addChild(effectContainer);
      }
      
      // Load effect sprite if not already loaded
      await this.loadEffectSprite(effect);
      
      // Update effect position
      this.updateEffectPosition(effect);
      
    } catch (error) {
      console.error(`[EffectRenderer] Error ensuring effect ${effect.effectId} is rendered:`, error);
    }
  }
  
  /**
   * Ensure a permanent effect attached to an entity is properly rendered
   */
  private async ensurePermanentEffectRendered(entityId: string, effectType: EffectType): Promise<void> {
    const effectId = `permanent_${entityId}_${effectType}`;
    
    try {
      // Check if effect container exists
      let effectContainer = this.effectContainers.get(effectId);
      
      if (!effectContainer) {
        // Create new effect container
        effectContainer = new Container();
        this.effectContainers.set(effectId, effectContainer);
        
        // Permanent effects default to below layer (most common case)
        this.belowEffectsLayer!.addChild(effectContainer);
      }
      
      // Create pseudo effect animation for loading
      const entity = battlemapStore.entities.summaries[entityId];
      if (!entity) return;
      
      const pseudoEffect: EffectAnimation = {
        effectId,
        effectType,
        category: EffectCategory.PERMANENT,
        position: toVisualPosition(entity.position),
        startTime: Date.now(),
        attachedToEntityId: entityId,
        scale: 1.0,
        alpha: 0.8, // Slightly transparent for permanent effects
      };
      
      // Load effect sprite
      await this.loadEffectSprite(pseudoEffect);
      
      // Update effect position
      this.updatePermanentEffectPosition(entityId, effectContainer);
      
    } catch (error) {
      console.error(`[EffectRenderer] Error ensuring permanent effect ${effectType} for entity ${entityId} is rendered:`, error);
    }
  }
  
  /**
   * Create consistent cache key for effect data
   */
  private createCacheKey(effectType: EffectType): string {
    return effectType;
  }
  
  /**
   * OPTIMIZED: Load effect sprite with PixiJS v8 Assets cache
   */
  private async loadEffectSprite(effect: EffectAnimation): Promise<void> {
    const cacheKey = this.createCacheKey(effect.effectType);
    
    try {
      // Get or load cached effect data
      let cachedData = this.effectCacheByKey.get(cacheKey);
      
      if (!cachedData) {
        // Load and cache effect data using PixiJS Assets
        const loadedData = await this.loadAndCacheEffectData(effect.effectType, cacheKey);
        if (!loadedData) return;
        
        cachedData = loadedData;
        this.effectCacheByKey.set(cacheKey, cachedData);
        console.log(`[EffectRenderer] Cached effect data for ${cacheKey} with ${cachedData.textures.length} frames`);
      }
      
      // Get or create animated sprite for this effect
      let animatedSprite = this.animatedSprites.get(effect.effectId);
      
      if (!animatedSprite) {
        // Create new animated sprite
        console.log(`[EffectRenderer] Creating new sprite for effect ${effect.effectType} (${effect.effectId})`);
        animatedSprite = this.createAnimatedSprite(effect, cachedData.textures, cacheKey);
        
        // Add to effect container
        const effectContainer = this.effectContainers.get(effect.effectId);
        if (effectContainer) {
          effectContainer.addChild(animatedSprite);
          this.animatedSprites.set(effect.effectId, animatedSprite);
        }
      } else {
        // Update existing sprite if needed
        this.updateExistingSprite(effect, animatedSprite, cachedData.textures);
      }
      
    } catch (error) {
      console.error(`[EffectRenderer] Error loading sprite for effect ${effect.effectId}:`, error);
    }
  }
  
  /**
   * Load and cache effect data using PixiJS v8 Assets
   */
  private async loadAndCacheEffectData(effectType: EffectType, cacheKey: string): Promise<CachedEffectData | null> {
    try {
      const effectPath = getEffectPath(effectType);
      
      // Use unique cache key to prevent conflicts
      const uniqueSpritesheetKey = `effect_${effectType}_spritesheet`;
      
      // Check if already cached with our unique key
      let spritesheet: Spritesheet;
      if (Assets.cache.has(uniqueSpritesheetKey)) {
        spritesheet = Assets.cache.get(uniqueSpritesheetKey);
        console.log(`[EffectRenderer] Using cached spritesheet: ${uniqueSpritesheetKey}`);
      } else {
        // Load with unique key to prevent conflicts
        spritesheet = await Assets.load<Spritesheet>({ alias: uniqueSpritesheetKey, src: effectPath });
        console.log(`[EffectRenderer] Loaded and cached spritesheet: ${uniqueSpritesheetKey} from ${effectPath}`);
      }
      
      if (!spritesheet) {
        console.error(`[EffectRenderer] Failed to load spritesheet: ${effectPath}`);
        return null;
      }
      
      // Extract textures in order
      const textures = this.getOrderedTextures(spritesheet);
      
      return {
        spritesheet,
        textures,
        cacheKey
      };
    } catch (error) {
      console.error(`[EffectRenderer] Error loading effect data:`, error);
      return null;
    }
  }
  
  /**
   * Get textures in proper order from a spritesheet
   */
  private getOrderedTextures(spritesheet: Spritesheet): Texture[] {
    const textures = spritesheet.textures;
    const orderedTextures: Texture[] = [];
    
    // Sort texture names by frame number
    const sortedNames = Object.keys(textures).sort((a, b) => {
      const aMatch = a.match(/_(\d+)\.png$/);
      const bMatch = b.match(/_(\d+)\.png$/);
      const aNum = aMatch ? parseInt(aMatch[1]) : 0;
      const bNum = bMatch ? parseInt(bMatch[1]) : 0;
      return aNum - bNum;
    });
    
    // Add textures in order
    sortedNames.forEach(name => {
      orderedTextures.push(textures[name]);
    });
    
    return orderedTextures;
  }
  
  /**
   * Create a new animated sprite with proper setup
   */
  private createAnimatedSprite(
    effect: EffectAnimation, 
    textures: Texture[], 
    cacheKey: string
  ): AnimatedSprite {
    const animatedSprite = new AnimatedSprite(textures);
    
    animatedSprite.name = `${cacheKey}_${effect.effectId}`;
    animatedSprite.anchor.set(0.5, 0.5); // Center anchor for effects
    
    // Set scale and alpha
    const scale = effect.scale || 1.0;
    animatedSprite.scale.set(scale);
    animatedSprite.alpha = effect.alpha || 1.0;
    
    // Use PixiJS v8 API properly
    animatedSprite.autoUpdate = true;
    
    // Determine if effect should loop
    const shouldLoop = shouldEffectLoop(effect.effectType);
    animatedSprite.loop = shouldLoop;
    
    // Set animation speed (effects are typically faster than entity animations)
    const duration = effect.duration || getDefaultEffectDuration(effect.effectType);
    const framesPerSecond = textures.length / (duration / 1000); // Convert ms to seconds
    animatedSprite.animationSpeed = framesPerSecond / 60; // PixiJS expects speed relative to 60fps
    
    // Set up animation callbacks
    this.setupEffectAnimationCallbacks(animatedSprite, effect);
    
    // Start playing
    console.log(`[EffectRenderer] Starting effect animation: ${effect.effectType} (${textures.length} frames, loop: ${shouldLoop})`);
    animatedSprite.play();
    
    return animatedSprite;
  }
  
  /**
   * Update existing sprite with new data
   */
  private updateExistingSprite(
    effect: EffectAnimation,
    animatedSprite: AnimatedSprite,
    textures: Texture[]
  ): void {
    // Update scale and alpha if changed
    const scale = effect.scale || 1.0;
    const alpha = effect.alpha || 1.0;
    
    if (Math.abs(animatedSprite.scale.x - scale) > 0.001) {
      animatedSprite.scale.set(scale);
    }
    
    if (Math.abs(animatedSprite.alpha - alpha) > 0.001) {
      animatedSprite.alpha = alpha;
    }
  }
  
  /**
   * Set up animation callbacks for effects
   */
  private setupEffectAnimationCallbacks(sprite: AnimatedSprite, effect: EffectAnimation): void {
    // Clear any existing callbacks
    sprite.onComplete = undefined;
    sprite.onLoop = undefined;
    sprite.onFrameChange = undefined;
    
    const shouldLoop = shouldEffectLoop(effect.effectType);
    
    if (!shouldLoop && effect.category === EffectCategory.TEMPORARY) {
      // Temporary effects complete when animation finishes
      sprite.onComplete = () => {
        console.log(`[EffectRenderer] Effect animation completed: ${effect.effectType} (${effect.effectId})`);
        this.completeEffect(effect.effectId);
      };
    }
    
    // For permanent effects, no callbacks needed - they loop indefinitely
  }
  
  /**
   * Update effect position on screen
   */
  private updateEffectPosition(effect: EffectAnimation): void {
    this.updateEffectVisualPosition(effect.effectId, effect.position);
  }
  
  /**
   * Update effect visual position on screen
   */
  private updateEffectVisualPosition(effectId: string, visualPosition: VisualPosition): void {
    const effectContainer = this.effectContainers.get(effectId);
    if (!effectContainer) return;
    
    this.updateEffectContainerPosition(effectContainer, visualPosition);
  }
  
  /**
   * Update effect container position
   */
  private updateEffectContainerPosition(container: Container, visualPosition: VisualPosition): void {
    const snap = battlemapStore;
    const { offsetX, offsetY, tileSize } = this.calculateGridOffset();
    
    if (snap.controls.isIsometric) {
      // Convert grid position to isometric coordinates
      const { isoX, isoY } = gridToIsometric(visualPosition.x, visualPosition.y);
      
      // Apply scale factor to isometric coordinates (tileSize is the scale factor)
      const scaledIsoX = isoX * tileSize;
      const scaledIsoY = isoY * tileSize;
      
      // Convert isometric coordinates to screen coordinates with proper centering
      const screenX = offsetX + scaledIsoX; // Center horizontally in isometric space
      const screenY = offsetY + scaledIsoY; // Center vertically in isometric space
      
      container.x = screenX;
      container.y = screenY;
    } else {
      // Convert visual position to screen coordinates (center of tile)
      const screenX = offsetX + (visualPosition.x * tileSize) + (tileSize / 2);
      const screenY = offsetY + (visualPosition.y * tileSize) + (tileSize / 2);
      
      container.x = screenX;
      container.y = screenY;
    }
  }
  
  /**
   * Update all effect positions (called on view changes)
   */
  private updateEffectPositions(): void {
    const snap = battlemapStore;
    
    // Update active effects
    Object.values(snap.effects.activeEffects).forEach(effect => {
      this.updateEffectPosition(effect);
    });
    
    // Update permanent effects
    Object.entries(snap.entities.permanentEffects).forEach(([entityId, effectTypes]) => {
      effectTypes.forEach(effectType => {
        const effectId = `permanent_${entityId}_${effectType}`;
        const effectContainer = this.effectContainers.get(effectId);
        if (effectContainer) {
          this.updatePermanentEffectPosition(entityId, effectContainer);
        }
      });
    });
  }
  
  /**
   * Calculate grid offset (adapted for isometric mode)
   */
  private calculateGridOffset(): { offsetX: number; offsetY: number; tileSize: number } {
    const snap = battlemapStore;
    const ENTITY_PANEL_WIDTH = 250;
    
    // Check if we're in isometric mode
    if (snap.controls.isIsometric) {
      // Use isometric coordinate calculation
      const isometricOffset = calculateIsometricGridOffset(
        this.engine?.containerSize?.width || 0,
        this.engine?.containerSize?.height || 0,
        snap.grid.width,
        snap.grid.height,
        snap.view.tileSize,
        snap.view.offset.x,
        snap.view.offset.y,
        ENTITY_PANEL_WIDTH
      );
      
      return { 
        offsetX: isometricOffset.offsetX, 
        offsetY: isometricOffset.offsetY,
        tileSize: isometricOffset.tileSize // This is the scale factor for isometric
      };
    } else {
      // Use regular grid coordinate calculation
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
  }
  
  /**
   * Remove effect from rendering
   */
  private removeEffectFromRendering(effectId: string): void {
    const effectContainer = this.effectContainers.get(effectId);
    const animatedSprite = this.animatedSprites.get(effectId);
    
    if (effectContainer) {
      // Remove from whichever layer it's in
      if (effectContainer.parent === this.belowEffectsLayer) {
        this.belowEffectsLayer!.removeChild(effectContainer);
      } else if (effectContainer.parent === this.aboveEffectsLayer) {
        this.aboveEffectsLayer!.removeChild(effectContainer);
      }
      effectContainer.destroy();
      this.effectContainers.delete(effectId);
    }
    
    if (animatedSprite) {
      animatedSprite.destroy();
      this.animatedSprites.delete(effectId);
    }
  }
  
  /**
   * Clean up effects that no longer exist
   */
  private cleanupRemovedEffects(): void {
    const snap = battlemapStore;
    const activeEffectIds = new Set(Object.keys(snap.effects.activeEffects));
    
    // Add permanent effect IDs
    Object.entries(snap.entities.permanentEffects).forEach(([entityId, effectTypes]) => {
      effectTypes.forEach(effectType => {
        activeEffectIds.add(`permanent_${entityId}_${effectType}`);
      });
    });
    
    // Remove effects that are no longer active
    const renderedEffectIds = Array.from(this.effectContainers.keys());
    renderedEffectIds.forEach(effectId => {
      if (!activeEffectIds.has(effectId)) {
        this.removeEffectFromRendering(effectId);
      }
    });
  }
  
  /**
   * Check if active effects have actually changed by comparing JSON hashes
   */
  private hasActiveEffectsActuallyChanged(): boolean {
    const snap = battlemapStore;
    let hasChanges = false;
    
    // Check active effects
    for (const [effectId, effect] of Object.entries(snap.effects.activeEffects)) {
      const effectHash = JSON.stringify({
        effectType: effect.effectType,
        category: effect.category,
        position: effect.position,
        scale: effect.scale,
        alpha: effect.alpha,
        attachedToEntityId: effect.attachedToEntityId,
      });
      
      const lastHash = this.lastEffectData.get(effectId);
      if (lastHash !== effectHash) {
        console.log(`[EffectRenderer] Active effect ${effectId} data changed`);
        this.lastEffectData.set(effectId, effectHash);
        hasChanges = true;
      }
    }
    
    // Check for removed effects
    const currentEffectIds = new Set(Object.keys(snap.effects.activeEffects));
    for (const effectId of Array.from(this.lastEffectData.keys())) {
      if (!currentEffectIds.has(effectId)) {
        console.log(`[EffectRenderer] Active effect ${effectId} was removed`);
        this.lastEffectData.delete(effectId);
        hasChanges = true;
      }
    }
    
    return hasChanges;
  }
  
  /**
   * Check if permanent effects have actually changed by comparing JSON hashes
   */
  private hasPermanentEffectsActuallyChanged(): boolean {
    const snap = battlemapStore;
    let hasChanges = false;
    
    // Check permanent effects
    for (const [entityId, effectTypes] of Object.entries(snap.entities.permanentEffects)) {
      const effectHash = JSON.stringify(effectTypes.sort()); // Sort for consistent comparison
      
      const lastHash = this.lastPermanentEffectData.get(entityId);
      if (lastHash !== effectHash) {
        console.log(`[EffectRenderer] Permanent effects for entity ${entityId} changed`);
        this.lastPermanentEffectData.set(entityId, effectHash);
        hasChanges = true;
      }
    }
    
    // Check for removed permanent effects
    const currentEntityIds = new Set(Object.keys(snap.entities.permanentEffects));
    for (const entityId of Array.from(this.lastPermanentEffectData.keys())) {
      if (!currentEntityIds.has(entityId)) {
        console.log(`[EffectRenderer] Permanent effects for entity ${entityId} were removed`);
        this.lastPermanentEffectData.delete(entityId);
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
      console.log(`[EffectRenderer] 10s Summary: ${this.renderCount} renders, ${this.subscriptionFireCount} subscription fires, ${this.actualChangeCount} actual changes, ${this.effectCacheByKey.size} cached effects`);
      this.lastSummaryTime = now;
      this.renderCount = 0;
      this.subscriptionFireCount = 0;
      this.actualChangeCount = 0;
    }
  }
  
  /**
   * Clean up resources with proper PixiJS v8 cache management
   */
  destroy(): void {
    // Clean up all effects
    this.effectContainers.forEach((container, effectId) => {
      this.removeEffectFromRendering(effectId);
    });
    
    // Clean up effect cache - let PixiJS Assets handle the actual texture cleanup
    this.effectCacheByKey.forEach(cachedData => {
      // Don't destroy the spritesheet - PixiJS Assets manages this
      // Just clear our references
    });
    this.effectCacheByKey.clear();
    
    // Clear layer references
    this.belowEffectsLayer = null;
    this.aboveEffectsLayer = null;
    
    // Unsubscribe from store changes
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
    // Call parent destroy
    super.destroy();
    
    console.log('[EffectRenderer] Destroyed');
  }
  
  /**
   * PUBLIC: Trigger a blood splat effect at a specific position
   * Called by EntityRenderer during damage animation
   */
  public triggerBloodSplat(position: VisualPosition, callback?: () => void): string {
    const effectId = `blood_splat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const bloodSplatEffect: EffectAnimation = {
      effectId,
      effectType: EffectType.BLOOD_SPLAT,
      category: EffectCategory.TEMPORARY,
      position,
      startTime: Date.now(),
      duration: getDefaultEffectDuration(EffectType.BLOOD_SPLAT),
      scale: 1.2, // Slightly larger for impact
      alpha: 1.0,
      triggerCallback: callback,
    };
    
    console.log(`[EffectRenderer] Triggering blood splat at (${position.x}, ${position.y})`);
    battlemapActions.startEffect(bloodSplatEffect);
    
    return effectId;
  }
  
  /**
   * PUBLIC: Trigger a generic effect at a specific position
   */
  public triggerEffect(
    effectType: EffectType, 
    position: VisualPosition, 
    options?: {
      scale?: number;
      alpha?: number;
      duration?: number;
      attachedToEntityId?: string;
      offsetX?: number;
      offsetY?: number;
      callback?: () => void;
    }
  ): string {
    const effectId = `${effectType}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const effect: EffectAnimation = {
      effectId,
      effectType,
      category: getEffectCategory(effectType),
      position,
      startTime: Date.now(),
      duration: options?.duration || getDefaultEffectDuration(effectType),
      scale: options?.scale || 1.0,
      alpha: options?.alpha || 1.0,
      attachedToEntityId: options?.attachedToEntityId,
      offsetX: options?.offsetX,
      offsetY: options?.offsetY,
      triggerCallback: options?.callback,
    };
    
    console.log(`[EffectRenderer] Triggering effect ${effectType} at (${position.x}, ${position.y})`);
    battlemapActions.startEffect(effect);
    
    return effectId;
  }
} 