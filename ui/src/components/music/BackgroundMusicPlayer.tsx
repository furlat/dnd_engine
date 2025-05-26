import * as React from 'react';
import { sound } from '@pixi/sound';
import { useSoundSettings } from '../../hooks/useSoundSettings';
import { Paper, Typography, IconButton, Slider, Select, MenuItem, FormControl, InputLabel, Box, Tooltip } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import ShuffleIcon from '@mui/icons-material/Shuffle';

// Flag to determine if we should use HTML5 Audio fallback
let useAudioFallback = false;

// Helper function to resolve audio file paths correctly
const resolveAudioPath = (path: string): string => {
  // If we're in development, make sure to use the correct base path
  if (process.env.NODE_ENV === 'development') {
    // In development, files in public folder are served from root
    return `/${path}`;
  }
  // In production, we can just use the path as is
  return path;
};

// Helper to check if a browser supports a specific audio format
const isSupportedAudioFormat = (format: string): boolean => {
  const audio = document.createElement('audio');
  // Check for MP3 support
  if (format === 'mp3') {
    return !!audio.canPlayType('audio/mpeg;').replace(/^no$/, '');
  }
  // Check for OGG support
  if (format === 'ogg') {
    return !!audio.canPlayType('audio/ogg; codecs="vorbis"').replace(/^no$/, '');
  }
  // Check for WAV support
  if (format === 'wav') {
    return !!audio.canPlayType('audio/wav; codecs="1"').replace(/^no$/, '');
  }
  return false;
};

// Check browser audio format support
const hasMP3Support = isSupportedAudioFormat('mp3');
if (!hasMP3Support) {
  console.warn('Browser does not seem to support MP3 audio format. Audio may not play correctly.');
  useAudioFallback = true; // Force HTML5 Audio which can try alternative formats
}

// List of music tracks
const MUSIC_TRACKS = [
  { id: 'track1', title: 'Combat Cyborg', path: 'sounds/music/combat_cyborg.mp3' },
  { id: 'track2', title: 'Intro Menu', path: 'sounds/music/intro_menu.mp3' },
  { id: 'track3', title: 'Relax Cyborg', path: 'sounds/music/relax_cyborg.mp3' },
  { id: 'track4', title: 'Xilo Cyborg', path: 'sounds/music/xilo_cyborg.mp3' },
];

// Create promises to track music loading
const musicLoadPromises: Record<string, Promise<void>> = {};

// Audio elements for fallback method
const audioElements: Record<string, HTMLAudioElement> = {};

// Helper function to try different file formats
const getAudioWithFallbackFormat = (basePath: string): HTMLAudioElement => {
  // First try with MP3 format
  const path = basePath.endsWith('.mp3') ? basePath : `${basePath}.mp3`;
  const audio = new Audio(resolveAudioPath(path));
  
  // Set up error handler that will try alternative formats if MP3 fails
  audio.onerror = () => {
    if (hasMP3Support) {
      // If MP3 is supported but still failed, might be a file issue
      console.log(`MP3 format failed for ${path}, trying alternative formats`);
      
      // Try OGG format if supported
      if (isSupportedAudioFormat('ogg')) {
        const oggPath = basePath.replace(/\.mp3$/, '') + '.ogg';
        audio.src = resolveAudioPath(oggPath);
        console.log(`Trying OGG format: ${oggPath}`);
        audio.load();
      } else if (isSupportedAudioFormat('wav')) {
        // Try WAV as last resort
        const wavPath = basePath.replace(/\.mp3$/, '') + '.wav';
        audio.src = resolveAudioPath(wavPath);
        console.log(`Trying WAV format: ${wavPath}`);
        audio.load();
      }
    }
  };
  
  return audio;
};

// Preload all music tracks
const preloadMusicTracks = async (): Promise<void> => {
  await Promise.all(
    MUSIC_TRACKS.map(track => {
      if (!musicLoadPromises[track.id]) {
        musicLoadPromises[track.id] = (async () => {
          try {
            if (useAudioFallback) {
              // Load using HTML5 Audio
              if (!audioElements[track.id]) {
                console.log(`[Music Preload] Loading track with HTML5 Audio: ${track.title}`);
                const audio = getAudioWithFallbackFormat(track.path);
                audio.loop = true;
                // Preload
                audio.load();
                audioElements[track.id] = audio;
                console.log(`[Music Preload] Loaded track with HTML5 Audio: ${track.title}`);
              }
            } else if (!sound.exists(track.id)) {
              // Try using Pixi Sound first
              console.log(`[Music Preload] Loading track with Pixi Sound: ${track.title}`);
              try {
                await sound.add(track.id, {
                  url: resolveAudioPath(track.path),
                  preload: true,
                  loop: true
                });
                console.log(`[Music Preload] Loaded track with Pixi Sound: ${track.title}`);
              } catch (error) {
                console.error(`Error preloading music track ${track.title} with Pixi Sound:`, error);
                // If Pixi Sound fails, switch to HTML5 Audio fallback for all tracks
                useAudioFallback = true;
                
                // Load using HTML5 Audio instead
                if (!audioElements[track.id]) {
                  console.log(`[Music Preload] Falling back to HTML5 Audio for: ${track.title}`);
                  const audioFallback = getAudioWithFallbackFormat(track.path);
                  audioFallback.loop = true;
                  // Preload
                  audioFallback.load();
                  audioElements[track.id] = audioFallback;
                }
              }
            }
          } catch (error) {
            console.error(`Error preloading music track ${track.title}:`, error);
            throw error;
          }
        })();
      }
      return musicLoadPromises[track.id];
    })
  );
};

interface BackgroundMusicPlayerProps {
  minimized?: boolean;
  onToggleMinimize?: () => void;
}

const BackgroundMusicPlayer: React.FC<BackgroundMusicPlayerProps> = ({ 
  minimized = false,
  onToggleMinimize
}) => {
  const { settings, getEffectiveVolume } = useSoundSettings();
  const [currentTrackIndex, setCurrentTrackIndex] = React.useState(0);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [isLoaded, setIsLoaded] = React.useState(false);
  const [shuffleMode, setShuffleMode] = React.useState(false);
  const musicInstanceRef = React.useRef<any>(null);
  const currentAudioRef = React.useRef<HTMLAudioElement | null>(null);

  // Get effective music volume from settings
  const effectiveMusicVolume = getEffectiveVolume('music');

  // Initialize by preloading music
  React.useEffect(() => {
    const loadMusic = async () => {
      try {
        await preloadMusicTracks();
        setIsLoaded(true);
      } catch (error) {
        console.error('Failed to load music tracks:', error);
      }
    };

    loadMusic();

    // Cleanup function
    return () => {
      if (useAudioFallback && currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      } else if (musicInstanceRef.current) {
        try {
          // Use sound.stop with the track ID
          sound.stop(musicInstanceRef.current);
        } catch (error) {
          console.error('Error cleaning up music:', error);
        }
      }
    };
  }, []);

  // Update volume when settings change
  React.useEffect(() => {
    if (isPlaying) {
      if (useAudioFallback && currentAudioRef.current) {
        // Update volume for HTML5 Audio
        currentAudioRef.current.volume = effectiveMusicVolume;
        console.log(`[Music Player] Updated HTML5 Audio volume for ${MUSIC_TRACKS[currentTrackIndex].title} to ${effectiveMusicVolume}`);
      } else if (musicInstanceRef.current) {
        // Update volume for Pixi Sound
        try {
          sound.volume(musicInstanceRef.current, effectiveMusicVolume);
          console.log(`[Music Player] Updated Pixi Sound volume for ${musicInstanceRef.current} to ${effectiveMusicVolume}`);
        } catch (error) {
          console.error('Error updating volume:', error);
          // If we encounter an error updating volume with Pixi Sound, switch to HTML5 Audio
          useAudioFallback = true;
          playCurrentTrack();
        }
      }
    }
  }, [effectiveMusicVolume, isPlaying, currentTrackIndex]);

  // Play the current track
  const playCurrentTrack = React.useCallback(() => {
    if (!isLoaded) return;
    
    const currentTrack = MUSIC_TRACKS[currentTrackIndex];
    
    // Stop any currently playing music first
    if (useAudioFallback && currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    } else if (musicInstanceRef.current) {
      try {
        sound.stop(musicInstanceRef.current);
      } catch (error) {
        console.error('Error stopping current track:', error);
      }
    }
    
    try {
      if (useAudioFallback) {
        // Play using HTML5 Audio
        console.log(`[Music Player] Playing track with HTML5 Audio: ${currentTrack.title} from path: ${currentTrack.path}`);
        
        if (audioElements[currentTrack.id]) {
          const audio = audioElements[currentTrack.id];
          audio.volume = effectiveMusicVolume;
          audio.currentTime = 0;
          
          // Set up event handlers
          audio.onended = () => {
            if (!shuffleMode) {
              nextTrack();
            } else {
              playRandomTrack();
            }
          };
          
          // Handle errors with audio element
          audio.onerror = (e) => {
            console.error(`Error playing audio for ${currentTrack.title}:`, e);
            setIsPlaying(false);
          };
          
          const playPromise = audio.play();
          if (playPromise !== undefined) {
            playPromise.catch(error => {
              console.error(`Error playing HTML5 Audio for ${currentTrack.title}:`, error);
              
              // If we get a user interaction error, we'll try again when user clicks
              if (error.name === 'NotAllowedError') {
                console.log('Audio playback requires user interaction first');
              } else if (error.name === 'NotFoundError' || error.name === 'NetworkError') {
                console.error(`File not found: ${currentTrack.path}`);
              }
              
              setIsPlaying(false);
            });
          }
          
          currentAudioRef.current = audio;
          setIsPlaying(true);
        } else {
          // Create audio element if it doesn't exist
          const audio = getAudioWithFallbackFormat(currentTrack.path);
          audio.loop = true;
          audio.volume = effectiveMusicVolume;
          
          // Handle errors with audio element
          audio.onerror = (e) => {
            console.error(`Error loading audio for ${currentTrack.title}:`, e);
            setIsPlaying(false);
          };
          
          const playPromise = audio.play();
          if (playPromise !== undefined) {
            playPromise.catch(error => {
              console.error(`Error playing HTML5 Audio for ${currentTrack.title}:`, error);
              
              // If we get a user interaction error, we'll try again when user clicks
              if (error.name === 'NotAllowedError') {
                console.log('Audio playback requires user interaction first');
              } else if (error.name === 'NotFoundError' || error.name === 'NetworkError') {
                console.error(`File not found: ${currentTrack.path}`);
              }
              
              setIsPlaying(false);
            });
          }
          
          audioElements[currentTrack.id] = audio;
          currentAudioRef.current = audio;
          setIsPlaying(true);
        }
      } else {
        // Try to play with Pixi Sound
        console.log(`[Music Player] Playing track with Pixi Sound: ${currentTrack.title} from path: ${currentTrack.path}`);
        
        // Make sure the sound is actually loaded before playing
        if (!sound.exists(currentTrack.id)) {
          console.log(`[Music Player] Sound ${currentTrack.id} doesn't exist, loading it first`);
          sound.add(currentTrack.id, {
            url: resolveAudioPath(currentTrack.path),
            preload: true,
            loop: true
          });
        }
        
        // Play the sound and store the ID
        try {
          sound.play(currentTrack.id, {
            volume: effectiveMusicVolume,
            loop: true,
            complete: () => {
              console.log(`[Music Player] Track complete: ${currentTrack.title}`);
              if (!shuffleMode) {
                nextTrack();
              } else {
                playRandomTrack();
              }
            }
          });
          
          // Store the track ID
          musicInstanceRef.current = currentTrack.id;
          setIsPlaying(true);
        } catch (error) {
          console.error(`Error playing with Pixi Sound for ${currentTrack.title}:`, error);
          
          // Switch to HTML5 Audio fallback
          console.log(`[Music Player] Switching to HTML5 Audio fallback for ${currentTrack.title}`);
          useAudioFallback = true;
          
          // Try playing with HTML5 Audio
          const audio = getAudioWithFallbackFormat(currentTrack.path);
          audio.loop = true;
          audio.volume = effectiveMusicVolume;
          
          // Handle errors with audio element
          audio.onerror = (e) => {
            console.error(`Error loading audio fallback for ${currentTrack.title}:`, e);
            setIsPlaying(false);
          };
          
          const playPromise = audio.play();
          if (playPromise !== undefined) {
            playPromise.catch(audioError => {
              console.error(`Error playing HTML5 Audio fallback for ${currentTrack.title}:`, audioError);
              
              // If we get a user interaction error, we'll try again when user clicks
              if (audioError.name === 'NotAllowedError') {
                console.log('Audio playback requires user interaction first');
              } else if (audioError.name === 'NotFoundError' || audioError.name === 'NetworkError') {
                console.error(`File not found: ${currentTrack.path}`);
              }
              
              setIsPlaying(false);
            });
          }
          
          audioElements[currentTrack.id] = audio;
          currentAudioRef.current = audio;
          setIsPlaying(true);
        }
      }
    } catch (error) {
      console.error(`Error playing music track ${currentTrack.title}:`, error);
      setIsPlaying(false);
    }
  }, [currentTrackIndex, effectiveMusicVolume, isLoaded, shuffleMode]);

  // Toggle play/pause
  const togglePlay = React.useCallback(() => {
    if (isPlaying) {
      if (useAudioFallback && currentAudioRef.current) {
        currentAudioRef.current.pause();
        setIsPlaying(false);
      } else if (musicInstanceRef.current) {
        try {
          // Use sound.stop with the track ID
          sound.stop(musicInstanceRef.current);
          setIsPlaying(false);
        } catch (error) {
          console.error('Error stopping track:', error);
          setIsPlaying(false);
        }
      }
    } else {
      playCurrentTrack();
    }
  }, [isPlaying, playCurrentTrack]);

  // Previous track
  const previousTrack = React.useCallback(() => {
    setCurrentTrackIndex(prev => {
      const newIndex = prev === 0 ? MUSIC_TRACKS.length - 1 : prev - 1;
      return newIndex;
    });
    
    if (isPlaying) {
      // Small delay to ensure track index is updated
      setTimeout(() => {
        playCurrentTrack();
      }, 0);
    }
  }, [isPlaying, playCurrentTrack]);

  // Next track
  const nextTrack = React.useCallback(() => {
    setCurrentTrackIndex(prev => {
      const newIndex = (prev + 1) % MUSIC_TRACKS.length;
      return newIndex;
    });
    
    if (isPlaying) {
      // Small delay to ensure track index is updated
      setTimeout(() => {
        playCurrentTrack();
      }, 0);
    }
  }, [isPlaying, playCurrentTrack]);

  // Play random track
  const playRandomTrack = React.useCallback(() => {
    const randomIndex = Math.floor(Math.random() * MUSIC_TRACKS.length);
    setCurrentTrackIndex(randomIndex);
    
    if (isPlaying) {
      // Small delay to ensure track index is updated
      setTimeout(() => {
        playCurrentTrack();
      }, 0);
    }
  }, [isPlaying, playCurrentTrack]);

  // Toggle shuffle mode
  const toggleShuffle = React.useCallback(() => {
    setShuffleMode(prev => !prev);
  }, []);

  // Handle track selection
  const handleTrackChange = React.useCallback((event: React.ChangeEvent<{ value: unknown }>) => {
    const newIndex = MUSIC_TRACKS.findIndex(track => track.id === event.target.value);
    if (newIndex !== -1) {
      setCurrentTrackIndex(newIndex);
      
      if (isPlaying) {
        // Small delay to ensure track index is updated
        setTimeout(() => {
          playCurrentTrack();
        }, 0);
      }
    }
  }, [isPlaying, playCurrentTrack]);

  if (minimized) {
    return (
      <Paper
        elevation={3}
        sx={{
          position: 'fixed',
          bottom: 20,
          left: 20,
          p: 1,
          borderRadius: 2,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          color: 'white',
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 1
        }}
      >
        {!isLoaded ? (
          <span>
            <IconButton size="small" disabled sx={{ color: 'white' }}>
              <PlayArrowIcon />
            </IconButton>
          </span>
        ) : (
          <IconButton size="small" onClick={togglePlay} sx={{ color: 'white' }}>
            {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
          </IconButton>
        )}
        
        <Typography variant="caption" sx={{ maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {isLoaded ? MUSIC_TRACKS[currentTrackIndex].title : 'Loading...'}
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'fixed',
        bottom: 20,
        left: 20,
        p: 2,
        borderRadius: 2,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        zIndex: 10,
        width: 300
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          Music Player
        </Typography>
        
        <IconButton 
          size="small" 
          onClick={toggleShuffle}
          sx={{ 
            color: 'white',
            bgcolor: shuffleMode ? 'rgba(255, 255, 255, 0.2)' : 'transparent'
          }}
        >
          <ShuffleIcon />
        </IconButton>
      </Box>

      <FormControl fullWidth size="small" sx={{ mb: 2 }}>
        <Select
          value={MUSIC_TRACKS[currentTrackIndex].id}
          onChange={handleTrackChange as any}
          disabled={!isLoaded}
          sx={{ 
            color: 'white',
            '.MuiOutlinedInput-notchedOutline': {
              borderColor: 'rgba(255, 255, 255, 0.3)'
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: 'rgba(255, 255, 255, 0.5)'
            },
            '.MuiSvgIcon-root': {
              color: 'white'
            }
          }}
        >
          {MUSIC_TRACKS.map(track => (
            <MenuItem key={track.id} value={track.id}>
              {track.title}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <VolumeUpIcon sx={{ mr: 1 }} />
        <Typography variant="caption" sx={{ width: 30 }}>
          {Math.round(effectiveMusicVolume * 100)}%
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
        {!isLoaded ? (
          <span>
            <IconButton disabled sx={{ color: 'white' }}>
              <SkipPreviousIcon />
            </IconButton>
          </span>
        ) : (
          <IconButton onClick={previousTrack} sx={{ color: 'white' }}>
            <SkipPreviousIcon />
          </IconButton>
        )}
        
        {!isLoaded ? (
          <span>
            <IconButton disabled sx={{ color: 'white' }}>
              <PlayArrowIcon />
            </IconButton>
          </span>
        ) : (
          <IconButton onClick={togglePlay} sx={{ color: 'white' }}>
            {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
          </IconButton>
        )}
        
        {!isLoaded ? (
          <span>
            <IconButton disabled sx={{ color: 'white' }}>
              <SkipNextIcon />
            </IconButton>
          </span>
        ) : (
          <IconButton onClick={nextTrack} sx={{ color: 'white' }}>
            <SkipNextIcon />
          </IconButton>
        )}
      </Box>

      <Typography variant="body2" sx={{ textAlign: 'center', opacity: 0.8 }}>
        {isLoaded ? `Now playing: ${MUSIC_TRACKS[currentTrackIndex].title}` : 'Loading music...'}
      </Typography>
    </Paper>
  );
};

export default BackgroundMusicPlayer; 