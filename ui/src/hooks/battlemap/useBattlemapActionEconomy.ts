import { useState, useCallback } from 'react';
import { refreshEntityActionEconomy } from '../../api/battlemap/battlemapApi';
import { battlemapActions } from '../../store/battlemapStore';

/**
 * Hook for managing action economy operations in the battlemap context
 */
export const useBattlemapActionEconomy = () => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Refresh action economy for a specific entity
   */
  const refreshActionEconomy = useCallback(async (entityId: string): Promise<boolean> => {
    if (isRefreshing) {
      console.warn('[useBattlemapActionEconomy] Already refreshing, ignoring request');
      return false;
    }

    setIsRefreshing(true);
    setError(null);

    try {
      console.log(`[useBattlemapActionEconomy] Refreshing action economy for entity ${entityId}`);
      
      // Call the battlemap-specific API endpoint
      const updatedEntity = await refreshEntityActionEconomy(entityId);
      
      // Refresh all entity summaries to ensure consistency and get the updated entity
      await battlemapActions.fetchEntitySummaries();
      
      console.log(`[useBattlemapActionEconomy] Successfully refreshed action economy for ${updatedEntity.name}`);
      return true;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to refresh action economy';
      console.error(`[useBattlemapActionEconomy] Error refreshing action economy:`, err);
      setError(errorMessage);
      return false;
    } finally {
      setIsRefreshing(false);
    }
  }, [isRefreshing]);

  /**
   * Clear any error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    refreshActionEconomy,
    isRefreshing,
    error,
    clearError,
  };
}; 