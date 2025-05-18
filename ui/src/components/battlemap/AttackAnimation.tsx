import * as React from 'react';
import { Assets, Spritesheet, Rectangle, Texture, AnimatedSprite as PixiAnimatedSprite } from 'pixi.js';

interface AttackAnimationProps {
  x: number;
  y: number;
  scale?: number;
  onComplete?: () => void;
}

const SPRITE_SIZE = 64;
const ANIMATION_ROW = 24; // The row we want to use from the spritesheet
const SPRITESHEET_WIDTH = 640;
const FRAMES_PER_ROW = 10; // Assuming 64px sprites with some spacing
const FRAME_INTERVAL = 100; // milliseconds per frame
const ANIMATION_PATH = '/assets/animations/weapons_combat_animations.png';

// Create a global promise to track the spritesheet loading
let spritesheetPromise: Promise<Texture[]> | null = null;

// Preload the animation frames
const preloadAnimationFrames = async (): Promise<Texture[]> => {
  // Only load once
  if (spritesheetPromise) {
    return spritesheetPromise;
  }
  
  console.log('[Attack Timing] Starting to preload animation frames');
  const startTime = performance.now();
  
  spritesheetPromise = (async () => {
    try {
      // Load the spritesheet
      await Assets.load({ src: ANIMATION_PATH, alias: 'weaponAnimations' });
      const baseTexture = Assets.get('weaponAnimations');
      
      // Calculate the y position for our animation row
      const yPosition = ANIMATION_ROW * SPRITE_SIZE;
      
      // Create frames from the spritesheet
      const frames = Array.from({ length: FRAMES_PER_ROW }, (_, i) => {
        const frame = new Rectangle(
          i * SPRITE_SIZE,
          yPosition,
          SPRITE_SIZE,
          SPRITE_SIZE
        );
        // Create a new texture with the frame
        return new Texture({
          source: baseTexture,
          frame
        });
      });
      
      console.log(`[Attack Timing] Frames preloaded in ${performance.now() - startTime}ms`);
      return frames;
    } catch (error) {
      console.error('Error preloading attack animation:', error);
      throw error;
    }
  })();
  
  return spritesheetPromise;
};

// Start preloading as soon as this module is imported
preloadAnimationFrames().catch(error => {
  console.error('Failed to preload attack animation:', error);
});

export const AttackAnimation: React.FC<AttackAnimationProps> = ({ x, y, scale = 1, onComplete }) => {
  const [frames, setFrames] = React.useState<Texture[]>([]);
  const [currentFrame, setCurrentFrame] = React.useState(0);
  const [isPlaying, setIsPlaying] = React.useState(true);
  const startTimeRef = React.useRef<number>(0);

  React.useEffect(() => {
    const loadFrames = async () => {
      startTimeRef.current = performance.now();
      console.log('[Attack Timing] Starting to load animation frames');
      
      try {
        // Use the preloaded frames
        const loadedFrames = await preloadAnimationFrames();
        setFrames(loadedFrames);
        console.log(`[Attack Timing] Frames loaded in ${performance.now() - startTimeRef.current}ms`);
        console.log('[Attack Timing] Animation playback starting');
      } catch (error) {
        console.error('Error loading attack animation:', error);
      }
    };

    loadFrames();
  }, []);

  React.useEffect(() => {
    if (!isPlaying || frames.length === 0) return;

    let startTime = performance.now();
    
    const interval = setInterval(() => {
      setCurrentFrame(prev => {
        if (prev >= frames.length - 1) {
          setIsPlaying(false);
          
          const animationDuration = performance.now() - startTimeRef.current;
          console.log(`[Attack Timing] Animation completed after ${animationDuration}ms`);
          console.log(`[Attack Timing] Animation details:
            - Total frames: ${frames.length}
            - Frame interval: ${FRAME_INTERVAL}ms
            - Expected duration: ${frames.length * FRAME_INTERVAL}ms
            - Actual duration: ${animationDuration}ms`);
            
          if (onComplete) onComplete();
          return 0;
        }
        return prev + 1;
      });
    }, FRAME_INTERVAL); // Animation speed - adjust as needed

    return () => clearInterval(interval);
  }, [isPlaying, frames.length, onComplete]);

  if (frames.length === 0) return null;

  return (
    <pixiContainer>
      <pixiSprite
        x={x}
        y={y}
        texture={frames[currentFrame]}
        anchor={0.5}
        scale={{ x: scale, y: scale }}
      />
    </pixiContainer>
  );
}; 