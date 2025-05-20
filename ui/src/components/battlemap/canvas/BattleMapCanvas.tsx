import React from 'react';
import { Application } from '@pixi/react';
import { Box } from '@mui/material';
import { useGrid, useEntitySelection, useVisibility, useMapControls } from '../../../hooks/battlemap';
import { battlemapStore } from '../../../store';
import { useSnapshot } from 'valtio';
import { CanvasGrid } from './CanvasGrid';
import { CanvasEntities } from './CanvasEntities';
import { CanvasControls } from './CanvasControls';

/**
 * Main component that renders the PixiJS application for the battlemap
 * Uses the various hooks for accessing store data and functionality
 */
const BattleMapCanvas: React.FC = () => {
  const { 
    gridWidth, 
    gridHeight, 
    tileSize, 
    containerSize, 
    calculateGridOffset, 
    pixelToGrid,
    updateHoveredCell 
  } = useGrid();
  
  const { isGridVisible, isLocked } = useMapControls();
  const { selectEntity } = useEntitySelection();
  const snap = useSnapshot(battlemapStore);
  const { isVisibilityEnabled } = useVisibility();

  // Event handlers
  const handleMouseMove = React.useCallback((event: React.MouseEvent) => {
    if (isLocked) return;
    
    // Convert mouse coordinates to grid coordinates
    const rect = event.currentTarget.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    
    const { gridX, gridY } = pixelToGrid(mouseX, mouseY, containerSize.width, containerSize.height);
    updateHoveredCell(gridX, gridY);
  }, [isLocked, pixelToGrid, containerSize, updateHoveredCell]);
  
  // Only render if we have valid container dimensions
  if (containerSize.width <= 0 || containerSize.height <= 0) {
    return null;
  }

  return (
    <Box 
      sx={{ 
        width: '100%', 
        height: '100%', 
        position: 'relative', 
        overflow: 'hidden',
        bgcolor: '#111',
        cursor: isLocked ? 'default' : 'pointer'
      }}
      onMouseMove={handleMouseMove}
    >
      <Application
        width={containerSize.width}
        height={containerSize.height}
        backgroundColor={0x111111}
        antialias
      >
        {/* Grid layer with tiles */}
        <CanvasGrid 
          gridWidth={gridWidth}
          gridHeight={gridHeight}
          tileSize={tileSize}
          containerSize={containerSize}
          isGridVisible={isGridVisible}
        />
        
        {/* Entities layer */}
        <CanvasEntities 
          containerSize={containerSize}
          tileSize={tileSize}
          isVisibilityEnabled={isVisibilityEnabled}
          onEntityClick={selectEntity}
        />
      </Application>
      
      {/* Controls overlay */}
      <CanvasControls />
    </Box>
  );
};

export default BattleMapCanvas; 