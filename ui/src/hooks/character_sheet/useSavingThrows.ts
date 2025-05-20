import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterSheetStore } from '../../store/characterSheetStore';
import type { 
  SavingThrowSetSnapshot, 
  SavingThrowBonusCalculationSnapshot,
  SavingThrowSnapshot 
} from '../../types/characterSheet_types';

interface SavingThrowsData {
  // Data from store
  savingThrows: SavingThrowSetSnapshot | null;
  calculations: Readonly<Record<string, SavingThrowBonusCalculationSnapshot>> | null;
  // UI state
  selectedSavingThrow: SavingThrowSnapshot | null;
  dialogOpen: boolean;
  // Actions
  handleSavingThrowClick: (savingThrow: SavingThrowSnapshot) => void;
  handleCloseDialog: () => void;
}

export function useSavingThrows(): SavingThrowsData {
  const snap = useSnapshot(characterSheetStore);
  const [selectedSavingThrow, setSelectedSavingThrow] = useState<SavingThrowSnapshot | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleSavingThrowClick = useCallback((savingThrow: SavingThrowSnapshot) => {
    setSelectedSavingThrow(savingThrow);
    setDialogOpen(true);
  }, []);

  const handleCloseDialog = useCallback(() => {
    setDialogOpen(false);
    setSelectedSavingThrow(null);
  }, []);

  return {
    savingThrows: snap.character?.saving_throws ?? null,
    calculations: snap.character?.saving_throw_calculations ?? null,
    selectedSavingThrow,
    dialogOpen,
    handleSavingThrowClick,
    handleCloseDialog
  };
} 