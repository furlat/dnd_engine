import * as React from 'react';
import {
  Box,
  Typography,
  Slider,
  Stack,
  Switch,
  FormControlLabel,
  Paper,
  IconButton,
  Divider,
} from '@mui/material';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import VolumeDownIcon from '@mui/icons-material/VolumeDown';
import VolumeMuteIcon from '@mui/icons-material/VolumeMute';
import MusicNoteIcon from '@mui/icons-material/MusicNote';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import CloseIcon from '@mui/icons-material/Close';
import { useSoundSettings } from '../../hooks/useSoundSettings';

interface SoundSettingsPanelProps {
  onClose?: () => void;
}

const SoundSettingsPanel: React.FC<SoundSettingsPanelProps> = ({ onClose }) => {
  const { settings, updateSettings, getEffectiveVolume } = useSoundSettings();

  const handleMasterVolumeChange = (_event: Event, newValue: number | number[]) => {
    updateSettings({ masterVolume: newValue as number });
  };

  const handleEffectsVolumeChange = (_event: Event, newValue: number | number[]) => {
    updateSettings({ effectsVolume: newValue as number });
  };

  const handleMusicVolumeChange = (_event: Event, newValue: number | number[]) => {
    updateSettings({ musicVolume: newValue as number });
  };

  const toggleSfxEnabled = () => {
    updateSettings({ sfxEnabled: !settings.sfxEnabled });
  };

  const toggleMusicEnabled = () => {
    updateSettings({ musicEnabled: !settings.musicEnabled });
  };

  // Helper to show volume icon based on level
  const getVolumeIcon = (volume: number) => {
    if (volume === 0) return <VolumeMuteIcon />;
    if (volume < 0.5) return <VolumeDownIcon />;
    return <VolumeUpIcon />;
  };

  return (
    <Paper 
      elevation={3} 
      sx={{ 
        p: 3, 
        width: '100%', 
        maxWidth: 400,
        borderRadius: 2,
        position: 'relative'
      }}
    >
      {onClose && (
        <IconButton 
          sx={{ position: 'absolute', top: 8, right: 8 }}
          onClick={onClose}
        >
          <CloseIcon />
        </IconButton>
      )}
      
      <Typography variant="h5" gutterBottom>
        Sound Settings
      </Typography>
      
      <Divider sx={{ mb: 2 }} />

      {/* Master Volume */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Master Volume
        </Typography>
        <Stack spacing={2} direction="row" alignItems="center" sx={{ mb: 1 }}>
          {getVolumeIcon(settings.masterVolume)}
          <Slider
            value={settings.masterVolume}
            onChange={handleMasterVolumeChange}
            aria-label="Master Volume"
            valueLabelDisplay="auto"
            valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
            min={0}
            max={1}
            step={0.01}
          />
        </Stack>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Sound Effects */}
      <Box sx={{ mb: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <SportsEsportsIcon />
          <Typography variant="h6">Sound Effects</Typography>
          <FormControlLabel
            control={
              <Switch
                checked={settings.sfxEnabled}
                onChange={toggleSfxEnabled}
              />
            }
            label={settings.sfxEnabled ? "Enabled" : "Disabled"}
            sx={{ ml: 'auto' }}
          />
        </Stack>
        
        <Slider
          value={settings.effectsVolume}
          onChange={handleEffectsVolumeChange}
          aria-label="Effects Volume"
          valueLabelDisplay="auto"
          valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
          disabled={!settings.sfxEnabled}
          min={0}
          max={1}
          step={0.01}
        />
        
        <Typography variant="caption" color="text.secondary">
          Effective volume: {Math.round(getEffectiveVolume('effects') * 100)}%
        </Typography>
      </Box>

      {/* Music */}
      <Box sx={{ mb: 2 }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <MusicNoteIcon />
          <Typography variant="h6">Music</Typography>
          <FormControlLabel
            control={
              <Switch
                checked={settings.musicEnabled}
                onChange={toggleMusicEnabled}
              />
            }
            label={settings.musicEnabled ? "Enabled" : "Disabled"}
            sx={{ ml: 'auto' }}
          />
        </Stack>
        
        <Slider
          value={settings.musicVolume}
          onChange={handleMusicVolumeChange}
          aria-label="Music Volume"
          valueLabelDisplay="auto"
          valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
          disabled={!settings.musicEnabled}
          min={0}
          max={1}
          step={0.01}
        />
        
        <Typography variant="caption" color="text.secondary">
          Effective volume: {Math.round(getEffectiveVolume('music') * 100)}%
        </Typography>
      </Box>
    </Paper>
  );
};

export default SoundSettingsPanel; 