import { useRef, useEffect } from 'react';

/**
 * Hook that returns a ref that tracks if the component is mounted
 * Useful for preventing state updates after unmount
 */
export const useMountedRef = () => {
  const mountedRef = useRef(false);
  
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  return mountedRef;
};

export default useMountedRef; 