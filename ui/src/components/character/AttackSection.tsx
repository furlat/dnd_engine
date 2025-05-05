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
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  List,
  ListItem,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
} from '@mui/material';
import { Character, AttackBonusCalculationSnapshot, ModifiableValueSnapshot, EquipmentSnapshot } from '../../models/character';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { useEntity } from '../../contexts/EntityContext';
import ItemDetailsDialog from './ItemDetailsDialog';
import { fetchAllEquipment, equipItem, unequipItem } from '../../api/characterApi';
import { EquipmentItem } from '../../api/types';
import { AdvantageStatus, AutoHitStatus, CriticalStatus } from '../../models/character';

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

interface WeaponListItem {
  uuid: string;
  name: string;
  type: string;
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

const ModifierBreakdown: React.FC<{ 
  components: { label: string; mv: ModifiableValueSnapshot }[];
  showAdvantage?: boolean;
}> = ({ components, showAdvantage = false }) => (
  <>
    <Typography variant="h6" gutterBottom>
      Modifier Breakdown
    </Typography>
    {components.map((c, idx) => (
      <Accordion key={idx} defaultExpanded sx={{ mb: 1 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography>{c.label}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {c.mv.channels.map((ch, chIdx) => (
            <Box key={chIdx} sx={{ mb: 1 }}>
              <Typography variant="body2" fontWeight="bold">
                {ch.name}
              </Typography>
              <List dense disablePadding>
                {(showAdvantage ? ch.advantage_modifiers : ch.value_modifiers).map((mod: any, modIdx: number) => (
                  <ListItem
                    key={modIdx}
                    dense
                    divider={modIdx < (showAdvantage ? ch.advantage_modifiers.length : ch.value_modifiers.length) - 1}
                  >
                    <ListItemText
                      primary={mod.name}
                      secondary={mod.source_entity_name}
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                    <Chip
                      label={showAdvantage ? mod.value : (mod.value >= 0 ? `+${mod.value}` : mod.value)}
                      size="small"
                      color={showAdvantage 
                        ? (mod.value === 'ADVANTAGE' ? 'success' : mod.value === 'DISADVANTAGE' ? 'error' : 'default')
                        : (mod.value >= 0 ? 'success' : 'error')
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          ))}
          {c.mv.channels.every(ch => (showAdvantage ? ch.advantage_modifiers.length : ch.value_modifiers.length) === 0) && (
            <Typography variant="body2" color="text.secondary">
              No {showAdvantage ? 'advantage' : 'value'} modifiers
            </Typography>
          )}
        </AccordionDetails>
      </Accordion>
    ))}
  </>
);

const AttackCard: React.FC<{ slot: 'MAIN_HAND' | 'OFF_HAND'; calc?: AttackBonusCalculationSnapshot; equipment: EquipmentSnapshot; entity: Character }> = ({ slot, calc, equipment, entity }) => {
  const [open, setOpen] = React.useState(false);
  const [detailMode, setDetailMode] = React.useState<'attack' | 'damage' | 'advantage'>('attack');
  const [itemDetailsOpen, setItemDetailsOpen] = React.useState(false);
  const [menuAnchor, setMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [weaponSelectOpen, setWeaponSelectOpen] = React.useState(false);
  const [availableWeapons, setAvailableWeapons] = React.useState<EquipmentItem[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const { refreshEntity, setEntityData } = useEntity();

  // Fetch available weapons when the selection dialog opens
  React.useEffect(() => {
    if (weaponSelectOpen) {
      setIsLoading(true);
      console.log('Fetching equipment for entity:', entity.uuid);
      fetchAllEquipment(entity.uuid)
        .then(items => {
          console.log('All equipment items:', items);
          // Filter for weapons only
          const weapons = items.filter(item => 
            'damage_dice' in item && 
            'damage_type' in item &&
            !('ac_bonus' in item) // Exclude shields which might have damage properties
          );
          console.log('Filtered weapon items:', weapons);
          setAvailableWeapons(weapons);
        })
        .catch(error => {
          console.error('Failed to fetch weapons:', error);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [weaponSelectOpen, entity.uuid]);

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

  // Get combat statuses from total_bonus
  const advantage = calc.total_bonus?.advantage ?? 'None';
  const autoHit = calc.total_bonus?.auto_hit ?? 'None';
  const critical = calc.total_bonus?.critical ?? 'None';

  console.log('Attack Card Debug:', {
    weaponName,
    slot,
    totalBonus: calc.total_bonus,
    advantage,
    autoHit,
    critical,
    rawCalc: calc
  });

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
  const damageTypeLabel = typeof damageType === 'string' ? damageType.charAt(0).toUpperCase() + damageType.slice(1).toLowerCase() : String(damageType);

  // Extra damage expressions
  const extraDamageExprs = (() => {
    if (!weapon || !weapon.extra_damages) return [];
    return weapon.extra_damages.map((extra: any) => {
      const base = `${extra.dice_numbers}d${extra.damage_dice}`;
      const bonus = extra.damage_bonus?.normalized_score ?? 0;
      const expr = bonus !== 0 ? `${base}${bonus > 0 ? '+' : ''}${bonus}` : base;
      const type = typeof extra.damage_type === 'string' 
        ? extra.damage_type.charAt(0).toUpperCase() + extra.damage_type.slice(1).toLowerCase() 
        : String(extra.damage_type);
      return { expr, type };
    });
  })();

  // Damage components list builder
  const buildDamageComponents = (): { label: string; mv: ModifiableValueSnapshot }[] => {
    const items: { label: string; mv: ModifiableValueSnapshot }[] = [];
    if (weapon && (weapon as any).damage_bonus) items.push({ label: 'Weapon Damage Bonus', mv: (weapon as any).damage_bonus });
    if (calc.is_unarmed && equipment.unarmed_damage_bonus)
      items.push({ label: 'Unarmed Damage Bonus', mv: equipment.unarmed_damage_bonus });
    // Global equipment bonuses
    if (equipment.damage_bonus) items.push({ label: 'Global Damage Bonus', mv: equipment.damage_bonus });
    if (calc.is_ranged && equipment.ranged_damage_bonus)
      items.push({ label: 'Ranged Damage Bonus', mv: equipment.ranged_damage_bonus });
    if (!calc.is_ranged && equipment.melee_damage_bonus)
      items.push({ label: 'Melee Damage Bonus', mv: equipment.melee_damage_bonus });
    // Add extra damage bonuses if they exist
    if (weapon && weapon.extra_damages) {
      weapon.extra_damages.forEach((extra: any, idx: number) => {
        if (extra.damage_bonus) {
          items.push({ 
            label: `Extra Damage ${idx + 1} Bonus`, 
            mv: extra.damage_bonus 
          });
        }
      });
    }
    return items;
  };

  const damageComponents = (() => {
    const base = buildDamageComponents();
    const pseudoMV: ModifiableValueSnapshot = {
      name: 'Ability Modifier',
      uuid: '',
      score: getAbilityModifier(),
      normalized_score: getAbilityModifier(),
      channels: [],
    } as any;
    base.push({ label: 'Ability Modifier', mv: pseudoMV });
    return base;
  })();

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();  // Prevent opening attack details
    setMenuAnchor(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
  };

  const handleUnequip = async () => {
    handleMenuClose();
    try {
      setIsLoading(true);
      const updatedEntity = await unequipItem(entity.uuid, slot);
      setEntityData(updatedEntity);
      setIsLoading(false);
    } catch (error: any) {
      console.error('Failed to unequip weapon:', error);
      if (error.response?.data?.message) {
        alert(error.response.data.message);
      } else {
        alert('Failed to unequip weapon. Please try again.');
      }
      setIsLoading(false);
    }
  };

  const handleWeaponSelect = async (weaponId: string) => {
    try {
      setIsLoading(true);
      const updatedEntity = await equipItem(entity.uuid, weaponId, slot);
      setEntityData(updatedEntity);
      setWeaponSelectOpen(false);
    } catch (error: any) {
      console.error('Failed to equip weapon:', error);
      if (error.response?.data?.detail) {
        alert(`Failed to equip weapon: ${error.response.data.detail}`);
      } else {
        alert('Failed to equip weapon. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Paper
        sx={{ p: 1.5, display: 'flex', gap: 1.5, alignItems: 'center', mb: 2.5, minHeight: 90 }}
        elevation={3}
        onClick={(e) => {
          // Only open details if not clicking menu, weapon name, or damage chips
          const target = e.target as HTMLElement;
          const isClickableElement = target.closest('.clickable-element') || target.closest('.MuiChip-root');
          if (!isClickableElement) {
            setDetailMode('attack');
            setOpen(true);
          }
        }}
      >
        {/* Attack bonus */}
        <Box className="clickable-element" onClick={(e) => { 
          e.stopPropagation(); 
          setDetailMode('attack'); 
          setOpen(true); 
        }}>
          <Typography variant="h4" color="primary">
            {format(final)}
          </Typography>
        </Box>

        {/* Weapon name and status */}
        <Box sx={{ flexGrow: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography 
              className="clickable-element"
              variant="subtitle1" 
              sx={{ 
                cursor: 'pointer', 
                '&:hover': { textDecoration: 'underline' }
              }}
              onClick={(e) => {
                e.stopPropagation();
                if (weapon) setItemDetailsOpen(true);
              }}
            >
              {weaponName}
            </Typography>
            {/* Combat Status Chips */}
            {/* Always show advantage status */}
            {advantage === 'None' ? (
              <Chip 
                size="small" 
                label="N/A" 
                color="default" 
                onClick={(e) => {
                  e.stopPropagation();
                  setDetailMode('advantage');
                  setOpen(true);
                }}
              />
            ) : advantage === 'Advantage' ? (
              <Chip 
                size="small" 
                label="Advantage" 
                color="success" 
                onClick={(e) => {
                  e.stopPropagation();
                  setDetailMode('advantage');
                  setOpen(true);
                }}
              />
            ) : advantage === 'Disadvantage' ? (
              <Chip 
                size="small" 
                label="Disadvantage" 
                color="error" 
                onClick={(e) => {
                  e.stopPropagation();
                  setDetailMode('advantage');
                  setOpen(true);
                }}
              />
            ) : (
              <Chip 
                size="small" 
                label="N/A" 
                color="default" 
                onClick={(e) => {
                  e.stopPropagation();
                  setDetailMode('advantage');
                  setOpen(true);
                }}
              />
            )}
            {autoHit === AutoHitStatus.AUTOHIT && (
              <Chip size="small" label="Auto Hit" color="info" />
            )}
            {autoHit === AutoHitStatus.AUTOMISS && (
              <Chip size="small" label="Auto Miss" color="error" />
            )}
            {critical === CriticalStatus.AUTOCRIT && (
              <Chip size="small" label="Always Crit" color="warning" />
            )}
            {critical === CriticalStatus.NOCRIT && (
              <Chip size="small" label="Never Crit" color="error" />
            )}
          </Box>
          <Typography variant="caption" color="text.secondary" display="block">
            {slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'} – {rangeLabel}
          </Typography>
        </Box>
        {/* Damage expressions */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Chip
            className="clickable-element"
            size="small"
            label={`${damageExpr} ${damageTypeLabel}`}
            onClick={(e) => { e.stopPropagation(); setDetailMode('damage'); setOpen(true); }}
          />
          {extraDamageExprs.map((extra, idx) => (
            <Chip
              key={idx}
              className="clickable-element"
              size="small"
              label={`${extra.expr} ${extra.type}`}
              onClick={(e) => { e.stopPropagation(); setDetailMode('damage'); setOpen(true); }}
              color="secondary"
            />
          ))}
        </Box>
        {calc.is_ranged && <Chip className="clickable-element" size="small" label="Ranged" sx={{ ml: 0.5 }} />}
        {calc.properties.includes('Finesse') && <Chip className="clickable-element" size="small" label="Finesse" sx={{ ml: 0.5 }} />}

        {/* Add menu button */}
        <Box 
          className="clickable-element"
          onClick={(e) => e.stopPropagation()}
          sx={{ ml: 'auto' }}
        >
          <IconButton
            size="small"
            onClick={handleMenuClick}
          >
            <MoreVertIcon />
          </IconButton>
        </Box>

        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={handleMenuClose}
          onClick={(e) => e.stopPropagation()}
        >
          <MenuItem onClick={() => {
            handleMenuClose();
            setWeaponSelectOpen(true);
          }}>
            <ListItemIcon>
              <SwapHorizIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Change Weapon</ListItemText>
          </MenuItem>
          <MenuItem 
            onClick={handleUnequip}
            disabled={calc.is_unarmed}
          >
            <ListItemIcon>
              <DeleteIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Unequip</ListItemText>
          </MenuItem>
        </Menu>
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {weaponName} {detailMode === 'attack' ? 'Attack' : detailMode === 'damage' ? 'Damage' : 'Advantage Status'} Details ({slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'})
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
                <ModifierBreakdown components={components} showAdvantage={false} />
              </Grid>
            </Grid>
          ) : detailMode === 'damage' ? (
            <Grid container spacing={2}>
              {/* Left column for Damage */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Overview
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                  <Typography variant="body2" color="text.secondary">
                    Base Damage
                  </Typography>
                  <Typography variant="h4" color="primary">
                    {damageExpr}
                  </Typography>
                  <Typography variant="h6">{damageTypeLabel}</Typography>
                  
                  {extraDamageExprs.length > 0 && (
                    <>
                      <Divider sx={{ my: 2 }} />
                      <Typography variant="body2" color="text.secondary">
                        Extra Damage
                      </Typography>
                      {extraDamageExprs.map((extra, idx) => (
                        <Box key={idx} sx={{ mt: 1 }}>
                          <Typography variant="h5" color="secondary">
                            {extra.expr}
                          </Typography>
                          <Typography variant="subtitle1">{extra.type}</Typography>
                        </Box>
                      ))}
                    </>
                  )}
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
                <ModifierBreakdown components={damageComponents} showAdvantage={false} />
              </Grid>
            </Grid>
          ) : (
            <Grid container spacing={2}>
              {/* Left column */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Overview
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                  <Typography variant="body2" color="text.secondary">
                    Current Status
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
                    {/* Advantage Status */}
                    <Chip 
                      size="small" 
                      label={advantage === AdvantageStatus.NONE ? 'Normal' :
                             advantage === AdvantageStatus.ADVANTAGE ? 'Advantage' : 'Disadvantage'}
                      color={advantage === AdvantageStatus.NONE ? 'default' :
                             advantage === AdvantageStatus.ADVANTAGE ? 'success' : 'error'}
                    />
                    {/* Critical Status */}
                    <Chip 
                      size="small" 
                      label={critical === CriticalStatus.NONE ? 'Normal Crit' :
                             critical === CriticalStatus.AUTOCRIT ? 'Always Crit' : 'Never Crit'}
                      color={critical === CriticalStatus.NONE ? 'default' :
                             critical === CriticalStatus.AUTOCRIT ? 'warning' : 'error'}
                    />
                    {/* Auto Hit Status */}
                    <Chip 
                      size="small" 
                      label={autoHit === AutoHitStatus.NONE ? 'Normal Hit' :
                             autoHit === AutoHitStatus.AUTOHIT ? 'Auto Hit' : 'Auto Miss'}
                      color={autoHit === AutoHitStatus.NONE ? 'default' :
                             autoHit === AutoHitStatus.AUTOHIT ? 'info' : 'error'}
                    />
                  </Box>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {advantage === AdvantageStatus.ADVANTAGE ? 'Roll twice and take the higher result' :
                     advantage === AdvantageStatus.DISADVANTAGE ? 'Roll twice and take the lower result' :
                     'Roll normally'}
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {critical === CriticalStatus.AUTOCRIT ? 'Attack always results in a critical hit' :
                     critical === CriticalStatus.NOCRIT ? 'Attack can never be a critical hit' :
                     'Normal critical hit rules apply'}
                  </Typography>
                  <Typography variant="body1">
                    {autoHit === AutoHitStatus.AUTOHIT ? 'Attack automatically hits the target' :
                     autoHit === AutoHitStatus.AUTOMISS ? 'Attack automatically misses the target' :
                     'Normal hit rules apply'}
                  </Typography>
                </Paper>

                <Typography variant="h6" gutterBottom>
                  Component Values
                </Typography>
                <Paper sx={{ p: 2 }} elevation={1}>
                  {/* Advantage Values */}
                  <Typography variant="subtitle2" gutterBottom>Advantage Effects</Typography>
                  {calc.total_bonus.channels.map((ch, idx) => (
                    <React.Fragment key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {ch.name}
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {ch.advantage_status}
                        </Typography>
                      </Box>
                      {idx < calc.total_bonus.channels.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}

                  {/* Critical Values */}
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>Critical Effects</Typography>
                  {calc.total_bonus.channels.map((ch, idx) => (
                    <React.Fragment key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {ch.name}
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {ch.critical_status}
                        </Typography>
                      </Box>
                      {idx < calc.total_bonus.channels.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}

                  {/* Auto Hit Values */}
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>Auto Hit Effects</Typography>
                  {calc.total_bonus.channels.map((ch, idx) => (
                    <React.Fragment key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {ch.name}
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {ch.auto_hit_status}
                        </Typography>
                      </Box>
                      {idx < calc.total_bonus.channels.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}
                </Paper>
              </Grid>

              {/* Right column */}
              <Grid item xs={12} md={6}>
                <ModifierBreakdown components={components} showAdvantage={true} />
              </Grid>
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Item Details Dialog */}
      {weapon && (
        <ItemDetailsDialog
          open={itemDetailsOpen}
          onClose={() => setItemDetailsOpen(false)}
          item={weapon}
          itemType="weapon"
        />
      )}

      {/* Weapon Selection Dialog */}
      <Dialog 
        open={weaponSelectOpen} 
        onClose={() => !isLoading && setWeaponSelectOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Select Weapon for {slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'}</DialogTitle>
        <DialogContent>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Box>
          ) : (
            <List>
              {availableWeapons.map((weapon) => (
                <ListItem 
                  button 
                  key={weapon.uuid}
                  onClick={() => handleWeaponSelect(weapon.uuid)}
                  disabled={isLoading}
                >
                  <ListItemText 
                    primary={weapon.name} 
                    secondary={
                      'damage_dice' in weapon ? 
                        `${weapon.dice_numbers}d${weapon.damage_dice} ${weapon.damage_type}` : 
                        undefined
                    }
                  />
                </ListItem>
              ))}
              {availableWeapons.length === 0 && !isLoading && (
                <ListItem>
                  <ListItemText primary="No weapons available" />
                </ListItem>
              )}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setWeaponSelectOpen(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

const AttackSection: React.FC<Props> = ({ entity }) => {
  const calcsObj = entity.attack_calculations ?? {};
  const equipment = entity.equipment;

  // Backend uses "MAIN_HAND" / "OFF_HAND" string values
  const mainHandCalc = Object.values(calcsObj).find(
    (c: any) => c && c.weapon_slot === 'MAIN_HAND'
  ) as AttackBonusCalculationSnapshot | undefined;

  const offHandCalc = Object.values(calcsObj).find(
    (c: any) => c && c.weapon_slot === 'OFF_HAND'
  ) as AttackBonusCalculationSnapshot | undefined;

  // If calculations are null, create default unarmed attack calculations
  const defaultUnarmedCalc: AttackBonusCalculationSnapshot = {
    weapon_slot: 'MAIN_HAND',
    proficiency_bonus: entity.proficiency_bonus,
    weapon_bonus: equipment.unarmed_attack_bonus,
    attack_bonuses: [],
    ability_bonuses: [],
    range: { type: 'REACH', normal: 5 },
    weapon_name: 'Unarmed Strike',
    is_unarmed: true,
    is_ranged: false,
    properties: equipment.unarmed_properties,
    has_cross_entity_effects: false,
    total_bonus: equipment.unarmed_attack_bonus,
    final_modifier: equipment.unarmed_attack_bonus.normalized_score,
    advantage_status: 'NONE',
    auto_hit_status: 'NONE',
    critical_status: 'NONE'
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Attack
      </Typography>
      <AttackCard 
        slot="MAIN_HAND" 
        calc={mainHandCalc || defaultUnarmedCalc} 
        equipment={equipment} 
        entity={entity} 
      />
      <AttackCard 
        slot="OFF_HAND" 
        calc={offHandCalc || {...defaultUnarmedCalc, weapon_slot: 'OFF_HAND'}} 
        equipment={equipment} 
        entity={entity} 
      />
    </Box>
  );
};

export default AttackSection; 