import * as React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Box,
  Grid,
  Paper,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { fetchCharacter } from '../api/characterApi';
import { Character } from '../models/character';
import {
  AbilityScoresBlock,
  SkillsSection,
  SavingThrowsSection,
  HealthSection,
  ArmorSection,
  AttackSection,
} from '../components/character';

// Define the params interface
type RouteParams = {
  characterId?: string;
}

const CharacterSheetPage: React.FC = () => {
  // Directly access params with correct typing
  const params = useParams();
  const characterId = params.characterId;
  const navigate = useNavigate();
  const [character, setCharacter] = React.useState<Character | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const loadCharacter = async () => {
      if (!characterId) return;
      
      try {
        setLoading(true);
        const data = await fetchCharacter(characterId);
        setCharacter(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch character:', err);
        setError('Failed to load character. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    loadCharacter();
  }, [characterId]);

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
      
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          {character.name}
        </Typography>
        {character.description && (
          <Typography variant="body1" color="text.secondary" paragraph>
            {character.description}
          </Typography>
        )}
      </Paper>

      {/* Single-page layout */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Abilities */}
        {character.ability_scores && (
          <AbilityScoresBlock abilityScores={character.ability_scores} />
        )}

        {/* Saving Throws */}
        {character.saving_throws && (
          <SavingThrowsSection
            savingThrows={character.saving_throws}
            savingThrowCalculations={(character as any).saving_throw_calculations}
          />
        )}

        {/* Health, Armor & Attack side-by-side */}
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {character.health && <HealthSection health={character.health} />}
              <ArmorSection entity={character} />
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <AttackSection entity={character} />
          </Grid>
        </Grid>

        {/* Skills */}
        {character.skill_set && (
          <SkillsSection
            skillSet={character.skill_set}
            skillCalculations={(character as any).skill_calculations}
          />
        )}
      </Box>
    </Box>
  );
};

export default CharacterSheetPage; 