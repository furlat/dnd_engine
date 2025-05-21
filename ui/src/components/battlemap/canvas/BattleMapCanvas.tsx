import React, { useCallback, useEffect, useRef } from 'react';
import { Application, extend } from '@pixi/react';
import { Graphics as PixiGraphics, Container, Sprite, FederatedPointerEvent } from 'pixi.js';
import { Box } from '@mui/material';
import { useGrid, useEntitySelection, useVisibility, useMapControls, useTileEditor } from '../../../hooks/battlemap';
import { battlemapStore, battlemapActions } from '../../../store';
import { useSnapshot } from 'valtio';
import { CanvasGrid } from './CanvasGrid';
import { CanvasControls } from './CanvasControls';
// import { CanvasEntities } from './CanvasEntities';  // Will re-enable later

// Extend must be called at the module level
extend({ Container, Graphics: PixiGraphics, Sprite });

/**
 * Main component that renders the PixiJS application for the battlemap
 */
const BattleMapCanvas: React.FC = () => {
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

  // Update container size when the box ref is available
  useEffect(() => {
    const updateSize = () => {
      if (boxRef.current) {
        const width = boxRef.current.clientWidth;
        const height = boxRef.current.clientHeight;
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

  // Event handlers for PixiJS pointer events
  const handlePointerMove = useCallback((event: FederatedPointerEvent) => {
    // Skip handling during WASD movement or when locked
    if (isLocked || isWasdMoving) return;
    
    // Convert pointer coordinates to grid coordinates
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY } = pixelToGrid(mouseX, mouseY, containerSize.width, containerSize.height);
    updateHoveredCell(gridX, gridY);
  }, [isLocked, isWasdMoving, pixelToGrid, containerSize, updateHoveredCell]);
   
  const handlePointerDown = useCallback((event: FederatedPointerEvent) => {
    // Skip handling during WASD movement or when locked
    if (isLocked || isWasdMoving) return;
    
    // Convert pointer coordinates to grid coordinates
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY } = pixelToGrid(mouseX, mouseY, containerSize.width, containerSize.height);

    // If in tile editing mode, handle cell click for tile placement
    if (isEditing) {
      handleCellClick(gridX, gridY, (tile) => {
        // Optimistic update will be handled by the store
        battlemapActions.fetchGridSnapshot();
      }, isLocked);
    }
    
  }, [isLocked, isWasdMoving, pixelToGrid, containerSize, isEditing, handleCellClick]);

  // PIXI.js background draw callback
  const drawBackground = useCallback((g: PixiGraphics) => {
    g.clear();
    g.beginFill(0x111111);
    g.drawRect(0, 0, containerSize.width, containerSize.height);
    g.endFill();
  }, [containerSize.width, containerSize.height]);

  return (
    <Box 
      ref={boxRef}
      sx={{ 
        width: '100%', 
        height: '100%', 
        position: 'relative', 
        overflow: 'hidden',
        bgcolor: '#111'
      }}
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
          <pixiGraphics
            eventMode="static"
            interactive={true}
            onPointerMove={handlePointerMove}
            onPointerDown={handlePointerDown}
            onPointerLeave={() => updateHoveredCell(-1, -1)}
            draw={drawBackground}
          />
          
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