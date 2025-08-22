type EventCallback = (data: any) => void;
type Unsubscribe = () => void;

/**
 * Simple event bus for animation events
 * Singleton pattern for global access
 */
export class AnimationEventBus {
  private static instance: AnimationEventBus;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private debug: boolean = false;
  
  private constructor() {}
  
  static getInstance(): AnimationEventBus {
    if (!AnimationEventBus.instance) {
      AnimationEventBus.instance = new AnimationEventBus();
    }
    return AnimationEventBus.instance;
  }
  
  /**
   * Subscribe to an event
   */
  on(event: string, callback: EventCallback): Unsubscribe {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    
    this.listeners.get(event)!.add(callback);
    
    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(event);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          this.listeners.delete(event);
        }
      }
    };
  }
  
  /**
   * Subscribe to an event, but only once
   */
  once(event: string, callback: EventCallback): Unsubscribe {
    const unsubscribe = this.on(event, (data) => {
      callback(data);
      unsubscribe();
    });
    return unsubscribe;
  }
  
  /**
   * Emit an event
   */
  emit(event: string, data?: any): void {
    if (this.debug) {
      console.log(`[AnimationEvent] ${event}`, data);
    }
    
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event handler for ${event}:`, error);
        }
      });
    }
  }
  
  /**
   * Enable debug logging
   */
  setDebug(enabled: boolean): void {
    this.debug = enabled;
  }
  
  /**
   * Clear all listeners
   */
  clear(): void {
    this.listeners.clear();
  }
}

// Export singleton instance
export const animationEventBus = AnimationEventBus.getInstance(); 