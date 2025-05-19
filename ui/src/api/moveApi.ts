import axios from 'axios';
import { EventData } from './combatApi';

const API_BASE_URL = 'http://localhost:8000/api';

// Define the movement result interface
export interface MoveResult {
  event: EventData;
  position: [number, number];
}

/**
 * Move an entity to a new position
 * @param entityId The UUID of the entity to move
 * @param position The target position as [x, y] coordinates
 * @returns Promise resolving to the movement result containing the event and final position
 */
export const moveEntity = async (
  entityId: string,
  position: [number, number]
): Promise<MoveResult> => {
  try {
    const startTime = performance.now();
    console.log(`[MOVE-API] Moving entity ${entityId} to position [${position}]`);
    
    const response = await axios.post(
      `${API_BASE_URL}/entities/${entityId}/move`,
      { position },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );
    
    const endTime = performance.now();
    console.log(`[MOVE-API] Move request completed in ${(endTime - startTime).toFixed(2)}ms`);
    
    return response.data;
  } catch (error) {
    console.error('[MOVE-API] Error moving entity:', error);
    throw error;
  }
}; 