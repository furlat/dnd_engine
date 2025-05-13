import { Character, Skill } from '../models/character';
import { ModifiableValueSnapshot } from '../api/values';

// API response types
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

// Skill-related types
export interface SkillBonusCalculationResult {
  total: number;
  base: number;
  abilityModifier: number;
  proficiencyBonus: number;
  otherModifiers: Array<{
    source: string;
    value: number;
  }>;
}

// Equipment-related types
export interface RangeSnapshot {
  type: 'RANGE' | 'REACH';
  normal: number;
  long?: number;
}

export interface DamageSnapshot {
  uuid: string;
  name: string;
  damage_dice: number;
  dice_numbers: number;
  damage_bonus?: ModifiableValueSnapshot;
  damage_type: string;
  source_entity_uuid: string;
  target_entity_uuid?: string;
}

export interface WeaponSnapshot {
  type: 'Weapon';
  uuid: string;
  name: string;
  description?: string;
  damage_dice: number;
  dice_numbers: number;
  damage_type: string;
  damage_bonus?: ModifiableValueSnapshot;
  attack_bonus: ModifiableValueSnapshot;
  range: RangeSnapshot;
  properties: string[];
  extra_damages: DamageSnapshot[];
}

export interface ShieldSnapshot {
  type: 'Shield';
  uuid: string;
  name: string;
  description?: string;
  ac_bonus: ModifiableValueSnapshot;
}

export interface ArmorSnapshot {
  type: 'Armor';
  uuid: string;
  name: string;
  description?: string;
  armor_type: string;
  body_part: string;
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

export type EquipmentItem = WeaponSnapshot | ArmorSnapshot | ShieldSnapshot;

// Entity-related types
export interface Entity {
  uuid: string;
  name: string;
  type: string;
}

// Common types used across the API
export type Position = [number, number];

// Add other common types here as needed 