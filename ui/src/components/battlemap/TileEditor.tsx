import React, { useState, useEffect } from 'react';
import { Paper, ToggleButton, ToggleButtonGroup, Box, IconButton, Collapse } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import EditIcon from '@mui/icons-material/Edit';
import EditOffIcon from '@mui/icons-material/EditOff';
import { createTile, TileSummary } from '../../api/tileApi';
import { v4 as uuidv4 } from 'uuid';
import { Assets, Texture } from 'pixi.js';

export type TileType = 'floor' | 'wall' | 'water';

interface TilePreviewProps {
  type: TileType;
  isSelected: boolean;
}

const TilePreview: React.FC<TilePreviewProps> = ({ type, isSelected }) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const spritePath = `/tiles/${type}.png`;

  // Fallback styles in case image fails to load
  const getFallbackStyle = (tileType: TileType) => {
    switch (tileType) {
      case 'floor':
        return { backgroundColor: '#8B7355' };
      case 'wall':
        return { backgroundColor: '#696969' };
      case 'water':
        return { backgroundColor: '#4682B4' };
    }
  };

  return (
    <Box
      sx={{
        width: 24,
        height: 24,
        borderRadius: 1,
        mr: 1.5,
        transition: 'all 0.2s ease',
        opacity: isSelected ? 1 : 0.7,
        overflow: 'hidden',
        position: 'relative',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        ...(!imageLoaded && getFallbackStyle(type)),
        '&:hover': {
          opacity: 1
        },
      }}
    >
      <img
        src={spritePath}
        alt={`${type} tile`}
        onLoad={() => setImageLoaded(true)}
        onError={() => setImageLoaded(false)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: imageLoaded ? 'block' : 'none'
        }}
      />
    </Box>
  );
};

interface TileEditorProps {
  onTileCreated?: () => void;
  selectedTile: TileType;
  onTileSelected: (tile: TileType) => void;
  isEditing: boolean;
  onToggleEditing: () => void;
  isLocked: boolean;
}

const TileEditor: React.FC<TileEditorProps> = ({ 
  onTileCreated, 
  selectedTile, 
  onTileSelected,
  isEditing,
  onToggleEditing,
  isLocked
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const handleTileChange = (
    event: React.MouseEvent<HTMLElement>,
    newTile: TileType | null,
  ) => {
    if (newTile !== null) {
      onTileSelected(newTile);
    }
  };

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: 8,
        left: '50%',
        marginLeft: '180px',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        color: 'white',
        zIndex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: '120px',
      }}
    >
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        p: 1,
        justifyContent: 'space-between'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <IconButton
            size="small"
            onClick={() => setIsExpanded(!isExpanded)}
            sx={{ 
              color: 'white', 
              mr: 1,
              visibility: isEditing && !isLocked ? 'visible' : 'hidden'
            }}
          >
            {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
          Tile Editor
        </Box>
        <IconButton
          size="small"
          onClick={onToggleEditing}
          disabled={isLocked}
          sx={{ 
            color: 'white',
            opacity: isLocked ? 0.5 : 1
          }}
        >
          {isEditing ? <EditOffIcon /> : <EditIcon />}
        </IconButton>
      </Box>

      <Collapse in={isExpanded && isEditing && !isLocked}>
        <Box sx={{ p: 1 }}>
          <ToggleButtonGroup
            value={selectedTile}
            exclusive
            onChange={handleTileChange}
            aria-label="tile type"
            size="small"
            orientation="vertical"
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 0.5,
              '& .MuiToggleButton-root': {
                color: 'white',
                borderColor: 'rgba(255, 255, 255, 0.3)',
                justifyContent: 'flex-start',
                px: 2,
                py: 1,
                display: 'flex',
                alignItems: 'center',
                '&.Mui-selected': {
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.3)',
                  },
                },
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                },
                '&.Mui-disabled': {
                  color: 'rgba(255, 255, 255, 0.3)',
                },
              },
            }}
          >
            <ToggleButton value="floor" aria-label="floor">
              <TilePreview type="floor" isSelected={selectedTile === 'floor'} />
              Floor
            </ToggleButton>
            <ToggleButton value="wall" aria-label="wall">
              <TilePreview type="wall" isSelected={selectedTile === 'wall'} />
              Wall
            </ToggleButton>
            <ToggleButton value="water" aria-label="water">
              <TilePreview type="water" isSelected={selectedTile === 'water'} />
              Water
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Collapse>
    </Paper>
  );
};

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

  const handleCellClick = async (
    x: number, 
    y: number, 
    onOptimisticUpdate: (tile: TileSummary) => void,
    isLocked: boolean
  ) => {
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
    } catch (error) {
      console.error('Error creating tile:', error);
      // Could add error handling/rollback here if needed
    }
  };

  const TileEditorComponent = ({ isLocked }: { isLocked: boolean }) => (
    <TileEditor
      selectedTile={selectedTile}
      onTileSelected={setSelectedTile}
      isEditing={isEditing}
      onToggleEditing={() => setIsEditing(!isEditing)}
      isLocked={isLocked}
    />
  );

  return {
    selectedTile,
    isEditing,
    handleCellClick,
    TileEditor: TileEditorComponent,
  };
};

export default TileEditor; 