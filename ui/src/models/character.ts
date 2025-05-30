import {
  AdvantageStatus,
  CriticalStatus,
  AutoHitStatus
} from './modifiers';

import type {
  Modifier,
  ModifierChannel,
  ModifiableValueSnapshot
} from './modifiers';

// Type alias for UUID
export type UUID = string;

// Re-export enums as values
export { AdvantageStatus, CriticalStatus, AutoHitStatus };

// Re-export types from modifiers
export type {
  Modifier,
  ModifierChannel,
  ModifiableValueSnapshot
};

// Position type
export type Position = [number, number];

// Add SensesType enum
export enum SensesType {
    BLINDSIGHT = "Blindsight",
    DARKVISION = "Darkvision",
    TREMORSENSE = "Tremorsense",
    TRUESIGHT = "Truesight"
}

// Add SensesSnapshot interface
export interface SensesSnapshot {
    entities: Record<UUID, Position>;
    visible: Record<string, boolean>;  // Using string for tuple key since TypeScript doesn't support tuple as key
    walkable: Record<string, boolean>;
    paths: Record<string, Position[]>;
    extra_senses: SensesType[];
    position: Position;
}

// Lightweight entity summary for combat UI
export interface EntitySummary {
    uuid: UUID;
    name: string;
    current_hp: number;
    max_hp: number;
    armor_class?: number;
    target_entity_uuid?: UUID;
    position: Position;
    sprite_name?: string;
    senses: SensesSnapshot;
}

// Channel interfaces
// AbilityScore interfaces
export interface AbilityScore {
  name: string;
  score: number;
  normalized_score: number;
  base_score: number;
  modifier: number;
  channels: ModifierChannel[];
  ability_score?: ModifiableValueSnapshot;
  modifier_bonus?: ModifiableValueSnapshot;
}

export interface AbilityScoresSnapshot {
  strength: AbilityScore;
  dexterity: AbilityScore;
  constitution: AbilityScore;
  intelligence: AbilityScore;
  wisdom: AbilityScore;
  charisma: AbilityScore;
}

// Skill interfaces
export interface Skill {
  name: string;
  ability: string;
  bonus: number;
  proficient: boolean;
}

export interface SkillSetSnapshot {
  skills: Record<string, Skill>;
}

// Detailed skill calculation snapshot (mirrors backend SkillBonusCalculationSnapshot)
export interface SkillBonusCalculationSnapshot {
  skill_name: string;
  ability_name: string;

  proficiency_bonus: ModifiableValueSnapshot;
  normalized_proficiency_bonus: ModifiableValueSnapshot;
  skill_bonus: ModifiableValueSnapshot;
  ability_bonus: ModifiableValueSnapshot;
  ability_modifier_bonus: ModifiableValueSnapshot;

  has_cross_entity_effects: boolean;
  target_entity_uuid?: string;

  total_bonus: ModifiableValueSnapshot;
  final_modifier: number;
}

// Equipment interfaces
export interface ArmorSnapshot {
  uuid: UUID;
  name: string;
  description?: string;
  type: string; // ArmorType string
  body_part: string; // BodyPart string
  ac: ModifiableValueSnapshot;
  max_dex_bonus: ModifiableValueSnapshot;
  strength_requirement?: number;
  dexterity_requirement?: number;
  intelligence_requirement?: number;
  constitution_requirement?: number;
  charisma_requirement?: number;
  wisdom_requirement?: number;
  stealth_disadvantage?: boolean;
}

export interface ShieldSnapshot {
  uuid: UUID;
  name: string;
  description?: string;
  ac_bonus: ModifiableValueSnapshot;
}

export interface EquipmentSnapshot {
  uuid: UUID;
  name: string;
  source_entity_uuid: UUID;
  source_entity_name?: string;

  // Equipped items
  helmet?: ArmorSnapshot;
  body_armor?: ArmorSnapshot;
  gauntlets?: ArmorSnapshot;
  greaves?: ArmorSnapshot;
  boots?: ArmorSnapshot;
  amulet?: ArmorSnapshot;
  ring_left?: ArmorSnapshot;
  ring_right?: ArmorSnapshot;
  cloak?: ArmorSnapshot;
  weapon_main_hand?: any; // For now, leaving weapon snapshots untyped
  weapon_off_hand?: any;

  // Core values
  unarmored_ac_type: string;
  unarmored_ac: ModifiableValueSnapshot;
  ac_bonus: ModifiableValueSnapshot;
  damage_bonus: ModifiableValueSnapshot;
  attack_bonus: ModifiableValueSnapshot;
  melee_attack_bonus: ModifiableValueSnapshot;
  ranged_attack_bonus: ModifiableValueSnapshot;
  melee_damage_bonus: ModifiableValueSnapshot;
  ranged_damage_bonus: ModifiableValueSnapshot;

  // Unarmed attack properties and other
  unarmed_attack_bonus: ModifiableValueSnapshot;
  unarmed_damage_bonus: ModifiableValueSnapshot;
  unarmed_damage_type: string;
  unarmed_damage_dice: number;
  unarmed_dice_numbers: number;
  unarmed_properties: string[];

  // Computed total
  armor_class?: number;
}

// AC Calculation interfaces mirroring backend ACBonusCalculationSnapshot
export interface ACBonusCalculationSnapshot {
  is_unarmored: boolean;

  // For unarmored path
  unarmored_values?: ModifiableValueSnapshot[];
  unarmored_abilities?: string[];
  ability_bonuses?: ModifiableValueSnapshot[];
  ability_modifier_bonuses?: ModifiableValueSnapshot[];

  // For armored path
  armored_values?: ModifiableValueSnapshot[];
  max_dexterity_bonus?: ModifiableValueSnapshot;
  dexterity_bonus?: ModifiableValueSnapshot;
  dexterity_modifier_bonus?: ModifiableValueSnapshot;
  combined_dexterity_bonus?: ModifiableValueSnapshot;

  // Cross entity
  has_cross_entity_effects: boolean;
  target_entity_uuid?: UUID;

  // Final result
  total_bonus: ModifiableValueSnapshot;
  final_ac: number;
  outgoing_advantage: AdvantageStatus;
  outgoing_critical: CriticalStatus;
  outgoing_auto_hit: AutoHitStatus;
}

// Attack calculation snapshot (mirrors backend AttackBonusCalculationSnapshot)
export interface AttackBonusCalculationSnapshot {
  weapon_slot: string; // 'MAIN_HAND' or 'OFF_HAND'
  proficiency_bonus: ModifiableValueSnapshot;
  weapon_bonus: ModifiableValueSnapshot;
  attack_bonuses: ModifiableValueSnapshot[];
  ability_bonuses: ModifiableValueSnapshot[];
  range: any;
  weapon_name?: string;
  is_unarmed: boolean;
  is_ranged: boolean;
  properties: string[];
  has_cross_entity_effects: boolean;
  target_entity_uuid?: UUID;
  total_bonus: ModifiableValueSnapshot;
  final_modifier: number;
  advantage_status: AdvantageStatus;
  auto_hit_status: AutoHitStatus;
  critical_status: CriticalStatus;
}

// Health interfaces
export interface HitDiceSnapshot {
  uuid: UUID;
  name: string;
  hit_dice_value: ModifiableValueSnapshot;
  hit_dice_count: ModifiableValueSnapshot;
  mode: string;
  ignore_first_level: boolean;
  hit_points: number;
}

export interface HealthSnapshot {
  hit_dices_total_hit_points: number;
  total_hit_dices_number: number;
  damage_taken: number;

  hit_dices: HitDiceSnapshot[];
  max_hit_points_bonus: ModifiableValueSnapshot;
  temporary_hit_points: ModifiableValueSnapshot;
  damage_reduction: ModifiableValueSnapshot;
  resistances: { damage_type: string; status: string }[];
  current_hit_points?: number;
  max_hit_points?: number;
}

// Saving throws
export interface SavingThrowSetSnapshot {
  saving_throws: Record<string, SavingThrowSnapshot>;
}

export interface SavingThrowSnapshot {
  uuid: UUID;
  name: string;
  ability: string;
  proficiency: boolean;
  bonus: ModifiableValueSnapshot;
  proficiency_multiplier: number;
  effective_bonus?: number;
}

export interface SavingThrowBonusCalculationSnapshot {
  ability_name: string;

  proficiency_bonus: ModifiableValueSnapshot;
  normalized_proficiency_bonus: ModifiableValueSnapshot;
  saving_throw_bonus: ModifiableValueSnapshot;
  ability_bonus: ModifiableValueSnapshot;
  ability_modifier_bonus: ModifiableValueSnapshot;

  has_cross_entity_effects: boolean;
  target_entity_uuid?: UUID;

  total_bonus: ModifiableValueSnapshot;
  final_modifier: number;
}

export interface NumericalModifierSnapshot {
  uuid: UUID;
  name: string;
  value: number;
  normalized_value: number;
  source_entity_name?: string;
}

// Action economy snapshot
export interface ActionEconomySnapshot {
  uuid: string;
  name: string;
  source_entity_uuid: string;
  source_entity_name?: string;
  
  // Core action values
  actions: ModifiableValueSnapshot;
  bonus_actions: ModifiableValueSnapshot;
  reactions: ModifiableValueSnapshot;
  movement: ModifiableValueSnapshot;
  
  // Base values
  base_actions: number;
  base_bonus_actions: number;
  base_reactions: number;
  base_movement: number;
  
  // Cost modifiers
  action_costs: NumericalModifierSnapshot[];
  bonus_action_costs: NumericalModifierSnapshot[];
  reaction_costs: NumericalModifierSnapshot[];
  movement_costs: NumericalModifierSnapshot[];
  
  // Computed values
  available_actions: number;
  available_bonus_actions: number;
  available_reactions: number;
  available_movement: number;
}

// Add the condition interfaces
export interface ConditionSnapshot {
  uuid: UUID;
  name: string;
  description?: string;
  duration_type: string;  // 'rounds' | 'permanent' | 'until_long_rest' | 'on_condition'
  duration_value?: number | string;  // number for rounds, string for on_condition
  source_entity_name?: string;
  source_entity_uuid: UUID;
  applied: boolean;
}

// Add condition enums
export enum ConditionType {
    BLINDED = "BLINDED",
    CHARMED = "CHARMED",
    DASHING = "DASHING",
    DEAFENED = "DEAFENED",
    DODGING = "DODGING",
    FRIGHTENED = "FRIGHTENED",
    GRAPPLED = "GRAPPLED",
    INCAPACITATED = "INCAPACITATED",
    INVISIBLE = "INVISIBLE",
    PARALYZED = "PARALYZED",
    POISONED = "POISONED",
    PRONE = "PRONE",
    RESTRAINED = "RESTRAINED",
    STUNNED = "STUNNED",
    UNCONSCIOUS = "UNCONSCIOUS"
}

export enum DurationType {
    ROUNDS = "rounds",
    PERMANENT = "permanent",
    UNTIL_LONG_REST = "until_long_rest",
    ON_CONDITION = "on_condition"
}

// Character interface matching EntitySnapshot
export interface Character {
  uuid: UUID;
  name: string;
  description?: string;
  target_entity_uuid?: UUID;
  target_summary?: EntitySummary;
  position: Position;
  sprite_name?: string;
  
  // Main blocks
  ability_scores: AbilityScoresSnapshot;
  skill_set: SkillSetSnapshot;
  equipment: EquipmentSnapshot;
  senses: SensesSnapshot;
  
  // Other blocks
  saving_throws: SavingThrowSetSnapshot;
  health: HealthSnapshot;
  
  // Core values
  proficiency_bonus: ModifiableValueSnapshot;
  skill_calculations: Record<string, SkillBonusCalculationSnapshot>;
  attack_calculations?: Record<string, AttackBonusCalculationSnapshot>;
  saving_throw_calculations?: Record<string, SavingThrowBonusCalculationSnapshot>;
  ac_calculation?: ACBonusCalculationSnapshot;
  action_economy: ActionEconomySnapshot;

  // Active conditions
  active_conditions: Record<string, ConditionSnapshot>;
} 