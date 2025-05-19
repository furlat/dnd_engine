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
import { mapStore, mapActions } from '../store/mapStore';
import { entityDirectionState } from '../store/entityDirectionStore';

// Extend the PixiJS components
extend({ Container, AnimatedSprite });

const BattleMapPage: React.FC = () => {
  const theme = useTheme();
  const [containerSize, setContainerSize] = React.useState({ width: 0, height: 0 });
  const containerRef = React.useRef<HTMLDivElement>(null);
  const { handleCellClick, TileEditor, isEditing } = useTileEditor();
  const snap = useSnapshot(characterStore);
  const mapSnap = useSnapshot(mapStore);
  const [redrawCounter, setRedrawCounter] = React.useState(0);
  const [attackAnimation, setAttackAnimation] = React.useState<{
    isHit: boolean,
    sourceEntityId: string,
    targetEntityId: string
  } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [musicPlayerMinimized, setMusicPlayerMinimized] = React.useState(true);
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
        mapActions.setContainerSize(width, height);
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
        mapActions.setGridDimensions(grid.width, grid.height);
        await characterActions.fetchSummaries();
      } catch (error) {
        console.error('Error fetching initial data:', error);
      }
    };

    fetchData();
  }, []);

  // Handle target selection
  const handleTargetSelect = async (entityId: string) => {
    // The selected entity should be the one clicked on
    console.log(`[TARGET-SELECT] Entity clicked: ${entityId}`);
    
    if (!entityId) {
      return; // Ignore empty selections
    }
    
    // Simply set this entity as the selected entity
    characterActions.setSelectedEntity(entityId);
    characterActions.setDisplayedEntity(entityId);
    
    // No need to set targets at this stage - just select the entity
    console.log(`[TARGET-SELECT] Set ${entityId} as selected entity`);
  };

  // Handle attack on entity
  const handleAttack = async (
    targetId: string
  ) => {
    // Skip using the snapshot and access store directly
    const selectedEntityId = characterStore.selectedEntityId;
    const selectedEntity = selectedEntityId ? characterStore.summaries[selectedEntityId] : undefined;
    
    // Log state for debugging
    console.log(`[ATTACK-FLOW] Selected entity ID: ${selectedEntityId}, Target ID: ${targetId}`);
    console.log(`[ATTACK-FLOW] Entity summaries:`, Object.keys(characterStore.summaries));
    
    if (!selectedEntityId || !selectedEntity) {
      console.error("[ATTACK-FLOW] No valid source entity found in state");
      
      // Try to force a refresh and report the error to the user
      try {
        await characterActions.forceRefresh();
        const refreshedSelectedId = characterStore.selectedEntityId;
        const refreshedEntity = refreshedSelectedId ? characterStore.summaries[refreshedSelectedId] : undefined;
        
        if (!refreshedEntity) {
          setError("No entity selected to perform attack");
          return;
        }
        
        // Continue with refreshed entity data
        console.log(`[ATTACK-FLOW] Recovered after refresh with entity ${refreshedEntity.uuid}`);
      } catch (err) {
        setError("No entity selected to perform attack");
        return;
      }
    }
    
    // Re-check after potential refresh
    const attackerEntityId = characterStore.selectedEntityId;
    const attackerEntity = attackerEntityId ? characterStore.summaries[attackerEntityId] : undefined;
    
    if (!attackerEntityId || !attackerEntity) {
      setError("Could not determine attacking entity");
      return;
    }

    // Start timing measurement
    const clickTime = performance.now();
    console.log(`[ATTACK-FLOW] Attack initiated at ${clickTime.toFixed(2)}ms - Source: ${attackerEntity.uuid}, Target: ${targetId}`);
    
    try {
      // We can directly use the combatApi without refresh since the attack API will get fresh data
      console.log(`[ATTACK-FLOW] Executing attack - Source: ${attackerEntity.uuid}, Target: ${targetId}`);

      // Use the combatApi module for attack
      const { executeAttack } = await import('../api/combatApi');
      const result = await executeAttack(attackerEntity.uuid, targetId, 'MAIN_HAND', 'Attack');
      
      // Check if the event was canceled
      if (result.event.canceled) {
        console.log('[ATTACK-FLOW] Attack was canceled:', result.event.status_message);
        return; // Don't play animation for canceled attacks
      }

      // Determine if the attack was a hit based on event data
      const statusMsg = result.event.status_message || '';
      const isHit = !statusMsg.includes('MISS') && !statusMsg.includes('missed');
      console.log(`[ATTACK-FLOW] Attack result: ${isHit ? 'HIT' : 'MISS'} - ${statusMsg}`);

      // Compute direction based on entity positions - use spreading to handle readonly arrays
      const direction = entityDirectionState.computeDirection(
        [...attackerEntity.position] as [number, number],
        [...characterStore.summaries[targetId].position] as [number, number]
      );

      // Update entity direction before starting animation
      entityDirectionState.setDirection(attackerEntity.uuid, direction);

      // Start animation
      setAttackAnimation({ 
        isHit,
        sourceEntityId: attackerEntity.uuid,
        targetEntityId: targetId
      });
      
      console.log(`[ATTACK-FLOW] Attack animation started - Hit: ${isHit}`);
    } catch (error) {
      console.error('[ATTACK-FLOW] Error executing attack:', error);
      
      // Show error in UI
      const errorMessage = error instanceof Error
        ? (error.message === 'Failed to fetch'
            ? 'Network error - could not reach server'
            : error.message)
        : 'Unknown error occurred';
        
      setError(errorMessage);
    }
  };

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
        <TileEditor isLocked={mapSnap.isLocked} />

        {containerSize.width > 0 && containerSize.height > 0 && (
          <>
            <BattleMapCanvas 
              width={mapSnap.gridWidth}
              height={mapSnap.gridHeight}
              tileSize={mapSnap.tileSize}
              onCellClick={(x, y, onOptimisticUpdate) => handleCellClick(x, y, onOptimisticUpdate, mapSnap.isLocked)}
              isEditing={isEditing}
              onLockChange={mapActions.toggleLock}
              isLocked={mapSnap.isLocked}
              containerWidth={containerSize.width}
              containerHeight={containerSize.height}
              onEntityClick={(targetId) => handleAttack(targetId)}
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
                    isHit={attackAnimation.isHit}
                    sourceEntityId={attackAnimation.sourceEntityId}
                    targetEntityId={attackAnimation.targetEntityId}
                    onComplete={() => setAttackAnimation(null)}
                  />
                </Application>
              </Box>
            )}
          </>
        )}

        {/* Entity Summary Overlays */}
        {Object.values(snap.summaries).map((entity, index) => (
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