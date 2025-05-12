import React, { createContext, useContext, useCallback, useRef } from 'react';

interface EventQueueContextType {
  refreshEvents: () => void;
  setRefreshEvents: (callback: () => Promise<void>) => void;
  isRefreshing: boolean;
}

// Create a no-op function that returns a resolved promise
const noopAsync = () => Promise.resolve();

const EventQueueContext = createContext<EventQueueContextType>({
  refreshEvents: () => {},
  setRefreshEvents: () => {},
  isRefreshing: false
});

export const EventQueueProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const refreshTimeoutRef = useRef<NodeJS.Timeout>();
  const refreshCallbackRef = useRef<() => Promise<void>>(noopAsync);

  // Debounced refresh to prevent multiple rapid refreshes
  const debouncedRefresh = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
    }
    
    refreshTimeoutRef.current = setTimeout(() => {
      if (!isRefreshing) {
        setIsRefreshing(true);
        refreshCallbackRef.current().finally(() => {
          setIsRefreshing(false);
        });
      }
    }, 100); // Small delay to batch rapid updates
  }, [isRefreshing]);

  const setRefreshEvents = useCallback((callback: () => Promise<void>) => {
    refreshCallbackRef.current = callback || noopAsync;
  }, []);

  // Cleanup timeout on unmount
  React.useEffect(() => {
    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current);
      }
    };
  }, []);

  return (
    <EventQueueContext.Provider value={{ 
      refreshEvents: debouncedRefresh, 
      setRefreshEvents,
      isRefreshing 
    }}>
      {children}
    </EventQueueContext.Provider>
  );
};

export const useEventQueue = () => useContext(EventQueueContext); 