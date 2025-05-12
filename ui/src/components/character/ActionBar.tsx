import * as React from 'react';
import {
  Box,
  Paper,
  Select,
  MenuItem,
  Button,
  Typography,
  Grid,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  Snackbar,
  Alert,
} from '@mui/material';
import SwordIcon from '@mui/icons-material/Gavel'; // Using Gavel as a sword icon
import RefreshIcon from '@mui/icons-material/Refresh';
import { useActionBar } from '../../hooks/character/useActionBar';

const ActionBar = React.memo(() => {
  const {
    character,
    targets,
    targetInfo,
    error,
    handleTargetChange,
    handleAttack,
    handleRefreshActionEconomy,
    clearError
  } = useActionBar();

  if (!character) return null;

  return (
    <>
      <Grid container spacing={2} alignItems="center">
        {/* Target Selection */}
        <Grid item xs={12} md={4}>
          <FormControl fullWidth>
            <InputLabel>Select Target</InputLabel>
            <Select
              value={character.target_entity_uuid || ''}
              onChange={(e) => handleTargetChange(e.target.value as string)}
              label="Select Target"
            >
              {targets.map((target) => (
                <MenuItem key={target.uuid} value={target.uuid}>
                  {target.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Target Info */}
        <Grid item xs={12} md={4}>
          {targetInfo && (
            <Box>
              <Typography variant="subtitle2">Target Info:</Typography>
              <Typography variant="body2">
                {targetInfo.name} - HP: {targetInfo.current_hp}/{targetInfo.max_hp}
                {targetInfo.armor_class !== undefined && ` - AC: ${targetInfo.armor_class}`}
              </Typography>
            </Box>
          )}
        </Grid>

        {/* Attack Buttons */}
        <Grid item xs={12} md={3}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={!character.target_entity_uuid ? "Select a target first" : ""}>
              <span>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={() => handleAttack('MAIN_HAND')}
                  disabled={!character.target_entity_uuid}
                  startIcon={<SwordIcon />}
                >
                  Main Hand
                </Button>
              </span>
            </Tooltip>
            <Tooltip title={!character.target_entity_uuid ? "Select a target first" : ""}>
              <span>
                <Button
                  variant="contained"
                  color="secondary"
                  onClick={() => handleAttack('OFF_HAND')}
                  disabled={!character.target_entity_uuid}
                  startIcon={<SwordIcon />}
                >
                  Off Hand
                </Button>
              </span>
            </Tooltip>
          </Box>
        </Grid>

        {/* Action Economy Refresh - Right Aligned */}
        <Grid item xs={12} md={1}>
          <Box display="flex" justifyContent="flex-end">
            <Tooltip title="Refresh Action Economy">
              <IconButton 
                onClick={handleRefreshActionEconomy}
                color="primary"
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Grid>
      </Grid>

      {/* Error Snackbar */}
      <Snackbar 
        open={!!error} 
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
});

ActionBar.displayName = 'ActionBar';

export default ActionBar; 