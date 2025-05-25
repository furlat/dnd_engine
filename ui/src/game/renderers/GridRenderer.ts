import { Graphics } from 'pixi.js';
import { battlemapStore } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { LayerName } from '../BattlemapEngine';
import { snapshot } from 'valtio';

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * GridRenderer handles rendering the grid lines 
 */
export class GridRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'grid'; }
  
  // Graphics references
  private gridGraphics: Graphics = new Graphics();
  private highlightGraphics: Graphics = new Graphics();
  
  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];
  
  // Summary logging system
  private lastSummaryTime = 0;
  private renderCount = 0;

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
    
    console.log('[GridRenderer] Initialized and added to grid layer');
  }
  
  /**
   * Log summary every 10 seconds instead of spamming
   */
  private logSummary(): void {
    const now = Date.now();
    if (now - this.lastSummaryTime >= 10000) { // 10 seconds
      console.log(`[GridRenderer] 10s Summary: ${this.renderCount} renders`);
      this.lastSummaryTime = now;
      this.renderCount = 0;
    }
  }
  
  /**
   * Set up subscriptions to the Valtio store
   */
  private setupSubscriptions(): void {
    // Store unsubscribe functions
    this.unsubscribeCallbacks = [];
    
    // Subscribe to view changes (for grid positioning and zoom)
    const unsubView = subscribe(battlemapStore.view, () => {
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubView);
    
    // Subscribe to control changes (for grid visibility)
    const unsubControls = subscribe(battlemapStore.controls, () => {
      this.render();
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
    gridWidth: number;
    gridHeight: number;
  } {
    const snap = battlemapStore;
    
    // Get container size from engine
    const containerSize = this.engine?.containerSize || { width: 0, height: 0 };
    
    const gridWidth = snap.grid.width;
    const gridHeight = snap.grid.height;
    const tileSize = snap.view.tileSize;
    
    const availableWidth = containerSize.width - ENTITY_PANEL_WIDTH;
    const gridPixelWidth = gridWidth * tileSize;
    const gridPixelHeight = gridHeight * tileSize;
    
    // Center grid in the available space (starting from entity panel width)
    const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
    const baseOffsetY = (containerSize.height - gridPixelHeight) / 2;
    
    // Apply the offset from WASD controls
    const offsetX = baseOffsetX + snap.view.offset.x;
    const offsetY = baseOffsetY + snap.view.offset.y;
    
    return { 
      offsetX, 
      offsetY,
      tileSize,
      gridPixelWidth,
      gridPixelHeight,
      gridWidth,
      gridHeight
    };
  }
  
  /**
   * Main render method
   */
  render(): void {
    this.renderCount++;
    this.renderGrid();
    this.renderCellHighlight();
    this.logSummary();
  }
  
  /**
   * Render the grid lines
   */
  private renderGrid(): void {
    if (!this.engine?.app) return;
    
    const snap = battlemapStore; // Use direct store reference, not snapshot
    const isVisible = snap.controls.isGridVisible;
    
    // Clear previous grid
    this.gridGraphics.clear();
    
    if (!isVisible) {
      return; // Don't draw grid if not visible
    }
    
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = this.calculateGridOffset();
    
    // Draw vertical lines using PixiJS v8 API with pixelLine
    for (let x = 0; x <= gridWidth; x++) {
      const lineX = offsetX + x * tileSize;
      this.gridGraphics
        .moveTo(lineX, offsetY)
        .lineTo(lineX, offsetY + gridHeight * tileSize);
    }
    
    // Draw horizontal lines
    for (let y = 0; y <= gridHeight; y++) {
      const lineY = offsetY + y * tileSize;
      this.gridGraphics
        .moveTo(offsetX, lineY)
        .lineTo(offsetX + gridWidth * tileSize, lineY);
    }
    
    // Apply stroke with pixelLine for pixel-perfect grid lines
    this.gridGraphics.stroke({ color: 0x444444, pixelLine: true }); // Back to gray color
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