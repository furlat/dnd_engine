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

// Types for events
interface Event {
  uuid: string;
  name: string;
  timestamp: string;
  event_type: string;
  phase: string;
  status_message: string | null;
  source_entity_name: string | null;
  target_entity_name: string | null;
  child_events: Event[];
}

const EventItem: React.FC<{ event: Event, depth?: number }> = ({ event, depth = 0 }) => {
  const [expanded, setExpanded] = React.useState(false);
  const hasChildren = event.child_events && event.child_events.length > 0;
  
  return (
    <>
      <ListItem
        sx={{
          pl: 2 + (depth * 2),
          borderLeft: depth > 0 ? '2px solid rgba(0, 0, 0, 0.1)' : 'none',
        }}
      >
        <ListItemText
          primary={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {hasChildren && (
                <IconButton
                  size="small"
                  onClick={() => setExpanded(!expanded)}
                  sx={{ transform: expanded ? 'rotate(180deg)' : 'none' }}
                >
                  <ExpandMoreIcon />
                </IconButton>
              )}
              <Typography variant="body1" component="span">
                {event.name}
              </Typography>
            </Box>
          }
          secondary={
            <>
              <Typography variant="caption" display="block" color="text.secondary">
                {formatTime(event.timestamp)} - {event.event_type} ({event.phase})
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
      </ListItem>
      {expanded && hasChildren && (
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
  const { setRefreshEvents } = useEventQueue();

  const fetchEvents = React.useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/events/latest/20?include_children=true');
      if (!response.ok) {
        throw new Error('Failed to fetch events');
      }
      const data = await response.json();
      // Sort events by timestamp in descending order (newest first) at all levels
      const sortedEvents = sortEventsRecursively([...data])
        .reverse(); // Reverse top-level events to show newest first
      setEvents(sortedEvents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, []);

  // Register the fetchEvents function with the context
  React.useEffect(() => {
    setRefreshEvents(fetchEvents);
  }, [fetchEvents, setRefreshEvents]);

  // Initial fetch
  React.useEffect(() => {
    fetchEvents();
    
    // Set up polling every 5 seconds
    const interval = setInterval(fetchEvents, 5000);
    return () => clearInterval(interval);
  }, [fetchEvents]);

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
            p: 2, 
            borderBottom: 1, 
            borderColor: 'divider', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between' 
          }}>
            <Typography variant="h6">Event Queue</Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title="Refresh events">
                <IconButton onClick={fetchEvents} disabled={loading}>
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
            {loading && events.length === 0 ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                <CircularProgress />
              </Box>
            ) : (
              events.map((event) => (
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