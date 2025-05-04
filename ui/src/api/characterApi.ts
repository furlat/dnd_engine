import axios from 'axios';
import { Character } from '../models/character';

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
    const response = await axios.get(`${API_BASE_URL}/entities/${characterId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching character ${characterId}:`, error);
    throw error;
  }
};

// Fetch character ability details (for detailed inspection)
export const fetchCharacterAbilities = async (characterId: string): Promise<Character> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/entities/${characterId}?include_skill_calculations=true`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching character abilities ${characterId}:`, error);
    throw error;
  }
}; 