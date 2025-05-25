import { Container, AnimatedSprite, Assets, Spritesheet, Ticker, Texture } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { AnimationState, Direction, EntitySpriteMapping, MovementAnimation, MovementState, VisualPosition, toVisualPosition } from '../../types/battlemap_types';
import { LayerName } from '../BattlemapEngine';
import { EntitySummary, Position } from '../../types/common';
import { getSpriteSheetPath } from '../../api/battlemap/battlemapApi';

/**
 * Cached sprite data using PixiJS v8 Assets cache properly
 * Key format: "spriteFolder|animation" for consistent cache management
 */
interface CachedSpriteData {
  spritesheet: Spritesheet;
  directionTextures: Record<Direction, Texture[]>;
  cacheKey: string; // For proper cleanup
}

/**
 * Local entity state for direction optimization - avoids store spam during movement
 */
interface LocalEntityState {
  currentDirection: Direction;
  pendingStoreDirection?: Direction; // Only set when we need to update store at the end
  lastStoreUpdateTime: number;
}

/**
 * Precomputed movement data to avoid recalculation
 */
interface PrecomputedMovementData {
  directions: Direction[]; // Direction for each path segment
  distances: number[];     // Distance for each path segment
  totalDistance: number;   // Total path distance
}

/**
 * EntityRenderer with optimized PixiJS v8 cache management and direction handling
 */
export class EntityRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'entities'; }
  
  // Enable ticker updates for movement animation
  protected needsTickerUpdate: boolean = true;
  
  // Entity management
  private entityContainers: Map<string, Container> = new Map();
  private animatedSprites: Map<string, AnimatedSprite> = new Map();
  
  // OPTIMIZED: Use PixiJS Assets cache with proper key management
  private spriteCacheByKey: Map<string, CachedSpriteData> = new Map(); // key: "spriteFolder|animation"
  
  // OPTIMIZED: Local entity state to avoid store spam during movement
  private localEntityStates: Map<string, LocalEntityState> = new Map();
  
  // OPTIMIZED: Precomputed movement data to avoid recalculation
  private precomputedMovementData: Map<string, PrecomputedMovementData> = new Map();
  
  // NEW: Visibility-based alpha management (no store subscriptions, just direct updates)
  private lastVisibilityStates: Map<string, { targetAlpha: number; shouldBeRenderable: boolean }> = new Map();
  
  // NEW: Cached senses data during movement to prevent visibility flickering
  private cachedSensesData: Map<string, { visible: Record<string, boolean>; seen: readonly Position[] }> = new Map();
  
  // NEW: Track last logged position for each entity to reduce console spam
  private lastLoggedPositions: Map<string, { x: number; y: number }> = new Map();
  
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
    console.log('[EntityRenderer] Initializing with PixiJS v8 Assets cache management');
    
    // Subscribe to store changes
    this.setupSubscriptions();
  }
  
  /**
   * Update method called every frame by ticker for movement animations
   */
  update(ticker: Ticker): void {
    if (!this.engine || !this.engine.app) return;
    
    const snap = battlemapStore;
    const movementAnimations = snap.entities.movementAnimations;
    
    // Update all active movement animations
    Object.values(movementAnimations).forEach(movement => {
      this.updateMovementAnimation(movement, ticker.deltaTime);
    });
    
    // NEW: Update entity visibility alpha (smooth, no store subscriptions)
    this.updateEntityVisibilityAlpha();
  }
  
  /**
   * Precompute movement data when movement starts
   */
  private precomputeMovementData(movement: MovementAnimation): PrecomputedMovementData {
    const directions: Direction[] = [];
    const distances: number[] = [];
    let totalDistance = 0;
    
    // Compute direction and distance for each path segment
    for (let i = 0; i < movement.path.length - 1; i++) {
      const fromPos = movement.path[i];
      const toPos = movement.path[i + 1];
      
      // Compute direction
      const direction = this.computeDirectionFromPositions(fromPos, toPos);
      directions.push(direction);
      
      // Compute distance
      const distance = this.calculateDistance(fromPos, toPos);
      distances.push(distance);
      totalDistance += distance;
    }
    
    return { directions, distances, totalDistance };
  }
  
  /**
   * Update a single movement animation with PRECOMPUTED direction handling
   */
  private updateMovementAnimation(movement: MovementAnimation, deltaTime: number): void {
    const entity = battlemapStore.entities.summaries[movement.entityId];
    if (!entity) return;
    
    // Get or create precomputed data
    let precomputed = this.precomputedMovementData.get(movement.entityId);
    if (!precomputed) {
      precomputed = this.precomputeMovementData(movement);
      this.precomputedMovementData.set(movement.entityId, precomputed);
      console.log(`[EntityRenderer] Precomputed movement data for ${entity.name}: ${precomputed.directions.length} segments, total distance ${precomputed.totalDistance.toFixed(2)}`);
    }
    
    const currentTime = Date.now();
    const elapsedSeconds = (currentTime - movement.startTime) / 1000;
    
    // Calculate how far along the path we should be based on movement speed
    const distanceTraveled = elapsedSeconds * movement.movementSpeed;
    
    // Find current position along the path using precomputed distances
    let pathDistance = 0;
    let currentPathIndex = 0;
    let interpolationT = 0;
    
    for (let i = 0; i < precomputed.distances.length; i++) {
      const segmentDistance = precomputed.distances[i];
      
      if (pathDistance + segmentDistance >= distanceTraveled) {
        // We're in this segment
        currentPathIndex = i;
        interpolationT = (distanceTraveled - pathDistance) / segmentDistance;
        break;
      }
      
      pathDistance += segmentDistance;
      
      // If we've reached the end of the path
      if (i === precomputed.distances.length - 1) {
        currentPathIndex = i;
        interpolationT = 1.0;
        break;
      }
    }
    
    // Clamp interpolation
    interpolationT = Math.max(0, Math.min(1, interpolationT));
    
    // Get current and next positions
    const currentPos = movement.path[currentPathIndex];
    const nextPos = movement.path[Math.min(currentPathIndex + 1, movement.path.length - 1)];
    
    // Interpolate visual position
    const visualPosition: VisualPosition = {
      x: currentPos[0] + (nextPos[0] - currentPos[0]) * interpolationT,
      y: currentPos[1] + (nextPos[1] - currentPos[1]) * interpolationT,
    };
    
    // OPTIMIZED: Handle direction changes locally using precomputed directions
    if (currentPathIndex !== movement.currentPathIndex && currentPathIndex < precomputed.directions.length) {
      const newDirection = precomputed.directions[currentPathIndex];
      
      // Update local direction immediately for smooth animation (no store updates during movement)
      this.updateLocalDirection(movement.entityId, newDirection);
      
      // Update movement animation with new path index
      battlemapActions.updateEntityMovementAnimation(movement.entityId, {
        currentPathIndex: currentPathIndex
      });
    }
    
    // Update visual position
    battlemapActions.updateEntityVisualPosition(movement.entityId, visualPosition);
    
    // Update entity container position
    this.updateEntityVisualPosition(movement.entityId, visualPosition);
    
    // Simple completion check: if we're close enough to the target position
    const targetDistance = this.calculateDistance([visualPosition.x, visualPosition.y], movement.targetPosition);
    const isAtTarget = targetDistance < 0.1; // Within 0.1 tiles of target
    
    // Check if movement is complete
    if (isAtTarget || (currentPathIndex >= movement.path.length - 1 && interpolationT >= 1.0)) {
      console.log(`[EntityRenderer] Movement completion detected for ${entity.name}`);
      this.completeMovement(movement);
    } else if (elapsedSeconds > 5) {
      console.warn(`[EntityRenderer] Movement timeout for ${entity.name}, forcing completion`);
      this.completeMovement(movement);
    }
  }
  
  /**
   * Update local direction state (immediate, no store update) - same pattern as position
   */
  private updateLocalDirection(entityId: string, direction: Direction): void {
    let localState = this.localEntityStates.get(entityId);
    if (!localState) {
      localState = {
        currentDirection: direction,
        lastStoreUpdateTime: 0
      };
      this.localEntityStates.set(entityId, localState);
    }
    
    // OPTIMIZED: Only update if direction actually changed
    if (localState.currentDirection === direction) {
      return; // No change needed
    }
    
    // Update local direction immediately
    localState.currentDirection = direction;
    
    // Mark for store update at the end (same pattern as position)
    localState.pendingStoreDirection = direction;
    
    // Update sprite direction immediately for smooth animation
    const animatedSprite = this.animatedSprites.get(entityId);
    if (animatedSprite) {
      this.updateSpriteDirection(entityId, direction);
    }
  }
  
  /**
   * Update sprite direction without changing animation
   */
  private async updateSpriteDirection(entityId: string, direction: Direction): Promise<void> {
    const entity = battlemapStore.entities.summaries[entityId];
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    const animatedSprite = this.animatedSprites.get(entityId);
    
    if (!entity || !mapping || !animatedSprite) return;
    
    // Get cached sprite data
    const cacheKey = this.createCacheKey(mapping.spriteFolder, mapping.currentAnimation);
    const cachedData = this.spriteCacheByKey.get(cacheKey);
    
    if (!cachedData) return;
    
    // Get textures for new direction
    const directionTextures = cachedData.directionTextures[direction];
    if (!directionTextures || directionTextures.length === 0) return;
    
    // Update textures without restarting animation if it's a looping animation
    const wasPlaying = animatedSprite.playing;
    const currentFrame = animatedSprite.currentFrame;
    const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || this.shouldLoop(mapping.currentAnimation);
    
    animatedSprite.textures = directionTextures;
    
    if (shouldLoop && wasPlaying) {
      // For looping animations, maintain current frame position
      animatedSprite.gotoAndPlay(Math.min(currentFrame, directionTextures.length - 1));
    } else if (wasPlaying) {
      // For non-looping animations, restart
      animatedSprite.gotoAndPlay(0);
    }
  }
  
  /**
   * Calculate distance between two positions
   */
  private calculateDistance(pos1: readonly [number, number], pos2: readonly [number, number]): number {
    const dx = pos2[0] - pos1[0];
    const dy = pos2[1] - pos1[1];
    return Math.sqrt(dx * dx + dy * dy);
  }
  
  /**
   * Compute direction from one position to another
   */
  private computeDirectionFromPositions(fromPos: readonly [number, number], toPos: readonly [number, number]): Direction {
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
   * Update entity visual position on screen
   */
  private updateEntityVisualPosition(entityId: string, visualPosition: VisualPosition): void {
    const entityContainer = this.entityContainers.get(entityId);
    if (!entityContainer) return;

    const { offsetX, offsetY, tileSize } = this.calculateGridOffset();
    
    // Convert visual position to screen coordinates
    const screenX = offsetX + (visualPosition.x * tileSize) + (tileSize / 2); // Center horizontally in tile
    const screenY = offsetY + (visualPosition.y * tileSize) + tileSize + (tileSize * 0.2); // Bottom of tile + 20% more south
    
    entityContainer.x = screenX;
    entityContainer.y = screenY;
  }
  
  /**
   * Complete a movement animation - sync both position AND direction at the end
   */
  private completeMovement(movement: MovementAnimation): void {
    console.log(`[EntityRenderer] Movement completed for entity ${movement.entityId}`);
    
    // Clean up precomputed data
    this.precomputedMovementData.delete(movement.entityId);
    
    // FIXED: Always sync the current direction to store before clearing local state
    const localState = this.localEntityStates.get(movement.entityId);
    if (localState) {
      // Use pending direction if available, otherwise use current direction
      const finalDirection = localState.pendingStoreDirection || localState.currentDirection;
      console.log(`[EntityRenderer] Syncing final direction ${finalDirection} to store for entity ${movement.entityId}`);
      battlemapActions.setEntityDirectionFromMapping(movement.entityId, finalDirection);
      
      // Clear local direction state AFTER committing final direction
      this.localEntityStates.delete(movement.entityId);
      console.log(`[EntityRenderer] Cleared local direction state for entity ${movement.entityId} after syncing direction`);
    } else {
      console.log(`[EntityRenderer] No local direction state found for entity ${movement.entityId} during movement completion`);
    }
    
    // Determine if we should resync based on server approval
    const shouldResync = movement.isServerApproved !== true;
    
    if (shouldResync) {
      console.log(`[EntityRenderer] Server rejected movement for ${movement.entityId}, will resync to original position`);
    } else {
      console.log(`[EntityRenderer] Server approved movement for ${movement.entityId}, staying at new position`);
    }
    
    // Complete movement in store (this will return to idle animation and handle resyncing)
    battlemapActions.completeEntityMovement(movement.entityId, shouldResync);
  }
  
  /**
   * NEW: Handle movement animation changes to cache senses data
   */
  private handleMovementAnimationChanges(): void {
    const snap = battlemapStore;
    const selectedEntity = this.getSelectedEntity();
    
    if (!selectedEntity || !snap.controls.isVisibilityEnabled) {
      return;
    }
    
    // Check for new movement animations that need senses data caching
    const currentMovements = Object.keys(snap.entities.movementAnimations);
    
    if (currentMovements.length > 0) {
      // There are active movements - ensure we have cached data for the current viewing entity
      if (!this.cachedSensesData.has(selectedEntity.uuid)) {
        const sensesData = {
          visible: selectedEntity.senses.visible,
          seen: selectedEntity.senses.seen
        };
        this.cachedSensesData.set(selectedEntity.uuid, sensesData);
        console.log(`[EntityRenderer] Cached senses data for viewing entity ${selectedEntity.name} (selection changed during movement or new movement started)`);
      }
    } else {
      // No active movements - clear all cached senses data
      if (this.cachedSensesData.size > 0) {
        console.log(`[EntityRenderer] Clearing all cached senses data - no active movements`);
        this.cachedSensesData.clear();
      }
    }
  }
  
  /**
   * NEW: Public method to cache senses data for a specific entity
   * Called by InteractionsManager before movement starts
   */
  public cacheSensesDataForEntity(entityId: string, sensesData: { visible: Record<string, boolean>; seen: readonly Position[] }): void {
    this.cachedSensesData.set(entityId, sensesData);
    console.log(`[EntityRenderer] Manually cached senses data for entity ${entityId}`);
  }
  
  /**
   * NEW: Public method to clear local direction state for an entity
   * Called by InteractionsManager before setting attack direction
   */
  public clearLocalDirectionState(entityId: string): void {
    if (this.localEntityStates.has(entityId)) {
      this.localEntityStates.delete(entityId);
      console.log(`[EntityRenderer] Cleared local direction state for entity ${entityId}`);
    }
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
    
    // NEW: Subscribe to movement animations to cache senses data when movement starts
    const unsubMovementAnimations = subscribe(battlemapStore.entities.movementAnimations, () => {
      this.handleMovementAnimationChanges();
    });
    this.unsubscribeCallbacks.push(unsubMovementAnimations);
    
    // NEW: Subscribe to entity selection changes to cache senses data when perspective changes during movement
    const unsubEntitySelection = subscribe(battlemapStore.entities, () => {
      // Simple subscription - check if we need to handle selection changes during movement
      this.handleEntitySelectionChange();
    });
    this.unsubscribeCallbacks.push(unsubEntitySelection);
    
    // NEW: Subscribe to pathSenses changes to trigger visibility updates when data becomes available
    const unsubPathSenses = subscribe(battlemapStore.entities.pathSenses, () => {
      // When path senses data becomes available, we need to update visibility immediately
      // This is a "hot swap" that doesn't trigger full re-renders, only visibility alpha updates
      const snap = battlemapStore;
      const selectedEntity = this.getSelectedEntity();
      
      // Only update if the selected entity has path senses (is moving and observing)
      if (selectedEntity && snap.entities.pathSenses[selectedEntity.uuid]) {
        this.updateEntityVisibilityAlpha();
      }
    });
    this.unsubscribeCallbacks.push(unsubPathSenses);
    
    // NEW: Subscribe to sprite mappings for snappy entity visibility updates during movement
    const unsubSpriteMappingsVisibility = subscribe(battlemapStore.entities.spriteMappings, () => {
      // When visual positions change during movement, update entity visibility immediately
      // This makes entity visibility changes feel snappy and responsive
      const snap = battlemapStore;
      const selectedEntity = this.getSelectedEntity();
      
      // Only trigger visibility update if the selected entity is moving (has dynamic path senses)
      if (selectedEntity && snap.entities.movementAnimations[selectedEntity.uuid] && snap.entities.pathSenses[selectedEntity.uuid]) {
        this.updateEntityVisibilityAlpha();
      }
    });
    this.unsubscribeCallbacks.push(unsubSpriteMappingsVisibility);
    
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
   * Create consistent cache key for sprite data
   */
  private createCacheKey(spriteFolder: string, animation: AnimationState): string {
    return `${spriteFolder}|${animation}`;
  }
  
  /**
   * OPTIMIZED: Load sprite with PixiJS v8 Assets cache and preloaded directions
   */
  private async loadEntitySprite(entity: EntitySummary, mapping: EntitySpriteMapping): Promise<void> {
    const cacheKey = this.createCacheKey(mapping.spriteFolder, mapping.currentAnimation);
    
    try {
      // Get or load cached sprite data
      let cachedData = this.spriteCacheByKey.get(cacheKey);
      
      if (!cachedData) {
        // Load and cache sprite data with ALL directions using PixiJS Assets
        const loadedData = await this.loadAndCacheSpriteData(mapping.spriteFolder, mapping.currentAnimation, cacheKey);
        if (!loadedData) return;
        
        cachedData = loadedData;
        this.spriteCacheByKey.set(cacheKey, cachedData);
        console.log(`[EntityRenderer] Cached sprite data for ${cacheKey} with ${Object.keys(cachedData.directionTextures).length} directions`);
      }
      
      // Get current direction (use local state if available, otherwise mapping)
      const localState = this.localEntityStates.get(entity.uuid);
      const currentDirection = localState?.currentDirection || mapping.currentDirection;
      
      // Get textures for current direction
      const directionTextures = cachedData.directionTextures[currentDirection];
      if (!directionTextures || directionTextures.length === 0) {
        console.warn(`[EntityRenderer] No textures found for direction ${currentDirection} in ${cacheKey}`);
        return;
      }
      
      // Get or create animated sprite for this entity
      let animatedSprite = this.animatedSprites.get(entity.uuid);
      
      if (!animatedSprite) {
        // Create new animated sprite
        console.log(`[EntityRenderer] Creating new sprite for ${entity.name} with animation ${mapping.currentAnimation}`);
        animatedSprite = this.createAnimatedSprite(entity, mapping, directionTextures, cacheKey);
        
        // Add to entity container
        const entityContainer = this.entityContainers.get(entity.uuid);
        if (entityContainer) {
          entityContainer.addChild(animatedSprite);
          this.animatedSprites.set(entity.uuid, animatedSprite);
        }
      } else {
        // Update existing sprite
        this.updateExistingSprite(entity, mapping, animatedSprite, cachedData, currentDirection);
      }
      
    } catch (error) {
      console.error(`[EntityRenderer] Error loading sprite for entity ${entity.uuid}:`, error);
    }
  }
  
  /**
   * Load and cache sprite data with ALL directions preloaded using PixiJS v8 Assets
   * FIXED: Use unique cache keys to prevent conflicts between different sprite folders
   */
  private async loadAndCacheSpriteData(spriteFolder: string, animation: AnimationState, cacheKey: string): Promise<CachedSpriteData | null> {
    try {
      const spritesheetPath = getSpriteSheetPath(spriteFolder, animation);
      
      // FIXED: Use unique cache key that includes sprite folder to prevent conflicts
      const uniqueSpritesheetKey = `${spriteFolder}|${animation}|spritesheet`;
      
      // Check if already cached with our unique key
      let spritesheet: Spritesheet;
      if (Assets.cache.has(uniqueSpritesheetKey)) {
        spritesheet = Assets.cache.get(uniqueSpritesheetKey);
        console.log(`[EntityRenderer] Using cached spritesheet: ${uniqueSpritesheetKey}`);
      } else {
        // Load with unique key to prevent conflicts
        spritesheet = await Assets.load<Spritesheet>({ alias: uniqueSpritesheetKey, src: spritesheetPath });
        console.log(`[EntityRenderer] Loaded and cached spritesheet: ${uniqueSpritesheetKey} from ${spritesheetPath}`);
      }
      
      if (!spritesheet) {
        console.error(`[EntityRenderer] Failed to load spritesheet: ${spritesheetPath}`);
        return null;
      }
      
      // Preload ALL directions
      const directionTextures: Record<Direction, Texture[]> = {} as Record<Direction, Texture[]>;
      
      for (const direction of Object.values(Direction)) {
        directionTextures[direction] = this.getDirectionTextures(spritesheet, direction);
      }
      
      return {
        spritesheet,
        directionTextures,
        cacheKey
      };
    } catch (error) {
      console.error(`[EntityRenderer] Error loading sprite data:`, error);
      return null;
    }
  }
  
  /**
   * Create a new animated sprite with proper setup - FIXED sprite key format
   */
  private createAnimatedSprite(
    entity: EntitySummary, 
    mapping: EntitySpriteMapping, 
    directionTextures: Texture[], 
    cacheKey: string
  ): AnimatedSprite {
    const animatedSprite = new AnimatedSprite(directionTextures);
    
    // FIXED: Use consistent sprite key format with direction
    const localState = this.localEntityStates.get(entity.uuid);
    const currentDirection = localState?.currentDirection || mapping.currentDirection;
    const spriteKey = `${cacheKey}_${currentDirection}`;
    
    animatedSprite.name = spriteKey;
    animatedSprite.anchor.set(0.5, 1.0); // Bottom-center anchor for character sprites
    
    // Set initial scale from mapping with zoom-dependent scaling
    this.updateSpriteScale(animatedSprite, mapping);
    
    // Use PixiJS v8 API properly - simple and direct
    animatedSprite.autoUpdate = true; // Let PixiJS handle updates
    
    // OPTIMIZED: Check if transitioning to same state to avoid unnecessary callbacks
    const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || this.shouldLoop(mapping.currentAnimation);
    animatedSprite.loop = shouldLoop;
    
    // Calculate animation speed based on desired duration from slider
    const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
    const framesPerSecond = directionTextures.length / desiredDurationSeconds;
    animatedSprite.animationSpeed = framesPerSecond / 60; // PixiJS expects speed relative to 60fps
    
    // OPTIMIZED: Set up animation callbacks with state transition checking
    this.setupOptimizedAnimationCallbacks(animatedSprite, entity, mapping);
    
    // Start playing
    console.log(`[EntityRenderer] Starting animation for ${entity.name}: ${mapping.currentAnimation} (${directionTextures.length} frames)`);
    animatedSprite.play();
    
    return animatedSprite;
  }
  
  /**
   * Update existing sprite with new data - FIXED to prevent unnecessary animation restarts
   */
  private updateExistingSprite(
    entity: EntitySummary,
    mapping: EntitySpriteMapping,
    animatedSprite: AnimatedSprite,
    cachedData: CachedSpriteData,
    currentDirection: Direction
  ): void {
    // FIXED: Use consistent cache key format
    const expectedCacheKey = this.createCacheKey(mapping.spriteFolder, mapping.currentAnimation);
    const spriteKey = `${expectedCacheKey}_${currentDirection}`;
    
    // FIXED: Parse current sprite key properly
    const currentSpriteKey = animatedSprite.name || '';
    const currentParts = currentSpriteKey.split('_');
    const currentCacheKey = currentParts.slice(0, -1).join('_'); // Everything except direction
    const currentDirectionFromKey = currentParts[currentParts.length - 1]; // Last part is direction
    
    // Check what actually changed
    const animationChanged = currentCacheKey !== expectedCacheKey;
    const directionChanged = currentDirectionFromKey !== currentDirection;
    
    console.log(`[EntityRenderer] Sprite update for ${entity.name}:`, {
      animationChanged,
      directionChanged,
      currentKey: currentSpriteKey,
      expectedKey: spriteKey,
      currentAnimation: mapping.currentAnimation,
      currentDirection
    });
    
    if (animationChanged) {
      console.log(`[EntityRenderer] Animation changed for ${entity.name}: ${currentCacheKey} -> ${expectedCacheKey}`);
      
      // Get textures for current direction
      const directionTextures = cachedData.directionTextures[currentDirection];
      if (directionTextures && directionTextures.length > 0) {
        // OPTIMIZED: Only restart if actually different animation
        animatedSprite.stop();
        animatedSprite.textures = directionTextures;
        animatedSprite.name = spriteKey;
        
        // Update animation properties
        const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || this.shouldLoop(mapping.currentAnimation);
        animatedSprite.loop = shouldLoop;
        
        const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
        const framesPerSecond = directionTextures.length / desiredDurationSeconds;
        animatedSprite.animationSpeed = framesPerSecond / 60;
        
        // FIXED: Set up callbacks without triggering store updates for looping animations
        this.setupOptimizedAnimationCallbacks(animatedSprite, entity, mapping);
        
        animatedSprite.play();
      }
    } else if (directionChanged) {
      console.log(`[EntityRenderer] Direction changed for ${entity.name}: ${currentDirectionFromKey} -> ${currentDirection}`);
      // Only direction changed - update textures smoothly without restarting animation
      this.updateSpriteDirection(entity.uuid, currentDirection);
      animatedSprite.name = spriteKey;
    } else {
      // Only duration/scale changed - update speed without restarting
      const desiredDurationSeconds = mapping.animationDurationSeconds || 1.0;
      const currentFrames = animatedSprite.totalFrames;
      const framesPerSecond = currentFrames / desiredDurationSeconds;
      const newSpeed = framesPerSecond / 60;
      
      if (Math.abs(animatedSprite.animationSpeed - newSpeed) > 0.001) {
        console.log(`[EntityRenderer] Speed changed for ${entity.name}: ${animatedSprite.animationSpeed} -> ${newSpeed}`);
        animatedSprite.animationSpeed = newSpeed;
      }
    }
    
    // Always update scale
    this.updateSpriteScale(animatedSprite, mapping);
  }
  
  /**
   * Update sprite scale based on mapping and zoom
   */
  private updateSpriteScale(animatedSprite: AnimatedSprite, mapping: EntitySpriteMapping): void {
    const userScaleMultiplier = mapping.scale || 1.0;
    
    if (animatedSprite.textures.length > 0 && 'frame' in animatedSprite.textures[0]) {
      const BASE_SCALE = 2.4;
      const textureWidth = animatedSprite.textures[0].frame.width;
      const textureHeight = animatedSprite.textures[0].frame.height;
      const { tileSize } = this.calculateGridOffset();
      const zoomDependentScale = (tileSize / Math.max(textureWidth, textureHeight)) * BASE_SCALE;
      const finalScale = zoomDependentScale * userScaleMultiplier;
      animatedSprite.scale.set(finalScale);
    } else {
      animatedSprite.scale.set(userScaleMultiplier);
    }
  }
  
  /**
   * Get textures for a specific direction from a spritesheet
   */
  private getDirectionTextures(spritesheet: Spritesheet, direction: Direction): Texture[] {
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
   * Determine if an animation should loop
   */
  private shouldLoop(animation: AnimationState): boolean {
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
   * OPTIMIZED: Set up animation callbacks with state transition checking - FIXED to prevent re-render loops
   */
  private setupOptimizedAnimationCallbacks(sprite: AnimatedSprite, entity: EntitySummary, mapping: EntitySpriteMapping): void {
    // Clear any existing callbacks to prevent memory leaks
    sprite.onComplete = undefined;
    sprite.onLoop = undefined;
    
    const shouldLoop = mapping.currentAnimation === mapping.idleAnimation || this.shouldLoop(mapping.currentAnimation);
    
    if (!shouldLoop) {
      // Non-looping animations only
      sprite.onComplete = () => {
        console.log(`[EntityRenderer] Non-looping animation ${mapping.currentAnimation} completed for ${entity.name}`);
        
        // FIXED: Double-check current state to prevent unnecessary updates
        const currentMapping = battlemapStore.entities.spriteMappings[entity.uuid];
        if (!currentMapping) {
          console.warn(`[EntityRenderer] No sprite mapping found for ${entity.uuid} during animation completion`);
          return;
        }
        
        // FIXED: Only update if we're still in the same animation that just completed
        // This prevents race conditions where the animation changed while completing
        if (currentMapping.currentAnimation === mapping.currentAnimation && 
            currentMapping.currentAnimation !== currentMapping.idleAnimation) {
          console.log(`[EntityRenderer] Transitioning ${entity.name} from ${mapping.currentAnimation} to ${currentMapping.idleAnimation}`);
          battlemapActions.setEntityAnimation(entity.uuid, currentMapping.idleAnimation);
        } else {
          console.log(`[EntityRenderer] Skipping transition for ${entity.name} - animation already changed or already idle`);
        }
        
        // If this was an attack animation, resync the entity position
        if (mapping.currentAnimation === AnimationState.ATTACK1 || 
            mapping.currentAnimation === AnimationState.ATTACK2 || 
            mapping.currentAnimation === AnimationState.ATTACK3) {
          console.log(`[EntityRenderer] Attack animation completed for ${entity.name}, resyncing position`);
          battlemapActions.resyncEntityPosition(entity.uuid);
        }
      };
    } else {
      // FIXED: For looping animations, absolutely no callbacks to prevent any store updates
      console.log(`[EntityRenderer] Setting up looping animation for ${entity.name} - no callbacks needed`);
    }
  }
  
  /**
   * Update entity position on screen - Uses visual position if available, otherwise server position
   */
  private updateEntityPosition(entity: EntitySummary): void {
    const entityContainer = this.entityContainers.get(entity.uuid);
    if (!entityContainer) {
      console.warn(`[EntityRenderer] No container found for entity ${entity.uuid} when updating position`);
      return;
    }

    const snap = battlemapStore;
    const spriteMapping = snap.entities.spriteMappings[entity.uuid];
    
    // Use visual position if available and not synced, otherwise use server position
    let positionToUse: VisualPosition;
    if (spriteMapping?.visualPosition && !spriteMapping.isPositionSynced) {
      positionToUse = spriteMapping.visualPosition;
    } else {
      positionToUse = toVisualPosition(entity.position);
    }
    
    this.updateEntityVisualPosition(entity.uuid, positionToUse);
    
    // Update sprite scale
    const animatedSprite = this.animatedSprites.get(entity.uuid);
    if (animatedSprite && spriteMapping) {
      this.updateSpriteScale(animatedSprite, spriteMapping);
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
    
    // Clean up local state
    this.localEntityStates.delete(entityId);
    
    // NEW: Clean up visibility state
    this.lastVisibilityStates.delete(entityId);
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
   * OPTIMIZED: Completely ignore direction changes during movement to avoid feedback loops
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
      });
      
      const lastHash = this.lastEntityData.get(entityId);
      if (lastHash !== entityHash) {
        console.log(`[EntityRenderer] Entity ${entity.name} data changed (position/name/etc)`);
        this.lastEntityData.set(entityId, entityHash);
        hasChanges = true;
      }
    }
    
    // Check sprite mappings (COMPLETELY exclude direction changes during movement)
    for (const [entityId, mapping] of Object.entries(snap.entities.spriteMappings)) {
      const isMoving = mapping.movementState === MovementState.MOVING;
      
      const mappingHash = JSON.stringify({
        spriteFolder: mapping.spriteFolder,
        currentAnimation: mapping.currentAnimation,
        // OPTIMIZED: Only include direction when NOT moving to prevent feedback loops
        currentDirection: isMoving ? 'MOVING' : mapping.currentDirection,
        scale: mapping.scale,
        animationDurationSeconds: mapping.animationDurationSeconds,
        movementState: mapping.movementState, // Include movement state changes
      });
      
      const lastMappingHash = this.lastSpriteMappingData.get(entityId);
      if (lastMappingHash !== mappingHash) {
        console.log(`[EntityRenderer] Entity ${entityId} sprite mapping changed:`, {
          animation: mapping.currentAnimation,
          direction: isMoving ? 'MOVING (ignored)' : mapping.currentDirection,
          duration: mapping.animationDurationSeconds,
          movementState: mapping.movementState
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
      console.log(`[EntityRenderer] 10s Summary: ${this.renderCount} renders, ${this.subscriptionFireCount} subscription fires, ${this.actualChangeCount} actual changes, ${this.spriteCacheByKey.size} cached sprites`);
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
    
    // Clean up local states
    this.localEntityStates.clear();
    
    // NEW: Clean up visibility states
    this.lastVisibilityStates.clear();
    
    // NEW: Clean up cached senses data
    this.cachedSensesData.clear();
    
    // NEW: Clean up position tracking
    this.lastLoggedPositions.clear();
    
    // Unsubscribe from store changes
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
    // Call parent destroy
    super.destroy();
    
    console.log('[EntityRenderer] Destroyed');
  }
  
  /**
   * NEW: Update entity visibility alpha based on selected entity's senses
   * This runs every frame but only updates alpha when visibility changes
   */
  private updateEntityVisibilityAlpha(): void {
    const snap = battlemapStore;
    const selectedEntity = this.getSelectedEntity();
    
    if (!selectedEntity || !snap.controls.isVisibilityEnabled) {
      // No selected entity or visibility disabled - make all entities fully visible and renderable
      this.entityContainers.forEach((container, entityId) => {
        container.alpha = 1.0;
        container.renderable = true;
        this.lastVisibilityStates.delete(entityId); // Clear state to force update when re-enabled
      });
      return;
    }
    
    const sensesData = this.getSensesData(selectedEntity);
    if (!sensesData) return;
    
    // Update visibility for each entity
    Object.values(snap.entities.summaries).forEach((entity: EntitySummary) => {
      const container = this.entityContainers.get(entity.uuid);
      if (!container) return;
      
      const visibility = this.calculateEntityVisibility(entity, selectedEntity, sensesData);
      const lastState = this.lastVisibilityStates.get(entity.uuid);
      
      // Only update if visibility state changed (performance optimization)
      if (!lastState || 
          lastState.targetAlpha !== visibility.targetAlpha || 
          lastState.shouldBeRenderable !== visibility.shouldBeRenderable) {
        
        // Update alpha for fog effect (seen but not visible)
        container.alpha = visibility.targetAlpha;
        
        // Update renderable for complete invisibility (unseen entities)
        // renderable = false makes sprites completely invisible while keeping animations running
        container.renderable = visibility.shouldBeRenderable;
        
        // Cache the new state
        this.lastVisibilityStates.set(entity.uuid, {
          targetAlpha: visibility.targetAlpha,
          shouldBeRenderable: visibility.shouldBeRenderable
        });
      }
    });
  }
  
  /**
   * NEW: Get the selected entity for visibility calculations
   */
  private getSelectedEntity(): EntitySummary | null {
    const snap = battlemapStore;
    if (!snap.entities.selectedEntityId) return null;
    return snap.entities.summaries[snap.entities.selectedEntityId] || null;
  }
  
  /**
   * NEW: Get senses data for visibility calculations using dynamic path senses
   */
  private getSensesData(entity: EntitySummary): {
    visible: Record<string, boolean>;
    seen: readonly Position[];
  } {
    const snap = battlemapStore;
    
    // Check if the OBSERVER entity (the one we're getting senses for) is currently moving
    const observerMovementAnimation = snap.entities.movementAnimations[entity.uuid];
    
    if (observerMovementAnimation) {
      // The OBSERVER entity is moving - use dynamic path senses based on their current animated position
      // This ensures visibility is only dynamic when the observer themselves is moving
      const pathSenses = snap.entities.pathSenses[entity.uuid];
      
      if (pathSenses) {
        // Get the entity's current animated position with anticipation
        const spriteMapping = snap.entities.spriteMappings[entity.uuid];
        if (spriteMapping?.visualPosition) {
          // Use anticipation: switch to next cell's senses when we're at the center of the sprite
          // This makes visibility changes feel more natural and realistic
          const anticipationThreshold = 0.5;
          const currentX = Math.floor(spriteMapping.visualPosition.x + anticipationThreshold);
          const currentY = Math.floor(spriteMapping.visualPosition.y + anticipationThreshold);
          const posKey = `${currentX},${currentY}`;
          
          // Use senses data for the current animated position
          const currentPositionSenses = pathSenses[posKey];
          if (currentPositionSenses) {
            // Only log when position changes to reduce spam
            const lastLoggedPos = this.lastLoggedPositions.get(entity.uuid);
            if (!lastLoggedPos || lastLoggedPos.x !== currentX || lastLoggedPos.y !== currentY) {
              console.log(`[EntityRenderer] Using dynamic path senses for ${entity.name} at position (${currentX}, ${currentY})`);
              this.lastLoggedPositions.set(entity.uuid, { x: currentX, y: currentY });
            }
            return {
              visible: currentPositionSenses.visible,
              seen: currentPositionSenses.seen
            };
          } else {
            // Path senses available but no data for current position - use entity's current senses
            // This can happen during the first few frames of movement before reaching the first path position
            return {
              visible: entity.senses.visible,
              seen: entity.senses.seen
            };
          }
        }
      } else {
        // Path senses not yet available (timing issue) - use entity's current senses as fallback
        // This is normal during the first few frames after movement starts
        return {
          visible: entity.senses.visible,
          seen: entity.senses.seen
        };
      }
    }
    
    // Check if ANY OTHER entity is currently moving (but not the selected entity)
    const hasOtherMovements = Object.keys(snap.entities.movementAnimations).some(id => id !== entity.uuid);
    
    if (hasOtherMovements) {
      // Other entities are moving but not the selected entity - use cached static perspective
      const cached = this.cachedSensesData.get(entity.uuid);
      if (cached) {
        console.log(`[EntityRenderer] Using cached static senses for observer ${entity.name} while other entities move`);
        return cached;
      }
      
      console.warn(`[EntityRenderer] No cached senses data for observer ${entity.name} during other movements - using current data`);
    }
    
    // No movements or fallback - use current data
    return {
      visible: entity.senses.visible,
      seen: entity.senses.seen
    };
  }
  
  /**
   * NEW: Calculate visibility state and target alpha for an entity
   */
  private calculateEntityVisibility(
    entity: EntitySummary, 
    selectedEntity: EntitySummary, 
    sensesData: { visible: Record<string, boolean>; seen: readonly Position[] }
  ): { visible: boolean; seen: boolean; targetAlpha: number; shouldBeRenderable: boolean } {
    // Self is always fully visible
    if (entity.uuid === selectedEntity.uuid) {
      return { visible: true, seen: true, targetAlpha: 1.0, shouldBeRenderable: true };
    }
    
    // NEW: Use entity's visual position if it's moving, otherwise use server position
    const snap = battlemapStore;
    const spriteMapping = snap.entities.spriteMappings[entity.uuid];
    const isEntityMoving = !spriteMapping?.isPositionSynced;
    
    let entityX: number, entityY: number;
    
    if (isEntityMoving && spriteMapping?.visualPosition) {
      // Entity is moving - use its current animated position for visibility calculation
      entityX = Math.floor(spriteMapping.visualPosition.x);
      entityY = Math.floor(spriteMapping.visualPosition.y);
      console.log(`[EntityRenderer] Using visual position for ${entity.name}: (${entityX}, ${entityY}) vs server (${entity.position[0]}, ${entity.position[1]})`);
    } else {
      // Entity is not moving - use server position
      [entityX, entityY] = entity.position;
    }
    
    const posKey = `${entityX},${entityY}`;
    
    // Check if entity position is visible using the observer's static senses
    const visible = !!sensesData.visible[posKey];
    
    // Check if entity position has been seen before using the observer's static senses
    const seen = sensesData.seen.some(([seenX, seenY]) => seenX === entityX && seenY === entityY);
    
    if (visible) {
      // Entity is in a visible cell - fully visible
      return { visible: true, seen: true, targetAlpha: 1.0, shouldBeRenderable: true };
    } else {
      // Entity is NOT in a visible cell - completely invisible (regardless of seen status)
      // For entities: if not visible, they should be completely invisible
      return { visible: false, seen, targetAlpha: 1.0, shouldBeRenderable: false };
    }
  }
  
  /**
   * NEW: Handle entity selection change
   */
  private handleEntitySelectionChange(): void {
    const snap = battlemapStore;
    const selectedEntity = this.getSelectedEntity();
    
    // Only handle if there are active movements and visibility is enabled
    if (!selectedEntity || !snap.controls.isVisibilityEnabled) {
      return;
    }
    
    const hasActiveMovements = Object.keys(snap.entities.movementAnimations).length > 0;
    if (hasActiveMovements) {
      // There are active movements and user changed perspective
      // Cache senses data for the newly selected entity if not already cached
      if (!this.cachedSensesData.has(selectedEntity.uuid)) {
        const sensesData = {
          visible: selectedEntity.senses.visible,
          seen: selectedEntity.senses.seen
        };
        this.cachedSensesData.set(selectedEntity.uuid, sensesData);
        console.log(`[EntityRenderer] Cached senses data for newly selected entity ${selectedEntity.name} during movement`);
      }
    }
  }
} 