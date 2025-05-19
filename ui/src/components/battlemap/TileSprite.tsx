import React, { useState, useEffect, useCallback } from 'react';
import { Graphics as PixiGraphics, Texture, Assets, Rectangle } from 'pixi.js';
import { TileSummary } from '../../api/tileApi';
import { DeepReadonly } from '../../models/readonly';

// Global tile texture cache to prevent reloading
const tileTextureCache: Record<string, Texture> = {};
const tileLoadPromises: Record<string, Promise<Texture>> = {};

// Preload common tile textures
export const preloadTileTextures = async () => {
  const commonTiles = ['floor.png', 'wall.png', 'door.png'];
  
  console.log('[TILE-CACHE] Preloading common tile textures');
  const startTime = performance.now();
  
  const loadPromises = commonTiles.map(tileName => 
    loadTileTexture(`/tiles/${tileName}`)
  );
  
  try {
    await Promise.all(loadPromises);
    console.log(`[TILE-CACHE] Preloaded ${commonTiles.length} common tile textures in ${(performance.now() - startTime).toFixed(2)}ms`);
  } catch (err) {
    console.error('[TILE-CACHE] Error preloading common tile textures:', err);
  }
};

// Centralized texture loading function with caching
const loadTileTexture = async (spritePath: string): Promise<Texture> => {
  // Return from cache if available
  if (tileTextureCache[spritePath]) {
    return tileTextureCache[spritePath];
  }
  
  // Return existing promise if already loading
  if (spritePath in tileLoadPromises) {
    return tileLoadPromises[spritePath];
  }
  
  // Create and store loading promise
  tileLoadPromises[spritePath] = (async () => {
    try {
      // First check if the asset is already in the PIXI cache
      let texture = Assets.get(spritePath);
      
      if (!texture) {
        texture = await Assets.load({
          src: spritePath,
          alias: spritePath
        });
      }
      
      // Store in our cache
      tileTextureCache[spritePath] = texture;
      return texture;
    } catch (err) {
      console.error(`[TILE-CACHE] Failed to load tile texture ${spritePath}:`, err);
      delete tileLoadPromises[spritePath]; // Remove failed promise
      throw err;
    }
  })();
  
  return tileLoadPromises[spritePath];
};

interface TileSpriteProps {
  tile: TileSummary | DeepReadonly<TileSummary>;
  width: number;
  height: number;
  gridSize: {
    rows: number;
    cols: number;
  };
  tileSize: number;
  alpha?: number;
}

const TileSprite: React.FC<TileSpriteProps> = ({ 
  tile, 
  width, 
  height, 
  gridSize, 
  tileSize, 
  alpha = 1 
}) => {
  const [texture, setTexture] = useState<Texture | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  
  // Calculate the offset to center the grid
  const offsetX = (width - (gridSize.cols * tileSize)) / 2;
  const offsetY = (height - (gridSize.rows * tileSize)) / 2;
  const [x, y] = tile.position;

  // Always define the draw callback with useCallback
  const drawFallback = useCallback((g: PixiGraphics) => {
    const color = tile.walkable ? 0x333333 : 0x666666;
    g.clear();
    g.setFillStyle({
      color: color,
      alpha: 1
    });
    g.rect(
      offsetX + (x * tileSize),
      offsetY + (y * tileSize),
      tileSize,
      tileSize
    );
    g.fill();
  }, [tile.walkable, offsetX, offsetY, x, y, tileSize]);

  useEffect(() => {
    let isMounted = true;
    
    const loadTextureAsync = async () => {
      if (!tile.sprite_name) return;
      
      try {
        const spritePath = `/tiles/${tile.sprite_name}`;
        const loadedTexture = await loadTileTexture(spritePath);
        
        if (!isMounted) return;
        
        setTexture(loadedTexture);
        setLoadError(null);
      } catch (error) {
        if (!isMounted) return;
        
        console.error(`[TILE-CACHE] Error loading tile sprite:`, error);
        setLoadError(error instanceof Error ? error.message : 'Failed to load sprite');
        setTexture(null);
      }
    };
    
    loadTextureAsync();
    
    return () => { isMounted = false; };
  }, [tile.sprite_name]);

  if (loadError || !texture || !tile.sprite_name) {
    return (
      <pixiGraphics draw={drawFallback} />
    );
  }

  return (
    <pixiSprite
      texture={texture}
      x={offsetX + (x * tileSize)}
      y={offsetY + (y * tileSize)}
      width={tileSize}
      height={tileSize}
      alpha={alpha}
    />
  );
};

export default TileSprite; 