import { Application, Container, Ticker } from 'pixi.js';
import { subscribe } from 'valtio';
import { battlemapStore } from '../store';

/**
 * Layer names for proper rendering order
 */
export type LayerName = 'tiles' | 'grid' | 'below_effects' | 'entities' | 'above_effects' | 'ui';

/**
 * BattlemapEngine is the core class that manages the PixiJS application
 * It handles initialization, destruction, layer management, and ticker-based updates
 */
export class BattlemapEngine {
  // PixiJS Application instance
  app: Application | null = null;
  
  // Track container element dimensions
  containerSize: { width: number; height: number } = { width: 0, height: 0 };
  
  // Track initialization state
  isInitialized = false;
  
  // Layer containers for proper rendering order
  private layers: Record<LayerName, Container> | null = null;
  
  // Renderers registry
  private renderers: Map<string, { render?: () => void; update?: (ticker: Ticker) => void }> = new Map();
  
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
      
      // Set up layer hierarchy
      this.setupLayers();
      
      // Initialize tickers
      this.setupTickers();
      
      // Enable render groups for static content
      this.enableRenderGroups();
      
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
   * Set up layer hierarchy for proper rendering order
   */
  private setupLayers(): void {
    if (!this.app?.stage) return;
    
    const stage = this.app.stage;
    
    this.layers = {
      tiles: new Container(),
      grid: new Container(),
      below_effects: new Container(),
      entities: new Container(),
      above_effects: new Container(),
      ui: new Container()
    };
    
    // Add layers in rendering order (bottom to top)
    // Two effect layers: below and above entities for isometric perspective
    stage.addChild(this.layers.tiles);
    stage.addChild(this.layers.grid);
    stage.addChild(this.layers.below_effects);  // Effects behind entities (when entity shows front)
    stage.addChild(this.layers.entities);
    stage.addChild(this.layers.above_effects);  // Effects in front of entities (when entity shows back)
    stage.addChild(this.layers.ui);
    
    console.log('[BattlemapEngine] Layer hierarchy established');
  }
  
  /**
   * Set up ticker system for frame-based updates
   */
  private setupTickers(): void {
    if (!this.app) return;
    
    // Ensure the main app ticker is started
    if (!this.app.ticker.started) {
      this.app.ticker.start();
      console.log('[BattlemapEngine] Started main app ticker');
    }
    
    // Use the main app ticker instead of creating a separate one
    // This ensures the canvas gets redrawn every frame
    this.app.ticker.add(this.updateRenderers, this);
    
    console.log('[BattlemapEngine] Ticker system initialized using main app ticker');
  }
  
  /**
   * Enable render groups for static content optimization
   */
  private enableRenderGroups(): void {
    if (!this.layers) return;
    
    // Enable render group for tiles (static content)
    this.layers.tiles.isRenderGroup = true;
    
    console.log('[BattlemapEngine] Render groups enabled');
  }
  
  /**
   * Get a specific layer container
   * @param layerName The name of the layer to retrieve
   */
  getLayer(layerName: LayerName): Container | null {
    return this.layers?.[layerName] || null;
  }
  
  /**
   * Register a renderer with the engine
   * @param name Unique name for the renderer
   * @param renderer Renderer object with render and/or update methods
   */
  registerRenderer(name: string, renderer: { render?: () => void; update?: (ticker: Ticker) => void }) {
    this.renderers.set(name, renderer);
    console.log(`[BattlemapEngine] Renderer '${name}' registered`);
  }
  
  /**
   * Get a registered renderer by name
   * @param name The name of the renderer to retrieve
   */
  getRenderer<T extends { render?: () => void; update?: (ticker: Ticker) => void }>(name: string): T | undefined {
    return this.renderers.get(name) as T | undefined;
  }
  
  /**
   * Update all renderers that need ticker updates (called every frame)
   */
  private updateRenderers(ticker: Ticker): void {
    if (!this.isInitialized) return;
    
    this.renderers.forEach(renderer => {
      if (renderer.update) {
        renderer.update(ticker);
      }
    });
    
    // Force a render to ensure canvas is redrawn
    // This is needed because PixiJS doesn't automatically redraw static scenes
    if (this.app?.renderer) {
      this.app.renderer.render(this.app.stage);
    }
  }
  
  /**
   * Render all registered renderers (called on store changes)
   */
  renderAll() {
    if (!this.isInitialized || !this.app) return;
    
    this.renderers.forEach(renderer => {
      if (renderer.render) {
        renderer.render();
      }
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
      // Remove ticker callback from main app ticker
      if (this.app?.ticker) {
        this.app.ticker.remove(this.updateRenderers, this);
      }
      
      this.renderers.clear();
      this.layers = null;
      
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