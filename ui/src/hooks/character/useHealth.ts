import { useSnapshot } from 'valtio';
import { useState, useCallback, useMemo } from 'react';
import { characterStore } from '../../store/characterStore';
import type { 
  ReadonlyHealthSnapshot, 
  ReadonlyModifiableValueSnapshot,
  ReadonlyHitDiceSnapshot,
  ReadonlyDamageResistanceSnapshot
} from '../../models/readonly';
import { modifyHealth, applyTemporaryHP } from '../../api/characterApi';
import { useEntity } from '../../contexts/EntityContext';

interface HealthStats {
  current: number;
  max: number;
  conModifier: number;
  conPerLevel: number;
  totalDice: number;
  damageReduction: number;
  immunities: number;
  resistances: number;
  vulnerabilities: number;
  hitDiceString: string;
}

interface HealthData {
  // Data from store
  health: ReadonlyHealthSnapshot | null;
  // Computed values
  stats: HealthStats | null;
  // UI state
  dialogOpen: boolean;
  modifyDialogOpen: boolean;
  // Actions
  handleOpenDialog: () => void;
  handleCloseDialog: () => void;
  handleOpenModifyDialog: () => void;
  handleCloseModifyDialog: () => void;
  handleModifyHealth: (amount: number) => Promise<void>;
  handleApplyTempHP: (amount: number) => Promise<void>;
  // Helper functions
  getResistancesByType: (status: 'Immunity' | 'Resistance' | 'Vulnerability') => ReadonlyDamageResistanceSnapshot[];
}

export function useHealth(): HealthData {
  const snap = useSnapshot(characterStore);
  const { setEntityData } = useEntity();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [modifyDialogOpen, setModifyDialogOpen] = useState(false);

  // Dialog handlers
  const handleOpenDialog = useCallback(() => setDialogOpen(true), []);
  const handleCloseDialog = useCallback(() => setDialogOpen(false), []);
  const handleOpenModifyDialog = useCallback(() => setModifyDialogOpen(true), []);
  const handleCloseModifyDialog = useCallback(() => setModifyDialogOpen(false), []);

  // Health modification handlers
  const handleModifyHealth = useCallback(async (amount: number) => {
    if (!snap.character?.uuid) return;
    try {
      const result = await modifyHealth(snap.character.uuid, amount);
      setEntityData(result);
      setModifyDialogOpen(false);
    } catch (error) {
      console.error('Failed to modify health:', error);
    }
  }, [snap.character?.uuid, setEntityData]);

  const handleApplyTempHP = useCallback(async (amount: number) => {
    if (!snap.character?.uuid) return;
    try {
      const result = await applyTemporaryHP(snap.character.uuid, amount);
      setEntityData(result);
      setModifyDialogOpen(false);
    } catch (error) {
      console.error('Failed to apply temporary HP:', error);
    }
  }, [snap.character?.uuid, setEntityData]);

  // Computed values
  const stats = useMemo((): HealthStats | null => {
    const health = snap.character?.health;
    if (!health) return null;

    const current = health.current_hit_points ?? 0;
    const max = health.max_hit_points ?? 
      health.hit_dices_total_hit_points + health.max_hit_points_bonus.normalized_score;
    
    const conMod = health.max_hit_points ? 
      max - health.hit_dices_total_hit_points - health.max_hit_points_bonus.normalized_score : 
      0;

    const totalDice = health.total_hit_dices_number;
    const conPerLevel = totalDice > 0 ? conMod / totalDice : 0;

    // Calculate hit dice string
    const hitDiceGroups: Record<string, number> = {};
    health.hit_dices.forEach((hd) => {
      const sides = hd.hit_dice_value.score;
      hitDiceGroups[sides] = (hitDiceGroups[sides] || 0) + hd.hit_dice_count.score;
    });
    const hitDiceString = Object.entries(hitDiceGroups)
      .sort((a, b) => Number(a[0]) - Number(b[0]))
      .map(([sides, cnt]) => `${cnt}d${sides}`)
      .join(' + ');

    return {
      current,
      max,
      conModifier: conMod,
      conPerLevel,
      totalDice,
      damageReduction: health.damage_reduction.normalized_score,
      immunities: health.resistances.filter(r => r.status === 'Immunity').length,
      resistances: health.resistances.filter(r => r.status === 'Resistance').length,
      vulnerabilities: health.resistances.filter(r => r.status === 'Vulnerability').length,
      hitDiceString
    };
  }, [snap.character?.health]);

  // Helper function for filtering resistances
  const getResistancesByType = useCallback((status: 'Immunity' | 'Resistance' | 'Vulnerability'): ReadonlyDamageResistanceSnapshot[] => {
    return (snap.character?.health?.resistances.filter(r => r.status === status) as ReadonlyDamageResistanceSnapshot[]) ?? [];
  }, [snap.character?.health]);

  return {
    health: snap.character?.health ?? null,
    stats,
    dialogOpen,
    modifyDialogOpen,
    handleOpenDialog,
    handleCloseDialog,
    handleOpenModifyDialog,
    handleCloseModifyDialog,
    handleModifyHealth,
    handleApplyTempHP,
    getResistancesByType
  };
} 