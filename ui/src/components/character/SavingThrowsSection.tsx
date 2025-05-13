import * as React from 'react';
import {
  Box,
  Grid,
  Typography,
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
import type {
  ReadonlySavingThrowSnapshot,
  ReadonlySavingThrowBonusCalculation,
  ReadonlyModifierChannel
} from '../../models/readonly';
import { AdvantageStatus, CriticalStatus, AutoHitStatus } from '../../models/character';
import { useSavingThrows } from '../../hooks/character/useSavingThrows';

// Helper to render modifier breakdown list
const ModifierBreakdown: React.FC<{ 
  savingThrow: ReadonlySavingThrowSnapshot; 
  calc?: ReadonlySavingThrowBonusCalculation 
}> = ({ savingThrow, calc }) => {
  // Helper to grab channels safely
  const extractChannels = (mv: any) => (mv && mv.channels ? mv.channels : []);

  const sections: { label: string; channels: ReadonlyModifierChannel[] }[] = [];

  // 1. Proficiency Bonus
  if (calc) {
    sections.push({ label: 'Proficiency Bonus', channels: extractChannels(calc.normalized_proficiency_bonus) });
    sections.push({ label: 'Ability Bonus', channels: extractChannels(calc.ability_bonus) });
    sections.push({ label: 'Ability Modifier Bonus', channels: extractChannels(calc.ability_modifier_bonus) });
  }

  // 2. Saving Throw Bonus itself (specific modifiers)
  const stBonusCh = extractChannels((savingThrow as any).bonus);
  sections.push({ label: 'Saving Throw Bonus', channels: stBonusCh });

  // Filter out empty groups
  const activeSections = sections.filter((s) => s.channels.length > 0);

  if (activeSections.length === 0) {
    return (
      <Paper elevation={1} sx={{ p: 2 }}>
        <Typography variant="body2">No detailed modifier breakdown available.</Typography>
      </Paper>
    );
  }

  const getTotal = (ch: ReadonlyModifierChannel) => ch.value_modifiers.reduce((s, m) => s + m.value, 0);

  return (
    <>
      {activeSections.map((section, sIdx) => (
        <Accordion key={sIdx} defaultExpanded sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1">{section.label}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            {section.channels.map((ch, idx) => (
              <Box key={idx} sx={{ mb: 2 }}>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {ch.name} – Total: {formatBonus(getTotal(ch))}
                </Typography>
                <List dense disablePadding>
                  {ch.value_modifiers.map((mod, i) => (
                    <ListItem key={i} dense divider={i < ch.value_modifiers.length - 1}>
                      <ListItemText
                        primary={mod.name}
                        secondary={mod.source_entity_name}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                      <Chip
                        label={formatBonus(mod.value)}
                        size="small"
                        color={mod.value >= 0 ? 'success' : 'error'}
                      />
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

const formatBonus = (n: number) => `${n}`;

const DetailDialog: React.FC<{
  savingThrow: ReadonlySavingThrowSnapshot | null;
  calc?: ReadonlySavingThrowBonusCalculation;
  onClose: () => void;
  open: boolean;
}> = ({ savingThrow, calc, onClose, open }) => {
  if (!savingThrow) return null;

    // Get status from total_bonus if available
    const advantage = calc?.total_bonus?.advantage ?? AdvantageStatus.NONE;
    const critical = calc?.total_bonus?.critical ?? CriticalStatus.NONE;
    const autoHit = calc?.total_bonus?.auto_hit ?? AutoHitStatus.NONE;

    return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{`${savingThrow.ability.toUpperCase()} Saving Throw Details`}</DialogTitle>
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
                    <Typography variant="h5">{savingThrow.ability.toUpperCase()}</Typography>
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

                {/* Components */}
                <Typography variant="h6" gutterBottom>
                  Component Values
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                  {[
                    { label: 'Proficiency Bonus', value: calc.normalized_proficiency_bonus.normalized_score },
                    { label: 'Saving Throw Bonus', value: calc.saving_throw_bonus.normalized_score },
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
                      {critical === CriticalStatus.AUTOCRIT ? 'Save automatically results in a critical success' :
                       critical === CriticalStatus.NOCRIT ? 'Save can never be a critical success' :
                       'Normal critical rules apply'}
                    </Typography>
                  )}
                  {autoHit !== AutoHitStatus.NONE && (
                    <Typography variant="body1">
                      {autoHit === AutoHitStatus.AUTOHIT ? 'Save automatically succeeds' :
                       autoHit === AutoHitStatus.AUTOMISS ? 'Save automatically fails' :
                       'Normal success rules apply'}
                    </Typography>
                  )}
                </Paper>
              </Grid>

              {/* Right column */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Modifier Breakdown
                </Typography>
              <ModifierBreakdown savingThrow={savingThrow} calc={calc} />
              </Grid>

              {/* Debug */}
              <Grid item xs={12}>
                <Accordion sx={{ mt: 2 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>Debug JSON</AccordionSummary>
                  <AccordionDetails>
                  <pre style={{ fontSize: 12 }}>{JSON.stringify(savingThrow, null, 2)}</pre>
                    {calc && (
                      <>
                        <Divider sx={{ my: 1 }} />
                        <pre style={{ fontSize: 12 }}>{JSON.stringify(calc, null, 2)}</pre>
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
        <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  };

const SavingThrowsSection: React.FC = () => {
  const {
    savingThrows,
    calculations,
    selectedSavingThrow,
    dialogOpen,
    handleSavingThrowClick,
    handleCloseDialog
  } = useSavingThrows();

  // Move useMemo outside the conditional and handle null case inside
  const ordered = React.useMemo(() => {
    if (!savingThrows) return [];
    
    const order = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'];
    return order
      .map((ability) => savingThrows.saving_throws[ability])
      .filter(Boolean) as ReadonlySavingThrowSnapshot[];
  }, [savingThrows]);

  if (!savingThrows) return null;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Saving Throws
      </Typography>
      <Grid container spacing={2}>
        {ordered.map((st) => {
          const bonus = st.effective_bonus ?? st.bonus?.normalized_score ?? 0;
          return (
            <Grid item xs={6} sm={4} md={2} key={st.name}>
              <Paper
                elevation={3}
                sx={{
                  textAlign: 'center',
                  p: 1.5,
                  cursor: 'pointer',
                  minHeight: 90,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: 0.5,
                  border: st.proficiency ? 2 : 1,
                  borderColor: st.proficiency ? 'primary.main' : 'transparent',
                }}
                onClick={() => handleSavingThrowClick(st)}
              >
                <Typography variant="subtitle1">{st.ability.toUpperCase()}</Typography>
                <Typography variant="h5" color={bonus >= 0 ? 'success.main' : 'error.main'}>
                  {formatBonus(bonus)}
                </Typography>
              </Paper>
            </Grid>
          );
        })}
      </Grid>
      <DetailDialog 
        savingThrow={selectedSavingThrow}
        calc={selectedSavingThrow ? calculations?.[selectedSavingThrow.ability] : undefined}
        open={dialogOpen}
        onClose={handleCloseDialog}
      />
    </Box>
  );
};

export default React.memo(SavingThrowsSection); 