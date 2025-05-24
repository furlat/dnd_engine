import { Container, Ticker } from 'pixi.js';
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
    // Remove the container from its parent (layer or stage)
    this.container.removeFromParent();
    
    // Destroy the container and all its children
    this.container.destroy({ children: true });
    
    // Clear references
    this.engine = null;
    this.layer = null;
  }
} 