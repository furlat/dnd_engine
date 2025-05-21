import { useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { createTile, deleteTile } from '../../api/battlemap/battlemapApi';
import { TileSummary } from '../../types/battlemap_types';
import { battlemapActions, battlemapStore } from '../../store/battlemapStore';
import { useSnapshot } from 'valtio';

export type TileType = 'floor' | 'wall' | 'water' | 'lava' | 'grass' | 'erase';

const getDefaultTileProperties = (tileType: TileType): Partial<TileSummary> => {
  switch (tileType) {
    case 'floor':
      return {
        walkable: true,
        visible: true,
        sprite_name: 'floor.png',
        name: 'Floor'
      };
    case 'wall':
      return {
        walkable: false,
        visible: false,
        sprite_name: 'wall.png',
        name: 'Wall'
      };
    case 'water':
      return {
        walkable: false,
        visible: true,
        sprite_name: 'water.png',
        name: 'Water'
      };
    case 'lava':
      return {
        walkable: false,
        visible: true,
        sprite_name: 'lava.png',
        name: 'Lava'
      };
    case 'grass':
      return {
        walkable: true,
        visible: true,
        sprite_name: 'grass.png',
        name: 'Grass'
      };
    case 'erase':
      return {
        walkable: true,
        visible: true,
        name: 'Eraser'
      };
  }
};

export const useTileEditor = () => {
  // Use the store instead of local state
  const snap = useSnapshot(battlemapStore);
  
  // Extract tile editor state from the store
  const selectedTile = snap.controls.selectedTileType as TileType;
  const isEditing = snap.controls.isEditing;
  const isEditorVisible = snap.controls.isEditorVisible;

  const toggleEditing = useCallback(() => {
    const newEditingState = !isEditing;
    console.log('[TileEditor] Toggling editing mode:', { current: isEditing, new: newEditingState });
    
    battlemapActions.setTileEditing(newEditingState);
    
    // When enabling editing, always show the editor panel
    if (newEditingState) {
      console.log('[TileEditor] Editing enabled, showing editor panel');
      battlemapActions.setTileEditorVisible(true);
    }
  }, [isEditing]);

  const toggleEditorVisibility = useCallback(() => {
    const newVisibility = !isEditorVisible;
    console.log('[TileEditor] Toggling editor visibility:', { current: isEditorVisible, new: newVisibility });
    
    battlemapActions.setTileEditorVisible(newVisibility);
  }, [isEditorVisible]);

  const selectTile = useCallback((tileType: TileType) => {
    console.log('[TileEditor] Selecting tile type:', { previous: selectedTile, new: tileType });
    
    battlemapActions.setSelectedTileType(tileType);
  }, [selectedTile]);

  const handleCellClick = useCallback(async (
    x: number, 
    y: number, 
    onOptimisticUpdate: (tile: TileSummary) => void,
    isLocked: boolean
  ) => {
    console.log('[TileEditor] Cell clicked for tile placement:', { 
      position: [x, y], 
      selectedTile, 
      isEditing, 
      isLocked 
    });
    
    if (!isEditing || isLocked) {
      console.log('[TileEditor] Skipping cell click - editor not active or map is locked');
      return;
    }

    // Special case for eraser - call the delete API
    if (selectedTile === 'erase') {
      console.log('[TileEditor] Erasing tile at position:', [x, y]);
      try {
        await deleteTile(x, y);
        console.log('[TileEditor] Tile deleted successfully at position:', [x, y]);
        // Refresh the grid after deletion
        battlemapActions.fetchGridSnapshot();
      } catch (error) {
        console.error('[TileEditor] Error deleting tile:', error);
      }
      return;
    }

    // Create optimistic tile
    const optimisticTile: TileSummary = {
      uuid: uuidv4(),
      position: [x, y],
      ...getDefaultTileProperties(selectedTile)
    } as TileSummary;

    // Update UI immediately
    console.log('[TileEditor] Applying optimistic UI update with tile:', optimisticTile);
    onOptimisticUpdate(optimisticTile);

    try {
      // Make API call in background
      console.log('[TileEditor] Creating tile on server:', { position: [x, y], type: selectedTile });
      await createTile([x, y], selectedTile);
      console.log('[TileEditor] Tile created successfully');
      // Refresh the grid to ensure server state is reflected
      battlemapActions.fetchGridSnapshot();
    } catch (error) {
      console.error('[TileEditor] Error creating tile:', error);
      // Could add error handling/rollback here if needed
    }
  }, [selectedTile, isEditing]);

  return {
    selectedTile,
    isEditing,
    isEditorVisible,
    toggleEditing,
    toggleEditorVisibility,
    selectTile,
    handleCellClick,
  };
};

export default useTileEditor; 