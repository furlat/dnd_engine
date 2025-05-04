import * as React from 'react';
import {
  Box,
  Typography,
  Grid,
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
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  SkillSetSnapshot,
  Skill,
  SkillBonusCalculationSnapshot,
} from '../../models/character';

interface Props {
  skillSet: SkillSetSnapshot;
  skillCalculations?: Record<string, SkillBonusCalculationSnapshot>;
}

const formatBonus = (n: number) => `${n}`;

// Helper to render modifier breakdown similar to Ability block
const ModifierBreakdown: React.FC<{ skill: Skill; calc?: SkillBonusCalculationSnapshot }> = ({ skill, calc }): JSX.Element => {
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
                  {ch.name} – Total: {formatBonus(getTotal(ch))}
                </Typography>
                <List dense disablePadding>
                  {ch.value_modifiers.map((mod: any, i: number) => (
                    <ListItem key={i} dense divider={i < ch.value_modifiers.length - 1}>
                      <ListItemText
                        primary={mod.name}
                        secondary={mod.source_entity_name}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                      <Chip label={formatBonus(mod.value)} size="small" color={mod.value >= 0 ? 'success' : 'error'} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            ))}
          </AccordionDetails>
        </Accordion>
      ))}
    </>
  );
};

const SkillsSection: React.FC<Props> = ({ skillSet, skillCalculations }) => {
  const [selected, setSelected] = React.useState<Skill | null>(null);

  // Group skills by ability and keep D&D ability order
  const abilityOrder = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'];
  const grouped = React.useMemo(() => {
    const map: Record<string, Skill[]> = {};
    Object.values(skillSet.skills).forEach((s) => {
      if (!map[s.ability]) map[s.ability] = [];
      map[s.ability].push(s);
    });
    // Ensure consistent ordering
    return abilityOrder
      .filter((a) => map[a]?.length)
      .reduce((acc, ab) => {
        acc[ab] = map[ab];
        return acc;
      }, {} as Record<string, Skill[]>);
  }, [skillSet]);

  // Detail dialog component
  const DetailDialog: React.FC = () => {
    if (!selected) return null;
    const calc = skillCalculations ? skillCalculations[selected.name] : undefined;

    return (
      <Dialog open onClose={() => setSelected(null)} maxWidth="md" fullWidth>
        <DialogTitle>{selected.name.toUpperCase()} Details</DialogTitle>
        <DialogContent dividers>
          {calc ? (
            <Grid container spacing={2}>
              {/* Left column */}
              <Grid item xs={12} md={6}>
                {/* Overview */}
                <Typography variant="h6" gutterBottom>
                  Overview
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">
                        Ability
                      </Typography>
                      <Typography variant="h5">
                        {calc.ability_name.toUpperCase()}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
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
                </Paper>

                {/* Components */}
                <Typography variant="h6" gutterBottom>
                  Component Values
                </Typography>
                <Paper sx={{ p: 2 }} elevation={1}>
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
              </Grid>

              {/* Right column */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Modifier Breakdown
                </Typography>
                <ModifierBreakdown skill={selected} calc={calc} />
              </Grid>

              {/* Debug full width */}
              <Grid item xs={12}>
                <Accordion sx={{ mt: 2 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    Debug JSON
                  </AccordionSummary>
                  <AccordionDetails>
                    <pre style={{ fontSize: 12 }}>
                      {JSON.stringify(selected, null, 2)}
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
          <Button onClick={() => setSelected(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Skills
      </Typography>

      {Object.entries(grouped).map(([ability, list]) => (
        <Box key={ability} sx={{ mb: 3 }}>
          <Typography variant="h6" color="primary" sx={{ mb: 1 }}>
            {ability.toUpperCase()} Skills
          </Typography>
          <Grid container spacing={2}>
            {list.map((skill) => {
              const bonus = (skill as any).bonus ?? (skill as any).effective_bonus ?? 0;
              const proficient = (skill as any).proficient;
              const expertise = (skill as any).expertise;
              return (
                <Grid item xs={12} sm={6} md={4} key={skill.name}>
                  <Paper
                    elevation={2}
                    sx={{
                      p: 2,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                      border: proficient ? 2 : 1,
                      borderColor: expertise ? 'secondary.main' : proficient ? 'primary.main' : 'transparent',
                    }}
                    onClick={() => setSelected(skill)}
                  >
                    <Box>
                      <Typography variant="subtitle1">{skill.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {ability}
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
        </Box>
      ))}

      <DetailDialog />
    </Box>
  );
};

export default SkillsSection; 