import type {
  AbilityScore,
  AbilityScoresSnapshot,
  Skill,
  SkillSetSnapshot,
  Character,
  EntitySummary,
  HealthSnapshot,
  ActionEconomySnapshot,
  ConditionSnapshot,
  SavingThrowSetSnapshot,
  EquipmentSnapshot,
  SkillBonusCalculationSnapshot,
  SavingThrowBonusCalculationSnapshot,
  AttackBonusCalculationSnapshot,
  ACBonusCalculationSnapshot,
  SavingThrowSnapshot,
  HitDiceSnapshot
} from './character';

import type {
  Modifier,
  ModifierChannel,
  ModifiableValueSnapshot
} from './modifiers';

// Make all properties and nested arrays readonly recursively
type Primitive = string | number | boolean | undefined | null;
type DeepReadonlyArray<T> = ReadonlyArray<DeepReadonly<T>>;
type DeepReadonlyObject<T> = {
  readonly [P in keyof T]: DeepReadonly<T[P]>;
};

export type DeepReadonly<T> = T extends Primitive
  ? T
  : T extends Array<infer U>
  ? DeepReadonlyArray<U>
  : T extends Map<infer K, infer V>
  ? ReadonlyMap<DeepReadonly<K>, DeepReadonly<V>>
  : T extends Set<infer U>
  ? ReadonlySet<DeepReadonly<U>>
  : DeepReadonlyObject<T>;

// Create readonly versions of our base types
export type ReadonlyModifier = DeepReadonly<Modifier>;
export type ReadonlyModifierChannel = DeepReadonly<ModifierChannel>;
export type ReadonlyModifiableValueSnapshot = DeepReadonly<ModifiableValueSnapshot>;

// Create readonly versions of calculation types
export type ReadonlySkillBonusCalculation = DeepReadonly<SkillBonusCalculationSnapshot>;
export type ReadonlySavingThrowBonusCalculation = DeepReadonly<SavingThrowBonusCalculationSnapshot>;
export type ReadonlyAttackBonusCalculation = DeepReadonly<AttackBonusCalculationSnapshot>;
export type ReadonlyACBonusCalculation = DeepReadonly<ACBonusCalculationSnapshot>;

// Create readonly versions of our complex types
export type ReadonlyAbilityScore = DeepReadonly<AbilityScore>;
export type ReadonlyAbilityScoresSnapshot = DeepReadonly<AbilityScoresSnapshot>;
export type ReadonlySkill = DeepReadonly<Skill>;
export type ReadonlySkillSetSnapshot = DeepReadonly<SkillSetSnapshot>;
export type ReadonlyCharacter = DeepReadonly<Character>;
export type ReadonlyEntitySummary = DeepReadonly<EntitySummary>;
export type ReadonlyHealthSnapshot = DeepReadonly<HealthSnapshot>;
export type ReadonlyHitDiceSnapshot = DeepReadonly<HitDiceSnapshot>;
export type ReadonlyActionEconomySnapshot = DeepReadonly<ActionEconomySnapshot>;
export type ReadonlyConditionSnapshot = DeepReadonly<ConditionSnapshot>;
export type ReadonlySavingThrowSnapshot = DeepReadonly<SavingThrowSnapshot>;
export type ReadonlySavingThrowSetSnapshot = DeepReadonly<SavingThrowSetSnapshot>;
export type ReadonlyEquipmentSnapshot = DeepReadonly<EquipmentSnapshot>;

export interface ReadonlyDamageResistanceSnapshot {
  damage_type: string;
  status: 'Immunity' | 'Resistance' | 'Vulnerability';
} 