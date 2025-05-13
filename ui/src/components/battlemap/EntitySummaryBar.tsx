import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Avatar,
  Tooltip,
  IconButton,
} from '@mui/material';
import { EntitySummary } from '../../models/character';
import { characterStore, characterActions } from '../../store/characterStore';
import { useSnapshot } from 'valtio';
import TargetIcon from '@mui/icons-material/RadioButtonChecked';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import PersonIcon from '@mui/icons-material/Person';

const SIDEBAR_WIDTH = '280px';
const COLLAPSED_WIDTH = '40px';

interface EntitySummaryBarProps {
  onSelectTarget: (entityId: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onSwitchToCharacter: () => void;
}

const EntitySummaryBar: React.FC<EntitySummaryBarProps> = ({ 
  onSelectTarget, 
  isCollapsed, 
  onToggleCollapse,
  onSwitchToCharacter
}) => {
  const snap = useSnapshot(characterStore);
  const summaries = Object.values(snap.summaries);
  const currentCharacter = snap.character;
  const selectedEntity = characterActions.getSelectedEntity();
  const displayedEntity = characterActions.getDisplayedEntity();

  return (
    <Box
      sx={{
        position: 'relative',
        height: 'calc(100vh - 64px)',
        width: isCollapsed ? COLLAPSED_WIDTH : SIDEBAR_WIDTH,
        transition: 'width 0.3s ease-in-out',
        display: 'flex',
        zIndex: 1200,
      }}
    >
      <Paper
        sx={{
          width: SIDEBAR_WIDTH,
          height: '100%',
          overflowY: 'auto',
          transform: isCollapsed ? `translateX(${SIDEBAR_WIDTH})` : 'none',
          transition: 'transform 0.3s ease-in-out',
          borderLeft: 1,
          borderColor: 'divider',
          borderRadius: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          color: 'white',
          display: 'flex',
          flexDirection: 'column',
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            backgroundColor: 'rgba(0, 0, 0, 0.2)',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: 'rgba(255, 255, 255, 0.3)',
            borderRadius: '4px',
          },
        }}
      >
        {/* Header with switch button */}
        <Box sx={{ 
          p: 2, 
          borderBottom: 1, 
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <Typography variant="h6">Entities</Typography>
          <Tooltip title="Switch to Character Sheet">
            <IconButton 
              onClick={onSwitchToCharacter}
              sx={{ color: 'white' }}
            >
              <PersonIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Entity List */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: 1, gap: 1, display: 'flex', flexDirection: 'column' }}>
          {summaries.map((entity) => (
            <Paper
              key={entity.uuid}
              sx={{
                p: 1,
                backgroundColor: selectedEntity?.uuid === entity.uuid 
                  ? 'rgba(25, 118, 210, 0.4)'
                  : displayedEntity?.uuid === entity.uuid
                    ? 'rgba(255, 255, 255, 0.15)'
                    : 'rgba(255, 255, 255, 0.05)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                '&:hover': {
                  backgroundColor: selectedEntity?.uuid === entity.uuid 
                    ? 'rgba(25, 118, 210, 0.5)'
                    : 'rgba(255, 255, 255, 0.2)',
                },
              }}
              onClick={() => onSelectTarget(entity.uuid)}
            >
              {/* Entity Icon/Avatar */}
              <Avatar
                sx={{
                  width: 40,
                  height: 40,
                  backgroundColor: 'primary.main',
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
                  {selectedEntity?.uuid === entity.uuid && (
                    <Tooltip title="Selected Target">
                      <TargetIcon sx={{ fontSize: 14, color: 'primary.main' }} />
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
            </Paper>
          ))}
        </Box>
      </Paper>

      {/* Toggle button */}
      <Paper
        sx={{
          position: 'absolute',
          left: isCollapsed ? 0 : -40,
          top: '50%',
          transform: 'translateY(-50%)',
          width: COLLAPSED_WIDTH,
          height: '80px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          borderTopLeftRadius: '8px',
          borderBottomLeftRadius: '8px',
          borderTopRightRadius: '0',
          borderBottomRightRadius: '0',
          zIndex: 1,
          boxShadow: 2,
          transition: 'left 0.3s ease-in-out',
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
        }}
        onClick={onToggleCollapse}
      >
        <IconButton sx={{ color: 'white' }}>
          {isCollapsed ? <ChevronLeftIcon /> : <ChevronRightIcon />}
        </IconButton>
      </Paper>
    </Box>
  );
};

export default EntitySummaryBar; 