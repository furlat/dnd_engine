import { proxy } from 'valtio';
import type { Character, EntitySummary } from '../models/character';
import type { ReadonlyCharacter, ReadonlyEntitySummary, DeepReadonly } from '../models/readonly';
import { fetchCharacter, fetchEntitySummaries } from '../api/character_sheet/characterSheetApi';

// Base state interface without readonly modifiers for the store
export interface CharacterSheetStoreState {
  character: Character | null;
  loading: boolean;
  error: string | null;
  summaries: Record<string, EntitySummary>;
  displayedEntityId: string | undefined;
}

// Read-only version for consuming components
export type ReadonlyCharacterSheetStore = DeepReadonly<CharacterSheetStoreState>;

// Initialize the store with default values
const characterSheetStore = proxy<CharacterSheetStoreState>({
  character: null,
  loading: false,
  error: null,
  summaries: {},
  displayedEntityId: undefined
});

// Actions to mutate the store
const characterSheetActions = {
  setLoading: (loading: boolean) => {
    characterSheetStore.loading = loading;
  },
  
  setError: (error: string | null) => {
    characterSheetStore.error = error;
  },
  
  setCharacter: (character: Character) => {
    characterSheetStore.character = character;
  },
  
  setSummaries: (summaries: Record<string, EntitySummary>) => {
    characterSheetStore.summaries = summaries;
  },

  setDisplayedEntity: (entityId: string | undefined) => {
    characterSheetStore.displayedEntityId = entityId;
    // If an entity is selected for display, fetch its full details
    if (entityId) {
      characterSheetActions.fetchCharacter(entityId);
    }
  },

  // Get the currently displayed entity summary
  getDisplayedEntity: (): EntitySummary | undefined => {
    return characterSheetStore.displayedEntityId 
      ? characterSheetStore.summaries[characterSheetStore.displayedEntityId] 
      : undefined;
  },
  
  // Fetch character data
  fetchCharacter: async (characterId: string, silent: boolean = false) => {
    if (!silent) {
      characterSheetStore.loading = true;
    }
    
    try {
      const characterData = await fetchCharacter(characterId);
      
      characterSheetStore.character = characterData;
      characterSheetStore.error = null;
    } catch (err) {
      console.error('Error fetching character data:', err);
      characterSheetStore.error = err instanceof Error ? err.message : 'Failed to fetch character';
    } finally {
      if (!silent) {
        characterSheetStore.loading = false;
      }
    }
  },
  
  // Fetch entity summaries
  fetchSummaries: async () => {
    try {
      const summariesData = await fetchEntitySummaries();
      
      // Convert array to record while preserving existing data
      const summariesRecord = summariesData.reduce((acc, summary) => {
        // Preserve existing data for smooth transitions
        const existingSummary = characterSheetStore.summaries[summary.uuid];
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

      characterSheetStore.summaries = summariesRecord;
    } catch (err) {
      console.error('Error fetching summaries:', err);
    }
  },
};

// Export both store and actions
export { characterSheetStore, characterSheetActions }; 