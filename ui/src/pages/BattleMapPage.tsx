import * as React from 'react';
import { Box, Typography } from '@mui/material';
import CharacterSheetPage from './CharacterSheetPage';
import EventQ from '../components/events/EventQ';

const BattleMapPage: React.FC = () => {
  return (
    <Box sx={{ 
      position: 'absolute',
      top: 64, // Height of AppBar
      left: 0,
      right: 0,
      bottom: 0,
      bgcolor: 'background.default',
      display: 'flex',
      overflow: 'hidden'
    }}>
      {/* Character Sheet Sidebar */}
      <CharacterSheetPage />

      {/* Main content area */}
      <Box sx={{ 
        flex: 1,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        overflow: 'hidden'
      }}>
        <Typography variant="h3">Battlemap Area</Typography>
      </Box>

      {/* Event Queue */}
      <EventQ />
    </Box>
  );
};

export default BattleMapPage; 