import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
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
import { DirectionalEntitySprite, Direction, preloadEntityAnimations } from './DirectionalEntitySprite';
import { entityDirectionState } from '../../store/entityDirectionStore';
import { mapStore, mapActions, mapHelpers } from '../../store/mapStore';
import { AttackAnimation } from './AttackAnimation';
import { animationStore, animationActions } from '../../store/animationStore';
import TileSprite, { preloadTileTextures } from './TileSprite';

// Add TypeScript declaration for our custom property
declare global {
  interface Window {
    PIXI_ASSETS_INITIALIZED?: boolean;
  }
}

// Initialize PixiJS Assets
// Use a guard to prevent multiple initializations
if (!window.PIXI_ASSETS_INITIALIZED) {
  console.log('[ASSET-INIT] Initializing PixiJS Assets');
Assets.init({
  basePath: '/',
});
  window.PIXI_ASSETS_INITIALIZED = true;
  
  // Start preloading common textures
  preloadTileTextures().catch(err => {
    console.error('[ASSET-INIT] Error preloading tile textures:', err);
  });
} else {
  console.log('[ASSET-INIT] PixiJS Assets already initialized, skipping');
}

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
    
    // Use mapHelpers to calculate base offsets
    const { offsetX, offsetY } = mapHelpers.getGridBaseOffset();
    
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
  }, [gridSize.cols, gridSize.rows, tileSize]);
  
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
  onEntityClick?: (entityId: string) => void;
  isEditing?: boolean;
  isLocked?: boolean;
  onLockChange?: (locked: boolean) => void;
  containerWidth: number;
  containerHeight: number;
  redrawCounter?: number;
}

const MIN_TILE_SIZE = 8;
const MAX_TILE_SIZE = 128;
const TILE_SIZE_STEP = 16;

// Modify the startEntityPreloading function to not use hardcoded entity IDs
let preloadingStarted = false;
const startEntityPreloading = () => {
  if (preloadingStarted) return;
  preloadingStarted = true;
  
  // Don't use hardcoded entity IDs - the effect hook will handle this
  console.log('[ENTITY-PRELOAD] Animation preloading system initialized');
};

// Attack animations reference - prevent this from being recreated on component remount
const attackAnimationsRef = { current: {} as Record<string, any> };

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
  containerHeight,
  redrawCounter: externalRedrawCounter
}) => {
  const [hoveredCell, setHoveredCell] = useState({ x: -1, y: -1 });
  const [internalRedrawCounter, setInternalRedrawCounter] = useState(0);
  const lastPointerMoveTime = useRef<number>(0);
  const pointerMoveTimes = useRef<number[]>([]);
  const lastStatsLogTime = useRef<number>(0);
  const pointerEventsBlocked = useRef<boolean>(false);
  
  // Use external redraw counter if provided
  const redrawCounter = externalRedrawCounter ?? internalRedrawCounter;

  // Use a ref to track if this is the initial render
  const isInitialRender = useRef(true);
  
  // Use snapshots for entities, tiles, and animations
  const charSnap = useSnapshot(characterStore);
  const mapSnap = useSnapshot(mapStore);
  const animSnap = useSnapshot(animationStore);
  
  // Use a ref to track entity count for stale state detection
  const entityCountRef = useRef<number>(0);
  
  // Track animation start/end
  useEffect(() => {
    // Update entity count reference
    entityCountRef.current = Object.keys(characterStore.summaries).length;
    
    // Check for animations
    const attackAnimations = Object.entries(animSnap.attackAnimations);
    
    // Update attackAnimationsRef with current animations
    attackAnimationsRef.current = attackAnimations.reduce((acc, [key, anim]) => {
      acc[key] = anim;
      return acc;
    }, {} as Record<string, any>);
    
    if (attackAnimations.length > 0) {
      const now = performance.now();
      console.log(`[ANIM-LIFECYCLE] Canvas has ${attackAnimations.length} active animations at ${now.toFixed(2)}ms`);
      
      // Log animation durations
      attackAnimations.forEach(([key, anim]) => {
        const duration = now - anim.startTime;
        console.log(`[ANIM-LIFECYCLE] Animation ${key} running for ${duration.toFixed(2)}ms (${anim.isHit ? 'HIT' : 'MISS'})`);
      });
    }
  }, [animSnap.attackAnimations, characterStore.summaries]);
  
  // Add more detailed performance logging on mount
  useEffect(() => {
    const now = performance.now();
    console.log(`[CANVAS-PERF] BattleMapCanvas mounted at ${now.toFixed(2)}ms${isInitialRender.current ? ' (initial render)' : ' (remount)'}`);
    
    // After first render, mark as no longer initial render
    isInitialRender.current = false;
    
    // Track app render count
    let lastRenderTime = performance.now();
    let renderCount = 0;
    let renderTimes: number[] = [];
    
    // Create a ticker to monitor framerate
    const ticker = PIXI.Ticker.shared;
    
    const renderMonitor = () => {
      const now = performance.now();
      const elapsed = now - lastRenderTime;
      
      renderCount++;
      renderTimes.push(elapsed);
      
      // Keep only last 100 render times
      if (renderTimes.length > 100) {
        renderTimes.shift();
      }
      
      // Log render stats every 300 frames
      if (renderCount % 300 === 0) {
        const avgRenderTime = renderTimes.reduce((sum, time) => sum + time, 0) / renderTimes.length;
        const maxRenderTime = Math.max(...renderTimes);
        const fps = 1000 / avgRenderTime;
        
        console.log(`[RENDER-PERF] Stats - FPS: ${fps.toFixed(1)}, Avg: ${avgRenderTime.toFixed(2)}ms, Max: ${maxRenderTime.toFixed(2)}ms, Active animations: ${Object.keys(animSnap.attackAnimations).length}`);
        
        // Reset tracking
        renderTimes = [];
      }
      
      lastRenderTime = now;
    };
    
    // Add ticker to monitor framerate
    ticker.add(renderMonitor);
    
    // Start preloading animations on component mount
    startEntityPreloading();
    
    // Preload attack animations and sounds
    const preloadAttackAssets = async () => {
      try {
        console.log('[ASSET-PRELOAD] Preloading attack animations and sounds');
        const startTime = performance.now();
        
        // Import and preload attack animations
        const { preloadAnimationFrames, preloadAllSounds } = await import('./AttackAnimation');
        
        // Preload both in parallel
        await Promise.all([
          preloadAnimationFrames(),
          preloadAllSounds()
        ]);
        
        console.log(`[ASSET-PRELOAD] Attack assets preloaded in ${(performance.now() - startTime).toFixed(2)}ms`);
      } catch (err) {
        console.error('[ASSET-PRELOAD] Error preloading attack assets:', err);
      }
    };
    
    // Start preloading attack assets
    preloadAttackAssets();
    
    // Set up periodic performance logging
    const statsInterval = setInterval(() => {
      if (pointerMoveTimes.current.length > 0) {
        const avgTime = pointerMoveTimes.current.reduce((sum, time) => sum + time, 0) / pointerMoveTimes.current.length;
        console.log(`[CANVAS-PERF] Pointer events stats - Count: ${pointerMoveTimes.current.length}, Avg processing time: ${avgTime.toFixed(2)}ms`);
        pointerMoveTimes.current = [];
      }
    }, 10000);
    
    return () => {
      ticker.remove(renderMonitor);
      clearInterval(statsInterval);
      
      // Cleanup active animation references to prevent memory leaks
      const animationKeys = Object.keys(attackAnimationsRef.current);
      if (animationKeys.length > 0) {
        console.log(`[CANVAS-CLEANUP] Cleaning up ${animationKeys.length} animation references`);
        attackAnimationsRef.current = {};
      }
      
      console.log(`[CANVAS-PERF] BattleMapCanvas unmounting at ${performance.now().toFixed(2)}ms - Animations active: ${Object.keys(animSnap.attackAnimations).length}`);
    };
  }, []);
  
  // When initializing, sync with mapStore
  useEffect(() => {
    // Update container size
    mapActions.setContainerSize(containerWidth, containerHeight);
    
    // Update grid dimensions
    mapActions.setGridDimensions(gridWidth, gridHeight);
    
    // Update tile size
    mapActions.setTileSize(initialTileSize);
    
    // Sync isLocked prop with mapStore
    if (isLocked !== mapSnap.isLocked) {
      mapActions.toggleLock();
    }
  }, []);
  
  // Sync container size when it changes
  useEffect(() => {
    // Update container size
    mapActions.setContainerSize(containerWidth, containerHeight);
    
    // Set up a ResizeObserver to detect changes (like console opening)
    const containerElement = document.querySelector('.MuiBox-root');
    if (containerElement) {
      console.log('[RESIZE] Setting up ResizeObserver for container element');
      
      // Create observer to handle layout changes (like console opening)
      const resizeObserver = new ResizeObserver((entries) => {
        // Only update if there's a significant change
        const [entry] = entries;
        const { width, height } = entry.contentRect;
        
        if (Math.abs(width - containerWidth) > 10 || Math.abs(height - containerHeight) > 10) {
          console.log(`[RESIZE] Layout changed: ${width}x${height} (previous: ${containerWidth}x${containerHeight})`);
          
          // Force redraw by updating the counter
          setInternalRedrawCounter(prev => prev + 1);
        }
      });
      
      resizeObserver.observe(containerElement);
      
      return () => {
        resizeObserver.disconnect();
      };
    }
  }, [containerWidth, containerHeight]);
  
  const entities = Object.values(charSnap.summaries);
  const tiles = charSnap.tiles;

  // Get selected entity's senses
  const selectedEntity = charSnap.selectedEntityId ? charSnap.summaries[charSnap.selectedEntityId] : undefined;
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

  // Only preload animations for specific entities ONCE on entity update
  // This avoids constant reloading during polling or direction changes
  const previousEntitiesRef = useRef<string[]>([]);
  useEffect(() => {
    const currentEntityIds = Object.values(charSnap.summaries).map(e => e.uuid);
    
    // Find new entities that weren't in the previous set
    const newEntityIds = currentEntityIds.filter(
      id => !previousEntitiesRef.current.includes(id)
    );
    
    // Only preload if we have new entities
    if (newEntityIds.length > 0) {
      console.log(`[ENTITY-PRELOAD] Preloading animations for ${newEntityIds.length} new entities with UUIDs: ${newEntityIds.join(', ')}`);
      preloadEntityAnimations(newEntityIds)
        .then(() => console.log(`[ENTITY-PRELOAD] Successfully preloaded animations for ${newEntityIds.length} entities`))
        .catch(err => console.error('[ENTITY-PRELOAD] Error preloading new entity animations:', err));
    }
    
    // Update reference
    previousEntitiesRef.current = currentEntityIds;
  }, [Object.keys(charSnap.summaries).join(',')]);

  // Handle WASD movement using only mapStore for state
  useEffect(() => {
    if (mapSnap.isLocked) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const MOVEMENT_SPEED = 8;
      
      // Handle WASD for grid movement
      switch (e.key.toLowerCase()) {
        case 'w':
          mapActions.moveGrid(0, MOVEMENT_SPEED);
          setInternalRedrawCounter(prev => prev + 1);
          return;
        case 's':
          mapActions.moveGrid(0, -MOVEMENT_SPEED);
          setInternalRedrawCounter(prev => prev + 1);
          return;
        case 'a':
          mapActions.moveGrid(MOVEMENT_SPEED, 0);
          setInternalRedrawCounter(prev => prev + 1);
          return;
        case 'd':
          mapActions.moveGrid(-MOVEMENT_SPEED, 0);
          setInternalRedrawCounter(prev => prev + 1);
          return;
      }

      // Handle arrow keys for entity direction
      if (!charSnap.selectedEntityId) return;
      
      let direction: Direction | null = null;
      
      switch (e.key) {
        case 'ArrowUp':
          direction = Direction.N;
          break;
        case 'ArrowDown':
          direction = Direction.S;
          break;
        case 'ArrowLeft':
          direction = Direction.W;
          break;
        case 'ArrowRight':
          direction = Direction.E;
          break;
        // Diagonals
        case 'Home': // NumPad 7
          direction = Direction.NW;
          break;
        case 'PageUp': // NumPad 9
          direction = Direction.NE;
          break;
        case 'End': // NumPad 1
          direction = Direction.SW;
          break;
        case 'PageDown': // NumPad 3
          direction = Direction.SE;
          break;
      }
      
      if (direction !== null) {
        entityDirectionState.setDirection(charSnap.selectedEntityId, direction);
        // Force a re-render
        setInternalRedrawCounter(prev => prev + 1);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mapSnap.isLocked, charSnap.selectedEntityId]);

  // Handle pointer move with corrected calculations - use mapHelpers
  const handlePointerMove = useCallback((event: FederatedPointerEvent) => {
    const startTime = performance.now();
    
    // Skip if we're blocked by a heavy animation
    if (pointerEventsBlocked.current) {
      return;
    }
    
    // Throttle pointer move events for performance
    if (startTime - lastPointerMoveTime.current < 16) { // ~60fps
      return;
    }
    lastPointerMoveTime.current = startTime;
    
    const mousePosition = event.global;
    
    // Use mapHelpers to convert pixel to grid coordinates
    const { gridX, gridY } = mapHelpers.pixelToGrid(mousePosition.x, mousePosition.y);
    
    // Update hover state if within grid bounds
    if (mapHelpers.isValidGridPosition(gridX, gridY)) {
      setHoveredCell({ x: gridX, y: gridY });
    } else {
      setHoveredCell({ x: -1, y: -1 });
    }
    
    // Track performance
    const processingTime = performance.now() - startTime;
    pointerMoveTimes.current.push(processingTime);
    
    // Log if we see excessively slow pointer processing
    if (processingTime > 50) {
      console.warn(`[CANVAS-PERF] Slow pointer move processing: ${processingTime.toFixed(2)}ms`);
    }
  }, []);

  // Handle pointer down - click on the canvas
  const handlePointerDown = useCallback(async (e: FederatedPointerEvent) => {
    const now = performance.now();
    if (pointerEventsBlocked.current) return;
    
    // Log only primary pointer downs (not right clicks)
    if (e.button === 0) {
      console.log(`[CANVAS-PERF] Pointer down at ${now.toFixed(2)}ms, button: ${e.button}`);
    }
    
    // Quick emergency entity state check
    const entityCount = Object.keys(characterStore.summaries).length;
    if (entityCount === 0 && entityCountRef.current > 0) {
      console.warn(`[CANVAS-SYNC] Possible stale entity state detected - had ${entityCountRef.current} entities, now has 0`);
      // Trigger an emergency refresh to avoid using stale data
      try {
        await characterActions.forceRefresh();
      } catch (err) {
        console.error('[CANVAS-SYNC] Emergency refresh failed:', err);
        return; // Prevent action with stale data
      }
    }
    
    const mousePosition = e.global;
    
    // Use mapHelpers to convert pixel to grid coordinates
    const { gridX, gridY } = mapHelpers.pixelToGrid(mousePosition.x, mousePosition.y);
    
    // Update hovered cell
    setHoveredCell({ x: gridX, y: gridY });
    
    // Handle grid clicks
    if (mapHelpers.isValidGridPosition(gridX, gridY)) {
      // Handle left click for tile editing
      if (e.button === 0 && isEditing && !mapSnap.isLocked && onCellClick) {
        const clickStartTime = performance.now();
        onCellClick(gridX, gridY, (newTile: TileSummary) => {
          console.log(`[CANVAS-PERF] Tile edit completed in ${(performance.now() - clickStartTime).toFixed(2)}ms`);
          characterActions.fetchTiles(); // Refresh tiles after update
        });
      } else if (e.button === 0 && !mapSnap.isLocked && onEntityClick) {
        // Check if there's an entity at the clicked position
        const entitySearchStart = performance.now();
        
        // Get entities directly from characterStore to avoid stale snapshot data
        const entitiesAtPosition = Object.values(characterStore.summaries).filter(entity => 
          entity.position[0] === gridX && entity.position[1] === gridY
        );

        console.log(`[CANVAS-PERF] Entity search took ${(performance.now() - entitySearchStart).toFixed(2)}ms, found: ${entitiesAtPosition.length}`);
        
        if (entitiesAtPosition.length > 0) {
          const targetEntity = entitiesAtPosition[0];
          console.log(`[CANVAS-PERF] Attack click on entity ${targetEntity.uuid} at ${performance.now().toFixed(2)}ms`);
          
          const currentSelected = characterStore.selectedEntityId;
          
          // If no entity is selected or clicking on the same entity, just select it
          if (!currentSelected || currentSelected === targetEntity.uuid) {
            console.log(`[ENTITY-TARGET] Selecting entity: ${targetEntity.uuid}`);
            await characterActions.setSelectedEntity(targetEntity.uuid);
            characterActions.setDisplayedEntity(targetEntity.uuid);
            return;
          }
          
          // We have a selected entity different from the target - this is an attack
          console.log(`[ENTITY-TARGET] Attacking: source=${currentSelected}, target=${targetEntity.uuid}`);
          
          // First ensure the displayed entity is updated to the target
          characterActions.setDisplayedEntity(targetEntity.uuid);
          
          // Check if the source entity still exists in the store
          const sourceEntity = characterStore.summaries[currentSelected];
          if (!sourceEntity) {
            console.error(`[ENTITY-TARGET] Source entity ${currentSelected} not found in store, forcing refresh`);
            try {
              await characterActions.forceRefresh();
            } catch (err) {
              console.error('[ENTITY-TARGET] Error refreshing state before attack:', err);
              return;
            }
          }
          
          // Execute attack without waiting for refresh completion
          if (onEntityClick) {
            onEntityClick(targetEntity.uuid);
          }
        }
      }
      
      // Handle right click for movement
      if ((e.button as number) === 2 && !mapSnap.isLocked) {
        const selectedEntityId = characterStore.selectedEntityId;
        const selectedEntity = selectedEntityId ? characterStore.summaries[selectedEntityId] : undefined;
        
        if (!selectedEntity) return;
        
        const movementClickTime = performance.now();
        e.preventDefault();
        e.stopPropagation();
        
        // Check if the position is walkable and in bounds
        const isInBounds = gridX >= 0 && 
                         gridY >= 0 && 
                         gridX < mapSnap.gridWidth && 
                         gridY < mapSnap.gridHeight;
        
        // Simple check if there's any tile data for this position
        const tileKey = `${gridX},${gridY}`;
        const hasTile = tileKey in characterStore.tiles;
        
        if (isInBounds) {
          // Move the selected entity
          characterActions.moveEntity(selectedEntity.uuid, [gridX, gridY]);
          console.log(`[CANVAS-PERF] Move entity command sent in ${(performance.now() - movementClickTime).toFixed(2)}ms`);
          
          // Update direction
          const [currentX, currentY] = selectedEntity.position;
          const direction = entityDirectionState.computeDirection(
            [currentX, currentY],
            [gridX, gridY]
          );
          entityDirectionState.setDirection(selectedEntity.uuid, direction);
        }
      }
    }
    
    console.log(`[CANVAS-PERF] Pointer down processing completed in ${(performance.now() - now).toFixed(2)}ms`);
  }, [
    isEditing,
    mapSnap.isLocked,
    onCellClick,
    onEntityClick,
    tiles,
    mapSnap.isMovementHighlightEnabled
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
    mapActions.zoomIn();
  }, []);

  const handleZoomOut = useCallback(() => {
    mapActions.zoomOut();
  }, []);

  const handleResetView = useCallback(() => {
    mapActions.resetView();
  }, []);

  const toggleLock = useCallback(() => {
    mapActions.toggleLock();
    onLockChange?.(mapSnap.isLocked);
  }, [mapSnap.isLocked, onLockChange]);

  // Add debug log for movement highlight toggle
  const handleMovementHighlightToggle = useCallback(() => {
    mapActions.toggleMovementHighlight();
    console.log('Toggling movement highlight:', !mapSnap.isMovementHighlightEnabled);
    if (!mapSnap.isMovementHighlightEnabled && selectedEntity) {
      console.log('Selected entity for movement:', selectedEntity.name);
      console.log('Path data available:', Object.keys(selectedEntity.senses.paths).length);
    }
  }, [mapSnap.isMovementHighlightEnabled, selectedEntity]);

  // Create a memoized map of valid path positions
  const validPathPositions = useMemo(() => {
    if (!selectedEntity || !mapSnap.isMovementHighlightEnabled) return {};
    
    const positions: Record<string, boolean> = {};
    Object.entries(selectedEntity.senses.paths).forEach(([posKey, path]) => {
      if (path && path.length <= 6) {
        positions[posKey] = true;
      }
    });
    return positions;
  }, [selectedEntity, mapSnap.isMovementHighlightEnabled]);

  // Fix references to tileSize to use mapSnap.tileSize instead
  const drawPathHighlight = useCallback((g: PixiGraphics, position: readonly [number, number]) => {
    const offsetX = (canvasSize.width - (gridWidth * mapSnap.tileSize)) / 2;
    const offsetY = (canvasSize.height - (gridHeight * mapSnap.tileSize)) / 2;
    const posKey = `${position[0]},${position[1]}`;
    
    g.clear();
    g.setFillStyle({
      color: validPathPositions[posKey] ? 0x00ff00 : 0xff0000,
      alpha: validPathPositions[posKey] ? 0.3 : 0.3  // Reduced alpha values
    });
    g.rect(
      offsetX + (position[0] * mapSnap.tileSize),
      offsetY + (position[1] * mapSnap.tileSize),
      mapSnap.tileSize,
      mapSnap.tileSize
    );
    g.fill();
  }, [canvasSize.width, canvasSize.height, gridWidth, gridHeight, mapSnap.tileSize, validPathPositions]);

  // Add memoization for entity directions to avoid recalculations
  const entityDirections = useMemo(() => {
    const directions: Record<string, Direction> = {};
    
    entities.forEach(entity => {
      // Get direction from state first
      let direction = entityDirectionState.getDirection(entity.uuid);
      
      // Only update direction based on target if there's no keyboard-set direction
      if (entity.target_entity_uuid && charSnap.summaries[entity.target_entity_uuid] && 
          !entityDirectionState.directions[entity.uuid]) {
        const targetEntity = charSnap.summaries[entity.target_entity_uuid];
        direction = entityDirectionState.computeDirection(
          [entity.position[0], entity.position[1]],
          [targetEntity.position[0], targetEntity.position[1]]
        );
        // We don't call setDirection here to avoid state changes during render
        directions[entity.uuid] = direction;
      } else {
        directions[entity.uuid] = direction;
      }
    });
    
    return directions;
  }, [entities, charSnap.summaries]);

  // Add this utility function for performance monitoring
  const reportMapPerformance = useCallback(() => {
    console.log(`[CANVAS-PERF] Map Performance Report - ${new Date().toISOString()}`);
    console.log(`- Grid Size: ${mapSnap.gridWidth}x${mapSnap.gridHeight}`);
    console.log(`- Container Size: ${mapSnap.containerWidth}x${mapSnap.containerHeight}`);
    console.log(`- Tile Size: ${mapSnap.tileSize}`);
    console.log(`- Entities Count: ${Object.keys(charSnap.summaries).length}`);
    console.log(`- Tiles Count: ${Object.keys(charSnap.tiles).length}`);
    console.log(`- Grid Offset: (${mapSnap.gridOffsetX}, ${mapSnap.gridOffsetY})`);
  }, [
    mapSnap.gridWidth, 
    mapSnap.gridHeight, 
    mapSnap.containerWidth,
    mapSnap.containerHeight,
    mapSnap.tileSize,
    mapSnap.gridOffsetX,
    mapSnap.gridOffsetY,
    charSnap.summaries,
    charSnap.tiles
  ]);

  // Add periodic performance reporting
  useEffect(() => {
    const interval = setInterval(reportMapPerformance, 30000);
    return () => clearInterval(interval);
  }, [reportMapPerformance]);

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
            {mapSnap.isLocked ? <LockIcon /> : <LockOpenIcon />}
          </IconButton>

          {/* Grid Toggle */}
          <Tooltip title="Toggle Grid">
            <IconButton
              size="small"
              onClick={() => mapActions.toggleGrid()}
              sx={{ color: 'white' }}
            >
              {mapSnap.isGridEnabled ? <GridOnIcon /> : <GridOffIcon />}
            </IconButton>
          </Tooltip>

          {/* Visibility Toggle */}
          <Tooltip title={getVisibilityTooltip()}>
            <span>
              <IconButton
                size="small"
                onClick={() => mapActions.toggleVisibility()}
                sx={{ 
                  color: 'white',
                  opacity: selectedEntity ? 1 : 0.5
                }}
                disabled={!selectedEntity}
              >
                {mapSnap.isVisibilityEnabled ? <VisibilityIcon /> : <VisibilityOffIcon />}
              </IconButton>
            </span>
          </Tooltip>

          {/* Movement Range Toggle */}
          <Tooltip title={getMovementTooltip()}>
            <span>
              <IconButton
                size="small"
                onClick={handleMovementHighlightToggle}
                sx={{ 
                  color: 'white',
                  opacity: selectedEntity ? 1 : 0.5,
                  backgroundColor: mapSnap.isMovementHighlightEnabled ? 'rgba(255, 255, 255, 0.1)' : 'transparent'
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
            {/* Background */}
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
            
            {/* WASD Grid Movement Container - applies WASD offset to all children */}
            {/* This is the ONLY place where gridOffsetX/Y should be applied */}
            <pixiContainer x={mapSnap.gridOffsetX} y={mapSnap.gridOffsetY}>
              {/* Grid Lines */}
              {mapSnap.isGridEnabled && (
                <Grid 
                  width={canvasSize.width}
                  height={canvasSize.height}
                  gridSize={{ rows: gridHeight, cols: gridWidth }}
                  tileSize={mapSnap.tileSize}
                />
              )}
              
              {/* Tiles Layer */}
              <pixiContainer>
              {Object.values(tiles).map(tile => {
                // Skip visibility checks if toggle is off
                  if (!mapSnap.isVisibilityEnabled) {
                  return (
                    <React.Fragment key={tile.uuid}>
                      <TileSprite
                        tile={tile}
                        width={canvasSize.width}
                        height={canvasSize.height}
                        gridSize={{ rows: gridHeight, cols: gridWidth }}
                          tileSize={mapSnap.tileSize}
                      />
                        {mapSnap.isMovementHighlightEnabled && (
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

                  const offsetX = (canvasSize.width - (gridWidth * mapSnap.tileSize)) / 2;
                  const offsetY = (canvasSize.height - (gridHeight * mapSnap.tileSize)) / 2;

                return (
                  <React.Fragment key={tile.uuid}>
                    <TileSprite
                      tile={tile}
                      width={canvasSize.width}
                      height={canvasSize.height}
                      gridSize={{ rows: gridHeight, cols: gridWidth }}
                        tileSize={mapSnap.tileSize}
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
                              offsetX + (x * mapSnap.tileSize),
                              offsetY + (y * mapSnap.tileSize),
                              mapSnap.tileSize,
                              mapSnap.tileSize
                          );
                          g.fill();
                        }}
                      />
                    )}
                      {mapSnap.isMovementHighlightEnabled && isVisible && (
                      <pixiGraphics
                        draw={(g) => drawPathHighlight(g, tile.position)}
                      />
                    )}
                  </React.Fragment>
                );
              })}
              </pixiContainer>

              {/* Movement Highlights Layer */}
              {mapSnap.isMovementHighlightEnabled && (
                <pixiContainer>
                  {Object.values(tiles).map(tile => {
                    if (mapSnap.isVisibilityEnabled && selectedEntity) {
                      const [x, y] = tile.position;
                      const posKey = `${x},${y}`;
                      const isVisible = selectedEntity.senses.visible[posKey];
                      if (!isVisible) return null;
                    }
                    return (
                      <pixiGraphics
                        key={tile.uuid}
                        draw={(g) => drawPathHighlight(g, tile.position)}
                      />
                    );
                  })}
                </pixiContainer>
              )}
              
              {/* Entities Layer */}
              <pixiContainer>
              {entities.map(entity => {
                // Show all entities if visibility is disabled
                  if (!mapSnap.isVisibilityEnabled) {
                    // Get direction from state first
                    let direction = entityDirectionState.getDirection(entity.uuid);
                    
                    // Only update direction based on target if there's no keyboard-set direction
                    if (entity.target_entity_uuid && charSnap.summaries[entity.target_entity_uuid] && 
                        !entityDirectionState.directions[entity.uuid]) {
                      const targetEntity = charSnap.summaries[entity.target_entity_uuid];
                      direction = entityDirectionState.computeDirection(
                        [entity.position[0], entity.position[1]],
                        [targetEntity.position[0], targetEntity.position[1]]
                      );
                      entityDirectionState.setDirection(entity.uuid, direction);
                    }
                    
                  return (
                      <DirectionalEntitySprite
                      key={entity.uuid}
                      entity={entity}
                        direction={direction}
                        selected={entity.uuid === charSnap.selectedEntityId}
                    />
                  );
                }

                // With visibility enabled, only show visible entities
                if (!selectedEntity) return null;
                const isVisible = entity.uuid === selectedEntity.uuid ||
                  selectedEntity.senses.entities[entity.uuid];
                
                if (!isVisible) return null;
                  
                  // Get direction from state first
                  let direction = entityDirectionState.getDirection(entity.uuid);
                  
                  // Only update direction based on target if there's no keyboard-set direction
                  if (entity.target_entity_uuid && charSnap.summaries[entity.target_entity_uuid] && 
                      !entityDirectionState.directions[entity.uuid]) {
                    const targetEntity = charSnap.summaries[entity.target_entity_uuid];
                    direction = entityDirectionState.computeDirection(
                      [entity.position[0], entity.position[1]],
                      [targetEntity.position[0], targetEntity.position[1]]
                    );
                    entityDirectionState.setDirection(entity.uuid, direction);
                  }

                return (
                    <DirectionalEntitySprite
                    key={entity.uuid}
                    entity={entity}
                      direction={entityDirections[entity.uuid]}
                      selected={entity.uuid === charSnap.selectedEntityId}
                  />
                );
              })}
              </pixiContainer>
              
              {/* Cell Highlight Layer */}
              {mapSnap.isGridEnabled && (
                <CellHighlight 
                  x={hoveredCell.x}
                  y={hoveredCell.y}
                  width={canvasSize.width}
                  height={canvasSize.height}
                  gridSize={{ rows: gridHeight, cols: gridWidth }}
                  tileSize={mapSnap.tileSize}
                />
              )}
              
              {/* Attack Animation Layer - use animation store to render active animations */}
              {Object.entries(attackAnimationsRef.current).map(([key, anim]) => (
                <AttackAnimation
                  key={key}
                  isHit={anim.isHit}
                  sourceEntityId={anim.sourceId}
                  targetEntityId={anim.targetId}
                />
              ))}
            </pixiContainer>
          </pixiContainer>
        </Application>
      </div>
    </div>
  );
};

export default React.memo(BattleMapCanvas, (prevProps, nextProps) => {
  // Only re-render if these specific props change
  return (
    prevProps.width === nextProps.width &&
    prevProps.height === nextProps.height &&
    prevProps.tileSize === nextProps.tileSize &&
    prevProps.containerWidth === nextProps.containerWidth &&
    prevProps.containerHeight === nextProps.containerHeight &&
    prevProps.isLocked === nextProps.isLocked &&
    prevProps.isEditing === nextProps.isEditing &&
    prevProps.redrawCounter === nextProps.redrawCounter
  );
}); 