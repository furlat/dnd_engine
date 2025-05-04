import * as React from 'react';
import { Box, Typography, Grid, Paper, Chip } from '@mui/material';
import { Character, Skill, SkillSetSnapshot } from '../../models/character';
import { SectionProps } from '../common';
import { useEntity } from '../../contexts/EntityContext';

const SkillsSection: React.FC = () => {
  const { entity } = useEntity();
  
  if (!entity || !entity.skill_set) {
    return (
      <Box>
        <Typography variant="h6">Skills data not available</Typography>
      </Box>
    );
  }

  const { skills } = entity.skill_set;
  
  // Group skills by ability
  const skillsByAbility: Record<string, Skill[]> = {};
  
  Object.values(skills).forEach((skill: Skill) => {
    if (!skillsByAbility[skill.ability]) {
      skillsByAbility[skill.ability] = [];
    }
    skillsByAbility[skill.ability].push(skill);
  });

  // Format bonus with + sign for positive values
  const formatBonus = (bonus: number) => {
    return bonus >= 0 ? `+${bonus}` : `${bonus}`;
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Skills
      </Typography>

      {Object.entries(skillsByAbility).map(([ability, abilitySkills]) => (
        <Box key={ability} sx={{ mb: 3 }}>
          <Typography variant="h6" color="primary" sx={{ mb: 1 }}>
            {ability} Skills
          </Typography>
          
          <Grid container spacing={2}>
            {abilitySkills.map((skill) => (
              <Grid item xs={12} sm={6} md={4} key={skill.name}>
                <Paper 
                  elevation={2} 
                  sx={{ 
                    p: 2,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    bgcolor: skill.proficient ? 'rgba(25, 118, 210, 0.08)' : 'inherit'
                  }}
                >
                  <Box>
                    <Typography variant="subtitle1">
                      {skill.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {ability}
                    </Typography>
                  </Box>
                  
                  <Box display="flex" alignItems="center">
                    <Typography variant="h6" color={skill.bonus >= 0 ? 'success.main' : 'error.main'}>
                      {formatBonus(skill.bonus)}
                    </Typography>
                    {skill.proficient && (
                      <Chip 
                        label="Prof" 
                        size="small" 
                        color="primary" 
                        sx={{ ml: 1 }}
                      />
                    )}
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Box>
      ))}
    </Box>
  );
};

export default SkillsSection; 