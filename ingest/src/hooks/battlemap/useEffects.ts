import { useState, useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../store';
import { Direction } from '../../components/battlemap/DirectionalEntitySprite';

// Types for different effects
export interface AttackEffectProps {
  x: number;
  y: number;
  scale: number;
  angle?: number;
  flipX?: boolean;
  isHit: boolean;
  sourceEntityId: string;
  targetEntityId: string;
}

export interface SpellEffectProps {
  x: number;
  y: number;
  scale: number;
  spellType: string;
  sourceEntityId: string;
  targetEntityId?: string;
}

export interface StatusEffectProps {
  entityId: string;
  effectType: string;
  duration: number;
}

export type EffectType = 'attack' | 'spell' | 'status';

/**
 * Hook for managing visual effects on the battlemap
 */
export const useEffects = () => {
  // State for various types of effects
  const [attackEffect, setAttackEffect] = useState<AttackEffectProps | null>(null);
  const [spellEffect, setSpellEffect] = useState<SpellEffectProps | null>(null);
  const [statusEffects, setStatusEffects] = useState<StatusEffectProps[]>([]);
  
  // Access to the battlemap store
  const snap = useSnapshot(battlemapStore);
  
  /**
   * Calculate the screen position for an entity
   */
  const calculateEntityScreenPosition = useCallback((entityId: string, containerWidth: number, containerHeight: number, tileSize: number) => {
    const entity = snap.entities.summaries[entityId];
    if (!entity) return { x: 0, y: 0 };
    
    const [x, y] = entity.position;
    
    // Calculate the offset to center the grid
    const offsetX = (containerWidth - (snap.grid.width * tileSize)) / 2 + snap.view.offset.x;
    const offsetY = (containerHeight - (snap.grid.height * tileSize)) / 2 + snap.view.offset.y;
    
    // Convert grid position to screen position
    const screenX = offsetX + (x * tileSize) + (tileSize / 2);
    const screenY = offsetY + (y * tileSize) + (tileSize / 2);
    
    return { x: screenX, y: screenY };
  }, [snap.entities.summaries, snap.grid.width, snap.grid.height, snap.view.offset]);
  
  /**
   * Calculate the midpoint between two entities
   */
  const calculateMidpoint = useCallback((entity1Id: string, entity2Id: string, containerWidth: number, containerHeight: number, tileSize: number) => {
    const pos1 = calculateEntityScreenPosition(entity1Id, containerWidth, containerHeight, tileSize);
    const pos2 = calculateEntityScreenPosition(entity2Id, containerWidth, containerHeight, tileSize);
    
    return {
      x: (pos1.x + pos2.x) / 2,
      y: (pos1.y + pos2.y) / 2
    };
  }, [calculateEntityScreenPosition]);
  
  /**
   * Calculate the direction from one entity to another
   */
  const calculateAttackDirection = useCallback((sourceId: string, targetId: string): Direction => {
    const source = snap.entities.summaries[sourceId];
    const target = snap.entities.summaries[targetId];
    
    if (!source || !target) return Direction.S;
    
    // Calculate the difference between the source and target positions
    const dx = target.position[0] - source.position[0];
    const dy = target.position[1] - source.position[1];
    
    // Determine the cardinal and diagonal directions based on dx and dy
    if (dx > 0 && dy > 0) return Direction.SE;
    if (dx > 0 && dy < 0) return Direction.NE;
    if (dx < 0 && dy > 0) return Direction.SW;
    if (dx < 0 && dy < 0) return Direction.NW;
    if (dx === 0 && dy > 0) return Direction.S;
    if (dx === 0 && dy < 0) return Direction.N;
    if (dx > 0 && dy === 0) return Direction.E;
    if (dx < 0 && dy === 0) return Direction.W;
    
    return Direction.S; // Default
  }, [snap.entities.summaries]);
  
  /**
   * Calculate the rotation angle for an attack effect
   */
  const calculateAttackAngle = useCallback((direction: Direction): number => {
    switch (direction) {
      case Direction.N: return -Math.PI / 2; // -90 degrees
      case Direction.NE: return -Math.PI / 4; // -45 degrees
      case Direction.E: return 0; // 0 degrees
      case Direction.SE: return Math.PI / 4; // 45 degrees
      case Direction.S: return Math.PI / 2; // 90 degrees
      case Direction.SW: return 3 * Math.PI / 4; // 135 degrees
      case Direction.W: return Math.PI; // 180 degrees
      case Direction.NW: return -3 * Math.PI / 4; // -135 degrees
      default: return 0;
    }
  }, []);
  
  /**
   * Start an attack animation effect
   */
  const showAttackEffect = useCallback((
    sourceId: string,
    targetId: string,
    isHit: boolean,
    containerWidth: number,
    containerHeight: number,
    tileSize: number
  ) => {
    // Get entity positions
    const source = snap.entities.summaries[sourceId];
    const target = snap.entities.summaries[targetId];
    
    if (!source || !target) return;
    
    // Calculate midpoint
    const midpoint = calculateMidpoint(sourceId, targetId, containerWidth, containerHeight, tileSize);
    
    // Calculate direction and angle
    const direction = calculateAttackDirection(sourceId, targetId);
    const angle = calculateAttackAngle(direction);
    
    // Calculate scale based on tile size
    const scale = tileSize / 32;
    
    // Show attack effect
    setAttackEffect({
      x: midpoint.x,
      y: midpoint.y,
      scale,
      angle,
      flipX: false,
      isHit,
      sourceEntityId: sourceId,
      targetEntityId: targetId
    });
    
    // Optional: Return a promise that resolves when the animation completes
    return new Promise<void>(resolve => {
      // Animation typically takes about 500ms
      setTimeout(() => {
        resolve();
      }, 600);
    });
  }, [snap.entities.summaries, calculateMidpoint, calculateAttackDirection, calculateAttackAngle]);
  
  /**
   * Clear the attack effect (call when animation completes)
   */
  const clearAttackEffect = useCallback(() => {
    setAttackEffect(null);
  }, []);
  
  /**
   * Show a spell effect
   */
  const showSpellEffect = useCallback((
    sourceId: string,
    targetId: string | undefined,
    spellType: string,
    containerWidth: number,
    containerHeight: number,
    tileSize: number
  ) => {
    const sourcePos = calculateEntityScreenPosition(sourceId, containerWidth, containerHeight, tileSize);
    
    // If there's a target, calculate the midpoint, otherwise use source position
    const position = targetId
      ? calculateMidpoint(sourceId, targetId, containerWidth, containerHeight, tileSize)
      : sourcePos;
    
    // Calculate scale based on tile size
    const scale = tileSize / 32;
    
    // Show spell effect
    setSpellEffect({
      x: position.x,
      y: position.y,
      scale,
      spellType,
      sourceEntityId: sourceId,
      targetEntityId: targetId
    });
    
    // Optional: Return a promise that resolves when the animation completes
    return new Promise<void>(resolve => {
      // Animation typically takes about 800ms
      setTimeout(() => {
        setSpellEffect(null);
        resolve();
      }, 800);
    });
  }, [calculateEntityScreenPosition, calculateMidpoint]);
  
  /**
   * Add a status effect to an entity
   */
  const addStatusEffect = useCallback((entityId: string, effectType: string, duration: number = 3000) => {
    setStatusEffects(prev => [...prev, { entityId, effectType, duration }]);
    
    // Automatically remove status effect after duration
    setTimeout(() => {
      setStatusEffects(prev => prev.filter(effect => 
        !(effect.entityId === entityId && effect.effectType === effectType)
      ));
    }, duration);
  }, []);
  
  return {
    attackEffect,
    spellEffect,
    statusEffects,
    showAttackEffect,
    clearAttackEffect,
    showSpellEffect,
    addStatusEffect,
    calculateEntityScreenPosition
  };
}; 