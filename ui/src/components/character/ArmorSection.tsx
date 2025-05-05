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
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  CircularProgress,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { Character, ModifiableValueSnapshot, AdvantageStatus, CriticalStatus, AutoHitStatus } from '../../models/character';
import { ArmorSnapshot } from '../../api/types';
import ItemDetailsDialog from './ItemDetailsDialog';
import { useEntity } from '../../contexts/EntityContext';
import { fetchAllEquipment, equipItem, unequipItem } from '../../api/characterApi';
import { EquipmentItem } from '../../api/types';

interface Props {
  entity: Character;
}

const format = (n: number | undefined) => (n ?? 0) >= 0 ? `+${n}` : `${n}`;

const ChannelBreakdown: React.FC<{ mv: ModifiableValueSnapshot; label: string; showAdvantage?: boolean }> = ({ mv, label, showAdvantage = false }) => {
  if (!mv || !mv.channels) return null;
  return (
    <Accordion defaultExpanded sx={{ mb: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>{label}</AccordionSummary>
      <AccordionDetails>
        {mv.channels.map((ch, idx) => (
          <Box key={idx} sx={{ mb: 1 }}>
            <Typography variant="body2" fontWeight="bold">
              {ch.name} – Total: {showAdvantage ? ch.advantage_status : format(ch.normalized_score)}
            </Typography>
            <List dense disablePadding>
              {(showAdvantage ? ch.advantage_modifiers : ch.value_modifiers).map((mod: any, i: number) => (
                <ListItem
                  key={i}
                  dense
                  divider={i < (showAdvantage ? ch.advantage_modifiers.length : ch.value_modifiers.length) - 1}
                >
                  <ListItemText
                    primary={mod.name}
                    secondary={mod.source_entity_name}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                  <Chip
                    label={showAdvantage ? mod.value : format(mod.value)}
                    size="small"
                    color={showAdvantage 
                      ? (mod.value === 'ADVANTAGE' ? 'success' : mod.value === 'DISADVANTAGE' ? 'error' : 'default')
                      : (mod.value >= 0 ? 'success' : 'error')
                    }
                  />
                </ListItem>
              ))}
            </List>
            {ch.advantage_modifiers.length === 0 && showAdvantage && (
              <Typography variant="body2" color="text.secondary">
                No advantage modifiers
              </Typography>
            )}
          </Box>
        ))}
      </AccordionDetails>
    </Accordion>
  );
};

const ArmorSection: React.FC<Props> = ({ entity }) => {
  const { setEntityData } = useEntity();
  const acCalc = entity.ac_calculation;
  const equipment = entity.equipment;

  // dialog states
  const [open, setOpen] = React.useState(false);
  const [detailMode, setDetailMode] = React.useState<'armor' | 'advantage' | 'critical' | 'auto_hit'>('armor');
  const [itemDetailsOpen, setItemDetailsOpen] = React.useState<'armor' | 'shield' | null>(null);
  const [menuAnchor, setMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [armorSelectOpen, setArmorSelectOpen] = React.useState(false);
  const [availableArmor, setAvailableArmor] = React.useState<ArmorSnapshot[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);

  // Fetch available armor when the selection dialog opens
  React.useEffect(() => {
    if (armorSelectOpen) {
      setIsLoading(true);
      console.log('Fetching equipment for entity:', entity.uuid);
      fetchAllEquipment(entity.uuid)
        .then(items => {
          console.log('All equipment items:', items);
          // Filter for body armor only
          const armor = items.filter((item): item is ArmorSnapshot => {
            console.log('Checking item:', item);
            // Check if it's an armor item and specifically for the body
            return 'type' in item && 
                   'body_part' in item && 
                   item.body_part === 'Body' &&
                   ['Light', 'Medium', 'Heavy', 'Cloth'].includes(item.type);
          });
          console.log('Filtered armor items:', armor);
          setAvailableArmor(armor);
        })
        .catch(error => {
          console.error('Failed to fetch armor:', error);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [armorSelectOpen, entity.uuid]);

  if (!acCalc) return null;

  const totalAC = acCalc.final_ac;
  const isUnarmored = acCalc.is_unarmored;

  const combinedDex = acCalc.combined_dexterity_bonus?.normalized_score;
  const maxDex = acCalc.max_dexterity_bonus?.normalized_score;

  const bodyArmorName = equipment.body_armor ? equipment.body_armor.name : 'No Armor';
  const armorType = equipment.body_armor ? equipment.body_armor.type : 'Unarmored';
  const shieldName = equipment.weapon_off_hand && (equipment.weapon_off_hand as any).ac_bonus ? (equipment.weapon_off_hand as any).name : undefined;

  // Get armor type color
  const getArmorTypeColor = () => {
    if (!equipment.body_armor) return 'default';
    switch (equipment.body_armor.type) {
      case 'LIGHT': return 'success';
      case 'MEDIUM': return 'warning';
      case 'HEAVY': return 'error';
      case 'CLOTH': return 'info';
      default: return 'default';
    }
  };

  // Format armor type display
  const formatArmorType = (type: string) => {
    if (type === 'Unarmored') return type;
    return type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();  // Prevent opening armor details
    setMenuAnchor(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
  };

  const handleUnequip = async () => {
    handleMenuClose();
    try {
      setIsLoading(true);
      const unequipResult = await unequipItem(entity.uuid, 'Body');
      setEntityData(unequipResult);
      setIsLoading(false);
    } catch (error: any) {
      console.error('Failed to unequip armor:', error);
      if (error.response?.data?.message) {
        alert(error.response.data.message);
      } else {
        alert('Failed to unequip armor. Please try again.');
      }
      setIsLoading(false);
    }
  };

  const handleArmorSelect = async (armorId: string) => {
    try {
      setIsLoading(true);
      const equipResult = await equipItem(entity.uuid, armorId, 'Body');
      setEntityData(equipResult);
      setArmorSelectOpen(false);
    } catch (error: any) {
      console.error('Failed to equip armor:', error);
      if (error.response?.data?.detail) {
        alert(`Failed to equip armor: ${error.response.data.detail}`);
      } else {
        alert('Failed to equip armor. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

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
        sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}
        elevation={3}
        onClick={() => setOpen(true)}
      >
        <Typography variant="h4" color="primary">
          {totalAC}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', flexGrow: 1 }}>
          {/* Armor Type Chip */}
          <Chip 
            label={formatArmorType(armorType)} 
            size="small" 
            color={getArmorTypeColor()}
          />
          {/* Armor Name Chip */}
          <Chip 
            label={bodyArmorName} 
            size="small" 
            variant="outlined"
            onClick={(e) => {
              e.stopPropagation();
              if (equipment.body_armor) setItemDetailsOpen('armor');
            }}
            sx={{ cursor: equipment.body_armor ? 'pointer' : 'default' }}
          />
          {/* Shield Chip if present */}
          {shieldName && (
            <Chip 
              label={shieldName} 
              size="small" 
              variant="outlined"
              color="secondary"
              onClick={(e) => {
                e.stopPropagation();
                setItemDetailsOpen('shield');
              }}
              sx={{ cursor: 'pointer' }}
            />
          )}
          {/* Combat Status Chips - Only show Advantage */}
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip 
              label={acCalc.outgoing_advantage === AdvantageStatus.ADVANTAGE ? 'Give Advantage' : 
                     acCalc.outgoing_advantage === AdvantageStatus.DISADVANTAGE ? 'Give Disadvantage' : 'Normal'}
              size="small"
              sx={{ 
                minWidth: '140px',
                height: '24px',
                '& .MuiChip-label': { 
                  px: 2,
                  fontSize: '0.8125rem'
                },
                backgroundColor: acCalc.outgoing_advantage === AdvantageStatus.ADVANTAGE ? '#d32f2f !important' : 
                                acCalc.outgoing_advantage === AdvantageStatus.DISADVANTAGE ? '#2e7d32 !important' : '#757575 !important',
                color: '#fff !important'
              }}
              onClick={(e) => {
                e.stopPropagation();
                setDetailMode('advantage');
                setOpen(true);
              }}
            />
          </Box>
        </Box>

        {/* Add menu button */}
        <Box 
          onClick={(e) => e.stopPropagation()}
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
            setArmorSelectOpen(true);
          }}>
            <ListItemIcon>
              <SwapHorizIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Change Armor</ListItemText>
          </MenuItem>
          <MenuItem 
            onClick={handleUnequip}
            disabled={!equipment.body_armor}
          >
            <ListItemIcon>
              <DeleteIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Unequip</ListItemText>
          </MenuItem>
        </Menu>
      </Paper>

      {/* AC Details Dialog */}
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {detailMode === 'armor' ? 'Armor Class Details' : 
           detailMode === 'advantage' ? 'Outgoing Advantage Status' :
           detailMode === 'critical' ? 'Outgoing Critical Status' :
           'Outgoing Auto Hit Status'}
        </DialogTitle>
        <DialogContent dividers>
          {detailMode === 'armor' ? (
            <Grid container spacing={2}>
              {/* Left column */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Overview
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                  <Typography variant="body2" color="text.secondary">
                    Final AC
                  </Typography>
                  <Typography variant="h4" color="primary">
                    {totalAC}
                  </Typography>
                  <Divider sx={{ my: 1 }} />
                  <Typography variant="body2" color="text.secondary">
                    Armor Type
                  </Typography>
                  <Typography variant="h6">{formatArmorType(armorType)}</Typography>
                  {!isUnarmored && combinedDex !== undefined && maxDex !== undefined && (
                    <>
                      <Divider sx={{ my: 1 }} />
                      <Typography variant="body2" color="text.secondary">
                        Dexterity Bonus
                      </Typography>
                      <Typography variant="h6">{combinedDex}/{maxDex}</Typography>
                    </>
                  )}
                </Paper>

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
          ) : (
            <Grid container spacing={2}>
              {/* Left column */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Combat Status Overview
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                  {/* Advantage Status */}
                  <Typography variant="body2" color="text.secondary">
                    Advantage Status
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
                    <Chip 
                      size="small" 
                      label={acCalc.outgoing_advantage === AdvantageStatus.ADVANTAGE ? 'Give Advantage' :
                             acCalc.outgoing_advantage === AdvantageStatus.DISADVANTAGE ? 'Give Disadvantage' : 'Normal'}
                      sx={{ 
                        minWidth: '120px',
                        '& .MuiChip-label': { px: 2 },
                        backgroundColor: acCalc.outgoing_advantage === AdvantageStatus.ADVANTAGE ? '#d32f2f !important' : 
                                       acCalc.outgoing_advantage === AdvantageStatus.DISADVANTAGE ? '#2e7d32 !important' : '#757575 !important',
                        color: '#fff !important'
                      }}
                    />
                  </Box>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {acCalc.outgoing_advantage === AdvantageStatus.ADVANTAGE ? 'Attackers have advantage against this target' :
                     acCalc.outgoing_advantage === AdvantageStatus.DISADVANTAGE ? 'Attackers have disadvantage against this target' :
                     'Normal attack rolls against this target'}
                  </Typography>

                  {/* Auto Hit Status */}
                  <Typography variant="body2" color="text.secondary">
                    Auto Hit Status
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                    <Chip 
                      size="small" 
                      label={acCalc.outgoing_auto_hit === AutoHitStatus.AUTOHIT ? 'Auto Hit' :
                             acCalc.outgoing_auto_hit === AutoHitStatus.AUTOMISS ? 'Auto Miss' : 'Normal'}
                      sx={{ 
                        minWidth: '120px',
                        '& .MuiChip-label': { px: 2 },
                        backgroundColor: acCalc.outgoing_auto_hit === AutoHitStatus.AUTOHIT ? '#d32f2f !important' : 
                                       acCalc.outgoing_auto_hit === AutoHitStatus.AUTOMISS ? '#2e7d32 !important' : '#757575 !important',
                        color: '#fff !important'
                      }}
                    />
                  </Box>
                  <Typography variant="body1">
                    {acCalc.outgoing_auto_hit === AutoHitStatus.AUTOHIT ? 'Attacks against this target automatically hit' :
                     acCalc.outgoing_auto_hit === AutoHitStatus.AUTOMISS ? 'Attacks against this target automatically miss' :
                     'Normal hit rules apply'}
                  </Typography>

                  {/* Critical Status */}
                  <Typography variant="body2" color="text.secondary">
                    Critical Status
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                    <Chip 
                      size="small" 
                      label={acCalc.outgoing_critical === CriticalStatus.AUTOCRIT ? 'Always Crit' :
                             acCalc.outgoing_critical === CriticalStatus.NOCRIT ? 'Never Crit' : 'Normal'}
                      sx={{ 
                        minWidth: '120px',
                        '& .MuiChip-label': { px: 2 },
                        backgroundColor: acCalc.outgoing_critical === CriticalStatus.AUTOCRIT ? '#d32f2f !important' : 
                                       acCalc.outgoing_critical === CriticalStatus.NOCRIT ? '#2e7d32 !important' : '#757575 !important',
                        color: '#fff !important'
                      }}
                    />
                  </Box>
                  <Typography variant="body1">
                    {acCalc.outgoing_critical === CriticalStatus.AUTOCRIT ? 'Attacks against this target are always critical hits' :
                     acCalc.outgoing_critical === CriticalStatus.NOCRIT ? 'Attacks against this target can never be critical hits' :
                     'Normal critical hit rules apply'}
                  </Typography>
                </Paper>

                {/* Component Values */}
                <Typography variant="h6" gutterBottom>
                  Component Values
                </Typography>
                <Paper sx={{ p: 2 }} elevation={1}>
                  {/* Advantage Values */}
                  <Typography variant="subtitle2" gutterBottom>Advantage Effects</Typography>
                  {acCalc.total_bonus.channels.map((ch, idx) => (
                    <React.Fragment key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {ch.name}
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {ch.advantage_status}
                        </Typography>
                      </Box>
                      {idx < acCalc.total_bonus.channels.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}

                  {/* Critical Values */}
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>Critical Effects</Typography>
                  {acCalc.total_bonus.channels.map((ch, idx) => (
                    <React.Fragment key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {ch.name}
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {ch.critical_status}
                        </Typography>
                      </Box>
                      {idx < acCalc.total_bonus.channels.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}

                  {/* Auto Hit Values */}
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>Auto Hit Effects</Typography>
                  {acCalc.total_bonus.channels.map((ch, idx) => (
                    <React.Fragment key={idx}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {ch.name}
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {ch.auto_hit_status}
                        </Typography>
                      </Box>
                      {idx < acCalc.total_bonus.channels.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}
                </Paper>
              </Grid>

              {/* Right column */}
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Modifier Breakdown
                </Typography>
                {/* Show appropriate modifiers based on mode */}
                {acCalc.total_bonus.channels.map((ch, idx) => (
                  <Accordion key={idx} defaultExpanded sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography>{ch.name}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <List dense disablePadding>
                        {(detailMode === 'advantage' ? ch.advantage_modifiers :
                          detailMode === 'critical' ? ch.critical_modifiers :
                          detailMode === 'auto_hit' ? ch.auto_hit_modifiers :
                          ch.value_modifiers).map((mod: any, modIdx: number) => (
                          <ListItem
                            key={modIdx}
                            dense
                            divider={modIdx < (detailMode === 'advantage' ? ch.advantage_modifiers.length :
                                              detailMode === 'critical' ? ch.critical_modifiers.length :
                                              detailMode === 'auto_hit' ? ch.auto_hit_modifiers.length :
                                              ch.value_modifiers.length) - 1}
                          >
                            <ListItemText
                              primary={mod.name}
                              secondary={mod.source_entity_name}
                              primaryTypographyProps={{ variant: 'body2' }}
                              secondaryTypographyProps={{ variant: 'caption' }}
                            />
                            <Chip
                              label={mod.value}
                              size="small"
                              color={detailMode === 'advantage' ? 
                                      (mod.value === 'ADVANTAGE' ? 'success' : 
                                       mod.value === 'DISADVANTAGE' ? 'error' : 'default') :
                                    detailMode === 'critical' ?
                                      (mod.value === 'AUTOCRIT' ? 'warning' :
                                       mod.value === 'NOCRIT' ? 'error' : 'default') :
                                    detailMode === 'auto_hit' ?
                                      (mod.value === 'AUTOHIT' ? 'info' :
                                       mod.value === 'AUTOMISS' ? 'error' : 'default') :
                                    (mod.value >= 0 ? 'success' : 'error')}
                            />
                          </ListItem>
                        ))}
                      </List>
                      {ch.advantage_modifiers.length === 0 && detailMode === 'advantage' && (
                        <Typography variant="body2" color="text.secondary">
                          No advantage modifiers
                        </Typography>
                      )}
                      {ch.critical_modifiers.length === 0 && detailMode === 'critical' && (
                        <Typography variant="body2" color="text.secondary">
                          No critical modifiers
                        </Typography>
                      )}
                      {ch.auto_hit_modifiers.length === 0 && detailMode === 'auto_hit' && (
                        <Typography variant="body2" color="text.secondary">
                          No auto-hit modifiers
                        </Typography>
                      )}
                    </AccordionDetails>
                  </Accordion>
                ))}
              </Grid>
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => {
              setDetailMode(detailMode === 'armor' ? 'advantage' : 
                          detailMode === 'advantage' ? 'critical' :
                          detailMode === 'critical' ? 'auto_hit' : 'armor');
            }}
            color="primary"
          >
            Show {detailMode === 'armor' ? 'Advantage' : 
                  detailMode === 'advantage' ? 'Critical' :
                  detailMode === 'critical' ? 'Auto Hit' : 'Armor'} Details
          </Button>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Armor Details Dialog */}
      {equipment.body_armor && (
        <ItemDetailsDialog
          open={itemDetailsOpen === 'armor'}
          onClose={() => setItemDetailsOpen(null)}
          item={equipment.body_armor}
          itemType="armor"
        />
      )}

      {/* Shield Details Dialog */}
      {equipment.weapon_off_hand && (equipment.weapon_off_hand as any).ac_bonus && (
        <ItemDetailsDialog
          open={itemDetailsOpen === 'shield'}
          onClose={() => setItemDetailsOpen(null)}
          item={equipment.weapon_off_hand}
          itemType="shield"
        />
      )}

      {/* Armor Selection Dialog */}
      <Dialog 
        open={armorSelectOpen} 
        onClose={() => !isLoading && setArmorSelectOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Select Armor</DialogTitle>
        <DialogContent>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Box>
          ) : (
            <List>
              {availableArmor.map((armor) => (
                <ListItem 
                  button 
                  key={armor.uuid}
                  onClick={() => handleArmorSelect(armor.uuid)}
                  disabled={isLoading}
                >
                  <ListItemText 
                    primary={armor.name} 
                    secondary={
                      'type' in armor ? 
                        `${formatArmorType(armor.type)} - AC ${armor.ac.normalized_score} (Max Dex ${armor.max_dex_bonus.normalized_score})` : 
                        undefined
                    }
                  />
                </ListItem>
              ))}
              {availableArmor.length === 0 && !isLoading && (
                <ListItem>
                  <ListItemText primary="No armor available" />
                </ListItem>
              )}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setArmorSelectOpen(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ArmorSection; 