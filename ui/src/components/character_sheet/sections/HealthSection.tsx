import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  GridLegacy as Grid,
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
  TextField,
  IconButton,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import type { 
  ModifiableValueSnapshot, 
  HitDiceSnapshot 
} from '../../../types/characterSheet_types';
import { useHealth } from '../../../hooks/character_sheet/useHealth';

const format = (v: number) => `${v}`;

const ValueBreakdown: React.FC<{ 
  label: string; 
  mv: ModifiableValueSnapshot 
}> = ({ label, mv }) => (
  <Accordion defaultExpanded sx={{ mb: 1 }}>
    <AccordionSummary expandIcon={<ExpandMoreIcon />}>{label}</AccordionSummary>
    <AccordionDetails>
      {(mv as any).channels?.map((ch: any, idx: number) => (
        <Box key={idx} sx={{ mb: 1 }}>
          <Typography variant="body2" fontWeight="bold">
            {ch.name} – Total: {format(ch.normalized_value)}
          </Typography>
          <List dense disablePadding>
            {ch.value_modifiers.map((mod: any, i: number) => (
              <ListItem key={i} dense divider={i < ch.value_modifiers.length - 1}>
                <ListItemText
                  primary={mod.name}
                  secondary={mod.source_entity_name}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
                <Chip label={format(mod.value)} size="small" color={mod.value >= 0 ? 'success' : 'error'} />
              </ListItem>
            ))}
          </List>
        </Box>
      ))}
    </AccordionDetails>
  </Accordion>
);

const HitDiceList: React.FC<{ 
  hitDices: ReadonlyArray<HitDiceSnapshot> 
}> = ({ hitDices }) => (
  <Accordion defaultExpanded sx={{ mb: 1 }}>
    <AccordionSummary expandIcon={<ExpandMoreIcon />}>Hit Dice</AccordionSummary>
    <AccordionDetails>
      <List dense>
        {hitDices.map((hd) => (
          <ListItem key={hd.uuid} divider>
            <ListItemText
              primary={`${hd.hit_dice_count.final_value}d${hd.hit_dice_value.final_value} (${hd.mode})`}
              secondary={`HP: ${hd.hit_points}`}
            />
          </ListItem>
        ))}
      </List>
    </AccordionDetails>
  </Accordion>
);

const ModifyHealthDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  onModify: (amount: number) => Promise<void>;
  onApplyTemp: (amount: number) => Promise<void>;
}> = ({ open, onClose, onModify, onApplyTemp }) => {
  const [amount, setAmount] = React.useState(0);
  const [tempAmount, setTempAmount] = React.useState(0);

  const handleModify = React.useCallback(() => {
    onModify(amount);
    setAmount(0);
  }, [amount, onModify]);

  const handleApplyTemp = React.useCallback(() => {
    onApplyTemp(tempAmount);
    setTempAmount(0);
  }, [tempAmount, onApplyTemp]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Modify Health</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>Modify Current HP</Typography>
          <Grid container spacing={1} alignItems="center">
            <Grid item>
              <IconButton size="small" onClick={() => setAmount(prev => prev - 1)}>
                <RemoveIcon />
              </IconButton>
            </Grid>
            <Grid item xs>
              <TextField
                fullWidth
                type="number"
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                size="small"
              />
            </Grid>
            <Grid item>
              <IconButton size="small" onClick={() => setAmount(prev => prev + 1)}>
                <AddIcon />
              </IconButton>
            </Grid>
          </Grid>
          <Button 
            fullWidth 
            variant="contained" 
            onClick={handleModify} 
            sx={{ mt: 1 }}
            color={amount >= 0 ? "primary" : "error"}
          >
            {amount >= 0 ? "Heal" : "Damage"}
          </Button>
        </Box>
        <Divider />
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" gutterBottom>Apply Temporary HP</Typography>
          <Grid container spacing={1} alignItems="center">
            <Grid item>
              <IconButton size="small" onClick={() => setTempAmount(prev => Math.max(0, prev - 1))}>
                <RemoveIcon />
              </IconButton>
            </Grid>
            <Grid item xs>
              <TextField
                fullWidth
                type="number"
                value={tempAmount}
                onChange={(e) => setTempAmount(Math.max(0, Number(e.target.value)))}
                size="small"
              />
            </Grid>
            <Grid item>
              <IconButton size="small" onClick={() => setTempAmount(prev => prev + 1)}>
                <AddIcon />
              </IconButton>
            </Grid>
          </Grid>
          <Button 
            fullWidth 
            variant="contained" 
            onClick={handleApplyTemp} 
            sx={{ mt: 1 }}
          >
            Apply Temp HP
          </Button>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

const HealthSection: React.FC = () => {
  const { 
    health, 
    stats,
    dialogOpen, 
    modifyDialogOpen,
    handleOpenDialog, 
    handleCloseDialog,
    handleOpenModifyDialog,
    handleCloseModifyDialog,
    handleModifyHealth,
    handleApplyTempHP,
    getResistancesByType
  } = useHealth();

  if (!health || !stats) return null;

  return (
    <>
      {/* Main health display */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={1} alignItems="center">
          {/* Current/Max HP */}
          <Grid item xs={12} sm={4}>
            <Typography variant="h6" gutterBottom align="center">HP</Typography>
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'baseline' }}>
              <Typography variant="h3" component="span">
                {stats.current}
              </Typography>
              <Typography variant="h5" component="span" sx={{ ml: 1 }}>
                / {stats.max}
              </Typography>
            </Box>
            {health.temporary_hit_points.final_value > 0 && (
              <Typography align="center" variant="body2" color="primary">
                +{health.temporary_hit_points.final_value} temporary
              </Typography>
            )}
          </Grid>

          {/* Hit dice */}
          <Grid item xs={8} sm={4}>
            <Typography variant="h6" gutterBottom align="center">
              Hit Dice
            </Typography>
            <Typography variant="body1" align="center">
              {stats.hitDiceString}
            </Typography>
            <Typography variant="caption" display="block" align="center">
              (Con per level: {format(stats.conPerLevel)})
            </Typography>
          </Grid>

          {/* Damage reduction */}
          <Grid item xs={4} sm={4}>
            <Typography variant="h6" gutterBottom align="center">
              Reduction
            </Typography>
            <Typography variant="h4" align="center">
              {stats.damageReduction}
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', justifyContent: 'center', mt: 1 }}>
              {stats.immunities > 0 && (
                <Chip 
                  label={`${stats.immunities} Immunities`} 
                  color="info" 
                  size="small" 
                  onClick={handleOpenDialog}
                />
              )}
              {stats.resistances > 0 && (
                <Chip 
                  label={`${stats.resistances} Resistances`} 
                  color="success" 
                  size="small" 
                  onClick={handleOpenDialog}
                />
              )}
              {stats.vulnerabilities > 0 && (
                <Chip 
                  label={`${stats.vulnerabilities} Vulnerabilities`} 
                  color="error" 
                  size="small" 
                  onClick={handleOpenDialog}
                />
              )}
              <Chip 
                label="Modify HP" 
                color="primary" 
                size="small" 
                onClick={handleOpenModifyDialog}
              />
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Detailed dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>Health Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            {/* Left column */}
            <Grid item xs={12} md={6}>
              {/* Resistances */}
              {['Immunity', 'Resistance', 'Vulnerability'].map(status => {
                const resistances = getResistancesByType(status as any);
                if (resistances.length === 0) return null;
                return (
                  <Box key={status} sx={{ mb: 2 }}>
                    <Typography variant="h6">{status}:</Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                      {resistances.map((r, idx) => (
                        <Chip 
                          key={idx} 
                          label={r.damage_type} 
                          size="small" 
                          color={
                            status === 'Immunity' ? 'info' : 
                            status === 'Resistance' ? 'success' : 'error'
                          }
                        />
                      ))}
                    </Box>
                  </Box>
                );
              })}

              {/* Damage Reduction */}
              <ValueBreakdown label="Damage Reduction" mv={health.damage_reduction} />
            </Grid>

            {/* Right column */}
            <Grid item xs={12} md={6}>
              {/* Temporary HP */}
              <ValueBreakdown label="Temporary HP" mv={health.temporary_hit_points} />
              
              {/* HP Bonus */}
              <ValueBreakdown label="Max HP Bonus" mv={health.max_hit_points_bonus} />

              {/* Hit Dice */}
              <HitDiceList hitDices={health.hit_dices} />
            </Grid>

            {/* Debug JSON */}
            <Grid item xs={12}>
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  Debug Raw Data
                </AccordionSummary>
                <AccordionDetails>
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.75rem' }}>
                    {JSON.stringify(health, null, 2)}
                  </pre>
                </AccordionDetails>
              </Accordion>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Modify HP Dialog */}
      <ModifyHealthDialog 
        open={modifyDialogOpen}
        onClose={handleCloseModifyDialog}
        onModify={handleModifyHealth}
        onApplyTemp={handleApplyTempHP}
      />
    </>
  );
};

export default HealthSection; 