import { Direction } from '../components/battlemap/DirectionalEntitySprite';
import { animationActions } from './animationStore';

export interface EntityDirectionState {
  directions: Record<string, Direction>;
  setDirection: (entityId: string, direction: Direction) => void;
  getDirection: (entityId: string) => Direction;
  computeDirection: (sourcePosition: [number, number], targetPosition: [number, number]) => Direction;
}

export const createEntityDirectionState = (): EntityDirectionState => {
  const directions: Record<string, Direction> = {};

  const setDirection = (entityId: string, direction: Direction) => {
    const previousDirection = directions[entityId];
    
    // Only update if the direction has changed
    if (previousDirection !== direction) {
      directions[entityId] = direction;
      
      // Notify the animation system of the direction change
      animationActions.updateEntityAnimation(entityId, direction);
      
      console.log(`[DIRECTION] Entity ${entityId} direction changed from ${previousDirection} to ${direction}`);
    }
  };

  const getDirection = (entityId: string): Direction => {
    return directions[entityId] || Direction.S; // Default to south
  };

  // Compute direction based on movement or targeting
  const computeDirection = (sourcePosition: [number, number], targetPosition: [number, number]): Direction => {
    if (!sourcePosition || !targetPosition) return Direction.S;

    const [sx, sy] = sourcePosition;
    const [tx, ty] = targetPosition;
    
    // Calculate the angle between source and target
    const dx = tx - sx;
    const dy = ty - sy;
    
    // If no movement, return current direction
    if (dx === 0 && dy === 0) return Direction.S;

    // For clarity, here's what each direction means:
    // Direction.SW (0): Target is southwest of source (bottom-left)
    // Direction.W  (1): Target is west of source (left)
    // Direction.NW (2): Target is northwest of source (top-left)
    // Direction.N  (3): Target is north of source (top)
    // Direction.NE (4): Target is northeast of source (top-right)
    // Direction.E  (5): Target is east of source (right)
    // Direction.SE (6): Target is southeast of source (bottom-right)
    // Direction.S  (7): Target is south of source (bottom)

    // Calculate angle in degrees (0 is east, 90 is south)
    // This matches the coordinate system in our grid (east is 0°, clockwise)
    let angle = Math.atan2(dy, dx) * (180 / Math.PI);
    if (angle < 0) angle += 360;
    
    // Debug logging to help diagnose direction issues
    console.debug(`[DIR-DEBUG] Direction from [${sx},${sy}] to [${tx},${ty}], dx=${dx}, dy=${dy}, angle=${angle.toFixed(1)}°`);
    
    // Map angles to directions - use 45° wedges centered on the cardinal directions
    if (angle >= 337.5 || angle < 22.5) {
      // 0° - East
      return Direction.E; // 5
    } else if (angle >= 22.5 && angle < 67.5) {
      // 45° - Southeast
      return Direction.SE; // 6
    } else if (angle >= 67.5 && angle < 112.5) {
      // 90° - South
      return Direction.S; // 7
    } else if (angle >= 112.5 && angle < 157.5) {
      // 135° - Southwest
      return Direction.SW; // 0
    } else if (angle >= 157.5 && angle < 202.5) {
      // 180° - West
      return Direction.W; // 1
    } else if (angle >= 202.5 && angle < 247.5) {
      // 225° - Northwest
      return Direction.NW; // 2
    } else if (angle >= 247.5 && angle < 292.5) {
      // 270° - North
      return Direction.N; // 3
    } else { // angle >= 292.5 && angle < 337.5
      // 315° - Northeast
      return Direction.NE; // 4
    }
  };

  return {
    directions,
    setDirection,
    getDirection,
    computeDirection
  };
};

// Create a singleton instance
export const entityDirectionState = createEntityDirectionState(); 