import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterSheetStore } from '../../store/characterSheetStore';
import type { 
  ReadonlySavingThrowSetSnapshot, 
  ReadonlySavingThrowBonusCalculation,
  ReadonlySavingThrowSnapshot 
} from '../../models/readonly';

interface SavingThrowsData {
  // Data from store
  savingThrows: ReadonlySavingThrowSetSnapshot | null;
  calculations: Readonly<Record<string, ReadonlySavingThrowBonusCalculation>> | null;
  // UI state
  selectedSavingThrow: ReadonlySavingThrowSnapshot | null;
  dialogOpen: boolean;
  // Actions
  handleSavingThrowClick: (savingThrow: ReadonlySavingThrowSnapshot) => void;
  handleCloseDialog: () => void;
}

export function useSavingThrows(): SavingThrowsData {
  const snap = useSnapshot(characterSheetStore);
  const [selectedSavingThrow, setSelectedSavingThrow] = useState<ReadonlySavingThrowSnapshot | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleSavingThrowClick = useCallback((savingThrow: ReadonlySavingThrowSnapshot) => {
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