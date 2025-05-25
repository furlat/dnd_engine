import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { AnimationState, Direction, SpriteFolderName } from '../../types/battlemap_types';

/**
 * Hook for managing sprite assignment and editing functionality
 */
export const useSpriteEditor = () => {
  const snap = useSnapshot(battlemapStore);
  
  const selectedEntityId = snap.entities.selectedEntityId;
  const selectedEntity = selectedEntityId ? snap.entities.summaries[selectedEntityId] : undefined;
  const isEditing = snap.controls.isEditing;
  const availableSpriteFolders = snap.entities.availableSpriteFolders;
  
  // Get current sprite mapping for selected entity
  const spriteMapping = selectedEntityId ? snap.entities.spriteMappings[selectedEntityId] : undefined;
  const hasAssignedSprite = Boolean(spriteMapping);
  const assignedSpriteFolder = spriteMapping?.spriteFolder;
  const currentAnimation = spriteMapping?.currentAnimation || AnimationState.IDLE;
  const currentDirection = spriteMapping?.currentDirection || Direction.S;
  const currentScale = spriteMapping?.scale || 1.0;
  const currentAnimationDuration = spriteMapping?.animationDurationSeconds || 1.0;
  
  // Assign sprite to selected entity
  const assignSpriteToSelectedEntity = useCallback((spriteFolder: SpriteFolderName) => {
    if (selectedEntityId) {
      console.log(`[useSpriteEditor] Assigning sprite ${spriteFolder} to entity ${selectedEntityId}`);
      battlemapActions.setEntitySpriteMapping(selectedEntityId, spriteFolder);
    }
  }, [selectedEntityId]);
  
  // Remove sprite from selected entity
  const removeSpriteFromSelectedEntity = useCallback(() => {
    if (selectedEntityId) {
      console.log(`[useSpriteEditor] Removing sprite from entity ${selectedEntityId}`);
      battlemapActions.removeEntitySpriteMapping(selectedEntityId);
    }
  }, [selectedEntityId]);
  
  // Set animation state for selected entity
  const setSelectedEntityAnimation = useCallback((animation: AnimationState) => {
    if (selectedEntityId) {
      console.log(`[useSpriteEditor] Setting animation ${animation} for entity ${selectedEntityId}`);
      battlemapActions.setEntityAnimation(selectedEntityId, animation);
    }
  }, [selectedEntityId]);
  
  // Set direction for selected entity
  const setSelectedEntityDirection = useCallback((direction: Direction) => {
    if (selectedEntityId) {
      console.log(`[useSpriteEditor] Setting direction ${direction} for entity ${selectedEntityId}`);
      battlemapActions.setEntityDirectionFromMapping(selectedEntityId, direction);
    }
  }, [selectedEntityId]);
  
  // Set scale for selected entity
  const setSelectedEntityScale = useCallback((scale: number) => {
    if (selectedEntityId) {
      console.log(`[useSpriteEditor] Setting scale ${scale} for entity ${selectedEntityId}`);
      battlemapActions.setEntitySpriteScale(selectedEntityId, scale);
    }
  }, [selectedEntityId]);
  
  // Set animation duration for selected entity
  const setSelectedEntityAnimationDuration = useCallback((durationSeconds: number) => {
    if (selectedEntityId) {
      console.log(`[useSpriteEditor] Setting animation duration ${durationSeconds}s for entity ${selectedEntityId}`);
      battlemapActions.setEntityAnimationDuration(selectedEntityId, durationSeconds);
    }
  }, [selectedEntityId]);
  
  return {
    // State
    isEditing,
    selectedEntity,
    selectedEntityId,
    availableSpriteFolders,
    hasAssignedSprite,
    assignedSpriteFolder,
    currentAnimation,
    currentDirection,
    currentScale,
    currentAnimationDuration,
    
    // Actions
    assignSpriteToSelectedEntity,
    removeSpriteFromSelectedEntity,
    setSelectedEntityAnimation,
    setSelectedEntityDirection,
    setSelectedEntityScale,
    setSelectedEntityAnimationDuration,
  };
}; 