import { Graphics, Texture, Sprite, Assets, Container } from 'pixi.js';
import { battlemapStore } from '../../store';
import { TileSummary } from '../../types/battlemap_types';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';

// Create a texture cache
const textureCache: Record<string, Texture> = {};

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * TileRenderer handles rendering the map tiles
 */
export class TileRenderer extends AbstractRenderer {
  // Texture cache reference
  private tileTextures: Record<string, Texture | null> = {};
  
  // Graphics references
  private backgroundGraphics: Graphics = new Graphics();
  
  // Reference to tiles for stable rendering during movement
  private tilesRef: Record<string, TileSummary> = {};
  
  // Container for tiles to make cleanup easier
  private tilesContainer: Container = new Container();

  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];
  
  // Flag to track when tiles need to be redrawn
  private tilesNeedUpdate: boolean = true;
  
  // Last known position offset for movement detection
  private lastOffset = { x: 0, y: 0 };

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
    
    // Load textures
    this.loadTileTextures();
    
    // Force initial render
    this.tilesNeedUpdate = true;
    
    console.log('[TileRenderer] Initialized');
  }
  
  /**
   * Set up subscriptions to the Valtio store
   */
  private setupSubscriptions(): void {
    // Store unsubscribe functions
    this.unsubscribeCallbacks = [];
    
    // Subscribe to grid changes (for tile updates)
    const unsubGrid = subscribe(battlemapStore.grid, () => {
      console.log('[TileRenderer] Grid changed, checking for tile updates');
      // Only update tiles reference when not moving
      if (!battlemapStore.view.wasd_moving) {
        // Check if tiles have actually changed
        const hasChanges = this.hasTilesChanged(battlemapStore.grid.tiles);
        
        if (hasChanges) {
          console.log('[TileRenderer] Tile changes detected, updating');
          this.tilesRef = {...battlemapStore.grid.tiles};
          this.loadTileTextures();
          this.tilesNeedUpdate = true;
        } else {
          console.log('[TileRenderer] No significant tile changes, skipping update');
        }
      }
      
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubGrid);
    
    // Subscribe to view changes (zooming, panning)
    const unsubView = subscribe(battlemapStore.view, () => {
      // Check if position has changed (movement)
      if (this.lastOffset.x !== battlemapStore.view.offset.x || 
          this.lastOffset.y !== battlemapStore.view.offset.y) {
        // Movement detected, update last offset
        this.lastOffset = { 
          x: battlemapStore.view.offset.x, 
          y: battlemapStore.view.offset.y 
        };
      }
      
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
   * Render everything
   */
  render(): void {
    // Skip if not properly initialized
    if (!this.engine || !this.engine.app) {
      console.log('[TileRenderer] Skipping render - engine not ready');
      return;
    }
    
    const snap = battlemapStore;
    
    // If tiles are set to invisible, clear everything and return
    if (!snap.controls.isTilesVisible) {
      if (this.backgroundGraphics) {
        this.backgroundGraphics.clear();
      }
      if (this.tilesContainer) {
        this.tilesContainer.visible = false;
      }
      return;
    }
    
    // Otherwise render everything and ensure tiles are visible
    if (this.tilesContainer) {
      this.tilesContainer.visible = true;
    }
    
    // Always render the background (it's cheap)
    this.renderBackground();
    
    // Only render tiles if needed (position change or tile content change)
    const hasPositionChanged = 
      this.lastOffset.x !== snap.view.offset.x || 
      this.lastOffset.y !== snap.view.offset.y;
      
    if (this.tilesNeedUpdate || hasPositionChanged || snap.view.wasd_moving) {
      this.renderTiles();
      // Reset flag after rendering
      this.tilesNeedUpdate = false;
      // Update last known position
      this.lastOffset = { 
        x: snap.view.offset.x, 
        y: snap.view.offset.y 
      };
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
    
    // Get grid offset and sizes
    const { offsetX, offsetY, tileSize } = this.calculateGridOffset();
    
    // Draw all tiles
    Object.values(this.tilesRef).forEach(tile => {
      const [x, y] = tile.position;
      const tileX = offsetX + (x * tileSize);
      const tileY = offsetY + (y * tileSize);
      
      // Check if we have a texture for this tile
      const texture = this.tileTextures[tile.uuid];
      
      if (texture) {
        // Use sprite for tiles with textures
        const sprite = new Sprite(texture);
        sprite.x = tileX;
        sprite.y = tileY;
        sprite.width = tileSize;
        sprite.height = tileSize;
        this.tilesContainer.addChild(sprite);
      } else {
        // Use a fallback color for tiles without textures
        const tileGraphics = new Graphics();
        const color = tile.walkable ? 0x333333 : 0x666666;
        
        tileGraphics
          .rect(tileX, tileY, tileSize, tileSize)
          .fill(color);
          
        this.tilesContainer.addChild(tileGraphics);
      }
    });
    
    console.log('[TileRenderer] Rendered tiles:', this.tilesContainer.children.length);
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // Unsubscribe from all subscriptions
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
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