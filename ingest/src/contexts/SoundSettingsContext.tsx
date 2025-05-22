import * as React from 'react';

interface SoundSettings {
  masterVolume: number; // 0 to 1
  effectsVolume: number; // 0 to 1
  musicVolume: number; // 0 to 1
  sfxEnabled: boolean;
  musicEnabled: boolean;
}

interface SoundSettingsContextProps {
  settings: SoundSettings;
  updateSettings: (newSettings: Partial<SoundSettings>) => void;
  getEffectiveVolume: (type: 'effects' | 'music') => number;
}

const defaultSettings: SoundSettings = {
  masterVolume: 0.7, // Default to 70%
  effectsVolume: 1.0,
  musicVolume: 0.8,
  sfxEnabled: true,
  musicEnabled: true
};

export const SoundSettingsContext = React.createContext<SoundSettingsContextProps>({
  settings: defaultSettings,
  updateSettings: () => {},
  getEffectiveVolume: () => 0
});

export const SoundSettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = React.useState<SoundSettings>(() => {
    // Try to load settings from localStorage
    const savedSettings = localStorage.getItem('soundSettings');
    if (savedSettings) {
      try {
        return JSON.parse(savedSettings) as SoundSettings;
      } catch (e) {
        console.error('Failed to parse saved sound settings:', e);
      }
    }
    return defaultSettings;
  });

  // Update settings and save to localStorage
  const updateSettings = React.useCallback((newSettings: Partial<SoundSettings>) => {
    setSettings(prev => {
      const updated = { ...prev, ...newSettings };
      // Save to localStorage
      localStorage.setItem('soundSettings', JSON.stringify(updated));
      return updated;
    });
  }, []);

  // Calculate effective volume based on master volume and type-specific volume
  const getEffectiveVolume = React.useCallback((type: 'effects' | 'music'): number => {
    const isEnabled = type === 'effects' ? settings.sfxEnabled : settings.musicEnabled;
    if (!isEnabled) return 0;
    
    const typeVolume = type === 'effects' ? settings.effectsVolume : settings.musicVolume;
    return settings.masterVolume * typeVolume;
  }, [settings]);

  return (
    <SoundSettingsContext.Provider value={{ settings, updateSettings, getEffectiveVolume }}>
      {children}
    </SoundSettingsContext.Provider>
  );
};

export const useSoundSettings = () => React.useContext(SoundSettingsContext); 