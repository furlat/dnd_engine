import axios from 'axios';
import { 
  GridSnapshot, 
  TileSummary,
  AttackResult,
  toMutablePosition
} from '../../types/battlemap_types';
import { Position, EntitySummary } from '../../types/common';

// API base URL
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

// Fetch grid snapshot
export const fetchGridSnapshot = async (): Promise<GridSnapshot> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/tiles/`);
    return response.data;
  } catch (error) {
    console.error('Error fetching grid snapshot:', error);
    throw error;
  }
};

// Fetch a specific tile
export const fetchTileAtPosition = async (x: number, y: number): Promise<TileSummary> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/tiles/position/${x}/${y}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching tile at position:', error);
    throw error;
  }
};

// Create a new tile
export const createTile = async (position: Position, tileType: 'floor' | 'wall' | 'water'): Promise<TileSummary> => {
  try {
    // Convert to mutable array for API call if necessary
    const mutablePosition = toMutablePosition(position);
    
    const response = await axios.post(`${API_BASE_URL}/tiles/`, {
      position: mutablePosition,
      tile_type: tileType
    });
    return response.data;
  } catch (error) {
    console.error('Error creating tile:', error);
    throw error;
  }
};

// Delete a tile
export const deleteTile = async (x: number, y: number): Promise<void> => {
  try {
    await axios.delete(`${API_BASE_URL}/tiles/position/${x}/${y}`);
  } catch (error) {
    console.error('Error deleting tile:', error);
    throw error;
  }
};

// Check if position is walkable
export const isPositionWalkable = async (x: number, y: number): Promise<boolean> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/tiles/walkable/${x}/${y}`);
    return response.data.walkable;
  } catch (error) {
    console.error('Error checking walkable status:', error);
    throw error;
  }
};

// Check if position is visible
export const isPositionVisible = async (x: number, y: number): Promise<boolean> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/tiles/visible/${x}/${y}`);
    return response.data.visible;
  } catch (error) {
    console.error('Error checking visible status:', error);
    throw error;
  }
};

// Move entity to a new position
export const moveEntity = async (entityId: string, position: Position): Promise<EntitySummary> => {
  try {
    // Convert to mutable array for API call if necessary
    const mutablePosition = toMutablePosition(position);
    
    const response = await axios.post(
      `${API_BASE_URL}/entities/${entityId}/move`,
      { position: mutablePosition },
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