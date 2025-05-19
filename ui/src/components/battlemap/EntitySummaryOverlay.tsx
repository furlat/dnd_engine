import React from 'react';
import {
  Box,
  Typography,
  Avatar,
  Tooltip,
  Paper
} from '@mui/material';
import { EntitySummary } from '../../models/character';
import { ReadonlyEntitySummary } from '../../models/readonly';
import TargetIcon from '@mui/icons-material/RadioButtonChecked';
import ShieldIcon from '@mui/icons-material/Shield';
import SwordIcon from '@mui/icons-material/Gavel';
import { characterActions } from '../../store/characterStore';

interface EntitySummaryOverlayProps {
  entity: EntitySummary | ReadonlyEntitySummary;
  isSelected: boolean;
  isDisplayed: boolean;
  onSelectTarget: (entityId: string) => void;
  index: number;
}

const EntitySummaryOverlay: React.FC<EntitySummaryOverlayProps> = ({
  entity,
  isSelected,
  isDisplayed,
  onSelectTarget,
  index
}) => {
  // Check if this entity is targeting another entity
  const hasTarget = !!entity.target_entity_uuid;
  
  // Handle selecting this entity
  const handleSelectEntity = async () => {
    console.log(`[ENTITY-OVERLAY] Selecting entity: ${entity.uuid}`);
    
    // First select the entity and update the store
    await characterActions.setSelectedEntity(entity.uuid);
    
    // Then notify parent component
    if (onSelectTarget) {
      onSelectTarget(entity.uuid);
    }
  };
  
  return (
    <Paper
      elevation={0}
      sx={{
        position: 'absolute',
        left: 16,
        top: 16 + (index * 90), // Stack vertically with spacing
        width: 260,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(5px)',
        color: 'white',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
        },
        borderRadius: 1,
        border: isSelected 
          ? '1px solid rgba(25, 118, 210, 0.7)'
          : isDisplayed
            ? '1px solid rgba(255, 255, 255, 0.3)'
            : '1px solid rgba(255, 255, 255, 0.1)',
      }}
      onClick={handleSelectEntity}
    >
      <Box sx={{ p: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        {/* Entity Icon/Avatar */}
        <Avatar
          sx={{
            width: 40,
            height: 40,
            backgroundColor: isSelected ? 'primary.main' : 'rgba(255,255,255,0.2)',
          }}
          src={entity.sprite_name ? `/sprites/${entity.sprite_name}` : undefined}
        >
          {!entity.sprite_name && entity.name[0]}
        </Avatar>

        {/* Entity Info */}
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2" noWrap>
              {entity.name}
            </Typography>
            {isSelected && (
              <Tooltip title="Selected Attacker">
                <SwordIcon sx={{ fontSize: 14, color: 'primary.main' }} />
              </Tooltip>
            )}
            {isDisplayed && !isSelected && (
              <Tooltip title="Selected Target">
                <TargetIcon sx={{ fontSize: 14, color: 'error.main' }} />
              </Tooltip>
            )}
            {hasTarget && (
              <Tooltip title="Has Target">
                <ShieldIcon sx={{ fontSize: 14, color: 'warning.main' }} />
              </Tooltip>
            )}
          </Box>

          {/* Stats Bar */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 0.5 }}>
            {/* HP Bar */}
            <Tooltip title="Hit Points">
              <Box sx={{ flex: 1 }}>
                <Box sx={{ 
                  width: '100%', 
                  height: 4, 
                  backgroundColor: 'rgba(255, 0, 0, 0.3)',
                  borderRadius: 1,
                }}>
                  <Box sx={{
                    width: `${(entity.current_hp / entity.max_hp) * 100}%`,
                    height: '100%',
                    backgroundColor: '#ff4444',
                    borderRadius: 1,
                    transition: 'width 0.3s ease',
                  }} />
                </Box>
                <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                  {entity.current_hp}/{entity.max_hp}
                </Typography>
              </Box>
            </Tooltip>

            {/* AC Badge */}
            {entity.armor_class !== undefined && (
              <Tooltip title="Armor Class">
                <Box sx={{
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  borderRadius: '50%',
                  width: 24,
                  height: 24,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                    {entity.armor_class}
                  </Typography>
                </Box>
              </Tooltip>
            )}
          </Box>
        </Box>
      </Box>
    </Paper>
  );
};

export default EntitySummaryOverlay; 