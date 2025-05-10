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
  Slide,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import { useEventQueue } from '../../contexts/EventQueueContext';

// Helper function to format time
const formatTime = (timestamp: string) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { 
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

// Helper function to sort events recursively
const sortEventsRecursively = (events: Event[]): Event[] => {
  return events
    .map(event => ({
      ...event,
      child_events: sortEventsRecursively(event.child_events || [])
    }))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
};

// Helper function to group events by lineage
const groupEventsByLineage = (events: Event[]): Event[] => {
  const lineageGroups = new Map<string, Event[]>();
  
  // Group events by lineage_uuid
  events.forEach(event => {
    if (!lineageGroups.has(event.lineage_uuid)) {
      lineageGroups.set(event.lineage_uuid, []);
    }
    lineageGroups.get(event.lineage_uuid)?.push(event);
  });
  
  // Convert each lineage group into a single event with phases
  return Array.from(lineageGroups.values()).map(lineageEvents => {
    // Sort events in the lineage by timestamp
    const sortedLineageEvents = lineageEvents.sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    
    // Use the latest event as the base
    const latestEvent = sortedLineageEvents[sortedLineageEvents.length - 1];
    
    return {
      ...latestEvent,
      uuid: latestEvent.lineage_uuid, // Use lineage_uuid as the main identifier
      name: latestEvent.name,
      phase_events: sortedLineageEvents, // Store all phase events
      timestamp: sortedLineageEvents[0].timestamp, // Use first event's timestamp
      is_lineage_group: true // Flag to identify this as a lineage group
    };
  }).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
};

// Types for events
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
  phase_events?: Event[]; // New field for lineage phases
  is_lineage_group?: boolean; // Flag to identify lineage groups
}

// Add interface for entity selection
interface EntityOption {
  uuid: string;
  name: string;
}

const EventItem: React.FC<{ event: Event, depth?: number }> = ({ event, depth = 0 }) => {
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
};

const EventQ: React.FC = () => {
  const [events, setEvents] = React.useState<Event[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const [selectedEntity, setSelectedEntity] = React.useState<string>('');
  const [entityOptions, setEntityOptions] = React.useState<EntityOption[]>([]);
  const { setRefreshEvents } = useEventQueue();

  const fetchEvents = React.useCallback(async (fetchAll: boolean = false) => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/events/latest/${fetchAll ? 999999 : 20}?include_children=true`);
      if (!response.ok) {
        throw new Error('Failed to fetch events');
      }
      const data = await response.json();
      
      // Sort new events by timestamp and group by lineage
      const sortedNewEvents = groupEventsByLineage([...data]);
      
      // If this is the initial fetch (fetchAll is true), just set the events
      if (fetchAll) {
        setEvents(sortedNewEvents);
        return;
      }
      
      // For polling updates, check if we have any new events
      setEvents(prevEvents => {
        // Create Sets for both lineage UUIDs and individual event UUIDs
        const existingLineageUUIDs = new Set(prevEvents.map(event => event.uuid)); // For lineage groups
        const existingEventUUIDs = new Set(
          prevEvents.flatMap(event => 
            event.phase_events?.map(e => e.uuid) || []
          )
        ); // For individual events

        // Check if we have any new events by comparing both lineage and individual events
        const hasNewEvents = sortedNewEvents.some(event => {
          // Check if this is a new lineage
          if (!existingLineageUUIDs.has(event.uuid)) {
            return true;
          }
          // Check if any phase events are new
          return event.phase_events?.some(phaseEvent => 
            !existingEventUUIDs.has(phaseEvent.uuid)
          );
        });

        // If no new events, keep the previous state
        if (!hasNewEvents) {
          return prevEvents;
        }

        // If we have new events, merge them with existing ones
        const mergedEvents = [...prevEvents];
        
        sortedNewEvents.forEach(newEvent => {
          const existingEventIndex = mergedEvents.findIndex(e => e.uuid === newEvent.uuid);
          if (existingEventIndex === -1) {
            // This is a completely new lineage
            mergedEvents.push(newEvent);
          } else {
            // This is an existing lineage, merge phase events
            const existingEvent = mergedEvents[existingEventIndex];
            const existingPhaseUUIDs = new Set(existingEvent.phase_events?.map(e => e.uuid) || []);
            
            // Add any new phase events
            const updatedPhaseEvents = [
              ...(existingEvent.phase_events || []),
              ...(newEvent.phase_events?.filter(e => !existingPhaseUUIDs.has(e.uuid)) || [])
            ];
            
            // Update the existing event with new phase events
            mergedEvents[existingEventIndex] = {
              ...existingEvent,
              phase_events: updatedPhaseEvents.sort((a, b) => 
                new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
              )
            };
          }
        });

        // Sort the merged events by timestamp
        return mergedEvents.sort((a, b) => 
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
      });
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, []);

  // Handler for refresh button click
  const handleRefreshClick = React.useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    fetchEvents(false);
  }, [fetchEvents]);

  // Add function to fetch entities
  const fetchEntityOptions = React.useCallback(async () => {
    try {
      const response = await fetch('/api/entities');
      if (!response.ok) throw new Error('Failed to fetch entities');
      const data = await response.json();
      setEntityOptions(data);
    } catch (err) {
      console.error('Failed to fetch entity options:', err);
    }
  }, []);

  // Add entity filter to events
  const filteredEvents = React.useMemo(() => {
    if (!selectedEntity) return events;
    return events.filter(event => 
      event.source_entity_uuid === selectedEntity || 
      event.target_entity_uuid === selectedEntity
    );
  }, [events, selectedEntity]);

  // Register the fetchEvents function with the context
  React.useEffect(() => {
    setRefreshEvents(fetchEvents);
  }, [fetchEvents, setRefreshEvents]);

  // Initial fetch - get all events on first load
  React.useEffect(() => {
    fetchEvents(true); // Fetch all events initially
    
    // Set up polling every 5 seconds with regular limit
    const interval = setInterval(() => fetchEvents(false), 5000);
    return () => clearInterval(interval);
  }, [fetchEvents]);

  // Update useEffect to fetch entities
  React.useEffect(() => {
    fetchEntityOptions();
  }, [fetchEntityOptions]);

  return (
    <Box sx={{ position: 'relative', height: '100vh' }}>
      <Slide direction="left" in={!isCollapsed} mountOnEnter unmountOnExit>
        <Paper
          sx={{
            height: '100vh',
            width: '350px',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <Box sx={{ 
            minHeight: {
              xs: 56,  // mobile height
              sm: 64   // desktop height
            },
            px: 2,     // horizontal padding
            borderBottom: 1, 
            borderColor: 'divider', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            flexDirection: 'column',
            py: 1
          }}>
            <Box sx={{ 
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <Typography variant="h6">Event Queue</Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Tooltip title="Refresh events">
                  <IconButton onClick={handleRefreshClick} disabled={loading}>
                    <RefreshIcon />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Collapse">
                  <IconButton onClick={() => setIsCollapsed(true)}>
                    <ChevronRightIcon />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
            
            <FormControl fullWidth size="small" sx={{ mt: 1 }}>
              <InputLabel>Filter by Entity</InputLabel>
              <Select
                value={selectedEntity}
                onChange={(e) => setSelectedEntity(e.target.value)}
                label="Filter by Entity"
              >
                <MenuItem value="">
                  <em>All Events</em>
                </MenuItem>
                {entityOptions.map((entity) => (
                  <MenuItem key={entity.uuid} value={entity.uuid}>
                    {entity.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
          
          {error && (
            <Box sx={{ p: 2, bgcolor: 'error.light', color: 'error.contrastText' }}>
              <Typography>{error}</Typography>
            </Box>
          )}
          
          <List
            sx={{
              flex: 1,
              overflow: 'auto',
              '& .MuiListItem-root': {
                borderBottom: '1px solid rgba(0, 0, 0, 0.05)',
              },
            }}
          >
            {loading && filteredEvents.length === 0 ? (
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
      </Slide>

      {/* Collapsed state button */}
      <Paper
        sx={{
          position: 'absolute',
          right: isCollapsed ? 0 : '-40px',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '40px',
          height: '80px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          transition: 'right 0.3s ease-in-out',
          borderTopLeftRadius: '8px',
          borderBottomLeftRadius: '8px',
          borderTopRightRadius: '0px',
          borderBottomRightRadius: '0px',
          zIndex: 1,
        }}
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <IconButton>
          {isCollapsed ? <ChevronLeftIcon /> : <ChevronRightIcon />}
        </IconButton>
      </Paper>
    </Box>
  );
};

export default EventQ; 