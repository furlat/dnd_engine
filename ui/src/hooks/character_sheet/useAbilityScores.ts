import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterSheetStore } from '../../store/characterSheetStore';
import type { AbilityScoresSnapshot, AbilityScore } from '../../types/characterSheet_types';

interface AbilityScoresState {
  // Data from store
  abilityScores: AbilityScoresSnapshot | null;
  // UI state
  selectedAbility: AbilityScore | null;
  dialogOpen: boolean;
  // Actions
  handleAbilityClick: (ability: AbilityScore) => void;
  handleCloseDialog: () => void;
}

export function useAbilityScores(): AbilityScoresState {
  // Get data from store
  const snap = useSnapshot(characterSheetStore);
  
  // Local UI state
  const [selectedAbility, setSelectedAbility] = useState<AbilityScore | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Handlers
  const handleAbilityClick = useCallback((ability: AbilityScore) => {
    setSelectedAbility(ability);
    setDialogOpen(true);
  }, []);

  const handleCloseDialog = useCallback(() => {
    setDialogOpen(false);
  }, []);

  return {
    abilityScores: snap.character?.ability_scores ?? null,
    selectedAbility,
    dialogOpen,
    handleAbilityClick,
    handleCloseDialog
  };
} 