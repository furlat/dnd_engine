import React, { useMemo, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Avatar,
  Tooltip,
} from '@mui/material';
import { battlemapStore, battlemapActions } from '../../../store/battlemapStore';
import { useSnapshot } from 'valtio';
import TargetIcon from '@mui/icons-material/RadioButtonChecked';
import { EntitySummary } from '../../../types/common';
import { useEntitySelection } from '../../../hooks/battlemap';

// Extracted to a separate component to prevent entire list re-rendering
const EntityCard = React.memo(({ 
  entity, 
  isSelected, 
  isDisplayed,
  onSelect
}: { 
  entity: EntitySummary, 
  isSelected: boolean,
  isDisplayed: boolean,
  onSelect: (id: string) => void 
}) => {
  const handleClick = useCallback(() => {
    onSelect(entity.uuid);
  }, [entity.uuid, onSelect]);

  // Memoize health percentage calculation
  const healthPercentage = useMemo(() => 
    (entity.current_hp / entity.max_hp) * 100, 
    [entity.current_hp, entity.max_hp]
  );

  // Memoize health color based on percentage
  const healthColor = useMemo(() => {
    if (healthPercentage > 50) return '#4caf50';
    if (healthPercentage > 25) return '#ff9800';
    return '#f44336';
  }, [healthPercentage]);

  // Memoize health text color
  const healthTextColor = useMemo(() => {
    if (healthPercentage > 50) return '#81c784';
    if (healthPercentage > 25) return '#ffb74d';
    return '#e57373';
  }, [healthPercentage]);

  return (
    <Paper
      sx={{
        p: 1,
        backgroundColor: isSelected 
          ? 'rgba(25, 118, 210, 0.6)'
          : isDisplayed
            ? 'rgba(30, 30, 30, 0.9)'
            : 'rgba(15, 15, 15, 0.7)',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        border: '1px solid',
        borderColor: isSelected 
          ? 'rgba(25, 118, 210, 0.8)'
          : 'rgba(255, 255, 255, 0.1)',
        '&:hover': {
          backgroundColor: isSelected 
            ? 'rgba(25, 118, 210, 0.7)'
            : 'rgba(50, 50, 50, 0.8)',
          borderColor: 'rgba(255, 255, 255, 0.3)',
        },
      }}
      onClick={handleClick}
      elevation={isSelected ? 8 : 2}
    >
      {/* Entity Icon/Avatar */}
      <Avatar
        sx={{
          width: 36,
          height: 36,
          backgroundColor: isSelected ? 'primary.main' : 'rgba(50, 50, 50, 0.8)',
          border: '2px solid',
          borderColor: isSelected ? 'primary.light' : 'rgba(255, 255, 255, 0.2)',
        }}
        src={entity.sprite_name ? `/sprites/${entity.sprite_name}` : undefined}
      >
        {!entity.sprite_name && entity.name[0]}
      </Avatar>

      {/* Entity Info */}
      <Box sx={{ flex: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography 
            variant="subtitle2" 
            noWrap
            sx={{
              color: isSelected ? '#fff' : 'rgba(255, 255, 255, 0.9)',
              fontWeight: isSelected ? 'bold' : 'normal',
            }}
          >
            {entity.name}
          </Typography>
          {isSelected && (
            <Tooltip title="Selected Target">
              <TargetIcon sx={{ fontSize: 14, color: '#4fc3f7' }} />
            </Tooltip>
          )}
        </Box>

        {/* HP Bar */}
        <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
          <Box sx={{ flex: 1 }}>
            <Box sx={{ 
              width: '100%', 
              height: 4, 
              backgroundColor: 'rgba(255, 0, 0, 0.2)',
              borderRadius: 1,
              boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.3)',
            }}>
              <Box sx={{
                width: `${healthPercentage}%`,
                height: '100%',
                backgroundColor: healthColor,
                borderRadius: 1,
                transition: 'width 0.3s ease, background-color 0.3s ease',
                boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
              }} />
            </Box>
            <Typography 
              variant="caption" 
              sx={{ 
                fontSize: '0.7rem',
                color: healthTextColor
              }}
            >
              {entity.current_hp}/{entity.max_hp}
            </Typography>
          </Box>
          
          {/* AC Badge */}
          {entity.armor_class !== undefined && (
            <Tooltip title="Armor Class">
              <Box sx={{
                backgroundColor: 'rgba(30, 30, 30, 0.9)',
                borderRadius: '50%',
                width: 24,
                height: 24,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                ml: 1,
                border: '1px solid rgba(255, 255, 255, 0.2)',
              }}>
                <Typography 
                  variant="caption" 
                  sx={{ 
                    fontSize: '0.7rem',
                    color: '#90caf9', // Light blue for AC
                    fontWeight: 'bold',
                  }}
                >
                  {entity.armor_class}
                </Typography>
              </Box>
            </Tooltip>
          )}
        </Box>
      </Box>
    </Paper>
  );
});

/**
 * Component that renders a fixed panel with all entity summaries
 * Always visible, allows clicking on entities to select them
 * Optimized for performance with memoization
 */
const EntitySummaryOverlays: React.FC = () => {
  const snap = useSnapshot(battlemapStore, { sync: true });
  const { selectEntity } = useEntitySelection();
  
  // Memoize expensive calculations
  const summaries = useMemo(() => 
    Object.values(snap.entities.summaries) as EntitySummary[], 
    [snap.entities.summaries]
  );
  
  const selectedEntityId = useMemo(() => 
    snap.entities.selectedEntityId, 
    [snap.entities.selectedEntityId]
  );
  
  const displayedEntityId = useMemo(() => 
    snap.entities.displayedEntityId, 
    [snap.entities.displayedEntityId]
  );

  // Memoize handler
  const handleSelectEntity = useCallback((entityId: string) => {
    selectEntity(entityId);
  }, [selectEntity]);
  
  // Memoize the entity list to prevent unnecessary re-renders
  const entityList = useMemo(() => (
    summaries.map((entity) => (
      <EntityCard
        key={entity.uuid}
        entity={entity}
        isSelected={entity.uuid === selectedEntityId}
        isDisplayed={entity.uuid === displayedEntityId && entity.uuid !== selectedEntityId}
        onSelect={handleSelectEntity}
      />
    ))
  ), [summaries, selectedEntityId, displayedEntityId, handleSelectEntity]);
  
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        pointerEvents: 'auto',
        padding: 2,
        '&::-webkit-scrollbar': {
          width: '8px',
        },
        '&::-webkit-scrollbar-track': {
          backgroundColor: 'rgba(0, 0, 0, 0.2)',
        },
        '&::-webkit-scrollbar-thumb': {
          backgroundColor: 'rgba(255, 255, 255, 0.2)',
          borderRadius: '4px',
        },
      }}
    >
      {/* Simple heading */}
      <Typography 
        variant="h6" 
        sx={{ 
          color: '#fff', 
          textShadow: '0 1px 3px rgba(0,0,0,0.8)',
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          px: 2,
          py: 1,
          borderRadius: 1,
          mb: 1
        }}
      >
        Entities
      </Typography>
      
      {/* Direct entity list without paper container */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {entityList}
      </Box>
    </Box>
  );
};

export default React.memo(EntitySummaryOverlays); 