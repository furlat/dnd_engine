import { Graphics } from 'pixi.js';
import { battlemapStore } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { LayerName } from '../BattlemapEngine';
import { GRID_STROKE_WIDTH } from '../../constants/layout';
import { IsometricRenderingUtils } from './utils/IsometricRenderingUtils';

/**
 * IsometricGridRenderer - Clean, focused grid rendering
 * CLEANED: Removed excessive action handling and redundant code
 */
export class IsometricGridRenderer extends AbstractRenderer {
  get layerName(): LayerName { return 'grid'; }
  
  private gridGraphics = new Graphics();
  private highlightGraphics = new Graphics();
  private pathGraphics = new Graphics();

  initialize(engine: any): void {
    super.initialize(engine);
    this.container.addChild(this.gridGraphics, this.highlightGraphics, this.pathGraphics);
    this.setupSubscriptions();
  }
  
  private setupSubscriptions(): void {
    this.addSubscription(subscribe(battlemapStore.view, () => this.render()));
    this.addSubscription(subscribe(battlemapStore.controls, () => this.render()));
  }
  
  render(): void {
    this.incrementRenderCount();
    this.renderGrid();
    this.renderHighlight();
    this.renderPaths();
    this.logRenderSummary();
  }
  
  private renderGrid(): void {
    if (!this.isEngineReady()) return;
    
    this.gridGraphics.clear();
    if (!battlemapStore.controls.isGridVisible) return;
    
    const { gridWidth, gridHeight } = IsometricRenderingUtils.calculateIsometricGridOffset(this.engine);
    const positions = [];
    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        positions.push({ x, y });
      }
    }
    
    IsometricRenderingUtils.renderIsometricDiamondBatch(
      this.gridGraphics, positions, this.engine, undefined,
      { color: 0x444444, width: GRID_STROKE_WIDTH }
    );
  }
  
  private renderHighlight(): void {
    this.highlightGraphics.clear();
    if (battlemapStore.view.wasd_moving) return;
    
    const { x, y } = battlemapStore.view.hoveredCell;
    if (!IsometricRenderingUtils.isValidGridPosition(x, y)) return;
    
    IsometricRenderingUtils.renderIsometricDiamond(
      this.highlightGraphics, x, y, this.engine,
      { color: 0x00FF00, alpha: 0.3 }
    );
  }
  
  private renderPaths(): void {
    this.pathGraphics.clear();
    if (!battlemapStore.controls.isMovementHighlightEnabled) return;
    
    const selectedEntity = IsometricRenderingUtils.getSelectedEntity();
    if (!selectedEntity) return;
    
    const { gridWidth, gridHeight } = IsometricRenderingUtils.calculateIsometricGridOffset(this.engine);
    const coloredPaths = new Map<string, Array<{ x: number; y: number }>>();
    
    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        const path = selectedEntity.senses.paths[`${x},${y}`];
        if (!path?.length) continue;
        
        const { color, alpha } = IsometricRenderingUtils.getMovementPathColor(path.length);
        const key = `${color}_${alpha}`;
        
        if (!coloredPaths.has(key)) coloredPaths.set(key, []);
        coloredPaths.get(key)!.push({ x, y });
      }
    }
    
    coloredPaths.forEach((positions, key) => {
      const [colorStr, alphaStr] = key.split('_');
      IsometricRenderingUtils.renderIsometricDiamondBatch(
        this.pathGraphics, positions, this.engine,
        { color: parseInt(colorStr), alpha: parseFloat(alphaStr) }
      );
    });
  }
  
  public screenToGrid(screenX: number, screenY: number) {
    return IsometricRenderingUtils.screenToGrid(screenX, screenY, this.engine);
  }
  
  destroy(): void {
    this.destroyGraphicsArray([this.gridGraphics, this.highlightGraphics, this.pathGraphics]);
    super.destroy();
  }
} 