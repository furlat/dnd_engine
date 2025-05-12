import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
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
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import type { 
  ReadonlyModifiableValueSnapshot, 
  ReadonlyHitDiceSnapshot 
} from '../../models/readonly';
import { useHealth } from '../../hooks/character/useHealth';

const format = (v: number) => `${v}`;

const ValueBreakdown: React.FC<{ 
  label: string; 
  mv: ReadonlyModifiableValueSnapshot 
}> = ({ label, mv }) => (
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
  hitDices: ReadonlyArray<ReadonlyHitDiceSnapshot> 
}> = ({ hitDices }) => (
  <Accordion defaultExpanded sx={{ mb: 1 }}>
    <AccordionSummary expandIcon={<ExpandMoreIcon />}>Hit Dice</AccordionSummary>
    <AccordionDetails>
      <List dense>
        {hitDices.map((hd) => (
          <ListItem key={hd.uuid} divider>
            <ListItemText
              primary={`${hd.hit_dice_count.score}d${hd.hit_dice_value.score} (${hd.mode})`}
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
    <Box>
      <Typography variant="h5" gutterBottom>Health</Typography>
      <Paper
        sx={{ p: 2, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        elevation={3}
        onClick={handleOpenDialog}
      >
        <Box sx={{ mr: 2 }}>
          <Typography variant="subtitle1">HP</Typography>
          <Typography variant="h4">{stats.current}/{stats.max}</Typography>
        </Box>
        <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
          {stats.immunities > 0 && <Chip size="small" label={`Imm ${stats.immunities}`} color="success" />}
          {stats.resistances > 0 && <Chip size="small" label={`Res ${stats.resistances}`} color="primary" />}
          {stats.vulnerabilities > 0 && <Chip size="small" label={`Vul ${stats.vulnerabilities}`} color="error" />}
        </Box>
        <Box sx={{ ml: 2, display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 2 }}>
          <Box textAlign="center">
            <Typography variant="subtitle2">Hit Dice</Typography>
            <Typography>{stats.hitDiceString}</Typography>
          </Box>
          <Box textAlign="center">
            <Typography variant="subtitle2">CON</Typography>
            <Typography>{stats.conPerLevel >= 0 ? `+${stats.conPerLevel}` : stats.conPerLevel}</Typography>
          </Box>
          {stats.damageReduction > 0 && (
            <Box textAlign="center">
              <Typography variant="subtitle2">DR</Typography>
              <Typography>{stats.damageReduction}</Typography>
            </Box>
          )}
        </Box>
      </Paper>

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography>Health Details</Typography>
            <Button variant="contained" onClick={handleOpenModifyDialog}>
              Modify HP
            </Button>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="body2">Current HP</Typography>
                <Typography variant="h5">{stats.current}</Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2">Max HP</Typography>
                <Typography variant="h5">{stats.max}</Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2">Temporary HP</Typography>
                <Typography variant="h6">{health.temporary_hit_points.normalized_score}</Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2">Damage Taken</Typography>
                <Typography variant="h6">{health.damage_taken}</Typography>
              </Paper>

              {/* Resistances / Vulnerabilities / Immunities */}
              {health.resistances && health.resistances.length > 0 && (
                <Paper sx={{ p: 2, mt: 2 }}>
                  <Typography variant="h6" gutterBottom>Damage Modifiers</Typography>
                  <Grid container spacing={1}>
                    {['Immunity', 'Resistance', 'Vulnerability'].map((status) => (
                      <Grid item xs={12} key={status}>
                        <Typography variant="subtitle2" color="text.secondary">{status}</Typography>
                        {getResistancesByType(status as any).length === 0 ? (
                          <Typography variant="caption">None</Typography>
                        ) : (
                          <List dense disablePadding>
                            {getResistancesByType(status as any).map((r) => (
                              <ListItem key={r.damage_type}>
                                <ListItemText primary={r.damage_type} />
                              </ListItem>
                            ))}
                          </List>
                        )}
                      </Grid>
                    ))}
                  </Grid>
                </Paper>
              )}
            </Grid>

            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 2, mb: 1 }} elevation={1}>
                <Typography variant="subtitle2">Constitution Bonus</Typography>
                <Typography>
                  {stats.totalDice > 0 
                    ? `${stats.conPerLevel} per level, Total: ${stats.conModifier}` 
                    : stats.conModifier}
                </Typography>
              </Paper>
              <HitDiceList hitDices={health.hit_dices} />
              <ValueBreakdown label="Max HP Bonus" mv={health.max_hit_points_bonus} />
              <ValueBreakdown label="Temporary HP" mv={health.temporary_hit_points} />
              <ValueBreakdown label="Damage Reduction" mv={health.damage_reduction} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Close</Button>
        </DialogActions>
      </Dialog>

      <ModifyHealthDialog
        open={modifyDialogOpen}
        onClose={handleCloseModifyDialog}
        onModify={handleModifyHealth}
        onApplyTemp={handleApplyTempHP}
      />
    </Box>
  );
};

export default React.memo(HealthSection); 