import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { AnimationState, Direction, SpriteFolderName, MovementState } from '../../types/battlemap_types';

/**
 * Hook for managing sprite assignment and editing functionality
 * Note: This controls the "idle animation" - the default animation when not moving/acting
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
  
  // Use idle animation for editor controls (this is what user sets as default)
  const currentAnimation = spriteMapping?.idleAnimation || AnimationState.IDLE;
  const currentDirection = spriteMapping?.currentDirection || Direction.S;
  const currentScale = spriteMapping?.scale || 1.0;
  const currentAnimationDuration = spriteMapping?.animationDurationSeconds || 1.0;
  
  // Additional state info
  const movementState = spriteMapping?.movementState || MovementState.IDLE;
  const isPositionSynced = spriteMapping?.isPositionSynced ?? true;
  const actualCurrentAnimation = spriteMapping?.currentAnimation || AnimationState.IDLE;
  
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
  
  // Set IDLE animation state for selected entity (this is what the editor controls)
  const setSelectedEntityAnimation = useCallback((animation: AnimationState) => {
    if (selectedEntityId) {
      console.log(`[useSpriteEditor] Setting idle animation ${animation} for entity ${selectedEntityId}`);
      battlemapActions.setEntityIdleAnimation(selectedEntityId, animation);
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
    
    // Animation state (idle animation - what user controls)
    currentAnimation, // This is the idle animation
    currentDirection,
    currentScale,
    currentAnimationDuration,
    
    // Additional state info
    movementState,
    isPositionSynced,
    actualCurrentAnimation, // What's actually playing (might be WALK during movement)
    
    // Actions
    assignSpriteToSelectedEntity,
    removeSpriteFromSelectedEntity,
    setSelectedEntityAnimation, // Sets idle animation
    setSelectedEntityDirection,
    setSelectedEntityScale,
    setSelectedEntityAnimationDuration,
  };
}; 