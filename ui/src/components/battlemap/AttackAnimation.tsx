import * as React from 'react';
import { Assets, Spritesheet, Rectangle, Texture, AnimatedSprite as PixiAnimatedSprite, Graphics } from 'pixi.js';
import { sound, IMediaInstance } from '@pixi/sound';
import { useSoundSettings } from '../../contexts/SoundSettingsContext';
import { useRef, useEffect } from 'react';
import { useSnapshot } from 'valtio';
import { characterStore } from '../../store/characterStore';

interface AttackAnimationProps {
  x: number;
  y: number;
  scale?: number;
  flipX?: boolean;
  angle?: number;
  isHit?: boolean;
  sourceEntityId?: string;
  targetEntityId?: string;
  onComplete?: () => void;
}

const SPRITE_SIZE = 64;
const ANIMATION_ROW = 24; // The row we want to use from the spritesheet
const SPRITESHEET_WIDTH = 640;
const FRAMES_PER_ROW = 10; // Assuming 64px sprites with some spacing
const FRAME_INTERVAL = 100; // milliseconds per frame
const ANIMATION_PATH = '/assets/animations/weapons_combat_animations.png';

// Fixed naming: use consistent names matching the actual file names
const SWORD_SWING_SOUND_PATH = '/sounds/sword-swing.mp3';
const SWORD_MISS_SOUND_PATH = '/sounds/sword-miss.mp3';
const MISS_SOUND_DURATION = 0.7; // Play only 0.7 seconds of the miss sound

// Create promises to track sound loading similar to spritesheets
let soundSwingPromise: Promise<void> | null = null;
let soundMissPromise: Promise<void> | null = null;

// Preload the sound effects
const preloadSounds = async (): Promise<void> => {
  // Only load each sound once
  const loadSwingSound = async () => {
    if (soundSwingPromise) return soundSwingPromise;
    soundSwingPromise = (async () => {
      try {
        if (!sound.exists('sword-swing')) {
          console.log('[Sound Preload] Loading sword-swing sound');
          await sound.add('sword-swing', SWORD_SWING_SOUND_PATH);
          console.log('[Sound Preload] sword-swing loaded successfully');
        }
      } catch (error) {
        console.error('Error preloading sword-swing sound:', error);
        throw error;
      }
    })();
    return soundSwingPromise;
  };

  const loadMissSound = async () => {
    if (soundMissPromise) return soundMissPromise;
    soundMissPromise = (async () => {
      try {
        if (!sound.exists('sword-miss')) {
          console.log('[Sound Preload] Loading sword-miss sound');
          await sound.add('sword-miss', SWORD_MISS_SOUND_PATH);
          console.log('[Sound Preload] sword-miss loaded successfully');
        }
      } catch (error) {
        console.error('Error preloading sword-miss sound:', error);
        throw error;
      }
    })();
    return soundMissPromise;
  };

  // Load both sounds in parallel
  await Promise.all([loadSwingSound(), loadMissSound()]);
};

// Start preloading sounds as soon as this module is imported
preloadSounds().catch(error => {
  console.error('Failed to preload sounds:', error);
});

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

export const AttackAnimation: React.FC<AttackAnimationProps> = ({ 
  x, 
  y, 
  scale = 1,
  flipX = false,
  angle = 0,
  isHit = true,
  sourceEntityId,
  targetEntityId,
  onComplete 
}) => {
  const { getEffectiveVolume } = useSoundSettings();
  const [frames, setFrames] = React.useState<Texture[]>([]);
  const [currentFrame, setCurrentFrame] = React.useState(0);
  const [isPlaying, setIsPlaying] = React.useState(true);
  const startTimeRef = React.useRef<number>(0);
  const soundPlayed = React.useRef<boolean>(false);
  const soundInstanceRef = useRef<IMediaInstance | null>(null);
  const snap = useSnapshot(characterStore);

  // Calculate animation position based on source and target entities from store
  const animationPosition = React.useMemo(() => {
    if (sourceEntityId && targetEntityId) {
      const sourceEntity = snap.summaries[sourceEntityId];
      const targetEntity = snap.summaries[targetEntityId];
      
      if (sourceEntity && targetEntity) {
        // Get grid positions from store
        const [sourceGridX, sourceGridY] = sourceEntity.position;
        const [targetGridX, targetGridY] = targetEntity.position;

        // Calculate screen coordinates using the same formula as DirectionalEntitySprite
        const sourceX = x + (sourceGridX * scale * 32) + ((scale * 32) / 2);
        const sourceY = y + (sourceGridY * scale * 32) + ((scale * 32) / 2);
        const targetX = x + (targetGridX * scale * 32) + ((scale * 32) / 2);
        const targetY = y + (targetGridY * scale * 32) + ((scale * 32) / 2);

        // Calculate midpoint between source and target
        const midX = (sourceX + targetX) / 2;
        const midY = (sourceY + targetY) / 2;
        return { x: midX, y: midY };
      }
    }
    return { x, y };
  }, [x, y, sourceEntityId, targetEntityId, snap.summaries, scale]);

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
    
    // Play the appropriate sound when animation starts
    if (!soundPlayed.current) {
      try {
        console.log('[SOUND DEBUG] isHit value in AttackAnimation:', isHit);
        console.log('[SOUND DEBUG] isHit type:', typeof isHit);
        
        const effectVolume = getEffectiveVolume('effects');
        console.log('[SOUND DEBUG] Effect volume from settings:', effectVolume);
        
        // Select appropriate sound
        const soundName = isHit ? "sword-swing" : "sword-miss";
        console.log('[SOUND DEBUG] Selected sound name:', `"${soundName}"`);
        
        // Check if sounds exist
        console.log('[SOUND DEBUG] Sound exists check:', 
          'sword-swing exists:', sound.exists('sword-swing'),
          'sword-miss exists:', sound.exists('sword-miss')
        );
        
        // Play sound if it exists
        if (sound.exists(soundName)) {
          try {
            const instance = sound.play(soundName, {
              volume: effectVolume,
              loop: false
            });
            
            // Handle both Promise and direct instance
            if (instance instanceof Promise) {
              instance.then(mediaInstance => {
                soundInstanceRef.current = mediaInstance;
              }).catch(err => {
                console.error('Error playing sound:', err);
              });
            } else {
              soundInstanceRef.current = instance;
            }
            
            console.log('[Attack Sound] Playing', soundName, 'sound effect at volume', effectVolume);
          } catch (err) {
            console.error('Error playing sound:', err);
          }
        }
        
        soundPlayed.current = true;
      } catch (error) {
        console.error('Error playing attack sound:', error);
      }
    }
    
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
  }, [isPlaying, frames.length, onComplete, isHit, getEffectiveVolume]);

  // Reset sound played status when component re-renders
  React.useEffect(() => {
    soundPlayed.current = false;
    
    // Cleanup function to stop any playing sounds when component unmounts
    return () => {
      // Clean up sound if it exists
      if (soundInstanceRef.current) {
        try {
          soundInstanceRef.current.stop();
        } catch (err) {
          console.warn('Error stopping sound:', err);
        }
      }
      soundInstanceRef.current = null;
    };
  }, [isPlaying, frames.length, onComplete, isHit, getEffectiveVolume]);

  if (frames.length === 0) return null;

  return (
    <pixiContainer 
      x={animationPosition.x}
      y={animationPosition.y}
      rotation={angle}
    >
      <pixiSprite
        texture={frames[currentFrame]}
        anchor={0.5}
        scale={{ x: flipX ? -scale : scale, y: scale }}
      />
    </pixiContainer>
  );
}; 