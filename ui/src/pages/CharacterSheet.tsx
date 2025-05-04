import * as React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Paper,
  Button,
  Grid,
  Drawer
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import { fetchCharacter } from '../api/characterApi';
import { Character } from '../models/character';
import { EntityProvider, useEntity } from '../contexts/EntityContext';
import TabPanel from '../components/common/TabPanel';

// Import character components and modifiers
import {
  AbilityScoresBlock,
  SkillsSection,
  ArmorSection,
  SavingThrowsSection,
  HealthSection,
} from '../components/character';
import { ModifierPanel } from '../components/modifiers';

// Actual character sheet content component
const CharacterSheetContent: React.FC = () => {
  const navigate = useNavigate();
  const [tabValue, setTabValue] = React.useState<number>(0);
  const [selectedValuePath, setSelectedValuePath] = React.useState<string | null>(null);
  
  // Use the entity from context
  const { entity, loading, error } = useEntity();

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleBack = () => {
    navigate('/');
  };

  const handleCloseModifiers = () => {
    setSelectedValuePath(null);
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

  if (!entity) {
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
          {entity.name}
        </Typography>
        {entity.description && (
          <Typography variant="body1" color="text.secondary" paragraph>
            {entity.description}
          </Typography>
        )}
      </Paper>

      <Grid container spacing={2}>
        <Grid item xs={12} md={selectedValuePath ? 8 : 12}>
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
            
            <TabPanel value={tabValue} index={0}>
              <AbilityScoresBlock abilityScores={entity.ability_scores} />
            </TabPanel>
            
            <TabPanel value={tabValue} index={1}>
              <SkillsSection skillSet={entity.skill_set} skillCalculations={entity.skill_calculations} />
            </TabPanel>
            
            <TabPanel value={tabValue} index={2}>
              <SavingThrowsSection 
                savingThrows={entity.saving_throws} 
                savingThrowCalculations={entity.saving_throw_calculations}
              />
            </TabPanel>
            
            <TabPanel value={tabValue} index={3}>
              <HealthSection health={entity.health} />
            </TabPanel>
            
            <TabPanel value={tabValue} index={4}>
              <ArmorSection entity={entity} />
            </TabPanel>
          </Box>
        </Grid>
        
        {selectedValuePath && (
          <Grid item xs={12} md={4}>
            <ModifierPanel 
              valuePath={selectedValuePath} 
              onClose={handleCloseModifiers} 
            />
          </Grid>
        )}
      </Grid>
      
      {/* Mobile drawer for modifier panel */}
      <Drawer
        anchor="bottom"
        open={!!selectedValuePath}
        onClose={handleCloseModifiers}
        sx={{ display: { md: 'none' } }}
      >
        <Box sx={{ p: 2, maxHeight: '80vh' }}>
          <ModifierPanel 
            valuePath={selectedValuePath} 
            onClose={handleCloseModifiers} 
          />
        </Box>
      </Drawer>
    </Box>
  );
};

// Wrapper component that provides context
const CharacterSheet: React.FC = () => {
  const { characterId } = useParams<{ characterId: string }>();
  
  if (!characterId) {
    return <Alert severity="error">Character ID is required</Alert>;
  }
  
  return (
    <EntityProvider
      entityId={characterId}
      fetchEntity={fetchCharacter}
    >
      <CharacterSheetContent />
    </EntityProvider>
  );
};

export default CharacterSheet; 