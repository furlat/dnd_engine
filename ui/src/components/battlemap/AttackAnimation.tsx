import * as React from 'react';
import { Assets, Rectangle, Texture, AnimatedSprite } from 'pixi.js';
import { sound, IMediaInstance } from '@pixi/sound';
import { useSoundSettings } from '../../contexts/SoundSettingsContext';
import { useRef, useEffect, useState, useCallback } from 'react';
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
const SWORD_SWING_SOUND_PATH = '/sounds/sword-swing.mp3';
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

      // Preload all sounds at once
      const promises = [
        this.loadSound('sword-swing', SWORD_SWING_SOUND_PATH),
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
        const soundPath = id === 'sword-swing' ? SWORD_SWING_SOUND_PATH : SWORD_MISS_SOUND_PATH;
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

// Create a global cache for attack animation textures
const attackTextureCache: {
  textures: Texture[] | null;
  loading: Promise<Texture[]> | null;
} = {
  textures: null,
  loading: null
};

// Preload the animation frames
const preloadAnimationFrames = async (): Promise<Texture[]> => {
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

// Start preloading as soon as this module is imported
preloadAnimationFrames().catch(error => {
  console.error('Failed to preload attack animation:', error);
});

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
  const animatedSpriteRef = useRef<AnimatedSprite | null>(null);
  const soundManager = React.useMemo(() => SoundManager.getInstance(), []);
  const animationStartTime = useRef(performance.now());
  
  // Use snapshots of stores
  const charSnap = useSnapshot(characterStore);
  const mapSnap = useSnapshot(mapStore);
  const animSnap = useSnapshot(animationStore);

  // Add a safety timeout to ensure animation completes
  useEffect(() => {
    if (!isPlaying || !sourceEntityId || !targetEntityId) return;
    
    // Set a timeout to force animation completion after MAX_ANIMATION_DURATION
    const timeoutId = setTimeout(() => {
      console.log(`[ANIM-PERF] Safety timeout forcing attack animation completion after ${MAX_ANIMATION_DURATION}ms`);
      handleAnimationComplete();
    }, MAX_ANIMATION_DURATION);
    
    return () => clearTimeout(timeoutId);
  }, [isPlaying, sourceEntityId, targetEntityId]);

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

    // Use mapHelpers to get pixel positions (WITHOUT adding grid offset since parent container handles it)
    const sourcePos = mapHelpers.gridToPixel(sourceEntity.position[0], sourceEntity.position[1]);
    const targetPos = mapHelpers.gridToPixel(targetEntity.position[0], targetEntity.position[1]);
    
    // Calculate angle between entities
    const dx = targetPos.x - sourcePos.x;
    const dy = targetPos.y - sourcePos.y;
    
    let angle = 0;
    
    // Cardinal and diagonal directions using only rotation
    if (dx > 0 && dy > 0) {
      // Southeast (attacker is northwest of target)
      angle = Math.PI / 4; // 45 degrees
    } else if (dx > 0 && dy < 0) {
      // Northeast (attacker is southwest of target)
      angle = -Math.PI / 4; // -45 degrees
    } else if (dx < 0 && dy > 0) {
      // Southwest (attacker is northeast of target)
      angle = 3 * Math.PI / 4; // 135 degrees
    } else if (dx < 0 && dy < 0) {
      // Northwest (attacker is southeast of target)
      angle = -3 * Math.PI / 4; // -135 degrees
    } else if (Math.abs(dx) < Math.abs(dy)) {
      // Vertical direction is primary
      if (dy > 0) {
        // South (attacker is north of target)
        angle = Math.PI / 2; // 90 degrees
      } else {
        // North (attacker is south of target)
        angle = -Math.PI / 2; // -90 degrees
      }
    } else {
      // Horizontal direction is primary
      if (dx > 0) {
        // East (attacker is west of target)
        angle = 0;
        } else {
        // West (attacker is east of target)
        angle = Math.PI; // 180 degrees
      }
    }
    
    // Calculate midpoint for animation
    const midX = (sourcePos.x + targetPos.x) / 2;
    const midY = (sourcePos.y + targetPos.y) / 2;
    
    return { x: midX, y: midY, angle };
  }, [sourceEntityId, targetEntityId, charSnap.summaries]);

  // Load frames once at component mount
  useEffect(() => {
    console.log(`[ANIM-PERF] Attack animation initializing for ${sourceEntityId} → ${targetEntityId}, hit: ${isHit}`);
    let isMounted = true;
    
    const setup = async () => {
      try {
        // Start sound playback immediately without waiting for textures
        // This creates the perception of faster response time
        const soundStartTime = performance.now();
        const effectVolume = getEffectiveVolume('effects');
        const soundName = isHit ? "sword-swing" : "sword-miss";
        soundManager.play(soundName, { volume: effectVolume });
        console.log(`[ANIM-PERF] Sound playback initiated in ${(performance.now() - soundStartTime).toFixed(2)}ms`);
        
        // Load animation textures (measure time)
        const textureStartTime = performance.now();
        const loadedTextures = await preloadAnimationFrames();
        const textureLoadTime = performance.now() - textureStartTime;
        console.log(`[ANIM-PERF] Attack textures loaded in ${textureLoadTime.toFixed(2)}ms`);
        
        if (!isMounted) return;
        
        // Update state and start animation
        setTextures(loadedTextures);
        setIsLoaded(true);
        setIsPlaying(true);
        
        console.log(`[ANIM-PERF] Attack animation loaded and playing - Total setup: ${(performance.now() - textureStartTime).toFixed(2)}ms`);
      } catch (error) {
        console.error('[ANIM-PERF] Error setting up attack animation:', error);
      }
    };
    
    setup();
    
    return () => {
      isMounted = false;
      soundManager.stopAll();
      console.log(`[ANIM-PERF] Attack animation component unmounted`);
    };
  }, [isHit, sourceEntityId, targetEntityId, getEffectiveVolume, soundManager]);

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

  // Set up the AnimatedSprite ref callback to configure it when created
  const spriteRef = useCallback((sprite: AnimatedSprite | null) => {
    if (!sprite) return;
    
    // Store the reference and configure
    animatedSpriteRef.current = sprite;
    
    // Configure the sprite with faster animation for better performance
    sprite.animationSpeed = animationStore.settings.attackAnimationSpeed * 1.5; // Make animations faster
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
      {/* Note: This animation component is a child of the pixiContainer that applies the grid offset,
          so we don't need to add gridOffsetX/Y to our position - the parent container handles it */}
      <pixiAnimatedSprite
        ref={spriteRef}
        textures={textures}
        anchor={0.5}
        scale={{ x: scale, y: scale }}
      />
    </pixiContainer>
  );
}; 