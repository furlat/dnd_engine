import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterSheetStore, characterSheetActions } from '../../store/characterSheetStore';
import { eventQueueActions } from '../../store/eventQueueStore';
import { battlemapStore } from '../../store/battlemapStore';
import type { 
  AttackBonusCalculationSnapshot,
  EquipmentSnapshot,
  ModifiableValueSnapshot,
  EquipmentItem
} from '../../types/characterSheet_types';
import { fetchAllEquipment, equipItem, unequipItem } from '../../api/character_sheet/characterSheetApi';
import { useMoveAndAttack } from '../battlemap/useMoveAndAttack';

export type WeaponSlot = 'MAIN_HAND' | 'OFF_HAND';

interface AttackData {
  // Store data
  mainHandCalc: AttackBonusCalculationSnapshot | null;
  offHandCalc: AttackBonusCalculationSnapshot | null;
  equipment: EquipmentSnapshot | null;
  // UI state
  dialogOpen: boolean;
  detailMode: 'attack' | 'damage' | 'advantage';
  itemDetailsOpen: boolean;
  weaponSelectOpen: boolean;
  availableWeapons: EquipmentItem[];
  error: string | null;
  menuAnchor: HTMLElement | null;
  // Actions
  handleOpenDialog: () => void;
  handleCloseDialog: () => void;
  handleDetailModeChange: (mode: 'attack' | 'damage' | 'advantage') => void;
  handleItemDetailsOpen: (open: boolean) => void;
  handleWeaponSelectOpen: () => void;
  handleWeaponSelectClose: () => void;
  handleWeaponSelect: (weaponId: string, slot: WeaponSlot) => Promise<void>;
  handleUnequipWeapon: (slot: WeaponSlot) => Promise<void>;
  handleMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
  handleMenuClose: () => void;
  clearError: () => void;
  // Attack actions
  attackTarget: (targetId: string, slot?: WeaponSlot) => Promise<boolean>;
  moveAndAttackTarget: (targetId: string, slot?: WeaponSlot) => Promise<boolean>;
  // Computed values
  getWeaponName: (slot: WeaponSlot) => string;
  getWeaponDamageExpr: (slot: WeaponSlot) => string;
  getWeaponDamageType: (slot: WeaponSlot) => string;
  getExtraDamageExprs: (slot: WeaponSlot) => Array<{ expr: string; type: string }>;
  getComponentList: (slot: WeaponSlot) => Array<{ label: string; mv: ModifiableValueSnapshot }>;
  getDamageComponents: (slot: WeaponSlot) => Array<{ label: string; mv: ModifiableValueSnapshot }>;
}

export function useAttack(): AttackData {
  const snap = useSnapshot(characterSheetStore);
  const battlemapSnap = useSnapshot(battlemapStore);
  const [detailMode, setDetailMode] = useState<'attack' | 'damage' | 'advantage'>('attack');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [itemDetailsOpen, setItemDetailsOpen] = useState(false);
  const [weaponSelectOpen, setWeaponSelectOpen] = useState(false);
  const [availableWeapons, setAvailableWeapons] = useState<EquipmentItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  
  // Get move-and-attack functionality
  const { attackTarget: battleAttackTarget, moveAndAttack: battleMoveAndAttack } = useMoveAndAttack();

  const equipment = snap.character?.equipment ?? null;
  const calcsObj = snap.character?.attack_calculations ?? {};

  // Get calculations for each slot
  const mainHandCalc = Object.values(calcsObj).find(
    (c) => c && c.weapon_slot === 'MAIN_HAND'
  ) as AttackBonusCalculationSnapshot | null;

  const offHandCalc = Object.values(calcsObj).find(
    (c) => c && c.weapon_slot === 'OFF_HAND'
  ) as AttackBonusCalculationSnapshot | null;

  // Fetch available weapons when the selection dialog opens
  const fetchWeapons = useCallback(async () => {
    if (!snap.character) return;
    try {
      const items = await fetchAllEquipment(snap.character.uuid);
      // Filter for weapons only
      const weapons = items.filter(item => 
        'damage_dice' in item && 
        'damage_type' in item &&
        !('ac_bonus' in item) // Exclude shields which might have damage properties
      );
      setAvailableWeapons(weapons);
    } catch (error) {
      console.error('Failed to fetch weapons:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch weapons');
    }
  }, [snap.character]);

  // Dialog handlers
  const handleOpenDialog = useCallback(() => setDialogOpen(true), []);
  const handleCloseDialog = useCallback(() => setDialogOpen(false), []);
  const handleDetailModeChange = useCallback((mode: 'attack' | 'damage' | 'advantage') => setDetailMode(mode), []);
  const handleItemDetailsOpen = useCallback((open: boolean) => setItemDetailsOpen(open), []);
  const handleWeaponSelectOpen = useCallback(() => {
    setWeaponSelectOpen(true);
    setError(null);
    fetchWeapons();
  }, [fetchWeapons]);
  const handleWeaponSelectClose = useCallback(() => {
    setWeaponSelectOpen(false);
    setError(null);
  }, []);
  const handleMenuClick = useCallback((event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setMenuAnchor(event.currentTarget);
  }, []);
  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);
  const clearError = useCallback(() => setError(null), []);

  // Weapon actions
  const handleWeaponSelect = useCallback(async (weaponId: string, slot: WeaponSlot) => {
    if (!snap.character) return;
    try {
      setWeaponSelectOpen(false);
      const updatedEntity = await equipItem(snap.character.uuid, weaponId, slot);
      characterSheetActions.setCharacter(updatedEntity);
      // Trigger event queue refresh after equipping weapon
      eventQueueActions.refresh();
    } catch (error: any) {
      console.error('Failed to equip weapon:', error);
      setError(error.response?.data?.detail ?? 'Failed to equip weapon');
      setWeaponSelectOpen(true);
    }
  }, [snap.character]);

  const handleUnequipWeapon = useCallback(async (slot: WeaponSlot) => {
    if (!snap.character) return;
    try {
      const updatedEntity = await unequipItem(snap.character.uuid, slot);
      characterSheetActions.setCharacter(updatedEntity);
      handleMenuClose();
      // Trigger event queue refresh after unequipping weapon
      eventQueueActions.refresh();
    } catch (error: any) {
      console.error('Failed to unequip weapon:', error);
      setError(error.response?.data?.message ?? 'Failed to unequip weapon');
    }
  }, [snap.character, handleMenuClose]);

  // Computed values getters
  const getWeaponName = useCallback((slot: WeaponSlot): string => {
    const calc = slot === 'MAIN_HAND' ? mainHandCalc : offHandCalc;
    return calc?.is_unarmed ? 'Unarmed Strike' : calc?.weapon_name ?? 'Weapon';
  }, [mainHandCalc, offHandCalc]);

  const getWeaponDamageExpr = useCallback((slot: WeaponSlot): string => {
    if (!equipment) return '';
    const weapon = slot === 'MAIN_HAND' ? equipment.weapon_main_hand : equipment.weapon_off_hand;
    
    if (weapon && 'damage_dice' in weapon) {
      const base = `${weapon.dice_numbers}d${weapon.damage_dice}`;
      const bonus = weapon.damage_bonus?.normalized_value ?? 0;
      return bonus !== 0 ? `${base}${bonus > 0 ? '+' : ''}${bonus}` : base;
    }
    
    // Unarmed fallback
    const base = `${equipment.unarmed_dice_numbers}d${equipment.unarmed_damage_dice}`;
    const bonus = equipment.unarmed_damage_bonus?.normalized_value ?? 0;
    return bonus !== 0 ? `${base}${bonus > 0 ? '+' : ''}${bonus}` : base;
  }, [equipment]);

  const getWeaponDamageType = useCallback((slot: WeaponSlot): string => {
    if (!equipment) return '';
    const weapon = slot === 'MAIN_HAND' ? equipment.weapon_main_hand : equipment.weapon_off_hand;
    
    const damageType = weapon ? (weapon as any).damage_type : equipment.unarmed_damage_type;
    return typeof damageType === 'string' 
      ? damageType.charAt(0).toUpperCase() + damageType.slice(1).toLowerCase() 
      : String(damageType);
  }, [equipment]);

  const getExtraDamageExprs = useCallback((slot: WeaponSlot): Array<{ expr: string; type: string }> => {
    if (!equipment) return [];
    const weapon = slot === 'MAIN_HAND' ? equipment.weapon_main_hand : equipment.weapon_off_hand;
    
    if (!weapon || !('extra_damages' in weapon)) return [];
    return (weapon as any).extra_damages.map((extra: any) => {
      const base = `${extra.dice_numbers}d${extra.damage_dice}`;
      const bonus = extra.damage_bonus?.normalized_value ?? 0;
      const expr = bonus !== 0 ? `${base}${bonus > 0 ? '+' : ''}${bonus}` : base;
      const type = typeof extra.damage_type === 'string' 
        ? extra.damage_type.charAt(0).toUpperCase() + extra.damage_type.slice(1).toLowerCase() 
        : String(extra.damage_type);
      return { expr, type };
    });
  }, [equipment]);

  const getComponentList = useCallback((slot: WeaponSlot) => {
    const calc = slot === 'MAIN_HAND' ? mainHandCalc : offHandCalc;
    if (!calc) return [];
    
    return [
      { label: 'Proficiency Bonus', mv: calc.proficiency_bonus },
      { label: calc.weapon_name ? 'Weapon Bonus' : 'Unarmed Bonus', mv: calc.weapon_bonus },
      ...calc.attack_bonuses.map((mv: ModifiableValueSnapshot) => ({ label: mv.name, mv })),
      ...calc.ability_bonuses.map((mv: ModifiableValueSnapshot) => ({ label: mv.name, mv })),
    ];
  }, [mainHandCalc, offHandCalc]);

  const getDamageComponents = useCallback((slot: WeaponSlot) => {
    if (!equipment) return [];
    const weapon = slot === 'MAIN_HAND' ? equipment.weapon_main_hand : equipment.weapon_off_hand;
    const calc = slot === 'MAIN_HAND' ? mainHandCalc : offHandCalc;
    
    const items: { label: string; mv: ModifiableValueSnapshot }[] = [];
    
    if (weapon && (weapon as any).damage_bonus) {
      items.push({ label: 'Weapon Damage Bonus', mv: (weapon as any).damage_bonus });
    }
    
    if (calc?.is_unarmed && equipment.unarmed_damage_bonus) {
      items.push({ label: 'Unarmed Damage Bonus', mv: equipment.unarmed_damage_bonus });
    }
    
    if (equipment.damage_bonus) {
      items.push({ label: 'Global Damage Bonus', mv: equipment.damage_bonus });
    }
    
    if (calc?.is_ranged && equipment.ranged_damage_bonus) {
      items.push({ label: 'Ranged Damage Bonus', mv: equipment.ranged_damage_bonus });
    }
    
    if (!calc?.is_ranged && equipment.melee_damage_bonus) {
      items.push({ label: 'Melee Damage Bonus', mv: equipment.melee_damage_bonus });
    }
    
    if (weapon && 'extra_damages' in weapon) {
      (weapon as any).extra_damages.forEach((extra: any, idx: number) => {
        if (extra.damage_bonus) {
          items.push({ 
            label: `Extra Damage ${idx + 1} Bonus`, 
            mv: extra.damage_bonus 
          });
        }
      });
    }
    
    return items;
  }, [equipment, mainHandCalc, offHandCalc]);

  // Attack actions using battlemap functionality
  const attackTarget = useCallback(async (targetId: string, slot: WeaponSlot = 'MAIN_HAND'): Promise<boolean> => {
    if (!snap.character) {
      console.warn('[useAttack] No character available for attack');
      return false;
    }
    
    return await battleAttackTarget(snap.character.uuid, targetId, slot);
  }, [snap.character, battleAttackTarget]);

  const moveAndAttackTarget = useCallback(async (targetId: string, slot: WeaponSlot = 'MAIN_HAND'): Promise<boolean> => {
    if (!snap.character) {
      console.warn('[useAttack] No character available for move-and-attack');
      return false;
    }
    
    return await battleMoveAndAttack(snap.character.uuid, targetId, slot);
  }, [snap.character, battleMoveAndAttack]);

  return {
    mainHandCalc,
    offHandCalc,
    equipment,
    dialogOpen,
    detailMode,
    itemDetailsOpen,
    weaponSelectOpen,
    availableWeapons,
    error,
    menuAnchor,
    handleOpenDialog,
    handleCloseDialog,
    handleDetailModeChange,
    handleItemDetailsOpen,
    handleWeaponSelectOpen,
    handleWeaponSelectClose,
    handleWeaponSelect,
    handleUnequipWeapon,
    handleMenuClick,
    handleMenuClose,
    clearError,
    attackTarget,
    moveAndAttackTarget,
    getWeaponName,
    getWeaponDamageExpr,
    getWeaponDamageType,
    getExtraDamageExprs,
    getComponentList,
    getDamageComponents
  };
} 