import React, { useCallback } from 'react';
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
import { useMapControls, useVisibility, useTileEditor } from '../../../hooks/battlemap';
import TileEditorPanel from './TileEditorPanel';
import { battlemapStore } from '../../../store';
import { useSnapshot } from 'valtio';

/**
 * Component that renders the battlemap control panel
 */
export const CanvasControls: React.FC = () => {
  // Use the hooks to get the state and actions
  const { 
    isLocked, 
    isGridVisible, 
    isMovementHighlightEnabled,
    toggleLock,
    toggleGridVisibility,
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
  
  // Get the current hovered cell position directly from the store
  const snap = useSnapshot(battlemapStore);
  const hoveredCell = snap.view.hoveredCell;
  
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
          <Tooltip title={isEditing ? "Exit Tile Editor" : "Open Tile Editor"}>
            <IconButton 
              size="small" 
              onClick={handleEditToggle}
              sx={{ 
                color: 'white',
                backgroundColor: isEditing ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                opacity: isLocked ? 0.5 : 1
              }}
              disabled={isLocked}
            >
              {isEditing ? <EditOffIcon /> : <EditIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>
      
      {/* Tile Editor Panel */}
      <TileEditorPanel isLocked={isLocked} />
    </>
  );
}; 