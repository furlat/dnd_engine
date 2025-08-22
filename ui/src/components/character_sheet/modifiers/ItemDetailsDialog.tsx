import * as React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Divider,
  Paper,
} from '@mui/material';

interface ItemDetailsProps {
  open: boolean;
  onClose: () => void;
  item: any; // We'll handle type checking in the component
  itemType: 'weapon' | 'armor' | 'shield';
}

const ItemDetailsDialog: React.FC<ItemDetailsProps> = ({ open, onClose, item, itemType }) => {
  if (!item) return null;

  const renderWeaponDetails = () => (
    <>
      <Typography variant="body1" sx={{ mb: 2, fontStyle: 'italic' }}>
        {item.description || 'A finely crafted weapon, ready for battle.'}
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        {item.properties?.map((prop: string, idx: number) => (
          <Chip key={idx} label={prop} size="small" />
        ))}
      </Box>
      <Paper sx={{ p: 2 }} elevation={1}>
        <Typography variant="body2" color="text.secondary">Base Damage</Typography>
        <Typography variant="h6">{item.dice_numbers}d{item.damage_dice} {item.damage_type}</Typography>
        {item.extra_damages?.map((extra: any, idx: number) => (
          <Box key={idx} sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">Extra Damage</Typography>
            <Typography variant="h6">{extra.dice_numbers}d{extra.damage_dice} {extra.damage_type}</Typography>
          </Box>
        ))}
        <Divider sx={{ my: 2 }} />
        <Typography variant="body2" color="text.secondary">Range</Typography>
        <Typography variant="h6">
          {item.range?.type === 'RANGE' 
            ? `${item.range.normal}/${item.range.long} ft.`
            : `${item.range.normal} ft.`}
        </Typography>
      </Paper>
    </>
  );

  const renderArmorDetails = () => (
    <>
      <Typography variant="body1" sx={{ mb: 2, fontStyle: 'italic' }}>
        {item.description || 'A well-crafted piece of armor, offering reliable protection.'}
      </Typography>
      <Paper sx={{ p: 2 }} elevation={1}>
        <Typography variant="body2" color="text.secondary">Base Armor Class</Typography>
        <Typography variant="h6">{item.ac?.base_value || item.ac?.normalized_value}</Typography>
        
        {item.max_dex_bonus && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="body2" color="text.secondary">Maximum Dexterity Bonus</Typography>
            <Typography variant="h6">{item.max_dex_bonus.normalized_value}</Typography>
          </>
        )}

        {item.stealth_disadvantage && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="body2" color="text.secondary">Special</Typography>
            <Chip label="Disadvantage on Stealth" size="small" color="error" />
          </>
        )}
      </Paper>
    </>
  );

  const renderShieldDetails = () => (
    <>
      <Typography variant="body1" sx={{ mb: 2, fontStyle: 'italic' }}>
        {item.description || 'A sturdy shield, providing additional protection in combat.'}
      </Typography>
      <Paper sx={{ p: 2 }} elevation={1}>
        <Typography variant="body2" color="text.secondary">AC Bonus</Typography>
        <Typography variant="h6">+{item.ac_bonus?.normalized_value || item.ac_bonus?.base_value}</Typography>
      </Paper>
    </>
  );

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {item.name}
          <Chip 
            label={itemType.charAt(0).toUpperCase() + itemType.slice(1)} 
            size="small" 
            color={itemType === 'weapon' ? 'error' : itemType === 'shield' ? 'warning' : 'primary'}
          />
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        {itemType === 'weapon' && renderWeaponDetails()}
        {itemType === 'armor' && renderArmorDetails()}
        {itemType === 'shield' && renderShieldDetails()}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default ItemDetailsDialog; 