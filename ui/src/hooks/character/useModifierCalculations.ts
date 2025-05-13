import type { ReadonlyModifierChannel, ReadonlyModifiableValueSnapshot } from '../../models/readonly';

interface ModifierCalculations {
  getTotalValue: (channel: ReadonlyModifierChannel) => number;
  getModifierBreakdown: (score: ReadonlyModifiableValueSnapshot) => {
    rawScore: number;
    normalizedScore: number;
    baseModifier?: number;
    modifierBonusValue: number;
    calculatedModifier: number;
  };
}

export function useModifierCalculations(): ModifierCalculations {
  const getTotalValue = (channel: ReadonlyModifierChannel): number => {
    return channel.value_modifiers.reduce((sum, mod) => sum + mod.value, 0);
  };

  const getModifierBreakdown = (score: ReadonlyModifiableValueSnapshot) => {
    const rawScore = score.score;
    const normalizedScore = score.normalized_score;
    const baseModifier = score.base_modifier?.value;
    const modifierBonusValue = score.channels.reduce((sum, channel) => 
      sum + channel.value_modifiers.reduce((modSum, mod) => modSum + mod.value, 0), 
      0
    );
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