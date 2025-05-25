import React, { useCallback, useEffect } from 'react';
import { Box, Paper, IconButton, Tooltip, Divider, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import GridOnIcon from '@mui/icons-material/GridOn';
import GridOffIcon from '@mui/icons-material/GridOff';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import EditIcon from '@mui/icons-material/Edit';
import EditOffIcon from '@mui/icons-material/EditOff';
import ImageIcon from '@mui/icons-material/Image';
import HideImageIcon from '@mui/icons-material/HideImage';
import PersonIcon from '@mui/icons-material/Person';
import { useMapControls, useVisibility, useTileEditor, useSpriteEditor } from '../../../hooks/battlemap';
import TileEditorPanel from './TileEditorPanel';
import SpriteEditorPanel from './SpriteEditorPanel';
import { battlemapStore, battlemapActions } from '../../../store';
import { useSnapshot } from 'valtio';
import { discoverAvailableSpriteFolders } from '../../../api/battlemap/battlemapApi';

/**
 * Component that renders the battlemap control panel
 */
export const CanvasControls: React.FC = () => {
  // Use the hooks to get the state and actions
  const { 
    isLocked, 
    isGridVisible, 
    isTilesVisible,
    isMovementHighlightEnabled,
    toggleLock,
    toggleGridVisibility,
    toggleTilesVisibility,
    toggleMovementHighlight,
    resetView,
    zoomIn,
    zoomOut
  } = useMapControls();
  
  const { toggleVisibility, isVisibilityEnabled } = useVisibility();
  const { 
    isEditing, 
    toggleEditing, 
    toggleEditorVisibility 
  } = useTileEditor();
  
  const {
    selectedEntity,
    hasAssignedSprite,
    availableSpriteFolders
  } = useSpriteEditor();
  
  // Get the current hovered cell position directly from the store
  const snap = useSnapshot(battlemapStore);
  const hoveredCell = snap.view.hoveredCell;
  
  // Initialize sprite folders on mount
  useEffect(() => {
    const loadSpriteFolders = async () => {
      try {
        console.log('[CanvasControls] Loading available sprite folders...');
        const folders = await discoverAvailableSpriteFolders();
        battlemapActions.setAvailableSpriteFolders(folders);
        console.log(`[CanvasControls] Loaded ${folders.length} sprite folders`);
      } catch (error) {
        console.error('[CanvasControls] Error loading sprite folders:', error);
      }
    };
    
    // Only load if we don't have any folders yet
    if (availableSpriteFolders.length === 0) {
      loadSpriteFolders();
    }
  }, [availableSpriteFolders.length]);
  
  const handleEditToggle = useCallback(() => {
    console.log('[CanvasControls] Edit button clicked, current state:', { isEditing });
    
    // Toggle editing state
    toggleEditing();
    
    // If we're enabling editing, also ensure editor panel is visible
    if (!isEditing) {
      toggleEditorVisibility();
    }
    
    console.log('[CanvasControls] After toggle, new editing state will be:', { isEditing: !isEditing });
  }, [isEditing, toggleEditing, toggleEditorVisibility]);
  
  return (
    <>
      {/* Controls Panel - Positioned at top center */}
      <Paper 
        elevation={3} 
        sx={{ 
          position: 'absolute', 
          top: 8, 
          left: '50%',
          transform: 'translateX(-50%)',
          padding: 1,
          paddingX: 2,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          color: 'white',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          gap: 2,
          zIndex: 1
        }}
      >
        <Typography variant="body2">
          Position: ({hoveredCell.x >= 0 ? hoveredCell.x : '-'}, {hoveredCell.y >= 0 ? hoveredCell.y : '-'})
        </Typography>
        
        {/* Entity info if selected */}
        {selectedEntity && (
          <>
            <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <PersonIcon sx={{ fontSize: 16 }} />
              <Typography variant="body2">
                {selectedEntity.name}
              </Typography>
              {hasAssignedSprite && (
                <Box 
                  sx={{ 
                    width: 8, 
                    height: 8, 
                    borderRadius: '50%', 
                    backgroundColor: '#4caf50' 
                  }} 
                />
              )}
            </Box>
          </>
        )}
        
        <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {/* Zoom controls */}
          <IconButton 
            size="small" 
            onClick={zoomOut}
            sx={{ color: 'white' }}
          >
            <RemoveIcon />
          </IconButton>
          <IconButton 
            size="small" 
            onClick={resetView}
            sx={{ color: 'white' }}
          >
            <RestartAltIcon />
          </IconButton>
          <IconButton 
            size="small" 
            onClick={zoomIn}
            sx={{ color: 'white' }}
          >
            <AddIcon />
          </IconButton>

          <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />

          {/* Lock Button */}
          <Tooltip title={isLocked ? "Unlock Map" : "Lock Map"}>
            <IconButton
              size="small"
              onClick={toggleLock}
              sx={{ 
                color: 'white',
                backgroundColor: isLocked ? 'rgba(255, 255, 255, 0.1)' : 'transparent'
              }}
            >
              {isLocked ? <LockIcon /> : <LockOpenIcon />}
            </IconButton>
          </Tooltip>

          {/* Grid Toggle */}
          <Tooltip title={isGridVisible ? "Hide Grid" : "Show Grid"}>
            <IconButton
              size="small"
              onClick={toggleGridVisibility}
              sx={{ 
                color: 'white',
                backgroundColor: isGridVisible ? 'rgba(255, 255, 255, 0.1)' : 'transparent'
              }}
            >
              {isGridVisible ? <GridOnIcon /> : <GridOffIcon />}
            </IconButton>
          </Tooltip>

          {/* Tiles Toggle */}
          <Tooltip title={isTilesVisible ? "Hide Tiles (Debug)" : "Show Tiles"}>
            <IconButton
              size="small"
              onClick={toggleTilesVisibility}
              sx={{ 
                color: 'white',
                backgroundColor: isTilesVisible ? 'rgba(255, 255, 255, 0.1)' : 'transparent'
              }}
            >
              {isTilesVisible ? <ImageIcon /> : <HideImageIcon />}
            </IconButton>
          </Tooltip>

          {/* Visibility Toggle */}
          <Tooltip title={isVisibilityEnabled ? "Disable Visibility" : "Enable Visibility"}>
            <IconButton
              size="small"
              onClick={toggleVisibility}
              sx={{ 
                color: 'white',
                backgroundColor: isVisibilityEnabled ? 'rgba(255, 255, 255, 0.1)' : 'transparent'
              }}
            >
              {isVisibilityEnabled ? <VisibilityIcon /> : <VisibilityOffIcon />}
            </IconButton>
          </Tooltip>
          
          {/* Movement highlight toggle */}
          <Tooltip title={isMovementHighlightEnabled ? "Hide Movement Range" : "Show Movement Range"}>
            <IconButton 
              size="small" 
              onClick={toggleMovementHighlight}
              sx={{ 
                color: 'white',
                backgroundColor: isMovementHighlightEnabled ? 'rgba(255, 255, 255, 0.1)' : 'transparent'
              }}
            >
              <DirectionsRunIcon />
            </IconButton>
          </Tooltip>

          {/* Tile Editor toggle */}
          <Tooltip title={isLocked ? "Unlock map to edit tiles" : (isEditing ? "Exit Tile Editor" : "Open Tile Editor")}>
            <IconButton 
              size="small" 
              onClick={isLocked ? undefined : handleEditToggle}
              sx={{ 
                color: 'white',
                backgroundColor: isEditing && !isLocked ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                opacity: isLocked ? 0.5 : 1
              }}
            >
              {isEditing && !isLocked ? <EditOffIcon /> : <EditIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>
      
      {/* Tile Editor Panel */}
      <TileEditorPanel isLocked={isLocked} />
      
      {/* Sprite Editor Panel */}
      <SpriteEditorPanel isLocked={isLocked} />
    </>
  );
}; 