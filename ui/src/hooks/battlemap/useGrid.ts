import { useCallback, useState } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { TileSummary } from '../../api/tileApi';

/**
 * Hook for grid operations and calculations
 */
export const useGrid = () => {
  const snap = useSnapshot(battlemapStore);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  
  /**
   * Set tile size
   */
  const setTileSize = useCallback((size: number) => {
    battlemapActions.setTileSize(size);
  }, []);
  
  /**
   * Get grid dimensions
   */
  const getGridDimensions = useCallback(() => {
    return {
      width: snap.grid.width,
      height: snap.grid.height
    };
  }, [snap.grid.width, snap.grid.height]);
  
  /**
   * Calculate offset to center grid in container
   */
  const calculateGridOffset = useCallback((containerWidth: number, containerHeight: number) => {
    const tileSize = snap.view.tileSize;
    const offsetX = (containerWidth - (snap.grid.width * tileSize)) / 2;
    const offsetY = (containerHeight - (snap.grid.height * tileSize)) / 2;
    
    return { 
      offsetX: offsetX + snap.view.offset.x, 
      offsetY: offsetY + snap.view.offset.y 
    };
  }, [snap.grid.width, snap.grid.height, snap.view.tileSize, snap.view.offset.x, snap.view.offset.y]);
  
  /**
   * Convert grid coordinates to pixel coordinates
   */
  const gridToPixel = useCallback((x: number, y: number, containerWidth: number, containerHeight: number) => {
    const { offsetX, offsetY } = calculateGridOffset(containerWidth, containerHeight);
    const tileSize = snap.view.tileSize;
    
    const pixelX = offsetX + (x * tileSize);
    const pixelY = offsetY + (y * tileSize);
    
    return { pixelX, pixelY };
  }, [calculateGridOffset, snap.view.tileSize]);
  
  /**
   * Convert grid coordinates to pixel coordinates with centering within tile
   */
  const gridToPixelCentered = useCallback((x: number, y: number, containerWidth: number, containerHeight: number) => {
    const { pixelX, pixelY } = gridToPixel(x, y, containerWidth, containerHeight);
    const tileSize = snap.view.tileSize;
    
    return { 
      pixelX: pixelX + (tileSize / 2), 
      pixelY: pixelY + (tileSize / 2) 
    };
  }, [gridToPixel, snap.view.tileSize]);
  
  /**
   * Convert pixel coordinates to grid coordinates
   */
  const pixelToGrid = useCallback((pixelX: number, pixelY: number, containerWidth: number, containerHeight: number) => {
    const { offsetX, offsetY } = calculateGridOffset(containerWidth, containerHeight);
    const tileSize = snap.view.tileSize;
    
    const gridX = Math.floor((pixelX - offsetX) / tileSize);
    const gridY = Math.floor((pixelY - offsetY) / tileSize);
    
    return { gridX, gridY };
  }, [calculateGridOffset, snap.view.tileSize]);
  
  /**
   * Check if coordinates are within the grid
   */
  const isInGrid = useCallback((x: number, y: number) => {
    return x >= 0 && x < snap.grid.width && y >= 0 && y < snap.grid.height;
  }, [snap.grid.width, snap.grid.height]);
  
  /**
   * Get tile at grid coordinates
   */
  const getTileAt = useCallback((x: number, y: number): TileSummary | undefined => {
    const posKey = `${x},${y}`;
    return snap.grid.tiles[posKey];
  }, [snap.grid.tiles]);
  
  /**
   * Check if tile is walkable
   */
  const isTileWalkable = useCallback((x: number, y: number): boolean => {
    const tile = getTileAt(x, y);
    return tile?.walkable ?? false;
  }, [getTileAt]);
  
  /**
   * Handle cell click
   */
  const handleCellClick = useCallback((x: number, y: number, optimisticUpdateFn?: (tile: TileSummary) => void) => {
    if (!isInGrid(x, y)) return;
    
    // Handle optimistic update if provided
    if (optimisticUpdateFn) {
      const tile = getTileAt(x, y);
      if (tile) {
        optimisticUpdateFn(tile);
      }
    }
    
    // Set hovered cell 
    battlemapActions.setHoveredCell(x, y);
  }, [isInGrid, getTileAt]);
  
  /**
   * Update hovered cell
   */
  const updateHoveredCell = useCallback((x: number, y: number) => {
    if (isInGrid(x, y)) {
      battlemapActions.setHoveredCell(x, y);
    } else {
      // If outside grid, set to invalid coordinates
      battlemapActions.setHoveredCell(-1, -1);
    }
  }, [isInGrid]);
  
  return {
    // Dimensions
    gridWidth: snap.grid.width,
    gridHeight: snap.grid.height,
    tileSize: snap.view.tileSize,
    
    // Current hover state
    hoveredCell: snap.view.hoveredCell,
    
    // Container size state
    containerSize,
    setContainerSize,
    
    // Tile size control
    setTileSize,
    
    // Methods
    getGridDimensions,
    calculateGridOffset,
    gridToPixel,
    gridToPixelCentered,
    pixelToGrid,
    isInGrid,
    getTileAt,
    isTileWalkable,
    handleCellClick,
    updateHoveredCell
  };
}; 