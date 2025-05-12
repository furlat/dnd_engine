/// <reference types="react" />
import * as React from 'react';
import type { ReactElement } from 'react';
import {
  Box,
  Typography,
  GridLegacy as Grid,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Divider,
  List,
  ListItem,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { AdvantageStatus, CriticalStatus, AutoHitStatus } from '../../models/character';
import { useSkills } from '../../hooks/character/useSkills';
import type { ReadonlySkill } from '../../models/readonly';

const formatBonus = (n: number) => `${n}`;

// Helper to render modifier breakdown similar to Ability block
const ModifierBreakdown: React.FC<{ 
  skill: ReadonlySkill; 
  calc?: any;
  showAdvantage?: boolean;
}> = ({ skill, calc, showAdvantage = false }): ReactElement => {
  // Gather sections
  const extractChannels = (mv: any) => (mv && mv.channels ? mv.channels : []);
  const sections: { label: string; channels: any[] }[] = [];

  // Proficiency Bonus
  if (calc) sections.push({ label: 'Proficiency Bonus', channels: extractChannels(calc.normalized_proficiency_bonus) });
  // Ability Bonus
  if (calc) sections.push({ label: 'Ability Bonus', channels: extractChannels(calc.ability_bonus) });
  // Ability Modifier Bonus
  if (calc) sections.push({ label: 'Ability Modifier Bonus', channels: extractChannels(calc.ability_modifier_bonus) });

  // Skill Bonus
  const skillBonusMV = (skill as any).skill_bonus as any | undefined;
  sections.push({ label: 'Skill Bonus', channels: extractChannels(skillBonusMV) });

  const activeSections = sections.filter((s) => s.channels.length > 0);
  if (activeSections.length === 0) {
    return (
      <Paper elevation={1} sx={{ p: 2 }}>
        <Typography variant="body2">No detailed modifier breakdown available.</Typography>
      </Paper>
    );
  }

  const getTotal = (ch: any) => ch.value_modifiers.reduce((s: number, m: any) => s + m.value, 0);

  return (
    <>
      {activeSections.map((section, sIdx) => (
        <Accordion key={sIdx} defaultExpanded sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1">{section.label}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            {section.channels.map((ch: any, idx: number) => (
              <Box key={idx} sx={{ mb: 2 }}>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {ch.name} – Total: {showAdvantage ? ch.advantage_status : formatBonus(getTotal(ch))}
                </Typography>
                <List dense disablePadding>
                  {(showAdvantage ? ch.advantage_modifiers : ch.value_modifiers).map((mod: any, i: number) => (
                    <ListItem key={i} dense divider={i < (showAdvantage ? ch.advantage_modifiers.length : ch.value_modifiers.length) - 1}>
                      <ListItemText
                        primary={mod.name}
                        secondary={mod.source_entity_name}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                      <Chip 
                        label={showAdvantage ? mod.value : formatBonus(mod.value)} 
                        size="small" 
                        color={showAdvantage 
                          ? (mod.value === AdvantageStatus.ADVANTAGE ? 'success' : 
                             mod.value === AdvantageStatus.DISADVANTAGE ? 'error' : 'default')
                          : (mod.value >= 0 ? 'success' : 'error')} 
                      />
                    </ListItem>
                  ))}
                  {showAdvantage && ch.advantage_modifiers.length === 0 && (
                    <Typography variant="body2" color="text.secondary">
                      No advantage modifiers
                    </Typography>
                  )}
                </List>
              </Box>
            ))}
          </AccordionDetails>
        </Accordion>
      ))}
    </>
  );
};

interface DetailDialogProps {
  calc?: any;
}

const DetailDialog: React.FC<DetailDialogProps> = ({ calc }) => {
  const [detailMode, setDetailMode] = React.useState<'values' | 'advantage'>('values');
  const { selectedSkill, handleSelectSkill } = useSkills();
  
  if (!selectedSkill) return null;

  const advantage = calc?.total_bonus?.advantage ?? AdvantageStatus.NONE;
  const critical = calc?.total_bonus?.critical ?? CriticalStatus.NONE;
  const autoHit = calc?.total_bonus?.auto_hit ?? AutoHitStatus.NONE;

  return (
    <Dialog open onClose={() => handleSelectSkill(null)} maxWidth="md" fullWidth>
      <DialogTitle>{selectedSkill.name.toUpperCase()} Details</DialogTitle>
      <DialogContent dividers>
        {calc ? (
          <Grid container spacing={2}>
            {/* Left column */}
            <Grid item xs={12} md={6} component="div">
              {/* Overview */}
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                <Grid container spacing={2}>
                  <Grid item xs={6} component="div">
                    <Typography variant="body2" color="text.secondary">
                      Ability
                    </Typography>
                    <Typography variant="h5">
                      {calc.ability_name.toUpperCase()}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} component="div">
                    <Typography variant="body2" color="text.secondary">
                      Final Modifier
                    </Typography>
                    <Typography
                      variant="h4"
                      color={calc.final_modifier >= 0 ? 'success.main' : 'error.main'}
                    >
                      {formatBonus(calc.final_modifier)}
                    </Typography>
                  </Grid>
                </Grid>

                {/* Status Chips */}
                <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {autoHit === AutoHitStatus.AUTOHIT && (
                    <Chip size="small" label="Auto Success" color="info" />
                  )}
                  {autoHit === AutoHitStatus.AUTOMISS && (
                    <Chip size="small" label="Auto Fail" color="error" />
                  )}
                  {critical === CriticalStatus.AUTOCRIT && (
                    <Chip size="small" label="Always Crit" color="warning" />
                  )}
                  {critical === CriticalStatus.NOCRIT && (
                    <Chip size="small" label="Never Crit" color="error" />
                  )}
                  <Chip 
                    size="small" 
                    label={advantage === AdvantageStatus.ADVANTAGE ? 'Advantage' :
                           advantage === AdvantageStatus.DISADVANTAGE ? 'Disadvantage' : 'Normal'}
                    color={advantage === AdvantageStatus.ADVANTAGE ? 'success' :
                           advantage === AdvantageStatus.DISADVANTAGE ? 'error' : 'default'}
                  />
                </Box>
              </Paper>

              {/* Component Values */}
              <Typography variant="h6" gutterBottom>
                Component Values
              </Typography>
              <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                {[
                  { label: 'Proficiency Bonus', value: calc.normalized_proficiency_bonus.normalized_score },
                  { label: 'Skill Bonus', value: calc.skill_bonus.normalized_score },
                  { label: 'Ability Bonus', value: calc.ability_bonus.normalized_score },
                  { label: 'Ability Modifier Bonus', value: calc.ability_modifier_bonus.normalized_score },
                ].map((row, idx, arr) => (
                  <React.Fragment key={row.label}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">
                        {row.label}
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {formatBonus(row.value)}
                      </Typography>
                    </Box>
                    {idx < arr.length - 1 && <Divider sx={{ my: 1 }} />}
                  </React.Fragment>
                ))}
              </Paper>

              {/* Status Details */}
              <Typography variant="h6" gutterBottom>
                Status Effects
              </Typography>
              <Paper sx={{ p: 2 }} elevation={1}>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {advantage === AdvantageStatus.ADVANTAGE ? 'Roll twice and take the higher result' :
                   advantage === AdvantageStatus.DISADVANTAGE ? 'Roll twice and take the lower result' :
                   'Roll normally'}
                </Typography>
                {critical !== CriticalStatus.NONE && (
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {critical === CriticalStatus.AUTOCRIT ? 'Check automatically results in a critical success' :
                     critical === CriticalStatus.NOCRIT ? 'Check can never be a critical success' :
                     'Normal critical rules apply'}
                  </Typography>
                )}
                {autoHit !== AutoHitStatus.NONE && (
                  <Typography variant="body1">
                    {autoHit === AutoHitStatus.AUTOHIT ? 'Check automatically succeeds' :
                     autoHit === AutoHitStatus.AUTOMISS ? 'Check automatically fails' :
                     'Normal success rules apply'}
                  </Typography>
                )}
              </Paper>
            </Grid>

            {/* Right column */}
            <Grid item xs={12} md={6} component="div">
              <Typography variant="h6" gutterBottom>
                Modifier Breakdown
              </Typography>
              <ModifierBreakdown skill={selectedSkill} calc={calc} showAdvantage={detailMode === 'advantage'} />
            </Grid>

            {/* Debug full width */}
            <Grid item xs={12} component="div">
              <Accordion sx={{ mt: 2 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  Debug JSON
                </AccordionSummary>
                <AccordionDetails>
                  <pre style={{ fontSize: 12 }}>
                    {JSON.stringify(selectedSkill, null, 2)}
                  </pre>
                  {calc && (
                    <>
                      <Divider sx={{ my: 1 }} />
                      <pre style={{ fontSize: 12 }}>
                        {JSON.stringify(calc, null, 2)}
                      </pre>
                    </>
                  )}
                </AccordionDetails>
              </Accordion>
            </Grid>
          </Grid>
        ) : (
          <Typography variant="body2">No calculation snapshot available.</Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button 
          onClick={() => setDetailMode(detailMode === 'values' ? 'advantage' : 'values')}
          color="primary"
        >
          Show {detailMode === 'values' ? 'Advantage' : 'Values'} Details
        </Button>
        <Button onClick={() => handleSelectSkill(null)}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

const SkillsSection: React.FC = () => {
  const { 
    calculations,
    selectedSkill,
    handleSelectSkill,
    getOrderedSkills,
    getSkillBonus,
    isSkillProficient,
    hasSkillExpertise
  } = useSkills();

  const orderedSkills = React.useMemo(() => getOrderedSkills(), [getOrderedSkills]);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Skills
      </Typography>

      <Grid container spacing={2}>
        {orderedSkills.map((skill) => {
          const bonus = getSkillBonus(skill);
          const proficient = isSkillProficient(skill);
          const expertise = hasSkillExpertise(skill);
          return (
            <Grid item xs={6} sm={4} md={3} key={skill.name} component="div">
              <Paper
                elevation={2}
                sx={{
                  p: 1.5,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  border: proficient ? 2 : 1,
                  borderColor: expertise ? 'secondary.main' : proficient ? 'primary.main' : 'transparent',
                }}
                onClick={() => handleSelectSkill(skill)}
              >
                <Box>
                  <Typography variant="subtitle1">{skill.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {skill.ability}
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center">
                  <Typography variant="h6" color={bonus >= 0 ? 'success.main' : 'error.main'}>
                    {formatBonus(bonus)}
                  </Typography>
                </Box>
              </Paper>
            </Grid>
          );
        })}
      </Grid>

      <DetailDialog calc={selectedSkill ? calculations?.[selectedSkill.name] : undefined} />
    </Box>
  );
};

export default SkillsSection; 