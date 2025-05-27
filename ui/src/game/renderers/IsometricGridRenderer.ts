import { Graphics } from 'pixi.js';
import { battlemapStore } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { LayerName } from '../BattlemapEngine';
import { EntitySummary, Position } from '../../types/common';
import { 
  gridToIsometric, 
  isometricToGrid, 
  screenToGrid, 
  calculateIsometricGridOffset,
  calculateIsometricDiamondCorners,
  ISOMETRIC_TILE_WIDTH,
  ISOMETRIC_TILE_HEIGHT,
  GRID_STROKE_WIDTH
} from '../../utils/isometricUtils';

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * IsometricGridRenderer handles rendering the grid lines in isometric perspective
 * This is an experimental renderer to test isometric coordinate transformations
 */
export class IsometricGridRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'grid'; }
  
  // Graphics references
  private gridGraphics: Graphics = new Graphics();
  private highlightGraphics: Graphics = new Graphics();
  
  // NEW: Graphics for movement path highlighting (isometric)
  private pathGraphics: Graphics = new Graphics();
  
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
    
    // Add graphics to container - grid first, then highlight, then paths
    this.container.addChild(this.gridGraphics);
    this.container.addChild(this.highlightGraphics);
    this.container.addChild(this.pathGraphics);
    
    // Setup subscriptions
    this.setupSubscriptions();
    
    console.log('[IsometricGridRenderer] Initialized and added to grid layer');
  }
  
  /**
   * Log summary every 10 seconds instead of spamming
   */
  private logSummary(): void {
    const now = Date.now();
    if (now - this.lastSummaryTime >= 10000) { // 10 seconds
      console.log(`[IsometricGridRenderer] 10s Summary: ${this.renderCount} renders`);
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
  
  // Coordinate conversion methods are now imported from isometricUtils
  
  /**
   * Calculate grid offset with proper centering for isometric view
   */
  private calculateIsometricGridOffset(): { 
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
    
    return calculateIsometricGridOffset(
      containerSize.width,
      containerSize.height,
      snap.grid.width,
      snap.grid.height,
      snap.view.tileSize,
      snap.view.offset.x,
      snap.view.offset.y,
      ENTITY_PANEL_WIDTH
    );
  }
  
  /**
   * Main render method
   */
  render(): void {
    this.renderCount++;
    this.renderIsometricGrid();
    this.renderIsometricCellHighlight();
    this.renderIsometricMovementPaths();
    this.logSummary();
  }
  
  /**
   * Render the isometric grid lines
   */
  private renderIsometricGrid(): void {
    if (!this.engine?.app) return;
    
    const snap = battlemapStore;
    const isVisible = snap.controls.isGridVisible;
    
    // Clear previous grid
    this.gridGraphics.clear();
    
    if (!isVisible) {
      return; // Don't draw grid if not visible
    }
    
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = this.calculateIsometricGridOffset();
    
    // Draw isometric grid lines
    // We need to draw diamond-shaped grid cells
    
    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        const { isoX, isoY } = gridToIsometric(x, y);
        
        // Scale the isometric coordinates
        const scaledIsoX = isoX * tileSize;
        const scaledIsoY = isoY * tileSize;
        
        // Calculate the four corners of the diamond using utility function
        const centerX = offsetX + scaledIsoX;
        const centerY = offsetY + scaledIsoY;
        const strokeOffset = GRID_STROKE_WIDTH * 0.5;
        
        const { topX, topY, rightX, rightY, bottomX, bottomY, leftX, leftY } = 
          calculateIsometricDiamondCorners(centerX, centerY, tileSize, strokeOffset);
        
        // Draw the diamond outline
        this.gridGraphics
          .moveTo(topX, topY)
          .lineTo(rightX, rightY)
          .lineTo(bottomX, bottomY)
          .lineTo(leftX, leftY)
          .lineTo(topX, topY);
      }
    }
    
    // Apply stroke for the grid lines
    this.gridGraphics.stroke({ color: 0x444444, width: GRID_STROKE_WIDTH });
  }
  
  /**
   * Render isometric cell highlight
   */
  private renderIsometricCellHighlight(): void {
    if (!this.highlightGraphics) {
      console.log('[IsometricGridRenderer] Highlight graphics not available');
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
    const { offsetX, offsetY, tileSize } = this.calculateIsometricGridOffset();
    
    // Convert grid coordinates to isometric
    const { isoX, isoY } = gridToIsometric(x, y);
    
    // Scale the isometric coordinates
    const scaledIsoX = isoX * tileSize;
    const scaledIsoY = isoY * tileSize;
    
    // Calculate the diamond highlight using utility function
    const centerX = offsetX + scaledIsoX;
    const centerY = offsetY + scaledIsoY;
    const strokeOffset = GRID_STROKE_WIDTH * 0.5;
    
    const { topX, topY, rightX, rightY, bottomX, bottomY, leftX, leftY } = 
      calculateIsometricDiamondCorners(centerX, centerY, tileSize, strokeOffset);
    
    // Draw highlight diamond
    this.highlightGraphics
      .moveTo(topX, topY)
      .lineTo(rightX, rightY)
      .lineTo(bottomX, bottomY)
      .lineTo(leftX, leftY)
      .lineTo(topX, topY)
      .fill({ color: 0x00FF00, alpha: 0.3 });
  }
  
  /**
   * Render isometric movement path highlights
   */
  private renderIsometricMovementPaths(): void {
    if (!this.pathGraphics) {
      return;
    }
    
    const snap = battlemapStore;
    
    // Clear previous paths
    this.pathGraphics.clear();
    
    // Only render if movement highlighting is enabled
    if (!snap.controls.isMovementHighlightEnabled) {
      return;
    }
    
    // Get selected entity
    const selectedEntity = this.getSelectedEntity();
    if (!selectedEntity) {
      return;
    }
    
    // Get grid offset and size
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = this.calculateIsometricGridOffset();
    
    // Render movement range highlights in isometric
    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        const posKey = `${x},${y}`;
        const path = selectedEntity.senses.paths[posKey];
        
        if (path && path.length > 0) {
          // Determine color based on path length (movement cost)
          let pathColor = 0x00FF00; // Green for close
          let pathAlpha = 0.2;
          
          if (path.length <= 6) {
            // Within 30ft (6 squares) - green
            pathColor = 0x00FF00;
            pathAlpha = 0.3;
          } else if (path.length <= 12) {
            // Within 60ft (12 squares) - yellow
            pathColor = 0xFFFF00;
            pathAlpha = 0.25;
          } else {
            // Beyond 60ft - red
            pathColor = 0xFF0000;
            pathAlpha = 0.2;
          }
          
          // Convert grid coordinates to isometric
          const { isoX, isoY } = gridToIsometric(x, y);
          
          // Scale the isometric coordinates
          const scaledIsoX = isoX * tileSize;
          const scaledIsoY = isoY * tileSize;
          
          // Calculate the diamond using utility function
          const centerX = offsetX + scaledIsoX;
          const centerY = offsetY + scaledIsoY;
          const strokeOffset = GRID_STROKE_WIDTH * 0.5;
          
          const { topX, topY, rightX, rightY, bottomX, bottomY, leftX, leftY } = 
            calculateIsometricDiamondCorners(centerX, centerY, tileSize, strokeOffset);
          
          // Draw movement range diamond
          this.pathGraphics
            .moveTo(topX, topY)
            .lineTo(rightX, rightY)
            .lineTo(bottomX, bottomY)
            .lineTo(leftX, leftY)
            .lineTo(topX, topY)
            .fill({ color: pathColor, alpha: pathAlpha });
        }
      }
    }
  }
  
  /**
   * Get the selected entity for movement path calculations
   */
  private getSelectedEntity(): EntitySummary | null {
    const snap = battlemapStore;
    if (!snap.entities.selectedEntityId) return null;
    return snap.entities.summaries[snap.entities.selectedEntityId] || null;
  }
  
  /**
   * Convert screen pixel coordinates to grid coordinates (for mouse interaction)
   * This is the critical function for mouse highlighting to work correctly
   */
  public screenToGrid(screenX: number, screenY: number): { gridX: number; gridY: number; inBounds: boolean } {
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = this.calculateIsometricGridOffset();
    
    // Use the utility function for precise coordinate conversion
    const result = screenToGrid(screenX, screenY, offsetX, offsetY, tileSize, gridWidth, gridHeight);
    
    // Debug logging for coordinate conversion
    // console.log(`[IsometricGridRenderer] Screen (${screenX.toFixed(1)}, ${screenY.toFixed(1)}) -> Grid (${result.gridX}, ${result.gridY}) [InBounds: ${result.inBounds}]`);
    
    return result;
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
        console.warn('[IsometricGridRenderer] Error destroying grid graphics:', e);
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
        console.warn('[IsometricGridRenderer] Error destroying highlight graphics:', e);
      }
    }
    
    if (this.pathGraphics) {
      try {
        if (this.pathGraphics.clear) {
          this.pathGraphics.clear();
        }
        if (!this.pathGraphics.destroyed) {
          this.pathGraphics.destroy();
        }
      } catch (e) {
        console.warn('[IsometricGridRenderer] Error destroying path graphics:', e);
      }
    }
    
    // Call parent destroy
    super.destroy();
  }
} 