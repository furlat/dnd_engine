import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  GridLegacy as Grid,
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
  CircularProgress,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ReplayIcon from '@mui/icons-material/Replay';
import StarIcon from '@mui/icons-material/Star';
import RefreshIcon from '@mui/icons-material/Refresh';
import { 
  ModifiableValueSnapshot, 
  NumericalModifierSnapshot, 
  AdvantageStatus 
} from '../../../types/characterSheet_types';
import { useActionEconomy } from '../../../hooks/character_sheet/useActionEconomy';

interface ModifierDisplay {
  name: string;
  value: number | string;
  source_entity_name?: string;
}

// Reusable component for displaying ModifiableValue breakdowns
const ValueBreakdown: React.FC<{ 
  label: string; 
  mv: ModifiableValueSnapshot 
}> = ({ label, mv }) => {
  const [showAdvantage, setShowAdvantage] = React.useState(false);

  // Extract modifiers from the ModifiableValueSnapshot
  const valueModifiers: ModifierDisplay[] = mv.modifiers.map(mod => ({
    name: mod.name,
    value: mod.value,
    source_entity_name: mod.source_entity_name
  }));

  // There might not be advantage modifiers in the new structure
  // This would need to be adjusted based on actual data structure
  const advantageModifiers: ModifierDisplay[] = [];
  if (mv.advantage) {
    advantageModifiers.push({
      name: 'Advantage Status',
      value: mv.advantage
    });
  }

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
        <Box sx={{ mb: 1 }}>
          <Typography variant="body2" fontWeight="bold">
            {label} – Total: {mv.normalized_value}
          </Typography>
          <List dense disablePadding>
            {/* Show value modifiers when not in advantage mode */}
            {!showAdvantage && valueModifiers.map((mod, i) => (
              <ListItem key={i} dense divider={i < valueModifiers.length - 1}>
                <ListItemText
                  primary={mod.name}
                  secondary={mod.source_entity_name}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
                <Chip 
                  label={typeof mod.value === 'number' ? (mod.value >= 0 ? `+${mod.value}` : mod.value) : mod.value} 
                  size="small" 
                  color={typeof mod.value === 'number' ? (mod.value >= 0 ? 'success' : 'error') : 'default'} 
                />
              </ListItem>
            ))}
            {/* Show advantage modifiers when in advantage mode */}
            {showAdvantage && advantageModifiers.map((mod, i) => (
              <ListItem key={i} dense divider={i < advantageModifiers.length - 1}>
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
            {showAdvantage && advantageModifiers.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
                No advantage modifiers
              </Typography>
            )}
          </List>
        </Box>
      </AccordionDetails>
    </Accordion>
  );
};

// Cost Summary component
const CostSummary: React.FC<{ costs: ReadonlyArray<NumericalModifierSnapshot> }> = ({ costs }) => (
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

// Movement Block Component
const MovementBlock: React.FC = () => {
  const { 
    actionEconomy,
    dialogState,
    handleOpenDialog,
    handleCloseDialog,
    getMovementDetails
  } = useActionEconomy();

  if (!actionEconomy) return null;
  const details = getMovementDetails();
  if (!details) return null;

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
        onClick={() => handleOpenDialog('movement')}
      >
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <DirectionsRunIcon sx={{ mr: 1 }} />
          <Box>
            <Typography variant="subtitle2">Movement</Typography>
            <Typography variant="h5">{details.available}/{details.base} ft.</Typography>
          </Box>
        </Box>
      </Paper>

      <Dialog 
        open={dialogState.movement} 
        onClose={() => handleCloseDialog('movement')} 
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle>Movement Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">Current / Base</Typography>
                <Typography variant="h4">{details.available}/{details.base} ft.</Typography>
                {details.totalCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Cost: {details.totalCost}
                  </Typography>
                )}
                {actionEconomy.movement_costs.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Costs</Typography>
                    <CostSummary costs={actionEconomy.movement_costs} />
                  </Box>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={8}>
              <ValueBreakdown label="Movement Modifiers" mv={actionEconomy.movement} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => handleCloseDialog('movement')}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Actions Block Component
const ActionsBlock: React.FC = () => {
  const { 
    actionEconomy,
    dialogState,
    handleOpenDialog,
    handleCloseDialog,
    getActionsDetails
  } = useActionEconomy();

  if (!actionEconomy) return null;
  const details = getActionsDetails();
  if (!details) return null;

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
        onClick={() => handleOpenDialog('actions')}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
          <PlayArrowIcon sx={{ mr: 1 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
            <Box>
              <Typography variant="subtitle2">Actions</Typography>
              <Typography variant="h5">
                {details.availableActions}/{details.baseActions}
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="subtitle2">Bonus Actions</Typography>
              <Typography variant="h5">
                {details.availableBonusActions}/{details.baseBonusActions}
              </Typography>
            </Box>
          </Box>
        </Box>
      </Paper>

      <Dialog 
        open={dialogState.actions} 
        onClose={() => handleCloseDialog('actions')} 
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle>Actions Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">Actions (Available / Base)</Typography>
                <Typography variant="h4">{details.availableActions}/{details.baseActions}</Typography>
                {details.totalActionCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Action Cost: {details.totalActionCost}
                  </Typography>
                )}
                {actionEconomy.action_costs.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Action Costs</Typography>
                    <CostSummary costs={actionEconomy.action_costs} />
                  </Box>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">Bonus Actions (Available / Base)</Typography>
                <Typography variant="h4">{details.availableBonusActions}/{details.baseBonusActions}</Typography>
                {details.totalBonusActionCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Bonus Action Cost: {details.totalBonusActionCost}
                  </Typography>
                )}
                {actionEconomy.bonus_action_costs.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Bonus Action Costs</Typography>
                    <CostSummary costs={actionEconomy.bonus_action_costs} />
                  </Box>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <ValueBreakdown label="Action Modifiers" mv={actionEconomy.actions} />
            </Grid>
            <Grid item xs={12} md={6}>
              <ValueBreakdown label="Bonus Action Modifiers" mv={actionEconomy.bonus_actions} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => handleCloseDialog('actions')}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Reactions Block Component
const ReactionsBlock: React.FC = () => {
  const { 
    actionEconomy,
    dialogState,
    handleOpenDialog,
    handleCloseDialog,
    getReactionsDetails
  } = useActionEconomy();

  if (!actionEconomy) return null;
  const details = getReactionsDetails();
  if (!details) return null;

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
        onClick={() => handleOpenDialog('reactions')}
      >
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <ReplayIcon sx={{ mr: 1 }} />
          <Box>
            <Typography variant="subtitle2">Reactions</Typography>
            <Typography variant="h5">{details.available}/{details.base}</Typography>
          </Box>
        </Box>
      </Paper>

      <Dialog 
        open={dialogState.reactions} 
        onClose={() => handleCloseDialog('reactions')} 
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle>Reactions Details</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">Current / Base</Typography>
                <Typography variant="h4">{details.available}/{details.base}</Typography>
                {details.totalCost !== 0 && (
                  <Typography variant="h6" color="error" sx={{ mt: 1 }}>
                    Total Cost: {details.totalCost}
                  </Typography>
                )}
                {actionEconomy.reaction_costs.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">Active Costs</Typography>
                    <CostSummary costs={actionEconomy.reaction_costs} />
                  </Box>
                )}
              </Box>
            </Grid>
            <Grid item xs={12} md={8}>
              <ValueBreakdown label="Reaction Modifiers" mv={actionEconomy.reactions} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => handleCloseDialog('reactions')}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Main Action Economy Section
const ActionEconomySection: React.FC = () => {
  const { 
    actionEconomy, 
    isRefreshing, 
    handleRefreshActionEconomy 
  } = useActionEconomy();

  if (!actionEconomy) return null;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">Action Economy</Typography>
        <IconButton 
          onClick={handleRefreshActionEconomy} 
          disabled={isRefreshing}
          sx={{ ml: 1 }}
        >
          {isRefreshing ? <CircularProgress size={24} /> : <RefreshIcon />}
        </IconButton>
      </Box>
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <MovementBlock />
        </Grid>
        <Grid item xs={12} md={4}>
          <ActionsBlock />
        </Grid>
        <Grid item xs={12} md={4}>
          <ReactionsBlock />
        </Grid>
      </Grid>
    </Box>
  );
};

export default React.memo(ActionEconomySection); 