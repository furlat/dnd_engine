import * as React from 'react';
import { Box, Snackbar, Alert } from '@mui/material';
import CharacterSheetPage from './CharacterSheetPage';
import EventQ from '../components/events/EventQ';
import { BattleMapCanvas } from '../components/battlemap';
import { EntitySummaryOverlays } from '../components/battlemap/summaries';
import BackgroundMusicPlayer from '../components/music/BackgroundMusicPlayer';
import { EffectsLayer } from '../components/battlemap/effects';
import { useEffects, useGrid, useMapControls } from '../hooks/battlemap';
import { useError } from '../hooks/useError';
import { battlemapActions } from '../store';

/**
 * BattleMapPage is responsible for overall layout of the game area
 * It positions the main components (character sheet, battlemap, event queue)
 * but delegates all game logic to hooks and child components
 */
const BattleMapPage: React.FC = () => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const { containerSize, setContainerSize } = useGrid();
  const { isMusicPlayerMinimized, toggleMusicPlayerSize } = useMapControls();
  const { attackEffect } = useEffects();
  const { error, setError, clearError } = useError();
  
  // State for UI collapsing
  const [isCharacterSheetCollapsed, setIsCharacterSheetCollapsed] = React.useState(true);
  const [isEventQCollapsed, setIsEventQCollapsed] = React.useState(true);
  const [showEntityList, setShowEntityList] = React.useState(false);

  // Initialize polling when the component mounts
  React.useEffect(() => {
    battlemapActions.startPolling();
    return () => battlemapActions.stopPolling();
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
  }, [setContainerSize]);

  // Toggle handlers
  const toggleCharacterSheet = React.useCallback(() => {
    setIsCharacterSheetCollapsed(prev => !prev);
  }, []);

  const toggleEventQ = React.useCallback(() => {
    setIsEventQCollapsed(prev => !prev);
  }, []);

  const toggleEntityList = React.useCallback(() => {
    setShowEntityList(prev => !prev);
  }, []);

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
        onToggleCollapse={toggleCharacterSheet}
        onSwitchToEntities={toggleEntityList}
      />

      {/* Error Snackbar */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={clearError}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          onClose={clearError} 
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
        {containerSize.width > 0 && containerSize.height > 0 && (
          <>
            {/* Main battlemap canvas */}
            <BattleMapCanvas />

            {/* Attack effects layer */}
            {attackEffect && (
              <Box sx={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                width: '100%', 
                height: '100%', 
                pointerEvents: 'none'
              }}>
                <EffectsLayer />
              </Box>
            )}
          </>
        )}

        {/* Entity summary overlays positioned absolutely */}
        <EntitySummaryOverlays />
      </Box>

      {/* Background Music Player */}
      <BackgroundMusicPlayer 
        minimized={isMusicPlayerMinimized}
        onToggleMinimize={toggleMusicPlayerSize}
      />

      {/* Event Queue */}
      <EventQ 
        isCollapsed={isEventQCollapsed}
        onToggleCollapse={toggleEventQ}
      />
    </Box>
  );
};

export default BattleMapPage; 