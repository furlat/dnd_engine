import { Graphics } from 'pixi.js';
import { battlemapStore } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * GridRenderer handles rendering the grid lines 
 */
export class GridRenderer extends AbstractRenderer {
  // Graphics references
  private gridGraphics: Graphics = new Graphics();
  private highlightGraphics: Graphics = new Graphics();
  
  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];

  /**
   * Initialize the renderer
   */
  initialize(engine: any): void {
    super.initialize(engine);
    
    // Add graphics to container - grid first, then highlight
    this.container.addChild(this.gridGraphics);
    this.container.addChild(this.highlightGraphics);
    
    // Setup subscriptions
    this.setupSubscriptions();
    
    console.log('[GridRenderer] Initialized');
  }
  
  /**
   * Set up subscriptions to the Valtio store
   */
  private setupSubscriptions(): void {
    // Store unsubscribe functions
    this.unsubscribeCallbacks = [];
    
    // Subscribe to view changes (zooming, panning)
    const unsubView = subscribe(battlemapStore.view, () => {
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubView);
    
    // Subscribe to hovered cell changes specifically
    const unsubHoveredCell = subscribe(battlemapStore.view.hoveredCell, () => {
      this.renderCellHighlight();
    });
    this.unsubscribeCallbacks.push(unsubHoveredCell);
    
    // Subscribe to control changes for grid visibility
    const unsubControls = subscribe(battlemapStore.controls, () => {
      console.log('[GridRenderer] Controls changed, isGridVisible:', battlemapStore.controls.isGridVisible);
      this.renderGrid();
    });
    this.unsubscribeCallbacks.push(unsubControls);
  }
  
  /**
   * Calculate grid offset with proper centering
   */
  private calculateGridOffset(): { 
    offsetX: number; 
    offsetY: number; 
    tileSize: number;
    gridPixelWidth: number;
    gridPixelHeight: number;
  } {
    const snap = battlemapStore;
    
    // Get container size from engine
    const containerSize = this.engine?.containerSize || { width: 0, height: 0 };
    
    const availableWidth = containerSize.width - ENTITY_PANEL_WIDTH;
    const gridPixelWidth = snap.grid.width * snap.view.tileSize;
    const gridPixelHeight = snap.grid.height * snap.view.tileSize;
    
    // Center grid in the available space (starting from entity panel width)
    const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
    const baseOffsetY = (containerSize.height - gridPixelHeight) / 2;
    
    // Apply the offset from WASD controls
    const offsetX = baseOffsetX + snap.view.offset.x;
    const offsetY = baseOffsetY + snap.view.offset.y;
    
    return { 
      offsetX, 
      offsetY,
      tileSize: snap.view.tileSize,
      gridPixelWidth,
      gridPixelHeight
    };
  }
  
  /**
   * Render everything
   */
  render(): void {
    // Skip if not properly initialized
    if (!this.engine || !this.engine.app) {
      console.log('[GridRenderer] Skipping render - engine not ready');
      return;
    }
    
    this.renderGrid();
    this.renderCellHighlight();
  }
  
  /**
   * Render the grid lines
   */
  private renderGrid(): void {
    // Check if graphics is available
    if (!this.gridGraphics) {
      console.log('[GridRenderer] Grid graphics not available');
      return;
    }
    
    // Get grid settings from store
    const snap = battlemapStore;
    const isGridVisible = snap.controls.isGridVisible;
    
    console.log('[GridRenderer] Rendering grid, visible:', isGridVisible);
    
    // Clear previous grid
    this.gridGraphics.clear();
    
    // Skip rendering if grid is not visible
    if (!isGridVisible) return;
    
    const gridWidth = snap.grid.width;
    const gridHeight = snap.grid.height;
    
    // Get grid offset and size
    const { offsetX, offsetY, tileSize, gridPixelWidth, gridPixelHeight } = this.calculateGridOffset();
    
    console.log('[GridRenderer] Drawing grid with:', {
      offsetX,
      offsetY,
      tileSize,
      gridWidth,
      gridHeight,
      containerSize: this.engine?.containerSize
    });
    
    // Create a line for each grid line (vertical)
    for (let i = 0; i <= gridWidth; i++) {
      const x = offsetX + (i * tileSize);
      this.gridGraphics
        .moveTo(x, offsetY)
        .lineTo(x, offsetY + gridPixelHeight)
        .stroke({ 
          width: 1, 
          color: 0xCCCCCC, 
          alpha: 0.5 
        });
    }
    
    // Create a line for each grid line (horizontal)
    for (let i = 0; i <= gridHeight; i++) {
      const y = offsetY + (i * tileSize);
      this.gridGraphics
        .moveTo(offsetX, y)
        .lineTo(offsetX + gridPixelWidth, y)
        .stroke({ 
          width: 1, 
          color: 0xCCCCCC, 
          alpha: 0.5 
        });
    }
    
    console.log('[GridRenderer] Grid drawn at:', { offsetX, offsetY, gridWidth, gridHeight });
  }
  
  /**
   * Render cell highlight
   */
  private renderCellHighlight(): void {
    // Check if graphics is available
    if (!this.highlightGraphics) {
      console.log('[GridRenderer] Highlight graphics not available');
      return;
    }
    
    const snap = battlemapStore;
    
    // Skip highlighting during movement for better performance
    if (snap.view.wasd_moving) {
      this.highlightGraphics.clear();
      return;
    }
    
    // Clear previous highlight
    this.highlightGraphics.clear();
    
    const { x, y } = snap.view.hoveredCell;
    
    // Only draw if valid coordinates
    if (x < 0 || y < 0 || x >= snap.grid.width || y >= snap.grid.height) {
      return;
    }
    
    // Get grid offset and size
    const { offsetX, offsetY, tileSize } = this.calculateGridOffset();
    
    // Draw highlight - always show highlight regardless of locked state
    this.highlightGraphics
      .rect(
        offsetX + (x * tileSize),
        offsetY + (y * tileSize),
        tileSize,
        tileSize
      )
      .fill({ color: 0x00FF00, alpha: 0.3 });
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // Unsubscribe from all subscriptions
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
    // Clear graphics
    if (this.gridGraphics) {
      try {
        if (this.gridGraphics.clear) {
          this.gridGraphics.clear();
        }
        if (!this.gridGraphics.destroyed) {
          this.gridGraphics.destroy();
        }
      } catch (e) {
        console.warn('[GridRenderer] Error destroying grid graphics:', e);
      }
    }
    
    if (this.highlightGraphics) {
      try {
        if (this.highlightGraphics.clear) {
          this.highlightGraphics.clear();
        }
        if (!this.highlightGraphics.destroyed) {
          this.highlightGraphics.destroy();
        }
      } catch (e) {
        console.warn('[GridRenderer] Error destroying highlight graphics:', e);
      }
    }
    
    // Call parent destroy
    super.destroy();
  }
} 