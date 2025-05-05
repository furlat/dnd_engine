import * as React from 'react';
import {
  Box,
  Typography,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Paper,
  CircularProgress,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { Character, ConditionType, DurationType } from '../../models/character';
import { removeCondition, addCondition } from '../../api/characterApi';
import { useEntity } from '../../contexts/EntityContext';

interface Props {
  entity: Character;
}

const CONDITIONS_LIST = Object.values(ConditionType).map(type => ({
  type,
  name: type.charAt(0) + type.slice(1).toLowerCase(),
  description: "A condition that affects the character's abilities and actions."  // We could add proper descriptions later
}));

const formatDuration = (type: string, value: number | string | null | undefined): string => {
  switch (type) {
    case 'rounds':
      return `${value} rounds`;
    case 'permanent':
      return 'Permanent';
    case 'until_long_rest':
      return 'Until long rest';
    case 'on_condition':
      return `Until ${value}`;
    default:
      return 'Unknown';
  }
};

const ActiveConditionsBar: React.FC<Props> = ({ entity }) => {
  const { setEntityData } = useEntity();
  const [selectedCondition, setSelectedCondition] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [addDialogOpen, setAddDialogOpen] = React.useState(false);

  const handleClose = () => {
    setSelectedCondition(null);
    setError(null);
  };

  const handleRemoveCondition = async (conditionName: string, event?: React.MouseEvent) => {
    if (event) {
      event.stopPropagation();
    }
    try {
      setIsLoading(true);
      setError(null);
      const updatedEntity = await removeCondition(entity.uuid, conditionName);
      setEntityData(updatedEntity);
      if (selectedCondition === conditionName) {
        setSelectedCondition(null);
      }
    } catch (err: any) {
      console.error('Failed to remove condition:', err);
      setError(err.response?.data?.detail?.message || err.response?.data?.message || 'Failed to remove condition');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddCondition = async (conditionType: ConditionType) => {
    try {
      setIsLoading(true);
      setError(null);
      const updatedEntity = await addCondition(entity.uuid, {
        condition_type: conditionType,
        source_entity_uuid: entity.uuid, // Self-inflicted for now
        duration_type: DurationType.PERMANENT
      });
      setEntityData(updatedEntity);
      setAddDialogOpen(false);
    } catch (err: any) {
      console.error('Failed to add condition:', err);
      setError(err.response?.data?.detail?.message || err.response?.data?.message || 'Failed to add condition');
    } finally {
      setIsLoading(false);
    }
  };

  const activeConditions = Object.entries(entity.active_conditions || {});

  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="subtitle1" sx={{ minWidth: 100 }}>
          Conditions:
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, flexGrow: 1 }}>
          {activeConditions.length > 0 ? (
            activeConditions.map(([name, condition]) => (
              <Chip
                key={condition.uuid}
                label={name}
                onClick={() => setSelectedCondition(name)}
                onDelete={(e) => handleRemoveCondition(name, e)}
                color="primary"
                variant="outlined"
                sx={{ cursor: 'pointer' }}
                disabled={isLoading}
              />
            ))
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
              No active conditions
            </Typography>
          )}
        </Box>
        <Tooltip title="Add condition">
          <IconButton 
            size="small" 
            onClick={() => setAddDialogOpen(true)}
            disabled={isLoading}
          >
            <AddIcon />
          </IconButton>
        </Tooltip>
        {isLoading && (
          <CircularProgress size={20} />
        )}
      </Box>

      {/* Add Condition Dialog */}
      <Dialog
        open={addDialogOpen}
        onClose={() => !isLoading && setAddDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Condition</DialogTitle>
        <DialogContent>
          {error && (
            <Typography color="error" sx={{ mb: 2 }}>
              {error}
            </Typography>
          )}
          <List>
            {CONDITIONS_LIST.map((condition) => (
              <ListItem
                button
                key={condition.type}
                onClick={() => handleAddCondition(condition.type)}
                disabled={isLoading}
              >
                <ListItemText
                  primary={condition.name}
                  secondary={condition.description}
                />
              </ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setAddDialogOpen(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
        </DialogActions>
      </Dialog>

      {/* Condition Details Dialog */}
      {selectedCondition && entity.active_conditions[selectedCondition] && (
        <Dialog open={true} onClose={handleClose} maxWidth="sm" fullWidth>
          <DialogTitle>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="h6">{selectedCondition}</Typography>
              {entity.active_conditions[selectedCondition].uuid && (
                <Typography variant="caption" color="text.secondary">
                  ID: {entity.active_conditions[selectedCondition].uuid}
                </Typography>
              )}
            </Box>
          </DialogTitle>
          <DialogContent dividers>
            {error && (
              <Typography color="error" sx={{ mb: 2 }}>
                {error}
              </Typography>
            )}
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Duration
              </Typography>
              <Typography variant="body1">
                {formatDuration(
                  entity.active_conditions[selectedCondition].duration_type,
                  entity.active_conditions[selectedCondition].duration_value
                )}
              </Typography>
            </Box>
            {entity.active_conditions[selectedCondition].source_entity_name && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">
                  Source
                </Typography>
                <Typography variant="body1">
                  {entity.active_conditions[selectedCondition].source_entity_name}
                </Typography>
              </Box>
            )}
            {entity.active_conditions[selectedCondition].description && (
              <Box>
                <Typography variant="subtitle2" color="text.secondary">
                  Description
                </Typography>
                <Typography variant="body1">
                  {entity.active_conditions[selectedCondition].description}
                </Typography>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button 
              onClick={() => handleRemoveCondition(selectedCondition)}
              color="error"
              disabled={isLoading}
            >
              Remove
            </Button>
            <Button onClick={handleClose}>Close</Button>
          </DialogActions>
        </Dialog>
      )}
    </Paper>
  );
};

export default ActiveConditionsBar; 