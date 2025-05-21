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
    // Subscribe to view changes (zooming, panning)
    subscribe(battlemapStore.view, () => {
      this.render();
    });
    
    // Subscribe to hovered cell changes specifically
    subscribe(battlemapStore.view.hoveredCell, () => {
      this.renderCellHighlight();
    });
    
    // Subscribe to control changes for grid visibility
    subscribe(battlemapStore.controls, () => {
      console.log('[GridRenderer] Controls changed, isGridVisible:', battlemapStore.controls.isGridVisible);
      this.renderGrid();
    });
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
    this.renderGrid();
    this.renderCellHighlight();
  }
  
  /**
   * Render the grid lines
   */
  private renderGrid(): void {
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
    
    // Set up stroke style for v8
    this.gridGraphics.stroke({ 
      width: 1, 
      color: 0xFFFFFF, 
      alpha: 0.5  // Increased for better visibility
    });
    
    // Draw vertical lines
    for (let i = 0; i <= gridWidth; i++) {
      const x = offsetX + (i * tileSize);
      this.gridGraphics.moveTo(x, offsetY);
      this.gridGraphics.lineTo(x, offsetY + gridPixelHeight);
    }
    
    // Draw horizontal lines
    for (let i = 0; i <= gridHeight; i++) {
      const y = offsetY + (i * tileSize);
      this.gridGraphics.moveTo(offsetX, y);
      this.gridGraphics.lineTo(offsetX + gridPixelWidth, y);
    }
    
    console.log('[GridRenderer] Grid drawn at:', { offsetX, offsetY, gridWidth, gridHeight });
  }
  
  /**
   * Render cell highlight
   */
  private renderCellHighlight(): void {
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
    
    // Draw highlight
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
    // Clear graphics
    this.gridGraphics.clear();
    this.highlightGraphics.clear();
    
    // Destroy graphics
    this.gridGraphics.destroy();
    this.highlightGraphics.destroy();
    
    // Call parent destroy
    super.destroy();
  }
} 