import { useSnapshot } from 'valtio';
import { useCallback, useMemo } from 'react';
import { battlemapStore, battlemapActions } from '../../store';
import { EntitySummary } from '../../models/character';
import { TileSummary } from '../../api/tileApi';

/**
 * Hook for managing visibility and fog of war on the battlemap
 */
export const useVisibility = () => {
  const snap = useSnapshot(battlemapStore);

  // Toggle visibility mode on/off
  const toggleVisibility = useCallback(() => {
    battlemapActions.setVisibilityEnabled(!snap.controls.isVisibilityEnabled);
  }, [snap.controls.isVisibilityEnabled]);

  // Get the currently selected entity for visibility checks
  const selectedEntity = useMemo(() => {
    if (!snap.entities.selectedEntityId) return null;
    return snap.entities.summaries[snap.entities.selectedEntityId];
  }, [snap.entities.selectedEntityId, snap.entities.summaries]);

  /**
   * Check if a specific tile is visible to the selected entity
   */
  const isTileVisible = useCallback((tilePosition: [number, number]): boolean => {
    // If visibility is disabled, everything is visible
    if (!snap.controls.isVisibilityEnabled) return true;

    // Need a selected entity to check visibility
    if (!selectedEntity) return false;

    const [x, y] = tilePosition;
    const posKey = `${x},${y}`;
    
    // Check if the position is in the entity's visible area
    return !!selectedEntity.senses.visible[posKey];
  }, [snap.controls.isVisibilityEnabled, selectedEntity]);

  /**
   * Check if a specific tile has been seen before (but may not be currently visible)
   */
  const isTileSeen = useCallback((tilePosition: [number, number]): boolean => {
    // If visibility is disabled, everything is considered seen
    if (!snap.controls.isVisibilityEnabled) return true;

    // Need a selected entity to check visibility
    if (!selectedEntity) return false;

    const [x, y] = tilePosition;
    
    // Check if the position is in the entity's seen list
    return selectedEntity.senses.seen.some(
      ([seenX, seenY]) => seenX === x && seenY === y
    );
  }, [snap.controls.isVisibilityEnabled, selectedEntity]);

  /**
   * Check if an entity is visible to the selected entity
   */
  const isEntityVisible = useCallback((entityId: string): boolean => {
    // If visibility is disabled, all entities are visible
    if (!snap.controls.isVisibilityEnabled) return true;

    // The selected entity is always visible to itself
    if (entityId === snap.entities.selectedEntityId) return true;

    // Need a selected entity to check visibility
    if (!selectedEntity) return false;
    
    // Check if the entity is in the visible entities list
    return !!selectedEntity.senses.entities[entityId];
  }, [snap.controls.isVisibilityEnabled, snap.entities.selectedEntityId, selectedEntity]);

  /**
   * Get display properties for a tile based on visibility
   */
  const getTileVisibilityProps = useCallback((tile: TileSummary): { alpha: number, fogAlpha: number } => {
    const [x, y] = tile.position;
    const visible = isTileVisible([x, y]);
    const seen = isTileSeen([x, y]);

    if (visible) {
      // Fully visible tile
      return { alpha: 1, fogAlpha: 0 };
    } else if (seen) {
      // Previously seen but not currently visible (fog of war)
      return { alpha: 0.7, fogAlpha: 0.5 };
    } else {
      // Never seen (completely hidden)
      return { alpha: 0, fogAlpha: 0 };
    }
  }, [isTileVisible, isTileSeen]);

  /**
   * Determine if a position is within valid movement range
   */
  const isInMovementRange = useCallback((position: [number, number]): boolean => {
    if (!snap.controls.isMovementHighlightEnabled || !selectedEntity) return false;
    
    const [x, y] = position;
    const posKey = `${x},${y}`;
    const path = selectedEntity.senses.paths[posKey];
    
    // Only consider positions with paths of length <= 6 to be in movement range
    return !!path && path.length <= 6;
  }, [snap.controls.isMovementHighlightEnabled, selectedEntity]);

  // Toggle movement highlighting
  const toggleMovementHighlight = useCallback(() => {
    battlemapActions.setMovementHighlightEnabled(!snap.controls.isMovementHighlightEnabled);
  }, [snap.controls.isMovementHighlightEnabled]);

  /**
   * Get tooltip text for the visibility button
   */
  const getVisibilityTooltip = useCallback((): string => {
    if (!selectedEntity) return "Select an entity to toggle visibility";
    
    const sensesList = selectedEntity.senses.extra_senses.length > 0 
      ? `\nSenses: ${selectedEntity.senses.extra_senses.join(', ')}`
      : '';
      
    return `Toggle visibility for ${selectedEntity.name}${sensesList}`;
  }, [selectedEntity]);

  /**
   * Get tooltip text for the movement range button
   */
  const getMovementTooltip = useCallback((): string => {
    if (!selectedEntity) return "Select an entity to show movement range";
    return `Show movement range for ${selectedEntity.name}\nGreen: ≤30ft (6 squares)\nRed: >30ft`;
  }, [selectedEntity]);

  return {
    isVisibilityEnabled: snap.controls.isVisibilityEnabled,
    isMovementHighlightEnabled: snap.controls.isMovementHighlightEnabled,
    toggleVisibility,
    toggleMovementHighlight,
    isTileVisible,
    isTileSeen,
    isEntityVisible,
    getTileVisibilityProps,
    isInMovementRange,
    getVisibilityTooltip,
    getMovementTooltip
  };
}; 