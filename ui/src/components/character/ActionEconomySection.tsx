import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemText,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  IconButton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ReplayIcon from '@mui/icons-material/Replay';
import StarIcon from '@mui/icons-material/Star';
import { ActionEconomySnapshot, ModifiableValueSnapshot, NumericalModifierSnapshot } from '../../models/character';
import { AdvantageStatus } from '../../models/character';

interface ActionEconomySectionProps {
  actionEconomy: ActionEconomySnapshot;
}

// Reusable component for displaying ModifiableValue breakdowns
const ValueBreakdown: React.FC<{ label: string; mv: ModifiableValueSnapshot }> = ({ label, mv }) => {
  const [showAdvantage, setShowAdvantage] = React.useState(false);

  return (
    <Accordion defaultExpanded sx={{ mb: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', justifyContent: 'space-between' }}>
          <Typography>{label}</Typography>
          <IconButton 
            size="small" 
            onClick={(e) => {
              e.stopPropagation();
              setShowAdvantage(!showAdvantage);
            }}
            sx={{ 
              color: showAdvantage ? 'primary.main' : 'text.secondary',
              '&:hover': { color: 'primary.main' }
            }}
          >
            <StarIcon />
          </IconButton>
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        {mv.channels.map((ch, idx) => (
          <Box key={idx} sx={{ mb: 1 }}>
            <Typography variant="body2" fontWeight="bold">
              {ch.name} – Total: {ch.normalized_score}
            </Typography>
            <List dense disablePadding>
              {/* Show value modifiers when not in advantage mode */}
              {!showAdvantage && ch.value_modifiers.map((mod, i) => (
                <ListItem key={i} dense divider={i < ch.value_modifiers.length - 1}>
                  <ListItemText
                    primary={mod.name}
                    secondary={mod.source_entity_name}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                  <Chip 
                    label={mod.value >= 0 ? `+${mod.value}` : mod.value} 
                    size="small" 
                    color={mod.value >= 0 ? 'success' : 'error'} 
                  />
                </ListItem>
              ))}
              {/* Show advantage modifiers when in advantage mode */}
              {showAdvantage && ch.advantage_modifiers.map((mod, i) => (
                <ListItem key={i} dense divider={i < ch.advantage_modifiers.length - 1}>
                  <ListItemText
                    primary={mod.name}
                    secondary={mod.source_entity_name}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                  <Chip 
                    label={mod.value}
                    size="small"
                    color={mod.value === AdvantageStatus.ADVANTAGE ? 'success' : 'error'} 
                  />
                </ListItem>
              ))}
              {showAdvantage && ch.advantage_modifiers.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
                  No advantage modifiers
                </Typography>
              )}
            </List>
          </Box>
        ))}
      </AccordionDetails>
    </Accordion>
  );
};

// Cost Summary component
const CostSummary: React.FC<{ costs: NumericalModifierSnapshot[] }> = ({ costs }) => (
  <List dense>
    {costs.map((cost, idx) => (
      <ListItem key={idx}>
        <ListItemText
          primary={cost.name}
          secondary={cost.source_entity_name}
          primaryTypographyProps={{ variant: 'body2' }}
        />
        <Chip
          label={cost.value}
          size="small"
          color="error"
        />
      </ListItem>
    ))}
  </List>
);

// Helper to calculate total cost
const calculateTotalCost = (costs: NumericalModifierSnapshot[]): number => {
  return costs.reduce((sum, cost) => sum + cost.value, 0);
};

// Movement Block Component
const MovementBlock: React.FC<{ 
  movement: ModifiableValueSnapshot; 
  available: number;
  base: number;
  costs: NumericalModifierSnapshot[];
}> = ({ movement, available, base, costs }) => {
  const [open, setOpen] = React.useState(false);
  const totalCost = calculateTotalCost(costs);

  return (
    <>
      <Paper
        sx={{ 
          p: 2, 
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          minWidth: '200px'
        }}
        elevation={3}
        onClick={() => setOpen(true)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <DirectionsRunIcon sx={{ mr: 1 }} />
          <Box>
            <Typography variant="subtitle2">Movement</Typography>
            <Typography variant="h5">{available}/{base} ft.</Typography>
          </Box>
        </Box>
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Movement Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">Current / Base</Typography>
                <Typography variant="h4">{available}/{base} ft.</Typography>
                {totalCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Cost: {totalCost}
                  </Typography>
                )}
                {costs.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Costs</Typography>
                    <CostSummary costs={costs} />
                  </Box>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={8}>
              <ValueBreakdown label="Movement Modifiers" mv={movement} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Actions Block Component
const ActionsBlock: React.FC<{ 
  actions: ModifiableValueSnapshot;
  bonusActions: ModifiableValueSnapshot;
  availableActions: number;
  availableBonusActions: number;
  baseActions: number;
  baseBonusActions: number;
  actionCosts: NumericalModifierSnapshot[];
  bonusActionCosts: NumericalModifierSnapshot[];
}> = ({ 
  actions, bonusActions, 
  availableActions, availableBonusActions,
  baseActions, baseBonusActions,
  actionCosts, bonusActionCosts
}) => {
  const [open, setOpen] = React.useState(false);
  const totalActionCost = calculateTotalCost(actionCosts);
  const totalBonusActionCost = calculateTotalCost(bonusActionCosts);

  return (
    <>
      <Paper
        sx={{ 
          p: 2, 
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          minWidth: '200px'
        }}
        elevation={3}
        onClick={() => setOpen(true)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
          <PlayArrowIcon sx={{ mr: 1 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
            <Box>
              <Typography variant="subtitle2">Actions</Typography>
              <Typography variant="h5">{availableActions}/{baseActions}</Typography>
            </Box>
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="subtitle2">Bonus Actions</Typography>
              <Typography variant="h5">{availableBonusActions}/{baseBonusActions}</Typography>
            </Box>
          </Box>
        </Box>
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Actions Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">Actions (Current / Base)</Typography>
                <Typography variant="h4">{availableActions}/{baseActions}</Typography>
                {totalActionCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Cost: {totalActionCost}
                  </Typography>
                )}
                {actionCosts.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Costs</Typography>
                    <CostSummary costs={actionCosts} />
                  </Box>
                )}

                <Divider sx={{ my: 2 }} />

                <Typography variant="subtitle2" color="text.secondary">Bonus Actions (Current / Base)</Typography>
                <Typography variant="h4">{availableBonusActions}/{baseBonusActions}</Typography>
                {totalBonusActionCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Cost: {totalBonusActionCost}
                  </Typography>
                )}
                {bonusActionCosts.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Costs</Typography>
                    <CostSummary costs={bonusActionCosts} />
                  </Box>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={8}>
              <ValueBreakdown label="Action Modifiers" mv={actions} />
              <ValueBreakdown label="Bonus Action Modifiers" mv={bonusActions} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Reactions Block Component
const ReactionsBlock: React.FC<{ 
  reactions: ModifiableValueSnapshot; 
  available: number;
  base: number;
  costs: NumericalModifierSnapshot[];
}> = ({ reactions, available, base, costs }) => {
  const [open, setOpen] = React.useState(false);
  const totalCost = calculateTotalCost(costs);

  return (
    <>
      <Paper
        sx={{ 
          p: 2, 
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          minWidth: '200px'
        }}
        elevation={3}
        onClick={() => setOpen(true)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <ReplayIcon sx={{ mr: 1 }} />
          <Box>
            <Typography variant="subtitle2">Reactions</Typography>
            <Typography variant="h5">{available}/{base}</Typography>
          </Box>
        </Box>
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Reactions Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">Current / Base</Typography>
                <Typography variant="h4">{available}/{base}</Typography>
                {totalCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Cost: {totalCost}
                  </Typography>
                )}
                {costs.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Costs</Typography>
                    <CostSummary costs={costs} />
                  </Box>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={8}>
              <ValueBreakdown label="Reaction Modifiers" mv={reactions} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Main Action Economy Section
const ActionEconomySection: React.FC<ActionEconomySectionProps> = ({ actionEconomy }) => {
  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Action Economy
      </Typography>
      <Grid container spacing={2} alignItems="stretch">
        <Grid item xs={12} md={4}>
          <MovementBlock 
            movement={actionEconomy.movement} 
            available={actionEconomy.available_movement}
            base={actionEconomy.base_movement}
            costs={actionEconomy.movement_costs}
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <ActionsBlock 
            actions={actionEconomy.actions}
            bonusActions={actionEconomy.bonus_actions}
            availableActions={actionEconomy.available_actions}
            availableBonusActions={actionEconomy.available_bonus_actions}
            baseActions={actionEconomy.base_actions}
            baseBonusActions={actionEconomy.base_bonus_actions}
            actionCosts={actionEconomy.action_costs}
            bonusActionCosts={actionEconomy.bonus_action_costs}
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <ReactionsBlock 
            reactions={actionEconomy.reactions} 
            available={actionEconomy.available_reactions}
            base={actionEconomy.base_reactions}
            costs={actionEconomy.reaction_costs}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default ActionEconomySection; 