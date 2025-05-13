import * as React from 'react';
import { Box, useTheme } from '@mui/material';
import CharacterSheetPage from './CharacterSheetPage';
import EventQ from '../components/events/EventQ';
import BattleMapCanvas from '../components/battlemap/BattleMapCanvas';
import TileEditor, { useTileEditor } from '../components/battlemap/TileEditor';
import { fetchGridSnapshot, TileSummary } from '../api/tileApi';

const BattleMapPage: React.FC = () => {
  const theme = useTheme();
  const [containerSize, setContainerSize] = React.useState({ width: 0, height: 0 });
  const [gridSize, setGridSize] = React.useState({ width: 30, height: 20 }); // Default size
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [isLocked, setIsLocked] = React.useState(false);
  const { handleCellClick, TileEditor, isEditing } = useTileEditor();

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
    const fetchGridDimensions = async () => {
      try {
        const grid = await fetchGridSnapshot();
        setGridSize({ width: grid.width, height: grid.height });
      } catch (error) {
        console.error('Error fetching grid dimensions:', error);
      }
    };

    fetchGridDimensions();
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
        {/* Tile Editor */}
        <TileEditor isLocked={isLocked} />

        {containerSize.width > 0 && containerSize.height > 0 && (
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
          />
        )}
      </Box>

      {/* Event Queue */}
      <EventQ />
    </Box>
  );
};

export default BattleMapPage; 