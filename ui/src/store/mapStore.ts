import { proxy } from 'valtio';

// Base state interface for the map store
export interface MapStoreState {
  // Grid parameters
  gridWidth: number;
  gridHeight: number;
  tileSize: number;
  
  // Movement offsets (from WASD)
  gridOffsetX: number;
  gridOffsetY: number;
  
  // Container dimensions
  containerWidth: number;
  containerHeight: number;
  
  // UI state
  isGridEnabled: boolean;
  isVisibilityEnabled: boolean;
  isMovementHighlightEnabled: boolean;
  isLocked: boolean;
}

// Initialize the store with default values
const mapStore = proxy<MapStoreState>({
  gridWidth: 30,
  gridHeight: 20,
  tileSize: 32,
  gridOffsetX: 0,
  gridOffsetY: 0,
  containerWidth: window.innerWidth,
  containerHeight: window.innerHeight,
  isGridEnabled: true,
  isVisibilityEnabled: true,
  isMovementHighlightEnabled: false,
  isLocked: false
});

// Helper functions for position calculations
const mapHelpers = {
  // Get grid offset (center of canvas)
  getGridBaseOffset: () => {
    const offsetX = (mapStore.containerWidth - (mapStore.gridWidth * mapStore.tileSize)) / 2;
    const offsetY = (mapStore.containerHeight - (mapStore.gridHeight * mapStore.tileSize)) / 2;
    return { offsetX, offsetY };
  },
  
  // Convert grid coordinates to pixel coordinates (without WASD movement offset)
  // The container handles the WASD movement offset separately
  gridToPixel: (gridX: number, gridY: number) => {
    const { offsetX, offsetY } = mapHelpers.getGridBaseOffset();
    return {
      x: offsetX + (gridX * mapStore.tileSize) + (mapStore.tileSize / 2),
      y: offsetY + (gridY * mapStore.tileSize) + (mapStore.tileSize / 2)
    };
  },
  
  // Convert pixel coordinates to grid coordinates (accounting for WASD movement)
  pixelToGrid: (pixelX: number, pixelY: number) => {
    const { offsetX, offsetY } = mapHelpers.getGridBaseOffset();
    // Subtract grid offset since it's applied at container level
    const adjustedX = pixelX - mapStore.gridOffsetX;
    const adjustedY = pixelY - mapStore.gridOffsetY;
    
    const gridX = Math.floor((adjustedX - offsetX) / mapStore.tileSize);
    const gridY = Math.floor((adjustedY - offsetY) / mapStore.tileSize);
    
    return { gridX, gridY };
  },
  
  // Check if grid coordinates are valid
  isValidGridPosition: (gridX: number, gridY: number) => {
    return gridX >= 0 && gridX < mapStore.gridWidth && gridY >= 0 && gridY < mapStore.gridHeight;
  }
};

// Actions to mutate the store
const mapActions = {
  setGridDimensions: (width: number, height: number) => {
    mapStore.gridWidth = width;
    mapStore.gridHeight = height;
  },
  
  setTileSize: (tileSize: number) => {
    // Limit tile size to prevent extreme values
    const MIN_TILE_SIZE = 8;
    const MAX_TILE_SIZE = 128;
    
    mapStore.tileSize = Math.max(MIN_TILE_SIZE, Math.min(MAX_TILE_SIZE, tileSize));
  },
  
  zoomIn: () => {
    const TILE_SIZE_STEP = 16;
    mapActions.setTileSize(mapStore.tileSize + TILE_SIZE_STEP);
  },
  
  zoomOut: () => {
    const TILE_SIZE_STEP = 16;
    mapActions.setTileSize(mapStore.tileSize - TILE_SIZE_STEP);
  },
  
  resetZoom: () => {
    mapActions.setTileSize(32); // Reset to default tile size
  },
  
  moveGrid: (dx: number, dy: number) => {
    mapStore.gridOffsetX += dx;
    mapStore.gridOffsetY += dy;
  },
  
  resetPosition: () => {
    mapStore.gridOffsetX = 0;
    mapStore.gridOffsetY = 0;
  },
  
  setContainerSize: (width: number, height: number) => {
    mapStore.containerWidth = width;
    mapStore.containerHeight = height;
  },
  
  toggleGrid: () => {
    mapStore.isGridEnabled = !mapStore.isGridEnabled;
  },
  
  toggleVisibility: () => {
    mapStore.isVisibilityEnabled = !mapStore.isVisibilityEnabled;
  },
  
  toggleMovementHighlight: () => {
    mapStore.isMovementHighlightEnabled = !mapStore.isMovementHighlightEnabled;
  },
  
  toggleLock: () => {
    mapStore.isLocked = !mapStore.isLocked;
  },
  
  resetView: () => {
    mapActions.resetZoom();
    mapActions.resetPosition();
  }
};

// Export both store and actions
export { mapStore, mapActions, mapHelpers }; 