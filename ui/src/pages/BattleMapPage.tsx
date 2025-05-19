import * as React from 'react';
import { Box, useTheme, Snackbar, Alert } from '@mui/material';
import CharacterSheetPage from './CharacterSheetPage';
import EventQ from '../components/events/EventQ';
import BattleMapCanvas from '../components/battlemap/BattleMapCanvas';
import TileEditor, { useTileEditor } from '../components/battlemap/TileEditor';
import EntitySummaryOverlay from '../components/battlemap/EntitySummaryOverlay';
import { fetchGridSnapshot } from '../api/tileApi';
import { characterStore, characterActions } from '../store/characterStore';
import { useSnapshot } from 'valtio';
import { AttackAnimation } from '../components/battlemap/AttackAnimation';
import { Application, extend } from '@pixi/react';
import { Container, AnimatedSprite } from 'pixi.js';
import BackgroundMusicPlayer from '../components/music/BackgroundMusicPlayer';
import { Direction } from '../components/battlemap/DirectionalEntitySprite';

// Extend the PixiJS components
extend({ Container, AnimatedSprite });

const BattleMapPage: React.FC = () => {
  const theme = useTheme();
  const [containerSize, setContainerSize] = React.useState({ width: 0, height: 0 });
  const [gridSize, setGridSize] = React.useState({ width: 30, height: 20 }); // Default size
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [isLocked, setIsLocked] = React.useState(false);
  const { handleCellClick, TileEditor, isEditing } = useTileEditor();
  const snap = useSnapshot(characterStore);
  const [redrawCounter, setRedrawCounter] = React.useState(0);
  const [attackAnimation, setAttackAnimation] = React.useState<{
    x: number, 
    y: number, 
    scale: number,
    angle?: number,
    flipX?: boolean,
    isHit: boolean,
    sourceEntityId: string,
    targetEntityId: string
  } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [musicPlayerMinimized, setMusicPlayerMinimized] = React.useState(true);

  // Panel states
  const [isCharacterSheetCollapsed, setIsCharacterSheetCollapsed] = React.useState(false);

  // Toggle music player size
  const toggleMusicPlayerSize = React.useCallback(() => {
    setMusicPlayerMinimized(prev => !prev);
  }, []);

  // Update container size when window resizes
  React.useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        const height = containerRef.current.clientHeight;
        setContainerSize({ width, height });
      }
    };

    // Initial size
    updateSize();

    // Add resize listener
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Fetch grid dimensions from backend
  React.useEffect(() => {
    const fetchData = async () => {
      try {
        const grid = await fetchGridSnapshot();
        setGridSize({ width: grid.width, height: grid.height });
        await characterActions.fetchSummaries();
      } catch (error) {
        console.error('Error fetching initial data:', error);
      }
    };

    fetchData();
  }, []);

  // Handle target selection
  const handleTargetSelect = (entityId: string) => {
    characterActions.setSelectedEntity(entityId);
    characterActions.setDisplayedEntity(entityId);
  };

  // Handle attack on entity
  const handleAttack = (
    targetId: string, 
    targetX: number, 
    targetY: number, 
    tileSize: number,
    mapState?: { 
      offsetX: number; 
      offsetY: number; 
      gridOffsetX: number; 
      gridOffsetY: number; 
      actualTileSize: number
    }
  ) => {
    const selectedEntity = snap.selectedEntityId ? snap.summaries[snap.selectedEntityId] : undefined;
    
    if (!selectedEntity) {
      setError("No entity selected to perform attack");
      return;
    }

    // Start timing measurement
    const clickTime = performance.now();
    console.log(`[Attack Timing] Click detected at ${clickTime}ms`);
    
    // Execute attack on the target entity
    const params = new URLSearchParams({
      weapon_slot: 'MAIN_HAND',
      attack_name: 'Attack'
    });
    
    console.log(`[Attack Timing] Sending attack request at ${performance.now() - clickTime}ms from click`);
    
    fetch(`/api/entities/${selectedEntity.uuid}/attack/${targetId}?${params}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    .then(async response => {
      const responseTime = performance.now();
      console.log(`[Attack Timing] Received server response at ${responseTime - clickTime}ms from click`);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail?.message || 'Attack failed');
      }
      return response.json();
    })
    .then(data => {
      // Check if the event was canceled
      if (data.event.canceled) {
        console.log('[Attack Result] Attack was canceled:', data.event.status_message);
        return; // Don't play animation for canceled attacks
      }

      // Animation is shown for both hits and misses
      const animationStartTime = performance.now();
      console.log(`[Attack Timing] Starting animation at ${animationStartTime - clickTime}ms from click`);
      
      // Log the entire event data for debugging
      console.log('Attack event data:', data.event);

      // Get detailed data about the hit property
      console.log('[HIT DEBUG] Raw hit value:', data.event.hit);
      console.log('[HIT DEBUG] Type of hit value:', typeof data.event.hit);
      console.log('[HIT DEBUG] JSON of hit data:', JSON.stringify(data.event, null, 2));

      // Determine if the attack was a hit based on event data
      const statusMsg = data.event.status_message || '';
      const isHit = !statusMsg.includes('MISS') && !statusMsg.includes('missed');
      console.log(`[Attack Result] Attack ${isHit ? 'hit' : 'missed'} (isHit=${isHit}) based on status message: "${statusMsg}"`);

      // Get fresh references to entities from store to ensure latest positions
      const currentSelectedEntity = snap.summaries[selectedEntity.uuid];
      const currentTargetEntity = snap.summaries[targetId];
      
      if (!currentSelectedEntity || !currentTargetEntity) {
        console.error("Could not find entities for animation");
        return;
      }

      // Calculate the offset to center the grid (same as DirectionalEntitySprite)
      const actualTileSize = mapState?.actualTileSize || tileSize;
      const offsetX = (containerSize.width - (gridSize.width * actualTileSize)) / 2 + (mapState?.gridOffsetX || 0);
      const offsetY = (containerSize.height - (gridSize.height * actualTileSize)) / 2 + (mapState?.gridOffsetY || 0);

      // Get current positions from the store
      const [sourceGridX, sourceGridY] = currentSelectedEntity.position;
      const [targetGridX, targetGridY] = currentTargetEntity.position;
      
      // Calculate screen coordinates using the same formula as DirectionalEntitySprite
      const sourceX = offsetX + (sourceGridX * actualTileSize) + (actualTileSize / 2);
      const sourceY = offsetY + (sourceGridY * actualTileSize) + (actualTileSize / 2);
      const targetX = offsetX + (targetGridX * actualTileSize) + (actualTileSize / 2);
      const targetY = offsetY + (targetGridY * actualTileSize) + (actualTileSize / 2);
      
      // Calculate the midpoint between the two entities
      const midX = (sourceX + targetX) / 2;
      const midY = (sourceY + targetY) / 2;
      
      // Calculate animation scale based on tile size
      const scale = actualTileSize / 32;

      // Calculate the difference between the source and target positions
      const dx = targetX - sourceX;
      const dy = targetY - sourceY;

      // Calculate the rotation angle based on the direction
      let rotation = 0;
      let direction = "";

      // Cardinal and diagonal directions using only rotation
      if (dx > 0 && dy > 0) {
        // Southeast (attacker is northwest of target)
        rotation = Math.PI / 4; // 45 degrees
        direction = "SE";
      } else if (dx > 0 && dy < 0) {
        // Northeast (attacker is southwest of target)
        rotation = -Math.PI / 4; // -45 degrees
        direction = "NE";
      } else if (dx < 0 && dy > 0) {
        // Southwest (attacker is northeast of target)
        rotation = 3 * Math.PI / 4; // 135 degrees
        direction = "SW";
      } else if (dx < 0 && dy < 0) {
        // Northwest (attacker is southeast of target)
        rotation = -3 * Math.PI / 4; // -135 degrees
        direction = "NW";
      } else if (Math.abs(dx) < Math.abs(dy)) {
        // Vertical direction is primary
        if (dy > 0) {
          // South (attacker is north of target)
          rotation = Math.PI / 2; // 90 degrees
          direction = "S";
        } else {
          // North (attacker is south of target)
          rotation = -Math.PI / 2; // -90 degrees
          direction = "N";
        }
      } else {
        // Horizontal direction is primary
        if (dx > 0) {
          // East (attacker is west of target)
          rotation = 0;
          direction = "E";
        } else {
          // West (attacker is east of target)
          rotation = Math.PI; // 180 degrees
          direction = "W";
        }
      }

      // Map direction string to Direction enum
      let entityDirection;
      switch (direction) {
        case "N": entityDirection = Direction.N; break;
        case "NE": entityDirection = Direction.NE; break;
        case "E": entityDirection = Direction.E; break;
        case "SE": entityDirection = Direction.SE; break;
        case "S": entityDirection = Direction.S; break;
        case "SW": entityDirection = Direction.SW; break;
        case "W": entityDirection = Direction.W; break;
        case "NW": entityDirection = Direction.NW; break;
        default: entityDirection = Direction.S; // Default to south if something goes wrong
      }

      // Update entity direction before starting animation
      characterActions.updateEntityDirection(currentSelectedEntity.uuid, entityDirection);
      // Force a re-render of the entity
      setRedrawCounter(prev => prev + 1);

      // Generate helpful debug info
      console.log('[Attack Direction]', {
        sourcePos: [sourceX, sourceY],
        targetPos: [targetX, targetY],
        dx,
        dy,
        direction,
        entityDirection,
        rotation: rotation * (180 / Math.PI), // Log in degrees for readability
        isHit
      });

      // Animation state with hit/miss status
      setAttackAnimation({ 
        x: midX, 
        y: midY, 
        scale,
        angle: rotation,
        flipX: false,
        isHit,
        sourceEntityId: currentSelectedEntity.uuid,
        targetEntityId: currentTargetEntity.uuid
      });
      
      // Log success event
      console.log('Attack executed:', data.event);
    })
    .catch(error => {
      console.error('Error executing attack:', error.message);
      
      // Show error in UI
      const errorMessage = error.message === 'Failed to fetch' 
        ? 'Network error - could not reach server'
        : error.message;
        
      setError(errorMessage);
      console.log(`[Attack Timing] Attack failed at ${performance.now() - clickTime}ms from click:`, errorMessage);
    });
  };

  const entities = Object.values(snap.summaries);

  return (
    <Box sx={{ 
      position: 'absolute',
      top: 64, // Height of AppBar
      left: 0,
      right: 0,
      bottom: 0,
      bgcolor: '#000000',
      display: 'flex',
      overflow: 'hidden'
    }}>
      {/* Character Sheet Panel */}
      <CharacterSheetPage 
        isCollapsed={isCharacterSheetCollapsed}
        onToggleCollapse={() => setIsCharacterSheetCollapsed(!isCharacterSheetCollapsed)}
        onSwitchToEntities={() => {}}
      />

      {/* Error Snackbar */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          onClose={() => setError(null)} 
          severity="error"
          variant="filled"
        >
          {error}
        </Alert>
      </Snackbar>

      {/* Main content area */}
      <Box 
        ref={containerRef}
        sx={{ 
          flex: 1,
          display: 'flex',
          position: 'relative',
          overflow: 'hidden',
          bgcolor: '#000000',
        }}
      >
        {/* Tile Editor */}
        <TileEditor isLocked={isLocked} />

        {containerSize.width > 0 && containerSize.height > 0 && (
          <>
            <BattleMapCanvas 
              width={gridSize.width}
              height={gridSize.height}
              tileSize={32}
              onCellClick={(x, y, onOptimisticUpdate) => handleCellClick(x, y, onOptimisticUpdate, isLocked)}
              isEditing={isEditing}
              onLockChange={setIsLocked}
              isLocked={isLocked}
              containerWidth={containerSize.width}
              containerHeight={containerSize.height}
              onEntityClick={(targetId, x, y, tileSize, mapState) => handleAttack(targetId, x, y, tileSize, mapState)}
              redrawCounter={redrawCounter}
            />

            {/* Attack Animation Container */}
            {attackAnimation && (
              <Box sx={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                width: '100%', 
                height: '100%', 
                pointerEvents: 'none'
              }}>
                <Application
                  width={containerSize.width}
                  height={containerSize.height}
                  backgroundColor={0x000000}
                  backgroundAlpha={0}
                >
                  <AttackAnimation
                    x={attackAnimation.x}
                    y={attackAnimation.y}
                    scale={attackAnimation.scale}
                    flipX={attackAnimation.flipX}
                    angle={attackAnimation.angle}
                    isHit={attackAnimation.isHit}
                    onComplete={() => setAttackAnimation(null)}
                  />
                </Application>
              </Box>
            )}
          </>
        )}

        {/* Entity Summary Overlays */}
        {entities.map((entity, index) => (
          <EntitySummaryOverlay
            key={entity.uuid}
            entity={entity}
            isSelected={entity.uuid === snap.selectedEntityId}
            isDisplayed={entity.uuid === snap.displayedEntityId}
            onSelectTarget={handleTargetSelect}
            index={index}
          />
        ))}
      </Box>

      {/* Background Music Player */}
      <BackgroundMusicPlayer 
        minimized={musicPlayerMinimized}
        onToggleMinimize={toggleMusicPlayerSize}
      />

      {/* Event Queue */}
      <EventQ />
    </Box>
  );
};

export default BattleMapPage; 