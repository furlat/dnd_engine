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
  cachedCharacters: Record<string, Character>;
  lastFetchedId: string | null;
}

// Read-only version for consuming components
export type ReadonlyCharacterSheetStore = DeepReadonly<CharacterSheetStoreState>;

// Initialize the store with default values
const characterSheetStore = proxy<CharacterSheetStoreState>({
  character: null,
  loading: false,
  error: null,
  cachedCharacters: {},
  lastFetchedId: null
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
    // Cache the character
    characterSheetStore.cachedCharacters[character.uuid] = character;
    characterSheetStore.lastFetchedId = character.uuid;
  },
  
  // Fetch character data based on the selected entity in battlemapStore
  fetchSelectedCharacter: async (silent: boolean = false) => {
    const selectedEntityId = battlemapStore.entities.selectedEntityId || 
                            battlemapStore.entities.displayedEntityId;
    
    if (!selectedEntityId) {
      characterSheetStore.character = null;
      return;
    }
    
    // If we already have this character loaded and it's the same as what we're requesting, don't refetch
    if (characterSheetStore.lastFetchedId === selectedEntityId && 
        characterSheetStore.character?.uuid === selectedEntityId) {
      return;
    }
    
    // Check if the character is already in the cache
    if (characterSheetStore.cachedCharacters[selectedEntityId]) {
      characterSheetStore.character = characterSheetStore.cachedCharacters[selectedEntityId];
      characterSheetStore.lastFetchedId = selectedEntityId;
      return;
    }
    
    if (!silent) {
      characterSheetStore.loading = true;
    }
    
    try {
      const characterData = await fetchCharacter(selectedEntityId);
      
      characterSheetStore.character = characterData;
      // Cache the character
      characterSheetStore.cachedCharacters[characterData.uuid] = characterData;
      characterSheetStore.lastFetchedId = characterData.uuid;
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
    // Check if the character is already in the cache
    if (characterSheetStore.cachedCharacters[characterId]) {
      characterSheetStore.character = characterSheetStore.cachedCharacters[characterId];
      characterSheetStore.lastFetchedId = characterId;
      return;
    }
    
    if (!silent) {
      characterSheetStore.loading = true;
    }
    
    try {
      const characterData = await fetchCharacter(characterId);
      
      characterSheetStore.character = characterData;
      // Cache the character
      characterSheetStore.cachedCharacters[characterData.uuid] = characterData;
      characterSheetStore.lastFetchedId = characterData.uuid;
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
  
  // Clear cache if needed (e.g., when we want to refresh all data)
  clearCache: () => {
    characterSheetStore.cachedCharacters = {};
    characterSheetStore.lastFetchedId = null;
  }
};

// Export both store and actions
export { characterSheetStore, characterSheetActions }; 