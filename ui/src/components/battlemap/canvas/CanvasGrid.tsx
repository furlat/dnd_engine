import React, { useCallback } from 'react';
import { Container, Graphics } from 'pixi.js';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../../store';

interface CanvasGridProps {
  gridWidth: number;
  gridHeight: number;
  tileSize: number;
  containerSize: {
    width: number;
    height: number;
  };
  isGridVisible: boolean;
}

export const CanvasGrid: React.FC<CanvasGridProps> = ({
  gridWidth,
  gridHeight,
  tileSize,
  containerSize,
  isGridVisible
}) => {
  const snap = useSnapshot(battlemapStore);
  
  // Calculate grid offset to center it in the container
  const offsetX = (containerSize.width - (gridWidth * tileSize)) / 2;
  const offsetY = (containerSize.height - (gridHeight * tileSize)) / 2;
  
  // Draw grid lines
  const drawGrid = useCallback((g: Graphics) => {
    if (!isGridVisible) {
      g.clear();
      return;
    }

    g.clear();
    g.lineStyle(1, 0xFFFFFF, 0.3);
    
    // Draw vertical lines
    for (let i = 0; i <= gridWidth; i++) {
      const x = offsetX + (i * tileSize);
      g.moveTo(x, offsetY);
      g.lineTo(x, offsetY + (gridHeight * tileSize));
    }
    
    // Draw horizontal lines
    for (let i = 0; i <= gridHeight; i++) {
      const y = offsetY + (i * tileSize);
      g.moveTo(offsetX, y);
      g.lineTo(offsetX + (gridWidth * tileSize), y);
    }
  }, [offsetX, offsetY, gridWidth, gridHeight, tileSize, isGridVisible]);
  
  // Draw tiles
  const drawTiles = useCallback((g: Graphics) => {
    g.clear();
    
    // Draw background
    g.beginFill(0x000000);
    g.drawRect(
      offsetX, 
      offsetY, 
      gridWidth * tileSize, 
      gridHeight * tileSize
    );
    g.endFill();
    
    // Draw tiles based on their types
    Object.values(snap.grid.tiles).forEach(tile => {
      const [x, y] = tile.position;
      const tileX = offsetX + (x * tileSize);
      const tileY = offsetY + (y * tileSize);
      
      // Fill color based on tile walkability
      const color = tile.walkable ? 0x333333 : 0x666666;
      g.beginFill(color);
      g.drawRect(tileX, tileY, tileSize, tileSize);
      g.endFill();
    });
  }, [snap.grid.tiles, offsetX, offsetY, tileSize, gridWidth, gridHeight]);
  
  // Cell highlight
  const drawCellHighlight = useCallback((g: Graphics) => {
    const { x, y } = snap.view.hoveredCell;
    
    // Only draw if valid coordinates
    if (x < 0 || y < 0 || x >= gridWidth || y >= gridHeight) {
      g.clear();
      return;
    }
    
    g.clear();
    g.beginFill(0x00FF00, 0.3);
    g.drawRect(
      offsetX + (x * tileSize),
      offsetY + (y * tileSize),
      tileSize,
      tileSize
    );
    g.endFill();
  }, [snap.view.hoveredCell, offsetX, offsetY, tileSize, gridWidth, gridHeight]);
  
  return (
    <pixiContainer>
      <pixiGraphics draw={drawTiles} />
      <pixiGraphics draw={drawGrid} />
      <pixiGraphics draw={drawCellHighlight} />
    </pixiContainer>
  );
}; 