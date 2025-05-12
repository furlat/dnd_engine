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
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { characterStore, characterActions } from '../store/characterStore';
import { useSnapshot } from 'valtio';
import CharacterSheetContent from '../components/character/CharacterSheetContent';
import ActionBar from '../components/character/ActionBar';

// Define the params interface
type RouteParams = {
  characterId?: string;
}

const CharacterSheetPage: React.FC = () => {
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
      <Button 
        startIcon={<ArrowBackIcon />} 
        onClick={handleBack}
        sx={{ mb: 2 }}
      >
        Back to Characters
      </Button>

      {/* Character Description Box */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          {snap.character.name}
        </Typography>
        {snap.character.description && (
          <Typography variant="body1" color="text.secondary" sx={{ whiteSpace: 'pre-line' }}>
            {snap.character.description}
          </Typography>
        )}
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

export default CharacterSheetPage; 