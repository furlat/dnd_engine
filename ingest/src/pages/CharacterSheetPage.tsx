import * as React from 'react';
import {
  Typography,
  Box,
  Paper,
  IconButton,
  Tooltip,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { battlemapStore } from '../store/battlemapStore';
import { useSnapshot } from 'valtio';
import CharacterSheetContent from '../components/character_sheet/CharacterSheetContent';

interface CharacterSheetPageProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

const SIDEBAR_WIDTH = '922px';
const COLLAPSED_WIDTH = '40px';

const CharacterSheetPage: React.FC<CharacterSheetPageProps> = ({
  isCollapsed,
  onToggleCollapse
}) => {
  const snap = useSnapshot(battlemapStore);
  const selectedEntity = snap.entities.selectedEntityId 
    ? snap.entities.summaries[snap.entities.selectedEntityId] 
    : snap.entities.displayedEntityId 
      ? snap.entities.summaries[snap.entities.displayedEntityId] 
      : undefined;
      
  // Memoize content to prevent unnecessary rendering when collapsed
  const sheetContent = React.useMemo(() => {
    if (isCollapsed) return null;
    
    return (
      <>
        {/* Header */}
        <Paper sx={{ p: 2, mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h4" component="h1">
            {selectedEntity?.name || 'Character Sheet'}
          </Typography>
        </Paper>

        {/* Character Sheet Content */}
        <Paper sx={{ p: 3 }}>
          <CharacterSheetContent />
        </Paper>
      </>
    );
  }, [isCollapsed, selectedEntity?.name]);

  return (
      <Box
        sx={{
          position: 'fixed',
          top: 64,
          left: 0,
          height: 'calc(100vh - 64px)',
          width: isCollapsed ? COLLAPSED_WIDTH : SIDEBAR_WIDTH,
          transition: 'width 0.3s ease-in-out',
          display: 'flex',
          zIndex: 1200,
        }}
      >
        <Paper
          sx={{
            width: SIDEBAR_WIDTH,
            height: '100%',
            overflowY: 'auto',
            transform: isCollapsed ? `translateX(-${SIDEBAR_WIDTH})` : 'none',
            transition: 'transform 0.3s ease-in-out',
            borderRight: 1,
            borderColor: 'divider',
            borderRadius: 0,
            p: 2,
            '&::-webkit-scrollbar': {
              width: '8px',
            },
            '&::-webkit-scrollbar-track': {
              backgroundColor: 'background.paper',
            },
            '&::-webkit-scrollbar-thumb': {
              backgroundColor: 'grey.400',
              borderRadius: '4px',
            },
          }}
        >
          {sheetContent}
        </Paper>

        {/* Toggle button */}
        <Paper
          sx={{
            position: 'absolute',
            right: isCollapsed ? 0 : -40,
            top: '50%',
            transform: 'translateY(-50%)',
            width: COLLAPSED_WIDTH,
            height: '80px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            borderTopRightRadius: '8px',
            borderBottomRightRadius: '8px',
            borderTopLeftRadius: '0',
            borderBottomLeftRadius: '0',
            zIndex: 1,
            boxShadow: 2,
            transition: 'right 0.3s ease-in-out'
          }}
          onClick={onToggleCollapse}
        >
          <IconButton>
            {isCollapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </IconButton>
        </Paper>
      </Box>
  );
};

export default CharacterSheetPage; 