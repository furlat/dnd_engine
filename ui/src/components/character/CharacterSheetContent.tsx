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

      {/* Health, Armor & Attack side-by-side */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <Fade in={true} timeout={150}>
              <div>
                <HealthSection />
              </div>
            </Fade>
            <Fade in={true} timeout={150}>
              <div>
                <ArmorSection />
              </div>
            </Fade>
          </Box>
        </Grid>
        <Grid item xs={12} md={6}>
          <Fade in={true} timeout={150}>
            <div>
              <AttackSection />
            </div>
          </Fade>
        </Grid>
      </Grid>

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