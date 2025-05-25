import { battlemapEngine } from './BattlemapEngine';
import { GridRenderer } from './renderers/GridRenderer';
import { TileRenderer } from './renderers/TileRenderer';
import { EntityRenderer } from './renderers/EntityRenderer';
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
  private entityRenderer: EntityRenderer = new EntityRenderer();
  private interactionsManager: InteractionsManager = new InteractionsManager();
  private movementController: MovementController = new MovementController();
  
  /**
   * Initialize the game manager and all its components
   * @param containerElement The HTML element that will contain the PixiJS canvas
   */
  async initialize(containerElement: HTMLElement): Promise<boolean> {
    if (this.isInitialized) {
      console.warn('[GameManager] Already initialized');
      return true;
    }

    try {
      console.log('[GameManager] Initializing...');

      // Initialize the engine first
      const success = await battlemapEngine.initialize(containerElement);
      if (!success) {
        throw new Error('Failed to initialize BattlemapEngine');
      }

      // Initialize all components
      this.initializeComponents();

      this.isInitialized = true;
      console.log('[GameManager] Successfully initialized');
      return true;

    } catch (error) {
      console.error('[GameManager] Initialization failed:', error);
      this.destroy();
      return false;
    }
  }
  
  /**
   * Initialize all game components
   */
  private initializeComponents(): void {
    console.log('[GameManager] Initializing components...');
    
    // Initialize renderers
    this.tileRenderer.initialize(battlemapEngine);
    this.gridRenderer.initialize(battlemapEngine);
    this.entityRenderer.initialize(battlemapEngine);
    
    // Register renderers with the engine
    battlemapEngine.registerRenderer('tiles', this.tileRenderer);
    battlemapEngine.registerRenderer('grid', this.gridRenderer);
    battlemapEngine.registerRenderer('entities', this.entityRenderer);
    
    // Initialize interactions (needs to be after renderers for proper layering)
    this.interactionsManager.initialize(battlemapEngine);
    
    // Initialize movement controller
    if (battlemapEngine.app) {
      this.movementController.initialize(battlemapEngine.app.ticker);
    }
    
    // Perform initial render
    battlemapEngine.renderAll();
    
    console.log(`[GameManager] Initialized ${battlemapEngine.getRendererCount()} components`);
  }
  
  /**
   * Get current movement state
   */
  getMovementState() {
    return this.movementController.getMovementState();
  }
  
  /**
   * Stop movement
   */
  stopMovement(): void {
    this.movementController.stop();
  }
  
  /**
   * Resize the game to new dimensions
   */
  resize(width: number, height: number): void {
    if (!this.isInitialized) return;
    
    console.log('[GameManager] Resizing to:', width, height);
    
    battlemapEngine.resize(width, height);
    this.interactionsManager.resize();
  }
  
  /**
   * Destroy the game manager and clean up all resources
   */
  destroy(): void {
    console.log('[GameManager] Destroying...');
    
    // Destroy components in reverse order
    this.movementController.destroy();
    this.interactionsManager.destroy();
    this.entityRenderer.destroy();
    this.gridRenderer.destroy();
    this.tileRenderer.destroy();
    
    // Destroy the engine last
    battlemapEngine.destroy();
    
    this.isInitialized = false;
    console.log('[GameManager] Destroyed');
  }
}

// Create and export a singleton instance
export const gameManager = new GameManager(); 