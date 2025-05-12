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
import { fetchCharacter } from '../api/characterApi';
import { EntityProvider, useEntity } from '../contexts/EntityContext';
import CharacterSheetContent from '../components/character/CharacterSheetContent';
import ActionBar from '../components/character/ActionBar';

// Define the params interface
type RouteParams = {
  characterId?: string;
}

// Content component that uses the EntityContext
const CharacterSheetContentWrapper: React.FC = () => {
  const navigate = useNavigate();
  const { entity: character, loading, error } = useEntity();

  const handleBack = (): void => {
    navigate('/');
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" my={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Button 
          startIcon={<ArrowBackIcon />} 
          onClick={handleBack}
          sx={{ mb: 2 }}
        >
          Back to Characters
        </Button>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (!character) {
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
      
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
            <Typography variant="h4" component="h1" gutterBottom>
              {character.name}
            </Typography>
            {character.description && (
              <Typography variant="body1" color="text.secondary" sx={{ whiteSpace: 'pre-line' }}>
                {character.description}
              </Typography>
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <ActionBar character={character} />
        </Grid>
      </Grid>

      <CharacterSheetContent character={character} />
    </Box>
  );
};

// Wrapper component that provides context
const CharacterSheetPage: React.FC = () => {
  const { characterId } = useParams<{ characterId: string }>();
  
  if (!characterId) {
    return <Alert severity="error">Character ID is required</Alert>;
  }
  
  return (
    <EntityProvider
      entityId={characterId}
      fetchEntity={fetchCharacter}
    >
      <CharacterSheetContentWrapper />
    </EntityProvider>
  );
};

export default CharacterSheetPage; 