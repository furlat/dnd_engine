import { useEffect } from 'react';
import { useSnapshot } from 'valtio';
import { eventQueueStore, eventQueueActions } from '../../store/eventQueueStore';

interface EventQueueHook {
  isRefreshing: boolean;
  refreshEvents: () => void;
  setRefreshEvents: (callback: () => Promise<void>) => void;
}

export function useEventQueue(): EventQueueHook {
  const snap = useSnapshot(eventQueueStore);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      eventQueueActions.cleanup();
    };
  }, []);

  return {
    isRefreshing: snap.isRefreshing,
    refreshEvents: eventQueueActions.refresh,
    setRefreshEvents: eventQueueActions.setRefreshCallback
  };
} 