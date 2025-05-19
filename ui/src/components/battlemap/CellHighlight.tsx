import React, { useCallback } from 'react';
import { Graphics as PixiGraphics } from 'pixi.js';
import { mapHelpers } from '../../store/mapStore';

interface CellHighlightProps {
  x: number;
  y: number;
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
}

// CellHighlight component that highlights the hovered cell
export const CellHighlight: React.FC<CellHighlightProps> = ({ 
  x, 
  y, 
  width, 
  height, 
  gridSize, 
  tileSize 
}) => {
  const drawHighlight = useCallback((g: PixiGraphics) => {
    // Only draw if we have valid coordinates
    if (x < 0 || y < 0 || x >= gridSize.cols || y >= gridSize.rows) return;

    // Use mapHelpers to calculate base offsets
    const { offsetX, offsetY } = mapHelpers.getGridBaseOffset();

    g.clear();
    g.setFillStyle({
      color: 0x00ff00,
      alpha: 0.3
    });
    g.rect(
      offsetX + (x * tileSize),
      offsetY + (y * tileSize),
      tileSize,
      tileSize
    );
    g.fill();
  }, [x, y, tileSize, gridSize.cols, gridSize.rows]);
  
  return <pixiGraphics draw={drawHighlight} />;
}; 