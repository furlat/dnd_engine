import { Graphics } from 'pixi.js';
import { battlemapStore } from '../../store';
import { TileSummary } from '../../types/battlemap_types';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { LayerName } from '../BattlemapEngine';
import { gridToIsometric, calculateIsometricGridOffset, calculateIsometricDiamondCorners } from '../../utils/isometricUtils';
import { EntitySummary, Position } from '../../types/common';

/**
 * IsometricTileRenderer handles rendering isometric tiles with basic colors
 */
export class IsometricTileRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'tiles'; }
  
  // Graphics references
  private tilesGraphics: Graphics = new Graphics();
  
  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];
  
  // Reference to tiles for stable rendering during movement
  private tilesRef: Record<string, TileSummary> = {};
  
  // Flag to track when tiles need to be redrawn
  private tilesNeedUpdate: boolean = true;
  
  // Last known position offset for movement detection
  private lastOffset = { x: 0, y: 0 };
  
  // Last known tile size for zoom detection
  private lastTileSize = 128;

  /**
   * Initialize the renderer
   */
  initialize(engine: any): void {
    super.initialize(engine);
    
    // Add graphics to container
    this.container.addChild(this.tilesGraphics);
    
    // Setup subscriptions
    this.setupSubscriptions();
    
    // Initial tile data
    this.tilesRef = {...battlemapStore.grid.tiles};
    
    // Initialize last offset
    this.lastOffset = { 
      x: battlemapStore.view.offset.x, 
      y: battlemapStore.view.offset.y 
    };
    
    // Initialize last tile size
    this.lastTileSize = battlemapStore.view.tileSize;
    
    // Force initial render
    this.tilesNeedUpdate = true;
    
    console.log('[IsometricTileRenderer] Initialized and added to tiles layer');
  }
  
  /**
   * Set up subscriptions to the Valtio store
   */
  private setupSubscriptions(): void {
    // Store unsubscribe functions
    this.unsubscribeCallbacks = [];
    
    // Subscribe to grid changes (for tile updates)
    const unsubGrid = subscribe(battlemapStore.grid, () => {
      // Only update tiles reference when not moving
      if (!battlemapStore.view.wasd_moving) {
        // Check if tiles have actually changed
        const hasChanges = this.hasTilesChanged(battlemapStore.grid.tiles);
        
        if (hasChanges) {
          this.tilesRef = {...battlemapStore.grid.tiles};
          this.tilesNeedUpdate = true;
        }
      }
      
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubGrid);
    
    // Subscribe to view changes (zooming, panning)
    const unsubView = subscribe(battlemapStore.view, () => {
      // Always render on view changes for panning/zooming
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubView);
    
    // Subscribe to control changes (e.g., tile visibility)
    const unsubControls = subscribe(battlemapStore.controls, () => {
      // Only need to re-render if tile visibility changed
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubControls);

    // NEW: Subscribe to pathSenses changes to trigger tile re-render when data becomes available
    const unsubPathSenses = subscribe(battlemapStore.entities.pathSenses, () => {
      // When path senses data becomes available, we need to re-render tiles immediately
      // This is a "hot swap" that provides dynamic visibility during movement
      this.tilesNeedUpdate = true;
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubPathSenses);
    
    // NEW: Subscribe to sprite mappings for snappy tile visibility updates during movement
    const unsubSpriteMappings = subscribe(battlemapStore.entities.spriteMappings, () => {
      // When visual positions change during movement, update tile visibility immediately
      // This makes tile visibility changes feel snappy and responsive
      const snap = battlemapStore;
      const selectedEntity = this.getSelectedEntity();
      
      // Only trigger re-render if the selected entity is moving (has dynamic path senses)
      if (selectedEntity && snap.entities.movementAnimations[selectedEntity.uuid] && snap.entities.pathSenses[selectedEntity.uuid]) {
        this.tilesNeedUpdate = true;
        this.render();
      }
    });
    this.unsubscribeCallbacks.push(unsubSpriteMappings);
  }
  
  /**
   * Check if the tiles have significantly changed to warrant a re-render
   */
  private hasTilesChanged(newTiles: Record<string, TileSummary>): boolean {
    // Quick check: different number of tiles
    if (Object.keys(this.tilesRef).length !== Object.keys(newTiles).length) {
      return true;
    }
    
    // Check each tile for changes
    for (const key in newTiles) {
      const oldTile = this.tilesRef[key];
      const newTile = newTiles[key];
      
      // New tile that didn't exist before
      if (!oldTile) {
        return true;
      }
      
      // Check for sprite changes (affects color)
      if (oldTile.sprite_name !== newTile.sprite_name) {
        return true;
      }
      
      // Check for walkable changes (affects color)
      if (oldTile.walkable !== newTile.walkable) {
        return true;
      }
    }
    
    // Check for removed tiles
    for (const key in this.tilesRef) {
      if (!newTiles[key]) {
        return true;
      }
    }
    
    return false;
  }
  
  /**
   * Get color for tile based on type and visibility
   */
  private getTileColor(tile: TileSummary, visible: boolean, seen: boolean): number {
    // If never seen, return black
    if (!seen) {
      return 0x000000; // Black for unseen areas
    }
    
    // Base color logic
    let baseColor: number;
    
    // Check sprite name first for specific types
    if (tile.sprite_name) {
      const spriteName = tile.sprite_name.toLowerCase();
      
      // Water tiles - blue
      if (spriteName.includes('water') || spriteName.includes('river') || spriteName.includes('lake')) {
        baseColor = 0x4A90E2; // Blue
      }
      // Wall/stone tiles - gray
      else if (spriteName.includes('wall') || spriteName.includes('stone') || spriteName.includes('brick')) {
        baseColor = 0x666666; // Gray
      }
      // Floor tiles - green
      else if (spriteName.includes('floor') || spriteName.includes('grass') || spriteName.includes('ground')) {
        baseColor = 0x7ED321; // Green
      }
      else {
        baseColor = tile.walkable ? 0x7ED321 : 0x666666;
      }
    } else {
      // Fallback to walkable status
      baseColor = tile.walkable ? 0x7ED321 : 0x666666;
    }
    
    // If seen but not currently visible, darken the color
    if (!visible) {
      // Convert to darker version (multiply RGB by 0.4)
      const r = Math.floor(((baseColor >> 16) & 0xFF) * 0.4);
      const g = Math.floor(((baseColor >> 8) & 0xFF) * 0.4);
      const b = Math.floor((baseColor & 0xFF) * 0.4);
      return (r << 16) | (g << 8) | b;
    }
    
    return baseColor;
  }

  /**
   * Get the selected entity for visibility calculations
   */
  private getSelectedEntity(): EntitySummary | null {
    const snap = battlemapStore;
    if (!snap.entities.selectedEntityId) return null;
    return snap.entities.summaries[snap.entities.selectedEntityId] || null;
  }

  /**
   * Get senses data for visibility calculations using dynamic path senses
   */
  private getSensesDataForVisibility(entity: EntitySummary): {
    visible: Record<string, boolean>;
    seen: readonly Position[];
  } {
    const snap = battlemapStore;
    
    // Check if the OBSERVER entity (the one we're getting senses for) is currently moving
    const observerMovementAnimation = snap.entities.movementAnimations[entity.uuid];
    
    if (observerMovementAnimation) {
      // The OBSERVER entity is moving - use dynamic path senses based on their current animated position
      // This ensures visibility is only dynamic when the observer themselves is moving
      const pathSenses = snap.entities.pathSenses[entity.uuid];
      
      if (pathSenses) {
        // Get the entity's current animated position with anticipation
        const spriteMapping = snap.entities.spriteMappings[entity.uuid];
        if (spriteMapping?.visualPosition) {
          // Use anticipation: switch to next cell's senses when we're at the center of the sprite
          // This makes visibility changes feel more natural and realistic
          const anticipationThreshold = 0.5;
          const currentX = Math.floor(spriteMapping.visualPosition.x + anticipationThreshold);
          const currentY = Math.floor(spriteMapping.visualPosition.y + anticipationThreshold);
          const posKey = `${currentX},${currentY}`;
          
          // Use senses data for the current animated position
          const currentPositionSenses = pathSenses[posKey];
          if (currentPositionSenses) {
            return {
              visible: currentPositionSenses.visible,
              seen: currentPositionSenses.seen
            };
          } else {
            // Path senses available but no data for current position - use entity's current senses
            // This can happen during the first few frames of movement before reaching the first path position
            return {
              visible: entity.senses.visible,
              seen: entity.senses.seen
            };
          }
        }
      } else {
        // Path senses not yet available (timing issue) - use entity's current senses as fallback
        // This is normal during the first few frames after movement starts
        return {
          visible: entity.senses.visible,
          seen: entity.senses.seen
        };
      }
    }
    
    // No movements or fallback - use current data
    return {
      visible: entity.senses.visible,
      seen: entity.senses.seen
    };
  }
  
  /**
   * Main render method
   */
  render(): void {
    if (!this.engine || !this.engine.app) {
      return;
    }
    
    // Update visibility based on controls
    this.tilesGraphics.visible = battlemapStore.controls.isTilesVisible;
    
    // Early exit if tiles are not visible
    if (!battlemapStore.controls.isTilesVisible) {
      this.tilesGraphics.clear();
      return;
    }
    
    // Check if position has changed (WASD movement) or if tiles need updating
    const hasPositionChanged = 
      this.lastOffset.x !== battlemapStore.view.offset.x || 
      this.lastOffset.y !== battlemapStore.view.offset.y;
    
    // Check if tile size has changed (zoom)
    const hasTileSizeChanged = this.lastTileSize !== battlemapStore.view.tileSize;
    
    // Render tiles if they need updating, position changed, size changed, or we're actively moving
    if (this.tilesNeedUpdate || hasPositionChanged || hasTileSizeChanged || battlemapStore.view.wasd_moving) {
      this.renderTiles();
      this.tilesNeedUpdate = false;
      
      // Update last known position and tile size after rendering
      this.lastOffset = { 
        x: battlemapStore.view.offset.x, 
        y: battlemapStore.view.offset.y 
      };
      this.lastTileSize = battlemapStore.view.tileSize;
    }
  }
  
  /**
   * Render the isometric tiles
   */
  private renderTiles(): void {
    // Check if graphics is available
    if (!this.tilesGraphics) {
      console.log('[IsometricTileRenderer] Tiles graphics not available');
      return;
    }

    // Clear previous tiles
    this.tilesGraphics.clear();

    // Get grid offset and sizes
    const snap = battlemapStore;
    const isometricOffset = calculateIsometricGridOffset(
      this.engine?.containerSize?.width || 0,
      this.engine?.containerSize?.height || 0,
      snap.grid.width,
      snap.grid.height,
      snap.view.tileSize,
      snap.view.offset.x,
      snap.view.offset.y,
      250 // ENTITY_PANEL_WIDTH
    );

    // Get visibility info for conditional rendering
    const selectedEntity = this.getSelectedEntity();
    const sensesData = selectedEntity && snap.controls.isVisibilityEnabled 
      ? this.getSensesDataForVisibility(selectedEntity) 
      : null;

    // Draw all tiles as colored diamonds
    Object.values(this.tilesRef).forEach(tile => {
      const [gridX, gridY] = tile.position;

      // Calculate visibility for this tile
      let visible = true;
      let seen = true;
      if (sensesData) {
        const posKey = `${gridX},${gridY}`;
        visible = !!sensesData.visible[posKey];
        seen = sensesData.seen.some(([seenX, seenY]) => seenX === gridX && seenY === gridY);
      }

      // Convert grid position to isometric coordinates
      const { isoX, isoY } = gridToIsometric(gridX, gridY);

      // Scale and position
      const scaledIsoX = isoX * isometricOffset.tileSize;
      const scaledIsoY = isoY * isometricOffset.tileSize;
      const centerX = isometricOffset.offsetX + scaledIsoX;
      const centerY = isometricOffset.offsetY + scaledIsoY;

      // Calculate diamond corners
      const corners = calculateIsometricDiamondCorners(
        centerX, 
        centerY, 
        isometricOffset.tileSize
      );

      // Get tile color with visibility
      const tileColor = this.getTileColor(tile, visible, seen);

      // Draw diamond tile
      this.tilesGraphics
        .moveTo(corners.topX, corners.topY)
        .lineTo(corners.rightX, corners.rightY)
        .lineTo(corners.bottomX, corners.bottomY)
        .lineTo(corners.leftX, corners.leftY)
        .lineTo(corners.topX, corners.topY)
        .fill({ color: tileColor, alpha: 0.8 })
        .stroke({ color: 0x333333, width: 1, alpha: 0.5 }); // Dark border
    });

    console.log('[IsometricTileRenderer] Rendered', Object.keys(this.tilesRef).length, 'isometric tiles');
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // Unsubscribe from all subscriptions
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
    // Clear and destroy graphics safely
    if (this.tilesGraphics) {
      try {
        if (this.tilesGraphics.clear) {
          this.tilesGraphics.clear();
        }
        if (!this.tilesGraphics.destroyed) {
          this.tilesGraphics.destroy();
        }
      } catch (e) {
        console.warn('[IsometricTileRenderer] Error destroying tiles graphics:', e);
      }
    }
    
    // Call parent destroy
    super.destroy();
  }
} 