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
import { Character, AttackBonusCalculationSnapshot, ModifiableValueSnapshot, EquipmentSnapshot } from '../../models/character';
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

// Lightweight Weapon type (mirrors backend WeaponSnapshot essentials)
type WeaponSnapshotLite = {
  name: string;
  damage_dice: number;
  dice_numbers: number;
  damage_bonus?: ModifiableValueSnapshot | null;
  damage_type: string;
  properties?: string[];
  range?: any;
  extra_damages?: any[];
};

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

const AttackCard: React.FC<{ slot: 'MAIN_HAND' | 'OFF_HAND'; calc?: AttackBonusCalculationSnapshot; equipment: EquipmentSnapshot; entity: Character }> = ({ slot, calc, equipment, entity }) => {
  const [open, setOpen] = React.useState(false);
  const [detailMode, setDetailMode] = React.useState<'attack' | 'damage'>('attack');

  if (!calc) return null;

  // Resolve weapon snapshot (or unarmed)
  const weapon: WeaponSnapshotLite | undefined = (() => {
    if (slot === 'MAIN_HAND') return equipment.weapon_main_hand as any;
    if (slot === 'OFF_HAND') return equipment.weapon_off_hand as any;
    return undefined;
  })();

  const weaponName = calc.is_unarmed ? 'Unarmed Strike' : calc.weapon_name ?? 'Weapon';
  const final = calc.final_modifier;
  const rangeLabel = calc.range.type === 'RANGE' ? `${calc.range.normal}/${calc.range.long ?? ''}` : 'Melee';

  const components = buildComponentList(calc);

  // --- Damage expression helpers ---
  const getAbilityModifier = (): number => {
    const strMod = entity.ability_scores.strength.modifier ?? 0;
    const dexMod = entity.ability_scores.dexterity.modifier ?? 0;

    if (calc.is_unarmed) {
      const hasFinesse = equipment.unarmed_properties?.includes('Finesse');
      return hasFinesse ? Math.max(strMod, dexMod) : strMod;
    }
    // Weapon path
    if (calc.is_ranged) return dexMod;
    if (calc.properties.includes('Finesse')) return Math.max(strMod, dexMod);
    return strMod;
  };

  const getDamageBonusValue = (): number => {
    let bonus = 0;
    if (weapon && weapon.damage_bonus) bonus += weapon.damage_bonus.normalized_score ?? 0;
    if (calc.is_unarmed) bonus += equipment.unarmed_damage_bonus.normalized_score ?? 0;
    // Global equipment bonuses
    bonus += equipment.damage_bonus?.normalized_score ?? 0;
    // Melee / ranged specific
    if (calc.is_ranged) {
      bonus += equipment.ranged_damage_bonus?.normalized_score ?? 0;
    } else {
      bonus += equipment.melee_damage_bonus?.normalized_score ?? 0;
    }

    bonus += getAbilityModifier();
    return bonus;
  };

  const damageExpr = (() => {
    if (weapon) {
      const base = `${weapon.dice_numbers}d${weapon.damage_dice}`;
      const bonus = getDamageBonusValue();
      return bonus !== 0 ? `${base}${bonus > 0 ? '+' : ''}${bonus}` : base;
    }
    // Unarmed fallback
    const base = `${equipment.unarmed_dice_numbers}d${equipment.unarmed_damage_dice}`;
    const bonus = getDamageBonusValue();
    return bonus !== 0 ? `${base}${bonus > 0 ? '+' : ''}${bonus}` : base;
  })();

  const damageType = weapon ? weapon.damage_type : equipment.unarmed_damage_type;
  const damageTypeAbbr = typeof damageType === 'string' ? damageType.slice(0, 3).toUpperCase() : String(damageType).slice(0,3).toUpperCase();

  // Damage components list for detail view
  const buildDamageComponents = (): { label: string; mv: ModifiableValueSnapshot }[] => {
    const items: { label: string; mv: ModifiableValueSnapshot }[] = [];
    if (weapon && weapon.damage_bonus) items.push({ label: 'Weapon Damage Bonus', mv: weapon.damage_bonus });
    if (calc.is_unarmed && equipment.unarmed_damage_bonus)
      items.push({ label: 'Unarmed Damage Bonus', mv: equipment.unarmed_damage_bonus });
    // Global equipment bonuses
    if (equipment.damage_bonus) items.push({ label: 'Global Damage Bonus', mv: equipment.damage_bonus });
    if (calc.is_ranged && equipment.ranged_damage_bonus)
      items.push({ label: 'Ranged Damage Bonus', mv: equipment.ranged_damage_bonus });
    if (!calc.is_ranged && equipment.melee_damage_bonus)
      items.push({ label: 'Melee Damage Bonus', mv: equipment.melee_damage_bonus });
    return items;
  };

  let damageComponents: { label: string; mv: ModifiableValueSnapshot }[] = [];
  if (calc) {
    damageComponents = buildDamageComponents();
    const pseudoMV: ModifiableValueSnapshot = {
      name: 'Ability Modifier',
      uuid: '',
      score: getAbilityModifier(),
      normalized_score: getAbilityModifier(),
      channels: [],
    } as any;
    damageComponents.push({ label: 'Ability Modifier', mv: pseudoMV });
  }

  return (
    <>
      <Paper
        sx={{ p: 1.5, cursor: 'pointer', display: 'flex', gap: 1.5, alignItems: 'center', mb: 2, minHeight: 90 }}
        elevation={3}
        onClick={() => {
          setDetailMode('attack');
          setOpen(true);
        }}
      >
        {/* Attack modifier clickable */}
        <Box onClick={(e) => { e.stopPropagation(); setDetailMode('attack'); setOpen(true); }}>
          <Typography variant="h4" color="primary">
            {format(final)}
          </Typography>
        </Box>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="subtitle1">{weaponName}</Typography>
          <Typography variant="caption" color="text.secondary">
            {slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'} – {rangeLabel}
          </Typography>
        </Box>
        {/* Damage expression clickable */}
        <Chip
          size="small"
          label={`${damageExpr} ${damageTypeAbbr}`}
          onClick={(e) => { e.stopPropagation(); setDetailMode('damage'); setOpen(true); }}
        />
        {calc.is_ranged && <Chip size="small" label="Ranged" sx={{ ml: 0.5 }} />}
        {calc.properties.includes('Finesse') && <Chip size="small" label="Finesse" sx={{ ml: 0.5 }} />}
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {weaponName} {detailMode === 'attack' ? 'Attack' : 'Damage'} Details ({slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'})
        </DialogTitle>
        <DialogContent dividers>
          {detailMode === 'attack' ? (
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
          ) : (
            <Grid container spacing={2}>
              {/* Left column for Damage */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Overview
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                  <Typography variant="body2" color="text.secondary">
                    Damage Expression
                  </Typography>
                  <Typography variant="h4" color="primary">
                    {damageExpr}
                  </Typography>
                  <Divider sx={{ my: 1 }} />
                  <Typography variant="body2" color="text.secondary">
                    Damage Type
                  </Typography>
                  <Typography variant="h6">{damageType}</Typography>
                </Paper>

                <Typography variant="h6" gutterBottom>
                  Component Values
                </Typography>
                <Paper sx={{ p: 2 }} elevation={1}>
                  {damageComponents.length === 0 && (
                    <Typography variant="body2">No damage modifiers.</Typography>
                  )}
                  {damageComponents.map((c, idx) => (
                    <React.Fragment key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {c.label}
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {format(c.mv.normalized_score)}
                        </Typography>
                      </Box>
                      {idx < damageComponents.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}
                </Paper>
              </Grid>

              {/* Right column for Damage breakdown */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Modifier Breakdown
                </Typography>
                {damageComponents.map((c, idx) => (
                  <ChannelBreakdown key={idx} mv={c.mv} label={c.label} />
                ))}
              </Grid>
            </Grid>
          )}
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
  const equipment = entity.equipment;

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
      <AttackCard slot="MAIN_HAND" calc={mainHandCalc} equipment={equipment} entity={entity} />
      <AttackCard slot="OFF_HAND" calc={offHandCalc} equipment={equipment} entity={entity} />
    </Box>
  );
};

export default AttackSection; 