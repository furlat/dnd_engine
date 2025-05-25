import { Graphics, Sprite, Assets, Container } from 'pixi.js';
import { TileSummary } from '../../types/battlemap_types';

// Define minimum width of entity panel (shared constant)
export const ENTITY_PANEL_WIDTH = 250;

/**
 * Calculate grid offset with proper centering
 * This is used by multiple renderers for consistent positioning
 */
export function calculateGridOffset(
  containerSize: { width: number; height: number },
  gridWidth: number,
  gridHeight: number,
  tileSize: number,
  viewOffset: { x: number; y: number }
): { 
  offsetX: number; 
  offsetY: number; 
  tileSize: number;
  gridPixelWidth: number;
  gridPixelHeight: number;
  gridWidth: number;
  gridHeight: number;
} {
  const availableWidth = containerSize.width - ENTITY_PANEL_WIDTH;
  const gridPixelWidth = gridWidth * tileSize;
  const gridPixelHeight = gridHeight * tileSize;
  
  // Center grid in the available space (starting from entity panel width)
  const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
  const baseOffsetY = (containerSize.height - gridPixelHeight) / 2;
  
  // Apply the offset from WASD controls
  const offsetX = baseOffsetX + viewOffset.x;
  const offsetY = baseOffsetY + viewOffset.y;
  
  return { 
    offsetX, 
    offsetY,
    tileSize,
    gridPixelWidth,
    gridPixelHeight,
    gridWidth,
    gridHeight
  };
}

/**
 * Add a color-based tile mask to a container
 * Used when tile sprites are not available or for masking purposes
 */
export function addColorTileMask(
  container: Container,
  x: number, 
  y: number, 
  tile: TileSummary, 
  offsetX: number, 
  offsetY: number, 
  tileSize: number
): void {
  const tileMask = new Graphics();
  const tileColor = tile.walkable ? 0x333333 : 0x666666; // Same fallback colors as TileRenderer
  
  tileMask
    .rect(
      offsetX + (x * tileSize),
      offsetY + (y * tileSize),
      tileSize,
      tileSize
    )
    .fill({ color: tileColor, alpha: 1.0 });
  
  container.addChild(tileMask);
}

/**
 * Add a tile sprite or fallback to color if sprite not available
 * Used for rendering tiles consistently across renderers
 */
export function addTileToContainer(
  container: Container,
  x: number,
  y: number,
  tile: TileSummary,
  offsetX: number,
  offsetY: number,
  tileSize: number
): void {
  if (tile.sprite_name) {
    // Try to use the actual tile sprite
    try {
      const spritePath = `/tiles/${tile.sprite_name}`;
      const texture = Assets.cache.get(spritePath);
      
      if (texture) {
        const tileSprite = new Sprite(texture);
        tileSprite.x = offsetX + (x * tileSize);
        tileSprite.y = offsetY + (y * tileSize);
        tileSprite.width = tileSize;
        tileSprite.height = tileSize;
        container.addChild(tileSprite);
        return;
      }
    } catch (error) {
      // Fall through to color fallback
    }
  }
  
  // Fallback to color if no sprite or sprite not available
  addColorTileMask(container, x, y, tile, offsetX, offsetY, tileSize);
}

/**
 * Create a simple colored tile graphic
 * Used for backgrounds and fallbacks
 */
export function createColorTile(
  x: number,
  y: number,
  tileSize: number,
  color: number,
  alpha: number = 1.0
): Graphics {
  const tile = new Graphics();
  tile
    .rect(x, y, tileSize, tileSize)
    .fill({ color, alpha });
  return tile;
} 