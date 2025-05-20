import axios from 'axios';
import { Position } from '../models/character';

const API_BASE_URL = 'http://localhost:8000/api';

export interface TileSummary {
  uuid: string;
  name: string;
  position: Position;
  walkable: boolean;
  visible: boolean;
  sprite_name: string | null;
}

export interface GridSnapshot {
  width: number;
  height: number;
  tiles: Record<string, TileSummary>;
}

// Fetch the entire grid
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
    const response = await axios.post(`${API_BASE_URL}/tiles/`, {
      position,
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