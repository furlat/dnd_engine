import { Graphics, Texture, Sprite, Assets, Container } from 'pixi.js';
import { battlemapStore } from '../../store';
import { TileSummary } from '../../types/battlemap_types';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { LayerName } from '../BattlemapEngine';
import { EntitySummary, Position } from '../../types/common';

// Create a texture cache
const textureCache: Record<string, Texture> = {};

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * TileRenderer handles rendering the map tiles
 */
export class TileRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'tiles'; }
  
  // Texture cache reference
  private tileTextures: Record<string, Texture | null> = {};
  
  // Graphics references
  private backgroundGraphics: Graphics = new Graphics();
  
  // Reference to tiles for stable rendering during movement
  private tilesRef: Record<string, TileSummary> = {};
  
  // Container for tiles to make cleanup easier
  private tilesContainer: Container = new Container();
  
  // NEW: Container for black fog overlays on unseen tiles
  private blackFogContainer: Container = new Container();

  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];
  
  // Flag to track when tiles need to be redrawn
  private tilesNeedUpdate: boolean = true;
  
  // Last known position offset for movement detection
  private lastOffset = { x: 0, y: 0 };
  
  // Last known tile size for zoom detection
  private lastTileSize = 32;
  
  // NEW: Visibility-based alpha management for tiles
  private tileSprites: Map<string, Sprite | Graphics> = new Map(); // Track individual tile sprites/graphics
  
  // NEW: Cached senses data during movement to prevent visibility flickering
  private cachedSensesData: Map<string, { visible: Record<string, boolean>; seen: readonly Position[] }> = new Map();
  
  // NEW: Track last logged position for each entity to reduce console spam
  private lastLoggedPositions: Map<string, { x: number; y: number }> = new Map();
  
  // Summary logging system
  private lastSummaryTime = 0;
  private renderCount = 0;
  private gridChangeCount = 0;
  private viewChangeCount = 0;
  
  // NEW: Track last selected entity and visibility state
  private lastSelectedEntityId: string | undefined = undefined;
  private lastVisibilityEnabled: boolean = false;

  /**
   * Initialize the renderer
   */
  initialize(engine: any): void {
    super.initialize(engine);
    
    // Add background to container
    this.container.addChild(this.backgroundGraphics);
    
    // Add tiles container
    this.container.addChild(this.tilesContainer);
    
    // Setup subscriptions
    this.setupSubscriptions();
    
    // Initial tile data
    this.tilesRef = {...battlemapStore.grid.tiles};
    
    // Initialize last offset
    this.lastOffset = { 
      x: battlemapStore.view.offset.x, 
      y: battlemapStore.view.offset.y 
    };
    
    // Initialize last tile size
    this.lastTileSize = battlemapStore.view.tileSize;
    
    // Load textures
    this.loadTileTextures();
    
    // Force initial render
    this.tilesNeedUpdate = true;
    
    console.log('[TileRenderer] Initialized and added to tiles layer');
  }
  
  /**
   * Log summary every 10 seconds instead of spamming
   */
  private logSummary(): void {
    const now = Date.now();
    if (now - this.lastSummaryTime >= 10000) { // 10 seconds
      console.log(`[TileRenderer] 10s Summary: ${this.renderCount} renders, ${this.gridChangeCount} grid changes, ${this.viewChangeCount} view changes`);
      this.lastSummaryTime = now;
      this.renderCount = 0;
      this.gridChangeCount = 0;
      this.viewChangeCount = 0;
    }
  }
  
  /**
   * Set up subscriptions to the Valtio store
   */
  private setupSubscriptions(): void {
    // Store unsubscribe functions
    this.unsubscribeCallbacks = [];
    
    // Subscribe to grid changes (for tile updates)
    const unsubGrid = subscribe(battlemapStore.grid, () => {
      this.gridChangeCount++;
      // Only update tiles reference when not moving
      if (!battlemapStore.view.wasd_moving) {
        // Check if tiles have actually changed
        const hasChanges = this.hasTilesChanged(battlemapStore.grid.tiles);
        
        if (hasChanges) {
          this.tilesRef = {...battlemapStore.grid.tiles};
          this.loadTileTextures();
          this.tilesNeedUpdate = true;
        }
      }
      
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubGrid);
    
    // Subscribe to view changes (zooming, panning)
    const unsubView = subscribe(battlemapStore.view, () => {
      this.viewChangeCount++;
      // Always render on view changes for panning/zooming
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubView);
    
    // Subscribe to control changes (e.g., tile visibility)
    const unsubControls = subscribe(battlemapStore.controls, () => {
      // Only need to re-render if tile visibility changed
      if (battlemapStore.controls.isTilesVisible !== this.tilesContainer?.visible) {
        this.render();
      }
    });
    this.unsubscribeCallbacks.push(unsubControls);
    
    // NEW: Subscribe to movement animations to cache senses data when movement starts
    const unsubMovementAnimations = subscribe(battlemapStore.entities.movementAnimations, () => {
      this.handleMovementAnimationChanges();
    });
    this.unsubscribeCallbacks.push(unsubMovementAnimations);
    
    // NEW: Subscribe to entity selection changes to cache senses data when perspective changes during movement
    const unsubEntitySelection = subscribe(battlemapStore.entities, () => {
      this.handleEntitySelectionChange();
    });
    this.unsubscribeCallbacks.push(unsubEntitySelection);
    
    // NEW: Subscribe to pathSenses changes to trigger tile re-render when data becomes available
    const unsubPathSenses = subscribe(battlemapStore.entities.pathSenses, () => {
      // When path senses data becomes available, we need to re-render tiles immediately
      // This is a "hot swap" that provides dynamic visibility during movement
      this.tilesNeedUpdate = true;
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubPathSenses);
    
    // NEW: Subscribe to sprite mappings for snappy tile visibility updates during movement
    const unsubSpriteMappings = subscribe(battlemapStore.entities.spriteMappings, () => {
      // When visual positions change during movement, update tile visibility immediately
      // This makes tile visibility changes feel snappy and responsive
      const snap = battlemapStore;
      const selectedEntity = this.getSelectedEntity();
      
      // Only trigger re-render if the selected entity is moving (has dynamic path senses)
      if (selectedEntity && snap.entities.movementAnimations[selectedEntity.uuid] && snap.entities.pathSenses[selectedEntity.uuid]) {
        this.tilesNeedUpdate = true;
        this.render();
      }
    });
    this.unsubscribeCallbacks.push(unsubSpriteMappings);
  }
  
  /**
   * Check if the tiles have significantly changed to warrant a re-render
   * @param newTiles The new tiles from the store
   * @returns true if there are significant changes
   */
  private hasTilesChanged(newTiles: Record<string, TileSummary>): boolean {
    // Quick check: different number of tiles
    if (Object.keys(this.tilesRef).length !== Object.keys(newTiles).length) {
      return true;
    }
    
    // Check each tile for changes in sprite or position
    for (const key in newTiles) {
      const oldTile = this.tilesRef[key];
      const newTile = newTiles[key];
      
      // New tile that didn't exist before
      if (!oldTile) {
        return true;
      }
      
      // Check for sprite changes (this is what we care about most)
      if (oldTile.sprite_name !== newTile.sprite_name) {
        return true;
      }
      
      // Check for position changes (this might happen during movement)
      if (oldTile.position[0] !== newTile.position[0] || 
          oldTile.position[1] !== newTile.position[1]) {
        return true;
      }
      
      // Check for walkable changes (affects fallback color)
      if (oldTile.walkable !== newTile.walkable) {
        return true;
      }
    }
    
    // Check for removed tiles
    for (const key in this.tilesRef) {
      if (!newTiles[key]) {
        return true;
      }
    }
    
    // No significant changes detected
    return false;
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
    Object.values(snap.entities.movementAnimations).forEach(movement => {
      // If we don't have cached data for this movement, cache it now
      if (!this.cachedSensesData.has(selectedEntity.uuid)) {
        const sensesData = {
          visible: selectedEntity.senses.visible,
          seen: selectedEntity.senses.seen
        };
        this.cachedSensesData.set(selectedEntity.uuid, sensesData);
        console.log(`[TileRenderer] Cached senses data for selected entity ${selectedEntity.name} due to movement start`);
      }
    });
    
    // Check if any movements ended and clear cache if no movements are active
    if (Object.keys(snap.entities.movementAnimations).length === 0) {
      // No active movements - clear all cached senses data
      if (this.cachedSensesData.size > 0) {
        console.log(`[TileRenderer] Clearing all cached senses data - no active movements`);
        this.cachedSensesData.clear();
        // Force re-render when cache is cleared to update visibility
        this.tilesNeedUpdate = true;
        this.render();
      }
    }
  }
  
  /**
   * NEW: Public method to cache senses data for a specific entity
   * Called by InteractionsManager before movement starts
   */
  public cacheSensesDataForEntity(entityId: string, sensesData: { visible: Record<string, boolean>; seen: readonly Position[] }): void {
    this.cachedSensesData.set(entityId, sensesData);
    console.log(`[TileRenderer] Manually cached senses data for entity ${entityId}`);
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
        console.log(`[TileRenderer] Cached senses data for newly selected entity ${selectedEntity.name} during movement`);
        
        // Force re-render to apply new perspective
        this.tilesNeedUpdate = true;
        this.render();
      }
    }
  }
  
  /**
   * Load textures for all tiles
   */
  private loadTileTextures(): void {
    // Always load textures regardless of wasd_moving state
    Object.values(this.tilesRef).forEach(tile => {
      if (tile.sprite_name) {
        const spritePath = `/tiles/${tile.sprite_name}`;
        
        // Check if already in cache
        if (textureCache[spritePath]) {
          this.tileTextures[tile.uuid] = textureCache[spritePath];
        } else {
          // Load new texture async
          Assets.load(spritePath)
            .then(texture => {
              textureCache[spritePath] = texture;
              this.tileTextures[tile.uuid] = texture;
              // Flag tiles need update when texture is loaded
              this.tilesNeedUpdate = true;
              // Re-render tiles when texture is loaded
              this.renderTiles();
            })
            .catch(error => {
              console.error(`Error loading tile sprite ${spritePath}:`, error);
              this.tileTextures[tile.uuid] = null;
            });
        }
      } else {
        this.tileTextures[tile.uuid] = null;
      }
    });
  }
  
  /**
   * Calculate grid offset with proper centering
   */
  private calculateGridOffset(): { 
    offsetX: number; 
    offsetY: number; 
    tileSize: number;
    gridPixelWidth: number;
    gridPixelHeight: number;
  } {
    const snap = battlemapStore;
    
    // Get container size from engine
    const containerSize = this.engine?.containerSize || { width: 0, height: 0 };
    
    const availableWidth = containerSize.width - ENTITY_PANEL_WIDTH;
    const gridPixelWidth = snap.grid.width * snap.view.tileSize;
    const gridPixelHeight = snap.grid.height * snap.view.tileSize;
    
    // Center grid in the available space (starting from entity panel width)
    const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
    const baseOffsetY = (containerSize.height - gridPixelHeight) / 2;
    
    // Apply the offset from WASD controls
    const offsetX = baseOffsetX + snap.view.offset.x;
    const offsetY = baseOffsetY + snap.view.offset.y;
    
    return { 
      offsetX, 
      offsetY,
      tileSize: snap.view.tileSize,
      gridPixelWidth,
      gridPixelHeight
    };
  }
  
  /**
   * Main render method
   */
  render(): void {
    if (!this.engine || !this.engine.app) {
      return;
    }
    
    this.renderCount++;
    this.logSummary();
    
    // Update visibility based on controls
    this.tilesContainer.visible = battlemapStore.controls.isTilesVisible;
    
    // Always render background (it's cheap and handles position/zoom changes)
    this.renderBackground();
    
    // Check if position has changed (WASD movement) or if tiles need updating
    const hasPositionChanged = 
      this.lastOffset.x !== battlemapStore.view.offset.x || 
      this.lastOffset.y !== battlemapStore.view.offset.y;
    
    // Check if tile size has changed (zoom)
    const hasTileSizeChanged = this.lastTileSize !== battlemapStore.view.tileSize;
    
    // NEW: Check if visibility settings changed (selected entity or visibility enabled)
    const snap = battlemapStore;
    const currentSelectedEntity = snap.entities.selectedEntityId;
    const currentVisibilityEnabled = snap.controls.isVisibilityEnabled;
    const visibilityChanged = 
      this.lastSelectedEntityId !== currentSelectedEntity ||
      this.lastVisibilityEnabled !== currentVisibilityEnabled;
    
    // Render tiles if they need updating, position changed, size changed, visibility changed, or we're actively moving
    if (this.tilesNeedUpdate || hasPositionChanged || hasTileSizeChanged || visibilityChanged || battlemapStore.view.wasd_moving) {
      this.renderTiles();
      this.tilesNeedUpdate = false;
      
      // Update last known position and tile size after rendering
      this.lastOffset = { 
        x: battlemapStore.view.offset.x, 
        y: battlemapStore.view.offset.y 
      };
      this.lastTileSize = battlemapStore.view.tileSize;
      
      // NEW: Update last known visibility state
      this.lastSelectedEntityId = currentSelectedEntity;
      this.lastVisibilityEnabled = currentVisibilityEnabled;
    }
  }
  
  /**
   * Render the background
   */
  private renderBackground(): void {
    // Check if graphics is available
    if (!this.backgroundGraphics) {
      console.log('[TileRenderer] Background graphics not available');
      return;
    }
    
    // Get grid offset and sizes
    const { offsetX, offsetY, gridPixelWidth, gridPixelHeight } = this.calculateGridOffset();
    
    // Clear and redraw
    this.backgroundGraphics.clear();
    
    // Draw background - use pure black for seamless blend with React components
    this.backgroundGraphics
      .rect(
        offsetX,
        offsetY,
        gridPixelWidth,
        gridPixelHeight
      )
      .fill(0x000000);
  }
  
  /**
   * Render the tiles
   */
  private renderTiles(): void {
    // Check if container is available
    if (!this.tilesContainer) {
      console.log('[TileRenderer] Tiles container not available');
      return;
    }
    
    // Completely clear the tiles container before rendering new tiles
    this.tilesContainer.removeChildren();
    
    // NEW: Clear tile sprites tracking
    this.tileSprites.clear();
    
    // Get grid offset and sizes
    const { offsetX, offsetY, tileSize } = this.calculateGridOffset();
    
    // NEW: Get visibility info for conditional rendering
    const snap = battlemapStore;
    const selectedEntity = this.getSelectedEntity();
    const sensesData = selectedEntity && snap.controls.isVisibilityEnabled 
      ? this.getSensesDataForVisibility(selectedEntity) 
      : null;
    
    // Draw all tiles
    Object.values(this.tilesRef).forEach(tile => {
      const [x, y] = tile.position;
      const tileX = offsetX + (x * tileSize);
      const tileY = offsetY + (y * tileSize);
      const tileKey = `${x},${y}`;
      
      // NEW: Calculate visibility for this tile
      let visible = true;
      let seen = true;
      if (sensesData) {
        const posKey = `${x},${y}`;
        visible = !!sensesData.visible[posKey];
        seen = sensesData.seen.some(([seenX, seenY]) => seenX === x && seenY === y);
      }
      
      let tileSprite: Sprite | Graphics;
      
      if (!visible && !seen) {
        // Never seen - render black tile directly
        const blackTile = new Graphics();
        blackTile
          .rect(tileX, tileY, tileSize, tileSize)
          .fill(0x000000);
        this.tilesContainer.addChild(blackTile);
        tileSprite = blackTile;
      } else {
        // Visible or seen - render actual tile
        const texture = this.tileTextures[tile.uuid];
        
        if (texture) {
          // Use sprite for tiles with textures
          const sprite = new Sprite(texture);
          sprite.x = tileX;
          sprite.y = tileY;
          sprite.width = tileSize;
          sprite.height = tileSize;
          
          // Apply alpha for seen-but-not-visible tiles
          if (!visible && seen) {
            sprite.alpha = 0.4;
          }
          
          this.tilesContainer.addChild(sprite);
          tileSprite = sprite;
        } else {
          // Use a fallback color for tiles without textures
          const tileGraphics = new Graphics();
          const color = tile.walkable ? 0x333333 : 0x666666;
          
          tileGraphics
            .rect(tileX, tileY, tileSize, tileSize)
            .fill(color);
          
          // Apply alpha for seen-but-not-visible tiles
          if (!visible && seen) {
            tileGraphics.alpha = 0.4;
          }
            
          this.tilesContainer.addChild(tileGraphics);
          tileSprite = tileGraphics;
        }
      }
      
      // NEW: Track this tile sprite for any future updates
      this.tileSprites.set(tileKey, tileSprite);
    });
    
    console.log('[TileRenderer] Rendered tiles:', this.tilesContainer.children.length);
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
  private getSensesDataForVisibility(entity: EntitySummary): {
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
              console.log(`[TileRenderer] Using dynamic path senses for ${entity.name} at position (${currentX}, ${currentY})`);
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
        console.log(`[TileRenderer] Using cached static senses for observer ${entity.name} while other entities move`);
        return cached;
      }
      
      console.warn(`[TileRenderer] No cached senses data for observer ${entity.name} during other movements - using current data`);
    }
    
    // No movements or fallback - use current data
    return {
      visible: entity.senses.visible,
      seen: entity.senses.seen
    };
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // Unsubscribe from all subscriptions
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
    // NEW: Clean up tile visibility tracking
    this.tileSprites.clear();
    
    // NEW: Clean up cached senses data
    this.cachedSensesData.clear();
    
    // NEW: Clean up position tracking
    this.lastLoggedPositions.clear();
    
    // Clear and destroy tiles container safely
    if (this.tilesContainer) {
      this.tilesContainer.removeChildren();
      try {
        if (!this.tilesContainer.destroyed) {
          this.tilesContainer.destroy({ children: true });
        }
      } catch (e) {
        console.warn('[TileRenderer] Error destroying tiles container:', e);
      }
    }
    
    // Clear and destroy background graphics safely
    if (this.backgroundGraphics) {
      try {
        if (this.backgroundGraphics.clear) {
          this.backgroundGraphics.clear();
        }
        if (!this.backgroundGraphics.destroyed) {
          this.backgroundGraphics.destroy();
        }
      } catch (e) {
        console.warn('[TileRenderer] Error destroying background graphics:', e);
      }
    }
    
    // Call parent destroy
    super.destroy();
  }
} 