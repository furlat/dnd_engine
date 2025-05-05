import axios from 'axios';
import { Character, ConditionType, DurationType } from '../models/character';
import { EquipmentItem } from './types';

// Update to point directly to FastAPI backend
const API_BASE_URL = 'http://localhost:8000/api';

// Fetch all characters
export const fetchCharacters = async (): Promise<Character[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities`);
    return response.data;
  } catch (error) {
    console.error('Error fetching characters:', error);
    throw error;
  }
};

// Fetch a single character by ID
export const fetchCharacter = async (characterId: string): Promise<Character> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities/${characterId}`, {
      params: {
        include_skill_calculations: true,
        include_saving_throw_calculations: true,
        include_ac_calculation: true,
        include_attack_calculations: true
      }
    });
    return response.data;
  } catch (error) {
    console.error(`Error fetching character ${characterId}:`, error);
    throw error;
  }
};

// Fetch character ability details (for detailed inspection)
export const fetchCharacterAbilities = async (characterId: string): Promise<Character> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities/${characterId}`, {
      params: {
        include_skill_calculations: true,
        include_saving_throw_calculations: true,
        include_ac_calculation: true,
        include_attack_calculations: true
      }
    });
    return response.data;
  } catch (error) {
    console.error(`Error fetching character abilities ${characterId}:`, error);
    throw error;
  }
};

// Equipment-related functions
export const fetchAllEquipment = async (sourceEntityUuid?: string): Promise<EquipmentItem[]> => {
  try {
    console.log('Fetching equipment with source entity:', sourceEntityUuid);
    const response = await axios.get(`${API_BASE_URL}/equipment`, {
      params: {
        source_entity_uuid: sourceEntityUuid
      }
    });
    console.log('Equipment API response:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error fetching equipment:', error);
    throw error;
  }
};

export const equipItem = async (characterId: string, equipmentId: string, slot: string): Promise<Character> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/entities/${characterId}/equip`, {
      equipment_uuid: equipmentId,
      slot: slot
    });
    return response.data;
  } catch (error) {
    console.error('Error equipping item:', error);
    throw error;
  }
};

export const unequipItem = async (characterId: string, slot: string): Promise<Character> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/entities/${characterId}/unequip/${slot}`);
    return response.data;
  } catch (error) {
    console.error('Error unequipping item:', error);
    throw error;
  }
};

// Add condition request type
interface AddConditionRequest {
  condition_type: ConditionType;
  source_entity_uuid: string;
  duration_type: DurationType;
  duration_rounds?: number;
}

// Add condition management functions
export const addCondition = async (entityId: string, request: AddConditionRequest): Promise<Character> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/entities/${entityId}/conditions`, request);
    return response.data;
  } catch (error) {
    console.error('Error adding condition:', error);
    throw error;
  }
};

export const removeCondition = async (entityId: string, conditionName: string): Promise<Character> => {
  try {
    const response = await axios.delete(`${API_BASE_URL}/entities/${entityId}/conditions/${conditionName}`);
    return response.data;
  } catch (error) {
    console.error('Error removing condition:', error);
    throw error;
  }
}; 