import React, { useCallback, useEffect, useRef, useMemo, useState } from 'react';
import { Graphics, Texture, Container, Sprite, Assets } from 'pixi.js';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../../store';
import { TileSummary } from '../../../types/battlemap_types';

// Initialize Assets system for sprite loading
Assets.init({
  basePath: '/',
});

// Create a cache for loaded textures
const textureCache: Record<string, Texture> = {};

interface CanvasGridProps {
  gridWidth: number;
  gridHeight: number;
  tileSize: number;
  containerSize: {
    width: number;
    height: number;
  };
  isGridVisible: boolean;
}

export const CanvasGrid: React.FC<CanvasGridProps> = ({
  gridWidth,
  gridHeight,
  tileSize,
  containerSize,
  isGridVisible
}) => {
  const snap = useSnapshot(battlemapStore);
  const lastRenderTimeRef = useRef(Date.now());
  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(Date.now());
  const fpsRef = useRef(0);
  const tilesRef = useRef(snap.grid.tiles);
  const [tileTextures, setTileTextures] = useState<Record<string, Texture | null>>({});
  
  // Only update the tiles reference when not moving to preserve a stable snapshot
  useEffect(() => {
    if (!snap.view.wasd_moving) {
      tilesRef.current = snap.grid.tiles;
    }
  }, [snap.grid.tiles, snap.view.wasd_moving]);

  // Load tile textures when tiles change
  useEffect(() => {
    const loadTileTextures = async () => {
      const newTextures: Record<string, Texture | null> = {};
      const loadPromises: Promise<void>[] = [];

      // Only attempt to load sprites for tiles that have a sprite_name
      Object.values(tilesRef.current).forEach(tile => {
        if (tile.sprite_name) {
          const spritePath = `/tiles/${tile.sprite_name}`;
          
          // Check if already in cache
          if (textureCache[spritePath]) {
            newTextures[tile.uuid] = textureCache[spritePath];
          } else {
            // Load new texture
            const loadPromise = (async () => {
              try {
                let loadedTexture = Assets.get(spritePath);
                
                if (!loadedTexture) {
                  loadedTexture = await Assets.load(spritePath);
                  textureCache[spritePath] = loadedTexture;
                }
                
                newTextures[tile.uuid] = loadedTexture;
              } catch (error) {
                console.error(`Error loading tile sprite ${spritePath}:`, error);
                newTextures[tile.uuid] = null;
              }
            })();
            
            loadPromises.push(loadPromise);
          }
        } else {
          newTextures[tile.uuid] = null;
        }
      });

      // Wait for all textures to load
      await Promise.all(loadPromises);
      setTileTextures(prev => ({...prev, ...newTextures}));
    };

    // Only load new textures if not during WASD movement
    if (!snap.view.wasd_moving) {
      loadTileTextures();
    }
  }, [tilesRef.current]);
  
  // Track FPS
  useEffect(() => {
    const updateFps = () => {
      frameCountRef.current++;
      
      const now = Date.now();
      const elapsed = now - lastFpsUpdateRef.current;
      
      if (elapsed >= 1000) { // Update FPS once per second
        fpsRef.current = Math.round(frameCountRef.current * 1000 / elapsed);
        console.log(`Grid Rendering FPS: ${fpsRef.current}`);
        
        frameCountRef.current = 0;
        lastFpsUpdateRef.current = now;
      }
      
      requestAnimationFrame(updateFps);
    };
    
    const animFrameId = requestAnimationFrame(updateFps);
    return () => cancelAnimationFrame(animFrameId);
  }, []);
  
  // Define a minimum margin from the left side to ensure we don't draw under entity panel
  const ENTITY_PANEL_WIDTH = 250;
  
  // Use memoized calculations for grid positioning to prevent recalculation during movement
  const gridPositions = useMemo(() => {
    // Calculate grid offset to center it in the available space (accounting for entity panel)
    const availableWidth = containerSize.width - ENTITY_PANEL_WIDTH;
    const gridPixelWidth = gridWidth * tileSize;
    const gridPixelHeight = gridHeight * tileSize;
    
    // Center grid in the available space (starting from entity panel width)
    const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
    const baseOffsetY = (containerSize.height - gridPixelHeight) / 2;
    
    // Apply the offset from WASD controls
    const offsetX = baseOffsetX + snap.view.offset.x;
    const offsetY = baseOffsetY + snap.view.offset.y;
    
    return {
      availableWidth,
      gridPixelWidth,
      gridPixelHeight,
      baseOffsetX,
      baseOffsetY,
      offsetX,
      offsetY
    };
  }, [
    containerSize.width,
    containerSize.height,
    gridWidth,
    gridHeight,
    tileSize,
    snap.view.offset.x,
    snap.view.offset.y
  ]);
  
  // Draw grid lines
  const drawGrid = useCallback((g: Graphics) => {
    if (!isGridVisible) {
      g.clear();
      return;
    }

    g.clear();
    
    try {
      // Set line style
      if (typeof g.setStrokeStyle === 'function') {
        g.setStrokeStyle({
          width: 1,
          color: 0xFFFFFF,
          alpha: 0.3
        });
      } else {
        g.lineStyle(1, 0xFFFFFF, 0.3);
      }
      
      const { offsetX, offsetY } = gridPositions;
      
      // Draw vertical lines
      for (let i = 0; i <= gridWidth; i++) {
        const x = offsetX + (i * tileSize);
        g.moveTo(x, offsetY);
        g.lineTo(x, offsetY + (gridHeight * tileSize));
      }
      
      // Draw horizontal lines
      for (let i = 0; i <= gridHeight; i++) {
        const y = offsetY + (i * tileSize);
        g.moveTo(offsetX, y);
        g.lineTo(offsetX + (gridWidth * tileSize), y);
      }

      // Use stroke if available
      if (typeof g.stroke === 'function') {
        g.stroke();
      }
    } catch (error) {
      console.error('Error drawing grid:', error);
    }
  }, [gridPositions, gridWidth, gridHeight, tileSize, isGridVisible]);
  
  // Render a single tile
  const renderTile = useCallback((tile: TileSummary, g: Graphics) => {
    const { offsetX, offsetY } = gridPositions;
    const [x, y] = tile.position;
    const tileX = offsetX + (x * tileSize);
    const tileY = offsetY + (y * tileSize);
    
    // Check if we have a texture for this tile
    const texture = tileTextures[tile.uuid];
    
    if (texture) {
      // Use the sprite for rendering
      return (
        <pixiSprite
          key={tile.uuid}
          texture={texture}
          x={tileX}
          y={tileY}
          width={tileSize}
          height={tileSize}
        />
      );
    } else {
      // Use a fallback color if no texture or failed to load
      const color = tile.walkable ? 0x333333 : 0x666666;
      g.beginFill(color);
      g.drawRect(tileX, tileY, tileSize, tileSize);
      g.endFill();
      return null;
    }
  }, [gridPositions, tileSize, tileTextures]);
  
  // Draw tiles with background
  const drawTilesBackground = useCallback((g: Graphics) => {
    const { offsetX, offsetY } = gridPositions;
    
    // Clear the canvas
    g.clear();
    
    try {
      // Draw background
      g.beginFill(0x000000);
      g.drawRect(
        offsetX, 
        offsetY, 
        gridWidth * tileSize, 
        gridHeight * tileSize
      );
      g.endFill();
      
      // Draw tiles without textures as fallback rectangles
      Object.values(tilesRef.current).forEach(tile => {
        // Only draw fallback rectangles here
        if (!tileTextures[tile.uuid]) {
          renderTile(tile, g);
        }
      });
    } catch (error) {
      console.error('Error drawing tiles background:', error);
    }
  }, [gridPositions, gridWidth, gridHeight, tileSize, renderTile, tileTextures]);
  
  // Cell highlight
  const drawCellHighlight = useCallback((g: Graphics) => {
    // Skip highlighting during movement for better performance
    if (snap.view.wasd_moving) {
      g.clear();
      return;
    }
    
    const { x, y } = snap.view.hoveredCell;
    
    // Only draw if valid coordinates
    if (x < 0 || y < 0 || x >= gridWidth || y >= gridHeight) {
      g.clear();
      return;
    }
    
    const { offsetX, offsetY } = gridPositions;
    
    try {
      g.clear();
      g.beginFill(0x00FF00, 0.3);
      g.drawRect(
        offsetX + (x * tileSize),
        offsetY + (y * tileSize),
        tileSize,
        tileSize
      );
      g.endFill();
    } catch (error) {
      console.error('Error drawing cell highlight:', error);
    }
  }, [snap.view.hoveredCell, snap.view.wasd_moving, gridPositions, gridWidth, gridHeight, tileSize]);
  
  // Get sprite components for tiles with textures
  const tileSprites = useMemo(() => {
    return Object.values(tilesRef.current)
      .filter(tile => tileTextures[tile.uuid]) // Only include tiles with textures
      .map(tile => {
        const { offsetX, offsetY } = gridPositions;
        const [x, y] = tile.position;
        const tileX = offsetX + (x * tileSize);
        const tileY = offsetY + (y * tileSize);
        
        return (
          <pixiSprite
            key={tile.uuid}
            texture={tileTextures[tile.uuid]!}
            x={tileX}
            y={tileY}
            width={tileSize}
            height={tileSize}
          />
        );
      });
  }, [tilesRef.current, tileTextures, gridPositions, tileSize]);
  
  return (
    <>
      <pixiContainer>
        {/* Background and non-textured tiles */}
        <pixiGraphics draw={drawTilesBackground} />
        
        {/* Sprites for tiles with textures */}
        {tileSprites}
        
        {/* Grid overlay */}
        <pixiGraphics draw={drawGrid} />
        
        {/* Cell highlight */}
        <pixiGraphics draw={drawCellHighlight} />
      </pixiContainer>
    </>
  );
}; 