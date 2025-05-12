import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Application, extend } from '@pixi/react';
import { Graphics as PixiGraphics, Container, FederatedPointerEvent } from 'pixi.js';
import { Box, Paper, Typography, IconButton } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';

// Extend must be called at the module level
extend({ Container, Graphics: PixiGraphics });

interface Position {
  x: number;
  y: number;
}

interface GridProps {
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
}

// Grid component that draws the grid lines
const Grid: React.FC<GridProps> = ({ width, height, gridSize, tileSize }) => {
  const drawGrid = useCallback((g: PixiGraphics) => {
    g.clear();
    g.setStrokeStyle({
      width: 1,
      color: 0xFFFFFF,
      alpha: 0.8
    });
    
    // Calculate the offset to center the grid
    const offsetX = (width - (gridSize.cols * tileSize)) / 2;
    const offsetY = (height - (gridSize.rows * tileSize)) / 2;
    
    // Draw vertical lines
    for (let i = 0; i <= gridSize.cols; i++) {
      const x = offsetX + (i * tileSize);
      g.moveTo(x, offsetY);
      g.lineTo(x, offsetY + (gridSize.rows * tileSize));
    }
    
    // Draw horizontal lines
    for (let i = 0; i <= gridSize.rows; i++) {
      const y = offsetY + (i * tileSize);
      g.moveTo(offsetX, y);
      g.lineTo(offsetX + (gridSize.cols * tileSize), y);
    }

    g.stroke();
  }, [width, height, gridSize.cols, gridSize.rows, tileSize]);
  
  return <pixiGraphics draw={drawGrid} />;
};

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
const CellHighlight: React.FC<CellHighlightProps> = ({ x, y, width, height, gridSize, tileSize }) => {
  const drawHighlight = useCallback((g: PixiGraphics) => {
    // Only draw if we have valid coordinates
    if (x < 0 || y < 0 || x >= gridSize.cols || y >= gridSize.rows) return;

    const offsetX = (width - (gridSize.cols * tileSize)) / 2;
    const offsetY = (height - (gridSize.rows * tileSize)) / 2;

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
  }, [x, y, width, height, gridSize, tileSize]);
  
  return <pixiGraphics draw={drawHighlight} />;
};

interface BattleMapCanvasProps {
  width: number;
  height: number;
  tileSize?: number;
}

const MIN_TILE_SIZE = 16;
const MAX_TILE_SIZE = 64;
const TILE_SIZE_STEP = 8;

const BattleMapCanvas: React.FC<BattleMapCanvasProps> = ({ 
  width: gridWidth, 
  height: gridHeight,
  tileSize: initialTileSize = 32
}) => {
  const [hoveredCell, setHoveredCell] = useState({ x: -1, y: -1 });
  const [tileSize, setTileSize] = useState(initialTileSize);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isLocked, setIsLocked] = useState(false);
  const MOVEMENT_SPEED = 8;

  // Calculate the canvas size
  const canvasSize = useMemo(() => {
    const minWidth = (gridWidth * tileSize) + (tileSize * 4);
    const minHeight = (gridHeight * tileSize) + (tileSize * 4);
    return {
      width: Math.max(800, minWidth),
      height: Math.max(600, minHeight)
    };
  }, [gridWidth, gridHeight, tileSize]);

  // Handle WASD movement
  useEffect(() => {
    if (isLocked) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key.toLowerCase()) {
        case 'w':
          setOffset(prev => ({ ...prev, y: prev.y + MOVEMENT_SPEED }));
          break;
        case 's':
          setOffset(prev => ({ ...prev, y: prev.y - MOVEMENT_SPEED }));
          break;
        case 'a':
          setOffset(prev => ({ ...prev, x: prev.x + MOVEMENT_SPEED }));
          break;
        case 'd':
          setOffset(prev => ({ ...prev, x: prev.x - MOVEMENT_SPEED }));
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isLocked]);

  const handlePointerMove = useCallback((event: FederatedPointerEvent) => {
    const mousePosition = event.global;
    
    // Calculate grid offsets including the movement offset
    const offsetX = (canvasSize.width - (gridWidth * tileSize)) / 2;
    const offsetY = (canvasSize.height - (gridHeight * tileSize)) / 2;

    // Convert mouse position to grid coordinates, subtracting the offset
    const gridX = Math.floor((mousePosition.x - offsetX - offset.x) / tileSize);
    const gridY = Math.floor((mousePosition.y - offsetY - offset.y) / tileSize);
    
    // Update hover state if within grid bounds
    if (gridX >= 0 && gridX < gridWidth && gridY >= 0 && gridY < gridHeight) {
      setHoveredCell({ x: gridX, y: gridY });
    } else {
      setHoveredCell({ x: -1, y: -1 });
    }
  }, [canvasSize.width, canvasSize.height, gridWidth, gridHeight, tileSize, offset]);

  const handleZoomIn = useCallback(() => {
    setTileSize(prev => Math.min(prev + TILE_SIZE_STEP, MAX_TILE_SIZE));
  }, []);

  const handleZoomOut = useCallback(() => {
    setTileSize(prev => Math.max(prev - TILE_SIZE_STEP, MIN_TILE_SIZE));
  }, []);

  const handleResetView = useCallback(() => {
    setTileSize(initialTileSize);
    setOffset({ x: 0, y: 0 });
  }, [initialTileSize]);

  const toggleLock = useCallback(() => {
    setIsLocked(prev => !prev);
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Position Display and Controls */}
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
          Position: ({hoveredCell.x}, {hoveredCell.y})
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <IconButton 
            size="small" 
            onClick={handleZoomOut}
            sx={{ color: 'white' }}
          >
            <RemoveIcon />
          </IconButton>
          <IconButton 
            size="small" 
            onClick={handleResetView}
            sx={{ color: 'white' }}
          >
            <RestartAltIcon />
          </IconButton>
          <IconButton 
            size="small" 
            onClick={handleZoomIn}
            sx={{ color: 'white' }}
          >
            <AddIcon />
          </IconButton>
          <IconButton
            size="small"
            onClick={toggleLock}
            sx={{ color: 'white' }}
          >
            {isLocked ? <LockIcon /> : <LockOpenIcon />}
          </IconButton>
        </Box>
      </Paper>

      {/* Canvas */}
      <div style={{ 
        display: 'flex', 
        width: '100%', 
        height: '100%',
        justifyContent: 'center',
        alignItems: 'center',
        overflow: 'hidden'
      }}>
        <Application
          width={canvasSize.width}
          height={canvasSize.height}
          backgroundColor={0x000000}
          antialias={true}
        >
          <pixiContainer>
            {/* Draw a background to ensure we can see the canvas */}
            <pixiGraphics
              eventMode="static"
              cursor="pointer"
              interactive={true}
              onPointerEnter={() => {}}
              onPointerLeave={() => setHoveredCell({ x: -1, y: -1 })}
              onPointerMove={handlePointerMove}
              draw={useCallback((g: PixiGraphics) => {
                g.clear();
                g.setFillStyle({
                  color: 0x000000
                });
                g.rect(0, 0, canvasSize.width, canvasSize.height);
                g.fill();
              }, [canvasSize.width, canvasSize.height])}
            />
            
            <pixiContainer
              x={offset.x}
              y={offset.y}
            >
              {/* Grid Lines */}
              <Grid 
                width={canvasSize.width}
                height={canvasSize.height}
                gridSize={{ rows: gridHeight, cols: gridWidth }}
                tileSize={tileSize}
              />
              
              {/* Game Objects Container */}
              <pixiContainer>
                {/* TODO: Add game objects here */}
              </pixiContainer>
              
              {/* Hovered Cell Highlight */}
              <CellHighlight 
                x={hoveredCell.x}
                y={hoveredCell.y}
                width={canvasSize.width}
                height={canvasSize.height}
                gridSize={{ rows: gridHeight, cols: gridWidth }}
                tileSize={tileSize}
              />
            </pixiContainer>
          </pixiContainer>
        </Application>
      </div>
    </div>
  );
};

export default BattleMapCanvas; 