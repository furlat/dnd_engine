import { useSnapshot } from 'valtio';
import { soundStore, soundActions, SoundSettings } from '../store/soundStore';

/**
 * Hook to access sound settings and actions using valtio store
 * Replaces the old React context-based useSoundSettings
 */
export const useSoundSettings = () => {
  const snap = useSnapshot(soundStore);
  
  return {
    settings: snap.settings,
    updateSettings: soundActions.updateSettings,
    getEffectiveVolume: soundActions.getEffectiveVolume,
    
    // Additional sound system features
    playSound: soundActions.playSound,
    playAttackSound: soundActions.playAttackSound,
    setCinematicVolumeMultiplier: soundActions.setCinematicVolumeMultiplier,
    
    // Music state
    currentTrack: snap.currentTrack,
    isPlaying: snap.isPlaying,
    currentTime: snap.currentTime,
    tracks: snap.tracks,
    shuffle: snap.shuffle,
    
    // Music actions
    setCurrentTrack: soundActions.setCurrentTrack,
    setPlaying: soundActions.setPlaying,
    setCurrentTime: soundActions.setCurrentTime,
    setShuffle: soundActions.setShuffle,
    playNextTrack: soundActions.playNextTrack,
    playPreviousTrack: soundActions.playPreviousTrack
  };
}; 