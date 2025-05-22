import { Application } from 'pixi.js';
import { subscribe } from 'valtio';
import { battlemapStore } from '../store';

/**
 * BattlemapEngine is the core class that manages the PixiJS application
 * It handles initialization, destruction, and basic rendering
 * but delegates specific rendering tasks to specialized renderers
 */
export class BattlemapEngine {
  // PixiJS Application instance
  app: Application | null = null;
  
  // Track container element dimensions
  containerSize: { width: number; height: number } = { width: 0, height: 0 };
  
  // Track initialization state
  isInitialized = false;
  
  // Renderers registry
  private renderers: Map<string, { render: () => void }> = new Map();
  
  /**
   * Initialize the PixiJS application
   * @param element The HTML element to attach the canvas to
   */
  async initialize(element: HTMLElement): Promise<boolean> {
    // Validate input element
    if (!element) {
      console.error('[BattlemapEngine] Cannot initialize - element is null or undefined');
      return false;
    }
    
    // Clean up existing instance if any
    if (this.app) this.destroy();
    
    try {
      console.log('[BattlemapEngine] Initializing PixiJS application');
      
      // Create new PixiJS application using v8 approach
      this.app = new Application();
      
      // Get dimensions before initialization
      const width = element.clientWidth || 800;  // Fallback width if clientWidth is 0
      const height = element.clientHeight || 600; // Fallback height if clientHeight is 0
      
      console.log('[BattlemapEngine] Container dimensions:', width, height);
      
      // Initialize the application with options
      await this.app.init({
        width: width,
        height: height,
        backgroundColor: 0x111111,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
      });
      
      // Update container size
      this.containerSize = {
        width: width,
        height: height
      };
      
      // Add the canvas to the DOM
      if (this.app.canvas) {
        element.appendChild(this.app.canvas);
        console.log('[BattlemapEngine] Canvas appended to DOM');
      } else {
        throw new Error('Canvas not created after app initialization');
      }
      
      this.isInitialized = true;
      console.log('[BattlemapEngine] Successfully initialized PixiJS application');
      return true;
    } catch (err) {
      console.error('[BattlemapEngine] Error initializing PixiJS:', err);
      // Clean up any partially created resources
      this.destroy();
      throw err;
    }
  }
  
  /**
   * Register a renderer with the engine
   * @param name Unique name for the renderer
   * @param renderer Renderer object with a render method
   */
  registerRenderer(name: string, renderer: { render: () => void }) {
    this.renderers.set(name, renderer);
  }
  
  /**
   * Get a registered renderer by name
   * @param name The name of the renderer to retrieve
   */
  getRenderer<T extends { render: () => void }>(name: string): T | undefined {
    return this.renderers.get(name) as T | undefined;
  }
  
  /**
   * Render all registered renderers
   */
  renderAll() {
    if (!this.isInitialized || !this.app) return;
    
    this.renderers.forEach(renderer => {
      renderer.render();
    });
  }
  
  /**
   * Get the number of registered renderers
   */
  getRendererCount(): number {
    return this.renderers.size;
  }
  
  /**
   * Resize the application
   * @param width New width
   * @param height New height
   */
  resize(width: number, height: number) {
    if (!this.app) return;
    
    console.log('[BattlemapEngine] Resizing to', width, height);
    this.containerSize = { width, height };
    
    // Use the renderer resize API for v8
    this.app.renderer.resize(width, height);
    
    // Re-render all
    this.renderAll();
  }
  
  /**
   * Clean up resources
   */
  destroy() {
    console.log('[BattlemapEngine] Destroying engine');
    
    try {
      this.renderers.clear();
      
      if (this.app) {
        // In v8, manually remove the canvas from the DOM
        if (this.app.canvas && this.app.canvas.parentNode) {
          this.app.canvas.parentNode.removeChild(this.app.canvas);
        }
        
        // Call destroy to clean up resources
        this.app.destroy(true, { children: true });
        this.app = null;
      }
      
      this.isInitialized = false;
    } catch (err) {
      console.error('[BattlemapEngine] Error during cleanup:', err);
      // Reset state even if there's an error
      this.app = null;
      this.isInitialized = false;
    }
  }
}

// Create and export a singleton instance
export const battlemapEngine = new BattlemapEngine(); 