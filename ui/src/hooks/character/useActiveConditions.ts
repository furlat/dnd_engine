import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterStore, characterActions } from '../../store/characterStore';
import { removeCondition, addCondition } from '../../api/characterApi';
import type { 
  ReadonlyConditionSnapshot,
  ReadonlyCharacter
} from '../../models/readonly';
import { ConditionType, DurationType } from '../../models/character';

export const CONDITIONS_LIST = Object.values(ConditionType).map(type => ({
  type,
  name: type.charAt(0) + type.slice(1).toLowerCase(),
  description: "A condition that affects the character's abilities and actions."  // We could add proper descriptions later
}));

interface ActiveConditionsData {
  // Store data
  conditions: Readonly<Record<string, ReadonlyConditionSnapshot>> | null;
  // UI State
  selectedCondition: string | null;
  error: string | null;
  addDialogOpen: boolean;
  // Actions
  handleSelectCondition: (condition: string | null) => void;
  handleCloseDialog: () => void;
  handleRemoveCondition: (conditionName: string, event?: React.MouseEvent) => Promise<void>;
  handleAddCondition: (conditionType: ConditionType) => Promise<void>;
  handleOpenAddDialog: () => void;
  handleCloseAddDialog: () => void;
  // Helpers
  formatDuration: (type: string, value: number | string | null | undefined) => string;
}

export function useActiveConditions(): ActiveConditionsData {
  const snap = useSnapshot(characterStore);
  const [selectedCondition, setSelectedCondition] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  // Dialog handlers
  const handleSelectCondition = useCallback((condition: string | null) => {
    setSelectedCondition(condition);
  }, []);

  const handleCloseDialog = useCallback(() => {
    setSelectedCondition(null);
    setError(null);
  }, []);

  const handleOpenAddDialog = useCallback(() => {
    setAddDialogOpen(true);
  }, []);

  const handleCloseAddDialog = useCallback(() => {
    setAddDialogOpen(false);
    setError(null);
  }, []);

  // API actions
  const handleRemoveCondition = useCallback(async (conditionName: string, event?: React.MouseEvent) => {
    if (event) {
      event.stopPropagation();
    }
    if (!snap.character?.uuid) return;

    console.time('Remove Condition Total');

    // Close dialog if this condition was selected
    if (selectedCondition === conditionName) {
      setSelectedCondition(null);
    }

    try {
      // Make the API call
      console.time('Remove Condition API Call');
      const updatedCharacter = await removeCondition(snap.character.uuid, conditionName);
      console.timeEnd('Remove Condition API Call');
      
      // Update with server state
      console.time('Remove Condition Store Update');
      characterActions.setCharacter(updatedCharacter);
      console.timeEnd('Remove Condition Store Update');
    } catch (error) {
      console.error('Failed to remove condition:', error);
      setError(error instanceof Error ? error.message : 'Failed to remove condition');
    } finally {
      console.timeEnd('Remove Condition Total');
    }
  }, [snap.character?.uuid, selectedCondition]);

  const handleAddCondition = useCallback(async (conditionType: ConditionType) => {
    if (!snap.character?.uuid) return;

    console.time('Add Condition Total');
    
    // Close dialog immediately
    setAddDialogOpen(false);

    try {
      console.time('Add Condition API Call');
      const updatedCharacter = await addCondition(snap.character.uuid, {
        condition_type: conditionType,
        source_entity_uuid: snap.character.uuid,
        duration_type: DurationType.PERMANENT
      });
      console.timeEnd('Add Condition API Call');
      
      console.time('Add Condition Store Update');
      characterActions.setCharacter(updatedCharacter);
      console.timeEnd('Add Condition Store Update');
    } catch (err) {
      console.error('Failed to add condition:', err);
      setError(err instanceof Error ? err.message : 'Failed to add condition');
      // Reopen dialog to show error
      setAddDialogOpen(true);
    } finally {
      console.timeEnd('Add Condition Total');
    }
  }, [snap.character?.uuid]);

  // Helper functions
  const formatDuration = useCallback((type: string, value: number | string | null | undefined): string => {
    switch (type) {
      case 'rounds':
        return `${value} rounds`;
      case 'permanent':
        return 'Permanent';
      case 'until_long_rest':
        return 'Until long rest';
      case 'on_condition':
        return `Until ${value}`;
      default:
        return 'Unknown';
    }
  }, []);

  return {
    conditions: snap.character?.active_conditions ?? null,
    selectedCondition,
    error,
    addDialogOpen,
    handleSelectCondition,
    handleCloseDialog,
    handleRemoveCondition,
    handleAddCondition,
    handleOpenAddDialog,
    handleCloseAddDialog,
    formatDuration
  };
} 