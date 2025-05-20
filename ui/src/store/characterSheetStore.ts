import { proxy } from 'valtio';
import type { Character } from '../types/characterSheet_types';
import type { DeepReadonly } from '../types/common';
import { fetchCharacter } from '../api/character_sheet/characterSheetApi';
import { battlemapStore } from './battlemapStore';

// Base state interface without readonly modifiers for the store
export interface CharacterSheetStoreState {
  character: Character | null;
  loading: boolean;
  error: string | null;
}

// Read-only version for consuming components
export type ReadonlyCharacterSheetStore = DeepReadonly<CharacterSheetStoreState>;

// Initialize the store with default values
const characterSheetStore = proxy<CharacterSheetStoreState>({
  character: null,
  loading: false,
  error: null
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
  
  // Fetch character data based on the selected entity in battlemapStore
  fetchSelectedCharacter: async (silent: boolean = false) => {
    const selectedEntityId = battlemapStore.entities.selectedEntityId || 
                            battlemapStore.entities.displayedEntityId;
    
    if (!selectedEntityId) {
      characterSheetStore.character = null;
      return;
    }
    
    if (!silent) {
      characterSheetStore.loading = true;
    }
    
    try {
      const characterData = await fetchCharacter(selectedEntityId);
      
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
  
  // Fetch a specific character by ID (for initial loading or explicit selection)
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
  }
};

// Export both store and actions
export { characterSheetStore, characterSheetActions }; 