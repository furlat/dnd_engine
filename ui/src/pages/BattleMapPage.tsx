import * as React from 'react';
import { Box, useTheme } from '@mui/material';
import CharacterSheetPage from './CharacterSheetPage';
import EventQ from '../components/events/EventQ';
import BattleMapCanvas from '../components/battlemap/BattleMapCanvas';

const DEFAULT_MAP_SIZE = {
  width: 30,
  height: 20
};

const BattleMapPage: React.FC = () => {
  const theme = useTheme();
  const [containerSize, setContainerSize] = React.useState({ width: 0, height: 0 });
  const containerRef = React.useRef<HTMLDivElement>(null);

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
      {/* Character Sheet Sidebar */}
      <CharacterSheetPage />

      {/* Main content area */}
      <Box 
        ref={containerRef}
        sx={{ 
          flex: 1,
          display: 'flex',
          position: 'relative',
          overflow: 'hidden',
          bgcolor: '#000000'
        }}
      >
        {containerSize.width > 0 && containerSize.height > 0 && (
          <BattleMapCanvas 
            width={DEFAULT_MAP_SIZE.width}
            height={DEFAULT_MAP_SIZE.height}
            tileSize={32}
          />
        )}
      </Box>

      {/* Event Queue */}
      <EventQ />
    </Box>
  );
};

export default BattleMapPage; 