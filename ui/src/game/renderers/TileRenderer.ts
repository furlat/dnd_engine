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
    
    // Load textures
    this.loadTileTextures();
    
    console.log('[TileRenderer] Initialized');
  }
  
  /**
   * Set up subscriptions to the Valtio store
   */
  private setupSubscriptions(): void {
    // Subscribe to grid changes (for tile updates)
    subscribe(battlemapStore.grid, () => {
      console.log('[TileRenderer] Grid changed, updating tiles');
      // Only update tiles reference when not moving
      if (!battlemapStore.view.wasd_moving) {
        this.tilesRef = {...battlemapStore.grid.tiles};
        this.loadTileTextures();
      }
      
      this.render();
    });
    
    // Subscribe to view changes (zooming, panning)
    subscribe(battlemapStore.view, () => {
      this.render();
    });
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
    this.renderBackground();
    this.renderTiles();
  }
  
  /**
   * Render the background
   */
  private renderBackground(): void {
    // Get grid offset and sizes
    const { offsetX, offsetY, gridPixelWidth, gridPixelHeight } = this.calculateGridOffset();
    
    // Clear and redraw
    this.backgroundGraphics.clear();
    
    // Draw background
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
    // Clear and destroy tiles container
    this.tilesContainer.removeChildren();
    this.tilesContainer.destroy({ children: true });
    
    // Clear and destroy background graphics
    this.backgroundGraphics.clear();
    this.backgroundGraphics.destroy();
    
    // Call parent destroy
    super.destroy();
  }
} 