import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import { Container, Graphics, Sprite, Assets, Texture } from 'pixi.js';
import { sound, IMediaInstance } from '@pixi/sound';
import { useSoundSettings } from '../../contexts/SoundSettingsContext';
import { useSnapshot } from 'valtio';
import { characterStore } from '../../store/characterStore';
import { mapStore, mapHelpers } from '../../store/mapStore';
import { animationStore, animationActions } from '../../store/animationStore';

interface AttackAnimationProps {
  isHit?: boolean;
  sourceEntityId?: string;
  targetEntityId?: string;
  onComplete?: () => void;
}

const SPRITE_SIZE = 64;
const ANIMATION_ROW = 24; // The row we want to use from the spritesheet
const FRAMES_PER_ROW = 10; // Assuming 64px sprites with some spacing
const ANIMATION_PATH = '/assets/animations/weapons_combat_animations.png';

// Constants for sounds
const SWORD_HIT_SOUND_PATH = '/sounds/sword-hit.mp3';
const SWORD_MISS_SOUND_PATH = '/sounds/sword-miss.mp3';

// Add a constant for maximum animation duration to prevent extremely long animations
const MAX_ANIMATION_DURATION = 1500; // 1.5 seconds maximum

// Create a sound manager with better caching
class SoundManager {
  private static instance: SoundManager;
  private soundsLoaded = false;
  private soundPromises: Record<string, Promise<void>> = {};
  private activeInstances: Record<string, IMediaInstance> = {};
  
  private constructor() {
    // Private constructor to enforce singleton
    // Start preloading immediately
    this.preload().catch(err => {
      console.error('Error during sound preloading in constructor:', err);
    });
  }
  
  public static getInstance(): SoundManager {
    if (!SoundManager.instance) {
      SoundManager.instance = new SoundManager();
    }
    return SoundManager.instance;
  }
  
  public async preload(): Promise<void> {
    if (this.soundsLoaded) return;
    
    try {
      console.log('[SOUND-PERF] Starting sound preloading');
      const startTime = performance.now();

      // Preload all sounds at once - no more draw-sword
      const promises = [
        this.loadSound('sword-hit', SWORD_HIT_SOUND_PATH),
        this.loadSound('sword-miss', SWORD_MISS_SOUND_PATH)
      ];
      
      await Promise.all(promises);
      this.soundsLoaded = true;
      
      const duration = performance.now() - startTime;
      console.log(`[SOUND-PERF] All sounds preloaded successfully in ${duration.toFixed(2)}ms`);
    } catch (error) {
      console.error('[SOUND-PERF] Failed to preload sounds:', error);
    }
  }
  
  private async loadSound(id: string, path: string): Promise<void> {
    // Return existing promise if already loading
    if (id in this.soundPromises) {
      return this.soundPromises[id];
    }
    
    // Create and cache the loading promise
    this.soundPromises[id] = (async () => {
      try {
        console.log(`[SOUND-PERF] Loading sound ${id} from ${path}`);
        const startTime = performance.now();
        
        if (!sound.exists(id)) {
          await sound.add(id, path);
        }
        
        const duration = performance.now() - startTime;
        console.log(`[SOUND-PERF] Sound ${id} loaded in ${duration.toFixed(2)}ms`);
      } catch (error) {
        console.error(`[SOUND-PERF] Error loading sound ${id}:`, error);
        throw error;
      }
    })();
    
    return this.soundPromises[id];
  }
  
  public play(id: string, options?: {volume?: number}): void {
    try {
      // Performance tracking
      const playStartTime = performance.now();
      
      // Stop previous instance of this sound
      this.stop(id);
      
      // Check if sound exists but don't block if not loaded yet
      if (!sound.exists(id)) {
        console.log(`[SOUND-PERF] Sound ${id} not loaded yet, loading on demand`);
        
        // Use the loadSound method instead of direct sound.add to maintain consistency
        const soundPath = id === 'sword-hit' ? SWORD_HIT_SOUND_PATH : SWORD_MISS_SOUND_PATH;
        this.loadSound(id, soundPath)
          .then(() => {
            const loadTime = performance.now() - playStartTime;
            console.log(`[SOUND-PERF] Sound ${id} loaded on demand in ${loadTime.toFixed(2)}ms`);
            
            // Now play immediately
            this.playSound(id, options, playStartTime);
          })
          .catch((err: Error) => {
            console.error(`[SOUND-PERF] Error loading sound ${id} on demand:`, err);
          });
          
        return; // Don't block, return immediately
      }
      
      // Sound already loaded, play directly
      this.playSound(id, options, playStartTime);
    } catch (error) {
      console.error(`[SOUND-PERF] Error playing sound ${id}:`, error);
    }
  }
  
  // Extract playing logic to a separate method
  private playSound(id: string, options?: {volume?: number}, startTime?: number): void {
    const now = startTime || performance.now();

    // Play sound with the specified volume (already loaded)
    const instance = sound.play(id, {
      volume: options?.volume ?? 1,
      loop: false
    });
    
    if (instance instanceof Promise) {
      instance.then(mediaInstance => {
        this.activeInstances[id] = mediaInstance;
        console.log(`[SOUND-PERF] Sound ${id} started playing in ${(performance.now() - now).toFixed(2)}ms`);
      }).catch(err => {
        console.error(`[SOUND-PERF] Error playing sound ${id}:`, err);
      });
    } else {
      this.activeInstances[id] = instance;
      console.log(`[SOUND-PERF] Sound ${id} started playing in ${(performance.now() - now).toFixed(2)}ms`);
    }
  }
  
  public stop(id: string): void {
    if (this.activeInstances[id]) {
      try {
        this.activeInstances[id].stop();
        console.log(`[SOUND-PERF] Stopped sound ${id}`);
      } catch (err) {
        // Ignore errors from stopping
      }
      delete this.activeInstances[id];
    }
  }
  
  public stopAll(): void {
    Object.keys(this.activeInstances).forEach(id => this.stop(id));
  }
}

// Sound playback cache to avoid reloading
const soundCache: Record<string, HTMLAudioElement> = {};
// Track currently playing attack sound instances for cleanup
const activeAttackSounds: Record<string, HTMLAudioElement> = {};
// Track if sounds are already stopped to prevent redundant calls
let soundsCurrentlyStopped = false;

// Load a sound if not already loaded
const loadSound = async (soundName: string): Promise<HTMLAudioElement> => {
  const soundPath = `/sounds/${soundName}.mp3`;
  
  // Use cached sound if available
  if (soundCache[soundName]) {
    return soundCache[soundName];
  }
  
  console.log(`[SOUND-PERF] Loading sound ${soundName} from ${soundPath}`);
  const startLoadTime = performance.now();
  
  // Create new audio object
  const audio = new Audio(soundPath);
  
  // Wait for audio to load
  return new Promise((resolve, reject) => {
    audio.addEventListener('canplaythrough', () => {
      const loadTime = performance.now() - startLoadTime;
      console.log(`[SOUND-PERF] Sound ${soundName} loaded in ${loadTime.toFixed(2)}ms`);
      soundCache[soundName] = audio;
      resolve(audio);
    }, { once: true });
    
    audio.addEventListener('error', (err) => {
      console.error(`[SOUND-PERF] Error loading sound ${soundName}:`, err);
      reject(err);
    }, { once: true });
    
    // Start loading
    audio.load();
  });
};

// Preload all sounds at module initialization to avoid first-load delay
export const preloadAllSounds = async (): Promise<void> => {
  console.log('[SOUND-PRELOAD] Preloading all attack sounds');
  const start = performance.now();
  
  try {
    // Load all sounds in parallel - no more draw-sword sound
    const [hitSound, missSound] = await Promise.all([
      loadSound('sword-hit'),
      loadSound('sword-miss')
    ]);
    
    // Force sound activation by playing at zero volume and immediately stopping
    // This ensures browsers will permit subsequent autoplay
    const activateSounds = () => {
      const sounds = [hitSound, missSound];
      
      console.log('[SOUND-PRELOAD] Activating sounds for autoplay on user interaction');
      
      for (const sound of sounds) {
        try {
          // Clone to avoid affecting the cached instance
          const tempSound = sound.cloneNode() as HTMLAudioElement;
          tempSound.volume = 0; // Silent
          tempSound.play()
            .then(() => {
              // Immediately stop
              setTimeout(() => {
                tempSound.pause();
                tempSound.currentTime = 0;
              }, 10);
            })
            .catch(e => {
              // Ignore - expected if no user interaction yet
            });
        } catch (e) {
          // Ignore errors during activation
        }
      }
    };
    
    // Try to activate, but it will likely only work after user interaction
    activateSounds();
    
    // Add a listener to try again on first user interaction
    const handleUserInteraction = () => {
      activateSounds();
      // Remove listener after first interaction
      document.removeEventListener('click', handleUserInteraction);
      document.removeEventListener('keydown', handleUserInteraction);
    };
    
    // Add listeners for user interaction
    document.addEventListener('click', handleUserInteraction, { once: true });
    document.addEventListener('keydown', handleUserInteraction, { once: true });
    
    console.log(`[SOUND-PRELOAD] All sounds preloaded in ${(performance.now() - start).toFixed(2)}ms`);
  } catch (err) {
    console.error('[SOUND-PRELOAD] Error preloading sounds:', err);
  }
};

// Create a global cache for attack animation textures
const attackTextureCache: {
  textures: Texture[] | null;
  loading: Promise<Texture[]> | null;
} = {
  textures: null,
  loading: null
};

// Preload the animation frames
export const preloadAnimationFrames = async (): Promise<Texture[]> => {
  // Return cached textures if available
  if (attackTextureCache.textures) {
    return attackTextureCache.textures;
  }
  
  // Return existing loading promise if in progress
  if (attackTextureCache.loading) {
    return attackTextureCache.loading;
  }
  
  // Start loading
  attackTextureCache.loading = (async () => {
    try {
      console.log('[ANIM-PERF] Loading weapon animation textures');
      const startTime = performance.now();
  
      // Load the spritesheet
      await Assets.load({ src: ANIMATION_PATH, alias: 'weaponAnimations' });
      const baseTexture = Assets.get('weaponAnimations');
      
      // Calculate the y position for our animation row
      const yPosition = ANIMATION_ROW * SPRITE_SIZE;
      
      // Create frames from the spritesheet
      const frames = Array.from({ length: FRAMES_PER_ROW }, (_, i) => {
        const frame = new PIXI.Rectangle(
          i * SPRITE_SIZE,
          yPosition,
          SPRITE_SIZE,
          SPRITE_SIZE
        );
        // Create a new texture with the frame
        return new PIXI.Texture({
          source: baseTexture,
          frame
        });
      });
      
      const duration = performance.now() - startTime;
      console.log(`[ANIM-PERF] Weapon animation textures loaded in ${duration.toFixed(2)}ms`);
      
      // Cache the result
      attackTextureCache.textures = frames;
      return frames;
    } catch (error) {
      console.error('[ANIM-PERF] Error preloading attack animation:', error);
      // Clear loading flag on error
      attackTextureCache.loading = null;
      throw error;
    }
  })();
  
  return attackTextureCache.loading;
};

// Eagerly start preloading as soon as this module is imported
// Use an IIFE to ensure it runs immediately
(() => {
  console.log('[ANIM-INIT] Eagerly preloading attack animation assets');
  // Don't wait for the promise - let it load in the background
preloadAnimationFrames().catch(error => {
    console.error('[ANIM-INIT] Failed to preload attack animation:', error);
  });
  
  // Immediately preload sounds too
  preloadAllSounds().catch(error => {
    console.error('[ANIM-INIT] Failed to preload attack sounds:', error);
  });
})();

// Play a sound with volume control - but don't wait for it to finish
const playSound = async (soundName: string, volume: number = 0.6): Promise<HTMLAudioElement> => {
  try {
    // Reset stopped flag when playing new sounds
    soundsCurrentlyStopped = false;
    
    // Stop any existing attack sounds without redundant logging
    stopAttackSounds();
    
    const startTime = performance.now();
    const audio = await loadSound(soundName);
    
    // Create a new instance to allow overlapping sounds
    const soundInstance = audio.cloneNode() as HTMLAudioElement;
    soundInstance.volume = volume;
    
    // Store the active instance
    activeAttackSounds[soundName] = soundInstance;
    
    // Play the sound but don't await completion
    const playPromise = soundInstance.play();
    
    // Handle play promise (needed for some browsers)
    if (playPromise !== undefined) {
      playPromise.catch(err => {
        console.error(`[SOUND-PERF] Error starting sound ${soundName}:`, err);
      });
    }
    
    console.log(`[SOUND-PERF] Sound ${soundName} started playing in ${(performance.now() - startTime).toFixed(2)}ms`);
    return soundInstance;
  } catch (err) {
    console.error(`[SOUND-PERF] Failed to play ${soundName}:`, err);
    throw err;
  }
};

// Simplified sound API - just play hit or miss - but don't block
export const playAttackResultSound = async (isHit: boolean = true): Promise<void> => {
  // Stop any existing attack sound first (like draw-sword)
  stopAttackSounds();
  
  // Play the correct result sound
  const soundName = isHit ? 'sword-hit' : 'sword-miss';
  console.log(`[SOUND-CTRL] Playing attack result sound: ${soundName}`);
  
  // Fire and forget - don't wait for the sound to load or play
  playSound(soundName, isHit ? 0.7 : 0.5).catch(err => {
    console.error(`[SOUND-CTRL] Error playing ${soundName}:`, err);
  });
};

// Stop all playing attack sounds (without affecting background music)
export const stopAttackSounds = (): void => {
  // If sounds are already stopped, don't do anything
  if (soundsCurrentlyStopped) {
    return;
  }
  
  // Mark as stopped before stopping to prevent recursive stops
  soundsCurrentlyStopped = true;
  
  // Stop all active attack sounds
  Object.values(activeAttackSounds).forEach(sound => {
    try {
      sound.pause();
      sound.currentTime = 0;
    } catch (err) {
      // Ignore errors during cleanup
    }
  });
  // Clear the active sounds record
  Object.keys(activeAttackSounds).forEach(key => {
    delete activeAttackSounds[key];
  });
  console.log('[SOUND-CTRL] Stopped all active attack sounds');
};

export const AttackAnimation: React.FC<AttackAnimationProps> = ({ 
  isHit = true,
  sourceEntityId,
  targetEntityId,
  onComplete 
}) => {
  const { getEffectiveVolume } = useSoundSettings();
  const [textures, setTextures] = useState<Texture[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const animatedSpriteRef = useRef<PIXI.AnimatedSprite | null>(null);
  const soundManager = React.useMemo(() => SoundManager.getInstance(), []);
  const animationStartTime = useRef(performance.now());
  
  // Use snapshots of stores
  const charSnap = useSnapshot(characterStore);
  const mapSnap = useSnapshot(mapStore);
  const animSnap = useSnapshot(animationStore);

  // Calculate animation position based on entity positions
  const animationPosition = React.useMemo(() => {
    // If we don't have entity IDs, we can't calculate the position
    if (!sourceEntityId || !targetEntityId) {
      return { x: 0, y: 0, angle: 0 };
    }
    
    // Get entities from store - this ensures we always have the latest positions
    const sourceEntity = charSnap.summaries[sourceEntityId];
    const targetEntity = charSnap.summaries[targetEntityId];
    
    if (!sourceEntity || !targetEntity) {
      return { x: 0, y: 0, angle: 0 };
    }

    // The attack animation should use the same positioning system as entities
    // Use mapHelpers to calculate pixel positions without adding grid offset
    // Since the BattleMapCanvas will position this within the offset container
    const sourcePos = mapHelpers.gridToPixel(sourceEntity.position[0], sourceEntity.position[1]);
    const targetPos = mapHelpers.gridToPixel(targetEntity.position[0], targetEntity.position[1]);
    
    // Calculate angle between entities
    const dx = targetPos.x - sourcePos.x;
    const dy = targetPos.y - sourcePos.y;
    
    let angle = 0;
    
    // Use the same angle calculation as in entityDirectionStore
    // 0° = east, 90° = south, 180° = west, 270° = north
    angle = Math.atan2(dy, dx);
    
    // No need for complex direction mapping, we can use the angle directly for rotation
    
    // Calculate midpoint for animation
    const midX = (sourcePos.x + targetPos.x) / 2;
    const midY = (sourcePos.y + targetPos.y) / 2;
    
    return { x: midX, y: midY, angle };
  }, [sourceEntityId, targetEntityId, charSnap.summaries]);

  // Handle animation completion - improve to capture time metrics
  const handleAnimationComplete = useCallback(() => {
    const duration = performance.now() - animationStartTime.current;
    console.log(`[ANIM-PERF] Attack animation complete after ${duration.toFixed(2)}ms`);
    setIsPlaying(false);
          
    // Notify animation store about completion
    if (sourceEntityId && targetEntityId) {
      animationActions.completeAttackAnimation(sourceEntityId, targetEntityId);
    }
    
    // Call callback if provided
    if (onComplete) {
      onComplete();
    }
  }, [sourceEntityId, targetEntityId, onComplete]);

  // Add a safety timeout to ensure animation completes
  useEffect(() => {
    if (!isPlaying) return;
    
    // Set a timeout to force animation completion after MAX_ANIMATION_DURATION
    const timeoutId = setTimeout(() => {
      console.log(`[ANIM-SAFETY] Forcing attack animation completion after ${MAX_ANIMATION_DURATION}ms`);
      handleAnimationComplete();
    }, MAX_ANIMATION_DURATION);
    
    return () => clearTimeout(timeoutId);
  }, [isPlaying, handleAnimationComplete]);

  // Load frames once at component mount - do not play sound here
  useEffect(() => {
    console.log(`[ANIM-PERF] Attack animation initializing for ${sourceEntityId} → ${targetEntityId}, hit: ${isHit}`);
    let isMounted = true;
    
    const setup = async () => {
      try {
        // Use already loaded textures immediately if available
        if (attackTextureCache.textures) {
          if (!isMounted) return;
          console.log('[ANIM-PERF] Using cached attack textures (no loading needed)');
          
          // Update state and start animation
          setTextures(attackTextureCache.textures);
          setIsLoaded(true);
          setIsPlaying(true);
          
          // Reset animation start time for accurate metrics
          animationStartTime.current = performance.now();
          console.log('[ANIM-PERF] Animation started with cached textures');
          return;
        }
        
        // Need to load textures
        const textureStartTime = performance.now();
        const loadedTextures = await preloadAnimationFrames();
        const textureLoadTime = performance.now() - textureStartTime;
        console.log(`[ANIM-PERF] Attack textures loaded in ${textureLoadTime.toFixed(2)}ms`);
        
        if (!isMounted) return;
        
        // Update state and start animation
        setTextures(loadedTextures);
        setIsLoaded(true);
        setIsPlaying(true);
        
        // Reset animation start time for accurate metrics
        animationStartTime.current = performance.now();
        console.log(`[ANIM-PERF] Attack animation loaded and playing - Total setup: ${(performance.now() - textureStartTime).toFixed(2)}ms`);
      } catch (error) {
        console.error('[ANIM-PERF] Error setting up attack animation:', error);
      }
    };
    
    setup();
    
    return () => {
      isMounted = false;
      
      // We no longer need to stop sounds here as they're managed at the page level
      console.log(`[ANIM-PERF] Attack animation component unmounted`);
    };
  }, [isHit, sourceEntityId, targetEntityId]);

  // Set up the AnimatedSprite ref callback to configure it when created
  const spriteRef = useCallback((sprite: PIXI.AnimatedSprite | null) => {
    if (!sprite) return;
    
    // Store the reference and configure
    animatedSpriteRef.current = sprite;
    
    // Configure the sprite with MUCH faster animation for better performance
    // Increase speed by 2.5x for snappier animations
    sprite.animationSpeed = animationStore.settings.attackAnimationSpeed * 2.5;
    sprite.loop = false;
    sprite.onComplete = handleAnimationComplete;
    
    // Start the animation immediately
    console.log('[ANIM-PERF] Starting attack animation playback');
    sprite.gotoAndPlay(0);
  }, [handleAnimationComplete]);

  // Don't render until loaded
  if (!isLoaded || textures.length === 0 || !isPlaying) {
    return null;
  }

  // Get position and angle from our calculated values
  const { x, y, angle } = animationPosition;
  
  // Calculate scale based on tile size
  const scale = mapSnap.tileSize / 32;

  return (
    <pixiContainer 
      x={x}
      y={y}
      rotation={angle}
    >
      {/* Animation sprite centered at the midpoint */}
      <pixiAnimatedSprite
        ref={spriteRef}
        textures={textures}
        anchor={0.5}
        scale={{ x: scale, y: scale }}
      />
    </pixiContainer>
  );
}; 