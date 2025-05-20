import axios from 'axios';
import { EntitySummary } from '../models/character';
import { TileSummary } from './tileApi';

// Update to point directly to FastAPI backend
const API_BASE_URL = 'http://localhost:8000/api';

// Position type
export type Position = [number, number];

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

// Fetch entities at a specific position
export const fetchEntitiesAtPosition = async (x: number, y: number): Promise<EntitySummary[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities/position/${x}/${y}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching entities at position:', error);
    throw error;
  }
};

// Move entity to a new position
export const moveEntity = async (entityId: string, position: Position): Promise<EntitySummary> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/entities/${entityId}/move`,
      { position }
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
      { target_entity_uuid: targetId }
    );
    return response.data;
  } catch (error) {
    console.error('Error setting target entity:', error);
    throw error;
  }
};

export interface AttackResult {
  attacker: EntitySummary;
  event: any; // The event details
}

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