import { Direction } from '../components/battlemap/DirectionalEntitySprite';

export interface EntityDirectionState {
  directions: Record<string, Direction>;
  setDirection: (entityId: string, direction: Direction) => void;
  getDirection: (entityId: string) => Direction;
  computeDirection: (sourcePosition: [number, number], targetPosition: [number, number]) => Direction;
}

export const createEntityDirectionState = (): EntityDirectionState => {
  const directions: Record<string, Direction> = {};

  const setDirection = (entityId: string, direction: Direction) => {
    directions[entityId] = direction;
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
    if (angle >= 0 && angle < 45) return Direction.E;
    if (angle >= 45 && angle < 90) return Direction.SE;
    if (angle >= 90 && angle < 135) return Direction.S;
    if (angle >= 135 && angle < 180) return Direction.SW;
    if (angle >= 180 && angle < 225) return Direction.W;
    if (angle >= 225 && angle < 270) return Direction.NW;
    if (angle >= 270 && angle < 315) return Direction.N;
    return Direction.NE;
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