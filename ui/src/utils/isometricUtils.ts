import { Direction } from '../types/battlemap_types';
import { GRID_STROKE_WIDTH, ISOMETRIC_TILE_WIDTH, ISOMETRIC_TILE_HEIGHT } from '../constants/layout';

/**
 * Convert grid coordinates to isometric screen coordinates
 * @param gridX Grid X coordinate
 * @param gridY Grid Y coordinate
 * @returns Screen coordinates in isometric perspective
 */
export function gridToIsometric(gridX: number, gridY: number): { isoX: number; isoY: number } {
  // Precise isometric transformation
  // In isometric view: X goes right-down diagonal, Y goes left-down diagonal
  const isoX = (gridX - gridY) * (ISOMETRIC_TILE_WIDTH / 2);
  const isoY = (gridX + gridY) * (ISOMETRIC_TILE_HEIGHT / 2);
  
  return { isoX, isoY };
}

/**
 * Convert isometric screen coordinates back to grid coordinates
 * @param isoX Isometric screen X coordinate (relative to grid origin)
 * @param isoY Isometric screen Y coordinate (relative to grid origin)
 * @returns Grid coordinates
 */
export function isometricToGrid(isoX: number, isoY: number): { gridX: number; gridY: number } {
  // Precise inverse isometric transformation
  // Solving the system of equations:
  // isoX = (gridX - gridY) * (TILE_WIDTH / 2)
  // isoY = (gridX + gridY) * (TILE_HEIGHT / 2)
  
  // Rearrange to solve for gridX and gridY:
  // Let A = TILE_WIDTH / 2, B = TILE_HEIGHT / 2
  // isoX = (gridX - gridY) * A  =>  isoX/A = gridX - gridY
  // isoY = (gridX + gridY) * B  =>  isoY/B = gridX + gridY
  //
  // Adding: isoX/A + isoY/B = 2*gridX  =>  gridX = (isoX/A + isoY/B) / 2
  // Subtracting: isoY/B - isoX/A = 2*gridY  =>  gridY = (isoY/B - isoX/A) / 2
  
  const A = ISOMETRIC_TILE_WIDTH / 2;   // 32
  const B = ISOMETRIC_TILE_HEIGHT / 2;  // 16
  
  const gridX = (isoX / A + isoY / B) / 2;
  const gridY = (isoY / B - isoX / A) / 2;
  
  return { 
    gridX: Math.floor(gridX + 0.5), // Round to nearest integer instead of just floor
    gridY: Math.floor(gridY + 0.5)  // Round to nearest integer instead of just floor
  };
}

/**
 * Convert screen pixel coordinates to grid coordinates (for mouse interaction)
 * This is the critical function for mouse highlighting to work correctly
 * @param screenX Screen X coordinate
 * @param screenY Screen Y coordinate
 * @param offsetX Grid origin X offset in screen coordinates
 * @param offsetY Grid origin Y offset in screen coordinates
 * @param scaleFactor Scale factor applied to the isometric grid
 * @param gridWidth Width of the grid in tiles
 * @param gridHeight Height of the grid in tiles
 * @returns Grid coordinates and bounds check
 */
export function screenToGrid(
  screenX: number, 
  screenY: number, 
  offsetX: number, 
  offsetY: number, 
  scaleFactor: number,
  gridWidth: number,
  gridHeight: number
): { gridX: number; gridY: number; inBounds: boolean } {
  // Convert screen coordinates to isometric space (relative to grid origin)
  const relativeX = screenX - offsetX;
  const relativeY = screenY - offsetY;
  
  // Scale back to unscaled isometric coordinates
  const isoX = relativeX / scaleFactor;
  const isoY = relativeY / scaleFactor;
  
  // Use precise inverse isometric transformation directly
  const A = ISOMETRIC_TILE_WIDTH / 2;   // 32
  const B = ISOMETRIC_TILE_HEIGHT / 2;  // 16
  
  // Solve the inverse transformation precisely:
  // isoX = (gridX - gridY) * A  =>  isoX/A = gridX - gridY
  // isoY = (gridX + gridY) * B  =>  isoY/B = gridX + gridY
  // Adding: isoX/A + isoY/B = 2*gridX  =>  gridX = (isoX/A + isoY/B) / 2
  // Subtracting: isoY/B - isoX/A = 2*gridY  =>  gridY = (isoY/B - isoX/A) / 2
  
  const gridXFloat = (isoX / A + isoY / B) / 2;
  const gridYFloat = (isoY / B - isoX / A) / 2;
  
  // Round to nearest integer for grid coordinates
  const gridX = Math.round(gridXFloat);
  const gridY = Math.round(gridYFloat);
  
  // Check bounds strictly
  const inBoundsX = gridX >= 0 && gridX < gridWidth;
  const inBoundsY = gridY >= 0 && gridY < gridHeight;
  const inBounds = inBoundsX && inBoundsY;
  
  return {
    gridX: inBounds ? gridX : -1,
    gridY: inBounds ? gridY : -1,
    inBounds
  };
}

/**
 * Calculate isometric grid offset with proper centering
 * @param containerWidth Width of the container
 * @param containerHeight Height of the container
 * @param gridWidth Width of the grid in tiles
 * @param gridHeight Height of the grid in tiles
 * @param tileSize Current tile size (used as scale factor)
 * @param offsetX WASD offset X
 * @param offsetY WASD offset Y
 * @param entityPanelWidth Width of the entity panel to account for
 * @returns Grid positioning information
 */
export function calculateIsometricGridOffset(
  containerWidth: number,
  containerHeight: number,
  gridWidth: number,
  gridHeight: number,
  tileSize: number,
  offsetX: number,
  offsetY: number,
  entityPanelWidth: number = 250
): { 
  offsetX: number; 
  offsetY: number; 
  tileSize: number;
  gridPixelWidth: number;
  gridPixelHeight: number;
  gridWidth: number;
  gridHeight: number;
} {
  // Calculate the bounds of the isometric grid
  // The grid extends from top-left corner to bottom-right corner in isometric space
  const topLeft = gridToIsometric(0, 0);
  const topRight = gridToIsometric(gridWidth - 1, 0);
  const bottomLeft = gridToIsometric(0, gridHeight - 1);
  const bottomRight = gridToIsometric(gridWidth - 1, gridHeight - 1);
  
  // Find the actual bounds of the isometric grid
  const minX = Math.min(topLeft.isoX, topRight.isoX, bottomLeft.isoX, bottomRight.isoX);
  const maxX = Math.max(topLeft.isoX, topRight.isoX, bottomLeft.isoX, bottomRight.isoX);
  const minY = Math.min(topLeft.isoY, topRight.isoY, bottomLeft.isoY, bottomRight.isoY);
  const maxY = Math.max(topLeft.isoY, topRight.isoY, bottomLeft.isoY, bottomRight.isoY);
  
  const gridPixelWidth = maxX - minX + ISOMETRIC_TILE_WIDTH;
  const gridPixelHeight = maxY - minY + ISOMETRIC_TILE_HEIGHT;
  
  // Scale the grid so isometric tiles have the same effective size as square tiles
  // We want each isometric diamond to occupy the same screen space as a square tile
  const targetTileSize = tileSize * 1.2; // Make tiles 20% bigger (was 10%, now 20%)
  const isometricScale = targetTileSize / ISOMETRIC_TILE_WIDTH; // Scale to match square tile size
  const scaledWidth = gridPixelWidth * isometricScale;
  const scaledHeight = gridPixelHeight * isometricScale;
  
  const availableWidth = containerWidth - entityPanelWidth;
  
  // Center the isometric grid in the available space
  const baseOffsetX = entityPanelWidth + (availableWidth - scaledWidth) / 2;
  const baseOffsetY = (containerHeight - scaledHeight) / 2;
  
  // Apply the offset from WASD controls
  const finalOffsetX = baseOffsetX + offsetX - (minX * isometricScale);
  const finalOffsetY = baseOffsetY + offsetY - (minY * isometricScale);
  
  return { 
    offsetX: finalOffsetX, 
    offsetY: finalOffsetY,
    tileSize: isometricScale, // Return scale factor
    gridPixelWidth: scaledWidth,
    gridPixelHeight: scaledHeight,
    gridWidth,
    gridHeight
  };
}

/**
 * Calculate diamond corners for isometric tile rendering
 * @param centerX Center X coordinate of the diamond
 * @param centerY Center Y coordinate of the diamond
 * @param tileSize Scale factor for the tile
 * @param strokeOffset Optional stroke offset for grid lines
 * @returns Diamond corner coordinates
 */
export function calculateIsometricDiamondCorners(
  centerX: number,
  centerY: number,
  tileSize: number,
  strokeOffset: number = 0
): {
  topX: number; topY: number;
  rightX: number; rightY: number;
  bottomX: number; bottomY: number;
  leftX: number; leftY: number;
} {
  const tileWidthHalf = (ISOMETRIC_TILE_WIDTH / 2) * tileSize;
  const tileHeightHalf = (ISOMETRIC_TILE_HEIGHT / 2) * tileSize;
  
  return {
    topX: centerX,
    topY: centerY - tileHeightHalf + strokeOffset,
    
    rightX: centerX + tileWidthHalf - strokeOffset,
    rightY: centerY,
    
    bottomX: centerX,
    bottomY: centerY + tileHeightHalf - strokeOffset,
    
    leftX: centerX - tileWidthHalf + strokeOffset,
    leftY: centerY
  };
}

/**
 * Convert absolute direction to isometric direction
 * In isometric view, absolute North appears as NE, East as SE, etc.
 * This accounts for the 45-degree rotation of the isometric perspective
 */
export function convertToIsometricDirection(absoluteDirection: Direction): Direction {
  const directionMap: Record<Direction, Direction> = {
    [Direction.N]: Direction.NE,   // North becomes Northeast
    [Direction.NE]: Direction.E,   // Northeast becomes East
    [Direction.E]: Direction.SE,   // East becomes Southeast
    [Direction.SE]: Direction.S,   // Southeast becomes South
    [Direction.S]: Direction.SW,   // South becomes Southwest
    [Direction.SW]: Direction.W,   // Southwest becomes West
    [Direction.W]: Direction.NW,   // West becomes Northwest
    [Direction.NW]: Direction.N    // Northwest becomes North
  };
  
  return directionMap[absoluteDirection];
} 