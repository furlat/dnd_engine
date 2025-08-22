import { Direction } from '../types/battlemap_types';

/**
 * Combat and positioning utilities for isometric battlemap
 * Centralized to avoid duplication across renderers and handlers
 */

/**
 * Determine if defender shows front or back based on attacker position
 * This logic works for GRID positions (before isometric conversion)
 * 
 * From defender's perspective (defender is center):
 * - If attacker is NE, E, SE, S, SW relative to defender: defender shows FRONT
 * - If attacker is W, NW, N relative to defender: defender shows BACK
 * 
 * @param attackerPosition Grid position of the attacker
 * @param defenderPosition Grid position of the defender
 * @returns true if defender shows front, false if defender shows back
 */
export function isDefenderShowingFront(
  attackerPosition: readonly [number, number], 
  defenderPosition: readonly [number, number]
): boolean {
  // Calculate attacker position relative to defender (defender is center)
  const dx = attackerPosition[0] - defenderPosition[0];
  const dy = attackerPosition[1] - defenderPosition[1];
  
  // Determine attacker's direction relative to defender
  let attackerDirection: Direction;
  if (dx > 0 && dy > 0) attackerDirection = Direction.SE;
  else if (dx > 0 && dy < 0) attackerDirection = Direction.NE;
  else if (dx < 0 && dy > 0) attackerDirection = Direction.SW;
  else if (dx < 0 && dy < 0) attackerDirection = Direction.NW;
  else if (dx === 0 && dy > 0) attackerDirection = Direction.S;
  else if (dx === 0 && dy < 0) attackerDirection = Direction.N;
  else if (dx > 0 && dy === 0) attackerDirection = Direction.E;
  else if (dx < 0 && dy === 0) attackerDirection = Direction.W;
  else attackerDirection = Direction.S; // Default
  
  // Determine if defender shows front or back
  return attackerDirection === Direction.NE || 
         attackerDirection === Direction.E || 
         attackerDirection === Direction.SE || 
         attackerDirection === Direction.S || 
         attackerDirection === Direction.SW;
}

/**
 * Get position offset by a specified distance in a given direction
 * Works with GRID coordinates (before isometric conversion)
 * 
 * @param position The base grid position
 * @param direction The direction to move
 * @param distance The distance to move (default: 0.25 for subtle movement)
 * @returns The new grid position
 */
export function getAdjacentPosition(
  position: readonly [number, number], 
  direction: Direction, 
  distance: number = 0.25
): readonly [number, number] {
  const [x, y] = position;
  
  switch (direction) {
    case Direction.N: return [x, y - distance];
    case Direction.NE: return [x + distance, y - distance];
    case Direction.E: return [x + distance, y];
    case Direction.SE: return [x + distance, y + distance];
    case Direction.S: return [x, y + distance];
    case Direction.SW: return [x - distance, y + distance];
    case Direction.W: return [x - distance, y];
    case Direction.NW: return [x - distance, y - distance];
    default: return position;
  }
}

/**
 * Get the opposite direction for dodge/retreat movement
 * 
 * @param direction The original direction
 * @returns The opposite direction
 */
export function getOppositeDirection(direction: Direction): Direction {
  switch (direction) {
    case Direction.N: return Direction.S;
    case Direction.NE: return Direction.SW;
    case Direction.E: return Direction.W;
    case Direction.SE: return Direction.NW;
    case Direction.S: return Direction.N;
    case Direction.SW: return Direction.NE;
    case Direction.W: return Direction.E;
    case Direction.NW: return Direction.SE;
    default: return Direction.S;
  }
}

/**
 * Compute direction from one grid position to another
 * Works with GRID coordinates (before isometric conversion)
 * 
 * @param fromPos Starting grid position
 * @param toPos Target grid position
 * @returns The direction from start to target
 */
export function computeDirection(
  fromPos: readonly [number, number], 
  toPos: readonly [number, number]
): Direction {
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
 * Calculate the Euclidean distance between two grid positions
 * 
 * @param pos1 First grid position
 * @param pos2 Second grid position
 * @returns The distance between the positions
 */
export function calculateDistance(
  pos1: readonly [number, number], 
  pos2: readonly [number, number]
): number {
  const dx = pos2[0] - pos1[0];
  const dy = pos2[1] - pos1[1];
  return Math.sqrt(dx * dx + dy * dy);
} 