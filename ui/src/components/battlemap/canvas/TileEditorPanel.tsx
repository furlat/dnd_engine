import React, { useState } from 'react';
import { Paper, ToggleButton, ToggleButtonGroup, Box, IconButton, Collapse } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useTileEditor, TileType } from '../../../hooks/battlemap';

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

interface TileEditorPanelProps {
  isLocked: boolean;
}

const TileEditorPanel: React.FC<TileEditorPanelProps> = ({ isLocked }) => {
  const { 
    selectedTile, 
    isEditing,
    isEditorVisible,
    toggleEditorVisibility,
    selectTile
  } = useTileEditor();
  
  const [isExpanded, setIsExpanded] = useState(true);

  const handleTileChange = (
    event: React.MouseEvent<HTMLElement>,
    newTile: TileType | null,
  ) => {
    if (newTile !== null) {
      selectTile(newTile);
    }
  };

  if (!isEditorVisible) return null;

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: 160,
        right: 16,
        backgroundColor: 'rgba(33, 33, 33, 0.9)',
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
            sx={{ color: 'white', mr: 1 }}
          >
            {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
          Tile Types
        </Box>
      </Box>

      <Collapse in={isExpanded && isEditing}>
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

export default TileEditorPanel; 