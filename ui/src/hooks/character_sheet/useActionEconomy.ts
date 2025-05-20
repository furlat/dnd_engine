import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterSheetStore, characterSheetActions } from '../../store/characterSheetStore';
import { refreshActionEconomy } from '../../api/character_sheet/characterSheetApi';
import type { 
  ReadonlyActionEconomySnapshot,
  ReadonlyModifiableValueSnapshot,
  ReadonlyModifier
} from '../../models/readonly';

interface ActionEconomyDialogState {
  movement: boolean;
  actions: boolean;
  reactions: boolean;
}

interface ActionEconomyData {
  // Store data
  actionEconomy: ReadonlyActionEconomySnapshot | null;
  // UI state
  isRefreshing: boolean;
  dialogState: ActionEconomyDialogState;
  // Actions
  handleOpenDialog: (type: keyof ActionEconomyDialogState) => void;
  handleCloseDialog: (type: keyof ActionEconomyDialogState) => void;
  handleRefreshActionEconomy: () => Promise<void>;
  // Computed values
  getMovementDetails: () => { available: number; base: number; totalCost: number } | null;
  getActionsDetails: () => {
    availableActions: number;
    availableBonusActions: number;
    baseActions: number;
    baseBonusActions: number;
    totalActionCost: number;
    totalBonusActionCost: number;
  } | null;
  getReactionsDetails: () => { available: number; base: number; totalCost: number } | null;
}

export function useActionEconomy(): ActionEconomyData {
  const snap = useSnapshot(characterSheetStore);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [dialogState, setDialogState] = useState<ActionEconomyDialogState>({
    movement: false,
    actions: false,
    reactions: false
  });

  // Dialog handlers
  const handleOpenDialog = useCallback((type: keyof ActionEconomyDialogState) => {
    setDialogState(prev => ({ ...prev, [type]: true }));
  }, []);

  const handleCloseDialog = useCallback((type: keyof ActionEconomyDialogState) => {
    setDialogState(prev => ({ ...prev, [type]: false }));
  }, []);

  // Action Economy refresh handler
  const handleRefreshActionEconomy = useCallback(async () => {
    if (!snap.character?.uuid) return;
    try {
      setIsRefreshing(true);
      const result = await refreshActionEconomy(snap.character.uuid);
      characterSheetActions.setCharacter(result);
    } catch (error) {
      console.error('Failed to refresh action economy:', error);
    } finally {
      setIsRefreshing(false);
    }
  }, [snap.character?.uuid]);

  // Helper function for cost calculation
  const calculateTotalCost = useCallback((modifiers: ReadonlyArray<ReadonlyModifier>) => {
    return modifiers.reduce((sum, mod) => sum + mod.value, 0);
  }, []);

  // Computed values getters
  const getMovementDetails = useCallback(() => {
    const ae = snap.character?.action_economy;
    if (!ae) return null;

    return {
      available: ae.available_movement,
      base: ae.base_movement,
      totalCost: calculateTotalCost(ae.movement_costs)
    };
  }, [snap.character?.action_economy, calculateTotalCost]);

  const getActionsDetails = useCallback(() => {
    const ae = snap.character?.action_economy;
    if (!ae) return null;

    return {
      availableActions: ae.available_actions,
      availableBonusActions: ae.available_bonus_actions,
      baseActions: ae.base_actions,
      baseBonusActions: ae.base_bonus_actions,
      totalActionCost: calculateTotalCost(ae.action_costs),
      totalBonusActionCost: calculateTotalCost(ae.bonus_action_costs)
    };
  }, [snap.character?.action_economy, calculateTotalCost]);

  const getReactionsDetails = useCallback(() => {
    const ae = snap.character?.action_economy;
    if (!ae) return null;

    return {
      available: ae.available_reactions,
      base: ae.base_reactions,
      totalCost: calculateTotalCost(ae.reaction_costs)
    };
  }, [snap.character?.action_economy, calculateTotalCost]);

  return {
    actionEconomy: snap.character?.action_economy ?? null,
    isRefreshing,
    dialogState,
    handleOpenDialog,
    handleCloseDialog,
    handleRefreshActionEconomy,
    getMovementDetails,
    getActionsDetails,
    getReactionsDetails
  };
} 