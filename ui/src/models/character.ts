import { UUID } from './common';

// Modifier interfaces
export interface Modifier {
  uuid: UUID;
  name: string;
  value: number;
  source_entity_name?: string;
}

// Channel interfaces
export interface ModifierChannel {
  name: string;
  score: number;
  normalized_score: number;
  value_modifiers: Modifier[];
}

// Ability scores interfaces
export interface AbilityScore {
  name: string;
  score: number;
  normalized_score: number;
  base_score: number;
  modifier: number;
  channels: ModifierChannel[];
  ability_score?: ModifiableValueSnapshot;
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

// Equipment interfaces
export interface EquipmentSnapshot {
  // Basic equipment structure
  armor_class: number;
}

// Value interfaces
export interface ModifiableValueSnapshot {
  name: string;
  uuid: UUID;
  score: number;
  normalized_score: number;
  base_modifier?: Modifier;
  channels: ModifierChannel[];
}

// Health interfaces
export interface HealthSnapshot {
  hit_dices_total_hit_points: number;
  total_hit_dices_number: number;
  damage_taken: number;
}

// Saving throws
export interface SavingThrowSetSnapshot {
  // Saving throw structure
  saving_throws: Record<string, any>;
}

// Character interface matching EntitySnapshot
export interface Character {
  uuid: UUID;
  name: string;
  description?: string;
  
  // Main blocks
  ability_scores: AbilityScoresSnapshot;
  skill_set: SkillSetSnapshot;
  equipment: EquipmentSnapshot;
  
  // Other blocks
  saving_throws: SavingThrowSetSnapshot;
  health: HealthSnapshot;
  
  // Core values
  proficiency_bonus: ModifiableValueSnapshot;
} 