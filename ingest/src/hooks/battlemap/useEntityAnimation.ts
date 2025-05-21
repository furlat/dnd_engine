import { useCallback, useState, useEffect } from 'react';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../store/battlemapStore';
import { Assets, Texture, Rectangle } from 'pixi.js';
import { useTick } from '@pixi/react';
import { Direction } from '../../components/battlemap/DirectionalEntitySprite';

// Animation states that entities can be in
export enum AnimationState {
  IDLE = 'idle',
  ATTACK = 'attack',
  MOVE = 'move',
  CAST = 'cast',
  HIT = 'hit',
  DEATH = 'death'
}

interface SpriteAnimationFrame {
  frame: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  duration: number;
}

interface SpriteAnimationData {
  frames: SpriteAnimationFrame[];
  meta: {
    frameAnimations: {
      name: string;
      fps: number;
      speed_scale: number;
      from: number;
      to: number;
    }[];
    size: {
      w: number;
      h: number;
    };
  };
}

interface AnimationOptions {
  entityId?: string;  
  direction?: Direction;
  state?: AnimationState;
  fps?: number;
  loop?: boolean;
  onComplete?: () => void;
}

/**
 * Hook for managing entity animations
 */
export const useEntityAnimation = (options: AnimationOptions = {}) => {
  const { 
    entityId,
    direction = Direction.S, 
    state = AnimationState.IDLE,
    fps = 10,
    loop = true,
    onComplete
  } = options;
  
  const snap = useSnapshot(battlemapStore);
  
  // Local state for animation management
  const [animationData, setAnimationData] = useState<SpriteAnimationData | null>(null);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTexture, setCurrentTexture] = useState<Texture | null>(null);
  
  // Map direction enum value to file path index (0-7 to 1-8)
  const directionToPathIndex = useCallback((dir: Direction): number => {
    return Number(dir) + 1;
  }, []);
  
  // Load animation data
  useEffect(() => {
    const loadAnimationData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Map entity and animation state to the appropriate file
        // For now, we only have Knight_Idle, but this can be expanded
        const entityType = 'Knight'; // This would be dynamic based on entity type
        const animationName = state === AnimationState.IDLE ? 'Idle' : 'Idle'; // Default to idle for now
        
        // Get the direction as 1-8 value
        const dirIndex = directionToPathIndex(direction);
        
        // Construct file paths
        const jsonPath = `/assets/entities/${entityType}_${animationName}_dir${dirIndex}.json`;
        const texturePath = `/assets/entities/${entityType}_${animationName}_dir${dirIndex}.png`;
        
        // Load animation data
        const response = await fetch(jsonPath);
        if (!response.ok) {
          throw new Error(`Failed to load animation data: ${response.statusText}`);
        }
        
        const animData = await response.json();
        setAnimationData(animData);
        
        // Load and set initial texture
        const texture = await Assets.load({ src: texturePath });
        const frameInfo = animData.frames[0].frame;
        const frameTexture = new Texture({
          source: texture.baseTexture,
          frame: new Rectangle(
            frameInfo.x,
            frameInfo.y,
            frameInfo.w,
            frameInfo.h
          )
        });
        
        setCurrentTexture(frameTexture);
        setIsLoading(false);
      } catch (err) {
        console.error('Error loading animation:', err);
        setError(err instanceof Error ? err.message : String(err));
        setIsLoading(false);
      }
    };
    
    loadAnimationData();
  }, [direction, state, directionToPathIndex]);
  
  // Animation ticker
  useTick((delta) => {
    if (isLoading || !animationData || !isPlaying) return;
    
    const animation = animationData.meta.frameAnimations[0];
    const frameDuration = 1000 / (fps * (animation?.speed_scale || 1));
    
    setElapsed(prev => {
      const newElapsed = prev + (Number(delta) * 16.6667); // delta is a fraction, convert to ms
      if (newElapsed >= frameDuration) {
        setCurrentFrame(prevFrame => {
          // Calculate max frame based on animation data
          const maxFrame = animation 
            ? (animation.to - animation.from) 
            : (animationData.frames.length - 1);
          
          // If we hit the last frame
          if (prevFrame >= maxFrame) {
            // If not looping, stop at the last frame and call onComplete
            if (!loop) {
              setIsPlaying(false);
              onComplete?.();
              return maxFrame;
            }
            // If looping, go back to first frame
            return 0;
          }
          
          // Otherwise, advance to next frame
          return prevFrame + 1;
        });
        
        // Update texture for the new frame
        if (animationData && currentFrame < animationData.frames.length) {
          const frameInfo = animationData.frames[animation?.from + currentFrame || currentFrame].frame;
          const baseTexture = currentTexture?.baseTexture;
          
          if (baseTexture) {
            const frameTexture = new Texture({
              source: baseTexture,
              frame: new Rectangle(
                frameInfo.x,
                frameInfo.y,
                frameInfo.w,
                frameInfo.h
              )
            });
            setCurrentTexture(frameTexture);
          }
        }
        
        return 0;
      }
      return newElapsed;
    });
  });
  
  // Play/pause control
  const play = useCallback(() => {
    setIsPlaying(true);
  }, []);
  
  const pause = useCallback(() => {
    setIsPlaying(false);
  }, []);
  
  // Reset animation to first frame
  const reset = useCallback(() => {
    setCurrentFrame(0);
    setElapsed(0);
  }, []);
  
  // Restart animation from beginning
  const restart = useCallback(() => {
    reset();
    play();
  }, [reset, play]);
  
  return {
    // Current state
    currentFrame,
    currentTexture,
    isLoading,
    isPlaying,
    error,
    
    // Animation info
    animationData,
    entityId, 
    direction,
    state,
    
    // Control methods
    play,
    pause,
    reset,
    restart
  };
}; 