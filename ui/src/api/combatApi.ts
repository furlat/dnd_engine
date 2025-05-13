import axios from 'axios';
import { Character } from '../models/character';

const API_BASE_URL = 'http://localhost:8000/api';

// Common params for character fetching
const DEFAULT_INCLUDE_PARAMS = {
  include_skill_calculations: true,
  include_saving_throw_calculations: true,
  include_ac_calculation: true,
  include_attack_calculations: true,
  include_target_summary: true
};

export interface AttackResult {
  attacker: Character;
  event: any; // The event details
}

export const setEntityTarget = async (entityId: string, targetId: string): Promise<Character> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/entities/${entityId}/target/${targetId}`, null, {
      params: DEFAULT_INCLUDE_PARAMS
    });
    return response.data;
  } catch (error) {
    console.error('Error setting target:', error);
    throw error;
  }
};

export const executeAttack = async (
  entityId: string,
  targetId: string,
  weaponSlot: 'MAIN_HAND' | 'OFF_HAND' = 'MAIN_HAND',
  attackName: string = 'Attack'
): Promise<AttackResult> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/entities/${entityId}/attack/${targetId}`,
      null,
      {
        params: {
          ...DEFAULT_INCLUDE_PARAMS,
          weapon_slot: weaponSlot,
          attack_name: attackName
        }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Error executing attack:', error);
    throw error;
  }
}; 