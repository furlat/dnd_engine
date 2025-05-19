import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Application, extend } from '@pixi/react';
import * as PIXI from 'pixi.js';
import { Graphics as PixiGraphics, Container, FederatedPointerEvent, Sprite, Assets, Texture, BLEND_MODES } from 'pixi.js';
import { Box, Paper, Typography, IconButton, Tooltip, Divider } from '@mui/material';
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
import { fetchEntitySummaries } from '../../api/characterApi';
import { EntitySummary } from '../../models/character';
import { fetchGridSnapshot, TileSummary } from '../../api/tileApi';
import { TileType } from './TileEditor';
import { characterStore, characterActions } from '../../store/characterStore';
import { useSnapshot } from 'valtio';
import { ReadonlyEntitySummary } from '../../models/readonly';
import type { DeepReadonly } from '../../models/readonly';
import { SensesType } from '../../models/character';
import SettingsButton from '../settings/SettingsButton';

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
  entity: EntitySummary | ReadonlyEntitySummary;
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
  tile: TileSummary | DeepReadonly<TileSummary>;
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
  alpha?: number;
}

const TileSprite: React.FC<TileSpriteProps> = ({ tile, width, height, gridSize, tileSize, alpha = 1 }) => {
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
      alpha={alpha}
    />
  );
};

interface MovementHighlightProps {
  selectedEntity: ReadonlyEntitySummary | undefined;
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
}

const MovementHighlight: React.FC<MovementHighlightProps> = ({
  selectedEntity,
  width,
  height,
  gridSize,
  tileSize
}) => {
  const drawHighlight = useCallback((g: PixiGraphics) => {
    if (!selectedEntity) {
      console.log('No selected entity for movement highlight');
      return;
    }

    console.log('Drawing movement highlight for entity:', selectedEntity.name);
    console.log('Path data:', selectedEntity.senses.paths);

    g.clear();

    // Calculate grid offset
    const offsetX = (width - (gridSize.cols * tileSize)) / 2;
    const offsetY = (height - (gridSize.rows * tileSize)) / 2;

    // Draw highlights only for terminal positions of paths with length ≤ 6
    for (let x = 0; x < gridSize.cols; x++) {
      for (let y = 0; y < gridSize.rows; y++) {
        const posKey = `${x},${y}`;
        const path = selectedEntity.senses.paths[posKey];
        
        if (path && path.length <= 6) {
          console.log(`Found valid path at ${posKey}, length: ${path.length}`);
          g.setFillStyle({
            color: 0x00ff00,
            alpha: 0.5
          });

          g.rect(
            offsetX + (x * tileSize),
            offsetY + (y * tileSize),
            tileSize,
            tileSize
          );
          g.fill();
        }
      }
    }
  }, [selectedEntity, width, height, gridSize, tileSize]);

  return <pixiGraphics draw={drawHighlight} />;
};

interface BattleMapCanvasProps {
  width: number;
  height: number;
  tileSize?: number;
  onCellClick?: (x: number, y: number, handleOptimisticUpdate: (newTile: TileSummary) => void) => void;
  onEntityClick?: (entityId: string, x: number, y: number, tileSize: number, mapState: { offsetX: number; offsetY: number; gridOffsetX: number; gridOffsetY: number; actualTileSize: number }) => void;
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
  onEntityClick,
  isEditing = false,
  isLocked = false,
  onLockChange,
  containerWidth,
  containerHeight
}) => {
  const [hoveredCell, setHoveredCell] = useState({ x: -1, y: -1 });
  const [tileSize, setTileSize] = useState(initialTileSize);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [gridDimensions, setGridDimensions] = useState({ width: 0, height: 0 });
  const MOVEMENT_SPEED = 8;
  const [isVisibilityEnabled, setIsVisibilityEnabled] = useState(true);
  const [isGridEnabled, setIsGridEnabled] = useState(true);
  const [isMovementHighlightEnabled, setIsMovementHighlightEnabled] = useState(false);
  
  // Use the store for entities and tiles
  const snap = useSnapshot(characterStore);
  const entities = Object.values(snap.summaries);
  const tiles = snap.tiles;

  // Get selected entity's senses
  const selectedEntity = snap.selectedEntityId ? snap.summaries[snap.selectedEntityId] : undefined;
  const entitySenses = selectedEntity?.senses.extra_senses || [];

  // Function to get visibility tooltip text
  const getVisibilityTooltip = useCallback(() => {
    if (!selectedEntity) return "Select an entity to toggle visibility";
    
    const sensesList = entitySenses.length > 0 
      ? `\nSenses: ${entitySenses.join(', ')}`
      : '';
      
    return `Toggle visibility for ${selectedEntity.name}${sensesList}`;
  }, [selectedEntity, entitySenses]);

  // Get movement highlight tooltip text
  const getMovementTooltip = useCallback(() => {
    if (!selectedEntity) return "Select an entity to show movement range";
    return `Show movement range for ${selectedEntity.name}\nGreen: ≤30ft (6 squares)\nRed: >30ft`;
  }, [selectedEntity]);

  // Start polling when component mounts
  useEffect(() => {
    characterActions.startPolling();
    return () => {
      characterActions.stopPolling();
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
  }, [canvasSize?.width, canvasSize?.height, gridWidth, gridHeight, tileSize, offset]);

  // Handle pointer down with the same calculations
  const handlePointerDown = useCallback((event: FederatedPointerEvent) => {
    const mousePosition = event.global;
    const offsetX = (canvasSize.width - (gridWidth * tileSize)) / 2;
    const offsetY = (canvasSize.height - (gridHeight * tileSize)) / 2;
    
    // Convert mouse position to grid coordinates
    const gridX = Math.floor((mousePosition.x - offsetX - offset.x) / tileSize);
    const gridY = Math.floor((mousePosition.y - offsetY - offset.y) / tileSize);
    
    // Only proceed if within grid bounds
    if (gridX >= 0 && gridX < gridWidth && gridY >= 0 && gridY < gridHeight) {
      // Handle left click for tile editing
      if (event.button === 0 && isEditing && !isLocked && onCellClick) {
        onCellClick(gridX, gridY, (newTile: TileSummary) => {
          characterActions.fetchTiles(); // Refresh tiles after update
        });
      } else if (event.button === 0 && selectedEntity && !isLocked && onEntityClick) {
        // Check if there's an entity at the clicked position
        const entitiesAtPosition = Object.values(snap.summaries).filter(entity => 
          entity.position[0] === gridX && entity.position[1] === gridY
        );

        const targetEntity = entitiesAtPosition.find(entity => entity.uuid !== selectedEntity.uuid);
        if (targetEntity) {
          // Calculate pixel position for animation, taking into account offset and scaling
          const pixelX = offsetX + (gridX * tileSize) + (tileSize / 2) + offset.x;
          const pixelY = offsetY + (gridY * tileSize) + (tileSize / 2) + offset.y;

          // Pass the current map state to the callback
          onEntityClick(
            targetEntity.uuid, 
            pixelX, 
            pixelY, 
            tileSize,
            {
              offsetX: offsetX + offset.x,
              offsetY: offsetY + offset.y,
              gridOffsetX: offset.x,
              gridOffsetY: offset.y,
              actualTileSize: tileSize
            }
          );
        }
      }
      
      // Handle right click for movement
      if (event.button === 2 && selectedEntity && !isLocked) {
        event.preventDefault();
        event.stopPropagation();
        
        // Check if the position is walkable
        const posKey = `${gridX},${gridY}`;
        const isWalkable = tiles[posKey]?.walkable ?? false;
        
        // Only check path if movement highlight is enabled
        if (isWalkable && (!isMovementHighlightEnabled || 
            (selectedEntity.senses.paths[posKey] && selectedEntity.senses.paths[posKey].length <= 6))) {
          characterActions.moveEntity(selectedEntity.uuid, [gridX, gridY]);
        }
      }
    }
  }, [
    canvasSize?.width,
    canvasSize?.height,
    gridWidth,
    gridHeight,
    tileSize,
    offset,
    onCellClick,
    onEntityClick,
    isEditing,
    isLocked,
    selectedEntity,
    tiles,
    snap.summaries,
    isMovementHighlightEnabled
  ]);

  // Prevent context menu on right click
  useEffect(() => {
    const preventDefault = (e: Event) => e.preventDefault();
    const canvas = document.querySelector('canvas');
    if (canvas) {
      canvas.addEventListener('contextmenu', preventDefault);
      return () => canvas.removeEventListener('contextmenu', preventDefault);
    }
  }, []);

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

  // Add debug log for movement highlight toggle
  const handleMovementHighlightToggle = useCallback(() => {
    const newState = !isMovementHighlightEnabled;
    console.log('Toggling movement highlight:', newState);
    if (newState && selectedEntity) {
      console.log('Selected entity for movement:', selectedEntity.name);
      console.log('Path data available:', Object.keys(selectedEntity.senses.paths).length);
    }
    setIsMovementHighlightEnabled(newState);
  }, [isMovementHighlightEnabled, selectedEntity]);

  // Create a memoized map of valid path positions
  const validPathPositions = useMemo(() => {
    if (!selectedEntity || !isMovementHighlightEnabled) return {};
    
    const positions: Record<string, boolean> = {};
    Object.entries(selectedEntity.senses.paths).forEach(([posKey, path]) => {
      if (path && path.length <= 6) {
        positions[posKey] = true;
      }
    });
    return positions;
  }, [selectedEntity, isMovementHighlightEnabled]);

  // Draw callback for path highlights
  const drawPathHighlight = useCallback((g: PixiGraphics, position: readonly [number, number]) => {
    const offsetX = (canvasSize.width - (gridWidth * tileSize)) / 2;
    const offsetY = (canvasSize.height - (gridHeight * tileSize)) / 2;
    const posKey = `${position[0]},${position[1]}`;
    
    g.clear();
    g.setFillStyle({
      color: validPathPositions[posKey] ? 0x00ff00 : 0xff0000,
      alpha: validPathPositions[posKey] ? 0.3 : 0.3  // Reduced alpha values
    });
    g.rect(
      offsetX + (position[0] * tileSize),
      offsetY + (position[1] * tileSize),
      tileSize,
      tileSize
    );
    g.fill();
  }, [canvasSize.width, canvasSize.height, gridWidth, gridHeight, tileSize, validPathPositions]);

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
        <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
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

          <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />

          {/* Lock Button */}
          <IconButton
            size="small"
            onClick={toggleLock}
            sx={{ color: 'white' }}
          >
            {isLocked ? <LockIcon /> : <LockOpenIcon />}
          </IconButton>

          {/* Grid Toggle */}
          <Tooltip title="Toggle Grid">
            <IconButton
              size="small"
              onClick={() => setIsGridEnabled(!isGridEnabled)}
              sx={{ color: 'white' }}
            >
              {isGridEnabled ? <GridOnIcon /> : <GridOffIcon />}
            </IconButton>
          </Tooltip>

          {/* Visibility Toggle */}
          <Tooltip title={getVisibilityTooltip()}>
            <span>
              <IconButton
                size="small"
                onClick={() => setIsVisibilityEnabled(!isVisibilityEnabled)}
                sx={{ 
                  color: 'white',
                  opacity: selectedEntity ? 1 : 0.5
                }}
                disabled={!selectedEntity}
              >
                {isVisibilityEnabled ? <VisibilityIcon /> : <VisibilityOffIcon />}
              </IconButton>
            </span>
          </Tooltip>

          {/* Movement Range Toggle with updated handler */}
          <Tooltip title={getMovementTooltip()}>
            <span>
              <IconButton
                size="small"
                onClick={handleMovementHighlightToggle}
                sx={{ 
                  color: 'white',
                  opacity: selectedEntity ? 1 : 0.5,
                  backgroundColor: isMovementHighlightEnabled ? 'rgba(255, 255, 255, 0.1)' : 'transparent'
                }}
                disabled={!selectedEntity}
              >
                <DirectionsRunIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
        <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
        <SettingsButton />
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
            
            <pixiContainer x={offset.x} y={offset.y}>
              {/* Grid Lines - Now conditional */}
              {isGridEnabled && (
                <Grid 
                  width={canvasSize.width}
                  height={canvasSize.height}
                  gridSize={{ rows: gridHeight, cols: gridWidth }}
                  tileSize={tileSize}
                />
              )}
              
              {/* Tiles - Now with fog of war effect */}
              {Object.values(tiles).map(tile => {
                // Skip visibility checks if toggle is off
                if (!isVisibilityEnabled) {
                  return (
                    <React.Fragment key={tile.uuid}>
                      <TileSprite
                        tile={tile}
                        width={canvasSize.width}
                        height={canvasSize.height}
                        gridSize={{ rows: gridHeight, cols: gridWidth }}
                        tileSize={tileSize}
                      />
                      {isMovementHighlightEnabled && (
                        <pixiGraphics
                          draw={(g) => drawPathHighlight(g, tile.position)}
                        />
                      )}
                    </React.Fragment>
                  );
                }

                // With visibility enabled, check visibility and seen status
                if (!selectedEntity) return null;

                const [x, y] = tile.position;
                const posKey = `${x},${y}`;
                const isVisible = selectedEntity.senses.visible[posKey];
                const hasBeenSeen = selectedEntity.senses.seen.some(
                  ([seenX, seenY]) => seenX === x && seenY === y
                );

                // If neither visible nor seen, don't render
                if (!isVisible && !hasBeenSeen) return null;

                const offsetX = (canvasSize.width - (gridWidth * tileSize)) / 2;
                const offsetY = (canvasSize.height - (gridHeight * tileSize)) / 2;

                return (
                  <React.Fragment key={tile.uuid}>
                    <TileSprite
                      tile={tile}
                      width={canvasSize.width}
                      height={canvasSize.height}
                      gridSize={{ rows: gridHeight, cols: gridWidth }}
                      tileSize={tileSize}
                      alpha={isVisible ? 1 : 0.5} // Dim previously seen tiles
                    />
                    {/* Add fog of war overlay for seen but not visible tiles */}
                    {hasBeenSeen && !isVisible && (
                      <pixiGraphics
                        draw={(g) => {
                          g.clear();
                          g.setFillStyle({
                            color: 0x000000,
                            alpha: 0.5
                          });
                          g.rect(
                            offsetX + (x * tileSize),
                            offsetY + (y * tileSize),
                            tileSize,
                            tileSize
                          );
                          g.fill();
                        }}
                      />
                    )}
                    {isMovementHighlightEnabled && isVisible && (
                      <pixiGraphics
                        draw={(g) => drawPathHighlight(g, tile.position)}
                      />
                    )}
                  </React.Fragment>
                );
              })}
              
              {/* Entities - With visibility check */}
              {entities.map(entity => {
                // Show all entities if visibility is disabled
                if (!isVisibilityEnabled) {
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
                }

                // With visibility enabled, only show visible entities
                if (!selectedEntity) return null;

                const isVisible = entity.uuid === selectedEntity.uuid ||
                  selectedEntity.senses.entities[entity.uuid];
                
                if (!isVisible) return null;

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
              
              {/* Cell Highlight */}
              {isGridEnabled && (
                <CellHighlight 
                  x={hoveredCell.x}
                  y={hoveredCell.y}
                  width={canvasSize.width}
                  height={canvasSize.height}
                  gridSize={{ rows: gridHeight, cols: gridWidth }}
                  tileSize={tileSize}
                />
              )}
            </pixiContainer>
          </pixiContainer>
        </Application>
      </div>
    </div>
  );
};

export default BattleMapCanvas; 