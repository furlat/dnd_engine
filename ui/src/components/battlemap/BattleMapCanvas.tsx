import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Application, extend } from '@pixi/react';
import { Graphics as PixiGraphics, Container, FederatedPointerEvent, Sprite, Assets, Texture } from 'pixi.js';
import { Box, Paper, Typography, IconButton } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import { fetchEntitySummaries } from '../../api/characterApi';
import { EntitySummary } from '../../models/character';
import { fetchGridSnapshot, TileSummary } from '../../api/tileApi';
import { TileType } from './TileEditor';

// Initialize PixiJS Assets
Assets.init({
  basePath: '/',
});

// Extend must be called at the module level
extend({ Container, Graphics: PixiGraphics, Sprite });

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

interface EntitySpriteProps {
  entity: EntitySummary;
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
}

// EntitySprite component that renders a sprite at the entity's position
const EntitySprite: React.FC<EntitySpriteProps> = ({ entity, width, height, gridSize, tileSize }) => {
  const [texture, setTexture] = useState<Texture | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Calculate the offset to center the grid
  const offsetX = (width - (gridSize.cols * tileSize)) / 2;
  const offsetY = (height - (gridSize.rows * tileSize)) / 2;
  const [x, y] = entity.position;
  const pixelX = offsetX + (x * tileSize) + (tileSize / 2);
  const pixelY = offsetY + (y * tileSize) + (tileSize / 2);

  useEffect(() => {
    const loadTexture = async () => {
      if (entity.sprite_name) {
        try {
          const spritePath = `/sprites/${entity.sprite_name}`;
          let loadedTexture = Assets.get(spritePath);
          
          if (!loadedTexture) {
            loadedTexture = await Assets.load(spritePath);
          }
          
          setTexture(loadedTexture);
          setLoadError(null);
        } catch (error) {
          console.error(`Error loading sprite for ${entity.name}:`, error);
          setLoadError(error instanceof Error ? error.message : 'Failed to load sprite');
          setTexture(null);
        }
      }
    };
    loadTexture();
  }, [entity.sprite_name, entity.name]);

  if (loadError) {
    console.warn(`Failed to load sprite for ${entity.name}:`, loadError);
    return null;
  }

  if (!texture || !entity.sprite_name) {
    console.log(`No texture or sprite name for entity ${entity.name}`);
    return null;
  }

  return (
    <pixiSprite
      texture={texture}
      x={pixelX}
      y={pixelY}
      width={tileSize}
      height={tileSize}
      anchor={0.5}
    />
  );
};

interface TileSpriteProps {
  tile: TileSummary;
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
}

const TileSprite: React.FC<TileSpriteProps> = ({ tile, width, height, gridSize, tileSize }) => {
  const [texture, setTexture] = useState<Texture | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  
  // Calculate the offset to center the grid
  const offsetX = (width - (gridSize.cols * tileSize)) / 2;
  const offsetY = (height - (gridSize.rows * tileSize)) / 2;
  const [x, y] = tile.position;

  // Always define the draw callback with useCallback
  const drawFallback = useCallback((g: PixiGraphics) => {
    const color = tile.walkable ? 0x333333 : 0x666666;
    g.clear();
    g.setFillStyle({
      color: color,
      alpha: 1
    });
    g.rect(
      offsetX + (x * tileSize),
      offsetY + (y * tileSize),
      tileSize,
      tileSize
    );
    g.fill();
  }, [tile.walkable, offsetX, offsetY, x, y, tileSize]);

  useEffect(() => {
    const loadTexture = async () => {
      if (tile.sprite_name) {
        try {
          const spritePath = `/tiles/${tile.sprite_name}`;
          let loadedTexture = Assets.get(spritePath);
          
          if (!loadedTexture) {
            loadedTexture = await Assets.load(spritePath);
          }
          
          setTexture(loadedTexture);
          setLoadError(null);
        } catch (error) {
          console.error(`Error loading tile sprite:`, error);
          setLoadError(error instanceof Error ? error.message : 'Failed to load sprite');
          setTexture(null);
        }
      }
    };
    loadTexture();
  }, [tile.sprite_name]);

  if (loadError || !texture || !tile.sprite_name) {
    return (
      <pixiGraphics draw={drawFallback} />
    );
  }

  return (
    <pixiSprite
      texture={texture}
      x={offsetX + (x * tileSize)}
      y={offsetY + (y * tileSize)}
      width={tileSize}
      height={tileSize}
    />
  );
};

interface BattleMapCanvasProps {
  width: number;
  height: number;
  tileSize?: number;
  onCellClick?: (x: number, y: number, handleOptimisticUpdate: (newTile: TileSummary) => void) => void;
  isEditing?: boolean;
  isLocked?: boolean;
  onLockChange?: (locked: boolean) => void;
  containerWidth: number;
  containerHeight: number;
}

const MIN_TILE_SIZE = 8;
const MAX_TILE_SIZE = 128;
const TILE_SIZE_STEP = 16;

const BattleMapCanvas: React.FC<BattleMapCanvasProps> = ({ 
  width: gridWidth, 
  height: gridHeight,
  tileSize: initialTileSize = 32,
  onCellClick,
  isEditing = false,
  isLocked = false,
  onLockChange,
  containerWidth,
  containerHeight
}) => {
  const [hoveredCell, setHoveredCell] = useState({ x: -1, y: -1 });
  const [tileSize, setTileSize] = useState(initialTileSize);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [entities, setEntities] = useState<EntitySummary[]>([]);
  const [tiles, setTiles] = useState<Record<string, TileSummary>>({});
  const [gridDimensions, setGridDimensions] = useState({ width: 0, height: 0 });
  const MOVEMENT_SPEED = 8;

  // Preload all sprites
  useEffect(() => {
    const preloadSprites = async () => {
      try {
        // List of all available sprites
        const spriteFiles = [
          'death_knight.png',
          'deep_elf_fighter_new.png',
          'hell_knight_new.png'
        ];

        // Load all sprites
        const loadPromises = spriteFiles.map(sprite => {
          const spritePath = `/sprites/${sprite}`;
          console.log(`Preloading sprite: ${spritePath}`);
          return Assets.load(spritePath);
        });

        await Promise.all(loadPromises);
        console.log('All sprites preloaded successfully');
      } catch (error) {
        console.error('Error preloading sprites:', error);
      }
    };

    preloadSprites();
  }, []);

  // Preload tile sprites
  useEffect(() => {
    const preloadSprites = async () => {
      try {
        const tileSprites = [
          'floor.png',
          'wall.png',
          'water.png'
        ];

        const loadPromises = tileSprites.map(sprite => {
          const spritePath = `/tiles/${sprite}`;
          return Assets.load(spritePath);
        });

        await Promise.all(loadPromises);
        console.log('All tile sprites preloaded successfully');
      } catch (error) {
        console.error('Error preloading tile sprites:', error);
      }
    };

    preloadSprites();
  }, []);

  // Fetch entities
  useEffect(() => {
    const fetchEntities = async () => {
      try {
        const summaries = await fetchEntitySummaries();
        console.log('Fetched entities with full payload:', summaries.map(e => ({
          name: e.name,
          sprite_name: e.sprite_name,
          position: e.position,
          full: e
        })));
        setEntities(summaries);
      } catch (error) {
        console.error('Error fetching entities:', error);
      }
    };
    fetchEntities();

    // Set up polling for entity updates
    const interval = setInterval(fetchEntities, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch grid data
  useEffect(() => {
    const fetchGrid = async () => {
      try {
        const grid = await fetchGridSnapshot();
        setTiles(grid.tiles);
        setGridDimensions({ width: grid.width, height: grid.height });
      } catch (error) {
        console.error('Error fetching grid:', error);
      }
    };

    fetchGrid();
    // Reduced polling frequency since we have optimistic updates
    const interval = setInterval(fetchGrid, 2000);
    return () => clearInterval(interval);
  }, []);

  // Optimize entity fetching
  useEffect(() => {
    let isMounted = true;
    const fetchEntitiesData = async () => {
      try {
        const summaries = await fetchEntitySummaries();
        if (isMounted) {
          setEntities(summaries);
        }
      } catch (error) {
        console.error('Error fetching entities:', error);
      }
    };

    fetchEntitiesData();
    const interval = setInterval(fetchEntitiesData, 200); // More frequent updates for entities
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Calculate the canvas size to fill the container
  const canvasSize = useMemo(() => ({
    width: containerWidth,
    height: containerHeight
  }), [containerWidth, containerHeight]);

  // Calculate base tile size to fit the grid in the container
  const baseTileSize = useMemo(() => {
    const horizontalFit = containerWidth / gridWidth;
    const verticalFit = containerHeight / gridHeight;
    return Math.floor(Math.min(horizontalFit, verticalFit));
  }, [containerWidth, containerHeight, gridWidth, gridHeight]);

  // Handle pointer move with corrected calculations
  const handlePointerMove = useCallback((event: FederatedPointerEvent) => {
    const mousePosition = event.global;
    
    // Calculate the offset to center the grid
    const offsetX = (canvasSize.width - (gridWidth * tileSize)) / 2;
    const offsetY = (canvasSize.height - (gridHeight * tileSize)) / 2;

    // Convert mouse position to grid coordinates
    const gridX = Math.floor((mousePosition.x - offsetX - offset.x) / tileSize);
    const gridY = Math.floor((mousePosition.y - offsetY - offset.y) / tileSize);
    
    // Update hover state if within grid bounds
    if (gridX >= 0 && gridX < gridWidth && gridY >= 0 && gridY < gridHeight) {
      setHoveredCell({ x: gridX, y: gridY });
    } else {
      setHoveredCell({ x: -1, y: -1 });
    }
  }, [canvasSize.width, canvasSize.height, gridWidth, gridHeight, tileSize, offset]);

  // Handle pointer down with the same calculations
  const handlePointerDown = useCallback((event: FederatedPointerEvent) => {
    if (!isEditing || isLocked || !onCellClick) return;

    const mousePosition = event.global;
    const offsetX = (canvasSize.width - (gridWidth * tileSize)) / 2;
    const offsetY = (canvasSize.height - (gridHeight * tileSize)) / 2;
    
    // Convert mouse position to grid coordinates
    const gridX = Math.floor((mousePosition.x - offsetX - offset.x) / tileSize);
    const gridY = Math.floor((mousePosition.y - offsetY - offset.y) / tileSize);
    
    // Only trigger if within grid bounds
    if (gridX >= 0 && gridX < gridWidth && gridY >= 0 && gridY < gridHeight) {
      const handleOptimisticUpdate = (newTile: TileSummary) => {
        setTiles(prev => ({
          ...prev,
          [newTile.uuid]: newTile
        }));
      };
      
      onCellClick(gridX, gridY, handleOptimisticUpdate);
    }
  }, [canvasSize.width, canvasSize.height, gridWidth, gridHeight, tileSize, offset, onCellClick, isEditing, isLocked]);

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
    const newLockState = !isLocked;
    onLockChange?.(newLockState);
  }, [isLocked, onLockChange]);

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
              cursor={isEditing ? "crosshair" : "pointer"}
              interactive={true}
              onPointerEnter={() => {}}
              onPointerLeave={() => setHoveredCell({ x: -1, y: -1 })}
              onPointerMove={handlePointerMove}
              onPointerDown={handlePointerDown}
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
              
              {/* Tiles */}
              {Object.values(tiles).map(tile => (
                <TileSprite
                  key={tile.uuid}
                  tile={tile}
                  width={canvasSize.width}
                  height={canvasSize.height}
                  gridSize={{ rows: gridHeight, cols: gridWidth }}
                  tileSize={tileSize}
                />
              ))}
              
              {/* Hovered Cell Highlight */}
              <CellHighlight 
                x={hoveredCell.x}
                y={hoveredCell.y}
                width={canvasSize.width}
                height={canvasSize.height}
                gridSize={{ rows: gridHeight, cols: gridWidth }}
                tileSize={tileSize}
              />

              {/* Game Objects Container - Now after grid and highlight */}
              {entities.map(entity => {
                console.log('Rendering entity:', entity);
                return (
                  <EntitySprite
                    key={entity.uuid}
                    entity={entity}
                    width={canvasSize.width}
                    height={canvasSize.height}
                    gridSize={{ rows: gridHeight, cols: gridWidth }}
                    tileSize={tileSize}
                  />
                );
              })}
            </pixiContainer>
          </pixiContainer>
        </Application>
      </div>
    </div>
  );
};

export default BattleMapCanvas; 