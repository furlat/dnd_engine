import * as React from 'react';
import {
  Box,
  Grid,
  Fade,
} from '@mui/material';
import { Character } from '../../models/character';
import AbilityScoresBlock from './AbilityScoresBlock';
import SkillsSection from './SkillsSection';
import SavingThrowsSection from './SavingThrowsSection';
import HealthSection from './HealthSection';
import ArmorSection from './ArmorSection';
import AttackSection from './AttackSection';
import ActionEconomySection from './ActionEconomySection';
import ActiveConditionsBar from './ActiveConditionsBar';
import { useCharacterChanges } from '../../utils/characterDiff';

interface CharacterSheetContentProps {
  character: Character;
}

// Memoized section components
const MemoizedAbilityScores = React.memo(AbilityScoresBlock);
const MemoizedSkills = React.memo(SkillsSection);
const MemoizedSavingThrows = React.memo(SavingThrowsSection);
const MemoizedHealth = React.memo(HealthSection);
const MemoizedArmor = React.memo(ArmorSection);
const MemoizedAttack = React.memo(AttackSection);
const MemoizedActionEconomy = React.memo(ActionEconomySection);
const MemoizedConditionsBar = React.memo(ActiveConditionsBar);

const CharacterSheetContent = React.memo<CharacterSheetContentProps>(({ character }) => {
  // Track which sections have changed
  const changes = useCharacterChanges(character);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Active Conditions Bar */}
      <Fade in={true} timeout={150}>
        <div>
          <MemoizedConditionsBar entity={character} />
        </div>
      </Fade>

      {/* Abilities */}
      {character.ability_scores && (
        <Fade in={true} timeout={150}>
          <div>
            <MemoizedAbilityScores 
              key={changes.abilityScores ? 'changed' : 'unchanged'}
              abilityScores={character.ability_scores} 
            />
          </div>
        </Fade>
      )}

      {/* Saving Throws */}
      {character.saving_throws && (
        <Fade in={true} timeout={150}>
          <div>
            <MemoizedSavingThrows
              key={changes.savingThrows ? 'changed' : 'unchanged'}
              savingThrows={character.saving_throws}
              savingThrowCalculations={character.saving_throw_calculations}
            />
          </div>
        </Fade>
      )}

      {/* Health, Armor & Attack side-by-side */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {character.health && (
              <Fade in={true} timeout={150}>
                <div>
                  <MemoizedHealth 
                    key={changes.health ? 'changed' : 'unchanged'}
                    health={character.health} 
                  />
                </div>
              </Fade>
            )}
            <Fade in={true} timeout={150}>
              <div>
                <MemoizedArmor 
                  key={changes.equipment ? 'changed' : 'unchanged'}
                  entity={character} 
                />
              </div>
            </Fade>
          </Box>
        </Grid>
        <Grid item xs={12} md={6}>
          <Fade in={true} timeout={150}>
            <div>
              <MemoizedAttack 
                key={changes.equipment ? 'changed' : 'unchanged'}
                entity={character} 
              />
            </div>
          </Fade>
        </Grid>
      </Grid>

      {/* Action Economy */}
      <Fade in={true} timeout={150}>
        <div>
          <MemoizedActionEconomy 
            key={changes.actionEconomy ? 'changed' : 'unchanged'}
            actionEconomy={character.action_economy} 
          />
        </div>
      </Fade>

      {/* Skills */}
      {character.skill_set && (
        <Fade in={true} timeout={150}>
          <div>
            <MemoizedSkills
              key={changes.skills ? 'changed' : 'unchanged'}
              skillSet={character.skill_set}
              skillCalculations={character.skill_calculations}
            />
          </div>
        </Fade>
      )}
    </Box>
  );
});

CharacterSheetContent.displayName = 'CharacterSheetContent';

export default CharacterSheetContent; 