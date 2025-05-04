import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  Grid,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Character, ModifiableValueSnapshot } from '../../models/character';

interface Props {
  entity: Character;
}

const format = (v: number | undefined) => (v ?? 0) >= 0 ? `+${v}` : `${v}`;

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
                <ListItem key={i} dense divider={i < ch.value_modifiers.length - 1}>
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

const ArmorSection: React.FC<Props> = ({ entity }) => {
  const acCalc = entity.ac_calculation;
  const equipment = entity.equipment;

  // dialog state - must be declared before any early return per hooks rules
  const [open, setOpen] = React.useState(false);

  if (!acCalc) return null;

  const totalAC = acCalc.final_ac;
  const isUnarmored = acCalc.is_unarmored;

  const combinedDex = acCalc.combined_dexterity_bonus?.normalized_score;
  const maxDex = acCalc.max_dexterity_bonus?.normalized_score;

  const bodyArmorName = equipment.body_armor ? equipment.body_armor.name : equipment.unarmored_ac_type;
  const shieldName = equipment.weapon_off_hand && (equipment.weapon_off_hand as any).ac_bonus ? (equipment.weapon_off_hand as any).name : undefined;

  // Normalize arrays so we avoid optional chaining complaints
  const abilityBonuses = acCalc.ability_bonuses ?? [];
  const abilityModifierBonuses = acCalc.ability_modifier_bonuses ?? [];
  const unarmoredAbilities = acCalc.unarmored_abilities ?? [];

  // Build arrays for display
  const unarmoredValues = acCalc.unarmored_values ?? [];
  const armoredValues = acCalc.armored_values ?? [];

  const leftValues: ModifiableValueSnapshot[] = [];
  if (isUnarmored) {
    leftValues.push(...unarmoredValues, ...abilityBonuses, ...abilityModifierBonuses);
    if (acCalc.max_dexterity_bonus) {
      leftValues.push(acCalc.max_dexterity_bonus);
    }
  } else {
    leftValues.push(...armoredValues);
    if (acCalc.combined_dexterity_bonus) leftValues.push(acCalc.combined_dexterity_bonus);
    if (acCalc.max_dexterity_bonus) leftValues.push(acCalc.max_dexterity_bonus);
  }

  const breakdownItems: { label: string; mv: ModifiableValueSnapshot }[] = [];
  if (isUnarmored) {
    unarmoredValues.forEach((mv) => breakdownItems.push({ label: mv.name, mv }));
    abilityBonuses.forEach((mv, idx) =>
      breakdownItems.push({
        label: unarmoredAbilities[idx] ? `${unarmoredAbilities[idx]} Score` : `Ability Bonus ${idx + 1}`,
        mv,
      })
    );
    abilityModifierBonuses.forEach((mv, idx) =>
      breakdownItems.push({
        label: unarmoredAbilities[idx] ? `${unarmoredAbilities[idx]} Modifier` : `Ability Modifier ${idx + 1}`,
        mv,
      })
    );
    if (acCalc.max_dexterity_bonus) {
      breakdownItems.push({ label: 'Max Dex Allowed', mv: acCalc.max_dexterity_bonus });
    }
  } else {
    armoredValues.forEach((mv) => breakdownItems.push({ label: mv.name, mv }));
    if (acCalc.combined_dexterity_bonus)
      breakdownItems.push({ label: 'Dexterity Bonus (Capped)', mv: acCalc.combined_dexterity_bonus });
    if (acCalc.dexterity_bonus) breakdownItems.push({ label: 'Dexterity Score', mv: acCalc.dexterity_bonus });
    if (acCalc.dexterity_modifier_bonus)
      breakdownItems.push({ label: 'Dexterity Modifier', mv: acCalc.dexterity_modifier_bonus });
    if (acCalc.max_dexterity_bonus)
      breakdownItems.push({ label: 'Max Dex Allowed', mv: acCalc.max_dexterity_bonus });
  }

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Armor
      </Typography>
      <Paper
        sx={{ p: 2, cursor: 'pointer', display: 'flex', gap: 2, alignItems: 'center' }}
        elevation={3}
        onClick={() => setOpen(true)}
      >
        <Typography variant="h4" color="primary">
          {totalAC}
        </Typography>
        <Chip label={isUnarmored ? 'Unarmored' : 'Armored'} size="small" color={isUnarmored ? 'default' : 'secondary'} />
        {!isUnarmored && combinedDex !== undefined && maxDex !== undefined && (
          <Chip label={`Dex ${combinedDex}/${maxDex}`} size="small" />
        )}
      </Paper>

      {/* Detail dialog */}
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Armor Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            {/* Left column */}
            <Grid item xs={12} md={6}>
              {/* Overview */}
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                <Typography variant="body2" color="text.secondary">
                  Armor Type
                </Typography>
                <Typography variant="h6" gutterBottom>
                  {isUnarmored ? bodyArmorName : bodyArmorName + (shieldName ? ` + ${shieldName}` : '')}
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Total AC
                </Typography>
                <Typography variant="h4" color="primary">
                  {totalAC}
                </Typography>
              </Paper>

              {/* Component values */}
              <Typography variant="h6" gutterBottom>
                Component Values
              </Typography>
              <Paper sx={{ p: 2 }} elevation={1}>
                {leftValues.map((mv, idx) => (
                  <React.Fragment key={idx}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography variant="body2" color="text.secondary">
                        {mv.name}
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {format(mv.normalized_score)}
                      </Typography>
                    </Box>
                    {idx < leftValues.length - 1 && <Divider sx={{ my: 1 }} />}
                  </React.Fragment>
                ))}
              </Paper>
            </Grid>

            {/* Right column */}
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Modifier Breakdown
              </Typography>
              {breakdownItems.map(({ label, mv }, idx) => (
                <ChannelBreakdown key={idx} mv={mv} label={label} />
              ))}
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ArmorSection; 