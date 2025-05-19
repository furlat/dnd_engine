import { proxy } from 'valtio';
import type { Character, EntitySummary } from '../models/character';
import type { ReadonlyCharacter, ReadonlyEntitySummary, DeepReadonly } from '../models/readonly';
import { fetchCharacter, fetchEntitySummaries } from '../api/characterApi';
import { fetchGridSnapshot, TileSummary } from '../api/tileApi';
import { Direction } from '../components/battlemap/DirectionalEntitySprite';
import { entityDirectionState } from './entityDirectionStore';
import { animationStore } from './animationStore';

// Base state interface without readonly modifiers for the store
export interface CharacterStoreState {
  character: Character | null;
  loading: boolean;
  error: string | null;
  summaries: Record<string, EntitySummary>;
  selectedEntityId: string | undefined;
  displayedEntityId: string | undefined;
  tiles: Record<string, TileSummary>;
  isAnimationActive: boolean;
  lastPollTime: number;
}

// Read-only version for consuming components
export type ReadonlyCharacterStore = DeepReadonly<CharacterStoreState>;

// Initialize the store with default values
const characterStore = proxy<CharacterStoreState>({
  character: null,
  loading: false,
  error: null,
  summaries: {},
  selectedEntityId: undefined,
  displayedEntityId: undefined,
  tiles: {},
  isAnimationActive: false,
  lastPollTime: 0
});

// Polling configuration - increase the base interval for better performance
const BASE_POLLING_INTERVAL = 500; // Reduced from 200ms for better performance
const SLOW_POLLING_INTERVAL = 1000; // Use during animations
let pollingSummariesInterval: NodeJS.Timeout | null = null;

// Actions to mutate the store
const characterActions = {
  setLoading: (loading: boolean) => {
    characterStore.loading = loading;
  },
  
  // Add a force refresh function for critical operations that need fresh data
  forceRefresh: async (): Promise<void> => {
    console.log('[STATE-SYNC] Forcing immediate data refresh before critical action');
    const now = performance.now();
    
    try {
      // Fetch latest summaries and wait for completion
      const summariesData = await fetchEntitySummaries();
      
      // Convert array to record
      const summariesRecord = summariesData.reduce((acc, summary) => {
        acc[summary.uuid] = summary;
        return acc;
      }, {} as Record<string, EntitySummary>);
      
      // Update store with fresh data
      characterStore.summaries = summariesRecord;
      characterStore.lastPollTime = now;
      
      console.log(`[STATE-SYNC] Force refresh completed in ${(performance.now() - now).toFixed(2)}ms`);
    } catch (err) {
      console.error('[STATE-SYNC] Force refresh failed:', err);
      throw err; // Rethrow to let caller handle the error
    }
  },
  
  setError: (error: string | null) => {
    characterStore.error = error;
  },
  
  setCharacter: (character: Character) => {
    characterStore.character = character;
  },
  
  setSummaries: (summaries: Record<string, EntitySummary>) => {
    characterStore.summaries = summaries;
  },

  setSelectedEntity: (entityId: string | undefined) => {
    console.log(`[ENTITY-SELECT] Setting selected entity to ${entityId || 'none'}`);
    
    // If undefined, clear selection
    if (entityId === undefined) {
      characterStore.selectedEntityId = undefined;
      if (characterStore.character) {
        characterStore.character.target_entity_uuid = undefined;
      }
      return;
    }
    
    // Make sure entity exists in summaries
    if (!characterStore.summaries[entityId]) {
      console.error(`[ENTITY-SELECT] Entity ${entityId} not found in summaries`);
      console.log(`[ENTITY-SELECT] Available entities: ${Object.keys(characterStore.summaries).join(', ')}`);
      
      // Try to refresh summaries in case of stale data
      characterActions.fetchSummaries().then(() => {
        // Check again after refresh
        if (characterStore.summaries[entityId]) {
          console.log(`[ENTITY-SELECT] Entity ${entityId} found after refresh, setting as selected`);
          characterStore.selectedEntityId = entityId;
          
          // Update character target only if we have a character
          if (characterStore.character) {
            console.log(`[ENTITY-SELECT] Updating character target to ${entityId}`);
            characterStore.character.target_entity_uuid = entityId;
          }
        } else {
          console.error(`[ENTITY-SELECT] Entity ${entityId} still not found after refresh`);
        }
      }).catch(err => {
        console.error(`[ENTITY-SELECT] Error refreshing summaries:`, err);
      });
      
      return;
    }

    // Set the selected entity
    characterStore.selectedEntityId = entityId;
    
    // Update character target only if we have a character
    if (characterStore.character) {
      console.log(`[ENTITY-SELECT] Updating character target to ${entityId}`);
      characterStore.character.target_entity_uuid = entityId;
    }
  },

  // Set target entity and sync with server
  setTargetEntity: async (sourceEntityId: string, targetEntityId: string): Promise<boolean> => {
    try {
      console.log(`[TARGET-SYNC] Setting target: ${sourceEntityId} -> ${targetEntityId}`);
      
      // First update local state
      characterStore.selectedEntityId = sourceEntityId;
      
      // Get entity from the state
      const sourceEntity = characterStore.summaries[sourceEntityId];
      if (!sourceEntity) {
        console.error(`[TARGET-SYNC] Source entity ${sourceEntityId} not found in state`);
        return false;
      }
      
      // Make sure target exists
      const targetEntity = characterStore.summaries[targetEntityId];
      if (!targetEntity) {
        console.error(`[TARGET-SYNC] Target entity ${targetEntityId} not found in state`);
        return false;
      }
      
      // Sync with server
      const response = await fetch(`/api/entities/${sourceEntityId}/target/${targetEntityId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail?.message || 'Failed to set target on server');
      }
      
      // Force a refresh to get updated data
      await characterActions.fetchSummaries();
      
      console.log(`[TARGET-SYNC] Target set successfully: ${sourceEntityId} -> ${targetEntityId}`);
      return true;
    } catch (error) {
      console.error('[TARGET-SYNC] Error setting target:', error);
      return false;
    }
  },

  setDisplayedEntity: (entityId: string | undefined) => {
    characterStore.displayedEntityId = entityId;
  },

  // Get the currently displayed entity summary
  getDisplayedEntity: (): EntitySummary | undefined => {
    return characterStore.displayedEntityId ? characterStore.summaries[characterStore.displayedEntityId] : undefined;
  },

  // Get the currently selected entity summary
  getSelectedEntity: (): EntitySummary | undefined => {
    return characterStore.selectedEntityId ? characterStore.summaries[characterStore.selectedEntityId] : undefined;
  },
  
  // Fetch character data
  fetchCharacter: async (characterId: string, silent: boolean = false) => {
    if (!silent) {
      characterStore.loading = true;
    }
    
    try {
      const characterData = await fetchCharacter(characterId);
      const summariesData = await fetchEntitySummaries();
      
      // Convert summaries array to record
      const summariesRecord = summariesData.reduce((acc, summary) => {
        acc[summary.uuid] = summary;
        return acc;
      }, {} as Record<string, EntitySummary>);
      
      characterStore.character = characterData;
      characterStore.summaries = summariesRecord;
      characterStore.selectedEntityId = characterData.target_entity_uuid;
      characterStore.error = null;
    } catch (err) {
      console.error('Error fetching character data:', err);
      characterStore.error = err instanceof Error ? err.message : 'Failed to fetch character';
    } finally {
      if (!silent) {
        characterStore.loading = false;
      }
    }
  },
  
  // Start polling for entity summaries and tiles with adaptive interval
  startPolling: () => {
    if (pollingSummariesInterval) {
      clearInterval(pollingSummariesInterval);
    }

    // Immediately fetch data
    Promise.all([
      characterActions.fetchSummaries(),
      characterActions.fetchTiles()
    ]);

    // Set up polling with adaptive interval
    pollingSummariesInterval = setInterval(async () => {
      // Check if there are active animations
      const hasActiveAnimations = Object.keys(animationStore.attackAnimations).length > 0;
      characterStore.isAnimationActive = hasActiveAnimations;
      
      // Calculate time since last poll
      const now = performance.now();
      const timeSinceLastPoll = now - characterStore.lastPollTime;
      
      // During animations, use slower polling (or optionally skip polls)
      if (hasActiveAnimations) {
        // Skip polling if the interval hasn't been reached
        if (timeSinceLastPoll < SLOW_POLLING_INTERVAL) {
          return;
        }
      } else if (timeSinceLastPoll < BASE_POLLING_INTERVAL) {
        // Skip polling if the base interval hasn't been reached
        return;
      }
      
      // Update last poll time
      characterStore.lastPollTime = now;
      
      // Perform the poll
      await Promise.all([
        characterActions.fetchSummaries(),
        // Only fetch tiles during non-animation periods for better performance
        hasActiveAnimations ? Promise.resolve() : characterActions.fetchTiles()
      ]);
    }, Math.min(BASE_POLLING_INTERVAL / 2, 200)); // Check frequently but apply adaptive logic
  },

  // Stop polling
  stopPolling: () => {
    if (pollingSummariesInterval) {
      clearInterval(pollingSummariesInterval);
      pollingSummariesInterval = null;
    }
  },

  // Fetch tiles
  fetchTiles: async () => {
    try {
      const grid = await fetchGridSnapshot();
      characterStore.tiles = grid.tiles;
    } catch (err) {
      console.error('Error fetching tiles:', err);
    }
  },

  // Fetch summaries with optimistic update handling
  fetchSummaries: async () => {
    try {
      // Skip fetching during animations if we've polled recently
      if (characterStore.isAnimationActive && 
          performance.now() - characterStore.lastPollTime < SLOW_POLLING_INTERVAL * 0.75) {
        return;
      }
      
      const summariesData = await fetchEntitySummaries();
      
      // Convert array to record while preserving existing data for smooth updates
      const summariesRecord = summariesData.reduce((acc, summary) => {
        // Preserve existing data for smooth transitions
        const existingSummary = characterStore.summaries[summary.uuid];
        if (existingSummary) {
          // Only update if data has changed to reduce rerenders
          // Use a more efficient comparison by checking only the relevant fields
          if (characterActions.hasEntityChanged(existingSummary, summary)) {
            acc[summary.uuid] = summary;
          } else {
            acc[summary.uuid] = existingSummary;
          }
        } else {
          acc[summary.uuid] = summary;
        }
        return acc;
      }, {} as Record<string, EntitySummary>);

      characterStore.summaries = summariesRecord;
    } catch (err) {
      console.error('Error fetching summaries:', err);
    }
  },
  
  // Helper to efficiently compare entities
  hasEntityChanged: (oldEntity: EntitySummary, newEntity: EntitySummary): boolean => {
    // Only check fields that would affect rendering
    return (
      oldEntity.position[0] !== newEntity.position[0] ||
      oldEntity.position[1] !== newEntity.position[1] ||
      oldEntity.current_hp !== newEntity.current_hp ||
      oldEntity.max_hp !== newEntity.max_hp ||
      oldEntity.target_entity_uuid !== newEntity.target_entity_uuid
    );
  },

  // Move entity to a new position
  moveEntity: async (entityId: string, position: [number, number]) => {
    try {
      // Make API call
      const response = await fetch(`/api/entities/${entityId}/move`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ position }),
      });

      if (!response.ok) {
        throw new Error('Failed to move entity');
      }

      // Update with server response
      const updatedSummary = await response.json();
      characterStore.summaries = {
        ...characterStore.summaries,
        [entityId]: updatedSummary
      };
    } catch (err) {
      console.error('Error moving entity:', err);
      // Refresh summaries to ensure consistent state
      await characterActions.fetchSummaries();
    }
  },

  updateEntityDirection: (entityId: string, direction: Direction) => {
    if (characterStore.selectedEntityId === entityId) {
      entityDirectionState.setDirection(entityId, direction);
    }
  }
};

// Export both store and actions
export { characterStore, characterActions }; 