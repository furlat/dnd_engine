import { proxy } from 'valtio';
import type { Character, EntitySummary } from '../models/character';
import type { ReadonlyCharacter, ReadonlyEntitySummary, DeepReadonly } from '../models/readonly';
import { fetchCharacter, fetchEntitySummaries } from '../api/characterApi';
import { fetchGridSnapshot, TileSummary } from '../api/tileApi';

// Base state interface without readonly modifiers for the store
export interface CharacterStoreState {
  character: Character | null;
  loading: boolean;
  error: string | null;
  summaries: Record<string, EntitySummary>;
  selectedEntityId: string | undefined;
  displayedEntityId: string | undefined;
  tiles: Record<string, TileSummary>;
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
  tiles: {}
});

// Polling configuration
const POLLING_INTERVAL = 200; // Match previous 200ms rate for responsive updates
let pollingSummariesInterval: NodeJS.Timeout | null = null;

// Actions to mutate the store
const characterActions = {
  setLoading: (loading: boolean) => {
    characterStore.loading = loading;
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
    // If we're selecting the currently selected entity, clear the selection
    if (characterStore.selectedEntityId === entityId) {
      characterStore.selectedEntityId = undefined;
      if (characterStore.character) {
        characterStore.character.target_entity_uuid = undefined;
      }
    } else {
      // Set new selection
      characterStore.selectedEntityId = entityId;
      if (characterStore.character) {
        characterStore.character.target_entity_uuid = entityId;
      }
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
  
  // Start polling for entity summaries and tiles
  startPolling: () => {
    if (pollingSummariesInterval) {
      clearInterval(pollingSummariesInterval);
    }

    // Immediately fetch data
    Promise.all([
      characterActions.fetchSummaries(),
      characterActions.fetchTiles()
    ]);

    // Set up polling interval
    pollingSummariesInterval = setInterval(async () => {
      await Promise.all([
        characterActions.fetchSummaries(),
        characterActions.fetchTiles()
      ]);
    }, POLLING_INTERVAL);
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
      const summariesData = await fetchEntitySummaries();
      
      // Convert array to record while preserving existing data for smooth updates
      const summariesRecord = summariesData.reduce((acc, summary) => {
        // Preserve existing data for smooth transitions
        const existingSummary = characterStore.summaries[summary.uuid];
        if (existingSummary) {
          // Only update if data has changed
          if (JSON.stringify(existingSummary) !== JSON.stringify(summary)) {
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

  // Move entity to a new position
  moveEntity: async (entityId: string, position: [number, number]) => {
    try {
      // Optimistically update the position
      const entity = characterStore.summaries[entityId];
      if (entity) {
        const updatedEntity = { ...entity, position };
        characterStore.summaries = {
          ...characterStore.summaries,
          [entityId]: updatedEntity
        };
      }

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
  }
};

// Export both store and actions
export { characterStore, characterActions }; 