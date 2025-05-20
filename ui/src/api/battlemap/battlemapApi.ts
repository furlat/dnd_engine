import axios from 'axios';
import { EntitySummary } from '../../models/character';
import { TileSummary } from '../tileApi';

// API base URL
const API_BASE_URL = 'http://localhost:8000/api';

// Type for position
export type Position = [number, number];

// Response types
export interface GridSnapshot {
  width: number;
  height: number;
  tiles: Record<string, TileSummary>;
}

export interface AttackResult {
  event: any; // Event details
  attacker: any; // Updated attacker state
}

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

// Fetch grid snapshot - fixed to match tileApi.ts
export const fetchGridSnapshot = async (): Promise<GridSnapshot> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/tiles/`);
    return response.data;
  } catch (error) {
    console.error('Error fetching grid snapshot:', error);
    throw error;
  }
};

// Move entity to a new position
export const moveEntity = async (entityId: string, position: Position): Promise<EntitySummary> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/entities/${entityId}/move`,
      { position },
      { params: DEFAULT_INCLUDE_PARAMS }
    );
    return response.data;
  } catch (error) {
    console.error('Error moving entity:', error);
    throw error;
  }
};

// Set target entity
export const setTargetEntity = async (entityId: string, targetId: string | null): Promise<EntitySummary> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/entities/${entityId}/target`,
      { target_entity_uuid: targetId },
      { params: DEFAULT_INCLUDE_PARAMS }
    );
    return response.data;
  } catch (error) {
    console.error('Error setting target entity:', error);
    throw error;
  }
};

// Execute an attack from one entity to another
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

// Update entity senses
export const updateEntitySenses = async (entityId: string): Promise<void> => {
  try {
    await axios.post(`${API_BASE_URL}/entities/${entityId}/senses/update`);
  } catch (error) {
    console.error('Error updating entity senses:', error);
    throw error;
  }
};

// Get entities at a position
export const getEntitiesAtPosition = async (x: number, y: number): Promise<EntitySummary[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities/position/${x}/${y}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching entities at position:', error);
    throw error;
  }
}; 