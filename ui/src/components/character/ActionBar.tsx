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
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import SwordIcon from '@mui/icons-material/Gavel'; // Using Gavel as a sword icon
import RefreshIcon from '@mui/icons-material/Refresh';
import { Character, EntitySummary } from '../../models/character';
import { useEntity } from '../../contexts/EntityContext';
import { refreshActionEconomy } from '../../api/characterApi';
import { executeAttack, setEntityTarget } from '../../api/combatApi';

interface ActionBarProps {
  character: Character;
}

const ActionBar = React.memo<ActionBarProps>(({ character }) => {
  const [loading, setLoading] = React.useState(false);
  const [refreshing, setRefreshing] = React.useState(false);
  const { setEntityData, refreshEntity, summaries } = useEntity();

  // Filter out current character from targets
  const targets = React.useMemo(() => (
    Object.values(summaries).filter(e => e.uuid !== character.uuid)
  ), [summaries, character.uuid]);

  const handleTargetChange = async (targetId: string) => {
    try {
      const updatedCharacter = await setEntityTarget(character.uuid, targetId);
      setEntityData(updatedCharacter);
    } catch (error) {
      console.error('Failed to set target:', error);
      // Refresh entity on error, silently but keep event queue updates
      refreshEntity({ silent: true });
    }
  };

  const handleAttack = async (weaponSlot: 'MAIN_HAND' | 'OFF_HAND') => {
    if (!character.target_entity_uuid) return;
    
    setLoading(true);
    try {
      const result = await executeAttack(character.uuid, character.target_entity_uuid, weaponSlot);
      
      if (result.attacker) {
        // Update character data
        setEntityData(result.attacker);
        
        // Refresh entity data silently but keep event queue updates
        await refreshEntity({ silent: true });
      } else {
        console.error('Attack result did not include attacker data');
        await refreshEntity({ silent: true });
      }
      
    } catch (error) {
      console.error('Failed to execute attack:', error);
      // Refresh entity on error silently but keep event queue updates
      await refreshEntity({ silent: true });
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshActionEconomy = async () => {
    setRefreshing(true);
    try {
      const updatedCharacter = await refreshActionEconomy(character.uuid);
      setEntityData(updatedCharacter);
    } catch (error) {
      console.error('Failed to refresh action economy:', error);
      // Refresh entity on error silently but keep event queue updates
      refreshEntity({ silent: true });
    } finally {
      setRefreshing(false);
    }
  };

  // Find current target info from summaries
  const targetInfo = character.target_entity_uuid ? summaries[character.target_entity_uuid] : null;

  return (
    <Paper elevation={2} sx={{ p: 2, mb: 2 }}>
      <Grid container spacing={2} alignItems="center">
        {/* Target Selection */}
        <Grid item xs={3}>
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
        <Grid item xs={4}>
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

        {/* Action Economy Refresh */}
        <Grid item xs={1}>
          <Tooltip title="Refresh Action Economy">
            <IconButton 
              onClick={handleRefreshActionEconomy}
              disabled={refreshing}
              color="primary"
            >
              {refreshing ? <CircularProgress size={24} /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
        </Grid>

        {/* Attack Buttons */}
        <Grid item xs={4}>
          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              color="primary"
              onClick={() => handleAttack('MAIN_HAND')}
              disabled={loading || !character.target_entity_uuid}
              startIcon={loading ? <CircularProgress size={20} /> : <SwordIcon />}
            >
              Main Hand
            </Button>
            <Button
              variant="contained"
              color="secondary"
              onClick={() => handleAttack('OFF_HAND')}
              disabled={loading || !character.target_entity_uuid}
              startIcon={loading ? <CircularProgress size={20} /> : <SwordIcon />}
            >
              Off Hand
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
});

ActionBar.displayName = 'ActionBar';

export default ActionBar; 