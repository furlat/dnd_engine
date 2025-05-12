import { useSnapshot } from 'valtio';
import { useState, useCallback, useMemo } from 'react';
import { characterStore, characterActions } from '../../store/characterStore';
import { eventQueueActions } from '../../store/eventQueueStore';
import { executeAttack, setEntityTarget } from '../../api/combatApi';
import { refreshActionEconomy } from '../../api/characterApi';
import type { ReadonlyCharacter, ReadonlyEntitySummary } from '../../models/readonly';
import React from 'react';

interface ActionBarData {
  // Store data
  character: ReadonlyCharacter | null;
  targets: ReadonlyEntitySummary[];
  targetInfo: ReadonlyEntitySummary | null;
  // UI State
  error: string | null;
  // Actions
  handleTargetChange: (targetId: string) => Promise<void>;
  handleAttack: (weaponSlot: 'MAIN_HAND' | 'OFF_HAND') => Promise<void>;
  handleRefreshActionEconomy: () => Promise<void>;
  clearError: () => void;
}

export function useActionBar(): ActionBarData {
  const snap = useSnapshot(characterStore);
  const [error, setError] = useState<string | null>(null);

  // Filter out current character from targets
  const targets = useMemo(() => {
    const character = snap.character;
    if (!character) return [];
    return Object.values(snap.summaries).filter(e => e.uuid !== character.uuid);
  }, [snap.summaries, snap.character]);

  // Get target info directly from character's target_summary
  const targetInfo = useMemo(() => {
    if (!snap.character?.target_entity_uuid) return null;
    
    // First try to get from target_summary
    if (snap.character.target_summary) {
      return snap.character.target_summary;
    }
    
    // Fallback to summaries if target_summary is not available
    return snap.summaries[snap.character.target_entity_uuid] ?? null;
  }, [snap.character?.target_summary, snap.character?.target_entity_uuid, snap.summaries]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const handleTargetChange = useCallback(async (targetId: string) => {
    if (!snap.character?.uuid) return;

    try {
      const updatedCharacter = await setEntityTarget(snap.character.uuid, targetId);
      characterActions.setCharacter(updatedCharacter);
      // Trigger event queue refresh after target change
      eventQueueActions.refresh();
    } catch (error) {
      console.error('Failed to set target:', error);
      setError(error instanceof Error ? error.message : 'Failed to set target');
    }
  }, [snap.character?.uuid]);

  const handleAttack = useCallback(async (weaponSlot: 'MAIN_HAND' | 'OFF_HAND') => {
    if (!snap.character?.uuid || !snap.character.target_entity_uuid) return;

    try {
      const result = await executeAttack(snap.character.uuid, snap.character.target_entity_uuid, weaponSlot);
      characterActions.setCharacter(result.attacker);
      // Trigger event queue refresh after attack
      eventQueueActions.refresh();
    } catch (error) {
      console.error('Failed to execute attack:', error);
      setError(error instanceof Error ? error.message : 'Failed to execute attack');
    }
  }, [snap.character?.uuid, snap.character?.target_entity_uuid]);

  const handleRefreshActionEconomy = useCallback(async () => {
    if (!snap.character?.uuid) return;

    try {
      const updatedCharacter = await refreshActionEconomy(snap.character.uuid);
      characterActions.setCharacter(updatedCharacter);
      // Trigger event queue refresh after action economy refresh
      eventQueueActions.refresh();
    } catch (error) {
      console.error('Failed to refresh action economy:', error);
      setError(error instanceof Error ? error.message : 'Failed to refresh action economy');
    }
  }, [snap.character?.uuid]);

  return {
    character: snap.character,
    targets,
    targetInfo,
    error,
    handleTargetChange,
    handleAttack,
    handleRefreshActionEconomy,
    clearError
  };
} 