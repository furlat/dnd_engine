import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';

// Constants for zoom
const MIN_TILE_SIZE = 8;  // Keep same minimum (allows zooming out to current minimal scale)
const MAX_TILE_SIZE = 512; // Increase maximum to 4x the previous max (128 * 4 = 512)
const TILE_SIZE_STEP = 16;

/**
 * Hook for managing the battlemap UI controls and settings
 * Note: WASD movement is now handled by MovementController in the PixiJS layer
 */
export const useMapControls = () => {
  const snap = useSnapshot(battlemapStore);
  
  /**
   * Zoom in (increase tile size)
   */
  const zoomIn = useCallback(() => {
    const currentSize = snap.view.tileSize;
    const newSize = Math.min(currentSize + TILE_SIZE_STEP, MAX_TILE_SIZE);
    battlemapActions.setTileSize(newSize);
  }, [snap.view.tileSize]);
  
  /**
   * Zoom out (decrease tile size)
   */
  const zoomOut = useCallback(() => {
    const currentSize = snap.view.tileSize;
    const newSize = Math.max(currentSize - TILE_SIZE_STEP, MIN_TILE_SIZE);
    battlemapActions.setTileSize(newSize);
  }, [snap.view.tileSize]);
  
  /**
   * Reset view to default (reset zoom and offset)
   */
  const resetView = useCallback(() => {
    battlemapActions.setTileSize(128); // 4x the previous default (32 * 4 = 128)
    battlemapActions.setOffset(0, 0);
  }, []);
  
  /**
   * Lock/unlock the map (affects movement and editing)
   */
  const setLocked = useCallback((locked: boolean) => {
    battlemapActions.setLocked(locked);
    
    // If locking, also close the tile editor
    if (locked && snap.controls.isEditing) {
      console.log('[MapControls] Map locked, closing tile editor');
      battlemapActions.setTileEditing(false);
      battlemapActions.setTileEditorVisible(false);
    }
  }, [snap.controls.isEditing]);
  
  /**
   * Toggle lock state
   */
  const toggleLock = useCallback(() => {
    const newLocked = !snap.controls.isLocked;
    setLocked(newLocked);
  }, [snap.controls.isLocked, setLocked]);
  
  /**
   * Set grid visibility
   */
  const setGridVisible = useCallback((visible: boolean) => {
    battlemapActions.setGridVisible(visible);
  }, []);
  
  /**
   * Toggle grid visibility
   */
  const toggleGridVisibility = useCallback(() => {
    battlemapActions.setGridVisible(!snap.controls.isGridVisible);
  }, [snap.controls.isGridVisible]);
  
  /**
   * Set tiles visibility
   */
  const setTilesVisible = useCallback((visible: boolean) => {
    battlemapActions.setTilesVisible(visible);
  }, []);
  
  /**
   * Toggle tiles visibility
   */
  const toggleTilesVisibility = useCallback(() => {
    battlemapActions.setTilesVisible(!snap.controls.isTilesVisible);
  }, [snap.controls.isTilesVisible]);
  
  /**
   * Set visibility mode
   */
  const setVisibilityEnabled = useCallback((enabled: boolean) => {
    battlemapActions.setVisibilityEnabled(enabled);
  }, []);
  
  /**
   * Toggle visibility mode
   */
  const toggleVisibilityMode = useCallback(() => {
    battlemapActions.setVisibilityEnabled(!snap.controls.isVisibilityEnabled);
  }, [snap.controls.isVisibilityEnabled]);
  
  /**
   * Set movement highlight mode
   */
  const setMovementHighlightEnabled = useCallback((enabled: boolean) => {
    battlemapActions.setMovementHighlightEnabled(enabled);
  }, []);
  
  /**
   * Toggle movement highlight
   */
  const toggleMovementHighlight = useCallback(() => {
    battlemapActions.setMovementHighlightEnabled(!snap.controls.isMovementHighlightEnabled);
  }, [snap.controls.isMovementHighlightEnabled]);
  
  /**
   * Toggle music player size
   */
  const toggleMusicPlayerSize = useCallback(() => {
    battlemapActions.setMusicPlayerMinimized(!snap.controls.isMusicPlayerMinimized);
  }, [snap.controls.isMusicPlayerMinimized]);
  
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
    isWasdMoving: snap.view.wasd_moving, // Still exposed for UI feedback
    
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