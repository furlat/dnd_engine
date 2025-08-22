import { Graphics } from 'pixi.js';
import { battlemapStore } from '../../../store';
import { LayerName } from '../../BattlemapEngine';
import { EntitySummary } from '../../../types/common';
import { ENTITY_PANEL_WIDTH, GRID_STROKE_WIDTH } from '../../../constants/layout';
import { 
  gridToIsometric, 
  calculateIsometricGridOffset,
  calculateIsometricDiamondCorners,
  screenToGrid
} from '../../../utils/isometricUtils';

/**
 * Isometric rendering utilities extracted from renderers
 * Following the guide structure for shared functionality
 */
export class IsometricRenderingUtils {
  /**
   * Calculate grid offset with proper centering for isometric view
   * Centralized version used by all isometric renderers
   */
  static calculateIsometricGridOffset(engine: any): { 
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
    const containerSize = engine?.containerSize || { width: 0, height: 0 };
    
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
   * Get the selected entity for visibility calculations
   * Centralized version used by all renderers
   */
  static getSelectedEntity(): EntitySummary | null {
    const snap = battlemapStore;
    if (!snap.entities.selectedEntityId) return null;
    return snap.entities.summaries[snap.entities.selectedEntityId] || null;
  }
  
  /**
   * Convert screen pixel coordinates to grid coordinates (for mouse interaction)
   * Centralized version with proper isometric conversion
   */
  static screenToGrid(
    screenX: number, 
    screenY: number, 
    engine: any
  ): { gridX: number; gridY: number; inBounds: boolean } {
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = 
      this.calculateIsometricGridOffset(engine);
    
    return screenToGrid(screenX, screenY, offsetX, offsetY, tileSize, gridWidth, gridHeight);
  }
  
  /**
   * Render an isometric diamond at grid coordinates
   * Common pattern used by grid, tile, and effect renderers
   */
  static renderIsometricDiamond(
    graphics: Graphics,
    gridX: number,
    gridY: number,
    engine: any,
    fillOptions?: { color: number; alpha: number },
    strokeOptions?: { color: number; width: number; alpha?: number }
  ): void {
    const { offsetX, offsetY, tileSize } = this.calculateIsometricGridOffset(engine);
    
    // Convert grid coordinates to isometric
    const { isoX, isoY } = gridToIsometric(gridX, gridY);
    
    // Scale the isometric coordinates
    const scaledIsoX = isoX * tileSize;
    const scaledIsoY = isoY * tileSize;
    
    // Calculate the diamond using utility function
    const centerX = offsetX + scaledIsoX;
    const centerY = offsetY + scaledIsoY;
    const strokeOffset = strokeOptions ? (strokeOptions.width || GRID_STROKE_WIDTH) * 0.5 : 0;
    
    const { topX, topY, rightX, rightY, bottomX, bottomY, leftX, leftY } = 
      calculateIsometricDiamondCorners(centerX, centerY, tileSize, strokeOffset);
    
    // Draw diamond path
    graphics
      .moveTo(topX, topY)
      .lineTo(rightX, rightY)
      .lineTo(bottomX, bottomY)
      .lineTo(leftX, leftY)
      .lineTo(topX, topY);
    
    // Apply fill if specified
    if (fillOptions) {
      graphics.fill({ color: fillOptions.color, alpha: fillOptions.alpha });
    }
    
    // Apply stroke if specified
    if (strokeOptions) {
      graphics.stroke({ 
        color: strokeOptions.color, 
        width: strokeOptions.width,
        alpha: strokeOptions.alpha || 1.0
      });
    }
  }
  
  /**
   * Render multiple isometric diamonds in a batch
   * Optimized for rendering many tiles/grid cells at once
   */
  static renderIsometricDiamondBatch(
    graphics: Graphics,
    positions: Array<{ x: number; y: number }>,
    engine: any,
    fillOptions?: { color: number; alpha: number },
    strokeOptions?: { color: number; width: number; alpha?: number }
  ): void {
    positions.forEach(({ x, y }) => {
      this.renderIsometricDiamond(graphics, x, y, engine, fillOptions, strokeOptions);
    });
  }
  
  /**
   * Check if a grid position is valid within bounds
   */
  static isValidGridPosition(gridX: number, gridY: number): boolean {
    const snap = battlemapStore;
    return gridX >= 0 && gridY >= 0 && gridX < snap.grid.width && gridY < snap.grid.height;
  }
  
  /**
   * Get movement path color based on distance
   * Common logic used in path rendering
   */
  static getMovementPathColor(pathLength: number): { color: number; alpha: number } {
    if (pathLength <= 6) {
      // Within 30ft (6 squares) - green
      return { color: 0x00FF00, alpha: 0.3 };
    } else if (pathLength <= 12) {
      // Within 60ft (12 squares) - yellow
      return { color: 0xFFFF00, alpha: 0.25 };
    } else {
      // Beyond 60ft - red
      return { color: 0xFF0000, alpha: 0.2 };
    }
  }
} 