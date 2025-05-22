import { proxy } from 'valtio';

interface EventQueueState {
  isRefreshing: boolean;
}

// Create the store
export const eventQueueStore = proxy<EventQueueState>({
  isRefreshing: false
});

// Create actions
export const eventQueueActions = {
  // Reference to the refresh callback
  refreshCallback: () => Promise.resolve(),

  // Set the refresh callback
  setRefreshCallback: (callback: () => Promise<void>) => {
    eventQueueActions.refreshCallback = callback;
  },

  // Debounced refresh function
  refreshTimeoutId: undefined as NodeJS.Timeout | undefined,

  // Trigger a refresh with debouncing
  refresh: () => {
    if (eventQueueActions.refreshTimeoutId) {
      clearTimeout(eventQueueActions.refreshTimeoutId);
    }

    eventQueueActions.refreshTimeoutId = setTimeout(async () => {
      if (!eventQueueStore.isRefreshing) {
        eventQueueStore.isRefreshing = true;
        try {
          await eventQueueActions.refreshCallback();
        } finally {
          eventQueueStore.isRefreshing = false;
        }
      }
    }, 100); // Small delay to batch rapid updates
  },

  // Cleanup function
  cleanup: () => {
    if (eventQueueActions.refreshTimeoutId) {
      clearTimeout(eventQueueActions.refreshTimeoutId);
    }
  }
}; 