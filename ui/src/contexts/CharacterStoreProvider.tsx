import * as React from 'react';
import { characterStore, characterActions } from '../store/characterStore';
import type { Character } from '../models/character';

interface CharacterStoreProviderProps {
  character: Character | null;
  children: React.ReactNode;
}

export const CharacterStoreProvider: React.FC<CharacterStoreProviderProps> = ({ 
  character,
  children 
}) => {
  // Update store when character changes
  React.useEffect(() => {
    if (character) {
      characterActions.setCharacter(character);
    }
  }, [character]);

  return <>{children}</>;
}; 