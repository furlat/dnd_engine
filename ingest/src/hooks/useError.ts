import { useState, useCallback } from 'react';

/**
 * Hook for managing error state throughout the application
 */
export const useError = () => {
  const [error, setError] = useState<string | null>(null);

  // Clear the error message
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    error,
    setError,
    clearError
  };
}; 