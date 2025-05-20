import React, { useState, useEffect, useCallback } from 'react';
import { useSnapshot } from 'valtio';
import { Assets, Texture } from 'pixi.js';
import { battlemapStore } from '../../../store';
import type { EntitySummary } from '../../../models/character';
import { Direction } from '../DirectionalEntitySprite';

// Cache for entity textures
const textureCache: Record<string, Texture> = {};

interface CanvasEntitiesProps {
  containerSize: {
    width: number;
    height: number;
  };
  tileSize: number;
  isVisibilityEnabled: boolean;
  onEntityClick: (entityId: string) => void;
}

export const CanvasEntities: React.FC<CanvasEntitiesProps> = ({
  containerSize,
  tileSize,
  isVisibilityEnabled,
  onEntityClick
}) => {
  const snap = useSnapshot(battlemapStore);
  
  // Calculate grid offset to center it in the container
  const gridWidth = snap.grid.width;
  const gridHeight = snap.grid.height;
  const offsetX = (containerSize.width - (gridWidth * tileSize)) / 2;
  const offsetY = (containerSize.height - (gridHeight * tileSize)) / 2;

  // Helper to generate entity key for stable component identity
  const getEntityKey = useCallback((entity: any, index: number) => {
    return `entity-${entity.uuid || index}`;
  }, []);
  
  // Handle entity click
  const handleEntityClick = useCallback((entityId: string) => {
    if (snap.controls.isLocked) return;
    onEntityClick(entityId);
  }, [snap.controls.isLocked, onEntityClick]);

  return (
    <pixiContainer>
      {Object.values(snap.entities.summaries).map((entity, index) => (
        <EntitySprite 
          key={getEntityKey(entity, index)}
          entity={entity as any}
          offsetX={offsetX}
          offsetY={offsetY}
          tileSize={tileSize}
          direction={snap.entities.directions[entity.uuid] || Direction.S}
          isSelected={entity.uuid === snap.entities.selectedEntityId}
          onClick={() => handleEntityClick(entity.uuid)}
        />
      ))}
    </pixiContainer>
  );
};

interface EntitySpriteProps {
  entity: EntitySummary;
  offsetX: number;
  offsetY: number;
  tileSize: number;
  direction: Direction;
  isSelected: boolean;
  onClick: () => void;
}

const EntitySprite: React.FC<EntitySpriteProps> = ({
  entity,
  offsetX,
  offsetY,
  tileSize,
  direction,
  isSelected,
  onClick
}) => {
  const [texture, setTexture] = useState<Texture | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  
  // Calculate position 
  const [x, y] = entity.position;
  const pixelX = offsetX + (x * tileSize) + (tileSize / 2);
  const pixelY = offsetY + (y * tileSize) + (tileSize / 2);
  
  // Load texture
  useEffect(() => {
    const loadTexture = async () => {
      if (!entity.sprite_name) return;
      
      try {
        const spritePath = `/sprites/${entity.sprite_name}`;
        
        // Check cache first
        if (textureCache[spritePath]) {
          setTexture(textureCache[spritePath]);
          return;
        }
        
        // Load texture if not in cache
        const loadedTexture = await Assets.load(spritePath);
        textureCache[spritePath] = loadedTexture;
        setTexture(loadedTexture);
      } catch (error) {
        console.error(`Error loading sprite for ${entity.name}:`, error);
      }
    };
    
    loadTexture();
  }, [entity.sprite_name, entity.name]);
  
  // No rendering if texture isn't loaded
  if (!texture) return null;
  
  // Highlight color for selected/hovered state
  const tint = isSelected ? 0x00FFFF : isHovered ? 0xFFFFFF : 0xCCCCCC;
  
  // Handler functions
  const handlePointerOver = () => setIsHovered(true);
  const handlePointerOut = () => setIsHovered(false);
  
  return (
    <pixiContainer 
      x={pixelX} 
      y={pixelY}
      interactive={true}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onPointerDown={onClick}
    >
      <pixiSprite
        texture={texture}
        anchor={0.5}
        width={tileSize * 0.9}
        height={tileSize * 0.9}
        tint={tint}
      />
      {isSelected && (
        <pixiGraphics
          draw={(g) => {
            g.clear();
            g.lineStyle(2, 0x00FFFF, 1);
            g.drawCircle(0, 0, tileSize / 2 + 2);
          }}
        />
      )}
    </pixiContainer>
  );
}; 