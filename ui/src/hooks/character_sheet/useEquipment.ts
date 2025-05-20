import { useSnapshot } from 'valtio';
import { useMemo } from 'react';
import { characterSheetStore } from '../../store/characterSheetStore';
import type { 
  ReadonlyEquipmentSnapshot, 
  ReadonlyACBonusCalculation, 
  ReadonlyAttackBonusCalculation,
  ReadonlyModifiableValueSnapshot
} from '../../models/readonly';

interface EquipmentStats {
  bodyArmorName: string;
  shieldName: string | null;
  armorClass: number;
  isUnarmored: boolean;
}

interface EquipmentData {
  // Data from store
  equipment: ReadonlyEquipmentSnapshot | null;
  acCalculation: ReadonlyACBonusCalculation | null;
  attackCalculations: Readonly<Record<string, ReadonlyAttackBonusCalculation>> | null;
  // Computed values
  stats: EquipmentStats | null;
  // Helper functions
  getArmorClassBreakdown: () => {
    baseAC: number;
    dexBonus: number;
    shieldBonus: number;
    otherBonuses: number;
    total: number;
  } | null;
  renderModifierChannels: (mv: ReadonlyModifiableValueSnapshot | undefined | null) => {
    name: string;
    total: number;
    modifiers: Array<{
      name: string;
      value: number;
      sourceName?: string;
    }>;
  } | null;
}

export function useEquipment(): EquipmentData {
  const snap = useSnapshot(characterSheetStore);

  // Computed stats
  const stats = useMemo((): EquipmentStats | null => {
    const equipment = snap.character?.equipment;
    if (!equipment) return null;

    return {
      bodyArmorName: equipment.body_armor ? equipment.body_armor.name : equipment.unarmored_ac_type,
      shieldName: equipment.weapon_off_hand && (equipment.weapon_off_hand as any).ac_bonus ? 
        (equipment.weapon_off_hand as any).name : null,
      armorClass: equipment.armor_class ?? 0,
      isUnarmored: !equipment.body_armor
    };
  }, [snap.character?.equipment]);

  // Helper function to get AC breakdown
  const getArmorClassBreakdown = useMemo(() => () => {
    const acCalc = snap.character?.ac_calculation;
    if (!acCalc) return null;

    const baseAC = acCalc.is_unarmored ? 
      (acCalc.unarmored_values?.reduce((sum, mv) => sum + mv.normalized_score, 0) ?? 0) :
      (acCalc.armored_values?.reduce((sum, mv) => sum + mv.normalized_score, 0) ?? 0);

    const dexBonus = acCalc.combined_dexterity_bonus?.normalized_score ?? 0;
    
    // Get total bonus from total_bonus field
    const totalBonus = acCalc.total_bonus?.normalized_score ?? 0;
    const shieldBonus = 0; // Shield bonus is included in total_bonus
    const otherBonuses = totalBonus - baseAC - dexBonus - shieldBonus;

    return {
      baseAC,
      dexBonus,
      shieldBonus,
      otherBonuses,
      total: acCalc.final_ac
    };
  }, [snap.character?.ac_calculation]);

  // Helper function to process modifier channels
  const renderModifierChannels = useMemo(() => (mv: ReadonlyModifiableValueSnapshot | undefined | null) => {
    if (!mv || !mv.channels) return null;

    const modifiers = mv.channels.flatMap(ch => 
      ch.value_modifiers.map(mod => ({
        name: mod.name,
        value: mod.value,
        sourceName: mod.source_entity_name
      }))
    );

    return {
      name: mv.name,
      total: mv.normalized_score,
      modifiers
    };
  }, []);

  return {
    equipment: snap.character?.equipment ?? null,
    acCalculation: snap.character?.ac_calculation ?? null,
    attackCalculations: snap.character?.attack_calculations ?? null,
    stats,
    getArmorClassBreakdown,
    renderModifierChannels
  };
} 