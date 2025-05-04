import * as React from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Grid,
  Divider,
} from '@mui/material';
import { Character, AttackBonusCalculationSnapshot, ModifiableValueSnapshot } from '../../models/character';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';

interface Props {
  entity: Character;
}

const format = (n: number | undefined) => (n ?? 0) >= 0 ? `+${n}` : `${n}`;

const ChannelBreakdown: React.FC<{ mv: ModifiableValueSnapshot; label: string }> = ({ mv, label }) => {
  if (!mv || !mv.channels) return null;
  return (
    <Accordion defaultExpanded sx={{ mb: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>{label}</AccordionSummary>
      <AccordionDetails>
        {mv.channels.map((ch, idx) => (
          <Box key={idx} sx={{ mb: 1 }}>
            <Typography variant="body2" fontWeight="bold">
              {ch.name} – Total: {format(ch.normalized_score)}
            </Typography>
            <List dense disablePadding>
              {ch.value_modifiers.map((mod, i) => (
                <ListItem
                  key={i}
                  dense
                  divider={i < ch.value_modifiers.length - 1}
                >
                  <ListItemText
                    primary={mod.name}
                    secondary={mod.source_entity_name}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                  <Chip
                    label={format(mod.value)}
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
  );
};

// Helper to build breakdown arrays
const buildComponentList = (calc: AttackBonusCalculationSnapshot) => {
  return [
    { label: 'Proficiency Bonus', mv: calc.proficiency_bonus },
    { label: calc.weapon_name ? 'Weapon Bonus' : 'Unarmed Bonus', mv: calc.weapon_bonus },
    ...calc.attack_bonuses.map((mv) => ({ label: mv.name, mv })),
    ...calc.ability_bonuses.map((mv) => ({ label: mv.name, mv })),
  ];
};

const AttackCard: React.FC<{ slot: 'MAIN_HAND' | 'OFF_HAND'; calc?: AttackBonusCalculationSnapshot }> = ({ slot, calc }) => {
  const [open, setOpen] = React.useState(false);

  if (!calc) return null;

  const weaponName = calc.is_unarmed ? 'Unarmed Strike' : calc.weapon_name ?? 'Weapon';
  const final = calc.final_modifier;
  const rangeLabel = calc.range.type === 'RANGE' ? `${calc.range.normal}/${calc.range.long ?? ''}` : 'Melee';

  const components = buildComponentList(calc);

  return (
    <>
      <Paper
        sx={{ p: 2, cursor: 'pointer', display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}
        elevation={3}
        onClick={() => setOpen(true)}
      >
        <Typography variant="h4" color="primary">
          {format(final)}
        </Typography>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="subtitle1">{weaponName}</Typography>
          <Typography variant="caption" color="text.secondary">
            {slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'} – {rangeLabel}
          </Typography>
        </Box>
        {calc.is_ranged && <Chip size="small" label="Ranged" />}
        {calc.properties.includes('Finesse') && <Chip size="small" label="Finesse" />}
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{weaponName} Details ({slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'})</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            {/* Left column */}
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                <Typography variant="body2" color="text.secondary">
                  Final Modifier
                </Typography>
                <Typography variant="h4" color="primary">
                  {format(final)}
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Range / Reach
                </Typography>
                <Typography variant="h6">{rangeLabel}</Typography>
                {calc.properties.length > 0 && (
                  <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {calc.properties.map((p) => (
                      <Chip key={p} size="small" label={p} />
                    ))}
                  </Box>
                )}
              </Paper>

              <Typography variant="h6" gutterBottom>
                Component Values
              </Typography>
              <Paper sx={{ p: 2 }} elevation={1}>
                {components.map((c, idx) => (
                  <React.Fragment key={idx}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">
                        {c.label}
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {format(c.mv.normalized_score)}
                      </Typography>
                    </Box>
                    {idx < components.length - 1 && <Divider sx={{ my: 1 }} />}
                  </React.Fragment>
                ))}
              </Paper>
            </Grid>

            {/* Right column */}
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Modifier Breakdown
              </Typography>
              {components.map((c, idx) => (
                <ChannelBreakdown key={idx} mv={c.mv} label={c.label} />
              ))}
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

const AttackSection: React.FC<Props> = ({ entity }) => {
  const calcsObj = entity.attack_calculations ?? {};

  // Backend uses "Main Hand" / "Off Hand" string values
  const mainHandCalc = Object.values(calcsObj).find(
    (c: any) => c && c.weapon_slot === 'Main Hand'
  ) as AttackBonusCalculationSnapshot | undefined;

  const offHandCalc = Object.values(calcsObj).find(
    (c: any) => c && c.weapon_slot === 'Off Hand'
  ) as AttackBonusCalculationSnapshot | undefined;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Attack
      </Typography>
      <AttackCard slot="MAIN_HAND" calc={mainHandCalc} />
      <AttackCard slot="OFF_HAND" calc={offHandCalc} />
    </Box>
  );
};

export default AttackSection; 