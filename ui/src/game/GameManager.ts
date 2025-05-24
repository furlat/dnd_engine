import { battlemapEngine } from './BattlemapEngine';
import { GridRenderer } from './renderers/GridRenderer';
import { TileRenderer } from './renderers/TileRenderer';
import { InteractionsManager } from './InteractionsManager';
import { MovementController } from './MovementController';

/**
 * GameManager is the main entry point for the game engine
 * It initializes all components and manages their lifecycle
 */
export class GameManager {
  // Flag to track initialization
  private isInitialized: boolean = false;
  
  // Component references
  private tileRenderer: TileRenderer = new TileRenderer();
  private gridRenderer: GridRenderer = new GridRenderer();
  private interactionsManager: InteractionsManager = new InteractionsManager();
  private movementController: MovementController = new MovementController();
  
  /**
   * Initialize the game engine and all components
   * @param containerElement The HTML element to attach the canvas to
   */
  async initialize(containerElement: HTMLElement): Promise<boolean> {
    try {
      console.log('[GameManager] Initializing game engine');
      
      // First initialize the battlemap engine
      await battlemapEngine.initialize(containerElement);
      
      // Initialize and register all components
      this.initializeComponents();
      
      // Trigger an initial render
      battlemapEngine.renderAll();
      
      this.isInitialized = true;
      console.log('[GameManager] Game engine initialized successfully');
      return true;
    } catch (error) {
      console.error('[GameManager] Failed to initialize game engine:', error);
      this.destroy();
      throw error;
    }
  }
  
  /**
   * Initialize all components in the correct order
   */
  private initializeComponents(): void {
    console.log('[GameManager] Initializing components');
    
    // Initialize and register tile renderer first (bottom layer)
    this.tileRenderer.initialize(battlemapEngine);
    battlemapEngine.registerRenderer('tiles', this.tileRenderer);
    console.log('[GameManager] Tile renderer initialized');
    
    // Initialize and register grid renderer next (middle layer)
    this.gridRenderer.initialize(battlemapEngine);
    battlemapEngine.registerRenderer('grid', this.gridRenderer);
    console.log('[GameManager] Grid renderer initialized');
    
    // Initialize interactions manager (handles user input)
    this.interactionsManager.initialize(battlemapEngine);
    console.log('[GameManager] Interactions manager initialized');
    
    // Initialize movement controller with the engine's ticker
    if (battlemapEngine.app) {
      // Use the engine's animation ticker for smooth movement
      const animationTicker = (battlemapEngine as any).animationTicker;
      if (animationTicker) {
        this.movementController.initialize(animationTicker);
        console.log('[GameManager] Movement controller initialized');
      } else {
        console.warn('[GameManager] Animation ticker not available, movement controller not initialized');
      }
    }
    
    // Check that engine has renderers registered
    console.log('[GameManager] Registered renderers count:', 
      battlemapEngine.getRendererCount());
    
    console.log('[GameManager] All components initialized');
  }
  
  /**
   * Get movement controller state for debugging
   */
  getMovementState() {
    return this.movementController.getMovementState();
  }
  
  /**
   * Force stop camera movement
   */
  stopMovement(): void {
    this.movementController.stop();
  }
  
  /**
   * Resize the game engine and all components
   * @param width New width
   * @param height New height 
   */
  resize(width: number, height: number): void {
    if (!this.isInitialized) return;
    
    battlemapEngine.resize(width, height);
    this.interactionsManager.resize();
  }
  
  /**
   * Clean up all resources
   */
  destroy(): void {
    console.log('[GameManager] Destroying game engine');
    
    // Clean up movement controller
    if (this.movementController) {
      this.movementController.destroy();
    }
    
    // Clean up interactions manager
    if (this.interactionsManager) {
      this.interactionsManager.destroy();
    }
    
    // Clean up grid renderer
    if (this.gridRenderer) {
      this.gridRenderer.destroy();
    }
    
    // Clean up tile renderer
    if (this.tileRenderer) {
      this.tileRenderer.destroy();
    }
    
    // Clean up engine (this also cleans up tickers)
    battlemapEngine.destroy();
    
    this.isInitialized = false;
  }
}

// Create and export a singleton instance
export const gameManager = new GameManager(); 