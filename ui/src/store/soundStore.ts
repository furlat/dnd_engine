import { proxy } from 'valtio';
import { subscribeKey } from 'valtio/utils';

// Sound settings interface
export interface SoundSettings {
  masterVolume: number; // 0 to 1
  effectsVolume: number; // 0 to 1
  musicVolume: number; // 0 to 1
  sfxEnabled: boolean;
  musicEnabled: boolean;
}

// Sound effect types for attack system
export type AttackSoundType = 'hit' | 'miss';

// Sound effect configuration
export interface SoundEffect {
  id: string;
  path: string;
  volume?: number; // Override volume for this specific sound
  category: 'attack' | 'music' | 'ui' | 'ambient';
}

// Music track interface
export interface MusicTrack {
  id: string;
  name: string;
  path: string;
  duration?: number;
}

// Sound store state
export interface SoundStoreState {
  settings: SoundSettings;
  
  // Music state
  currentTrack: MusicTrack | null;
  isPlaying: boolean;
  currentTime: number;
  tracks: MusicTrack[];
  shuffle: boolean;
  
  // Sound effects
  loadedSounds: Map<string, HTMLAudioElement>;
  
  // Volume control for cinematic effects
  cinematicVolumeMultiplier: number; // 0 to 1, for dynamic volume adjustments
}

// Default settings
const defaultSettings: SoundSettings = {
  masterVolume: 0.7,
  effectsVolume: 1.0,
  musicVolume: 0.8,
  sfxEnabled: true,
  musicEnabled: true
};

// Load settings from localStorage
const loadSettingsFromStorage = (): SoundSettings => {
  try {
    const savedSettings = localStorage.getItem('soundSettings');
    if (savedSettings) {
      return { ...defaultSettings, ...JSON.parse(savedSettings) };
    }
  } catch (e) {
    console.error('Failed to parse saved sound settings:', e);
  }
  return defaultSettings;
};

// Available music tracks
const musicTracks: MusicTrack[] = [
  {
    id: 'intro_menu',
    name: 'Intro Menu',
    path: 'sounds/music/intro_menu.mp3'
  },
  {
    id: 'relax_cyborg',
    name: 'Relax Cyborg',
    path: 'sounds/music/relax_cyborg.mp3'
  },
  {
    id: 'xilo_cyborg',
    name: 'Xilo Cyborg',
    path: 'sounds/music/xilo_cyborg.mp3'
  },
  {
    id: 'combat_cyborg',
    name: 'Combat Cyborg',
    path: 'sounds/music/combat_cyborg.mp3'
  }
];

// Available attack sound effects
const attackSounds: SoundEffect[] = [
  // Hit sounds
  { id: 'sword-hit-1', path: 'sounds/attack/sword-swing-hit-1.mp3', category: 'attack' },
  { id: 'sword-hit-2', path: 'sounds/attack/sword-swing-hit-2.mp3', category: 'attack' },
  { id: 'sword-hit-3', path: 'sounds/attack/sword-swing-hit-3.mp3', category: 'attack' },
  { id: 'hit-flesh', path: 'sounds/attack/hit_flesh.mp3', category: 'attack' },
  
  // Miss sounds (swoosh)
  { id: 'swoosh-1', path: 'sounds/attack/swoosh-1.mp3', category: 'attack' },
  { id: 'swoosh-2', path: 'sounds/attack/swoosh-2.mp3', category: 'attack' },
  { id: 'swoosh-3', path: 'sounds/attack/swoosh-3.mp3', category: 'attack' },
  { id: 'swoosh-4', path: 'sounds/attack/swoosh-4.mp3', category: 'attack' },
  
  // Other attack sounds
  { id: 'sword-parry', path: 'sounds/attack/sword-parry.mp3', category: 'attack' },
  { id: 'unsheath', path: 'sounds/attack/unsheat.mp3', category: 'attack' },
  { id: 'magical-spell', path: 'sounds/attack/magical-spell-cast-190272.mp3', category: 'attack' }
];

// Create the sound store
export const soundStore = proxy<SoundStoreState>({
  settings: loadSettingsFromStorage(),
  
  // Music state
  currentTrack: null,
  isPlaying: false,
  currentTime: 0,
  tracks: musicTracks,
  shuffle: false,
  
  // Sound effects
  loadedSounds: new Map(),
  
  // Cinematic volume
  cinematicVolumeMultiplier: 1.0
});

// Sound actions
export const soundActions = {
  // Settings management
  updateSettings: (newSettings: Partial<SoundSettings>) => {
    soundStore.settings = { ...soundStore.settings, ...newSettings };
    localStorage.setItem('soundSettings', JSON.stringify(soundStore.settings));
  },
  
  // Calculate effective volume
  getEffectiveVolume: (type: 'effects' | 'music'): number => {
    const settings = soundStore.settings;
    const isEnabled = type === 'effects' ? settings.sfxEnabled : settings.musicEnabled;
    if (!isEnabled) return 0;
    
    const typeVolume = type === 'effects' ? settings.effectsVolume : settings.musicVolume;
    return settings.masterVolume * typeVolume * soundStore.cinematicVolumeMultiplier;
  },
  
  // Cinematic volume control
  setCinematicVolumeMultiplier: (multiplier: number) => {
    soundStore.cinematicVolumeMultiplier = Math.max(0, Math.min(1, multiplier));
  },
  
  // Sound effect management
  preloadSound: async (soundEffect: SoundEffect): Promise<void> => {
    if (soundStore.loadedSounds.has(soundEffect.id)) {
      return; // Already loaded
    }
    
    try {
      const audio = new Audio(`/${soundEffect.path}`);
      audio.preload = 'auto';
      
      // Wait for the audio to be loaded
      await new Promise<void>((resolve, reject) => {
        audio.addEventListener('canplaythrough', () => resolve(), { once: true });
        audio.addEventListener('error', reject, { once: true });
        audio.load();
      });
      
      soundStore.loadedSounds.set(soundEffect.id, audio);
      console.log(`[SoundStore] Preloaded sound: ${soundEffect.id}`);
    } catch (error) {
      console.error(`[SoundStore] Failed to preload sound ${soundEffect.id}:`, error);
    }
  },
  
  // Play sound effect
  playSound: (soundId: string, volumeOverride?: number): void => {
    const audio = soundStore.loadedSounds.get(soundId);
    if (!audio) {
      console.warn(`[SoundStore] Sound not loaded: ${soundId}`);
      return;
    }
    
    const effectiveVolume = soundActions.getEffectiveVolume('effects');
    if (effectiveVolume === 0) {
      return; // Sound effects disabled
    }
    
    // Clone the audio for overlapping sounds
    const audioClone = audio.cloneNode() as HTMLAudioElement;
    audioClone.volume = volumeOverride !== undefined ? volumeOverride : effectiveVolume;
    
    audioClone.play().catch(error => {
      console.error(`[SoundStore] Failed to play sound ${soundId}:`, error);
    });
  },
  
  // Attack-specific sound methods
  playAttackSound: (attackOutcome: 'Hit' | 'Miss' | 'Crit'): void => {
    let soundIds: string[];
    
    if (attackOutcome === 'Hit' || attackOutcome === 'Crit') {
      // Play hit sound - only use the first one for now, others are too metallic
      soundIds = ['sword-hit-1'];
    } else {
      // Play miss sound (swoosh)
      soundIds = ['swoosh-1', 'swoosh-2', 'swoosh-3', 'swoosh-4'];
    }
    
    // Randomly select one of the available sounds (or just use the single hit sound)
    const randomSoundId = soundIds[Math.floor(Math.random() * soundIds.length)];
    
    console.log(`[SoundStore] Playing attack sound for ${attackOutcome}: ${randomSoundId}`);
    soundActions.playSound(randomSoundId);
  },
  
  // Music management
  setCurrentTrack: (track: MusicTrack | null) => {
    soundStore.currentTrack = track;
  },
  
  setPlaying: (playing: boolean) => {
    soundStore.isPlaying = playing;
  },
  
  setCurrentTime: (time: number) => {
    soundStore.currentTime = time;
  },
  
  setShuffle: (shuffle: boolean) => {
    soundStore.shuffle = shuffle;
  },
  
  // Music playback controls
  playNextTrack: () => {
    const currentIndex = musicTracks.findIndex(track => track.id === soundStore.currentTrack?.id);
    const nextIndex = (currentIndex + 1) % musicTracks.length;
    soundStore.currentTrack = musicTracks[nextIndex];
  },
  
  playPreviousTrack: () => {
    const currentIndex = musicTracks.findIndex(track => track.id === soundStore.currentTrack?.id);
    const prevIndex = currentIndex <= 0 ? musicTracks.length - 1 : currentIndex - 1;
    soundStore.currentTrack = musicTracks[prevIndex];
  },
  
  // Initialize music with intro_menu
  initializeMusic: () => {
    if (!soundStore.currentTrack) {
      soundStore.currentTrack = musicTracks[0]; // Start with intro_menu
    }
  },
  
  // Initialize sound system
  initialize: async (): Promise<void> => {
    console.log('[SoundStore] Initializing sound system...');
    
    // Initialize music
    soundActions.initializeMusic();
    
    // Preload all attack sounds
    for (const sound of attackSounds) {
      await soundActions.preloadSound(sound);
    }
    
    console.log(`[SoundStore] Preloaded ${attackSounds.length} attack sounds`);
  }
};

// Subscribe to settings changes to update any active audio
subscribeKey(soundStore, 'settings', (settings) => {
  console.log('[SoundStore] Settings updated:', settings);
  
  // Update volume of any currently playing sounds would go here
  // For now, new sounds will use the updated volume
});

// Export attack sounds for reference
export { attackSounds }; 