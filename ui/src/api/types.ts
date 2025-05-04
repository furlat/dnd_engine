import { Character, Skill } from '../models/character';

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
export interface EquipmentItem {
  id: string;
  name: string;
  type: string;
  properties: string[];
  armorClass?: number;
  damage?: string;
  weight: number;
  equipped: boolean;
}

export interface CharacterEquipment {
  armor: EquipmentItem[];
  weapons: EquipmentItem[];
  gear: EquipmentItem[];
}

// Entity-related types
export interface Entity {
  uuid: string;
  name: string;
  type: string;
} 