import { UUID, SensesType, Position, DeepReadonly, SensesSnapshot, EntitySummary } from './common';

// Define advantage, critical, auto-hit status enums
export enum AdvantageStatus {
  NONE = "NONE",
  ADVANTAGE = "ADVANTAGE",
  DISADVANTAGE = "DISADVANTAGE"
}

export enum CriticalStatus {
  NONE = "NONE",
  CRITICAL = "CRITICAL",
  NORMAL = "NORMAL"
}

export enum AutoHitStatus {
  NONE = "NONE",
  HIT = "HIT",
  MISS = "MISS"
}

// Condition and Duration types
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

// Common types for modifiers
export interface ScoreModifier {
  readonly name: string;
  readonly value: number;
  readonly source_entity_name?: string;
  readonly normalized_value: number;
}

// Display-oriented type to use in UI components
export interface ModifierDisplay {
  name: string;
  value: number;
  source_entity_name?: string;
}

// Display-oriented type for advantage modifiers
export interface AdvantageModifier {
  name: string;
  value: AdvantageStatus;
  source_entity_name?: string;
}

// Base modified value snapshot
export interface ModifiableValueSnapshot {
  readonly name: string;
  readonly base_value: number;
  readonly modifiers: ReadonlyArray<ScoreModifier>;
  readonly final_value: number;
  readonly normalized_value: number;
  
  // Channel information for UI rendering
  readonly channels?: ReadonlyArray<{
    readonly name: string;
    readonly normalized_value: number;
    readonly advantage_status?: string;
    readonly value_modifiers: ReadonlyArray<ScoreModifier>;
    readonly advantage_modifiers?: ReadonlyArray<AdvantageModifier>;
  }>;
  
  // Base modifier
  readonly base_modifier?: ScoreModifier;
  
  // Status effects
  readonly advantage?: AdvantageStatus;
  readonly critical?: CriticalStatus;
  readonly auto_hit?: AutoHitStatus;
  // For outgoing effects
  readonly outgoing_advantage?: AdvantageStatus;
  readonly outgoing_critical?: CriticalStatus;
  readonly outgoing_auto_hit?: AutoHitStatus;
}

// Ability Score interfaces
export interface AbilityScore {
  readonly name: string;
  readonly score: number;
  readonly normalized_value: number;
  readonly base_score: number;
  readonly modifier: number;
  readonly channels: readonly string[];
  readonly ability_score?: ModifiableValueSnapshot;
  readonly modifier_bonus?: ModifiableValueSnapshot;
}

export interface AbilityScoresSnapshot {
  readonly strength: AbilityScore;
  readonly dexterity: AbilityScore;
  readonly constitution: AbilityScore;
  readonly intelligence: AbilityScore;
  readonly wisdom: AbilityScore;
  readonly charisma: AbilityScore;
}

// Skill interfaces
export interface Skill {
  readonly name: string;
  readonly ability: string;
  readonly bonus: number;
  readonly proficient: boolean;
}

export interface SkillSetSnapshot {
  readonly skills: Readonly<Record<string, Skill>>;
}

// Detailed skill calculation snapshot
export interface SkillBonusCalculationSnapshot {
  readonly skill_name: string;
  readonly ability_name: string;

  readonly proficiency_bonus: ModifiableValueSnapshot;
  readonly normalized_proficiency_bonus: ModifiableValueSnapshot;
  readonly skill_bonus: ModifiableValueSnapshot;
  readonly ability_bonus: ModifiableValueSnapshot;
  readonly ability_modifier_bonus: ModifiableValueSnapshot;

  readonly has_cross_entity_effects: boolean;
  readonly target_entity_uuid?: string;

  readonly total_bonus: ModifiableValueSnapshot;
  readonly final_modifier: number;
}

// Equipment interfaces
export interface ArmorSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly description?: string;
  readonly type: string;
  readonly body_part: string;
  readonly ac: ModifiableValueSnapshot;
  readonly max_dex_bonus: ModifiableValueSnapshot;
  readonly strength_requirement?: number;
  readonly dexterity_requirement?: number;
  readonly intelligence_requirement?: number;
  readonly constitution_requirement?: number;
  readonly charisma_requirement?: number;
  readonly wisdom_requirement?: number;
  readonly stealth_disadvantage?: boolean;
}

export interface ShieldSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly description?: string;
  readonly ac_bonus: ModifiableValueSnapshot;
}

export interface WeaponSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly description?: string;
  readonly weapon_type: string;
  readonly properties: ReadonlyArray<string>;
  readonly damage_type: string;
  readonly damage_dice: number;
  readonly dice_numbers: number;
  readonly attack_bonus: ModifiableValueSnapshot;
  readonly damage_bonus: ModifiableValueSnapshot;
  readonly range_normal?: number;
  readonly range_long?: number;
}

export interface EquipmentSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly source_entity_uuid: UUID;
  readonly source_entity_name?: string;

  // Equipped items
  readonly helmet?: ArmorSnapshot;
  readonly body_armor?: ArmorSnapshot;
  readonly gauntlets?: ArmorSnapshot;
  readonly greaves?: ArmorSnapshot;
  readonly boots?: ArmorSnapshot;
  readonly amulet?: ArmorSnapshot;
  readonly ring_left?: ArmorSnapshot;
  readonly ring_right?: ArmorSnapshot;
  readonly cloak?: ArmorSnapshot;
  readonly weapon_main_hand?: WeaponSnapshot;
  readonly weapon_off_hand?: WeaponSnapshot;

  // Core values
  readonly unarmored_ac_type: string;
  readonly unarmored_ac: ModifiableValueSnapshot;
  readonly ac_bonus: ModifiableValueSnapshot;
  readonly damage_bonus: ModifiableValueSnapshot;
  readonly attack_bonus: ModifiableValueSnapshot;
  readonly melee_attack_bonus: ModifiableValueSnapshot;
  readonly ranged_attack_bonus: ModifiableValueSnapshot;
  readonly melee_damage_bonus: ModifiableValueSnapshot;
  readonly ranged_damage_bonus: ModifiableValueSnapshot;

  // Unarmed attack properties
  readonly unarmed_attack_bonus: ModifiableValueSnapshot;
  readonly unarmed_damage_bonus: ModifiableValueSnapshot;
  readonly unarmed_damage_type: string;
  readonly unarmed_damage_dice: number;
  readonly unarmed_dice_numbers: number;
  readonly unarmed_properties: ReadonlyArray<string>;

  // Computed total
  readonly armor_class?: number;
}

// AC Calculation interfaces
export interface ACBonusCalculationSnapshot {
  readonly is_unarmored: boolean;

  // For unarmored path
  readonly unarmored_values?: ReadonlyArray<ModifiableValueSnapshot>;
  readonly unarmored_abilities?: ReadonlyArray<string>;
  readonly ability_bonuses?: ReadonlyArray<ModifiableValueSnapshot>;
  readonly ability_modifier_bonuses?: ReadonlyArray<ModifiableValueSnapshot>;

  // For armored path
  readonly armored_values?: ReadonlyArray<ModifiableValueSnapshot>;
  readonly max_dexterity_bonus?: ModifiableValueSnapshot;
  readonly dexterity_bonus?: ModifiableValueSnapshot;
  readonly dexterity_modifier_bonus?: ModifiableValueSnapshot;
  readonly combined_dexterity_bonus?: ModifiableValueSnapshot;

  // Cross entity
  readonly has_cross_entity_effects: boolean;
  readonly target_entity_uuid?: UUID;

  // Final result
  readonly total_bonus: ModifiableValueSnapshot;
  readonly final_ac: number;
  readonly outgoing_advantage: AdvantageStatus;
  readonly outgoing_critical: CriticalStatus;
  readonly outgoing_auto_hit: AutoHitStatus;
}

// Attack calculation snapshot
export interface AttackBonusCalculationSnapshot {
  readonly weapon_slot: string;
  readonly proficiency_bonus: ModifiableValueSnapshot;
  readonly weapon_bonus: ModifiableValueSnapshot;
  readonly attack_bonuses: ReadonlyArray<ModifiableValueSnapshot>;
  readonly ability_bonuses: ReadonlyArray<ModifiableValueSnapshot>;
  readonly range: any;
  readonly weapon_name?: string;
  readonly is_unarmed: boolean;
  readonly is_ranged: boolean;
  readonly properties: ReadonlyArray<string>;
  readonly has_cross_entity_effects: boolean;
  readonly target_entity_uuid?: UUID;
  readonly total_bonus: ModifiableValueSnapshot;
  readonly final_modifier: number;
  readonly advantage_status: AdvantageStatus;
  readonly auto_hit_status: AutoHitStatus;
  readonly critical_status: CriticalStatus;
}

// Health interfaces
export interface HitDiceSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly hit_dice_value: ModifiableValueSnapshot;
  readonly hit_dice_count: ModifiableValueSnapshot;
  readonly mode: string;
  readonly ignore_first_level: boolean;
  readonly hit_points: number;
}

export interface HealthSnapshot {
  readonly hit_dices_total_hit_points: number;
  readonly total_hit_dices_number: number;
  readonly damage_taken: number;

  readonly hit_dices: ReadonlyArray<HitDiceSnapshot>;
  readonly max_hit_points_bonus: ModifiableValueSnapshot;
  readonly temporary_hit_points: ModifiableValueSnapshot;
  readonly damage_reduction: ModifiableValueSnapshot;
  readonly resistances: ReadonlyArray<{ readonly damage_type: string; readonly status: string }>;
  readonly current_hit_points?: number;
  readonly max_hit_points?: number;
}

// Saving throws
export interface SavingThrowSetSnapshot {
  readonly saving_throws: Readonly<Record<string, SavingThrowSnapshot>>;
}

export interface SavingThrowSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly ability: string;
  readonly proficiency: boolean;
  readonly bonus: ModifiableValueSnapshot;
  readonly proficiency_multiplier: number;
  readonly effective_bonus?: number;
}

export interface SavingThrowBonusCalculationSnapshot {
  readonly ability_name: string;

  readonly proficiency_bonus: ModifiableValueSnapshot;
  readonly normalized_proficiency_bonus: ModifiableValueSnapshot;
  readonly saving_throw_bonus: ModifiableValueSnapshot;
  readonly ability_bonus: ModifiableValueSnapshot;
  readonly ability_modifier_bonus: ModifiableValueSnapshot;

  readonly has_cross_entity_effects: boolean;
  readonly target_entity_uuid?: UUID;

  readonly total_bonus: ModifiableValueSnapshot;
  readonly final_modifier: number;
}

export interface NumericalModifierSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly value: number;
  readonly normalized_value: number;
  readonly source_entity_name?: string;
}

// Action economy snapshot
export interface ActionEconomySnapshot {
  readonly uuid: string;
  readonly name: string;
  readonly source_entity_uuid: string;
  readonly source_entity_name?: string;
  
  // Core action values
  readonly actions: ModifiableValueSnapshot;
  readonly bonus_actions: ModifiableValueSnapshot;
  readonly reactions: ModifiableValueSnapshot;
  readonly movement: ModifiableValueSnapshot;
  
  // Base values
  readonly base_actions: number;
  readonly base_bonus_actions: number;
  readonly base_reactions: number;
  readonly base_movement: number;
  
  // Cost modifiers
  readonly action_costs: ReadonlyArray<NumericalModifierSnapshot>;
  readonly bonus_action_costs: ReadonlyArray<NumericalModifierSnapshot>;
  readonly reaction_costs: ReadonlyArray<NumericalModifierSnapshot>;
  readonly movement_costs: ReadonlyArray<NumericalModifierSnapshot>;
  
  // Computed values
  readonly available_actions: number;
  readonly available_bonus_actions: number;
  readonly available_reactions: number;
  readonly available_movement: number;
}

// Condition interfaces
export interface ConditionSnapshot {
  readonly uuid: UUID;
  readonly name: string;
  readonly description?: string;
  readonly duration_type: string;
  readonly duration_value?: number | string;
  readonly source_entity_name?: string;
  readonly source_entity_uuid: UUID;
  readonly applied: boolean;
}

// Character interface matching EntitySnapshot
export interface Character {
  readonly uuid: UUID;
  readonly name: string;
  readonly description?: string;
  readonly target_entity_uuid?: UUID;
  readonly target_summary?: EntitySummary;
  readonly position: Position;
  readonly sprite_name?: string;
  
  // Main blocks
  readonly ability_scores: AbilityScoresSnapshot;
  readonly skill_set: SkillSetSnapshot;
  readonly equipment: EquipmentSnapshot;
  readonly senses: SensesSnapshot;
  
  // Other blocks
  readonly saving_throws: SavingThrowSetSnapshot;
  readonly health: HealthSnapshot;
  
  // Core values
  readonly proficiency_bonus: ModifiableValueSnapshot;
  readonly skill_calculations: Readonly<Record<string, SkillBonusCalculationSnapshot>>;
  readonly attack_calculations?: Readonly<Record<string, AttackBonusCalculationSnapshot>>;
  readonly saving_throw_calculations?: Readonly<Record<string, SavingThrowBonusCalculationSnapshot>>;
  readonly ac_calculation?: ACBonusCalculationSnapshot;
  readonly action_economy: ActionEconomySnapshot;

  // Active conditions
  readonly active_conditions: Readonly<Record<string, ConditionSnapshot>>;
}

// CONVERSION FUNCTIONS

/**
 * Helper function to make a position mutable if needed for API calls
 */
export function toMutablePosition(position: Position): [number, number] {
  return [...position];
}

/**
 * Helper function to make a readonly record mutable if needed for API calls
 */
export function toMutableRecord<K extends string | number | symbol, V>(
  record: Readonly<Record<K, V>>
): Record<K, V> {
  return { ...record };
}

// Item for equipment lists
export interface EquipmentItem {
  readonly uuid: string;
  readonly name: string;
  readonly description: string;
  readonly equipment_type: string;
  readonly cost_gp: number;
  readonly weight_lb: number;
  readonly rarity: string;
  readonly cursed: boolean;
  readonly source_entity_name?: string;
  readonly source_entity_uuid?: string;
  
  // Weapon properties
  readonly weapon_type?: string;
  readonly damage_type?: string;
  readonly damage_dice?: number;
  readonly dice_numbers?: number;
  readonly properties?: string[];
  readonly range_normal?: number;
  readonly range_long?: number;
  
  // Armor properties
  readonly type?: string;
  readonly body_part?: string;
  readonly ac?: ModifiableValueSnapshot;
  readonly max_dex_bonus?: ModifiableValueSnapshot;
  readonly stealth_disadvantage?: boolean;
  
  // Requirements
  readonly strength_requirement?: number;
  readonly dexterity_requirement?: number;
  readonly intelligence_requirement?: number;
  readonly constitution_requirement?: number;
  readonly charisma_requirement?: number;
  readonly wisdom_requirement?: number;
  
  // Shield properties
  readonly ac_bonus?: ModifiableValueSnapshot;
}

// Add condition request type
export interface AddConditionRequest {
  condition_type: ConditionType;
  source_entity_uuid: string;
  duration_type: DurationType;
  duration_rounds?: number;
} 