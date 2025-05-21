import { useState, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { createTile } from '../../api/battlemap/battlemapApi';
import { TileSummary } from '../../types/battlemap_types';

export type TileType = 'floor' | 'wall' | 'water';

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
  }
};

export const useTileEditor = () => {
  const [selectedTile, setSelectedTile] = useState<TileType>('floor');
  const [isEditing, setIsEditing] = useState(false);
  const [isEditorVisible, setIsEditorVisible] = useState(false);

  const toggleEditing = useCallback(() => {
    setIsEditing(prev => !prev);
    // When enabling editing, show the editor panel
    if (!isEditing) {
      setIsEditorVisible(true);
    }
  }, [isEditing]);

  const toggleEditorVisibility = useCallback(() => {
    setIsEditorVisible(prev => !prev);
  }, []);

  const selectTile = useCallback((tileType: TileType) => {
    console.log('Selecting tile type:', tileType);
    setSelectedTile(tileType);
  }, []);

  const handleCellClick = useCallback(async (
    x: number, 
    y: number, 
    onOptimisticUpdate: (tile: TileSummary) => void,
    isLocked: boolean
  ) => {
    console.log('Cell clicked for tile placement:', { x, y, selectedTile, isEditing, isLocked });
    if (!isEditing || isLocked) return;

    // Create optimistic tile
    const optimisticTile: TileSummary = {
      uuid: uuidv4(),
      position: [x, y],
      ...getDefaultTileProperties(selectedTile)
    } as TileSummary;

    // Update UI immediately
    onOptimisticUpdate(optimisticTile);

    try {
      // Make API call in background
      await createTile([x, y], selectedTile);
      console.log('Tile created successfully:', optimisticTile);
    } catch (error) {
      console.error('Error creating tile:', error);
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