import { Graphics, Container, Ticker } from 'pixi.js';
import { battlemapStore } from '../../store';
import { AbstractRenderer } from './BaseRenderer';
import { subscribe } from 'valtio';
import { LayerName } from '../BattlemapEngine';
import { EntitySummary, Position } from '../../types/common';
import { calculateGridOffset, addTileToContainer, createColorTile, ENTITY_PANEL_WIDTH } from './renderer_utils';

/**
 * SubjectiveRenderer handles visibility/fog of war overlays
 * This layer sits above entities/effects and selectively hides content
 * based on the selected entity's perception
 */
export class SubjectiveRenderer extends AbstractRenderer {
  // Specify which layer this renderer belongs to
  get layerName(): LayerName { return 'subjective'; }
  
  // NO ticker updates - we'll use store subscriptions only
  protected needsTickerUpdate: boolean = false;
  
  // Graphics for fog of war overlays
  private fogContainer: Container = new Container();
  
  // Graphics for movement path overlays
  private pathContainer: Container = new Container();
  
  // Graphics for grid overlay (always visible)
  private gridContainer: Container = new Container();
  
  // Store unsubscribe callbacks
  private unsubscribeCallbacks: Array<() => void> = [];
  
  // Cached senses data from before movement started
  private cachedSensesData: Map<string, {
    visible: Record<string, boolean>;
    seen: readonly Position[];
    paths: Record<string, readonly Position[]>;
  }> = new Map();
  
  // Change detection to avoid unnecessary re-renders
  private lastRenderHash: string = '';
  private lastSelectedEntityId: string | undefined = undefined;
  
  // Debug mode for troubleshooting (set to true when needed)
  private debugMode: boolean = false;
  
  // Summary logging system
  private lastSummaryTime = 0;
  private renderCount = 0;
  private skippedRenders = 0;

  /**
   * Initialize the renderer
   */
  initialize(engine: any): void {
    super.initialize(engine);
    
    // Add containers to main container (order matters for rendering)
    this.container.addChild(this.pathContainer); // Paths below fog
    this.container.addChild(this.fogContainer);  // Fog in middle
    this.container.addChild(this.gridContainer); // Grid on top (always visible)
    
    // Setup subscriptions
    this.setupSubscriptions();
    
    console.log('[SubjectiveRenderer] Initialized and added to subjective layer with ticker updates');
  }
  
  // Remove ticker update method - we don't need it
  
  // Remove the complex animation state checking - we'll use a simpler approach
  
  /**
   * Log summary every 10 seconds instead of spamming
   */
  private logSummary(): void {
    const now = Date.now();
    if (now - this.lastSummaryTime >= 10000) { // 10 seconds
      console.log(`[SubjectiveRenderer] 10s Summary: ${this.renderCount} actual renders, ${this.skippedRenders} skipped, ${this.cachedSensesData.size} cached entities`);
      this.lastSummaryTime = now;
      this.renderCount = 0;
      this.skippedRenders = 0;
    }
  }
  
  /**
   * Set up subscriptions to the Valtio store
   */
  private setupSubscriptions(): void {
    // Store unsubscribe functions
    this.unsubscribeCallbacks = [];
    
    // Subscribe to entities changes (for selected entity and visibility)
    const unsubEntities = subscribe(battlemapStore.entities, () => {
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubEntities);
    
    // Subscribe to view changes (for positioning)
    const unsubView = subscribe(battlemapStore.view, () => {
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubView);
    
    // Subscribe to control changes (for visibility toggle)
    const unsubControls = subscribe(battlemapStore.controls, () => {
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubControls);
    
    // Subscribe to grid changes (for tile positions)
    const unsubGrid = subscribe(battlemapStore.grid, () => {
      this.render();
    });
    this.unsubscribeCallbacks.push(unsubGrid);
  }
  
  /**
   * Calculate grid offset using shared utility
   */
  private getGridOffset() {
    const snap = battlemapStore;
    const containerSize = this.engine?.containerSize || { width: 0, height: 0 };
    
    return calculateGridOffset(
      containerSize,
      snap.grid.width,
      snap.grid.height,
      snap.view.tileSize,
      snap.view.offset
    );
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
   * Check if a tile position is visible to the given entity
   */
  private isTileVisible(x: number, y: number, entity: EntitySummary): boolean {
    const sensesData = this.getSensesData(entity);
    const posKey = `${x},${y}`;
    return !!sensesData.visible[posKey];
  }
  
  /**
   * Check if a tile position has been seen before by the given entity
   */
  private isTileSeen(x: number, y: number, entity: EntitySummary): boolean {
    const sensesData = this.getSensesData(entity);
    return sensesData.seen.some(
      ([seenX, seenY]) => seenX === x && seenY === y
    );
  }
  
  /**
   * Cache senses data for an entity when they start moving
   */
  private cacheSensesData(entityId: string, entity: EntitySummary): void {
    this.cachedSensesData.set(entityId, {
      visible: { ...entity.senses.visible },
      seen: [...entity.senses.seen],
      paths: { ...entity.senses.paths }
    });
    // Cache created (logged in summary)
  }
  
  /**
   * Get senses data for an entity - use cached data if animating, current data if synced
   * This is the ONLY place we check animation state to avoid triggering re-renders
   */
  private getSensesData(entity: EntitySummary): {
    visible: Record<string, boolean>;
    seen: readonly Position[];
    paths: Record<string, readonly Position[]>;
  } {
    const snap = battlemapStore;
    const spriteMapping = snap.entities.spriteMappings[entity.uuid];
    const isAnimating = !spriteMapping?.isPositionSynced;
    
    if (isAnimating) {
      // Entity is animating - use cached data if available, otherwise cache current data
      if (!this.cachedSensesData.has(entity.uuid)) {
        // Cache current senses data for this animation
        this.cacheSensesData(entity.uuid, entity);
      }
      return this.cachedSensesData.get(entity.uuid)!;
    } else {
      // Entity is synced - clear any cache and use current data
      if (this.cachedSensesData.has(entity.uuid)) {
        this.cachedSensesData.delete(entity.uuid);
      }
      return {
        visible: entity.senses.visible,
        seen: entity.senses.seen,
        paths: entity.senses.paths
      };
    }
  }
  
  /**
   * Update cached senses data when entities change - now simplified
   */
  private updateSensesCache(): void {
    // Cache management is now handled lazily in getSensesData()
    // This method is kept for compatibility but does nothing
  }
  
  /**
   * Main render method
   */
  render(): void {
    const snap = battlemapStore;
    
    // Get selected entity for both visibility and movement
    const selectedEntity = this.getSelectedEntity();
    
    if (!selectedEntity) {
      // Clear containers if no entity selected
      this.fogContainer.removeChildren();
      this.pathContainer.removeChildren();
      this.gridContainer.removeChildren();
      this.lastRenderHash = '';
      this.lastSelectedEntityId = undefined;
      return;
    }
    
    // Create a hash of the current render state to detect changes
    const currentHash = this.createRenderHash(selectedEntity, snap);
    
    // Skip render if nothing has changed
    if (currentHash === this.lastRenderHash && selectedEntity.uuid === this.lastSelectedEntityId) {
      this.skippedRenders++;
      if (this.debugMode) {
        console.log(`[SubjectiveRenderer] Skipped render - no changes detected`);
      }
      return;
    }
    
    // Something changed, do the actual render
    this.renderCount++;
    this.logSummary();
    
    if (this.debugMode) {
      console.log(`[SubjectiveRenderer] Rendering due to changes:`, {
        entityChanged: selectedEntity.uuid !== this.lastSelectedEntityId,
        hashChanged: currentHash !== this.lastRenderHash,
        entityId: selectedEntity.uuid
      });
    }
    
    this.lastRenderHash = currentHash;
    this.lastSelectedEntityId = selectedEntity.uuid;
    
    // Clear previous overlays
    this.fogContainer.removeChildren();
    this.pathContainer.removeChildren();
    this.gridContainer.removeChildren();
    
    // Render movement paths if enabled
    if (snap.controls.isMovementHighlightEnabled) {
      this.renderMovementPaths(selectedEntity);
    }
    
    // Render fog of war if visibility is enabled
    if (snap.controls.isVisibilityEnabled) {
      this.renderFogOfWar(selectedEntity);
    }
    
    // Render grid overlay only for unseen areas if grid is visible
    if (snap.controls.isGridVisible && snap.controls.isVisibilityEnabled) {
      this.renderGridOverlay(selectedEntity);
    }
  }
  
  /**
   * Create a hash of the current render state to detect changes
   */
  private createRenderHash(selectedEntity: EntitySummary, snap: any): string {
    const sensesData = this.getSensesData(selectedEntity);
    const spriteMapping = snap.entities.spriteMappings[selectedEntity.uuid];
    
    return JSON.stringify({
      entityId: selectedEntity.uuid,
      isAnimating: !spriteMapping?.isPositionSynced,
      visibilityEnabled: snap.controls.isVisibilityEnabled,
      movementHighlightEnabled: snap.controls.isMovementHighlightEnabled,
      gridVisible: snap.controls.isGridVisible,
      tileSize: snap.view.tileSize,
      offset: snap.view.offset,
      // Only include a sample of senses data to avoid huge hash
      visibleCount: Object.keys(sensesData.visible).length,
      seenCount: sensesData.seen.length,
      pathsCount: Object.keys(sensesData.paths).length
    });
  }
  
  /**
   * Get the tile at a specific position
   */
  private getTileAtPosition(x: number, y: number) {
    const snap = battlemapStore;
    const posKey = `${x},${y}`;
    return snap.grid.tiles[posKey] || null;
  }
  
  /**
   * Render fog of war overlays
   */
  private renderFogOfWar(entity: EntitySummary): void {
    const snap = battlemapStore;
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = this.getGridOffset();
    
    // Create fog graphics for each tile
    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        const visible = this.isTileVisible(x, y, entity);
        const seen = this.isTileSeen(x, y, entity);
        const tile = this.getTileAtPosition(x, y);
        
        if (!visible && !seen) {
          // Never seen - completely black
          const blackTile = createColorTile(
            offsetX + (x * tileSize),
            offsetY + (y * tileSize),
            tileSize,
            0x000000,
            1.0
          );
          this.fogContainer.addChild(blackTile);
        } else if (!visible && seen && tile) {
          // Seen but not visible - redraw tile then apply fog
          // First redraw the tile to mask anything underneath (entities, etc.)
          addTileToContainer(this.fogContainer, x, y, tile, offsetX, offsetY, tileSize);
          
          // Then apply fog of war on top
          const fogTile = createColorTile(
            offsetX + (x * tileSize),
            offsetY + (y * tileSize),
            tileSize,
            0x000000,
            0.6
          );
          this.fogContainer.addChild(fogTile);
        }
        // If visible, no fog - let the underlying layers show through
      }
    }
    
    // Removed spammy log - use summary instead
  }
  
  /**
   * Render movement path highlights
   */
  private renderMovementPaths(entity: EntitySummary): void {
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = this.getGridOffset();
    const sensesData = this.getSensesData(entity);
    
    // Render movement range highlights
    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        const posKey = `${x},${y}`;
        const path = sensesData.paths[posKey];
        
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
          
          const pathTile = new Graphics();
          pathTile
            .rect(
              offsetX + (x * tileSize),
              offsetY + (y * tileSize),
              tileSize,
              tileSize
            )
            .fill({ color: pathColor, alpha: pathAlpha });
          
          this.pathContainer.addChild(pathTile);
        }
      }
    }
    
    // Removed spammy log - use summary instead
  }
  
  /**
   * Render grid overlay only for unseen areas (to avoid double-drawing with main grid)
   */
  private renderGridOverlay(entity: EntitySummary): void {
    const snap = battlemapStore;
    const { offsetX, offsetY, tileSize, gridWidth, gridHeight } = this.getGridOffset();
    
    // Create grid graphics
    const gridGraphics = new Graphics();
    
    // Only draw grid lines that pass through unseen areas
    // We'll draw line segments only where they cross unseen tiles
    
    // Draw vertical lines (only segments in unseen areas)
    for (let x = 0; x <= gridWidth; x++) {
      const lineX = offsetX + x * tileSize;
      
      let segmentStart = -1;
      for (let y = 0; y <= gridHeight; y++) {
        const tileY = y < gridHeight ? y : y - 1; // Handle edge case for last line
        const isUnseen = tileY >= 0 && tileY < gridHeight && !this.isTileVisible(x < gridWidth ? x : x - 1, tileY, entity) && !this.isTileSeen(x < gridWidth ? x : x - 1, tileY, entity);
        
        if (isUnseen && segmentStart === -1) {
          // Start a new segment
          segmentStart = y;
        } else if (!isUnseen && segmentStart !== -1) {
          // End the current segment
          const startY = offsetY + segmentStart * tileSize;
          const endY = offsetY + y * tileSize;
          gridGraphics.moveTo(lineX, startY).lineTo(lineX, endY);
          segmentStart = -1;
        }
      }
      
      // Handle segment that goes to the end
      if (segmentStart !== -1) {
        const startY = offsetY + segmentStart * tileSize;
        const endY = offsetY + gridHeight * tileSize;
        gridGraphics.moveTo(lineX, startY).lineTo(lineX, endY);
      }
    }
    
    // Draw horizontal lines (only segments in unseen areas)
    for (let y = 0; y <= gridHeight; y++) {
      const lineY = offsetY + y * tileSize;
      
      let segmentStart = -1;
      for (let x = 0; x <= gridWidth; x++) {
        const tileX = x < gridWidth ? x : x - 1; // Handle edge case for last line
        const isUnseen = tileX >= 0 && tileX < gridWidth && !this.isTileVisible(tileX, y < gridHeight ? y : y - 1, entity) && !this.isTileSeen(tileX, y < gridHeight ? y : y - 1, entity);
        
        if (isUnseen && segmentStart === -1) {
          // Start a new segment
          segmentStart = x;
        } else if (!isUnseen && segmentStart !== -1) {
          // End the current segment
          const startX = offsetX + segmentStart * tileSize;
          const endX = offsetX + x * tileSize;
          gridGraphics.moveTo(startX, lineY).lineTo(endX, lineY);
          segmentStart = -1;
        }
      }
      
      // Handle segment that goes to the end
      if (segmentStart !== -1) {
        const startX = offsetX + segmentStart * tileSize;
        const endX = offsetX + gridWidth * tileSize;
        gridGraphics.moveTo(startX, lineY).lineTo(endX, lineY);
      }
    }
    
    // Apply stroke with pixelLine for pixel-perfect grid lines
    gridGraphics.stroke({ color: 0x444444, pixelLine: true });
    
    this.gridContainer.addChild(gridGraphics);
    
    // Removed spammy log - use summary instead
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    // Clear caches
    this.cachedSensesData.clear();
    
    // Unsubscribe from all subscriptions
    this.unsubscribeCallbacks.forEach(unsubscribe => unsubscribe());
    this.unsubscribeCallbacks = [];
    
    // Clear and destroy containers
    if (this.fogContainer) {
      this.fogContainer.removeChildren();
      try {
        if (!this.fogContainer.destroyed) {
          this.fogContainer.destroy({ children: true });
        }
      } catch (e) {
        console.warn('[SubjectiveRenderer] Error destroying fog container:', e);
      }
    }
    
    if (this.pathContainer) {
      this.pathContainer.removeChildren();
      try {
        if (!this.pathContainer.destroyed) {
          this.pathContainer.destroy({ children: true });
        }
      } catch (e) {
        console.warn('[SubjectiveRenderer] Error destroying path container:', e);
      }
    }
    
    if (this.gridContainer) {
      this.gridContainer.removeChildren();
      try {
        if (!this.gridContainer.destroyed) {
          this.gridContainer.destroy({ children: true });
        }
      } catch (e) {
        console.warn('[SubjectiveRenderer] Error destroying grid container:', e);
      }
    }
    
    // Call parent destroy
    super.destroy();
  }
} 