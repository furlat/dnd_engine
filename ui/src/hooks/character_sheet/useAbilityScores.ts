import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterSheetStore } from '../../store/characterSheetStore';
import type { ReadonlyAbilityScoresSnapshot, ReadonlyAbilityScore } from '../../models/readonly';

interface AbilityScoresState {
  // Data from store
  abilityScores: ReadonlyAbilityScoresSnapshot | null;
  // UI state
  selectedAbility: ReadonlyAbilityScore | null;
  dialogOpen: boolean;
  // Actions
  handleAbilityClick: (ability: ReadonlyAbilityScore) => void;
  handleCloseDialog: () => void;
}

export function useAbilityScores(): AbilityScoresState {
  // Get data from store
  const snap = useSnapshot(characterSheetStore);
  
  // Local UI state
  const [selectedAbility, setSelectedAbility] = useState<ReadonlyAbilityScore | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Handlers
  const handleAbilityClick = useCallback((ability: ReadonlyAbilityScore) => {
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