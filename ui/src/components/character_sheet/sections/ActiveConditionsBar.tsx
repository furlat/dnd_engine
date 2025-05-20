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
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useActiveConditions, CONDITIONS_LIST } from '../../../hooks/character_sheet/useActiveConditions';

const ActiveConditionsBar: React.FC = () => {
  const {
    conditions,
    selectedCondition,
    error,
    addDialogOpen,
    handleSelectCondition,
    handleCloseDialog,
    handleRemoveCondition,
    handleAddCondition,
    handleOpenAddDialog,
    handleCloseAddDialog,
    formatDuration
  } = useActiveConditions();

  if (!conditions) return null;

  const activeConditions = Object.entries(conditions);

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
                onClick={() => handleSelectCondition(name)}
                onDelete={(e) => handleRemoveCondition(name, e)}
                color="primary"
                variant="outlined"
                sx={{ cursor: 'pointer' }}
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
            onClick={handleOpenAddDialog}
          >
            <AddIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Add Condition Dialog */}
      <Dialog 
        open={addDialogOpen} 
        onClose={handleCloseAddDialog}
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
            {CONDITIONS_LIST.map(condition => (
              <ListItemButton
                key={condition.type}
                onClick={() => handleAddCondition(condition.type)}
              >
                <ListItemText 
                  primary={condition.name}
                  secondary={condition.description}
                />
              </ListItemButton>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseAddDialog}>Cancel</Button>
        </DialogActions>
      </Dialog>

      {/* Condition Details Dialog */}
      <Dialog
        open={selectedCondition !== null}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        {selectedCondition && conditions[selectedCondition] && (
          <>
            <DialogTitle>{selectedCondition}</DialogTitle>
            <DialogContent>
              <Typography variant="body1" gutterBottom>
                Duration: {formatDuration(
                  conditions[selectedCondition].duration_type,
                  conditions[selectedCondition].duration_value
                )}
              </Typography>
              {conditions[selectedCondition].source_entity_name && (
                <Typography variant="body2" color="text.secondary">
                  Source: {conditions[selectedCondition].source_entity_name}
                </Typography>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={handleCloseDialog}>Close</Button>
              <Button 
                onClick={() => handleRemoveCondition(selectedCondition)}
                color="error"
              >
                Remove
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Paper>
  );
};

export default ActiveConditionsBar; 