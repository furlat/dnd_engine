import * as React from 'react';
import { Character, EntitySummary } from '../models/character';
import { useEventQueue } from './EventQueueContext';
import { fetchCharacter, fetchEntitySummaries } from '../api/characterApi';

// Define the context type
interface EntityContextType {
  entity: Character | null;
  loading: boolean;
  error: string | null;
  refreshEntity: (options?: { skipEventQueue?: boolean, silent?: boolean }) => Promise<void>;
  setEntityData: (data: Character) => void;
  summaries: Record<string, EntitySummary>;
  setSummaries: (data: Record<string, EntitySummary>) => void;
}

// Create context with default values
const EntityContext = React.createContext<EntityContextType>({
  entity: null,
  loading: false,
  error: null,
  refreshEntity: async () => {},
  setEntityData: () => {},
  summaries: {},
  setSummaries: () => {},
});

// Context provider component
export const EntityProvider: React.FC<{
  children: React.ReactNode;
  entityId: string;
  fetchEntity?: (id: string) => Promise<Character>;
}> = ({ children, entityId, fetchEntity: customFetchEntity }) => {
  const [entity, setEntity] = React.useState<Character | null>(null);
  const [summaries, setSummaries] = React.useState<Record<string, EntitySummary>>({});
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const { refreshEvents } = useEventQueue();

  const fetchData = React.useCallback(async (silent: boolean = false) => {
    try {
      // Fetch both character and summaries in parallel
      const [characterData, summariesData] = await Promise.all([
        (customFetchEntity || fetchCharacter)(entityId),
        fetchEntitySummaries()
      ]);

      // Convert summaries array to record for faster lookups
      const summariesRecord = summariesData.reduce((acc, summary) => {
        acc[summary.uuid] = summary;
        return acc;
      }, {} as Record<string, EntitySummary>);

      // Update data without triggering loading state if silent
      setEntity(prev => {
        // Only update if there are actual changes
        if (JSON.stringify(prev) === JSON.stringify(characterData)) {
          return prev;
        }
        return characterData;
      });
      
      setSummaries(prev => {
        // Only update if there are actual changes
        if (JSON.stringify(prev) === JSON.stringify(summariesRecord)) {
          return prev;
        }
        return summariesRecord;
      });
      
      setError(null);
    } catch (err) {
      console.error('Error fetching entity data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch entity');
    }
  }, [entityId, customFetchEntity]);

  const refreshEntity = React.useCallback(async (options?: { skipEventQueue?: boolean, silent?: boolean }) => {
    const isSilent = options?.silent ?? false;
    
    if (!isSilent) {
      setLoading(true);
    }
    
    try {
      // Start data fetch
      await fetchData(isSilent);
      
      // Always trigger event queue refresh asynchronously unless explicitly skipped
      if (!options?.skipEventQueue) {
        // Fire and forget - don't await the refresh
        Promise.resolve().then(() => {
          refreshEvents();
        }).catch(err => {
          console.error('Background event queue refresh failed:', err);
        });
      }
    } finally {
      if (!isSilent) {
        setLoading(false);
      }
    }
  }, [fetchData, refreshEvents]);

  // Initial load
  React.useEffect(() => {
    refreshEntity();
  }, [entityId]);

  const setEntityData = React.useCallback((data: Character) => {
    setEntity(prev => {
      // Only update if there are actual changes
      if (JSON.stringify(prev) === JSON.stringify(data)) {
        return prev;
      }
      return data;
    });
  }, []);

  const contextValue = React.useMemo(() => ({
    entity,
    loading,
    error,
    refreshEntity,
    setEntityData,
    summaries,
    setSummaries,
  }), [entity, loading, error, refreshEntity, setEntityData, summaries]);

  return (
    <EntityContext.Provider value={contextValue}>
      {children}
    </EntityContext.Provider>
  );
};

export const useEntity = () => {
  const context = React.useContext(EntityContext);
  if (!context) {
    throw new Error('useEntity must be used within an EntityProvider');
  }
  return context;
};

export default EntityContext; 