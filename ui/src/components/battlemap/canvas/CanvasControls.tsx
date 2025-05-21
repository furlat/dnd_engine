import React from 'react';
import { Box, Paper, IconButton, Tooltip, Divider } from '@mui/material';
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
import { useMapControls, useGrid, useVisibility, useTileEditor } from '../../../hooks/battlemap';
import TileEditorPanel from './TileEditorPanel';

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
  
  const { toggleVisibility } = useVisibility();
  const { isVisibilityEnabled } = useVisibility();
  const { 
    isEditing, 
    toggleEditing, 
    toggleEditorVisibility 
  } = useTileEditor();
  
  const handleEditToggle = () => {
    toggleEditing();
    toggleEditorVisibility();
  };
  
  return (
    <>
      <Box sx={{ position: 'absolute', top: 16, right: 16 }}>
        <Paper 
          elevation={3}
          sx={{ 
            display: 'flex', 
            flexDirection: 'column', 
            p: 0.5,
            backgroundColor: 'rgba(33, 33, 33, 0.9)',
          }}
        >
          {/* Zoom controls */}
          <Tooltip title="Zoom In" placement="left">
            <IconButton onClick={zoomIn} size="small" color="primary">
              <AddIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Zoom Out" placement="left">
            <IconButton onClick={zoomOut} size="small" color="primary">
              <RemoveIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Reset View" placement="left">
            <IconButton onClick={resetView} size="small" color="primary">
              <RestartAltIcon />
            </IconButton>
          </Tooltip>
          
          <Divider sx={{ my: 0.5 }} />
          
          {/* Lock/unlock */}
          <Tooltip title={isLocked ? "Unlock Map" : "Lock Map"} placement="left">
            <IconButton 
              onClick={toggleLock} 
              size="small" 
              color={isLocked ? "success" : "primary"}
            >
              {isLocked ? <LockIcon /> : <LockOpenIcon />}
            </IconButton>
          </Tooltip>
          
          {/* Grid toggle */}
          <Tooltip title={isGridVisible ? "Hide Grid" : "Show Grid"} placement="left">
            <IconButton 
              onClick={toggleGridVisibility} 
              size="small" 
              color={isGridVisible ? "success" : "primary"}
            >
              {isGridVisible ? <GridOnIcon /> : <GridOffIcon />}
            </IconButton>
          </Tooltip>
          
          {/* Visibility toggle */}
          <Tooltip title={isVisibilityEnabled ? "Disable Visibility" : "Enable Visibility"} placement="left">
            <IconButton 
              onClick={toggleVisibility} 
              size="small" 
              color={isVisibilityEnabled ? "success" : "primary"}
            >
              {isVisibilityEnabled ? <VisibilityIcon /> : <VisibilityOffIcon />}
            </IconButton>
          </Tooltip>
          
          {/* Movement highlight toggle */}
          <Tooltip title={isMovementHighlightEnabled ? "Hide Movement Range" : "Show Movement Range"} placement="left">
            <IconButton 
              onClick={toggleMovementHighlight} 
              size="small" 
              color={isMovementHighlightEnabled ? "success" : "primary"}
            >
              <DirectionsRunIcon />
            </IconButton>
          </Tooltip>

          {/* Tile Editor toggle */}
          <Tooltip title={isEditing ? "Exit Tile Editor" : "Open Tile Editor"} placement="left">
            <IconButton 
              onClick={handleEditToggle} 
              size="small" 
              color={isEditing ? "success" : "primary"}
              disabled={isLocked}
            >
              {isEditing ? <EditOffIcon /> : <EditIcon />}
            </IconButton>
          </Tooltip>
        </Paper>
      </Box>
      
      {/* Tile Editor Panel */}
      <TileEditorPanel isLocked={isLocked} />
    </>
  );
}; 