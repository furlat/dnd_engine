import { proxy } from 'valtio';

// Event types
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

interface EntityOption {
  uuid: string;
  name: string;
}

interface EventQueueState {
  // UI State
  isCollapsed: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Data
  events: Event[];
  entityOptions: EntityOption[];
  selectedEntityId: string;
  
  // Internal
  pollingInterval: NodeJS.Timeout | null;
  lastFetchTime: number;
}

// Create the isolated store
export const eventQueueStore = proxy<EventQueueState>({
  // UI State
  isCollapsed: false,
  isLoading: false,
  error: null,
  
  // Data
  events: [],
  entityOptions: [],
  selectedEntityId: '',
  
  // Internal
  pollingInterval: null,
  lastFetchTime: 0,
});

// Helper functions (pure, no side effects)
const formatTime = (timestamp: string) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { 
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const groupEventsByLineage = (events: Event[]): Event[] => {
  const lineageGroups = new Map<string, Event[]>();
  
  events.forEach(event => {
    if (!lineageGroups.has(event.lineage_uuid)) {
      lineageGroups.set(event.lineage_uuid, []);
    }
    lineageGroups.get(event.lineage_uuid)?.push(event);
  });
  
  return Array.from(lineageGroups.values()).map(lineageEvents => {
    const sortedLineageEvents = lineageEvents.sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    
    const latestEvent = sortedLineageEvents[sortedLineageEvents.length - 1];
    
    return {
      ...latestEvent,
      uuid: latestEvent.lineage_uuid,
      name: latestEvent.name,
      phase_events: sortedLineageEvents,
      timestamp: sortedLineageEvents[0].timestamp,
      is_lineage_group: true
    };
  }).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
};

// Isolated actions (no React dependencies)
export const eventQueueActions = {
  // UI Actions
  toggleCollapse: () => {
    eventQueueStore.isCollapsed = !eventQueueStore.isCollapsed;
  },
  
  setSelectedEntity: (entityId: string) => {
    eventQueueStore.selectedEntityId = entityId;
  },
  
  // Data fetching (isolated from React)
  fetchEvents: async (fetchAll: boolean = false) => {
    try {
      eventQueueStore.isLoading = true;
      eventQueueStore.error = null;
      
      const response = await fetch(`/api/events/latest/${fetchAll ? 999999 : 20}?include_children=true`);
      if (!response.ok) {
        throw new Error('Failed to fetch events');
      }
      
      const data = await response.json();
      const sortedNewEvents = groupEventsByLineage([...data]);
      
      if (fetchAll) {
        eventQueueStore.events = sortedNewEvents;
        eventQueueStore.lastFetchTime = Date.now();
        return;
      }
      
      // For polling updates, check for new events
      const existingLineageUUIDs = new Set(eventQueueStore.events.map(event => event.uuid));
      const existingEventUUIDs = new Set(
        eventQueueStore.events.flatMap(event => 
          event.phase_events?.map(e => e.uuid) || []
        )
      );

      const hasNewEvents = sortedNewEvents.some(event => {
        if (!existingLineageUUIDs.has(event.uuid)) {
          return true;
        }
        return event.phase_events?.some(phaseEvent => 
          !existingEventUUIDs.has(phaseEvent.uuid)
        );
      });

      if (!hasNewEvents) {
        return; // No updates needed
      }

      // Merge new events
      const mergedEvents = [...eventQueueStore.events];
      
      sortedNewEvents.forEach(newEvent => {
        const existingEventIndex = mergedEvents.findIndex(e => e.uuid === newEvent.uuid);
        if (existingEventIndex === -1) {
          mergedEvents.push(newEvent);
        } else {
          const existingEvent = mergedEvents[existingEventIndex];
          const existingPhaseUUIDs = new Set(existingEvent.phase_events?.map(e => e.uuid) || []);
          
          const updatedPhaseEvents = [
            ...(existingEvent.phase_events || []),
            ...(newEvent.phase_events?.filter(e => !existingPhaseUUIDs.has(e.uuid)) || [])
          ];
          
          mergedEvents[existingEventIndex] = {
            ...existingEvent,
            phase_events: updatedPhaseEvents.sort((a, b) => 
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
            )
          };
        }
      });

      eventQueueStore.events = mergedEvents.sort((a, b) => 
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      eventQueueStore.lastFetchTime = Date.now();
      
    } catch (err) {
      eventQueueStore.error = err instanceof Error ? err.message : 'An error occurred';
      console.error('[EventQueue] Fetch error:', err);
    } finally {
      eventQueueStore.isLoading = false;
    }
  },
  
  fetchEntityOptions: async () => {
    try {
      const response = await fetch('/api/entities');
      if (!response.ok) throw new Error('Failed to fetch entities');
      const data = await response.json();
      eventQueueStore.entityOptions = data;
    } catch (err) {
      console.error('[EventQueue] Failed to fetch entity options:', err);
    }
  },
  
  // Polling management (isolated)
  startPolling: () => {
    // Stop existing polling
    eventQueueActions.stopPolling();
    
    // Initial fetch
    eventQueueActions.fetchEvents(true);
    eventQueueActions.fetchEntityOptions();
    
    // Set up polling every 1 second for reactive updates (safe now that it's decoupled)
    eventQueueStore.pollingInterval = setInterval(() => {
      eventQueueActions.fetchEvents(false);
    }, 500);
    
    console.log('[EventQueue] Polling started (isolated from React)');
  },
  
  stopPolling: () => {
    if (eventQueueStore.pollingInterval) {
      clearInterval(eventQueueStore.pollingInterval);
      eventQueueStore.pollingInterval = null;
    }
    console.log('[EventQueue] Polling stopped');
  },
  
  // Manual refresh
  refresh: () => {
    eventQueueActions.fetchEvents(false);
  },
  
  // Get filtered events (computed)
  getFilteredEvents: (): Event[] => {
    if (!eventQueueStore.selectedEntityId) {
      return eventQueueStore.events;
    }
    return eventQueueStore.events.filter(event => 
      event.source_entity_uuid === eventQueueStore.selectedEntityId || 
      event.target_entity_uuid === eventQueueStore.selectedEntityId
    );
  }
};

// Export helper functions for UI components
export { formatTime }; 