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
  ListItemButton,
  ListItemText,
  GridLegacy as Grid,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  Alert,
  Snackbar,
  CircularProgress,
  Tooltip
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { 
  AdvantageStatus, 
  ModifiableValueSnapshot,
  AdvantageModifier,
  ModifierDisplay
} from '../../../types/characterSheet_types';
import ItemDetailsDialog from '../modifiers/ItemDetailsDialog';
import { useArmor } from '../../../hooks/character_sheet/useArmor';

// Format helper function
const format = (value: number | AdvantageStatus | undefined): string => {
  if (typeof value === 'number') {
    return value >= 0 ? `+${value}` : `${value}`;
  }
  return value?.toString() ?? '';
};

interface Channel {
  name: string;
  normalized_value: number;
  advantage_status?: string;
  value_modifiers: ModifierDisplay[];
  advantage_modifiers: AdvantageModifier[];
}

interface ChannelBreakdownProps {
  mv: ModifiableValueSnapshot;
  label: string;
  showAdvantage?: boolean;
}

const ChannelBreakdown: React.FC<ChannelBreakdownProps> = ({ mv, label, showAdvantage = false }) => {
  if (!mv || !(mv as any).channels) return null;

  return (
    <Accordion defaultExpanded sx={{ mb: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>{label}</AccordionSummary>
      <AccordionDetails>
        {(mv as any).channels.map((ch: Channel, idx: number) => (
          <Box key={idx} sx={{ mb: 1 }}>
            <Typography variant="body2" fontWeight="bold">
              {ch.name} – Total: {showAdvantage ? ch.advantage_status : format(ch.normalized_value)}
            </Typography>
            <List dense disablePadding>
              {(showAdvantage ? ch.advantage_modifiers : ch.value_modifiers).map((mod: ModifierDisplay | AdvantageModifier, i: number) => (
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
                    label={showAdvantage ? String(mod.value) : format(mod.value as number)}
                    size="small"
                    color={showAdvantage 
                      ? ((mod.value as AdvantageStatus) === AdvantageStatus.ADVANTAGE ? 'success' : 
                         (mod.value as AdvantageStatus) === AdvantageStatus.DISADVANTAGE ? 'error' : 'default')
                      : (typeof mod.value === 'number' ? (mod.value >= 0 ? 'success' : 'error') : 'default')
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

const ArmorSection: React.FC = () => {
  const {
    acCalculation: acCalc,
    equipment,
    detailMode,
    dialogOpen,
    itemDetailsOpen,
    armorSelectOpen,
    availableArmor,
    error,
    menuAnchor,
    totalAC,
    isUnarmored,
    combinedDex,
    maxDex,
    bodyArmorName,
    armorType,
    shieldName,
    handleOpenDialog,
    handleCloseDialog,
    handleDetailModeChange,
    handleItemDetailsOpen,
    handleArmorSelectOpen,
    handleArmorSelectClose,
    handleArmorSelect,
    handleUnequipArmor,
    handleMenuClick,
    handleMenuClose,
    clearError,
    getLeftValues,
    getBreakdownItems
  } = useArmor();

  if (!acCalc || !equipment) return null;

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

  // Get the arrays for display
  const leftValues = getLeftValues();
  const breakdownItems = getBreakdownItems();

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Armor
      </Typography>
      
      {/* Main Armor Display */}
      <Paper
        sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}
        elevation={3}
        onClick={handleOpenDialog}
      >
        <Typography variant="h4" color="primary">
          {totalAC}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', flexGrow: 1 }}>
          <Chip 
            label={formatArmorType(armorType)} 
            size="small" 
            color={getArmorTypeColor()}
          />
          <Chip 
            label={bodyArmorName} 
            size="small" 
            variant="outlined"
            onClick={(e) => {
              e.stopPropagation();
              if (equipment.body_armor) handleItemDetailsOpen('armor');
            }}
            sx={{ cursor: equipment.body_armor ? 'pointer' : 'default' }}
          />
          {shieldName && (
            <Chip 
              label={shieldName} 
              size="small" 
              variant="outlined"
              color="secondary"
              onClick={(e) => {
                e.stopPropagation();
                handleItemDetailsOpen('shield');
              }}
              sx={{ cursor: 'pointer' }}
            />
          )}
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip 
              label={acCalc.outgoing_advantage === AdvantageStatus.ADVANTAGE ? 'Give Advantage' : 
                     acCalc.outgoing_advantage === AdvantageStatus.DISADVANTAGE ? 'Give Disadvantage' : 'Normal'}
              size="small"
              sx={{ 
                height: '24px',
                '& .MuiChip-label': { 
                  px: 1,
                  fontSize: '0.75rem',
                  whiteSpace: 'nowrap'
                },
                backgroundColor: acCalc.outgoing_advantage === AdvantageStatus.ADVANTAGE ? '#d32f2f !important' : 
                                acCalc.outgoing_advantage === AdvantageStatus.DISADVANTAGE ? '#2e7d32 !important' : '#757575 !important',
                color: '#fff !important'
              }}
              onClick={(e) => {
                e.stopPropagation();
                handleDetailModeChange('advantage');
                handleOpenDialog();
              }}
            />
          </Box>
        </Box>

        <Box onClick={(e) => e.stopPropagation()}>
          <IconButton size="small" onClick={handleMenuClick}>
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
          handleArmorSelectOpen();
          }}>
            <ListItemIcon>
              <SwapHorizIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Change Armor</ListItemText>
          </MenuItem>
          <MenuItem 
          onClick={handleUnequipArmor}
            disabled={!equipment.body_armor}
          >
            <ListItemIcon>
              <DeleteIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Unequip</ListItemText>
          </MenuItem>
        </Menu>

      {/* AC Details Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {detailMode === 'armor' ? 'Armor Class Details' : 
           detailMode === 'advantage' ? 'Outgoing Advantage Status' :
           detailMode === 'critical' ? 'Outgoing Critical Status' :
           'Outgoing Auto Hit Status'}
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            {/* Left column */}
            <Grid item container xs={12} md={6}>
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
                        {format(mv.normalized_value)}
                      </Typography>
                    </Box>
                    {idx < leftValues.length - 1 && <Divider sx={{ my: 1 }} />}
                  </React.Fragment>
                ))}
              </Paper>
            </Grid>

            {/* Right column */}
            <Grid item container xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Modifier Breakdown
              </Typography>
              {breakdownItems.map(({ label, mv }, idx) => (
                <ChannelBreakdown 
                  key={idx} 
                  mv={mv} 
                  label={label} 
                  showAdvantage={detailMode === 'advantage'} 
                />
              ))}
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => {
              handleDetailModeChange(detailMode === 'armor' ? 'advantage' : 
                          detailMode === 'advantage' ? 'critical' :
                          detailMode === 'critical' ? 'auto_hit' : 'armor');
            }}
            color="primary"
          >
            Show {detailMode === 'armor' ? 'Advantage' : 
                  detailMode === 'advantage' ? 'Critical' :
                  detailMode === 'critical' ? 'Auto Hit' : 'Armor'} Details
          </Button>
          <Button onClick={handleCloseDialog}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Armor Selection Dialog */}
      <Dialog 
        open={armorSelectOpen} 
        onClose={handleArmorSelectClose}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Select Armor</DialogTitle>
        <DialogContent>
          {error && (
            <Typography color="error" sx={{ mb: 2 }}>
              {error}
            </Typography>
          )}
            <List>
              {availableArmor.map((armor) => (
                <ListItemButton 
                  key={armor.uuid}
                  onClick={() => handleArmorSelect(armor.uuid)}
                >
                  <ListItemText 
                    primary={armor.name} 
                    secondary={
                      'type' in armor ? 
                        `${formatArmorType(armor.type)} - AC ${armor.ac.normalized_value} (Max Dex ${armor.max_dex_bonus.normalized_value})` : 
                        undefined
                    }
                  />
                </ListItemButton>
              ))}
              {availableArmor.length === 0 && (
                <ListItem>
                  <ListItemText primary="No armor available" />
                </ListItem>
              )}
            </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleArmorSelectClose}>
            Cancel
          </Button>
        </DialogActions>
      </Dialog>

      {/* Item Details Dialogs */}
      {equipment.body_armor && (
        <ItemDetailsDialog
          open={itemDetailsOpen === 'armor'}
          onClose={() => handleItemDetailsOpen(null)}
          item={equipment.body_armor}
          itemType="armor"
        />
      )}
      {equipment.weapon_off_hand && (equipment.weapon_off_hand as any).ac_bonus && (
        <ItemDetailsDialog
          open={itemDetailsOpen === 'shield'}
          onClose={() => handleItemDetailsOpen(null)}
          item={equipment.weapon_off_hand}
          itemType="shield"
        />
      )}

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
    </Box>
  );
};

export default React.memo(ArmorSection); 