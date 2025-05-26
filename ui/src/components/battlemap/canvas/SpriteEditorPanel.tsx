import React, { useState, useCallback, useEffect } from 'react';
import { 
  Paper, 
  ToggleButton, 
  ToggleButtonGroup, 
  Box, 
  Typography, 
  Divider, 
  Tabs, 
  Tab,
  Button,
  Chip,
  Avatar,
  Slider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSpriteEditor } from '../../../hooks/battlemap';
import { useSnapshot } from 'valtio';
import { battlemapStore, battlemapActions } from '../../../store';
import { SpriteFolderName, AnimationState, Direction, EffectType } from '../../../types/battlemap_types';
import { getSpriteSheetPath } from '../../../api/battlemap/battlemapApi';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`sprite-tabpanel-${index}`}
      aria-labelledby={`sprite-tab-${index}`}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
};

// Component to show a preview of the sprite (first frame of south-facing idle)
const SpritePreview: React.FC<{ spriteFolder: string; isSelected: boolean }> = ({ 
  spriteFolder, 
  isSelected 
}) => {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadPreview = async () => {
      setIsLoading(true);
      try {
        // Try to load the Idle spritesheet for this folder
        const spritesheetPath = `/assets/entities/${spriteFolder}/Idle.json`;
        const response = await fetch(spritesheetPath);
        
        if (!response.ok) {
          throw new Error(`Failed to load spritesheet: ${response.status}`);
        }
        
        const spritesheetData = await response.json();
        
        // Look for south-facing idle frame (try different naming patterns)
        const possibleFrameNames = [
          'Idle_S_00.png',
          'Idle_S_01.png', 
          'Idle_S_1.png',
          'Idle_S_0.png',
          'idle_s_00.png',
          'idle_s_01.png',
          'idle_s_1.png',
          'idle_s_0.png'
        ];
        
        let frameData = null;
        for (const frameName of possibleFrameNames) {
          if (spritesheetData.frames && spritesheetData.frames[frameName]) {
            frameData = spritesheetData.frames[frameName];
            break;
          }
        }
        
        if (!frameData) {
          // If no south frame found, try to get the first available frame
          const firstFrameKey = Object.keys(spritesheetData.frames || {})[0];
          if (firstFrameKey) {
            frameData = spritesheetData.frames[firstFrameKey];
          }
        }
        
        if (frameData && spritesheetData.meta && spritesheetData.meta.image) {
          // Create a canvas to extract the specific frame
          const img = new Image();
          img.crossOrigin = 'anonymous';
          
          await new Promise<void>((resolve, reject) => {
            img.onload = () => resolve();
            img.onerror = () => reject(new Error('Failed to load sprite image'));
            img.src = `/assets/entities/${spriteFolder}/${spritesheetData.meta.image}`;
          });
          
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          
          if (ctx) {
            const frame = frameData.frame;
            canvas.width = frame.w;
            canvas.height = frame.h;
            
            // Draw the specific frame from the spritesheet
            ctx.drawImage(
              img,
              frame.x, frame.y, frame.w, frame.h, // Source rectangle
              0, 0, frame.w, frame.h // Destination rectangle
            );
            
            setPreviewUrl(canvas.toDataURL());
          }
        }
      } catch (error) {
        console.warn(`[SpritePreview] Could not load preview for ${spriteFolder}:`, error);
        setPreviewUrl(null);
      } finally {
        setIsLoading(false);
      }
    };

    loadPreview();
  }, [spriteFolder]);

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(255,255,255,0.1)',
        borderRadius: 1,
        overflow: 'hidden',
      }}
      title={spriteFolder} // Show full name on hover
    >
      {isLoading ? (
        <CircularProgress size={32} sx={{ color: 'rgba(255,255,255,0.5)' }} />
      ) : previewUrl ? (
        <Box
          component="img"
          src={previewUrl}
          alt={`${spriteFolder} preview`}
          sx={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
          }}
        />
      ) : (
        <Box
          sx={{
            color: 'rgba(255,255,255,0.5)',
            fontSize: '2rem',
          }}
        >
          ?
        </Box>
      )}
    </Box>
  );
};

interface SpriteEditorPanelProps {
  isLocked: boolean;
}

const SpriteEditorPanel: React.FC<SpriteEditorPanelProps> = ({ isLocked }) => {
  const snap = useSnapshot(battlemapStore);
  const { 
    isEditing,
    selectedEntity,
    selectedEntityId,
    availableSpriteFolders,
    assignSpriteToSelectedEntity,
    removeSpriteFromSelectedEntity,
    hasAssignedSprite,
    assignedSpriteFolder,
    currentAnimation,
    currentDirection,
    currentScale,
    currentAnimationDuration,
    setSelectedEntityAnimation,
    setSelectedEntityDirection,
    setSelectedEntityScale,
    setSelectedEntityAnimationDuration,
  } = useSpriteEditor();
  
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = useCallback((event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  }, []);

  const handleSpriteChange = useCallback((
    event: React.MouseEvent<HTMLElement>,
    newSprite: SpriteFolderName | null,
  ) => {
    if (newSprite !== null) {
      console.log('[SpriteEditorPanel] Sprite selected:', newSprite);
      assignSpriteToSelectedEntity(newSprite);
    }
  }, [assignSpriteToSelectedEntity]);

  const handleRemoveSprite = useCallback(() => {
    removeSpriteFromSelectedEntity();
  }, [removeSpriteFromSelectedEntity]);

  const handleAnimationChange = useCallback((event: any) => {
    setSelectedEntityAnimation(event.target.value as AnimationState);
  }, [setSelectedEntityAnimation]);

  const handleDirectionChange = useCallback((event: any, newDirection: Direction | null) => {
    if (newDirection !== null) {
      setSelectedEntityDirection(newDirection);
    }
  }, [setSelectedEntityDirection]);

  const handleScaleChange = useCallback((event: Event, newValue: number | number[]) => {
    const scale = Array.isArray(newValue) ? newValue[0] : newValue;
    setSelectedEntityScale(scale);
  }, [setSelectedEntityScale]);

  const handleAnimationDurationChange = useCallback((event: Event, newValue: number | number[]) => {
    const duration = Array.isArray(newValue) ? newValue[0] : newValue;
    setSelectedEntityAnimationDuration(duration);
  }, [setSelectedEntityAnimationDuration]);

  // Don't show if not editing or no entity selected
  if (!isEditing || !selectedEntity || !selectedEntityId) {
    return null;
  }

  // Categorize sprites
  const humanoidSprites = availableSpriteFolders.filter(folder => {
    const lowerFolder = folder.toLowerCase();
    return !lowerFolder.includes('zombie') && 
           !lowerFolder.includes('ork') &&
           !lowerFolder.includes('golem') &&
           !lowerFolder.includes('brute') &&
           !lowerFolder.includes('ogre') &&
           !lowerFolder.includes('deathlord') &&
           !lowerFolder.includes('darkknight') &&
           !lowerFolder.includes('berserker_undead') &&
           !lowerFolder.includes('6warrior') &&
           !lowerFolder.includes('5archer') &&
           !lowerFolder.includes('7darkarcher') &&
           !lowerFolder.includes('8necromancer') &&
           !lowerFolder.includes('9wizard');
  });
  
  const zombieSprites = availableSpriteFolders.filter(folder => 
    folder.toLowerCase().includes('zombie')
  );
  
  const monsterSprites = availableSpriteFolders.filter(folder => {
    const lowerFolder = folder.toLowerCase();
    return lowerFolder.includes('ork') || 
           lowerFolder.includes('golem') ||
           lowerFolder.includes('brute') ||
           lowerFolder.includes('ogre') ||
           lowerFolder.includes('deathlord') ||
           lowerFolder.includes('darkknight') ||
           lowerFolder.includes('berserker_undead') ||
           lowerFolder.includes('6warrior') ||
           lowerFolder.includes('5archer') ||
           lowerFolder.includes('7darkarcher') ||
           lowerFolder.includes('8necromancer') ||
           lowerFolder.includes('9wizard');
  });

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        bottom: 80, // Above the tile editor if both are open
        right: 16,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        zIndex: 2,
        borderRadius: 2,
        width: 'auto',
        minWidth: '450px',
        maxWidth: '550px',
        maxHeight: '70vh',
        overflow: 'hidden'
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
        <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Avatar sx={{ width: 24, height: 24 }}>
            {selectedEntity.name[0]}
          </Avatar>
          Assign Sprite to {selectedEntity.name}
        </Typography>
        
        {hasAssignedSprite && assignedSpriteFolder && (
          <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip
              label={`Current: ${assignedSpriteFolder}`}
              size="small"
              color="primary"
              onDelete={handleRemoveSprite}
              deleteIcon={<DeleteIcon />}
              sx={{ 
                backgroundColor: 'rgba(25, 118, 210, 0.3)',
                color: 'white',
                '& .MuiChip-deleteIcon': { color: 'rgba(255,255,255,0.7)' }
              }}
            />
          </Box>
        )}
      </Box>

      {/* Animation Controls - Only show if sprite is assigned */}
      {hasAssignedSprite && (
        <Box sx={{ p: 2, borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>Animation Controls</Typography>
          
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            {/* Animation State */}
            <Box sx={{ flex: 1 }}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ color: 'rgba(255,255,255,0.7)' }}>Animation</InputLabel>
                <Select
                  value={currentAnimation}
                  onChange={handleAnimationChange}
                  label="Animation"
                  sx={{ 
                    color: 'white',
                    '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.3)' },
                    '& .MuiSvgIcon-root': { color: 'rgba(255,255,255,0.7)' }
                  }}
                >
                  {Object.values(AnimationState).map(state => (
                    <MenuItem key={state} value={state}>{state}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
            
            {/* Scale */}
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                Scale: {currentScale.toFixed(1)}x
              </Typography>
              <Slider
                value={currentScale}
                onChange={handleScaleChange}
                min={0.1}
                max={3.0}
                step={0.1}
                sx={{ 
                  color: 'primary.main',
                  '& .MuiSlider-track': { backgroundColor: 'primary.main' },
                  '& .MuiSlider-thumb': { backgroundColor: 'primary.main' }
                }}
              />
            </Box>
          </Box>
          
          {/* Animation Duration */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
              Animation Duration: {currentAnimationDuration.toFixed(1)} seconds
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.65rem', display: 'block' }}>
              Time for one complete animation cycle
            </Typography>
            <Slider
              value={currentAnimationDuration}
              onChange={handleAnimationDurationChange}
              min={0.1}
              max={10.0}
              step={0.1}
              sx={{ 
                color: 'secondary.main',
                '& .MuiSlider-track': { backgroundColor: 'secondary.main' },
                '& .MuiSlider-thumb': { backgroundColor: 'secondary.main' }
              }}
            />
          </Box>
          
          {/* Direction */}
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', mb: 1, display: 'block' }}>
              Direction
            </Typography>
            <ToggleButtonGroup
              value={currentDirection}
              exclusive
              onChange={handleDirectionChange}
              size="small"
              sx={{
                '& .MuiToggleButton-root': {
                  color: 'rgba(255,255,255,0.7)',
                  borderColor: 'rgba(255,255,255,0.3)',
                  '&.Mui-selected': {
                    backgroundColor: 'primary.main',
                    color: 'white'
                  }
                }
              }}
            >
              {Object.values(Direction).map(dir => (
                <ToggleButton key={dir} value={dir}>
                  {dir}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>
        </Box>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs 
          value={tabValue} 
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{
            '& .MuiTab-root': {
              color: 'rgba(255, 255, 255, 0.7)',
              '&.Mui-selected': {
                color: 'white'
              }
            }
          }}
        >
          <Tab label={`Humanoids (${humanoidSprites.length})`} />
          <Tab label={`Zombies (${zombieSprites.length})`} />
          <Tab label={`Monsters (${monsterSprites.length})`} />
          <Tab label="Effects" />
        </Tabs>
      </Box>

      {/* Content with scroll */}
      <Box sx={{ maxHeight: '400px', overflow: 'auto' }}>
        <TabPanel value={tabValue} index={0}>
          <SpriteGrid 
            sprites={humanoidSprites}
            selectedSprite={assignedSpriteFolder}
            onSpriteChange={handleSpriteChange}
          />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <SpriteGrid 
            sprites={zombieSprites}
            selectedSprite={assignedSpriteFolder}
            onSpriteChange={handleSpriteChange}
          />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <SpriteGrid 
            sprites={monsterSprites}
            selectedSprite={assignedSpriteFolder}
            onSpriteChange={handleSpriteChange}
          />
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <EffectsPanel selectedEntityId={selectedEntityId} />
        </TabPanel>
      </Box>
    </Paper>
  );
};

// Helper component for effects panel
const EffectsPanel: React.FC<{ selectedEntityId: string }> = ({ selectedEntityId }) => {
  const snap = useSnapshot(battlemapStore);
  const currentEffects = snap.entities.permanentEffects[selectedEntityId] || [];

  const handleAddEffect = useCallback((effectType: EffectType) => {
    battlemapActions.addPermanentEffectToEntity(selectedEntityId, effectType);
  }, [selectedEntityId]);

  const handleRemoveEffect = useCallback((effectType: EffectType) => {
    battlemapActions.removePermanentEffectFromEntity(selectedEntityId, effectType);
  }, [selectedEntityId]);

  const handleClearAllEffects = useCallback(() => {
    battlemapActions.clearAllPermanentEffectsFromEntity(selectedEntityId);
  }, [selectedEntityId]);

  // Categorize effects
  const temporaryEffects = [
    EffectType.BLOOD_SPLAT,
    EffectType.SPARKS,
    EffectType.SPLASH,
    EffectType.SMOKE_SIMPLE_1,
    EffectType.SMOKE_SIMPLE_2,
    EffectType.SMOKE_SIMPLE_3,
    EffectType.ROCK_BREAK,
    EffectType.LIGHT_SPARK,
  ];

  const permanentEffects = [
    EffectType.DARK_AURA,
    EffectType.HOLY_LIGHT_AURA,
    EffectType.BUBBLE_SHIELD,
    EffectType.ROTATING_SHIELD,
    EffectType.CONFUSE1,
    EffectType.CONFUSE2,
    EffectType.REGEN,
    EffectType.ELECTRIC_AURA,
    EffectType.FIRE_AURA,
    EffectType.POISON_CLOUD,
  ];

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h6" sx={{ mb: 2, color: 'white' }}>
        Entity Effects (Debug)
      </Typography>

      {/* Current Effects */}
      {currentEffects.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: 'rgba(255,255,255,0.8)' }}>
            Active Effects ({currentEffects.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            {currentEffects.map(effectType => (
              <Chip
                key={effectType}
                label={effectType.replace(/_/g, ' ').replace(/-/g, ' ')}
                size="small"
                color="primary"
                onDelete={() => handleRemoveEffect(effectType)}
                deleteIcon={<DeleteIcon />}
                sx={{ 
                  backgroundColor: 'rgba(25, 118, 210, 0.3)',
                  color: 'white',
                  '& .MuiChip-deleteIcon': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            ))}
          </Box>
          <Button
            variant="outlined"
            size="small"
            onClick={handleClearAllEffects}
            sx={{ 
              color: 'rgba(255,255,255,0.7)',
              borderColor: 'rgba(255,255,255,0.3)',
              '&:hover': {
                borderColor: 'rgba(255,255,255,0.5)',
                backgroundColor: 'rgba(255,255,255,0.1)'
              }
            }}
          >
            Clear All Effects
          </Button>
        </Box>
      )}

      {/* Permanent Effects */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2, color: 'rgba(255,255,255,0.8)' }}>
          Permanent Effects (Looping)
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {permanentEffects.map(effectType => {
            const isActive = currentEffects.includes(effectType);
            return (
              <Button
                key={effectType}
                variant={isActive ? "contained" : "outlined"}
                size="small"
                onClick={() => isActive ? handleRemoveEffect(effectType) : handleAddEffect(effectType)}
                sx={{ 
                  color: isActive ? 'white' : 'rgba(255,255,255,0.7)',
                  borderColor: 'rgba(255,255,255,0.3)',
                  backgroundColor: isActive ? 'rgba(25, 118, 210, 0.6)' : 'transparent',
                  '&:hover': {
                    borderColor: 'rgba(255,255,255,0.5)',
                    backgroundColor: isActive ? 'rgba(25, 118, 210, 0.8)' : 'rgba(255,255,255,0.1)'
                  },
                  fontSize: '0.7rem',
                  minWidth: 'auto',
                  px: 1,
                }}
              >
                {effectType.replace(/_/g, ' ').replace(/-/g, ' ')}
              </Button>
            );
          })}
        </Box>
      </Box>

      {/* Temporary Effects (for testing) */}
      <Box>
        <Typography variant="subtitle2" sx={{ mb: 2, color: 'rgba(255,255,255,0.8)' }}>
          Temporary Effects (Test Trigger)
        </Typography>
        <Typography variant="caption" sx={{ mb: 2, color: 'rgba(255,255,255,0.5)', display: 'block' }}>
          These effects play once and disappear. Click to trigger at entity position.
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {temporaryEffects.map(effectType => (
            <Button
              key={effectType}
              variant="outlined"
              size="small"
              onClick={() => {
                // Trigger temporary effect at entity position
                const entity = snap.entities.summaries[selectedEntityId];
                if (entity) {
                  const entityMapping = snap.entities.spriteMappings[selectedEntityId];
                  const position = entityMapping?.visualPosition || { x: entity.position[0], y: entity.position[1] };
                  
                  // Import gameManager dynamically to avoid circular imports
                  import('../../../game/GameManager').then(({ gameManager }) => {
                    const effectRenderer = gameManager.getEffectRenderer();
                    effectRenderer.triggerEffect(effectType, position, {
                      callback: () => console.log(`[EffectsPanel] ${effectType} completed`)
                    });
                  });
                }
              }}
              sx={{ 
                color: 'rgba(255,255,255,0.7)',
                borderColor: 'rgba(255,255,255,0.3)',
                '&:hover': {
                  borderColor: 'rgba(255,255,255,0.5)',
                  backgroundColor: 'rgba(255,255,255,0.1)'
                },
                fontSize: '0.7rem',
                minWidth: 'auto',
                px: 1,
              }}
            >
              {effectType.replace(/_/g, ' ').replace(/-/g, ' ')}
            </Button>
          ))}
        </Box>
      </Box>
    </Box>
  );
};

// Helper component for sprite grid
const SpriteGrid: React.FC<{
  sprites: SpriteFolderName[];
  selectedSprite?: string;
  onSpriteChange: (event: React.MouseEvent<HTMLElement>, sprite: SpriteFolderName | null) => void;
}> = ({ sprites, selectedSprite, onSpriteChange }) => {
  if (sprites.length === 0) {
    return (
      <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)', textAlign: 'center', py: 2 }}>
        No sprites available in this category
      </Typography>
    );
  }

  return (
    <ToggleButtonGroup
      value={selectedSprite}
      exclusive
      onChange={onSpriteChange}
      aria-label="sprite selection"
      size="small"
      sx={{
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 1,
        '& .MuiToggleButton-root': {
          color: 'white',
          borderColor: 'rgba(255, 255, 255, 0.3)',
          justifyContent: 'flex-start',
          px: 1,
          py: 1,
          width: '140px', // Fixed width for consistency
          height: '90px', // Fixed height for consistency
          display: 'flex',
          alignItems: 'center',
          flexDirection: 'column',
          gap: 0.5,
          '&.Mui-selected': {
            backgroundColor: 'rgba(25, 118, 210, 0.3)',
            color: 'white',
            '&:hover': {
              backgroundColor: 'rgba(25, 118, 210, 0.4)',
            },
          },
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          },
        },
      }}
    >
      {sprites.map(sprite => (
        <ToggleButton key={sprite} value={sprite} aria-label={sprite}>
          <SpritePreview spriteFolder={sprite} isSelected={selectedSprite === sprite} />
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
};

export default SpriteEditorPanel; 