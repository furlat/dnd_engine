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
  const [attackAnimation, setAttackAnimation] = React.useState<{x: number, y: number, scale: number} | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  // Panel states
  const [isCharacterSheetCollapsed, setIsCharacterSheetCollapsed] = React.useState(false);

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
  const handleAttack = (targetId: string, targetX: number, targetY: number, tileSize: number) => {
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
      // Only show animation if attack was successful
      const animationStartTime = performance.now();
      console.log(`[Attack Timing] Starting animation at ${animationStartTime - clickTime}ms from click`);
      
      // Calculate animation scale based on tile size
      const scale = tileSize / 32;
      setAttackAnimation({ x: targetX, y: targetY, scale });
      
      // Log success event
      console.log('Attack successful:', data.event);
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
              onEntityClick={(targetId, x, y, tileSize) => handleAttack(targetId, x, y, tileSize)}
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

      {/* Event Queue */}
      <EventQ />
    </Box>
  );
};

export default BattleMapPage; 