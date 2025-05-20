import { useSnapshot } from 'valtio';
import { characterSheetStore } from '../../store/characterSheetStore';
import { battlemapStore } from '../../store/battlemapStore';
import type { Character } from '../../types/characterSheet_types';
import type { EntitySummary } from '../../types/common';

interface CharacterSheetState {
  // Data from store
  character: Character | null;
  loading: boolean;
  error: string | null;
  selectedEntityId: string | undefined;
}

export function useCharacterSheet(): CharacterSheetState {
  // Get data from store
  const characterSnap = useSnapshot(characterSheetStore);
  const battlemapSnap = useSnapshot(battlemapStore);
  
  return {
    character: characterSnap.character,
    loading: characterSnap.loading,
    error: characterSnap.error,
    selectedEntityId: battlemapSnap.entities.selectedEntityId || battlemapSnap.entities.displayedEntityId
  };
} 