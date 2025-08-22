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
  GridLegacy as Grid,
  Divider,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  List,
  ListItemButton,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  Snackbar,
  ListItem,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { useAttack, WeaponSlot } from '../../../hooks/character_sheet/useAttack';
import { 
  ModifiableValueSnapshot, 
  AdvantageStatus, 
  AutoHitStatus, 
  CriticalStatus,
  ModifierDisplay,
  AdvantageModifier
} from '../../../types/characterSheet_types';
import ItemDetailsDialog from '../modifiers/ItemDetailsDialog';

const format = (value: number | undefined) => (value ?? 0) >= 0 ? `+${value}` : `${value}`;

interface ChannelBreakdownProps {
  mv: ModifiableValueSnapshot;
  label: string;
  showAdvantage?: boolean;
}

const ChannelBreakdown: React.FC<ChannelBreakdownProps> = ({ mv, label, showAdvantage = false }) => {
  if (!mv) return null;
  
  // Extract modifiers from ModifiableValueSnapshot
  const valueModifiers: ModifierDisplay[] = mv.modifiers.map(mod => ({
    name: mod.name,
    value: mod.value,
    source_entity_name: mod.source_entity_name
  }));
  
  // For advantage display
  const advantageModifiers: AdvantageModifier[] = [];
  if (mv.advantage) {
    advantageModifiers.push({
      name: 'Advantage Status',
      value: mv.advantage
    });
  }
  
  return (
    <Accordion defaultExpanded sx={{ mb: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>{label}</AccordionSummary>
      <AccordionDetails>
        <Box sx={{ mb: 1 }}>
          <Typography variant="body2" fontWeight="bold">
            {mv.name} – Total: {showAdvantage ? (mv.advantage || 'NONE') : format(mv.normalized_value)}
          </Typography>
          <List dense disablePadding>
            {showAdvantage 
              ? advantageModifiers.map((mod, i) => (
                <ListItem
                  key={i}
                  dense
                  divider={i < advantageModifiers.length - 1}
                >
                  <ListItemText
                    primary={mod.name}
                    secondary={mod.source_entity_name}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                  <Chip
                    label={String(mod.value)}
                    size="small"
                    color={mod.value === AdvantageStatus.ADVANTAGE ? 'success' : 
                           mod.value === AdvantageStatus.DISADVANTAGE ? 'error' : 'default'}
                  />
                </ListItem>
              ))
              : valueModifiers.map((mod, i) => (
                <ListItem
                  key={i}
                  dense
                  divider={i < valueModifiers.length - 1}
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
              ))
            }
          </List>
          {advantageModifiers.length === 0 && showAdvantage && (
            <Typography variant="body2" color="text.secondary">
              No advantage modifiers
            </Typography>
          )}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
};

interface AttackCardProps {
  slot: WeaponSlot;
}

const AttackCard: React.FC<AttackCardProps> = ({ slot }) => {
  const {
    mainHandCalc,
    offHandCalc,
    equipment,
    dialogOpen,
    detailMode,
    itemDetailsOpen,
    weaponSelectOpen,
    availableWeapons,
    error,
    menuAnchor,
    handleOpenDialog,
    handleCloseDialog,
    handleDetailModeChange,
    handleItemDetailsOpen,
    handleWeaponSelectOpen,
    handleWeaponSelectClose,
    handleWeaponSelect,
    handleUnequipWeapon,
    handleMenuClick,
    handleMenuClose,
    clearError,
    getWeaponName,
    getWeaponDamageExpr,
    getWeaponDamageType,
    getExtraDamageExprs,
    getComponentList,
    getDamageComponents
  } = useAttack();

  const calc = slot === 'MAIN_HAND' ? mainHandCalc : offHandCalc;
  if (!calc || !equipment) return null;

  const weapon = slot === 'MAIN_HAND' ? equipment.weapon_main_hand : equipment.weapon_off_hand;
  const weaponName = getWeaponName(slot);
  const damageExpr = getWeaponDamageExpr(slot);
  const damageType = getWeaponDamageType(slot);
  const extraDamageExprs = getExtraDamageExprs(slot);
  const components = getComponentList(slot);
  const damageComponents = getDamageComponents(slot);

  return (
    <>
      <Paper
        sx={{ p: 1.5, display: 'flex', gap: 1.5, alignItems: 'center', mb: 2.5, minHeight: 90 }}
        elevation={3}
        onClick={(e) => {
          const target = e.target as HTMLElement;
          const isClickableElement = target.closest('.clickable-element') || target.closest('.MuiChip-root');
          if (!isClickableElement) {
            handleDetailModeChange('attack');
            handleOpenDialog();
          }
        }}
      >
        {/* Attack bonus */}
        <Box className="clickable-element" onClick={(e) => { 
          e.stopPropagation(); 
          handleDetailModeChange('attack'); 
          handleOpenDialog(); 
        }}>
          <Typography variant="h4" color="primary">
            {format(calc.final_modifier)}
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
                if (!calc.is_unarmed) handleItemDetailsOpen(true);
              }}
            >
              {weaponName}
            </Typography>
            {/* Combat Status Chips */}
            <Chip 
              size="small" 
              label={calc.total_bonus.advantage === AdvantageStatus.ADVANTAGE ? 'Advantage' :
                     calc.total_bonus.advantage === AdvantageStatus.DISADVANTAGE ? 'Disadvantage' : 'N/A'}
              color={calc.total_bonus.advantage === AdvantageStatus.ADVANTAGE ? 'success' :
                     calc.total_bonus.advantage === AdvantageStatus.DISADVANTAGE ? 'error' : 'default'}
              onClick={(e) => {
                e.stopPropagation();
                handleDetailModeChange('advantage');
                handleOpenDialog();
              }}
            />
            {calc.total_bonus.auto_hit === AutoHitStatus.HIT && (
              <Chip size="small" label="Auto Hit" color="info" />
            )}
            {calc.total_bonus.auto_hit === AutoHitStatus.MISS && (
              <Chip size="small" label="Auto Miss" color="error" />
            )}
            {calc.total_bonus.critical === CriticalStatus.CRITICAL && (
              <Chip size="small" label="Always Crit" color="warning" />
            )}
            {calc.total_bonus.critical === CriticalStatus.NORMAL && (
              <Chip size="small" label="Never Crit" color="error" />
            )}
          </Box>
          <Typography variant="caption" color="text.secondary" display="block">
            {slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'} – {calc.range.type === 'RANGE' ? `${calc.range.normal}/${calc.range.long ?? ''}` : 'Melee'}
          </Typography>
        </Box>

        {/* Damage expressions */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Chip
            className="clickable-element"
            size="small"
            label={`${damageExpr} ${damageType}`}
            onClick={(e) => { 
              e.stopPropagation(); 
              handleDetailModeChange('damage'); 
              handleOpenDialog(); 
            }}
          />
          {extraDamageExprs.map((extra, idx) => (
            <Chip
              key={idx}
              className="clickable-element"
              size="small"
              label={`${extra.expr} ${extra.type}`}
              onClick={(e) => { 
                e.stopPropagation(); 
                handleDetailModeChange('damage'); 
                handleOpenDialog(); 
              }}
              color="secondary"
            />
          ))}
        </Box>
        {calc.is_ranged && <Chip className="clickable-element" size="small" label="Ranged" sx={{ ml: 0.5 }} />}
        {calc.properties.includes('Finesse') && <Chip className="clickable-element" size="small" label="Finesse" sx={{ ml: 0.5 }} />}

        {/* Menu button */}
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
      </Paper>

      {/* Menu */}
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={handleMenuClose}
        onClick={(e) => e.stopPropagation()}
      >
        <MenuItem onClick={() => {
          handleMenuClose();
          handleWeaponSelectOpen();
        }}>
          <ListItemIcon>
            <SwapHorizIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Change Weapon</ListItemText>
        </MenuItem>
        <MenuItem 
          onClick={() => handleUnequipWeapon(slot)}
          disabled={calc.is_unarmed}
        >
          <ListItemIcon>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Unequip</ListItemText>
        </MenuItem>
      </Menu>

      {/* Attack Details Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
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
                    {format(calc.final_modifier)}
                  </Typography>
                  <Divider sx={{ my: 1 }} />
                  <Typography variant="body2" color="text.secondary">
                    Range / Reach
                  </Typography>
                  <Typography variant="h6">{calc.range.type === 'RANGE' ? `${calc.range.normal}/${calc.range.long ?? ''}` : 'Melee'}</Typography>
                  {calc.properties.length > 0 && (
                    <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      {calc.properties.map((p: string) => (
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
                          {format(c.mv.normalized_value)}
                        </Typography>
                      </Box>
                      {idx < components.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}
                </Paper>
              </Grid>

              {/* Right column */}
              <Grid item xs={12} md={6}>
                <ChannelBreakdown mv={calc.total_bonus} label="Total Bonus" showAdvantage={true} />
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
                  <Typography variant="h6">{damageType}</Typography>
                  
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
                          {format(c.mv.normalized_value)}
                        </Typography>
                      </Box>
                      {idx < damageComponents.length - 1 && <Divider sx={{ my: 1 }} />}
                    </React.Fragment>
                  ))}
                </Paper>
              </Grid>

              {/* Right column for Damage breakdown */}
              <Grid item xs={12} md={6}>
                <ChannelBreakdown mv={calc.total_bonus} label="Total Bonus" showAdvantage={true} />
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
                      label={calc.total_bonus.advantage === AdvantageStatus.NONE ? 'Normal' :
                             calc.total_bonus.advantage === AdvantageStatus.ADVANTAGE ? 'Advantage' : 'Disadvantage'}
                      color={calc.total_bonus.advantage === AdvantageStatus.NONE ? 'default' :
                             calc.total_bonus.advantage === AdvantageStatus.ADVANTAGE ? 'success' : 'error'}
                    />
                    {/* Critical Status */}
                    <Chip 
                      size="small" 
                      label={calc.total_bonus.critical === CriticalStatus.NONE ? 'Normal Crit' :
                             calc.total_bonus.critical === CriticalStatus.CRITICAL ? 'Always Crit' : 'Never Crit'}
                      color={calc.total_bonus.critical === CriticalStatus.NONE ? 'default' :
                             calc.total_bonus.critical === CriticalStatus.CRITICAL ? 'warning' : 'error'}
                    />
                    {/* Auto Hit Status */}
                    <Chip 
                      size="small" 
                      label={calc.total_bonus.auto_hit === AutoHitStatus.NONE ? 'Normal Hit' :
                             calc.total_bonus.auto_hit === AutoHitStatus.HIT ? 'Auto Hit' : 'Auto Miss'}
                      color={calc.total_bonus.auto_hit === AutoHitStatus.NONE ? 'default' :
                             calc.total_bonus.auto_hit === AutoHitStatus.HIT ? 'info' : 'error'}
                    />
                  </Box>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {calc.total_bonus.advantage === AdvantageStatus.ADVANTAGE ? 'Roll twice and take the higher result' :
                     calc.total_bonus.advantage === AdvantageStatus.DISADVANTAGE ? 'Roll twice and take the lower result' :
                     'Roll normally'}
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {calc.total_bonus.critical === CriticalStatus.CRITICAL ? 'Attack always results in a critical hit' :
                     calc.total_bonus.critical === CriticalStatus.NORMAL ? 'Attack can never be a critical hit' :
                     'Normal critical hit rules apply'}
                  </Typography>
                  <Typography variant="body1">
                    {calc.total_bonus.auto_hit === AutoHitStatus.HIT ? 'Attack automatically hits the target' :
                     calc.total_bonus.auto_hit === AutoHitStatus.MISS ? 'Attack automatically misses the target' :
                     'Normal hit rules apply'}
                  </Typography>
                </Paper>

                <Typography variant="h6" gutterBottom>
                  Status Effects
                </Typography>
                <Paper sx={{ p: 2 }} elevation={1}>
                  {/* Advantage status */}
                  <Typography variant="subtitle2" gutterBottom>Advantage Status</Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                    <Typography variant="body2" color="text.secondary">Current Status</Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {calc.total_bonus.advantage || 'NONE'}
                    </Typography>
                  </Box>

                  {/* Critical status */}
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>Critical Status</Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                    <Typography variant="body2" color="text.secondary">Current Status</Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {calc.total_bonus.critical || 'NONE'}
                    </Typography>
                  </Box>

                  {/* Auto Hit status */}
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>Auto Hit Status</Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                    <Typography variant="body2" color="text.secondary">Current Status</Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {calc.total_bonus.auto_hit || 'NONE'}
                    </Typography>
                  </Box>
                </Paper>
              </Grid>

              {/* Right column */}
              <Grid item xs={12} md={6}>
                <ChannelBreakdown mv={calc.total_bonus} label="Total Bonus" showAdvantage={true} />
              </Grid>
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Item Details Dialog */}
      {!calc.is_unarmed && weapon && (
        <ItemDetailsDialog
          open={itemDetailsOpen}
          onClose={() => handleItemDetailsOpen(false)}
          item={weapon}
          itemType="weapon"
        />
      )}

      {/* Weapon Selection Dialog */}
      <Dialog 
        open={weaponSelectOpen} 
        onClose={handleWeaponSelectClose}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Select Weapon for {slot === 'MAIN_HAND' ? 'Main Hand' : 'Off Hand'}</DialogTitle>
        <DialogContent>
          {error && (
            <Typography color="error" sx={{ mb: 2 }}>
              {error}
            </Typography>
          )}
          <List>
            {availableWeapons.map((weapon) => (
              <ListItemButton key={weapon.uuid} onClick={() => handleWeaponSelect(weapon.uuid, slot)}>
                <ListItemText 
                  primary={weapon.name} 
                  secondary={
                    'damage_dice' in weapon ? 
                      `${weapon.dice_numbers}d${weapon.damage_dice} ${weapon.damage_type}` : 
                      undefined
                  }
                />
              </ListItemButton>
            ))}
            {availableWeapons.length === 0 && (
              <ListItemButton>
                <ListItemText primary="No weapons available" />
              </ListItemButton>
            )}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleWeaponSelectClose}>
            Cancel
          </Button>
        </DialogActions>
      </Dialog>

      {/* Error Snackbar */}
      <Snackbar 
        open={Boolean(error)} 
        autoHideDuration={6000} 
        onClose={clearError}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={clearError} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>
    </>
  );
};

const AttackSection: React.FC = () => {
  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Attack
      </Typography>
      <AttackCard slot="MAIN_HAND" />
      <AttackCard slot="OFF_HAND" />
    </Box>
  );
};

export default AttackSection; 