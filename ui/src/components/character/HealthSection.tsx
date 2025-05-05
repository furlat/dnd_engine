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
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { HealthSnapshot, HitDiceSnapshot, ModifiableValueSnapshot } from '../../models/character';

interface Props {
  health: HealthSnapshot;
}

const format = (v: number) => `${v}`;

const ValueBreakdown: React.FC<{ label: string; mv: ModifiableValueSnapshot }> = ({ label, mv }) => (
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

const HitDiceList: React.FC<{ hitDices: HitDiceSnapshot[] }> = ({ hitDices }) => (
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

const HealthSection: React.FC<Props> = ({ health }) => {
  const current = health.current_hit_points ?? 0;
  const max = health.max_hit_points ?? health.hit_dices_total_hit_points + health.max_hit_points_bonus.normalized_score;

  const conMod = health.max_hit_points ? max - health.hit_dices_total_hit_points - health.max_hit_points_bonus.normalized_score : 0;

  const totalDice = health.total_hit_dices_number;
  const conPerLevel = totalDice > 0 ? conMod / totalDice : 0;

  const hitDiceStr = React.useMemo(() => {
    const groups: Record<string, number> = {};
    health.hit_dices.forEach((hd:any)=>{
      const sides = hd.hit_dice_value.score;
      groups[sides] = (groups[sides]||0)+ hd.hit_dice_count.score;
    });
    return Object.entries(groups)
      .sort((a,b)=>Number(a[0])-Number(b[0]))
      .map(([sides, cnt])=>`${cnt}d${sides}`)
      .join(' + ');
  }, [health]);

  const [open, setOpen] = React.useState(false);

  const imm = health.resistances.filter((r:any)=>r.status==='Immunity').length;
  const res = health.resistances.filter((r:any)=>r.status==='Resistance').length;
  const vul = health.resistances.filter((r:any)=>r.status==='Vulnerability').length;
  const dr = health.damage_reduction.normalized_score;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Health</Typography>
      <Paper
        sx={{ p: 2, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        elevation={3}
        onClick={() => setOpen(true)}
      >
        <Box sx={{ mr:2 }}>
          <Typography variant="subtitle1">HP</Typography>
          <Typography variant="h4">{current}/{max}</Typography>
        </Box>
        <Box sx={{ flexGrow:1, display:'flex', alignItems:'center', gap:0.5, flexWrap:'wrap' }}>
          {imm>0 && <Chip size="small" label={`Imm ${imm}`} color="success" />}
          {res>0 && <Chip size="small" label={`Res ${res}`} color="primary" />}
          {vul>0 && <Chip size="small" label={`Vul ${vul}`} color="error" />}
        </Box>
        <Box sx={{ ml: 2, display:'flex', flexDirection:'row', alignItems:'center', gap:2 }}>
          <Box textAlign="center">
            <Typography variant="subtitle2">Hit Dice</Typography>
            <Typography>{hitDiceStr}</Typography>
          </Box>
          <Box textAlign="center">
            <Typography variant="subtitle2">CON</Typography>
            <Typography>{conPerLevel >= 0 ? `+${conPerLevel}` : conPerLevel}</Typography>
          </Box>
          {dr>0 && (
            <Box textAlign="center">
              <Typography variant="subtitle2">DR</Typography>
              <Typography>{dr}</Typography>
            </Box>
          )}
        </Box>
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Health Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p:2 }}>
                <Typography variant="body2">Current HP</Typography>
                <Typography variant="h5">{current}</Typography>
                <Divider sx={{ my:1 }}/>
                <Typography variant="body2">Max HP</Typography>
                <Typography variant="h5">{max}</Typography>
                <Divider sx={{ my:1 }}/>
                <Typography variant="body2">Temporary HP</Typography>
                <Typography variant="h6">{health.temporary_hit_points.normalized_score}</Typography>
                <Divider sx={{ my:1 }}/>
                <Typography variant="body2">Damage Taken</Typography>
                <Typography variant="h6">{health.damage_taken}</Typography>
              </Paper>

              {/* Resistances / Vulnerabilities / Immunities - Moved here */}
              {health.resistances && health.resistances.length > 0 && (
                <Paper sx={{ p: 2, mt: 2 }}>
                  <Typography variant="h6" gutterBottom>Damage Modifiers</Typography>
                  <Grid container spacing={1}>
                    {['Immunity', 'Resistance', 'Vulnerability'].map((status) => (
                      <Grid item xs={12} key={status}>
                        <Typography variant="subtitle2" color="text.secondary">{status}</Typography>
                        {health.resistances.filter((r: any) => r.status === status).length === 0 ? (
                          <Typography variant="caption">None</Typography>
                        ) : (
                          <List dense disablePadding>
                            {health.resistances.filter((r: any) => r.status === status).map((r: any) => (
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
                <Typography>{health.total_hit_dices_number > 0 ? `${conMod / health.total_hit_dices_number} per level, Total: ${conMod}` : conMod}</Typography>
              </Paper>
              <HitDiceList hitDices={health.hit_dices} />
              <ValueBreakdown label="Max HP Bonus" mv={health.max_hit_points_bonus} />
              <ValueBreakdown label="Temporary HP" mv={health.temporary_hit_points} />
              <ValueBreakdown label="Damage Reduction" mv={health.damage_reduction} />
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

export default HealthSection; 