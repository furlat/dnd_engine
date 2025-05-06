import * as React from 'react';
import {
  Box,
  Grid,
} from '@mui/material';
import { Character } from '../../models/character';
import {
  AbilityScoresBlock,
  SkillsSection,
  SavingThrowsSection,
  HealthSection,
  ArmorSection,
  AttackSection,
  ActionEconomySection,
} from './';
import ActiveConditionsBar from './ActiveConditionsBar';

interface CharacterSheetContentProps {
  character: Character;
}

const CharacterSheetContent: React.FC<CharacterSheetContentProps> = ({ character }) => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Active Conditions Bar */}
      <ActiveConditionsBar entity={character} />

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

      {/* Action Economy */}
      <ActionEconomySection actionEconomy={character.action_economy} />

      {/* Skills */}
      {character.skill_set && (
        <SkillsSection
          skillSet={character.skill_set}
          skillCalculations={(character as any).skill_calculations}
        />
      )}
    </Box>
  );
};

export default CharacterSheetContent; 