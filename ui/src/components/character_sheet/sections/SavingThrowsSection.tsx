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
import { 
  SavingThrowSnapshot, 
  SavingThrowBonusCalculationSnapshot,
  ModifiableValueSnapshot,
  AdvantageStatus,
  CriticalStatus,
  AutoHitStatus
} from '../../../types/characterSheet_types';
import { useSavingThrows } from '../../../hooks/character_sheet/useSavingThrows';

interface ModifierDisplay {
  name: string;
  value: number;
  source_entity_name?: string;
}

// Helper to render modifier breakdown list
const ModifierBreakdown: React.FC<{ 
  savingThrow: SavingThrowSnapshot; 
  calc?: SavingThrowBonusCalculationSnapshot 
}> = ({ savingThrow, calc }) => {
  // Helper to get modifiers safely
  const extractModifiers = (mv: ModifiableValueSnapshot | undefined) => 
    (mv && mv.modifiers ? mv.modifiers : []);
  
  const sections: { label: string; modifiers: ModifierDisplay[] }[] = [];
  
  // 1. Proficiency Bonus
  if (calc) {
    sections.push({ 
      label: 'Proficiency Bonus', 
      modifiers: extractModifiers(calc.normalized_proficiency_bonus).map(m => ({
        name: m.name,
        value: m.value,
        source_entity_name: m.source_entity_name
      }))
    });
    
    sections.push({ 
      label: 'Ability Bonus', 
      modifiers: extractModifiers(calc.ability_bonus).map(m => ({
        name: m.name,
        value: m.value,
        source_entity_name: m.source_entity_name
      }))
    });
    
    sections.push({ 
      label: 'Ability Modifier Bonus', 
      modifiers: extractModifiers(calc.ability_modifier_bonus).map(m => ({
        name: m.name,
        value: m.value,
        source_entity_name: m.source_entity_name
      }))
    });
  }
  
  // 2. Saving Throw Bonus itself (specific modifiers)
  if (savingThrow.bonus) {
    sections.push({ 
      label: 'Saving Throw Bonus', 
      modifiers: extractModifiers(savingThrow.bonus).map(m => ({
        name: m.name,
        value: m.value,
        source_entity_name: m.source_entity_name
      }))
    });
  }
  
  // Filter out empty groups
  const activeSections = sections.filter((s) => s.modifiers.length > 0);
  if (activeSections.length === 0) {
    return (
      <Paper elevation={1} sx={{ p: 2 }}>
        <Typography variant="body2">No detailed modifier breakdown available.</Typography>
      </Paper>
    );
  }
  
  const getTotal = (modifiers: ModifierDisplay[]): number => 
    modifiers.reduce((sum: number, mod: ModifierDisplay) => sum + mod.value, 0);
  
  return (
    <>
      {activeSections.map((section, sIdx) => (
        <Accordion key={sIdx} defaultExpanded sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1">{section.label}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box key={sIdx} sx={{ mb: 2 }}>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {section.label} – Total: {formatBonus(getTotal(section.modifiers))}
              </Typography>
              <List dense disablePadding>
                {section.modifiers.map((mod, i) => (
                  <ListItem key={i} dense divider={i < section.modifiers.length - 1}>
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
          </AccordionDetails>
        </Accordion>
      ))}
    </>
  );
};

const formatBonus = (n: number) => `${n}`;

const DetailDialog: React.FC<{
  savingThrow: SavingThrowSnapshot | null;
  calc?: SavingThrowBonusCalculationSnapshot;
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
            <Grid size={{ xs: 12, md: 6 }}>
              {/* Overview */}
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                <Grid container spacing={2}>
                  <Grid size={6}>
                    <Typography variant="body2" color="text.secondary">
                      Ability
                    </Typography>
                    <Typography variant="h5">{savingThrow.ability.toUpperCase()}</Typography>
                  </Grid>
                  <Grid size={6}>
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
                  {autoHit === AutoHitStatus.HIT && (
                    <Chip size="small" label="Auto Success" color="info" />
                  )}
                  {autoHit === AutoHitStatus.MISS && (
                    <Chip size="small" label="Auto Fail" color="error" />
                  )}
                  {critical === CriticalStatus.CRITICAL && (
                    <Chip size="small" label="Always Crit" color="warning" />
                  )}
                  {critical === CriticalStatus.NORMAL && (
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
                  { label: 'Proficiency Bonus', value: calc.normalized_proficiency_bonus.normalized_value },
                  { label: 'Saving Throw Bonus', value: calc.saving_throw_bonus.normalized_value },
                  { label: 'Ability Bonus', value: calc.ability_bonus.normalized_value },
                  { label: 'Ability Modifier Bonus', value: calc.ability_modifier_bonus.normalized_value },
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
                    {critical === CriticalStatus.CRITICAL ? 'Save automatically results in a critical success' :
                     critical === CriticalStatus.NORMAL ? 'Save can never be a critical success' :
                     'Normal critical rules apply'}
                  </Typography>
                )}
                {autoHit !== AutoHitStatus.NONE && (
                  <Typography variant="body1">
                    {autoHit === AutoHitStatus.HIT ? 'Save automatically succeeds' :
                     autoHit === AutoHitStatus.MISS ? 'Save automatically fails' :
                     'Normal success rules apply'}
                  </Typography>
                )}
              </Paper>
            </Grid>
            
            {/* Right column */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="h6" gutterBottom>
                Modifier Breakdown
              </Typography>
              <ModifierBreakdown savingThrow={savingThrow} calc={calc} />
            </Grid>
            
            {/* Debug */}
            <Grid size={12}>
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
      .filter(Boolean) as SavingThrowSnapshot[];
  }, [savingThrows]);
  
  if (!savingThrows) return null;
  
  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Saving Throws
      </Typography>
      <Grid container spacing={2}>
        {ordered.map((st) => {
          const bonus = st.effective_bonus ?? st.bonus?.normalized_value ?? 0;
          return (
            <Grid size={{ xs: 6, sm: 4, md: 2 }} key={st.name}>
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