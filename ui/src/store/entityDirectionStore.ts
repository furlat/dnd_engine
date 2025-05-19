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

    // Calculate angle in degrees (0 is east, 90 is south)
    let angle = Math.atan2(dy, dx) * (180 / Math.PI);
    if (angle < 0) angle += 360;
    
    // Map angle to direction (0-7)
    // Direction enum: SW = 0, W = 1, NW = 2, N = 3, NE = 4, E = 5, SE = 6, S = 7
    let calculatedDirection: Direction;
    
    if (angle >= 0 && angle < 45) calculatedDirection = Direction.E;
    else if (angle >= 45 && angle < 90) calculatedDirection = Direction.SE;
    else if (angle >= 90 && angle < 135) calculatedDirection = Direction.S;
    else if (angle >= 135 && angle < 180) calculatedDirection = Direction.SW;
    else if (angle >= 180 && angle < 225) calculatedDirection = Direction.W;
    else if (angle >= 225 && angle < 270) calculatedDirection = Direction.NW;
    else if (angle >= 270 && angle < 315) calculatedDirection = Direction.N;
    else calculatedDirection = Direction.NE;
    
    return calculatedDirection;
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