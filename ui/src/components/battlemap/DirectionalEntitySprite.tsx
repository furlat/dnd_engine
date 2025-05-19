import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Container, Assets, Texture, Rectangle, Sprite, AnimatedSprite, Graphics as PixiGraphics } from 'pixi.js';
import { EntitySummary } from '../../models/character';
import { ReadonlyEntitySummary } from '../../models/readonly';
import { useSnapshot } from 'valtio';
import { mapStore, mapHelpers } from '../../store/mapStore';
import { animationStore } from '../../store/animationStore';
import * as PIXI from 'pixi.js';

// Direction mapping constants
export enum Direction {
  SW = 0,
  W = 1,
  NW = 2,
  N = 3,
  NE = 4,
  E = 5,
  SE = 6,
  S = 7
}

interface DirectionalEntitySpriteProps {
  entity: EntitySummary | ReadonlyEntitySummary;
  direction: Direction;
  selected?: boolean;
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

// Preloaded assets tracking
const preloadedAssets: Record<string, boolean> = {};

// Add texture cache
const textureCache: Record<string, Texture> = {};

// Add animation data cache with better error handling
const loadAnimationDataCache: Record<string, Promise<SpriteAnimationData>> = {};

const loadAnimationData = async (entityId: string, dirIndex: number): Promise<SpriteAnimationData> => {
  const cacheKey = `entity_${entityId}_dir${dirIndex}`;
  
  // Check if we already have this animation data loading or loaded
  if (cacheKey in loadAnimationDataCache) {
    return loadAnimationDataCache[cacheKey];
  }
  
  // Start loading and cache the promise
  loadAnimationDataCache[cacheKey] = (async () => {
    try {
      const jsonPath = `/assets/entities/Knight_Idle_dir${dirIndex}.json`;
      
      // Log the specific fetch for debugging
      console.log(`[ASSET-LOAD] Fetching animation data from ${jsonPath}`);
      
      const response = await fetch(jsonPath);
      if (!response.ok) {
        throw new Error(`Failed to load animation data: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log(`[ASSET-LOAD] Successfully loaded animation data for ${cacheKey}`);
      return data;
    } catch (err) {
      console.error(`[ASSET-LOAD] Error loading animation data for ${cacheKey}:`, err);
      // Remove failed loading promise from cache to allow retrying
      delete loadAnimationDataCache[cacheKey];
      throw err;
    }
  })();
  
  return loadAnimationDataCache[cacheKey];
};

// Function to load all textures for an animation with better caching
const loadAnimationTextures = async (entityId: string, dirIndex: number): Promise<Texture[]> => {
  try {
    const assetId = `entity_${entityId}_dir${dirIndex}`;
    const spritesheetPath = `/assets/entities/Knight_Idle_dir${dirIndex}.png`;
    
    // Check if we already have the textures cached by direction
    if (textureCacheByDirection[entityId]?.[dirIndex as Direction]) {
      console.log(`[ASSET-LOAD] Using cached textures for ${assetId}`);
      return textureCacheByDirection[entityId][dirIndex as Direction];
    }
    
    console.log(`[ASSET-LOAD] Loading textures for ${assetId}`);
    
    // Load the animation data
    const animData = await loadAnimationData(entityId, dirIndex);
    
    // Load the texture if not already loaded
    let baseTexture;
    try {
      baseTexture = Assets.get(assetId);
      if (!baseTexture) {
        console.log(`[ASSET-LOAD] Base texture not found in cache, loading from ${spritesheetPath}`);
        baseTexture = await Assets.load({ src: spritesheetPath, alias: assetId });
      }
    } catch (err) {
      console.error(`[ASSET-LOAD] Error loading base texture for ${assetId}:`, err);
      // Provide a placeholder texture if needed
      throw err;
    }
    
    // Create an array of frame textures
    const textures: Texture[] = [];
    const animation = animData.meta.frameAnimations[0];
    
    // For each frame in the animation range
    for (let i = animation.from; i <= animation.to; i++) {
      const frame = animData.frames[i].frame;
      
      // Create texture for this frame
      const textureKey = `${assetId}_frame${i}`;
      
      // Use cached texture if available
      if (textureCache[textureKey]) {
        textures.push(textureCache[textureKey]);
      } else {
        // Create new texture
        const frameTexture = new Texture({
          source: baseTexture.baseTexture,
          frame: new Rectangle(
            frame.x,
            frame.y,
            frame.w,
            frame.h
          )
        });
        
        // Cache the texture
        textureCache[textureKey] = frameTexture;
        textures.push(frameTexture);
      }
    }
    
    // Ensure the direction cache exists
    if (!textureCacheByDirection[entityId]) {
      textureCacheByDirection[entityId] = {} as Record<Direction, Texture[]>;
    }
    
    // Cache by direction for faster swapping
    textureCacheByDirection[entityId][dirIndex as Direction] = textures;
    
    return textures;
  } catch (err) {
    console.error(`[ASSET-LOAD] Error loading animation textures:`, err);
    throw err;
  }
};

// Enhance preloading to also load animation data JSON 
export const preloadEntityAnimations = async (entityIds: string[]) => {
  const directions = [1, 2, 3, 4, 5, 6, 7, 8];
  
  console.log(`[ENTITY-PRELOAD] Starting preload for ${entityIds.length} entities with ${directions.length} directions each`);
  const startTime = performance.now();
  
  const loadPromises: Promise<void>[] = [];
  const results = {
    total: entityIds.length * directions.length,
    succeeded: 0,
    failed: 0,
    skipped: 0
  };
  
  for (const entityId of entityIds) {
    for (const dir of directions) {
      const assetId = `entity_${entityId}_dir${dir}`;
      
      // Skip if already preloaded
      if (preloadedAssets[assetId]) {
        results.skipped++;
        continue;
      }
      
      // Preload all textures
      const texturePromise = (async () => {
        try {
          const startLoadTime = performance.now();
          await loadAnimationTextures(entityId, dir);
          const loadDuration = performance.now() - startLoadTime;
          
          console.log(`[ENTITY-PRELOAD] Loaded entity ${entityId} direction ${dir} in ${loadDuration.toFixed(2)}ms`);
          preloadedAssets[assetId] = true;
          results.succeeded++;
        } catch (err) {
          console.error(`[ENTITY-PRELOAD] Error preloading textures for ${assetId}:`, err);
          results.failed++;
        }
      })();
      
      loadPromises.push(texturePromise);
    }
  }
  
  await Promise.all(loadPromises);
  const totalTime = performance.now() - startTime;
  
  console.log(`[ENTITY-PRELOAD] Completed animation preload in ${totalTime.toFixed(2)}ms - Success: ${results.succeeded}, Failed: ${results.failed}, Skipped: ${results.skipped}`);
  return results;
};

// Loading textures - modify to enable faster swapping between directions
const textureCacheByDirection: Record<string, Record<Direction, Texture[]>> = {};

export const DirectionalEntitySprite: React.FC<DirectionalEntitySpriteProps> = ({
  entity,
  direction,
  selected = false
}) => {
  // Get map state from the store
  const mapSnap = useSnapshot(mapStore);
  const animSnap = useSnapshot(animationStore);
  
  // Use mapHelpers to calculate the pixel position
  const [x, y] = entity.position;
  const pixelPosition = mapHelpers.gridToPixel(x, y);
  
  // Map 0-7 direction to 1-8 filename
  const dirFileIndex = direction + 1;

  // Animation state
  const [textures, setTextures] = useState<Texture[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const animatedSpriteRef = useRef<AnimatedSprite | null>(null);
  const entityIdRef = useRef<string>(entity.uuid);
  const directionRef = useRef<Direction>(direction);

  // Track direction changes for perf debugging
  useEffect(() => {
    if (directionRef.current !== direction) {
      console.log(`[IDLE-PERF] Entity ${entity.uuid} direction changed from ${directionRef.current} to ${direction} at ${performance.now().toFixed(2)}ms`);
      directionRef.current = direction;
    }
  }, [entity.uuid, direction]);

  // Calculate unique asset ID
  const assetId = `entity_${entity.uuid}_dir${dirFileIndex}`;
  
  // Load textures when entity or direction changes
  useEffect(() => {
    let isMounted = true;
    
    // Don't create a log spam for direction changes if in an attack animation
    if (entityIdRef.current !== entity.uuid) {
      console.log(`[IDLE-PERF] Entity changed from ${entityIdRef.current} to ${entity.uuid} at ${performance.now().toFixed(2)}ms`);
      entityIdRef.current = entity.uuid;
    }
    
    const loadTexturesAndSetup = async () => {
      try {
        if (!isMounted) return;
        
        // Check if this entity is involved in an attack
        const isAttacking = Object.values(animationStore.attackAnimations).some(
          anim => anim.sourceId === entity.uuid || anim.targetId === entity.uuid
        );
        
        // Verify entity position data is consistent with the map
        // This helps detect stale data scenarios
        const [x, y] = entity.position;
        const validPosition = x >= 0 && y >= 0 && x < mapStore.gridWidth && y < mapStore.gridHeight;
        if (!validPosition) {
          console.warn(`[ENTITY-SYNC] Entity ${entity.uuid} has possibly stale position data [${x},${y}], grid is ${mapStore.gridWidth}x${mapStore.gridHeight}`);
        }
        
        const loadStartTime = performance.now();
        setIsLoading(true);
        setLoadError(null);
        
        // Only log new animations, not direction changes during animation
        if (!isAttacking) {
          console.log(`[IDLE-PERF] Loading animation for entity ${entity.uuid} direction ${direction} at ${loadStartTime.toFixed(2)}ms`);
        }

        // Load textures
        const loadedTextures = await loadAnimationTextures(entity.uuid, dirFileIndex);
        const loadEndTime = performance.now();
        const loadDuration = loadEndTime - loadStartTime;
        
        if (!isMounted) return;
        
        // Store in direction cache
        if (!textureCacheByDirection[entity.uuid]) {
          textureCacheByDirection[entity.uuid] = {} as Record<Direction, Texture[]>;
        }
        textureCacheByDirection[entity.uuid][direction] = loadedTextures;
        
        setTextures(loadedTextures);
        setIsLoading(false);
        
        // Only log new animations, not direction changes
        if (!isAttacking) {
          console.log(`[IDLE-PERF] Textures loaded in ${loadDuration.toFixed(2)}ms for ${entity.uuid} dir ${direction}, frames: ${loadedTextures.length}`);
        }
      } catch (err) {
        if (!isMounted) return;
        const errorTime = performance.now();
        setLoadError(`Error loading animation textures: ${err instanceof Error ? err.message : String(err)}`);
        setIsLoading(false);
        console.error(`[IDLE-PERF] Animation load error for ${entity.uuid} at ${errorTime.toFixed(2)}ms:`, err);
      }
    };

    loadTexturesAndSetup();
    
    return () => {
      isMounted = false;
      
      // Check if in attack animation before logging cleanup
      const isInAttack = Object.values(animationStore.attackAnimations).some(
        anim => anim.sourceId === entity.uuid || anim.targetId === entity.uuid
      );
      
      // Only log if not in an attack animation to reduce noise
      if (!isInAttack) {
        console.log(`[IDLE-PERF] Animation cleanup for entity ${entity.uuid} at ${performance.now().toFixed(2)}ms`);
      }
    };
  }, [entity.uuid, dirFileIndex]);

  // Handle sprite setup via ref
  const spriteRef = useCallback((sprite: AnimatedSprite | null) => {
    if (!sprite) return;
    
    // Store reference
    animatedSpriteRef.current = sprite;
    
    // Check if in attack - if so, keep animation state quiet
    const isInAttack = Object.values(animationStore.attackAnimations).some(
      anim => anim.sourceId === entity.uuid || anim.targetId === entity.uuid
    );
    
    // Configure sprite
    sprite.animationSpeed = animationStore.settings.idleAnimationSpeed;
    sprite.loop = true;
    
    if (!isInAttack) {
      console.log(`[IDLE-PERF] Animated sprite created for ${entity.uuid}`);
    }
    
    // Start playing - the direct approach
    sprite.play();
    
    // Track animation frames
    let lastFrameTime = performance.now();
    let lastFrameNumber = sprite.currentFrame;
    
    // Add event listener for animation frames
    sprite.onFrameChange = () => {
      const now = performance.now();
      const elapsed = now - lastFrameTime;
      
      // Check for frame transitions
      if (sprite.currentFrame !== lastFrameNumber) {
        // Check if this is a loop transition (last frame to first frame)
        const isLoop = (lastFrameNumber === textures.length - 1 && sprite.currentFrame === 0);
        
        // Only log non-sequential transitions that aren't loops
        if (Math.abs(sprite.currentFrame - lastFrameNumber) !== 1 && !isLoop) {
          console.log(`[IDLE-TRACK] Entity ${entity.uuid} animation skipped from frame ${lastFrameNumber} to ${sprite.currentFrame} after ${elapsed.toFixed(2)}ms`);
        }
        
        lastFrameNumber = sprite.currentFrame;
        lastFrameTime = now;
      }
    };
  }, [entity.uuid, textures.length]);

  if (loadError) {
    console.warn(`Failed to load sprite for ${entity.name}:`, loadError);
    return null;
  }

  if (isLoading || textures.length === 0) {
    return null;
  }

  // Calculate scale to fit tile size with 20% increase
  const BASE_SCALE = 2.4; // 2.0 (original) * 1.2 (20% larger)
  const scale = (mapSnap.tileSize / Math.max(textures[0].width, textures[0].height)) * BASE_SCALE;

  // Calculate vertical offset to position sprite slightly south
  const verticalOffset = mapSnap.tileSize / 6; // Move down by 1/6 of tile size

  return (
    <pixiContainer x={pixelPosition.x} y={pixelPosition.y}>
      <pixiAnimatedSprite
        ref={spriteRef}
        textures={textures}
        anchor={0.5} // Center anchor
        scale={scale}
        y={verticalOffset} // Positive offset to move south
      />
    </pixiContainer>
  );
}; 