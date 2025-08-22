import { Direction } from '../../../types/battlemap_types';
import { Position } from '../../../types/common';

/**
 * Direction conversion utilities extracted from IsometricEntityRenderer
 * Following the exact structure from animation_refactor_guide.md
 */
export class DirectionUtils {
  /**
   * Convert absolute direction to isometric direction
   * In isometric view, absolute North appears as NE, East as SE, etc.
   * This accounts for the 45-degree rotation of the isometric perspective
   */
  static convertToIsometricDirection(absoluteDirection: Direction): Direction {
    const directionMap: Record<Direction, Direction> = {
      [Direction.N]: Direction.NE,   // North becomes Northeast
      [Direction.NE]: Direction.E,   // Northeast becomes East
      [Direction.E]: Direction.SE,   // East becomes Southeast
      [Direction.SE]: Direction.S,   // Southeast becomes South
      [Direction.S]: Direction.SW,   // South becomes Southwest
      [Direction.SW]: Direction.W,   // Southwest becomes West
      [Direction.W]: Direction.NW,   // West becomes Northwest
      [Direction.NW]: Direction.N    // Northwest becomes North
    };
    
    return directionMap[absoluteDirection];
  }
  
  /**
   * Convert isometric direction back to absolute direction
   */
  static convertFromIsometricDirection(isometricDirection: Direction): Direction {
    const directionMap: Record<Direction, Direction> = {
      [Direction.NE]: Direction.N,   // Northeast becomes North
      [Direction.E]: Direction.NE,   // East becomes Northeast
      [Direction.SE]: Direction.E,   // Southeast becomes East
      [Direction.S]: Direction.SE,   // South becomes Southeast
      [Direction.SW]: Direction.S,   // Southwest becomes South
      [Direction.W]: Direction.SW,   // West becomes Southwest
      [Direction.NW]: Direction.W,   // Northwest becomes West
      [Direction.N]: Direction.NW    // North becomes Northwest
    };
    
    return directionMap[isometricDirection];
  }
  
  /**
   * Compute direction from one position to another (returns grid direction)
   */
  static computeDirection(fromPos: readonly [number, number], toPos: readonly [number, number]): Direction {
    const [fromX, fromY] = fromPos;
    const [toX, toY] = toPos;
    
    const dx = toX - fromX;
    const dy = toY - fromY;
    
    if (dx > 0 && dy > 0) return Direction.SE;
    if (dx > 0 && dy < 0) return Direction.NE;
    if (dx < 0 && dy > 0) return Direction.SW;
    if (dx < 0 && dy < 0) return Direction.NW;
    if (dx === 0 && dy > 0) return Direction.S;
    if (dx === 0 && dy < 0) return Direction.N;
    if (dx > 0 && dy === 0) return Direction.E;
    if (dx < 0 && dy === 0) return Direction.W;
    
    return Direction.S; // Default
  }
  
  /**
   * Get the opposite direction for dodge movement
   */
  static getOppositeDirection(direction: Direction): Direction {
    const opposites: Record<Direction, Direction> = {
      [Direction.N]: Direction.S,
      [Direction.NE]: Direction.SW,
      [Direction.E]: Direction.W,
      [Direction.SE]: Direction.NW,
      [Direction.S]: Direction.N,
      [Direction.SW]: Direction.NE,
      [Direction.W]: Direction.E,
      [Direction.NW]: Direction.SE
    };
    
    return opposites[direction];
  }
  
  /**
   * Get position offset by distance in a given direction
   */
  static getAdjacentPosition(
    position: readonly [number, number], 
    direction: Direction, 
    distance: number = 0.25
  ): readonly [number, number] {
    const [x, y] = position;
    
    switch (direction) {
      case Direction.N:  return [x, y - distance];
      case Direction.NE: return [x + distance, y - distance];
      case Direction.E:  return [x + distance, y];
      case Direction.SE: return [x + distance, y + distance];
      case Direction.S:  return [x, y + distance];
      case Direction.SW: return [x - distance, y + distance];
      case Direction.W:  return [x - distance, y];
      case Direction.NW: return [x - distance, y - distance];
      default: return position;
    }
  }
  
  /**
   * Calculate distance between two positions
   */
  static calculateDistance(pos1: readonly [number, number], pos2: readonly [number, number]): number {
    const [x1, y1] = pos1;
    const [x2, y2] = pos2;
    return Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
  }
  
  /**
   * Get all 8 directions as an array
   */
  static getAllDirections(): Direction[] {
    return Object.values(Direction);
  }
  
  /**
   * Check if direction is diagonal
   */
  static isDiagonal(direction: Direction): boolean {
    return [Direction.NE, Direction.SE, Direction.SW, Direction.NW].includes(direction);
  }
  
  /**
   * Check if direction is cardinal (N, S, E, W)
   */
  static isCardinal(direction: Direction): boolean {
    return [Direction.N, Direction.S, Direction.E, Direction.W].includes(direction);
  }
  
  /**
   * Get direction angle in degrees (0 = North, 90 = East, etc.)
   */
  static getDirectionAngle(direction: Direction): number {
    const angles: Record<Direction, number> = {
      [Direction.N]: 0,
      [Direction.NE]: 45,
      [Direction.E]: 90,
      [Direction.SE]: 135,
      [Direction.S]: 180,
      [Direction.SW]: 225,
      [Direction.W]: 270,
      [Direction.NW]: 315
    };
    
    return angles[direction];
  }
  
  /**
   * Get direction from angle in degrees
   */
  static getDirectionFromAngle(angle: number): Direction {
    // Normalize angle to 0-360 range
    const normalizedAngle = ((angle % 360) + 360) % 360;
    
    if (normalizedAngle >= 337.5 || normalizedAngle < 22.5) return Direction.N;
    if (normalizedAngle >= 22.5 && normalizedAngle < 67.5) return Direction.NE;
    if (normalizedAngle >= 67.5 && normalizedAngle < 112.5) return Direction.E;
    if (normalizedAngle >= 112.5 && normalizedAngle < 157.5) return Direction.SE;
    if (normalizedAngle >= 157.5 && normalizedAngle < 202.5) return Direction.S;
    if (normalizedAngle >= 202.5 && normalizedAngle < 247.5) return Direction.SW;
    if (normalizedAngle >= 247.5 && normalizedAngle < 292.5) return Direction.W;
    if (normalizedAngle >= 292.5 && normalizedAngle < 337.5) return Direction.NW;
    
    return Direction.N; // Default fallback
  }
} 