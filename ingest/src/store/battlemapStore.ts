import { proxy } from 'valtio';
import { TileSummary } from '../types/battlemap_types';
import { EntitySummary } from '../types/common';
import type { DeepReadonly } from '../types/common';
import { Direction } from '../components/battlemap/DirectionalEntitySprite';
import { fetchGridSnapshot, fetchEntitySummaries } from '../api/battlemap/battlemapApi';
import { TileType } from '../hooks/battlemap';

// Types for the store
export interface GridState {
  width: number;
  height: number;
  tiles: Record<string, TileSummary>;
}

export interface ViewState {
  tileSize: number;
  offset: { x: number; y: number };
  hoveredCell: { x: number; y: number };
  wasd_moving: boolean;
}

export interface ControlState {
  isLocked: boolean;
  isGridVisible: boolean;
  isVisibilityEnabled: boolean;
  isMovementHighlightEnabled: boolean;
  isMusicPlayerMinimized: boolean;
  // Tile editor controls
  isEditing: boolean;
  isEditorVisible: boolean;
  selectedTileType: TileType;
}

export interface EntityState {
  summaries: Record<string, EntitySummary>;
  selectedEntityId: string | undefined;
  displayedEntityId: string | undefined;
  directions: Record<string, Direction>;
  // Will expand with animation states later
}

export interface BattlemapStoreState {
  grid: GridState;
  view: ViewState;
  controls: ControlState;
  entities: EntityState;
  loading: boolean;
  error: string | null;
}

// Read-only type for consuming components
export type ReadonlyBattlemapStore = DeepReadonly<BattlemapStoreState>;

// Initialize the store with default values
const battlemapStore = proxy<BattlemapStoreState>({
  grid: {
    width: 30,
    height: 20,
    tiles: {},
  },
  view: {
    tileSize: 32,
    offset: { x: 0, y: 0 },
    hoveredCell: { x: -1, y: -1 },
    wasd_moving: false,
  },
  controls: {
    isLocked: false,
    isGridVisible: true,
    isVisibilityEnabled: true,
    isMovementHighlightEnabled: false,
    isMusicPlayerMinimized: true,
    // Tile editor defaults
    isEditing: false,
    isEditorVisible: false,
    selectedTileType: 'floor',
  },
  entities: {
    summaries: {},
    selectedEntityId: undefined,
    displayedEntityId: undefined,
    directions: {},
  },
  loading: false,
  error: null,
});

// Polling configuration
const POLLING_INTERVAL = 200; // Match previous 200ms rate for responsive updates
let pollingInterval: NodeJS.Timeout | null = null;

// Actions to mutate the store
const battlemapActions = {
  // Grid actions
  setGridDimensions: (width: number, height: number) => {
    battlemapStore.grid.width = width;
    battlemapStore.grid.height = height;
  },
  
  setTiles: (tiles: Record<string, TileSummary>) => {
    battlemapStore.grid.tiles = tiles;
  },
  
  // View actions
  setTileSize: (size: number) => {
    battlemapStore.view.tileSize = size;
  },
  
  setOffset: (x: number, y: number) => {
    battlemapStore.view.offset.x = x;
    battlemapStore.view.offset.y = y;
  },
  
  setHoveredCell: (x: number, y: number) => {
    battlemapStore.view.hoveredCell.x = x;
    battlemapStore.view.hoveredCell.y = y;
  },
  
  setWasdMoving: (moving: boolean) => {
    battlemapStore.view.wasd_moving = moving;
  },
  
  // Controls actions
  setLocked: (locked: boolean) => {
    battlemapStore.controls.isLocked = locked;
  },
  
  setGridVisible: (visible: boolean) => {
    battlemapStore.controls.isGridVisible = visible;
  },
  
  setVisibilityEnabled: (enabled: boolean) => {
    battlemapStore.controls.isVisibilityEnabled = enabled;
  },
  
  setMovementHighlightEnabled: (enabled: boolean) => {
    battlemapStore.controls.isMovementHighlightEnabled = enabled;
  },
  
  setMusicPlayerMinimized: (minimized: boolean) => {
    battlemapStore.controls.isMusicPlayerMinimized = minimized;
  },
  
  // Tile editor actions
  setTileEditing: (editing: boolean) => {
    battlemapStore.controls.isEditing = editing;
    // When disabling editing, also hide the editor panel
    if (!editing) {
      battlemapStore.controls.isEditorVisible = false;
    }
  },
  
  setTileEditorVisible: (visible: boolean) => {
    battlemapStore.controls.isEditorVisible = visible;
  },
  
  setSelectedTileType: (tileType: TileType) => {
    battlemapStore.controls.selectedTileType = tileType;
  },
  
  // Entity actions
  setEntitySummaries: (summaries: Record<string, EntitySummary>) => {
    battlemapStore.entities.summaries = summaries;
  },
  
  setSelectedEntity: (entityId: string | undefined) => {
    // If selecting the currently selected entity, clear the selection
    if (battlemapStore.entities.selectedEntityId === entityId) {
      battlemapStore.entities.selectedEntityId = undefined;
    } else {
      battlemapStore.entities.selectedEntityId = entityId;
    }
  },
  
  setDisplayedEntity: (entityId: string | undefined) => {
    battlemapStore.entities.displayedEntityId = entityId;
  },
  
  setEntityDirection: (entityId: string, direction: Direction) => {
    battlemapStore.entities.directions[entityId] = direction;
  },
  
  // Get the currently selected entity
  getSelectedEntity: (): EntitySummary | undefined => {
    return battlemapStore.entities.selectedEntityId 
      ? battlemapStore.entities.summaries[battlemapStore.entities.selectedEntityId] 
      : undefined;
  },
  
  // Loading/error status
  setLoading: (loading: boolean) => {
    battlemapStore.loading = loading;
  },
  
  setError: (error: string | null) => {
    battlemapStore.error = error;
  },
  
  // Fetch grid data
  fetchGridSnapshot: async () => {
    try {
      const gridData = await fetchGridSnapshot();
      battlemapStore.grid.width = gridData.width;
      battlemapStore.grid.height = gridData.height;
      battlemapStore.grid.tiles = gridData.tiles;
      return gridData;
    } catch (err) {
      console.error('Error fetching grid data:', err);
      battlemapActions.setError(err instanceof Error ? err.message : 'Failed to fetch grid data');
      return null;
    }
  },
  
  // Fetch entity summaries
  fetchEntitySummaries: async () => {
    try {
      const summariesData = await fetchEntitySummaries();
      
      // Convert array to record while preserving existing data
      const summariesRecord = summariesData.reduce((acc: Record<string, EntitySummary>, summary: EntitySummary) => {
        // Preserve existing data for smooth transitions
        const existingSummary = battlemapStore.entities.summaries[summary.uuid];
        if (existingSummary) {
          // Only update if data has changed
          if (JSON.stringify(existingSummary) !== JSON.stringify(summary)) {
            acc[summary.uuid] = summary;
          } else {
            acc[summary.uuid] = existingSummary;
          }
        } else {
          acc[summary.uuid] = summary;
        }
        return acc;
      }, {});

      battlemapStore.entities.summaries = summariesRecord;
      return summariesRecord;
    } catch (err) {
      console.error('Error fetching entity summaries:', err);
      return {};
    }
  },
  
  // Start polling for data
  startPolling: () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }

    // Immediately fetch data
    Promise.all([
      battlemapActions.fetchGridSnapshot(),
      battlemapActions.fetchEntitySummaries()
    ]).then(() => {
      // Select the first entity by default if none is selected
      if (!battlemapStore.entities.selectedEntityId) {
        const entityIds = Object.keys(battlemapStore.entities.summaries);
        if (entityIds.length > 0) {
          const firstEntityId = entityIds[0];
          battlemapStore.entities.selectedEntityId = firstEntityId;
          battlemapStore.entities.displayedEntityId = firstEntityId;
        }
      }
    });

    // Set up polling interval
    pollingInterval = setInterval(async () => {
      await Promise.all([
        battlemapActions.fetchEntitySummaries(),
        battlemapActions.fetchGridSnapshot()
      ]);
    }, POLLING_INTERVAL);
  },

  // Stop polling
  stopPolling: () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  },

  // Compute direction between two positions
  computeDirection: (fromPos: [number, number], toPos: [number, number]): Direction => {
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
  },
};

// Export both store and actions
export { battlemapStore, battlemapActions }; 