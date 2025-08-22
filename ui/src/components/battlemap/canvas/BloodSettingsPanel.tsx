import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Switch,
  Slider,
  FormControlLabel,
  IconButton,
  Divider,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RestoreIcon from '@mui/icons-material/Restore';
import { battlemapStore, battlemapActions } from '../../../store';
import { useSnapshot } from 'valtio';
import { BloodSplatDirection, BloodSplatSettings } from '../../../types/battlemap_types';

interface BloodSettingsPanelProps {
  isLocked: boolean;
}

const BloodSettingsPanel: React.FC<BloodSettingsPanelProps> = ({ isLocked }) => {
  const snap = useSnapshot(battlemapStore);
  const { isBloodSettingsVisible, bloodSplatConfig } = snap.controls;
  const [activeDirection, setActiveDirection] = useState<'towardAttacker' | 'awayFromAttacker'>('awayFromAttacker');

  if (!isBloodSettingsVisible) return null;

  const handleClose = () => {
    battlemapActions.setBloodSettingsVisible(false);
  };

  const handleDirectionChange = (
    event: React.MouseEvent<HTMLElement>,
    newDirection: 'towardAttacker' | 'awayFromAttacker' | null,
  ) => {
    if (newDirection !== null) {
      setActiveDirection(newDirection);
    }
  };

  const handleSettingChange = (key: keyof BloodSplatSettings, value: any) => {
    battlemapActions.updateBloodSplatSettings(activeDirection, { [key]: value });
  };

  const handleDropletsPerStageChange = (stageIndex: number, value: number) => {
    const currentSettings = bloodSplatConfig[activeDirection];
    const newDroplets = [...currentSettings.dropletsPerStage];
    newDroplets[stageIndex] = value;
    battlemapActions.updateBloodSplatSettings(activeDirection, { dropletsPerStage: newDroplets });
  };

  const handleReset = () => {
    battlemapActions.resetBloodSplatConfig();
  };

  const currentSettings = bloodSplatConfig[activeDirection];
  const directionLabel = activeDirection === 'towardAttacker' ? 'Toward Attacker' : 'Away From Attacker';
  const directionIcon = activeDirection === 'towardAttacker' ? '🔴' : '🟢';
  const directionDescription = activeDirection === 'towardAttacker' 
    ? 'Blood that sprays toward the attacker (defensive wounds, blocking)'
    : 'Blood that sprays away from the attacker (impact wounds, main spray)';

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: 60,
        right: 16,
        width: 420,
        maxHeight: '85vh',
        overflow: 'auto',
        backgroundColor: 'rgba(0, 0, 0, 0.95)',
        color: 'white',
        p: 2,
        zIndex: 1000,
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          🩸 Blood Splat Settings
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Reset to defaults">
            <IconButton size="small" onClick={handleReset} sx={{ color: 'white' }}>
              <RestoreIcon />
            </IconButton>
          </Tooltip>
          <IconButton size="small" onClick={handleClose} sx={{ color: 'white' }}>
            <CloseIcon />
          </IconButton>
        </Box>
      </Box>

      {isLocked && (
        <Typography variant="body2" color="warning.main" sx={{ mb: 2 }}>
          ⚠️ Unlock the map to modify blood settings
        </Typography>
      )}

      {/* Direction Selector */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
          Blood Direction
        </Typography>
        <ToggleButtonGroup
          value={activeDirection}
          exclusive
          onChange={handleDirectionChange}
          aria-label="blood direction"
          fullWidth
          sx={{ mb: 1 }}
        >
          <ToggleButton 
            value="awayFromAttacker" 
            aria-label="away from attacker"
            sx={{ 
              color: 'white', 
              '&.Mui-selected': { 
                backgroundColor: 'rgba(76, 175, 80, 0.3)',
                color: 'white'
              }
            }}
          >
            🟢 Away From Attacker
          </ToggleButton>
          <ToggleButton 
            value="towardAttacker" 
            aria-label="toward attacker"
            sx={{ 
              color: 'white',
              '&.Mui-selected': { 
                backgroundColor: 'rgba(244, 67, 54, 0.3)',
                color: 'white'
              }
            }}
          >
            🔴 Toward Attacker
          </ToggleButton>
        </ToggleButtonGroup>
        <Typography variant="caption" sx={{ display: 'block', opacity: 0.8, fontStyle: 'italic' }}>
          {directionDescription}
        </Typography>
      </Box>

      {/* Current Direction Settings */}
      <Box sx={{ 
        border: activeDirection === 'towardAttacker' ? '2px solid rgba(244, 67, 54, 0.5)' : '2px solid rgba(76, 175, 80, 0.5)',
        borderRadius: 2,
        p: 2,
        mb: 2
      }}>
        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          {directionIcon} {directionLabel} Settings
        </Typography>

        {/* Main Enable/Disable */}
        <FormControlLabel
          control={
            <Switch
              checked={currentSettings.enabled}
              onChange={(e) => handleSettingChange('enabled', e.target.checked)}
              disabled={isLocked}
            />
          }
          label={`Enable ${directionLabel} Blood`}
          sx={{ mb: 2 }}
        />

        <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

        {/* Position Controls */}
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
          📍 Position Controls
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mb: 2, opacity: 0.8, fontStyle: 'italic' }}>
          Blood positioning: Up/Down on screen + Toward/Away from attacker axis
        </Typography>

        {/* Simple Up/Down Positioning */}
        <Typography variant="body2" sx={{ mb: 1, fontWeight: 'bold', color: '#2196F3' }}>
          📺 Screen Position
        </Typography>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" gutterBottom>
            Up/Down: {currentSettings.upDownOffset.toFixed(2)}
          </Typography>
          <Slider
            value={currentSettings.upDownOffset}
            onChange={(_, value) => handleSettingChange('upDownOffset', value)}
            min={-1}
            max={1}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ⬆️ Up (+) / Down (-) on screen
          </Typography>
        </Box>

        {/* Attacker-Target Axis */}
        <Typography variant="body2" sx={{ mb: 1, fontWeight: 'bold', color: '#4CAF50' }}>
          🎯 Attacker-Target Axis
        </Typography>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" gutterBottom>
            Forward/Backward: {currentSettings.forwardBackwardOffset.toFixed(2)}
          </Typography>
          <Slider
            value={currentSettings.forwardBackwardOffset}
            onChange={(_, value) => handleSettingChange('forwardBackwardOffset', value)}
            min={-1}
            max={1}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            🔙 Toward Attacker (+) / Away From Attacker (-)
          </Typography>
        </Box>

        <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

        {/* Conditional Offsets */}
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
          🎭 Camera Perspective Adjustments
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mb: 2, opacity: 0.8, fontStyle: 'italic' }}>
          Additional offsets based on whether defender shows front or back to camera
        </Typography>

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
          <Box>
            <Typography variant="body2" gutterBottom sx={{ fontWeight: 'bold', color: 'lightblue' }}>
              👤 Front Facing
            </Typography>
            <Box sx={{ pl: 1 }}>
              <Typography variant="body2" gutterBottom>
                Up/Down: {currentSettings.frontFacingUpDownOffset.toFixed(2)}
              </Typography>
              <Slider
                value={currentSettings.frontFacingUpDownOffset}
                onChange={(_, value) => handleSettingChange('frontFacingUpDownOffset', value)}
                min={-0.5}
                max={0.5}
                step={0.05}
                disabled={isLocked}
                size="small"
              />
              <Typography variant="body2" gutterBottom>
                F/B Offset: {currentSettings.frontFacingForwardBackwardOffset.toFixed(2)}
              </Typography>
              <Slider
                value={currentSettings.frontFacingForwardBackwardOffset}
                onChange={(_, value) => handleSettingChange('frontFacingForwardBackwardOffset', value)}
                min={-0.5}
                max={0.5}
                step={0.05}
                disabled={isLocked}
                size="small"
              />
            </Box>
          </Box>
          <Box>
            <Typography variant="body2" gutterBottom sx={{ fontWeight: 'bold', color: 'lightcoral' }}>
              🔄 Back Facing
            </Typography>
            <Box sx={{ pl: 1 }}>
              <Typography variant="body2" gutterBottom>
                Up/Down: {currentSettings.backFacingUpDownOffset.toFixed(2)}
              </Typography>
              <Slider
                value={currentSettings.backFacingUpDownOffset}
                onChange={(_, value) => handleSettingChange('backFacingUpDownOffset', value)}
                min={-0.5}
                max={0.5}
                step={0.05}
                disabled={isLocked}
                size="small"
              />
              <Typography variant="body2" gutterBottom>
                F/B Offset: {currentSettings.backFacingForwardBackwardOffset.toFixed(2)}
              </Typography>
              <Slider
                value={currentSettings.backFacingForwardBackwardOffset}
                onChange={(_, value) => handleSettingChange('backFacingForwardBackwardOffset', value)}
                min={-0.5}
                max={0.5}
                step={0.05}
                disabled={isLocked}
                size="small"
              />
            </Box>
          </Box>
        </Box>

        <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

        {/* Spray Pattern */}
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
          💥 Spray Pattern
        </Typography>

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
          <Box>
            <Typography variant="body2" gutterBottom>
              Spray Intensity: {currentSettings.sprayIntensity.toFixed(1)}
            </Typography>
            <Slider
              value={currentSettings.sprayIntensity}
              onChange={(_, value) => handleSettingChange('sprayIntensity', value)}
              min={0}
              max={2}
              step={0.1}
              disabled={isLocked}
              size="small"
            />
            <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
              How much blood spreads out
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" gutterBottom>
              Randomness: {currentSettings.sprayRandomness.toFixed(1)}
            </Typography>
            <Slider
              value={currentSettings.sprayRandomness}
              onChange={(_, value) => handleSettingChange('sprayRandomness', value)}
              min={0}
              max={1}
              step={0.1}
              disabled={isLocked}
              size="small"
            />
            <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
              How random the spray is
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" gutterBottom>
              Max Travel: {currentSettings.maxTravelDistance.toFixed(1)}
            </Typography>
            <Slider
              value={currentSettings.maxTravelDistance}
              onChange={(_, value) => handleSettingChange('maxTravelDistance', value)}
              min={0.5}
              max={3.0}
              step={0.1}
              disabled={isLocked}
              size="small"
            />
          </Box>
          <Box>
            <Typography variant="body2" gutterBottom>
              Spread Multiplier: {currentSettings.spreadMultiplier.toFixed(1)}
            </Typography>
            <Slider
              value={currentSettings.spreadMultiplier}
              onChange={(_, value) => handleSettingChange('spreadMultiplier', value)}
              min={1.0}
              max={5.0}
              step={0.1}
              disabled={isLocked}
              size="small"
            />
          </Box>
        </Box>

        {/* Droplets Per Stage */}
        <Typography variant="body2" gutterBottom>
          Droplets Per Stage: [{currentSettings.dropletsPerStage.join(', ')}]
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${currentSettings.dropletsPerStage.length}, 1fr)`, gap: 1, mb: 2 }}>
          {currentSettings.dropletsPerStage.map((count: number, index: number) => (
            <Box key={index} sx={{ textAlign: 'center' }}>
              <Typography variant="caption" sx={{ display: 'block' }}>
                S{index + 1}
              </Typography>
              <Slider
                value={count}
                onChange={(_, value) => handleDropletsPerStageChange(index, value as number)}
                min={0}
                max={10}
                step={1}
                disabled={isLocked}
                size="small"
                orientation="vertical"
                sx={{ height: 60, mx: 'auto' }}
              />
              <Typography variant="caption" sx={{ display: 'block' }}>
                {count}
              </Typography>
            </Box>
          ))}
        </Box>

        <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

        {/* Timing and Visual */}
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
          ⏱️ Timing & Visual
        </Typography>

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
          <Box>
            <Typography variant="body2" gutterBottom>
              Stage Delay: {currentSettings.stageDelayMs}ms
            </Typography>
            <Slider
              value={currentSettings.stageDelayMs}
              onChange={(_, value) => handleSettingChange('stageDelayMs', value)}
              min={10}
              max={200}
              step={10}
              disabled={isLocked}
              size="small"
            />
          </Box>
          <Box>
            <Typography variant="body2" gutterBottom>
              Droplet Delay: {currentSettings.dropletDelayMs}ms
            </Typography>
            <Slider
              value={currentSettings.dropletDelayMs}
              onChange={(_, value) => handleSettingChange('dropletDelayMs', value)}
              min={10}
              max={100}
              step={5}
              disabled={isLocked}
              size="small"
            />
          </Box>
          <Box>
            <Typography variant="body2" gutterBottom>
              Scale: {currentSettings.scale.toFixed(2)}x
            </Typography>
            <Slider
              value={currentSettings.scale}
              onChange={(_, value) => handleSettingChange('scale', value)}
              min={0.5}
              max={3.0}
              step={0.1}
              disabled={isLocked}
              size="small"
            />
          </Box>
          <Box>
            <Typography variant="body2" gutterBottom>
              Alpha: {Math.round(currentSettings.alpha * 100)}%
            </Typography>
            <Slider
              value={currentSettings.alpha}
              onChange={(_, value) => handleSettingChange('alpha', value)}
              min={0.1}
              max={1.0}
              step={0.05}
              disabled={isLocked}
              size="small"
            />
          </Box>
        </Box>
      </Box>

      {/* Summary Info */}
      <Box sx={{ 
        backgroundColor: 'rgba(255,255,255,0.05)', 
        borderRadius: 1, 
        p: 1,
        mt: 2
      }}>
        <Typography variant="caption" sx={{ display: 'block', opacity: 0.8 }}>
          💡 Current: {currentSettings.dropletsPerStage.reduce((sum: number, count: number) => sum + count, 0)} droplets across {currentSettings.stageCount} stages
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', opacity: 0.8 }}>
          🟢 Away: {bloodSplatConfig.awayFromAttacker.enabled ? 'ON' : 'OFF'} | 🔴 Toward: {bloodSplatConfig.towardAttacker.enabled ? 'ON' : 'OFF'}
        </Typography>
      </Box>
    </Paper>
  );
};

export default BloodSettingsPanel; 