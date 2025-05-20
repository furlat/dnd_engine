import axios from 'axios';
import { Character, ConditionType, DurationType, EntitySummary } from '../../models/character';
import { EquipmentItem } from '../types';

// Update to point directly to FastAPI backend
const API_BASE_URL = 'http://localhost:8000/api';

// Common params for character fetching
const DEFAULT_INCLUDE_PARAMS = {
  include_skill_calculations: true,
  include_saving_throw_calculations: true,
  include_ac_calculation: true,
  include_attack_calculations: true,
  include_target_summary: true
};

// Fetch all entity summaries (lightweight version)
export const fetchEntitySummaries = async (): Promise<EntitySummary[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities/summaries`);
    return response.data;
  } catch (error) {
    console.error('Error fetching entity summaries:', error);
    throw error;
  }
};

// Fetch all characters
export const fetchCharacters = async (): Promise<Character[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities`, {
      params: DEFAULT_INCLUDE_PARAMS
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching characters:', error);
    throw error;
  }
};

// Fetch a single character by ID with full details
export const fetchCharacter = async (characterId: string): Promise<Character> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities/${characterId}`, {
      params: DEFAULT_INCLUDE_PARAMS
    });
    return response.data;
  } catch (error) {
    console.error(`Error fetching character ${characterId}:`, error);
    throw error;
  }
};

// Equipment-related functions
export const fetchAllEquipment = async (sourceEntityUuid?: string): Promise<EquipmentItem[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/equipment`, {
      params: {
        source_entity_uuid: sourceEntityUuid
      }
    });
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
    }, {
      params: DEFAULT_INCLUDE_PARAMS
    });
    return response.data;
  } catch (error) {
    console.error('Error equipping item:', error);
    throw error;
  }
};

export const unequipItem = async (characterId: string, slot: string): Promise<Character> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/entities/${characterId}/unequip/${slot}`, null, {
      params: DEFAULT_INCLUDE_PARAMS
    });
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
    const response = await axios.post(`${API_BASE_URL}/entities/${entityId}/conditions`, request, {
      params: DEFAULT_INCLUDE_PARAMS
    });
    return response.data;
  } catch (error) {
    console.error('Error adding condition:', error);
    throw error;
  }
};

export const refreshActionEconomy = async (entityId: string): Promise<Character> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/entities/${entityId}/action-economy/refresh`, null, {
      params: DEFAULT_INCLUDE_PARAMS
    });
    return response.data;
  } catch (error) {
    console.error('Error refreshing action economy:', error);
    throw error;
  }
};

export const removeCondition = async (entityId: string, conditionName: string): Promise<Character> => {
  try {
    const response = await axios.delete(`${API_BASE_URL}/entities/${entityId}/conditions/${conditionName}`, {
      params: DEFAULT_INCLUDE_PARAMS
    });
    return response.data;
  } catch (error) {
    console.error('Error removing condition:', error);
    throw error;
  }
};

export async function modifyHealth(characterId: string, amount: number): Promise<Character> {
  const response = await axios.post(`${API_BASE_URL}/characters/${characterId}/health/modify`, { amount }, {
    params: DEFAULT_INCLUDE_PARAMS
  });
  return response.data;
}

export async function applyTemporaryHP(characterId: string, amount: number): Promise<Character> {
  const response = await axios.post(`${API_BASE_URL}/characters/${characterId}/health/temporary`, { amount }, {
    params: DEFAULT_INCLUDE_PARAMS
  });
  return response.data;
} 