import { useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { EntitySummary } from '../../models/character';
import { setTargetEntity } from '../../api/battlemap';

/**
 * Hook for entity selection and targeting operations
 */
export const useEntitySelection = () => {
  const snap = useSnapshot(battlemapStore);
  
  /**
   * Get all entities as an array
   */
  const getAllEntities = useCallback((): EntitySummary[] => {
    return Object.values(snap.entities.summaries);
  }, [snap.entities.summaries]);
  
  /**
   * Get entity by ID
   */
  const getEntityById = useCallback((entityId: string): EntitySummary | undefined => {
    return snap.entities.summaries[entityId];
  }, [snap.entities.summaries]);
  
  /**
   * Get entities at a specific position
   */
  const getEntitiesAtPosition = useCallback((x: number, y: number): EntitySummary[] => {
    return getAllEntities().filter(entity => 
      entity.position[0] === x && entity.position[1] === y
    );
  }, [getAllEntities]);
  
  /**
   * Get currently selected entity
   */
  const getSelectedEntity = useCallback((): EntitySummary | undefined => {
    return snap.entities.selectedEntityId 
      ? snap.entities.summaries[snap.entities.selectedEntityId] 
      : undefined;
  }, [snap.entities.selectedEntityId, snap.entities.summaries]);
  
  /**
   * Get currently displayed entity (for character sheet)
   */
  const getDisplayedEntity = useCallback((): EntitySummary | undefined => {
    return snap.entities.displayedEntityId 
      ? snap.entities.summaries[snap.entities.displayedEntityId] 
      : undefined;
  }, [snap.entities.displayedEntityId, snap.entities.summaries]);
  
  /**
   * Select an entity for targeting (or deselect if clicking the same one)
   */
  const selectEntity = useCallback((entityId: string | undefined) => {
    battlemapActions.setSelectedEntity(entityId);
    
    // If an entity is selected, also make it the displayed entity
    if (entityId && entityId !== snap.entities.selectedEntityId) {
      battlemapActions.setDisplayedEntity(entityId);
    }
  }, [snap.entities.selectedEntityId]);
  
  /**
   * Display an entity in the character sheet without selecting for targeting
   */
  const displayEntity = useCallback((entityId: string | undefined) => {
    battlemapActions.setDisplayedEntity(entityId);
  }, []);
  
  /**
   * Set target for the currently selected entity
   */
  const setTarget = useCallback(async (targetId: string | null) => {
    if (!snap.entities.selectedEntityId) return;
    
    try {
      battlemapActions.setLoading(true);
      
      // Call API to set target
      await setTargetEntity(snap.entities.selectedEntityId, targetId);
      
      // Successful targeting - refresh entities
      await battlemapActions.fetchEntitySummaries();
    } catch (error) {
      console.error('Error setting target:', error);
      battlemapActions.setError(error instanceof Error ? error.message : 'Failed to set target');
    } finally {
      battlemapActions.setLoading(false);
    }
  }, [snap.entities.selectedEntityId]);
  
  return {
    // Current state
    selectedEntityId: snap.entities.selectedEntityId,
    displayedEntityId: snap.entities.displayedEntityId,
    entities: snap.entities.summaries,
    
    // Query methods
    getAllEntities,
    getEntityById,
    getEntitiesAtPosition,
    getSelectedEntity,
    getDisplayedEntity,
    
    // Action methods
    selectEntity,
    displayEntity,
    setTarget
  };
}; 