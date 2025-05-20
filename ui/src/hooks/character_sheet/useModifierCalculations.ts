import { ModifiableValueSnapshot } from '../../types/characterSheet_types';

// Define channel type needed for calculations
interface ModifierChannel {
  readonly value_modifiers: ReadonlyArray<{
    readonly value: number;
  }>;
}

interface ModifierCalculations {
  getTotalValue: (channel: ModifierChannel) => number;
  getModifierBreakdown: (score: ModifiableValueSnapshot) => {
    rawScore: number;
    normalizedScore: number;
    baseModifier?: number;
    modifierBonusValue: number;
    calculatedModifier: number;
  };
}

export function useModifierCalculations(): ModifierCalculations {
  const getTotalValue = (channel: ModifierChannel): number => {
    return channel.value_modifiers.reduce((sum: number, mod: { value: number }) => sum + mod.value, 0);
  };

  const getModifierBreakdown = (score: ModifiableValueSnapshot) => {
    const rawScore = score.base_value;
    const normalizedScore = score.normalized_value;
    const baseModifier = score.base_modifier?.value;
    const modifierBonusValue = score.channels?.reduce((sum: number, channel: ModifierChannel) => 
      sum + channel.value_modifiers.reduce((modSum: number, mod: { value: number }) => modSum + mod.value, 0), 
      0
    ) || 0;
    const calculatedModifier = normalizedScore + modifierBonusValue;

    return {
      rawScore,
      normalizedScore,
      baseModifier,
      modifierBonusValue,
      calculatedModifier
    };
  };

  return {
    getTotalValue,
    getModifierBreakdown
  };
} 