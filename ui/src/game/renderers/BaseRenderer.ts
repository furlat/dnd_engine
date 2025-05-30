import { Container, Ticker, Graphics } from 'pixi.js';
import { BattlemapEngine, LayerName } from '../BattlemapEngine';

/**
 * Base interface for all renderers
 */
export interface BaseRenderer {
  /**
   * The main container for this renderer's graphics
   */
  container: Container;
  
  /**
   * Initialize the renderer
   * @param engine The battlemap engine instance
   */
  initialize(engine: BattlemapEngine): void;
  
  /**
   * Render the graphics (called on store changes)
   */
  render?(): void;
  
  /**
   * Update the renderer (called every frame via ticker)
   */
  update?(ticker: Ticker): void;
  
  /**
   * Clean up resources
   */
  destroy(): void;
}

/**
 * Base abstract class that implements common renderer functionality
 */
export abstract class AbstractRenderer implements BaseRenderer {
  // The main container for this renderer's graphics
  container: Container = new Container();
  
  // Reference to the engine
  protected engine: BattlemapEngine | null = null;
  
  // Layer this renderer belongs to
  protected layer: Container | null = null;
  
  // Layer name for this renderer (must be implemented by subclasses)
  abstract get layerName(): LayerName;
  
  // Whether this renderer needs ticker updates (default: false)
  protected needsTickerUpdate: boolean = false;
  
  // NEW: Common subscription management
  protected unsubscribeCallbacks: Array<() => void> = [];
  
  // NEW: Common logging system
  protected lastSummaryTime = 0;
  protected renderCount = 0;
  
  /**
   * Initialize the renderer
   * @param engine The battlemap engine instance
   */
  initialize(engine: BattlemapEngine): void {
    this.engine = engine;
    
    // Get the appropriate layer container
    this.layer = engine.getLayer(this.layerName);
    
    if (this.layer) {
      // Add container to the appropriate layer instead of directly to stage
      this.layer.addChild(this.container);
      console.log(`[${this.constructor.name}] Added to layer: ${this.layerName}`);
    } else {
      console.warn(`[${this.constructor.name}] Layer '${this.layerName}' not available, adding to stage`);
      // Fallback to stage if layer not available
      if (engine.app?.stage) {
        engine.app.stage.addChild(this.container);
      }
    }
    
    // Register for ticker updates if needed
    if (this.needsTickerUpdate) {
      this.registerTickerUpdate();
    }
  }
  
  /**
   * Register this renderer for ticker updates
   */
  private registerTickerUpdate(): void {
    if (this.engine && this.update) {
      // The engine will call our update method via its ticker system
      console.log(`[${this.constructor.name}] Registered for ticker updates`);
    }
  }
  
  /**
   * NEW: Protected helper to safely destroy graphics with error handling
   * Common pattern used across all renderers
   */
  protected destroyGraphics(graphics: Graphics, name?: string): void {
    if (graphics) {
      try {
        if (graphics.clear && !graphics.destroyed) {
          graphics.clear();
        }
        if (!graphics.destroyed) {
          graphics.destroy();
        }
      } catch (e) {
        const graphicsName = name || 'graphics';
        console.warn(`[${this.constructor.name}] Error destroying ${graphicsName}:`, e);
      }
    }
  }
  
  /**
   * NEW: Protected helper to safely destroy multiple graphics objects
   */
  protected destroyGraphicsArray(graphicsArray: Graphics[], names?: string[]): void {
    graphicsArray.forEach((graphics, index) => {
      const name = names?.[index] || `graphics[${index}]`;
      this.destroyGraphics(graphics, name);
    });
  }
  
  /**
   * NEW: Protected helper to clean up all subscriptions
   * Common pattern used across all renderers
   */
  protected cleanupSubscriptions(): void {
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
  }
  
  /**
   * NEW: Protected helper to add a subscription with automatic cleanup tracking
   */
  protected addSubscription(unsubscribeCallback: () => void): void {
    this.unsubscribeCallbacks.push(unsubscribeCallback);
  }
  
  /**
   * NEW: Protected logging utility for render summaries
   * Prevents spam by logging every 10 seconds instead of every render
   */
  protected logRenderSummary(additionalInfo?: string): void {
    const now = Date.now();
    if (now - this.lastSummaryTime >= 10000) { // 10 seconds
      const baseInfo = `10s Summary: ${this.renderCount} renders`;
      const fullInfo = additionalInfo ? `${baseInfo}, ${additionalInfo}` : baseInfo;
      console.log(`[${this.constructor.name}] ${fullInfo}`);
      
      this.lastSummaryTime = now;
      this.renderCount = 0;
    }
  }
  
  /**
   * NEW: Protected helper to increment render count
   * Should be called at the start of render() method
   */
  protected incrementRenderCount(): void {
    this.renderCount++;
  }
  
  /**
   * NEW: Protected helper to check if engine is properly initialized
   * Common check across all renderers
   */
  protected isEngineReady(): boolean {
    if (!this.engine || !this.engine.app) {
      console.warn(`[${this.constructor.name}] Render called but engine not initialized`);
      return false;
    }
    return true;
  }
  
  /**
   * Render the graphics - can be implemented by subclasses
   */
  render?(): void;
  
  /**
   * Update the renderer - can be implemented by subclasses
   */
  update?(ticker: Ticker): void;
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // NEW: Use centralized subscription cleanup
    this.cleanupSubscriptions();
    
    // Remove the container from its parent (layer or stage)
    this.container.removeFromParent();
    
    // Destroy the container and all its children
    this.container.destroy({ children: true });
    
    // Clear references
    this.engine = null;
    this.layer = null;
  }
} 