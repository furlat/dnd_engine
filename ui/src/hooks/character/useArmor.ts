import { useSnapshot } from 'valtio';
import { useState, useCallback, useEffect } from 'react';
import { characterStore, characterActions } from '../../store/characterStore';
import { eventQueueActions } from '../../store/eventQueueStore';
import type { 
  ReadonlyACBonusCalculation,
  ReadonlyEquipmentSnapshot,
  ReadonlyModifiableValueSnapshot
} from '../../models/readonly';
import { ArmorSnapshot } from '../../api/types';
import { fetchAllEquipment, equipItem, unequipItem } from '../../api/characterApi';

interface ArmorData {
  // Store data
  acCalculation: ReadonlyACBonusCalculation | null;
  equipment: ReadonlyEquipmentSnapshot | null;
  // UI state
  detailMode: 'armor' | 'advantage' | 'critical' | 'auto_hit';
  dialogOpen: boolean;
  itemDetailsOpen: 'armor' | 'shield' | null;
  armorSelectOpen: boolean;
  availableArmor: ArmorSnapshot[];
  error: string | null;
  menuAnchor: HTMLElement | null;
  // Computed values
  totalAC: number;
  isUnarmored: boolean;
  combinedDex: number | undefined;
  maxDex: number | undefined;
  bodyArmorName: string;
  armorType: string;
  shieldName: string | undefined;
  // Actions
  handleOpenDialog: () => void;
  handleCloseDialog: () => void;
  handleDetailModeChange: (mode: 'armor' | 'advantage' | 'critical' | 'auto_hit') => void;
  handleItemDetailsOpen: (type: 'armor' | 'shield' | null) => void;
  handleArmorSelectOpen: () => void;
  handleArmorSelectClose: () => void;
  handleArmorSelect: (armorId: string) => Promise<void>;
  handleUnequipArmor: () => Promise<void>;
  handleMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
  handleMenuClose: () => void;
  clearError: () => void;
  // Modifier arrays for display
  getLeftValues: () => ReadonlyModifiableValueSnapshot[];
  getBreakdownItems: () => Array<{ label: string; mv: ReadonlyModifiableValueSnapshot }>;
}

export function useArmor(): ArmorData {
  const snap = useSnapshot(characterStore);
  const [detailMode, setDetailMode] = useState<'armor' | 'advantage' | 'critical' | 'auto_hit'>('armor');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [itemDetailsOpen, setItemDetailsOpen] = useState<'armor' | 'shield' | null>(null);
  const [armorSelectOpen, setArmorSelectOpen] = useState(false);
  const [availableArmor, setAvailableArmor] = useState<ArmorSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);

  const acCalc = snap.character?.ac_calculation ?? null;
  const equipment = snap.character?.equipment ?? null;

  // Fetch available armor when the selection dialog opens
  useEffect(() => {
    if (armorSelectOpen && snap.character) {
      fetchAllEquipment(snap.character.uuid)
        .then(items => {
          // Filter for body armor only
          const armor = items.filter((item): item is ArmorSnapshot => 
            'type' in item && 
            'body_part' in item && 
            item.body_part === 'Body' &&
            ['Light', 'Medium', 'Heavy', 'Cloth'].includes(item.type)
          );
          setAvailableArmor(armor);
        })
        .catch(error => {
          console.error('Failed to fetch armor:', error);
          setError(error instanceof Error ? error.message : 'Failed to fetch armor');
        });
    }
  }, [armorSelectOpen, snap.character]);

  // Computed values
  const totalAC = acCalc?.final_ac ?? 0;
  const isUnarmored = acCalc?.is_unarmored ?? true;
  const combinedDex = acCalc?.combined_dexterity_bonus?.normalized_score;
  const maxDex = acCalc?.max_dexterity_bonus?.normalized_score;
  const bodyArmorName = equipment?.body_armor ? equipment.body_armor.name : 'No Armor';
  const armorType = equipment?.body_armor ? equipment.body_armor.type : 'Unarmored';
  const shieldName = equipment?.weapon_off_hand && (equipment.weapon_off_hand as any).ac_bonus 
    ? (equipment.weapon_off_hand as any).name 
    : undefined;

  // Actions
  const handleOpenDialog = useCallback(() => setDialogOpen(true), []);
  const handleCloseDialog = useCallback(() => setDialogOpen(false), []);
  const handleDetailModeChange = useCallback((mode: 'armor' | 'advantage' | 'critical' | 'auto_hit') => setDetailMode(mode), []);
  const handleItemDetailsOpen = useCallback((type: 'armor' | 'shield' | null) => setItemDetailsOpen(type), []);
  const handleArmorSelectOpen = useCallback(() => {
    setArmorSelectOpen(true);
    setError(null);
  }, []);
  const handleArmorSelectClose = useCallback(() => {
    setArmorSelectOpen(false);
    setError(null);
  }, []);
  const handleMenuClick = useCallback((event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setMenuAnchor(event.currentTarget);
  }, []);
  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);
  const clearError = useCallback(() => setError(null), []);

  const handleArmorSelect = useCallback(async (armorId: string) => {
    if (!snap.character) return;
    try {
      setArmorSelectOpen(false);
      const equipResult = await equipItem(snap.character.uuid, armorId, 'Body');
      characterActions.setCharacter(equipResult);
      // Trigger event queue refresh after equipping armor
      eventQueueActions.refresh();
    } catch (error: any) {
      console.error('Failed to equip armor:', error);
      setError(error.response?.data?.detail ?? 'Failed to equip armor');
      setArmorSelectOpen(true);
    }
  }, [snap.character]);

  const handleUnequipArmor = useCallback(async () => {
    if (!snap.character) return;
    try {
      const unequipResult = await unequipItem(snap.character.uuid, 'Body');
      characterActions.setCharacter(unequipResult);
      handleMenuClose();
      // Trigger event queue refresh after unequipping armor
      eventQueueActions.refresh();
    } catch (error: any) {
      console.error('Failed to unequip armor:', error);
      setError(error.response?.data?.message ?? 'Failed to unequip armor');
    }
  }, [snap.character, handleMenuClose]);

  // Helper functions for modifier arrays
  const getLeftValues = useCallback(() => {
    if (!acCalc) return [];

    const leftValues: ReadonlyModifiableValueSnapshot[] = [];
    if (isUnarmored) {
      leftValues.push(...(acCalc.unarmored_values ?? []));
      leftValues.push(...(acCalc.ability_bonuses ?? []));
      leftValues.push(...(acCalc.ability_modifier_bonuses ?? []));
      if (acCalc.max_dexterity_bonus) {
        leftValues.push(acCalc.max_dexterity_bonus);
      }
    } else {
      leftValues.push(...(acCalc.armored_values ?? []));
      if (acCalc.combined_dexterity_bonus) leftValues.push(acCalc.combined_dexterity_bonus);
      if (acCalc.max_dexterity_bonus) leftValues.push(acCalc.max_dexterity_bonus);
    }
    return leftValues;
  }, [acCalc, isUnarmored]);

  const getBreakdownItems = useCallback(() => {
    if (!acCalc) return [];

    const items: Array<{ label: string; mv: ReadonlyModifiableValueSnapshot }> = [];
    if (isUnarmored) {
      (acCalc.unarmored_values ?? []).forEach((mv) => items.push({ label: mv.name, mv }));
      (acCalc.ability_bonuses ?? []).forEach((mv, idx) =>
        items.push({
          label: acCalc.unarmored_abilities?.[idx] ? `${acCalc.unarmored_abilities[idx]} Score` : `Ability Bonus ${idx + 1}`,
          mv,
        })
      );
      (acCalc.ability_modifier_bonuses ?? []).forEach((mv, idx) =>
        items.push({
          label: acCalc.unarmored_abilities?.[idx] ? `${acCalc.unarmored_abilities[idx]} Modifier` : `Ability Modifier ${idx + 1}`,
          mv,
        })
      );
      if (acCalc.max_dexterity_bonus) {
        items.push({ label: 'Max Dex Allowed', mv: acCalc.max_dexterity_bonus });
      }
    } else {
      (acCalc.armored_values ?? []).forEach((mv) => items.push({ label: mv.name, mv }));
      if (acCalc.combined_dexterity_bonus)
        items.push({ label: 'Dexterity Bonus (Capped)', mv: acCalc.combined_dexterity_bonus });
      if (acCalc.dexterity_bonus) items.push({ label: 'Dexterity Score', mv: acCalc.dexterity_bonus });
      if (acCalc.dexterity_modifier_bonus)
        items.push({ label: 'Dexterity Modifier', mv: acCalc.dexterity_modifier_bonus });
      if (acCalc.max_dexterity_bonus)
        items.push({ label: 'Max Dex Allowed', mv: acCalc.max_dexterity_bonus });
    }
    return items;
  }, [acCalc, isUnarmored]);

  return {
    acCalculation: acCalc,
    equipment,
    detailMode,
    dialogOpen,
    itemDetailsOpen,
    armorSelectOpen,
    availableArmor,
    error,
    menuAnchor,
    totalAC,
    isUnarmored,
    combinedDex,
    maxDex,
    bodyArmorName,
    armorType,
    shieldName,
    handleOpenDialog,
    handleCloseDialog,
    handleDetailModeChange,
    handleItemDetailsOpen,
    handleArmorSelectOpen,
    handleArmorSelectClose,
    handleArmorSelect,
    handleUnequipArmor,
    handleMenuClick,
    handleMenuClose,
    clearError,
    getLeftValues,
    getBreakdownItems
  };
} 