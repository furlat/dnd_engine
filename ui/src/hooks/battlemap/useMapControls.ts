import { useCallback, useEffect } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';

// Constants for zoom and pan
const MIN_TILE_SIZE = 8;
const MAX_TILE_SIZE = 128;
const TILE_SIZE_STEP = 16;
const MOVEMENT_SPEED = 8;

/**
 * Hook for managing the battlemap UI controls and settings
 */
export const useMapControls = () => {
  const snap = useSnapshot(battlemapStore);
  
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
   * Pan the map view
   */
  const panView = useCallback((deltaX: number, deltaY: number) => {
    battlemapActions.setOffset(
      snap.view.offset.x + deltaX,
      snap.view.offset.y + deltaY
    );
  }, [snap.view.offset.x, snap.view.offset.y]);
  
  // Lock/unlock the map
  const setLocked = useCallback((locked: boolean) => {
    battlemapActions.setLocked(locked);
  }, []);
  
  // Toggle lock state
  const toggleLock = useCallback(() => {
    battlemapActions.setLocked(!snap.controls.isLocked);
  }, [snap.controls.isLocked]);
  
  // Set grid visibility
  const setGridVisible = useCallback((visible: boolean) => {
    battlemapActions.setGridVisible(visible);
  }, []);
  
  // Toggle grid visibility
  const toggleGridVisibility = useCallback(() => {
    battlemapActions.setGridVisible(!snap.controls.isGridVisible);
  }, [snap.controls.isGridVisible]);
  
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
      switch (e.key.toLowerCase()) {
        case 'w':
          panView(0, MOVEMENT_SPEED);
          break;
        case 's':
          panView(0, -MOVEMENT_SPEED);
          break;
        case 'a':
          panView(MOVEMENT_SPEED, 0);
          break;
        case 'd':
          panView(-MOVEMENT_SPEED, 0);
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [snap.controls.isLocked, panView]);
  
  return {
    // Current state
    tileSize: snap.view.tileSize,
    offset: snap.view.offset,
    isLocked: snap.controls.isLocked,
    isGridVisible: snap.controls.isGridVisible,
    isVisibilityEnabled: snap.controls.isVisibilityEnabled,
    isMovementHighlightEnabled: snap.controls.isMovementHighlightEnabled,
    isMusicPlayerMinimized: snap.controls.isMusicPlayerMinimized,
    
    // Methods
    zoomIn,
    zoomOut,
    resetView,
    panView,
    setLocked,
    toggleLock,
    setGridVisible,
    toggleGridVisibility,
    setVisibilityEnabled,
    toggleVisibilityMode,
    setMovementHighlightEnabled,
    toggleMovementHighlight,
    toggleMusicPlayerSize
  };
}; 