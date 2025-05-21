import { battlemapEngine } from './BattlemapEngine';
import { GridRenderer } from './renderers/GridRenderer';
import { TileRenderer } from './renderers/TileRenderer';
import { InteractionsManager } from './InteractionsManager';

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
  
  /**
   * Initialize the game engine and all components
   * @param containerElement The HTML element to attach the canvas to
   */
  async initialize(containerElement: HTMLElement): Promise<boolean> {
    try {
      console.log('[GameManager] Initializing game engine');
      
      // First initialize the battlemap engine
      await battlemapEngine.initialize(containerElement);
      
      // Initialize and register components
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
   * Initialize all components
   */
  private initializeComponents(): void {
    // Initialize and register tile renderer first (bottom layer)
    this.tileRenderer.initialize(battlemapEngine);
    battlemapEngine.registerRenderer('tiles', this.tileRenderer);
    
    // Initialize and register grid renderer next (middle layer)
    this.gridRenderer.initialize(battlemapEngine);
    battlemapEngine.registerRenderer('grid', this.gridRenderer);
    
    // Initialize interactions manager last (top layer)
    this.interactionsManager.initialize(battlemapEngine);
    
    console.log('[GameManager] All components initialized');
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
    
    // Clean up engine
    battlemapEngine.destroy();
    
    this.isInitialized = false;
  }
}

// Create and export a singleton instance
export const gameManager = new GameManager(); 