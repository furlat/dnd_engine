import axios from 'axios';
import { 
  GridSnapshot, 
  TileSummary,
  AttackResult,
  AttackResponse,
  toMutablePosition,
  SpriteFolderName,
  AnimationState,
  EntitySpriteMapping,
  Direction,
  MovementResponse
} from '../../types/battlemap_types';
import { Position, EntitySummary } from '../../types/common';
import { TileType } from '../../hooks/battlemap';

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
export const createTile = async (position: Position, tileType: TileType): Promise<TileSummary> => {
  try {
    // Convert to mutable array for API call if necessary
    const mutablePosition = toMutablePosition(position);
    
    // Ensure we're not sending "erase" as a tile type to the API
    const apiTileType = tileType === 'erase' ? 'floor' : tileType;
    
    const response = await axios.post(`${API_BASE_URL}/tiles/`, {
      position: mutablePosition,
      tile_type: apiTileType
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

/**
 * Move an entity to a new position
 * @param entityId The UUID of the entity to move
 * @param position The target position [x, y]
 * @param includePathSenses Whether to include senses data for each position in the path (default: true for debugging)
 * @returns Promise<EntitySummary> The updated entity summary
 */
export const moveEntity = async (
  entityId: string, 
  position: Position, 
  includePathSenses: boolean = true
): Promise<EntitySummary> => {
  const response = await fetch(`/api/entities/${entityId}/move`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      position: position,
      include_paths_senses: includePathSenses
    }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail?.message || `Failed to move entity: ${response.statusText}`);
  }

  const movementResponse: MovementResponse = await response.json();
  
  // NEW: Store path senses data in the store if available
  if (movementResponse.path_senses && Object.keys(movementResponse.path_senses).length > 0) {
    console.log(`[moveEntity] Received path senses for ${Object.keys(movementResponse.path_senses).length} positions:`, movementResponse.path_senses);
    
    // Import battlemapActions dynamically to avoid circular imports
    const { battlemapActions } = await import('../../store/battlemapStore');
    battlemapActions.setEntityPathSenses(entityId, movementResponse.path_senses);
  }
  
  return movementResponse.entity;
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
): Promise<AttackResponse> => {
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

// Sprite folder discovery - attempts to load available entity sprite folders
export const discoverAvailableSpriteFolders = async (): Promise<SpriteFolderName[]> => {
  // This is a list of known sprite folders from your assets
  // In a real app, you might have an API endpoint that lists these
  const knownFolders = [
    '1Brute', '1Ogre', '2Archer', '2DeathLord', '2Golem',
    '3DarkKnight', '3Nomad', '3Wizard', '4Berserker', '4Berserker_undead',
    '5Archer', '5BarbArcher', '5CamoArcher', '6Barbarian', '6Mage', '6Warrior',
    '7BowMan', '7DarkArcher', '8DarkLord', '8Necromancer', '8Witchdoctor',
    '9Longbow', '9Shaman', '9Wizard', 'chainsaw_ork',
    'CityZombie 1', 'CityZombie 2', 'CityZombie 3', 'CityZombie 5',
    'RuralZombie 1', 'RuralZombie 2', 'RuralZombie 3', 'RuralZombie 4', 'RuralZombie 5',
    'ZombieFemale1', 'ZombieFemale2', 'ZombieFemale3', 'ZombieFemale4', 'ZombieFemale5', 'ZombieFemale6', 'ZombieFemale7',
    'ZombieHulk1', 'ZombieHulk2',
    'ZombieMale1', 'ZombieMale2', 'ZombieMale3', 'ZombieMale4', 'ZombieMale5', 'ZombieMale6', 'ZombieMale7', 'ZombieMale8', 'ZombieMale9',
    'ZombieMonster1', 'ZombieMonster2', 'ZombieMonster3',
    'ZombieRadioactive1', 'ZombieRadioactive2', 'ZombieRadioactive3'
  ];

  const validFolders: SpriteFolderName[] = [];

  // Test each folder by trying to load the Idle.json sprite sheet
  for (const folder of knownFolders) {
    try {
      const testUrl = `/assets/entities/${folder}/Idle.json`;
      const response = await fetch(testUrl, { method: 'HEAD' });
      if (response.ok) {
        validFolders.push(folder);
      }
    } catch (error) {
      // Folder doesn't exist or sprite sheet missing, skip
      console.warn(`Sprite folder ${folder} not accessible:`, error);
    }
  }

  console.log(`[API] Discovered ${validFolders.length} valid sprite folders:`, validFolders);
  return validFolders;
};

// Get sprite sheet path for entity
export const getSpriteSheetPath = (spriteFolder: string, animation: AnimationState): string => {
  return `/assets/entities/${spriteFolder}/${animation}.json`;
};

// Refresh action economy for an entity (battlemap-specific)
export const refreshEntityActionEconomy = async (entityId: string): Promise<EntitySummary> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/entities/${entityId}/action-economy/refresh`,
      null,
      { params: DEFAULT_INCLUDE_PARAMS }
    );
    return response.data;
  } catch (error) {
    console.error('Error refreshing entity action economy:', error);
    throw error;
  }
}; 