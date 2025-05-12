import * as React from 'react';
import { Box, Grid, Fade } from '@mui/material';
import AbilityScoresBlock from './AbilityScoresBlock';
import ArmorSection from './ArmorSection';
import AttackSection from './AttackSection';
import SavingThrowsSection from './SavingThrowsSection';
import HealthSection from './HealthSection';
import ActionEconomySection from './ActionEconomySection';
import SkillsSection from './SkillsSection';
import ActiveConditionsBar from './ActiveConditionsBar';

const CharacterSheetContent: React.FC = () => {
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