import * as React from 'react';
import { useSoundSettings } from '../../hooks/useSoundSettings';
import { Paper, Typography, IconButton, Box, Tooltip, Divider } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import MusicNoteIcon from '@mui/icons-material/MusicNote';

const BackgroundMusicPlayer: React.FC = () => {
  const { 
    currentTrack, 
    isPlaying, 
    setPlaying, 
    playNextTrack, 
    playPreviousTrack,
    getEffectiveVolume 
  } = useSoundSettings();

  // Audio element ref
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
      
  // Initialize audio element when track changes
  React.useEffect(() => {
    if (currentTrack && audioRef.current) {
      audioRef.current.src = `/${currentTrack.path}`;
      audioRef.current.load();
      
      // Set volume based on settings
      const volume = getEffectiveVolume('music');
      audioRef.current.volume = volume;

      // Auto-play if was playing
      if (isPlaying) {
        audioRef.current.play().catch(error => {
          console.error('[BackgroundMusicPlayer] Failed to play:', error);
          setPlaying(false);
        });
      }
    }
  }, [currentTrack, getEffectiveVolume]);

  // Update volume when settings change
  React.useEffect(() => {
    if (audioRef.current) {
      const volume = getEffectiveVolume('music');
      audioRef.current.volume = volume;
    }
  }, [getEffectiveVolume]);

  // Handle play/pause state changes
  React.useEffect(() => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.play().catch(error => {
          console.error('[BackgroundMusicPlayer] Failed to play:', error);
          setPlaying(false);
          });
      } else {
        audioRef.current.pause();
              }
            }
  }, [isPlaying, setPlaying]);
          
  // Handle play/pause toggle
  const handlePlayPause = () => {
    setPlaying(!isPlaying);
  };

  // Handle next track
  const handleNext = () => {
    playNextTrack();
  };

  // Handle previous track
  const handlePrevious = () => {
    playPreviousTrack();
  };

  // Handle track end - auto play next
  const handleTrackEnd = () => {
    playNextTrack();
  };
  
  if (!currentTrack) {
    return null; // No track selected
  }

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute', 
        bottom: 8, 
        left: 258, // 250px entity panel width + 8px margin
        padding: 1,
        paddingX: 2,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        color: 'white',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        gap: 2,
        zIndex: 1
          }}
        >
      {/* Hidden audio element */}
      <audio
        ref={audioRef}
        onEnded={handleTrackEnd}
        onError={() => {
          console.error('[BackgroundMusicPlayer] Audio error');
          setPlaying(false);
        }}
      />
      
      {/* Music icon and track info */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <MusicNoteIcon sx={{ fontSize: 16 }} />
        <Typography variant="body2" noWrap>
          {currentTrack.name}
        </Typography>
      </Box>

      <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
      
      {/* Control buttons */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Tooltip title="Previous Track">
          <IconButton 
            size="small" 
            onClick={handlePrevious}
            sx={{ color: 'white' }}
          >
            <SkipPreviousIcon />
          </IconButton>
        </Tooltip>
        
        <Tooltip title={isPlaying ? "Pause" : "Play"}>
          <IconButton 
            size="small" 
            onClick={handlePlayPause}
            sx={{ color: 'white' }}
          >
            {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Next Track">
          <IconButton 
            size="small" 
            onClick={handleNext}
            sx={{ color: 'white' }}
          >
            <SkipNextIcon />
          </IconButton>
        </Tooltip>
      </Box>
    </Paper>
  );
};

export default BackgroundMusicPlayer; 