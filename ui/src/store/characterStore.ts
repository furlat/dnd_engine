import { proxy } from 'valtio';
import type { Character, EntitySummary } from '../models/character';
import type { ReadonlyCharacter, ReadonlyEntitySummary, DeepReadonly } from '../models/readonly';
import { fetchCharacter, fetchEntitySummaries } from '../api/characterApi';

// Base state interface without readonly modifiers for the store
export interface CharacterStoreState {
  character: Character | null;
  loading: boolean;
  error: string | null;
  summaries: Record<string, EntitySummary>;
}

// Read-only version for consuming components
export type ReadonlyCharacterStore = DeepReadonly<CharacterStoreState>;

// Initialize the store with default values
const characterStore = proxy<CharacterStoreState>({
  character: null,
  loading: false,
  error: null,
  summaries: {},
});

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
  
  // Fetch summaries
  fetchSummaries: async () => {
    try {
      const summariesData = await fetchEntitySummaries();
      // Convert array to record
      const summariesRecord = summariesData.reduce((acc, summary) => {
        acc[summary.uuid] = summary;
        return acc;
      }, {} as Record<string, EntitySummary>);
      characterStore.summaries = summariesRecord;
    } catch (err) {
      console.error('Error fetching summaries:', err);
    }
  }
};

// Export both store and actions
export { characterStore, characterActions }; 