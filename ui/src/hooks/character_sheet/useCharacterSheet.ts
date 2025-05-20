import { useSnapshot } from 'valtio';
import { characterSheetStore } from '../../store/characterSheetStore';
import type { Character, EntitySummary } from '../../models/character';
import type { ReadonlyCharacter, ReadonlyEntitySummary } from '../../models/readonly';

interface CharacterSheetState {
  // Data from store
  character: ReadonlyCharacter | null;
  loading: boolean;
  error: string | null;
  summaries: Record<string, ReadonlyEntitySummary>;
  displayedEntityId: string | undefined;
}

export function useCharacterSheet(): CharacterSheetState {
  // Get data from store
  const snap = useSnapshot(characterSheetStore);
  
  return {
    character: snap.character,
    loading: snap.loading,
    error: snap.error,
    summaries: snap.summaries,
    displayedEntityId: snap.displayedEntityId
  };
} 