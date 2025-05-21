import React, { useState, useEffect, useCallback } from 'react';
import { Paper, ToggleButton, ToggleButtonGroup, Box, Typography, Divider, Tabs, Tab } from '@mui/material';
import { Assets, Texture } from 'pixi.js';
import { useTileEditor, TileType } from '../../../hooks/battlemap';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../../store';

// Initialize PixiJS Assets
Assets.init({
  basePath: '/',
});

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
    >
      {value === index && (
        <Box sx={{ p: 1 }}>
          {children}
        </Box>
      )}
    </div>
  );
};

const TilePreview: React.FC<{ type: TileType; isSelected: boolean }> = ({ type, isSelected }) => {
  const [texture, setTexture] = useState<Texture | null>(null);
  const spritePath = `/tiles/${type}.png`;

  // Fallback styles based on tile type
  const getFallbackStyle = (tileType: TileType) => {
    switch (tileType) {
      case 'floor':
        return { backgroundColor: '#8B7355' };
      case 'wall':
        return { backgroundColor: '#696969' };
      case 'water':
        return { backgroundColor: '#4682B4' };
      case 'lava':
        return { backgroundColor: '#FF4500' };
      case 'grass':
        return { backgroundColor: '#228B22' };
      case 'erase':
        return { backgroundColor: '#303030' };
    }
  };

  // Load the texture
  useEffect(() => {
    const loadTexture = async () => {
      try {
        let loadedTexture = Assets.get(spritePath);
        
        if (!loadedTexture) {
          loadedTexture = await Assets.load(spritePath);
        }
        
        setTexture(loadedTexture);
      } catch (error) {
        console.error(`Error loading tile sprite:`, error);
        setTexture(null);
      }
    };
    
    loadTexture();
  }, [spritePath]);

  return (
    <Box
      sx={{
        width: 32,
        height: 32,
        borderRadius: 1,
        mr: 1.5,
        transition: 'all 0.2s ease',
        opacity: isSelected ? 1 : 0.7,
        overflow: 'hidden',
        position: 'relative',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        ...(!texture && getFallbackStyle(type)),
        '&:hover': {
          opacity: 1,
          transform: 'scale(1.05)'
        },
      }}
    >
      {texture ? (
        <img
          src={spritePath}
          alt={`${type} tile`}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover'
          }}
        />
      ) : (
        <Box 
          sx={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            ...getFallbackStyle(type)
          }}
        >
          {type === 'erase' && (
            <Typography variant="caption" sx={{ color: 'white' }}>X</Typography>
          )}
        </Box>
      )}
    </Box>
  );
};

interface TileEditorPanelProps {
  isLocked: boolean;
}

const TileEditorPanel: React.FC<TileEditorPanelProps> = ({ isLocked }) => {
  const snap = useSnapshot(battlemapStore);
  const { 
    selectedTile, 
    selectTile
  } = useTileEditor();
  
  // Get editor state directly from store
  const isEditing = snap.controls.isEditing;
  const isEditorVisible = snap.controls.isEditorVisible;
  
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = useCallback((event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  }, []);

  const handleTileChange = useCallback((
    event: React.MouseEvent<HTMLElement>,
    newTile: TileType | null,
  ) => {
    if (newTile !== null) {
      console.log('[TileEditorPanel] Tile selected:', newTile);
      selectTile(newTile);
    }
  }, [selectTile]);

  // Early return if editor is not visible or editing is not active
  if (!isEditorVisible || !isEditing) {
    console.log('[TileEditorPanel] Not rendering panel, conditions not met:', { isEditorVisible, isEditing });
    return null;
  }

  console.log('[TileEditorPanel] Rendering panel with selected tile:', selectedTile);

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        color: 'white',
        zIndex: 1,
        borderRadius: 2,
        width: 'auto',
        minWidth: '400px',
        maxWidth: '80%'
      }}
    >
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs 
          value={tabValue} 
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{
            '& .MuiTab-root': {
              color: 'rgba(255, 255, 255, 0.7)',
              '&.Mui-selected': {
                color: 'white'
              }
            }
          }}
        >
          <Tab label="Basic Tiles" />
          <Tab label="Special Tiles" />
        </Tabs>
      </Box>

      <TabPanel value={tabValue} index={0}>
        <ToggleButtonGroup
          value={selectedTile}
          exclusive
          onChange={handleTileChange}
          aria-label="basic tile types"
          size="small"
          sx={{
            display: 'flex',
            flexDirection: 'row',
            flexWrap: 'wrap',
            gap: 1,
            '& .MuiToggleButton-root': {
              color: 'white',
              borderColor: 'rgba(255, 255, 255, 0.3)',
              justifyContent: 'flex-start',
              px: 2,
              py: 1,
              minWidth: '90px',
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
          <ToggleButton value="erase" aria-label="erase">
            <TilePreview type="erase" isSelected={selectedTile === 'erase'} />
            Erase
          </ToggleButton>
        </ToggleButtonGroup>
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <ToggleButtonGroup
          value={selectedTile}
          exclusive
          onChange={handleTileChange}
          aria-label="special tile types"
          size="small"
          sx={{
            display: 'flex',
            flexDirection: 'row',
            flexWrap: 'wrap',
            gap: 1,
            '& .MuiToggleButton-root': {
              color: 'white',
              borderColor: 'rgba(255, 255, 255, 0.3)',
              justifyContent: 'flex-start',
              px: 2,
              py: 1,
              minWidth: '90px',
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
            },
          }}
        >
          <ToggleButton value="lava" aria-label="lava">
            <TilePreview type="lava" isSelected={selectedTile === 'lava'} />
            Lava
          </ToggleButton>
          <ToggleButton value="grass" aria-label="grass">
            <TilePreview type="grass" isSelected={selectedTile === 'grass'} />
            Grass
          </ToggleButton>
        </ToggleButtonGroup>
      </TabPanel>
    </Paper>
  );
};

export default TileEditorPanel; 