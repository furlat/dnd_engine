import React, { useCallback, useEffect, useRef } from 'react';
import { Application, extend } from '@pixi/react';
import { Graphics as PixiGraphics, Container, Sprite } from 'pixi.js';
import { Box } from '@mui/material';
import { useGrid, useEntitySelection, useVisibility, useMapControls, useTileEditor } from '../../../hooks/battlemap';
import { battlemapStore, battlemapActions } from '../../../store';
import { useSnapshot } from 'valtio';
import { CanvasGrid } from './CanvasGrid';
import { CanvasControls } from './CanvasControls';
// import { CanvasEntities } from './CanvasEntities';  // Will re-enable later

// Extend must be called at the module level
console.log('Extending PixiJS components for JSX...');
extend({ Container, Graphics: PixiGraphics, Sprite });

/**
 * Main component that renders the PixiJS application for the battlemap
 */
const BattleMapCanvas: React.FC = () => {
  console.log('BattleMapCanvas rendering...');
  const appRef = useRef(null);
  const boxRef = useRef<HTMLDivElement>(null);
  
  const { 
    gridWidth, 
    gridHeight, 
    tileSize, 
    containerSize, 
    setContainerSize,
    calculateGridOffset, 
    pixelToGrid,
    updateHoveredCell 
  } = useGrid();

  const { 
    isGridVisible, 
    isLocked,
    isWasdMoving
  } = useMapControls();
  
  const { selectEntity } = useEntitySelection();
  const snap = useSnapshot(battlemapStore);
  const { isVisibilityEnabled } = useVisibility();
  const { isEditing, handleCellClick } = useTileEditor();

  // Log component mounting
  useEffect(() => {
    console.log('BattleMapCanvas mounted');
    return () => console.log('BattleMapCanvas unmounted');
  }, []);

  // Update container size when the box ref is available
  useEffect(() => {
    const updateSize = () => {
      if (boxRef.current) {
        const width = boxRef.current.clientWidth;
        const height = boxRef.current.clientHeight;
        console.log('Setting container size from direct measurement:', { width, height });
        setContainerSize({ width, height });
      }
    };

    // Initial size calculation
    updateSize();
    
    // Also update after a small delay to ensure all components are rendered
    const timeoutId = setTimeout(updateSize, 100);

    // Add resize listener
    window.addEventListener('resize', updateSize);
    return () => {
      window.removeEventListener('resize', updateSize);
      clearTimeout(timeoutId);
    };
  }, [setContainerSize]);

  // Add debugging for container size changes
  useEffect(() => {
    console.log('Container size updated:', containerSize);
  }, [containerSize]);

  // Event handlers for mouse interaction
  const handleMouseMove = useCallback((event: React.MouseEvent) => {
    // Skip mouse handling during WASD movement or when locked
    if (isLocked || isWasdMoving) return;
    
    // Convert mouse coordinates to grid coordinates
    const rect = event.currentTarget.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    
    const { gridX, gridY } = pixelToGrid(mouseX, mouseY, containerSize.width, containerSize.height);
    updateHoveredCell(gridX, gridY);
  }, [isLocked, isWasdMoving, pixelToGrid, containerSize, updateHoveredCell]);
   
  const handleClick = useCallback((event: React.MouseEvent) => {
    // Skip click handling during WASD movement or when locked
    if (isLocked || isWasdMoving) return;
    
    // Convert mouse coordinates to grid coordinates
    const rect = event.currentTarget.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    
    const { gridX, gridY } = pixelToGrid(mouseX, mouseY, containerSize.width, containerSize.height);
    
    console.log(`Grid clicked at: (${gridX}, ${gridY})`);

    // If in tile editing mode, handle cell click for tile placement
    if (isEditing) {
      handleCellClick(gridX, gridY, (tile) => {
        // Optimistic update will be handled by the store
        battlemapActions.fetchGridData();
      }, isLocked);
    }
    
  }, [isLocked, isWasdMoving, pixelToGrid, containerSize, isEditing, handleCellClick]);

  // Calculate cursor style based on state
  const getCursorStyle = () => {
    if (isLocked) return 'default';
    if (isWasdMoving) return 'grabbing';
    if (isEditing) return 'crosshair';
    return 'pointer';
  };

  return (
    <Box 
      ref={boxRef}
      sx={{ 
        width: '100%', 
        height: '100%', 
        position: 'relative', 
        overflow: 'hidden',
        bgcolor: '#111',
        cursor: getCursorStyle()
      }}
      onMouseMove={handleMouseMove}
      onClick={handleClick}
    >
      {containerSize.width > 0 && containerSize.height > 0 && (
        <Application
          ref={appRef}
          width={containerSize.width}
          height={containerSize.height}
          backgroundColor={0x111111}
          antialias
          autoDensity
          resolution={window.devicePixelRatio || 1}
        >
          <CanvasGrid 
            gridWidth={gridWidth}
            gridHeight={gridHeight}
            tileSize={tileSize}
            containerSize={containerSize}
            isGridVisible={isGridVisible}
          />
          
          {/* Will re-enable entity rendering later
          <CanvasEntities 
            containerSize={containerSize}
            tileSize={tileSize}
            isVisibilityEnabled={isVisibilityEnabled}
            onEntityClick={selectEntity}
          />
          */}
        </Application>
      )}
      
      {/* Canvas Controls */}
      <CanvasControls />
    </Box>
  );
};

export default BattleMapCanvas; 