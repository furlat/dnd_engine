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
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSpriteEditor } from '../../../hooks/battlemap';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../../store';
import { SpriteFolderName, AnimationState, Direction } from '../../../types/battlemap_types';
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

const SpritePreview: React.FC<{ spriteFolder: string; isSelected: boolean }> = ({ 
  spriteFolder, 
  isSelected 
}) => {
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  
  // Try to load a preview image (first frame of Idle animation, South direction)
  useEffect(() => {
    const loadPreview = async () => {
      try {
        // Try to load the idle sprite sheet JSON to get the first frame
        const spritesheetPath = getSpriteSheetPath(spriteFolder, AnimationState.IDLE);
        const response = await fetch(spritesheetPath);
        
        if (response.ok) {
          const spritesheetData = await response.json();
          
          // Look for the first frame of south-facing idle animation
          // Pattern: Idle_S_1.png or similar
          const frames = Object.keys(spritesheetData.frames || {});
          const southIdleFrame = frames.find(frame => 
            frame.includes('_S_') && frame.includes('_1.')
          );
          
          if (southIdleFrame) {
            // Extract the frame from the spritesheet
            const baseImagePath = spritesheetPath.replace('.json', '.png');
            setPreviewSrc(baseImagePath); // For now, show the full spritesheet
            // TODO: Extract specific frame if needed
          } else {
            setPreviewSrc(null);
          }
        } else {
          setPreviewSrc(null);
        }
      } catch (error) {
        console.warn(`[SpritePreview] Could not load preview for ${spriteFolder}:`, error);
        setPreviewSrc(null);
      }
    };
    
    loadPreview();
  }, [spriteFolder]);

  return (
    <Box
      sx={{
        width: 48,
        height: 48,
        borderRadius: 1,
        mr: 1.5,
        transition: 'all 0.2s ease',
        opacity: isSelected ? 1 : 0.7,
        overflow: 'hidden',
        position: 'relative',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        backgroundColor: 'rgba(50, 50, 50, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        '&:hover': {
          opacity: 1,
          transform: 'scale(1.05)'
        },
      }}
    >
      {previewSrc ? (
        <img
          src={previewSrc}
          alt={`${spriteFolder} preview`}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'contain'
          }}
        />
      ) : (
        <PersonIcon sx={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: 32 }} />
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
  const humanoidSprites = availableSpriteFolders.filter(folder => 
    !folder.toLowerCase().includes('zombie') && 
    !folder.toLowerCase().includes('ork') &&
    !folder.toLowerCase().includes('golem')
  );
  
  const zombieSprites = availableSpriteFolders.filter(folder => 
    folder.toLowerCase().includes('zombie')
  );
  
  const monsterSprites = availableSpriteFolders.filter(folder => 
    folder.toLowerCase().includes('ork') || 
    folder.toLowerCase().includes('golem') ||
    folder.toLowerCase().includes('ogre')
  );

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
      </Box>
    </Paper>
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
          minWidth: '120px',
          maxWidth: '180px',
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
          <Typography variant="caption" sx={{ textAlign: 'center', fontSize: '0.7rem' }}>
            {sprite}
          </Typography>
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
};

export default SpriteEditorPanel; 