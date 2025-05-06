import React, { createContext, useContext, useCallback } from 'react';

interface EventQueueContextType {
  refreshEvents: () => void;
  setRefreshEvents: (callback: () => void) => void;
}

const EventQueueContext = createContext<EventQueueContextType>({
  refreshEvents: () => {},
  setRefreshEvents: () => {},
});

export const EventQueueProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [refreshCallback, setRefreshCallback] = React.useState<() => void>(() => () => {});

  const setRefreshEvents = useCallback((callback: () => void) => {
    setRefreshCallback(() => callback);
  }, []);

  return (
    <EventQueueContext.Provider value={{ refreshEvents: refreshCallback, setRefreshEvents }}>
      {children}
    </EventQueueContext.Provider>
  );
};

export const useEventQueue = () => useContext(EventQueueContext); 