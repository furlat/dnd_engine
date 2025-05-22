import { Container } from 'pixi.js';
import { BattlemapEngine } from '../BattlemapEngine';

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
   * Render the graphics
   */
  render(): void;
  
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
  
  /**
   * Initialize the renderer
   * @param engine The battlemap engine instance
   */
  initialize(engine: BattlemapEngine): void {
    this.engine = engine;
    
    // Add the container to the stage if app is available
    if (engine.app?.stage) {
      engine.app.stage.addChild(this.container);
    }
  }
  
  /**
   * Render the graphics - to be implemented by subclasses
   */
  abstract render(): void;
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // Remove the container from the stage
    this.container.removeFromParent();
    
    // Destroy the container and all its children
    this.container.destroy({ children: true });
    
    // Clear the engine reference
    this.engine = null;
  }
} 