import { Container, AnimatedSprite, Assets, Spritesheet, Ticker, Texture } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../../store';
import { soundActions } from '../../store/soundStore';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { AnimationState, Direction, EntitySpriteMapping, MovementAnimation, MovementState, VisualPosition, toVisualPosition, EffectType, EffectCategory } from '../../types/battlemap_types';
import { LayerName } from '../BattlemapEngine';
import { EntitySummary, Position } from '../../types/common';
import { getSpriteSheetPath } from '../../api/battlemap/battlemapApi';
import { gridToIsometric, calculateIsometricGridOffset, isometricToGrid } from '../../utils/isometricUtils';
// NEW: Import animation system
import { animationController } from '../animation/AnimationController';
import { animationEventBus, AnimationLifecycleEvents, animationStore, animationActions } from '../../store/animationStore';
// NEW: Import centralized animation utilities following guide structure
import { SpriteLoadingUtils, SpriteCallbackUtils, AnimationTimingUtils, CachedSpriteData } from '../animation/utils/AnimationUtils';
import { DirectionUtils } from '../animation/utils/DirectionUtils';
import { IsometricRenderingUtils } from './utils/IsometricRenderingUtils';
// NEW: Import sprite rendering utilities
import { SpriteRenderingUtils } from './utils/SpriteRenderingUtils';
// NEW: Import senses calculation utilities
import { SensesCalculationUtils } from './utils/SensesCalculationUtils';
// NEW: Import centralized combat utilities  
import { computeDirection, getOppositeDirection, getAdjacentPosition, isDefenderShowingFront, calculateDistance } from '../../utils/combatUtils';
// NEW: Import specialized managers following our architecture guide
import { VisibilityManager } from './managers/VisibilityManager';
import { ZOrderManager } from './managers/ZOrderManager';
import { PositionManager } from './managers/PositionManager';

/**
 * IsometricEntityRenderer - CLEANED with specialized managers
 * 
 * RESPONSIBILITIES (following architecture guide):
 * ✅ Sprite rendering and texture management
 * ✅ Animation callback setup (frame timing only)
 * ✅ Coordinate with animation system
 * ✅ DELEGATE complex logic to specialized managers
 * 
 * CLEANED: Extracted visibility, z-order, and position logic to managers
 */
export class IsometricEntityRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'entities'; }
  
  // Enable ticker updates for movement animation
  protected needsTickerUpdate: boolean = true;
  
  // Entity management
  private entityContainers: Map<string, Container> = new Map();
  private animatedSprites: Map<string, AnimatedSprite> = new Map();
  
  // OPTIMIZED: Use PixiJS Assets cache with proper key management
  private spriteCacheByKey: Map<string, CachedSpriteData> = new Map(); // key: "spriteFolder|animation"
  
  // NEW: Specialized managers following architecture guide
  private visibilityManager = new VisibilityManager();
  private zOrderManager = new ZOrderManager();
  private positionManager = new PositionManager();
  
  // MEMOIZATION: Track last seen entity data to prevent unnecessary re-renders
  private lastEntityData: Map<string, string> = new Map(); // entityId -> JSON hash
  private lastSpriteMappingData: Map<string, string> = new Map(); // entityId -> JSON hash
  
  // Summary logging system
  private subscriptionFireCount = 0;
  private actualChangeCount = 0;
  
  initialize(engine: any): void {
    super.initialize(engine);
    console.log('[IsometricEntityRenderer] Initializing with specialized managers');
    console.log('[IsometricEntityRenderer] Container added to layer:', this.layerName);
    console.log('[IsometricEntityRenderer] Main container visible:', this.container.visible, 'alpha:', this.container.alpha);
    
    // NEW: Initialize animation controller
    animationController.initialize();
    
    // NEW: Initialize movement handler with manager-based callbacks
    animationController.initializeMovementHandler({
      onUpdateEntityVisualPosition: this.updateEntityVisualPosition.bind(this),
      onUpdateSpriteDirection: this.updateSpriteDirection.bind(this),
      onSetLocalZOrder: this.setLocalZOrder.bind(this),
      onClearLocalZOrder: this.clearLocalZOrder.bind(this)
    });
    
    // Subscribe to store changes
    this.setupSubscriptions();
    
    // NEW: Listen for animation events
    this.setupAnimationEventListeners();
  }
  
  /**
   * NEW: Set up animation event listeners
   */
  private setupAnimationEventListeners(): void {
    // Listen for attack impact to trigger effects
    animationEventBus.on(AnimationLifecycleEvents.ATTACK_IMPACT_FRAME, (animation) => {
      console.log('[IsometricEntityRenderer] Attack impact event received:', animation);
      // Existing attack impact logic can be triggered here
      // This is where we'll gradually move the callback logic
    });
    
    // Enable debug logging for development
    animationEventBus.setDebug(true);
  }
  
  /**
   * Update method called every frame by ticker - now using managers
   */
  update(ticker: Ticker): void {
    if (!this.engine || !this.engine.app) return;
    
    // FIXED: Only update animations if entities are actually rendered
    // This prevents interference with basic sprite setup
    if (this.entityContainers.size > 0) {
      // NEW: Update animation controller first
      animationController.updateAnimations(ticker.deltaTime);
    }
    
    // Use VisibilityManager for entity visibility updates
    this.visibilityManager.updateEntityVisibilityAlpha(this.entityContainers);
  }
  
  /**
   * Update sprite direction without changing animation
   */
  private async updateSpriteDirection(entityId: string, gridDirection: Direction): Promise<void> {
    const entity = battlemapStore.entities.summaries[entityId];
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    const animatedSprite = this.animatedSprites.get(entityId);
    
    if (!entity || !mapping || !animatedSprite) return;
    
    // Convert grid-based direction to isometric direction for sprite rendering
    const isometricDirection = DirectionUtils.convertToIsometricDirection(gridDirection);
    
    console.log(`[IsometricEntityRenderer] updateSpriteDirection for ${entity.name}: grid ${gridDirection} -> isometric ${isometricDirection}`);
    
    // Get cached sprite data
    const cacheKey = SpriteLoadingUtils.createCacheKey(mapping.spriteFolder, mapping.currentAnimation);
    const cachedData = SpriteLoadingUtils.getCachedSprite(mapping.spriteFolder, mapping.currentAnimation);
    
    if (!cachedData) return;
    
    // Get textures for isometric direction
    const directionTextures = cachedData.directionTextures[isometricDirection];
    if (!directionTextures || directionTextures.length === 0) return;
    
    // Update textures without restarting animation if it's a looping animation
    const wasPlaying = animatedSprite.playing;
    const currentFrame = animatedSprite.currentFrame;
    const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || SpriteLoadingUtils.shouldLoop(mapping.currentAnimation);
    
    animatedSprite.textures = directionTextures;
    
    // Update the sprite name to reflect the new isometric direction
    const expectedCacheKey = SpriteLoadingUtils.createCacheKey(mapping.spriteFolder, mapping.currentAnimation);
    const spriteKey = `${expectedCacheKey}_${isometricDirection}`;
    animatedSprite.name = spriteKey;
    
    if (shouldLoop && wasPlaying) {
      // For looping animations, maintain current frame position
      animatedSprite.gotoAndPlay(Math.min(currentFrame, directionTextures.length - 1));
    } else if (wasPlaying) {
      // For non-looping animations, restart
      animatedSprite.gotoAndPlay(0);
    }
  }
  
  /**
   * Update entity visual position using PositionManager
   */
  private updateEntityVisualPosition(entityId: string, visualPosition: VisualPosition): void {
    this.positionManager.updateEntityVisualPosition(entityId, visualPosition, this.entityContainers, this.engine);
  }
  
  /**
   * NEW: Handle movement animation changes using VisibilityManager
   */
  private handleMovementAnimationChanges(): void {
    this.visibilityManager.handleMovementAnimationChanges();
  }
  
  /**
   * NEW: Public method to cache senses data for a specific entity (using VisibilityManager)
   * Called by InteractionsManager before movement starts
   */
  public cacheSensesDataForEntity(entityId: string, sensesData: { visible: Record<string, boolean>; seen: readonly Position[] }): void {
    this.visibilityManager.cacheSensesDataForEntity(entityId, sensesData);
  }
  
  /**
   * NEW: Public method to clear local direction state for an entity
   * Called by InteractionsManager before setting attack direction
   * Now delegates to MovementAnimationHandler
   */
  public clearLocalDirectionState(entityId: string): void {
    // Delegate to MovementAnimationHandler
    const movementHandler = animationController.getMovementHandler();
    movementHandler.clearLocalDirectionState(entityId);
  }
  
  /**
   * NEW: Set local z-order using ZOrderManager
   */
  private setLocalZOrder(entityId: string, zIndex: number): void {
    this.zOrderManager.setLocalZOrder(entityId, zIndex);
      // Trigger container re-ordering
    this.zOrderManager.updateEntityContainerOrder(this.entityContainers, this.container);
  }
  
  /**
   * NEW: Clear local z-order using ZOrderManager
   */
  private clearLocalZOrder(entityId: string): void {
    this.zOrderManager.clearLocalZOrder(entityId);
      // Trigger container re-ordering
    this.zOrderManager.updateEntityContainerOrder(this.entityContainers, this.container);
  }
  
  /**
   * Set up subscriptions to store changes - now using managers
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
    this.addSubscription(unsubEntities);
    
    // NEW: Subscribe to animation state changes using VisibilityManager
    const unsubAnimationChanges = subscribe(animationStore, () => {
      this.handleMovementAnimationChanges();
    });
    this.addSubscription(unsubAnimationChanges);
    
    // NEW: Subscribe to entity selection changes for immediate visibility updates
    const unsubEntitySelection = subscribe(battlemapStore.entities, (ops) => {
      // Check if selectedEntityId changed
      const snap = battlemapStore;
      const currentSelectedId = snap.entities.selectedEntityId;
      
      // Trigger immediate visibility update when selection changes
      // Note: VisibilityManager now maintains separate cached states per observer
      console.log(`[IsometricEntityRenderer] Entity selection changed to: ${currentSelectedId || 'none'}`);
      this.visibilityManager.updateEntityVisibilityAlpha(this.entityContainers);
    });
    this.addSubscription(unsubEntitySelection);
    
    // NEW: Subscribe to visibility settings changes for immediate updates
    const unsubVisibilitySettings = subscribe(battlemapStore.controls, (ops) => {
      // Check if visibility settings changed
      const snap = battlemapStore;
      
      // Trigger immediate visibility update when visibility settings change
      console.log(`[IsometricEntityRenderer] Visibility settings changed - isVisibilityEnabled: ${snap.controls.isVisibilityEnabled}`);
      this.visibilityManager.updateEntityVisibilityAlpha(this.entityContainers);
    });
    this.addSubscription(unsubVisibilitySettings);
    
    // NEW: Subscribe to pathSenses changes to trigger visibility updates
    const unsubPathSenses = subscribe(battlemapStore.entities.pathSenses, () => {
      // When path senses data becomes available, update visibility immediately
      const snap = battlemapStore;
      const selectedEntity = SensesCalculationUtils.getSelectedEntity();
      
      // Only update if the selected entity has path senses (is moving and observing)
      if (selectedEntity && snap.entities.pathSenses[selectedEntity.uuid]) {
        this.visibilityManager.updateEntityVisibilityAlpha(this.entityContainers);
      }
    });
    this.addSubscription(unsubPathSenses);
    
    // NEW: Subscribe to sprite mappings for visibility updates using VisibilityManager
    const unsubSpriteMappingsVisibility = subscribe(battlemapStore.entities.spriteMappings, () => {
      // When visual positions change during movement, update entity visibility immediately
      const snap = battlemapStore;
      const selectedEntity = SensesCalculationUtils.getSelectedEntity();
      
      // Only trigger visibility update if the selected entity is moving (has dynamic path senses)
      if (selectedEntity && animationActions.getActiveAnimation(selectedEntity.uuid) && snap.entities.pathSenses[selectedEntity.uuid]) {
        this.visibilityManager.updateEntityVisibilityAlpha(this.entityContainers);
      }
    });
    this.addSubscription(unsubSpriteMappingsVisibility);
    
    // Subscribe to view changes for positioning using PositionManager
    const unsubView = subscribe(battlemapStore.view, () => {
      this.updateEntityPositions();
      // Don't call render() here - position updates don't need full re-render
    });
    this.addSubscription(unsubView);
    
    // Also subscribe to grid changes in case grid size affects positioning
    const unsubGrid = subscribe(battlemapStore.grid, () => {
      this.updateEntityPositions();
      // Don't call render() here - position updates don't need full re-render
    });
    this.addSubscription(unsubGrid);
  }
  
  /**
   * Main render method - now using ZOrderManager for container ordering
   */
  render(): void {
    this.incrementRenderCount();
    
    // Skip if not properly initialized
    if (!this.isEngineReady()) {
      return;
    }
    
    const snap = battlemapStore;
    const entities = Object.values(snap.entities.summaries) as EntitySummary[];
    const spriteMappings = snap.entities.spriteMappings;
    
          console.log(`[IsometricEntityRenderer] Rendering ${entities.length} entities, ${Object.keys(spriteMappings).length} sprite mappings`);
      
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
    
    // NEW: Update container order using ZOrderManager
    this.zOrderManager.updateEntityContainerOrder(this.entityContainers, this.container);
    
    // Debug: Check if any entities are actually visible (reduced logging)
    if (this.renderCount % 100 === 0) { // Only log every 100 renders
      console.log(`[IsometricEntityRenderer] Render complete. Main container children: ${this.container.children.length}, visible containers: ${Array.from(this.entityContainers.values()).filter(c => c.visible).length}`);
    }
    
  }
  
  /**
   * Ensure an entity with sprite mapping is properly rendered
   */
  private async ensureEntityRendered(entity: EntitySummary, mapping: EntitySpriteMapping): Promise<void> {
    try {
      // Use SpriteRenderingUtils for all sprite management
      const getCurrentDirection = (entityId: string) => {
        const movementHandler = animationController.getMovementHandler();
        return movementHandler.getCurrentDirection(entityId);
      };
      
      const result = await SpriteRenderingUtils.ensureEntitySprite(
        entity,
        mapping,
        this.entityContainers,
        this.animatedSprites,
        this.container,
        this.engine,
        getCurrentDirection
      );
      
      if (result) {
        // Set up animation callbacks if sprite was created/updated
        this.setupOptimizedAnimationCallbacks(result.sprite, entity, mapping);
      }
      
    } catch (error) {
      console.error(`[IsometricEntityRenderer] Error ensuring entity ${entity.uuid} is rendered:`, error);
    }
  }
  
  /**
   * Update all entity positions using PositionManager
   */
  private updateEntityPositions(): void {
    this.positionManager.updateAllEntityPositions(
      this.entityContainers,
      this.animatedSprites,
      this.engine
    );
  }
  
  /**
   * Remove entity from rendering - now using managers for cleanup
   */
  private removeEntityFromRendering(entityId: string): void {
    // Use SpriteRenderingUtils for sprite cleanup
    SpriteRenderingUtils.removeEntitySprite(
      entityId,
      this.entityContainers,
      this.animatedSprites,
      this.container
    );
    
    // Clean up manager-specific state
    this.visibilityManager.cleanupEntityVisibilityState(entityId);
    this.zOrderManager.cleanupEntityZOrderState(entityId);
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
   * FIXED: Let server data flow normally, just shield rendering during animation
   * 
   * Server data should ALWAYS flow to store - animation only affects RENDERING
   */
  private hasEntitiesActuallyChanged(): boolean {
    const snap = battlemapStore;
    let hasChanges = false;
    
    // Check if any entities are currently animating
    const allEntityIds = Object.keys(snap.entities.summaries);
    const hasActiveAnimations = allEntityIds.some(entityId => !!animationActions.getActiveAnimation(entityId));
    
    // FIXED: Always check server state changes - don't block them during animation
    // Check entity summaries (server state) - ALWAYS process these
    for (const [entityId, entity] of Object.entries(snap.entities.summaries)) {
      const entityHash = JSON.stringify({
        uuid: entity.uuid,
        name: entity.name,
        position: entity.position,
      });
      
      const lastHash = this.lastEntityData.get(entityId);
      if (lastHash !== entityHash) {
        if (hasActiveAnimations) {
          console.log(`[IsometricEntityRenderer] SERVER STATE updated for entity ${entity.name} (will not affect rendering during animation)`);
        } else {
          console.log(`[IsometricEntityRenderer] SERVER STATE change for entity ${entity.name} (position/name/etc)`);
        }
        this.lastEntityData.set(entityId, entityHash);
        
        // Only trigger re-render if NOT animating (shielding rendering, not data flow)
        if (!hasActiveAnimations) {
        hasChanges = true;
        }
      }
    }
    
    // Check sprite mappings for animation-related changes (always process these)
    for (const [entityId, mapping] of Object.entries(snap.entities.spriteMappings)) {
      const mappingHash = JSON.stringify({
        spriteFolder: mapping.spriteFolder,
        currentAnimation: mapping.currentAnimation,
        currentDirection: mapping.currentDirection,
        scale: mapping.scale,
        animationDurationSeconds: mapping.animationDurationSeconds,
        movementState: mapping.movementState,
      });
      
      const lastMappingHash = this.lastSpriteMappingData.get(entityId);
      if (lastMappingHash !== mappingHash) {
        console.log(`[IsometricEntityRenderer] SPRITE MAPPING change for entity ${entityId}:`, {
          animation: mapping.currentAnimation,
          direction: mapping.currentDirection,
          movementState: mapping.movementState
        });
        this.lastSpriteMappingData.set(entityId, mappingHash);
        hasChanges = true;
      }
    }
    
    // Check for removed entities (always important)
    const currentEntityIds = new Set(Object.keys(snap.entities.summaries));
    for (const entityId of Array.from(this.lastEntityData.keys())) {
      if (!currentEntityIds.has(entityId)) {
        console.log(`[IsometricEntityRenderer] Entity ${entityId} was removed`);
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
    const additionalInfo = `${this.subscriptionFireCount} subscription fires, ${this.actualChangeCount} actual changes, ${this.spriteCacheByKey.size} cached sprites`;
    this.logRenderSummary(additionalInfo);
    
    // Reset counters when summary is logged
    const now = Date.now();
    if (now - this.lastSummaryTime >= 10000) { // 10 seconds
      this.subscriptionFireCount = 0;
      this.actualChangeCount = 0;
    }
  }
  
  /**
   * Clean up resources with proper PixiJS v8 cache management and manager cleanup
   */
  destroy(): void {
    // NEW: Clean up animation controller
    animationController.destroy();
    
    // Clean up all entities
    this.entityContainers.forEach((container, entityId) => {
      this.removeEntityFromRendering(entityId);
    });
    
    // Clean up sprite cache - let PixiJS Assets handle the actual texture cleanup
    this.spriteCacheByKey.forEach(cachedData => {
      // Don't destroy the spritesheet - PixiJS Assets manages this
      // Just clear our references
    });
    this.spriteCacheByKey.clear();
    
    // NEW: Clean up managers
    this.visibilityManager.destroy();
    this.zOrderManager.destroy();
    this.positionManager.destroy();
    
    // Call parent destroy (handles subscription cleanup automatically)
    super.destroy();
    
    console.log('[IsometricEntityRenderer] Destroyed with managers');
  }
  
  /**
   * SIMPLIFIED: Set up animation callbacks with only frame timing detection
   * Combat logic now handled by EntityCombatService and CombatAnimationHandler
   */
  private setupOptimizedAnimationCallbacks(sprite: AnimatedSprite, entity: EntitySummary, mapping: EntitySpriteMapping): void {
    // Clear any existing callbacks to prevent memory leaks
    sprite.onComplete = undefined;
    sprite.onLoop = undefined;
    sprite.onFrameChange = undefined;
    
    const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || SpriteLoadingUtils.shouldLoop(mapping.currentAnimation);
    const isAttackAnimation = mapping.currentAnimation === AnimationState.ATTACK1 || 
                             mapping.currentAnimation === AnimationState.ATTACK2 || 
                             mapping.currentAnimation === AnimationState.ATTACK3;
    
    if (!shouldLoop) {
      // Non-looping animations
      
      if (isAttackAnimation) {
        // NEW: Set default z-order for attacking entity (on top initially)
        this.setLocalZOrder(entity.uuid, 150);
        
        // SIMPLIFIED: Only emit frame timing events - no combat logic
        let damageTriggered = false; // Prevent multiple triggers
        
        sprite.onFrameChange = (currentFrame: number) => {
          const totalFrames = sprite.totalFrames;
          const frameProgress = currentFrame / Math.max(totalFrames - 1, 1); // 0.0 to 1.0
          
          // Trigger impact event at 40% through attack animation
          // RENDERER RESPONSIBILITY: Only frame timing detection
          if (!damageTriggered && frameProgress >= 0.4) {
            damageTriggered = true;
            
            console.log(`[IsometricEntityRenderer] FRAME TIMING: Attack impact frame ${currentFrame}/${totalFrames} (${Math.round(frameProgress * 100)}%) - emitting event`);
                   
            // CLEAN SEPARATION: Only emit event, all combat logic in CombatAnimationHandler
            try {
              animationEventBus.emit(AnimationLifecycleEvents.ATTACK_IMPACT_FRAME, {
                id: `attack_impact_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                entityId: entity.uuid,
                type: mapping.currentAnimation,
                status: 'playing' as any,
                startTime: Date.now(),
                duration: 1000,
                progress: frameProgress,
                clientInitiated: false,
                data: {
                  currentFrame: currentFrame,
                  totalFrames: totalFrames,
                  frameProgress: frameProgress
                }
              });
            } catch (error) {
              console.warn('[IsometricEntityRenderer] Error emitting attack impact event:', error);
            }
          }
        };
        
        // SIMPLIFIED: Only emit completion event and clear local z-order
        sprite.onComplete = () => {
          console.log(`[IsometricEntityRenderer] FRAME TIMING: Attack animation completed for ${entity.name} - emitting event`);
          
          // VISUAL CLEANUP ONLY: Clear local z-order overrides
          this.clearLocalZOrder(entity.uuid);
          
          // CLEAN SEPARATION: Only emit completion event, all combat logic in CombatAnimationHandler
          try {
            animationEventBus.emit(AnimationLifecycleEvents.ATTACK_COMPLETED, {
              id: `attack_complete_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              entityId: entity.uuid,
              type: mapping.currentAnimation,
              status: 'completed' as any,
              startTime: Date.now(),
              duration: 1000,
              progress: 1.0,
              clientInitiated: false,
              data: {}
            });
          } catch (error) {
            console.warn('[IsometricEntityRenderer] Error emitting attack completion event:', error);
          }
        };
        
          } else {
        // Non-attack animations use standard onComplete behavior
        sprite.onComplete = () => {
          console.log(`[IsometricEntityRenderer] Non-looping animation ${mapping.currentAnimation} completed for ${entity.name}`);
          
          // FIXED: Double-check current state to prevent unnecessary updates
          const currentMapping = battlemapStore.entities.spriteMappings[entity.uuid];
          if (!currentMapping) {
            console.warn(`[IsometricEntityRenderer] No sprite mapping found for ${entity.uuid} during animation completion`);
            return;
          }
          
          // FIXED: Only update if we're still in the same animation that just completed
          // This prevents race conditions where the animation changed while completing
          if (currentMapping.currentAnimation === mapping.currentAnimation && 
              currentMapping.currentAnimation !== currentMapping.idleAnimation) {
            console.log(`[IsometricEntityRenderer] Transitioning ${entity.name} from ${mapping.currentAnimation} to ${currentMapping.idleAnimation}`);
            battlemapActions.setEntityAnimation(entity.uuid, currentMapping.idleAnimation);
          } else {
            console.log(`[IsometricEntityRenderer] Skipping transition for ${entity.name} - animation already changed or already idle`);
          }
        };
      }
    } else {
      // FIXED: For looping animations, absolutely no callbacks to prevent any store updates
      console.log(`[IsometricEntityRenderer] Setting up looping animation for ${entity.name} - no callbacks needed`);
    }
  }
  
} 