import * as React from 'react';
import { Character } from '../models/character';
import { useEventQueue } from './EventQueueContext';

// Define the context type
interface EntityContextType {
  entity: Character | null;
  loading: boolean;
  error: string | null;
  refreshEntity: () => Promise<void>;
  setEntityData: (data: Character) => void;
}

// Create context with default values
const EntityContext = React.createContext<EntityContextType>({
  entity: null,
  loading: false,
  error: null,
  refreshEntity: async () => {},
  setEntityData: () => {},
});

// Context provider component
export const EntityProvider: React.FC<{
  children: React.ReactNode;
  entityId: string;
  fetchEntity: (id: string) => Promise<Character>;
}> = ({ children, entityId, fetchEntity }) => {
  const [entity, setEntity] = React.useState<Character | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);
  const { refreshEvents } = useEventQueue();

  const loadEntity = React.useCallback(async () => {
    if (!entityId) return;

    try {
      setLoading(true);
      const data = await fetchEntity(entityId);
      setEntity(data);
      setError(null);
      refreshEvents(); // Refresh events after loading entity
    } catch (err) {
      console.error('Failed to fetch entity:', err);
      setError('Failed to load entity data. Please try again later.');
    } finally {
      setLoading(false);
    }
  }, [entityId, fetchEntity, refreshEvents]);

  // Load entity on mount and when entityId changes
  React.useEffect(() => {
    loadEntity();
  }, [loadEntity]);

  // Function to manually refresh the entity
  const refreshEntity = async () => {
    await loadEntity();
  };

  // Function to update entity data without a full reload
  const setEntityData = (data: Character) => {
    setEntity(data);
    refreshEvents(); // Refresh events after updating entity data
  };

  const value = {
    entity,
    loading,
    error,
    refreshEntity,
    setEntityData,
  };

  return <EntityContext.Provider value={value}>{children}</EntityContext.Provider>;
};

// Custom hook to use the context
export const useEntity = () => {
  const context = React.useContext(EntityContext);
  if (context === undefined) {
    throw new Error('useEntity must be used within an EntityProvider');
  }
  return context;
};

export default EntityContext; 