import { proxy } from 'valtio';
import { Direction } from '../components/battlemap/DirectionalEntitySprite';

// Types of animations
export enum AnimationType {
  IDLE = 'idle',
  ATTACK = 'attack',
  MOVEMENT = 'movement'
}

// Animation state interface
export interface AnimationState {
  // Track entity idle animations
  entityAnimations: Record<string, {
    entityId: string;
    direction: Direction;
    isPlaying: boolean;
    lastUpdateTime: number;
  }>;
  
  // Track attack animations
  attackAnimations: Record<string, {
    sourceId: string;
    targetId: string;
    isHit: boolean;
    startTime: number;
  }>;
  
  // Track entities that should not change direction
  directionLocked: Record<string, boolean>;
  
  // Global animation settings
  settings: {
    idleAnimationSpeed: number;
    attackAnimationSpeed: number;
  };
}

// Initialize the store with default values
const animationStore = proxy<AnimationState>({
  entityAnimations: {},
  attackAnimations: {},
  directionLocked: {},
  settings: {
    idleAnimationSpeed: 0.1,
    attackAnimationSpeed: 0.15
  }
});

// Actions to mutate the store
const animationActions = {
  // Start or update an entity's idle animation
  updateEntityAnimation: (entityId: string, direction: Direction) => {
    const now = performance.now();
    
    // Skip direction updates for locked entities (during attack)
    if (animationStore.directionLocked[entityId]) {
      console.log(`[ANIM-STORE] Direction change ignored for locked entity: ${entityId}`);
      return;
    }
    
    // Update existing or create new
    animationStore.entityAnimations[entityId] = {
      entityId,
      direction,
      isPlaying: true,
      lastUpdateTime: now
    };
    
    console.log(`[ANIM-STORE] Updated entity animation: ${entityId}, direction: ${direction} at ${now.toFixed(2)}ms`);
  },
  
  // Explicitly stop an entity animation
  stopEntityAnimation: (entityId: string) => {
    if (animationStore.entityAnimations[entityId]) {
      animationStore.entityAnimations[entityId].isPlaying = false;
      console.log(`[ANIM-STORE] Stopped entity animation: ${entityId}`);
    }
  },
  
  // Start a new attack animation
  startAttackAnimation: (sourceId: string, targetId: string, isHit: boolean) => {
    const key = `${sourceId}-${targetId}`;
    const now = performance.now();
    
    // Lock source entity direction during attack
    animationStore.directionLocked[sourceId] = true;
    
    animationStore.attackAnimations[key] = {
      sourceId,
      targetId,
      isHit,
      startTime: now
    };
    
    console.log(`[ANIM-STORE] Started attack animation: ${sourceId} → ${targetId}, hit: ${isHit} at ${now.toFixed(2)}ms`);
  },
  
  // Mark an attack animation as complete
  completeAttackAnimation: (sourceId: string, targetId: string) => {
    const key = `${sourceId}-${targetId}`;
    
    if (animationStore.attackAnimations[key]) {
      const startTime = animationStore.attackAnimations[key].startTime;
      const duration = performance.now() - startTime;
      
      // Unlock entity direction
      delete animationStore.directionLocked[sourceId];
      
      delete animationStore.attackAnimations[key];
      console.log(`[ANIM-STORE] Completed attack animation: ${sourceId} → ${targetId}, duration: ${duration.toFixed(2)}ms`);
    }
  },
  
  // Cancel all active animations
  cancelAllAnimations: () => {
    console.log(`[ANIM-STORE] Cancelling all animations`);
    
    // Record counts for logging
    const entityCount = Object.keys(animationStore.entityAnimations).length;
    const attackCount = Object.keys(animationStore.attackAnimations).length;
    
    // Clear all animations
    animationStore.entityAnimations = {};
    animationStore.attackAnimations = {};
    animationStore.directionLocked = {};
    
    console.log(`[ANIM-STORE] Cancelled ${entityCount} entity animations and ${attackCount} attack animations`);
  },
  
  // Update animation settings
  updateSettings: (settings: Partial<AnimationState['settings']>) => {
    animationStore.settings = {
      ...animationStore.settings,
      ...settings
    };
  }
};

// Export both store and actions
export { animationStore, animationActions }; 