import React from 'react';
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
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RestoreIcon from '@mui/icons-material/Restore';
import { battlemapStore, battlemapActions } from '../../../store';
import { useSnapshot } from 'valtio';

interface BloodSettingsPanelProps {
  isLocked: boolean;
}

const BloodSettingsPanel: React.FC<BloodSettingsPanelProps> = ({ isLocked }) => {
  const snap = useSnapshot(battlemapStore);
  const { isBloodSettingsVisible, bloodSettings } = snap.controls;

  if (!isBloodSettingsVisible) return null;

  const handleClose = () => {
    battlemapActions.setBloodSettingsVisible(false);
  };

  const handleSettingChange = (key: keyof typeof bloodSettings, value: any) => {
    battlemapActions.updateBloodSettings({ [key]: value });
  };

  const handleDropletsPerStageChange = (stageIndex: number, value: number) => {
    const newDroplets = [...bloodSettings.dropletsPerStage];
    newDroplets[stageIndex] = value;
    battlemapActions.updateBloodSettings({ dropletsPerStage: newDroplets });
  };

  const handleReset = () => {
    battlemapActions.resetBloodSettings();
  };

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: 60,
        right: 16,
        width: 400,
        maxHeight: '80vh',
        overflow: 'auto',
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        color: 'white',
        p: 2,
        zIndex: 1000,
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          🩸 Blood & Gore Settings
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

      {/* Main Enable/Disable */}
      <FormControlLabel
        control={
          <Switch
            checked={bloodSettings.enabled}
            onChange={(e) => handleSettingChange('enabled', e.target.checked)}
            disabled={isLocked}
          />
        }
        label="Enable Blood Effects"
        sx={{ mb: 2 }}
      />

      <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

      {/* Position Controls */}
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
        📍 Position Controls
      </Typography>
      <Typography variant="caption" sx={{ display: 'block', mb: 2, opacity: 0.8, fontStyle: 'italic' }}>
        Blood positioning relative to target entity center. Uses both absolute world directions and relative positioning based on attacker→target line.
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="body2" gutterBottom>
            Back Distance: {bloodSettings.backDistance.toFixed(2)}
          </Typography>
          <Slider
            value={bloodSettings.backDistance}
            onChange={(_, value) => handleSettingChange('backDistance', value)}
            min={0}
            max={1}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            🔙 Away from attacker
          </Typography>
        </Box>
        <Box>
          <Typography variant="body2" gutterBottom>
            Lateral Offset: {bloodSettings.lateralOffset.toFixed(2)}
          </Typography>
          <Slider
            value={bloodSettings.lateralOffset}
            onChange={(_, value) => handleSettingChange('lateralOffset', value)}
            min={-1}
            max={1}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ↔️ Right of attack line
          </Typography>
        </Box>
        <Box>
          <Typography variant="body2" gutterBottom>
            Height Offset: {bloodSettings.heightOffset.toFixed(2)}
          </Typography>
          <Slider
            value={bloodSettings.heightOffset}
            onChange={(_, value) => handleSettingChange('heightOffset', value)}
            min={-1}
            max={1}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ⬆️ Absolute north
          </Typography>
        </Box>

      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="body2" gutterBottom>
            West Offset: {bloodSettings.westOffset.toFixed(2)}
          </Typography>
          <Slider
            value={bloodSettings.westOffset}
            onChange={(_, value) => handleSettingChange('westOffset', value)}
            min={-0.5}
            max={0.5}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ⬅️ Toward west
          </Typography>
        </Box>
        <Box>
          <Typography variant="body2" gutterBottom>
            East Offset: {bloodSettings.eastOffset.toFixed(2)}
          </Typography>
          <Slider
            value={bloodSettings.eastOffset}
            onChange={(_, value) => handleSettingChange('eastOffset', value)}
            min={-0.5}
            max={0.5}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ➡️ Toward east
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

      {/* Directional Conditional Offsets */}
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
        🎭 Directional Conditional Offsets
      </Typography>
      <Typography variant="caption" sx={{ display: 'block', mb: 2, opacity: 0.8, fontStyle: 'italic' }}>
        Additional offsets based on whether defender shows front or back to camera
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="body2" gutterBottom sx={{ fontWeight: 'bold', color: 'lightblue' }}>
            👤 Front Facing (NE,E,SE,S,SW attackers)
          </Typography>
          <Box sx={{ pl: 1 }}>
            <Typography variant="body2" gutterBottom>
              Height Offset: {bloodSettings.frontFacingHeightOffset.toFixed(2)}
            </Typography>
            <Slider
              value={bloodSettings.frontFacingHeightOffset}
              onChange={(_, value) => handleSettingChange('frontFacingHeightOffset', value)}
              min={-0.5}
              max={0.5}
              step={0.05}
              disabled={isLocked}
              size="small"
            />
            <Typography variant="body2" gutterBottom>
              Back Distance: {bloodSettings.frontFacingBackDistance.toFixed(2)}
            </Typography>
            <Slider
              value={bloodSettings.frontFacingBackDistance}
              onChange={(_, value) => handleSettingChange('frontFacingBackDistance', value)}
              min={-0.5}
              max={1.0}
              step={0.05}
              disabled={isLocked}
              size="small"
            />
          </Box>
        </Box>
        <Box>
          <Typography variant="body2" gutterBottom sx={{ fontWeight: 'bold', color: 'lightcoral' }}>
            🔄 Back Facing (W,NW,N attackers)
          </Typography>
          <Box sx={{ pl: 1 }}>
            <Typography variant="body2" gutterBottom>
              Height Offset: {bloodSettings.backFacingHeightOffset.toFixed(2)}
            </Typography>
            <Slider
              value={bloodSettings.backFacingHeightOffset}
              onChange={(_, value) => handleSettingChange('backFacingHeightOffset', value)}
              min={-0.5}
              max={0.5}
              step={0.05}
              disabled={isLocked}
              size="small"
            />
            <Typography variant="body2" gutterBottom>
              Back Distance: {bloodSettings.backFacingBackDistance.toFixed(2)}
            </Typography>
            <Slider
              value={bloodSettings.backFacingBackDistance}
              onChange={(_, value) => handleSettingChange('backFacingBackDistance', value)}
              min={-0.5}
              max={1.0}
              step={0.05}
              disabled={isLocked}
              size="small"
            />
          </Box>
        </Box>
      </Box>

      <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

      {/* Spray Direction Controls */}
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
        🎯 Spray Direction
      </Typography>
      <Typography variant="caption" sx={{ display: 'block', mb: 2, opacity: 0.8, fontStyle: 'italic' }}>
        Control which directions blood travels (relative to attacker from south)
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="body2" gutterBottom>
            North Spray: {bloodSettings.sprayNorthAmount.toFixed(1)}
          </Typography>
          <Slider
            value={bloodSettings.sprayNorthAmount}
            onChange={(_, value) => handleSettingChange('sprayNorthAmount', value)}
            min={0}
            max={2}
            step={0.1}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ⬆️ Away from attacker
          </Typography>
        </Box>
        <Box>
          <Typography variant="body2" gutterBottom>
            South Spray: {bloodSettings.spraySouthAmount.toFixed(1)}
          </Typography>
          <Slider
            value={bloodSettings.spraySouthAmount}
            onChange={(_, value) => handleSettingChange('spraySouthAmount', value)}
            min={0}
            max={2}
            step={0.1}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ⬇️ Toward attacker
          </Typography>
        </Box>
        <Box>
          <Typography variant="body2" gutterBottom>
            West Spray: {bloodSettings.sprayWestAmount.toFixed(1)}
          </Typography>
          <Slider
            value={bloodSettings.sprayWestAmount}
            onChange={(_, value) => handleSettingChange('sprayWestAmount', value)}
            min={0}
            max={2}
            step={0.1}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ⬅️ Toward west
          </Typography>
        </Box>
        <Box>
          <Typography variant="body2" gutterBottom>
            East Spray: {bloodSettings.sprayEastAmount.toFixed(1)}
          </Typography>
          <Slider
            value={bloodSettings.sprayEastAmount}
            onChange={(_, value) => handleSettingChange('sprayEastAmount', value)}
            min={0}
            max={2}
            step={0.1}
            disabled={isLocked}
            size="small"
          />
          <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem' }}>
            ➡️ Toward east
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

      {/* Spray Pattern Controls */}
      <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 'bold' }}>
        💥 Spray Pattern
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="body2" gutterBottom>
            Max Travel Distance: {bloodSettings.maxTravelDistance.toFixed(1)}
          </Typography>
          <Slider
            value={bloodSettings.maxTravelDistance}
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
            Spread Multiplier: {bloodSettings.spreadMultiplier.toFixed(1)}
          </Typography>
          <Slider
            value={bloodSettings.spreadMultiplier}
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
        Droplets Per Stage: [{bloodSettings.dropletsPerStage.join(', ')}]
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 1, mb: 2 }}>
        {bloodSettings.dropletsPerStage.map((count, index) => (
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

      {/* Timing Controls */}
      <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 'bold' }}>
        ⏱️ Timing
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="body2" gutterBottom>
            Stage Delay: {bloodSettings.stageDelayMs}ms
          </Typography>
          <Slider
            value={bloodSettings.stageDelayMs}
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
            Droplet Delay: {bloodSettings.dropletDelayMs}ms
          </Typography>
          <Slider
            value={bloodSettings.dropletDelayMs}
            onChange={(_, value) => handleSettingChange('dropletDelayMs', value)}
            min={10}
            max={100}
            step={5}
            disabled={isLocked}
            size="small"
          />
        </Box>
      </Box>

      <Divider sx={{ my: 2, bgcolor: 'rgba(255,255,255,0.2)' }} />

      {/* Visual Controls */}
      <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 'bold' }}>
        🎨 Visual
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="body2" gutterBottom>
            Scale: {bloodSettings.scale.toFixed(2)}x
          </Typography>
          <Slider
            value={bloodSettings.scale}
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
            Alpha: {Math.round(bloodSettings.alpha * 100)}%
          </Typography>
          <Slider
            value={bloodSettings.alpha}
            onChange={(_, value) => handleSettingChange('alpha', value)}
            min={0.1}
            max={1.0}
            step={0.05}
            disabled={isLocked}
            size="small"
          />
        </Box>
      </Box>

      {/* Info */}
      <Typography variant="caption" sx={{ display: 'block', mt: 2, opacity: 0.7 }}>
        💡 Total droplets: {bloodSettings.dropletsPerStage.reduce((sum, count) => sum + count, 0)} across {bloodSettings.stageCount} stages
      </Typography>
    </Paper>
  );
};

export default BloodSettingsPanel; 