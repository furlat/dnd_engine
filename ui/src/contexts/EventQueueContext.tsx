import React, { createContext, useContext } from 'react';
import { useEventQueue as useEventQueueStore } from '../hooks/useEventQueue';

interface EventQueueContextType {
  refreshEvents: () => void;
  setRefreshEvents: (callback: () => Promise<void>) => void;
  isRefreshing: boolean;
}

const EventQueueContext = createContext<EventQueueContextType>({
  refreshEvents: () => {},
  setRefreshEvents: () => {},
  isRefreshing: false
});

export const EventQueueProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const eventQueue = useEventQueueStore();

  return (
    <EventQueueContext.Provider value={eventQueue}>
      {children}
    </EventQueueContext.Provider>
  );
};

// Keep this for backward compatibility
export const useEventQueue = () => useContext(EventQueueContext); 