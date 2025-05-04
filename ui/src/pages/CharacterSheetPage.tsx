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
  Tabs,
  Tab
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
} from '../components/character';
import TabPanel from '../components/common/TabPanel';

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
  const [tabValue, setTabValue] = React.useState<number>(0);

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

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number): void => {
    setTabValue(newValue);
  };

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

      <Box sx={{ width: '100%' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={tabValue} 
            onChange={handleTabChange} 
            aria-label="character sheet tabs"
          >
            <Tab label="Abilities" id="tab-0" aria-controls="tabpanel-0" />
            <Tab label="Skills" id="tab-1" aria-controls="tabpanel-1" />
            <Tab label="Saving Throws" id="tab-2" aria-controls="tabpanel-2" />
            <Tab label="Health" id="tab-3" aria-controls="tabpanel-3" />
            <Tab label="Armor" id="tab-4" aria-controls="tabpanel-4" />
          </Tabs>
        </Box>
        
        {/* Abilities Tab */}
        <TabPanel value={tabValue} index={0}>
          {character.ability_scores && (
            <AbilityScoresBlock abilityScores={character.ability_scores} />
          )}
        </TabPanel>
        
        {/* Skills Tab */}
        <TabPanel value={tabValue} index={1}>
          {character.skill_set && (
            <SkillsSection skillSet={character.skill_set} skillCalculations={(character as any).skill_calculations} />
          )}
        </TabPanel>
        
        {/* Saving Throws Tab */}
        <TabPanel value={tabValue} index={2}>
          {character.saving_throws && (
            <SavingThrowsSection savingThrows={character.saving_throws} savingThrowCalculations={(character as any).saving_throw_calculations} />
          )}
        </TabPanel>
        
        {/* Health Tab */}
        <TabPanel value={tabValue} index={3}>
          {character.health && <HealthSection health={character.health} />}
        </TabPanel>

        {/* Armor Tab */}
        <TabPanel value={tabValue} index={4}>
          <ArmorSection entity={character} />
        </TabPanel>
      </Box>
    </Box>
  );
};

export default CharacterSheetPage; 