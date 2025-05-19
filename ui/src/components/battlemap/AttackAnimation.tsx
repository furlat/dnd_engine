import * as React from 'react';
import { Assets, Spritesheet, Rectangle, Texture, AnimatedSprite as PixiAnimatedSprite, Graphics } from 'pixi.js';
import { sound } from '@pixi/sound';
import { useSoundSettings } from '../../contexts/SoundSettingsContext';

interface AttackAnimationProps {
  x: number;
  y: number;
  scale?: number;
  flipX?: boolean;
  angle?: number;
  isHit?: boolean;
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
  onComplete 
}) => {
  const { getEffectiveVolume } = useSoundSettings();
  const [frames, setFrames] = React.useState<Texture[]>([]);
  const [currentFrame, setCurrentFrame] = React.useState(0);
  const [isPlaying, setIsPlaying] = React.useState(true);
  const startTimeRef = React.useRef<number>(0);
  const soundPlayed = React.useRef<boolean>(false);
  const soundInstanceRef = React.useRef<any>(null);

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
        
        // Get the effective volume for sound effects from context
        const effectsVolume = getEffectiveVolume('effects');
        console.log(`[SOUND DEBUG] Effect volume from settings: ${effectsVolume}`);
        
        const soundName = isHit ? 'sword-swing' : 'sword-miss';
        console.log(`[SOUND DEBUG] Selected sound name: "${soundName}"`);
        
        // Check if sounds are properly loaded
        console.log('[SOUND DEBUG] Sound exists check:',
          'sword-swing exists:', sound.exists('sword-swing'),
          'sword-miss exists:', sound.exists('sword-miss'));
        
        // Play the sound with appropriate options
        if (isHit) {
          // For hit, play the full sound with volume from settings
          soundInstanceRef.current = sound.play('sword-swing', {
            volume: effectsVolume
          });
        } else {
          // For miss, play only part of the sound with volume from settings
          soundInstanceRef.current = sound.play('sword-miss', {
            volume: effectsVolume,
            complete: () => {
              console.log('[Sound] Miss sound completed');
            }
          });
          
          // Set a timer to stop the miss sound after MISS_SOUND_DURATION seconds
          setTimeout(() => {
            if (soundInstanceRef.current) {
              soundInstanceRef.current.stop();
              console.log(`[Sound] Miss sound stopped after ${MISS_SOUND_DURATION}s`);
            }
          }, MISS_SOUND_DURATION * 1000);
        }
        
        console.log(`[Attack Sound] Playing ${soundName} sound effect at volume ${effectsVolume}`);
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
      if (soundInstanceRef.current) {
        soundInstanceRef.current.stop();
      }
    };
  }, []);

  if (frames.length === 0) return null;

  return (
    <pixiContainer 
      x={x}
      y={y}
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