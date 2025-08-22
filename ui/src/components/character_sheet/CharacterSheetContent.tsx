import * as React from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
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
  const [initialLoadDone, setInitialLoadDone] = React.useState(false);
  
  // Track if initial load has occurred to avoid showing loading indicator repeatedly
  React.useEffect(() => {
    if (snap.character && !initialLoadDone) {
      setInitialLoadDone(true);
    }
  }, [snap.character, initialLoadDone]);

  // Update character data when selected entity changes
  React.useEffect(() => {
    if (selectedEntityId) {
      characterSheetActions.fetchSelectedCharacter();
    }
  }, [selectedEntityId]);

  // Show loading state for initial load only
  if (snap.loading && !initialLoadDone) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
        <CircularProgress size={24} sx={{ color: 'text.secondary' }} />
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
      <ActiveConditionsBar />

      {/* Abilities */}
      <AbilityScoresBlock />

      {/* Saving Throws */}
      <SavingThrowsSection />

      {/* Health */}
      <HealthSection />

      {/* Armor */}
      <ArmorSection />

      {/* Attack */}
      <AttackSection />

      {/* Action Economy */}
      <ActionEconomySection />

      {/* Skills */}
      <SkillsSection />
    </Box>
  );
};

export default React.memo(CharacterSheetContent); 