import * as React from 'react';
import { Box, Snackbar, Alert } from '@mui/material';
import CharacterSheetPage from './CharacterSheetPage';
import EventQ from '../components/events/EventQ';
import { BattleMapCanvas } from '../components/battlemap';
import { EntitySummaryOverlays } from '../components/battlemap/summaries';
import BackgroundMusicPlayer from '../components/music/BackgroundMusicPlayer';
import { useMapControls } from '../hooks/battlemap';
// Simple local error hook since we can't find the imported one
const useError = () => {
  const [error, setError] = React.useState<string | null>(null);
  const clearError = React.useCallback(() => setError(null), []);
  return { error, setError, clearError };
};
import { battlemapActions } from '../store';
import { soundActions } from '../store/soundStore';

/**
 * BattleMapPage is responsible for overall layout of the game area
 * It positions the main components (character sheet, battlemap, event queue)
 * but delegates all game logic to hooks and child components
 */
const BattleMapPage: React.FC = () => {
  const { isMusicPlayerMinimized, toggleMusicPlayerSize } = useMapControls();
  const { error, setError, clearError } = useError();
  
  // State for UI collapsing
  const [isCharacterSheetCollapsed, setIsCharacterSheetCollapsed] = React.useState(true);

  // Initialize polling and sound system when the component mounts
  React.useEffect(() => {
    battlemapActions.startPolling();
    
    // Initialize sound system
    soundActions.initialize().catch(error => {
      console.error('[BattleMapPage] Failed to initialize sound system:', error);
    });
    
    return () => battlemapActions.stopPolling();
  }, []);

  // Toggle handlers
  const toggleCharacterSheet = React.useCallback(() => {
    setIsCharacterSheetCollapsed(prev => !prev);
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

      {/* Main content area - Single container with overlays */}
      <Box 
        sx={{ 
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          bgcolor: '#000000',
        }}
      >
        {/* BattleMap Canvas - takes full area */}
        <BattleMapCanvas />

        {/* Entity summary overlays - positioned as overlay */}
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '250px',  // Fixed width for entity summary
            height: '100%',
            zIndex: 10,
            pointerEvents: 'auto',
            bgcolor: '#000000',
          }}
        >
          <EntitySummaryOverlays />
        </Box>
      </Box>

      {/* Background Music Player */}
      <BackgroundMusicPlayer />

      {/* Event Queue */}
      <EventQ />
    </Box>
  );
};

export default BattleMapPage; 