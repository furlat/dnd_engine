import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Container, Assets, Texture, Rectangle, Sprite } from 'pixi.js';
import { useTick } from '@pixi/react';
import { EntitySummary } from '../../types/common';

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
  entity: EntitySummary;
  direction: Direction;
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
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

// Update preloadEntityAnimations to cache textures
export const preloadEntityAnimations = async (entityIds: string[]) => {
  const directions = [1, 2, 3, 4, 5, 6, 7, 8];
  
  const loadPromises: Promise<void>[] = [];
  
  for (const entityId of entityIds) {
    for (const dir of directions) {
      const assetId = `entity_${entityId}_dir${dir}`;
      
      // Skip if already preloaded
      if (preloadedAssets[assetId]) continue;
      
      const spritesheetPath = `/assets/entities/Knight_Idle_dir${dir}.png`;
      const jsonPath = `/assets/entities/Knight_Idle_dir${dir}.json`;
      
      // Load JSON and create frame textures
      const jsonPromise = fetch(jsonPath)
        .then(async response => {
          if (!response.ok) throw new Error(`Failed to load ${jsonPath}`);
          const animData = await response.json();
          
          // Load and cache spritesheet
          const texture = await Assets.load({ src: spritesheetPath, alias: assetId });
          
          // Pre-create and cache all frame textures
          animData.frames.forEach((frame: SpriteAnimationFrame, index: number) => {
            const frameTexture = new Texture({
              source: texture.baseTexture,
              frame: new Rectangle(
                frame.frame.x,
                frame.frame.y,
                frame.frame.w,
                frame.frame.h
              )
            });
            textureCache[`${assetId}_frame${index}`] = frameTexture;
          });
          
          preloadedAssets[assetId] = true;
        })
        .catch(err => {
          console.error(`Error preloading ${jsonPath}:`, err);
        });
      
      loadPromises.push(jsonPromise);
    }
  }
  
  await Promise.all(loadPromises);
  console.log('All entity animations preloaded and cached.');
};

export const DirectionalEntitySprite: React.FC<DirectionalEntitySpriteProps> = ({
  entity,
  direction,
  width,
  height,
  gridSize,
  tileSize,
  selected = false
}) => {
  // Calculate the offset to center the grid
  const offsetX = (width - (gridSize.cols * tileSize)) / 2;
  const offsetY = (height - (gridSize.rows * tileSize)) / 2;
  const [x, y] = entity.position;
  const pixelX = offsetX + (x * tileSize) + (tileSize / 2);
  const pixelY = offsetY + (y * tileSize) + (tileSize / 2);

  // Map 0-7 direction to 1-8 filename
  const dirFileIndex = direction + 1;

  // State for animation
  const [animationData, setAnimationData] = useState<SpriteAnimationData | null>(null);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Calculate unique asset ID
  const assetId = `entity_${entity.uuid}_dir${dirFileIndex}`;
  
  // Load animation data
  useEffect(() => {
    const loadAnimationData = async () => {
      try {
        setIsLoading(true);
        setLoadError(null);

        const jsonPath = `/assets/entities/Knight_Idle_dir${dirFileIndex}.json`;
        const response = await fetch(jsonPath);
        if (!response.ok) {
          throw new Error(`Failed to load animation data: ${response.statusText}`);
        }
        const animData = await response.json();
        setAnimationData(animData);
        setIsLoading(false);
      } catch (err) {
        setLoadError(`Error loading animation data: ${err instanceof Error ? err.message : String(err)}`);
      }
    };

    loadAnimationData();
  }, [dirFileIndex]);

  // Animation ticker
  useTick(() => {
    if (isLoading || !animationData) return;

    const animation = animationData.meta.frameAnimations[0];
    const fps = animation.fps * animation.speed_scale;
    const frameDuration = 1000 / fps;
    
    setElapsed(prev => {
      const newElapsed = prev + 16.6667;
      if (newElapsed >= frameDuration) {
        setCurrentFrame(prevFrame => {
          const nextFrame = (prevFrame + 1) % (animation.to - animation.from + 1);
          return nextFrame;
        });
        return 0;
      }
      return newElapsed;
    });
  });

  if (loadError) {
    console.warn(`Failed to load sprite for ${entity.name}:`, loadError);
    return null;
  }

  if (isLoading || !animationData) {
    return null; // Don't show placeholder
  }

  // Get the current frame texture from cache
  const frameTexture = textureCache[`${assetId}_frame${currentFrame + animationData.meta.frameAnimations[0].from}`];
  if (!frameTexture) {
    return null; // Don't show placeholder if texture isn't ready
  }

  // Calculate scale to fit tile size with 20% increase
  const BASE_SCALE = 2.4; // 2.0 (original) * 1.2 (20% larger)
  const scale = (tileSize / Math.max(frameTexture.width, frameTexture.height)) * BASE_SCALE;

  // Calculate vertical offset to position sprite slightly south
  const verticalOffset = tileSize / 6; // Move down by 1/6 of tile size

  return (
    <pixiContainer x={pixelX} y={pixelY}>
      <pixiSprite
        texture={frameTexture}
        anchor={0.5} // Center anchor
        scale={scale}
        y={verticalOffset} // Positive offset to move south
      />
    </pixiContainer>
  );
}; 