import * as React from 'react';
import { Box, Grid, Fade, Typography, CircularProgress } from '@mui/material';
import AbilityScoresBlock from './sections/AbilityScoresBlock';
import ArmorSection from './sections/ArmorSection';
import AttackSection from './sections/AttackSection';
import SavingThrowsSection from './sections/SavingThrowsSection';
import HealthSection from './sections/HealthSection';
import ActionEconomySection from './sections/ActionEconomySection';
import SkillsSection from './sections/SkillsSection';
import ActiveConditionsBar from './sections/ActiveConditionsBar';
import { useSnapshot } from 'valtio';
import { characterSheetStore, characterSheetActions } from '../../store/characterSheetStore';
import { battlemapStore } from '../../store/battlemapStore';

const CharacterSheetContent: React.FC = () => {
  const snap = useSnapshot(characterSheetStore);
  const battlemapSnap = useSnapshot(battlemapStore);
  const selectedEntityId = battlemapSnap.entities.selectedEntityId || battlemapSnap.entities.displayedEntityId;

  // Update character data when selected entity changes
  React.useEffect(() => {
    if (selectedEntityId) {
      characterSheetActions.fetchSelectedCharacter();
    }
  }, [selectedEntityId]);

  // Show loading state
  if (snap.loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show empty state when no entity is selected
  if (!snap.character) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
        <Typography variant="body1">Select an entity to view details</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Active Conditions Bar */}
      <Fade in={true} timeout={150}>
        <div>
          <ActiveConditionsBar />
        </div>
      </Fade>

      {/* Abilities */}
      <Fade in={true} timeout={150}>
        <div>
          <AbilityScoresBlock />
        </div>
      </Fade>

      {/* Saving Throws */}
      <Fade in={true} timeout={150}>
        <div>
          <SavingThrowsSection />
        </div>
      </Fade>

      {/* Health */}
      <Fade in={true} timeout={150}>
        <div>
          <HealthSection />
        </div>
      </Fade>

      {/* Armor */}
      <Fade in={true} timeout={150}>
        <div>
          <ArmorSection />
        </div>
      </Fade>

      {/* Attack */}
      <Fade in={true} timeout={150}>
        <div>
          <AttackSection />
        </div>
      </Fade>

      {/* Action Economy */}
      <Fade in={true} timeout={150}>
        <div>
          <ActionEconomySection />
        </div>
      </Fade>

      {/* Skills */}
      <Fade in={true} timeout={150}>
        <div>
          <SkillsSection />
        </div>
      </Fade>
    </Box>
  );
};

export default CharacterSheetContent; 