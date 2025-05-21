import { useCallback, useEffect, useRef } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';

// Constants for zoom and pan
const MIN_TILE_SIZE = 8;
const MAX_TILE_SIZE = 128;
const TILE_SIZE_STEP = 16;
const MOVEMENT_SPEED = 20; // Increased for more noticeable movement
const MOVEMENT_END_DELAY = 100; // Time to wait after last keypress before ending movement mode

/**
 * Hook for managing the battlemap UI controls and settings
 */
export const useMapControls = () => {
  const snap = useSnapshot(battlemapStore);
  const movementTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  /**
   * Zoom in (increase tile size)
   */
  const zoomIn = useCallback(() => {
    const currentSize = snap.view.tileSize;
    battlemapActions.setTileSize(Math.min(currentSize + TILE_SIZE_STEP, MAX_TILE_SIZE));
  }, [snap.view.tileSize]);
  
  /**
   * Zoom out (decrease tile size)
   */
  const zoomOut = useCallback(() => {
    const currentSize = snap.view.tileSize;
    battlemapActions.setTileSize(Math.max(currentSize - TILE_SIZE_STEP, MIN_TILE_SIZE));
  }, [snap.view.tileSize]);
  
  /**
   * Reset view to default (reset zoom and offset)
   */
  const resetView = useCallback(() => {
    battlemapActions.setTileSize(32);
    battlemapActions.setOffset(0, 0);
  }, []);
  
  /**
   * Start movement mode - enable wasd_moving flag
   */
  const startMovement = useCallback(() => {
    // Clear any existing timeout
    if (movementTimeoutRef.current) {
      clearTimeout(movementTimeoutRef.current);
      movementTimeoutRef.current = null;
    }
    
    // Set moving flag if not already set
    if (!snap.view.wasd_moving) {
      battlemapActions.setWasdMoving(true);
    }
  }, [snap.view.wasd_moving]);
  
  /**
   * End movement mode after a delay
   */
  const endMovement = useCallback(() => {
    // Clear any existing timeout
    if (movementTimeoutRef.current) {
      clearTimeout(movementTimeoutRef.current);
    }
    
    // Set a new timeout to end movement mode
    movementTimeoutRef.current = setTimeout(() => {
      battlemapActions.setWasdMoving(false);
      movementTimeoutRef.current = null;
    }, MOVEMENT_END_DELAY);
  }, []);
  
  // Lock/unlock the map
  const setLocked = useCallback((locked: boolean) => {
    battlemapActions.setLocked(locked);
    
    // If locking, end movement immediately
    if (locked && snap.view.wasd_moving) {
      if (movementTimeoutRef.current) {
        clearTimeout(movementTimeoutRef.current);
        movementTimeoutRef.current = null;
      }
      battlemapActions.setWasdMoving(false);
    }
  }, [snap.view.wasd_moving]);
  
  // Toggle lock state
  const toggleLock = useCallback(() => {
    const newLocked = !snap.controls.isLocked;
    battlemapActions.setLocked(newLocked);
    
    // If locking, end movement immediately
    if (newLocked && snap.view.wasd_moving) {
      if (movementTimeoutRef.current) {
        clearTimeout(movementTimeoutRef.current);
        movementTimeoutRef.current = null;
      }
      battlemapActions.setWasdMoving(false);
    }
  }, [snap.controls.isLocked, snap.view.wasd_moving]);
  
  // Set grid visibility
  const setGridVisible = useCallback((visible: boolean) => {
    battlemapActions.setGridVisible(visible);
  }, []);
  
  // Toggle grid visibility
  const toggleGridVisibility = useCallback(() => {
    battlemapActions.setGridVisible(!snap.controls.isGridVisible);
  }, [snap.controls.isGridVisible]);
  
  // Set tiles visibility
  const setTilesVisible = useCallback((visible: boolean) => {
    battlemapActions.setTilesVisible(visible);
  }, []);
  
  // Toggle tiles visibility
  const toggleTilesVisibility = useCallback(() => {
    battlemapActions.setTilesVisible(!snap.controls.isTilesVisible);
  }, [snap.controls.isTilesVisible]);
  
  // Set visibility mode
  const setVisibilityEnabled = useCallback((enabled: boolean) => {
    battlemapActions.setVisibilityEnabled(enabled);
  }, []);
  
  // Toggle visibility mode
  const toggleVisibilityMode = useCallback(() => {
    battlemapActions.setVisibilityEnabled(!snap.controls.isVisibilityEnabled);
  }, [snap.controls.isVisibilityEnabled]);
  
  // Set movement highlight mode
  const setMovementHighlightEnabled = useCallback((enabled: boolean) => {
    battlemapActions.setMovementHighlightEnabled(enabled);
  }, []);
  
  // Toggle movement highlight
  const toggleMovementHighlight = useCallback(() => {
    battlemapActions.setMovementHighlightEnabled(!snap.controls.isMovementHighlightEnabled);
  }, [snap.controls.isMovementHighlightEnabled]);
  
  // Toggle music player size
  const toggleMusicPlayerSize = useCallback(() => {
    battlemapActions.setMusicPlayerMinimized(!snap.controls.isMusicPlayerMinimized);
  }, [snap.controls.isMusicPlayerMinimized]);
  
  // Set up WASD keyboard controls for panning
  useEffect(() => {
    if (snap.controls.isLocked) return;
    
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if modifier keys are pressed
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      
      // Mark key as pressed and apply direct movement
      let moved = true;
      
      switch (e.key.toLowerCase()) {
        case 'w':
          // Move up (decrease Y)
          battlemapActions.setOffset(
            snap.view.offset.x, 
            snap.view.offset.y - MOVEMENT_SPEED
          );
          break;
        case 's':
          // Move down (increase Y)
          battlemapActions.setOffset(
            snap.view.offset.x, 
            snap.view.offset.y + MOVEMENT_SPEED
          );
          break;
        case 'a':
          // Move left (decrease X)
          battlemapActions.setOffset(
            snap.view.offset.x - MOVEMENT_SPEED, 
            snap.view.offset.y
          );
          break;
        case 'd':
          // Move right (increase X)
          battlemapActions.setOffset(
            snap.view.offset.x + MOVEMENT_SPEED, 
            snap.view.offset.y
          );
          break;
        default:
          moved = false;
      }
      
      // If we actually moved, handle movement state
      if (moved) {
        startMovement();
      }
    };
    
    const handleKeyUp = (e: KeyboardEvent) => {
      // When a WASD key is released, schedule the end of movement
      if (['w', 'a', 's', 'd'].includes(e.key.toLowerCase())) {
        endMovement();
      }
    };
    
    // Handle window blur - end movement when window loses focus
    const handleBlur = () => {
      if (snap.view.wasd_moving) {
        battlemapActions.setWasdMoving(false);
        if (movementTimeoutRef.current) {
          clearTimeout(movementTimeoutRef.current);
          movementTimeoutRef.current = null;
        }
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
      
      // Clean up timeout if component unmounts
      if (movementTimeoutRef.current) {
        clearTimeout(movementTimeoutRef.current);
      }
    };
  }, [snap.controls.isLocked, snap.view.offset.x, snap.view.offset.y, snap.view.wasd_moving, startMovement, endMovement]);
  
  return {
    // Current state
    tileSize: snap.view.tileSize,
    offset: snap.view.offset,
    isLocked: snap.controls.isLocked,
    isGridVisible: snap.controls.isGridVisible,
    isTilesVisible: snap.controls.isTilesVisible,
    isVisibilityEnabled: snap.controls.isVisibilityEnabled,
    isMovementHighlightEnabled: snap.controls.isMovementHighlightEnabled,
    isMusicPlayerMinimized: snap.controls.isMusicPlayerMinimized,
    isWasdMoving: snap.view.wasd_moving,
    
    // Methods
    zoomIn,
    zoomOut,
    resetView,
    setLocked,
    toggleLock,
    setGridVisible,
    toggleGridVisibility,
    setTilesVisible,
    toggleTilesVisibility,
    setVisibilityEnabled,
    toggleVisibilityMode,
    setMovementHighlightEnabled,
    toggleMovementHighlight,
    toggleMusicPlayerSize
  };
}; 