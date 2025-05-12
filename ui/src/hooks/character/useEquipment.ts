import { useSnapshot } from 'valtio';
import { characterStore } from '../../store/characterStore';
import type { ReadonlyEquipmentSnapshot, ReadonlyACBonusCalculation, ReadonlyAttackBonusCalculation } from '../../models/readonly';

interface EquipmentData {
  equipment: ReadonlyEquipmentSnapshot | null;
  acCalculation: ReadonlyACBonusCalculation | null;
  attackCalculations: Readonly<Record<string, ReadonlyAttackBonusCalculation>> | null;
}

export function useEquipment(): EquipmentData {
  const snap = useSnapshot(characterStore);
  return {
    equipment: snap.character?.equipment ?? null,
    acCalculation: snap.character?.ac_calculation ?? null,
    attackCalculations: snap.character?.attack_calculations ?? null
  };
} 