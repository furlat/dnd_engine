import axios from 'axios';
import { Character, EntitySummary } from '../models/character';

const API_BASE_URL = 'http://localhost:8000/api';

export interface AttackResult {
  attacker: Character;
  target: EntitySummary;
  event: any; // The event details
}

export const setEntityTarget = async (entityId: string, targetId: string): Promise<Character> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/entities/${entityId}/target/${targetId}`, null, {
      params: {
        include_skill_calculations: true,
        include_saving_throw_calculations: true,
        include_ac_calculation: true,
        include_attack_calculations: true
      }
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
      `${API_BASE_URL}/events/entity/${entityId}/attack/${targetId}`,
      null,
      {
        params: {
          weaponSlot,
          attackName,
          include_attacker: true,
          include_target: true
        }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Error executing attack:', error);
    throw error;
  }
}; 