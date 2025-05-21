import { FederatedPointerEvent, Graphics } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../store';
import { BattlemapEngine } from './BattlemapEngine';
import { createTile, deleteTile } from '../api/battlemap/battlemapApi';
import { TileSummary } from '../types/battlemap_types';
import { v4 as uuidv4 } from 'uuid';

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * InteractionsManager handles user input and edits
 */
export class InteractionsManager {
  // Reference to the engine
  private engine: BattlemapEngine | null = null;
  
  // Hit area for detecting mouse events
  private hitArea: Graphics | null = null;

  /**
   * Initialize with the engine
   * @param engine The battlemap engine
   */
  initialize(engine: BattlemapEngine): void {
    this.engine = engine;
    
    if (!engine.app) {
      console.error('[InteractionsManager] Cannot initialize - engine app is null');
      return;
    }
    
    // Create hit area
    this.createHitArea();
    
    console.log('[InteractionsManager] Initialized');
  }
  
  /**
   * Create a hit area for mouse interaction
   */
  private createHitArea(): void {
    if (!this.engine?.app?.stage) return;
    
    // Create a hit area that covers the entire visible area
    this.hitArea = new Graphics()
      .rect(0, 0, this.engine.containerSize.width, this.engine.containerSize.height)
      .fill(0xFFFFFF, 0.001);
    
    // Configure hit area
    this.hitArea.eventMode = 'static';
    this.hitArea.cursor = 'pointer';
    
    // Add event listeners
    this.hitArea.on('pointermove', this.handlePointerMove.bind(this));
    this.hitArea.on('pointerdown', this.handlePointerDown.bind(this));
    this.hitArea.on('pointerleave', () => {
      battlemapActions.setHoveredCell(-1, -1);
    });
    
    // Add to stage
    this.engine.app.stage.addChild(this.hitArea);
  }
  
  /**
   * Calculate grid offset
   */
  private calculateGridOffset(): { 
    offsetX: number, 
    offsetY: number, 
    tileSize: number 
  } {
    const snap = battlemapStore;
    const containerSize = this.engine?.containerSize || { width: 0, height: 0 };
    
    const availableWidth = containerSize.width - ENTITY_PANEL_WIDTH;
    const gridPixelWidth = snap.grid.width * snap.view.tileSize;
    const gridPixelHeight = snap.grid.height * snap.view.tileSize;
    
    // Center grid in the available space
    const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
    const baseOffsetY = (containerSize.height - gridPixelHeight) / 2;
    
    // Apply the offset from WASD controls
    const offsetX = baseOffsetX + snap.view.offset.x;
    const offsetY = baseOffsetY + snap.view.offset.y;
    
    return { offsetX, offsetY, tileSize: snap.view.tileSize };
  }
  
  /**
   * Convert pixel coordinates to grid coordinates
   */
  private pixelToGrid(pixelX: number, pixelY: number): { 
    gridX: number; 
    gridY: number; 
    inBounds: boolean 
  } {
    const snap = battlemapStore;
    const { offsetX, offsetY, tileSize } = this.calculateGridOffset();
    
    // Adjust pixel coords by the offset
    const relativeX = pixelX - offsetX;
    const relativeY = pixelY - offsetY;
    
    // Convert to grid coordinates
    const gridX = Math.floor(relativeX / tileSize);
    const gridY = Math.floor(relativeY / tileSize);
    
    // Check if in bounds
    const inBoundsX = gridX >= 0 && gridX < snap.grid.width;
    const inBoundsY = gridY >= 0 && gridY < snap.grid.height;
    
    return { 
      gridX: inBoundsX ? gridX : -1,
      gridY: inBoundsY ? gridY : -1,
      inBounds: inBoundsX && inBoundsY
    };
  }
  
  /**
   * Handle pointer movement
   */
  private handlePointerMove(event: FederatedPointerEvent): void {
    const snap = battlemapStore;
    
    // Skip handling during WASD movement or when locked
    if (snap.controls.isLocked || snap.view.wasd_moving) return;
    
    // Convert to grid coordinates
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY, inBounds } = this.pixelToGrid(mouseX, mouseY);
    
    // Update store with hovered cell position
    battlemapActions.setHoveredCell(gridX, gridY);
  }
  
  /**
   * Handle pointer down (click)
   */
  private handlePointerDown(event: FederatedPointerEvent): void {
    const snap = battlemapStore;
    
    // Skip handling during WASD movement or when locked
    if (snap.controls.isLocked || snap.view.wasd_moving) return;
    
    // Convert to grid coordinates
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY } = this.pixelToGrid(mouseX, mouseY);
    
    // If we're editing tiles, handle tile placement
    if (snap.controls.isEditing) {
      this.handleTileEdit(gridX, gridY);
    }
  }
  
  /**
   * Handle tile editing
   */
  private async handleTileEdit(x: number, y: number): Promise<void> {
    const snap = battlemapStore;
    const selectedTile = snap.controls.selectedTileType;
    
    // Skip if position is invalid
    if (x < 0 || y < 0) return;
    
    console.log('[InteractionsManager] Editing tile:', { 
      position: [x, y], 
      selectedTile
    });
    
    // Special case for eraser - call the delete API
    if (selectedTile === 'erase') {
      try {
        await deleteTile(x, y);
        console.log('[InteractionsManager] Tile deleted successfully at position:', [x, y]);
        // Refresh the grid after deletion
        battlemapActions.fetchGridSnapshot();
      } catch (error) {
        console.error('[InteractionsManager] Error deleting tile:', error);
      }
      return;
    }
    
    // Get default properties for the selected tile type
    const getDefaultTileProperties = (tileType: string): Partial<TileSummary> => {
      switch (tileType) {
        case 'floor':
          return {
            walkable: true,
            visible: true,
            sprite_name: 'floor.png',
            name: 'Floor'
          };
        case 'wall':
          return {
            walkable: false,
            visible: false,
            sprite_name: 'wall.png',
            name: 'Wall'
          };
        case 'water':
          return {
            walkable: false,
            visible: true,
            sprite_name: 'water.png',
            name: 'Water'
          };
        case 'lava':
          return {
            walkable: false,
            visible: true,
            sprite_name: 'lava.png',
            name: 'Lava'
          };
        case 'grass':
          return {
            walkable: true,
            visible: true,
            sprite_name: 'grass.png',
            name: 'Grass'
          };
        default:
          return {
            walkable: true,
            visible: true,
            name: 'Unknown'
          };
      }
    };
    
    try {
      // Make API call to create tile
      console.log('[InteractionsManager] Creating tile on server:', { 
        position: [x, y], 
        type: selectedTile 
      });
      await createTile([x, y], selectedTile);
      
      console.log('[InteractionsManager] Tile created successfully');
      // Refresh the grid to ensure server state is reflected
      battlemapActions.fetchGridSnapshot();
    } catch (error) {
      console.error('[InteractionsManager] Error creating tile:', error);
    }
  }
  
  /**
   * Resize the hit area when container size changes
   */
  resize(): void {
    if (!this.engine || !this.hitArea) return;
    
    this.hitArea.clear();
    this.hitArea
      .rect(0, 0, this.engine.containerSize.width, this.engine.containerSize.height)
      .fill(0xFFFFFF, 0.001);
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    if (this.hitArea) {
      this.hitArea.removeAllListeners();
      this.hitArea.destroy();
      this.hitArea = null;
    }
    
    this.engine = null;
  }
} 