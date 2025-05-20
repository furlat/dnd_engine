import * as React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Box,
  Paper,
  CircularProgress,
  Alert,
  Button,
  Grid,
  Slide,
  IconButton,
  Tooltip,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import GroupIcon from '@mui/icons-material/Group';
import { characterStore, characterActions } from '../store/characterStore';
import { useSnapshot } from 'valtio';
import CharacterSheetContent from '../components/character_sheet/CharacterSheetContent';
import ActionBar from '../components/character_sheet/ActionBar';

// Define the params interface
type RouteParams = {
  characterId?: string;
}

interface CharacterSheetPageProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onSwitchToEntities: () => void;
}

const SIDEBAR_WIDTH = '922px';
const COLLAPSED_WIDTH = '40px';

const CharacterSheetPage: React.FC<CharacterSheetPageProps> = ({
  isCollapsed,
  onToggleCollapse,
  onSwitchToEntities
}) => {
  const { characterId } = useParams<RouteParams>();
  const navigate = useNavigate();
  const snap = useSnapshot(characterStore);

  // Load character data on mount
  React.useEffect(() => {
    if (characterId) {
      characterActions.fetchCharacter(characterId);
    }
  }, [characterId]);

  const handleBack = (): void => {
    navigate('/');
  };

  const renderContent = () => {
    if (snap.loading) {
      return (
        <Box display="flex" justifyContent="center" my={4}>
          <CircularProgress />
        </Box>
      );
    }

    if (snap.error) {
      return (
        <Box>
          <Button 
            startIcon={<ArrowBackIcon />} 
            onClick={handleBack}
            sx={{ mb: 2 }}
          >
            Back to Characters
          </Button>
          <Alert severity="error">{snap.error}</Alert>
        </Box>
      );
    }

    if (!snap.character) {
      return (
        <Box>
          <Button 
            startIcon={<ArrowBackIcon />} 
            onClick={handleBack}
            sx={{ mb: 2 }}
          >
            Back to Characters
          </Button>
          <Alert severity="warning">Character not found</Alert>
        </Box>
      );
    }

    return (
      <Box>
        {/* Header with switch button */}
        <Paper sx={{ p: 2, mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h4" component="h1">
            {snap.character.name}
          </Typography>
          <Tooltip title="Switch to Entity List">
            <IconButton onClick={onSwitchToEntities}>
              <GroupIcon />
            </IconButton>
          </Tooltip>
        </Paper>

        {/* Action Bar - Full Width */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <ActionBar />
        </Paper>

        {/* Character Sheet Content */}
        <Paper sx={{ p: 3 }}>
          <CharacterSheetContent />
        </Paper>
      </Box>
    );
  };

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
          {renderContent()}
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