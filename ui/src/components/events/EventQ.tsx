import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
  CircularProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import { useSnapshot } from 'valtio';
import { eventQueueStore, eventQueueActions, formatTime } from '../../store/eventQueueStore';

const SIDEBAR_WIDTH = '350px';
const COLLAPSED_WIDTH = '40px';

// Event types (imported from store)
interface Event {
  uuid: string;
  lineage_uuid: string;
  name: string;
  timestamp: string;
  event_type: string;
  phase: string;
  status_message: string | null;
  source_entity_uuid: string;
  source_entity_name: string | null;
  target_entity_uuid: string | null;
  target_entity_name: string | null;
  child_events: Event[];
  phase_events?: Event[];
  is_lineage_group?: boolean;
}

interface EventQProps {
  // No external props needed - everything is in Valtio store
}

const EventItem: React.FC<{ event: Event, depth?: number }> = React.memo(({ event, depth = 0 }) => {
  // Use local React state only for UI expansion (doesn't affect global state)
  const [expanded, setExpanded] = React.useState(false);
  const hasChildren = event.child_events && event.child_events.length > 0;
  const hasPhases = event.is_lineage_group && event.phase_events && event.phase_events.length > 0;
  
  const renderEventContent = (event: Event, showPhase: boolean = true) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography variant="body1" component="span">
        {event.name}
      </Typography>
      {showPhase && (
        <Typography variant="caption" color="text.secondary" component="span">
          ({event.phase})
        </Typography>
      )}
    </Box>
  );

  return (
    <>
      <ListItem
        sx={{
          pl: 2 + (depth * 2),
          borderLeft: depth > 0 ? '2px solid rgba(0, 0, 0, 0.1)' : 'none',
        }}
      >
        <ListItemText
          primary={renderEventContent(event, !event.is_lineage_group)}
          secondary={
            <>
              <Typography variant="caption" display="block" color="text.secondary">
                {formatTime(event.timestamp)} - {event.event_type}
                {!event.is_lineage_group && ` (${event.phase})`}
              </Typography>
              {event.status_message && (
                <Typography variant="caption" display="block" color="text.secondary">
                  {event.status_message}
                </Typography>
              )}
              {(event.source_entity_name || event.target_entity_name) && (
                <Typography variant="caption" display="block" color="text.secondary">
                  {event.source_entity_name} → {event.target_entity_name || 'none'}
                </Typography>
              )}
            </>
          }
        />
        {(hasChildren || hasPhases) && (
          <IconButton
            size="small"
            onClick={() => setExpanded(!expanded)}
            sx={{ transform: expanded ? 'rotate(180deg)' : 'none' }}
          >
            <ExpandMoreIcon />
          </IconButton>
        )}
      </ListItem>
      
      {/* Show phases when expanded */}
      {expanded && hasPhases && (
        <Box>
          {event.phase_events!.map((phaseEvent) => (
            <Box key={phaseEvent.uuid}>
              <EventItem event={phaseEvent} depth={depth + 1} />
            </Box>
          ))}
        </Box>
      )}
      
      {/* Show child events when expanded */}
      {expanded && hasChildren && !event.is_lineage_group && (
        <Box>
          {event.child_events.map((childEvent) => (
            <EventItem key={childEvent.uuid} event={childEvent} depth={depth + 1} />
          ))}
        </Box>
      )}
    </>
  );
});

const EventQ: React.FC<EventQProps> = () => {
  // ONLY use Valtio state - no React state that could interfere with game engine
  const snap = useSnapshot(eventQueueStore);
  
  // Get filtered events from store
  const filteredEvents = eventQueueActions.getFilteredEvents();

  // Start polling when component mounts, stop when unmounts
  React.useEffect(() => {
    console.log('[EventQ] Component mounted - starting isolated polling');
    eventQueueActions.startPolling();
    
    return () => {
      console.log('[EventQ] Component unmounting - stopping polling');
      eventQueueActions.stopPolling();
    };
  }, []);

  // Handlers that only call Valtio actions (no React state updates)
  const handleToggleCollapse = React.useCallback(() => {
    eventQueueActions.toggleCollapse();
  }, []);

  const handleRefreshClick = React.useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    eventQueueActions.refresh();
  }, []);

  const handleEntityChange = React.useCallback((entityId: string) => {
    eventQueueActions.setSelectedEntity(entityId);
  }, []);

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 64,
        right: 0,
        height: 'calc(100vh - 64px)',
        width: snap.isCollapsed ? COLLAPSED_WIDTH : SIDEBAR_WIDTH,
        transition: 'width 0.3s ease-in-out',
        display: 'flex',
        zIndex: 1200,
      }}
    >
      {/* Toggle button */}
      <Paper
        sx={{
          position: 'absolute',
          left: snap.isCollapsed ? 0 : -40,
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
          transition: 'left 0.3s ease-in-out'
        }}
        onClick={handleToggleCollapse}
      >
        <IconButton>
          {snap.isCollapsed ? <ChevronLeftIcon /> : <ChevronRightIcon />}
        </IconButton>
      </Paper>

      <Paper
        sx={{
          width: SIDEBAR_WIDTH,
          height: '100%',
          transform: snap.isCollapsed ? `translateX(${SIDEBAR_WIDTH})` : 'none',
          transition: 'transform 0.3s ease-in-out',
          borderLeft: 1,
          borderColor: 'divider',
          borderRadius: 0,
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            backgroundColor: 'background.paper',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: 'grey.400',
            borderRadius: '4px',
          },
        }}
      >
        <Box sx={{ 
          p: 2,
          borderBottom: 1, 
          borderColor: 'divider',
          position: 'sticky',
          top: 0,
          bgcolor: 'background.paper',
          zIndex: 1,
        }}>
          <Box sx={{ 
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2
          }}>
            <Typography variant="h6">Event Queue</Typography>
            <Tooltip title="Refresh events">
              <IconButton onClick={handleRefreshClick} disabled={snap.isLoading}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
          
          <FormControl fullWidth size="small">
            <InputLabel>Filter by Entity</InputLabel>
            <Select
              value={snap.selectedEntityId}
              onChange={(e) => handleEntityChange(e.target.value)}
              label="Filter by Entity"
            >
              <MenuItem value="">
                <em>All Events</em>
              </MenuItem>
              {snap.entityOptions.map((entity) => (
                <MenuItem key={entity.uuid} value={entity.uuid}>
                  {entity.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
        
        {snap.error && (
          <Box sx={{ p: 2, bgcolor: 'error.light', color: 'error.contrastText' }}>
            <Typography>{snap.error}</Typography>
          </Box>
        )}
        
        <List
          sx={{
            '& .MuiListItem-root': {
              borderBottom: '1px solid rgba(0, 0, 0, 0.05)',
            },
          }}
        >
          {snap.isLoading && filteredEvents.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            filteredEvents.map((event) => (
              <EventItem key={event.uuid} event={event} />
            ))
          )}
        </List>
      </Paper>
    </Box>
  );
};

export default EventQ; 