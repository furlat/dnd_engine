import { Graphics, FederatedPointerEvent, Container } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../store';
import { createTile, deleteTile } from '../api/battlemap/battlemapApi';
import { BattlemapEngine, LayerName } from './BattlemapEngine';
import { TileSummary } from '../types/battlemap_types';

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * InteractionsManager handles user input and interactions with the battlemap
 * It manages mouse/touch events for tile editing and entity selection
 */
export class InteractionsManager {
  // Engine reference
  private engine: BattlemapEngine | null = null;
  
  // Hit area for capturing events (transparent overlay)
  private hitArea: Graphics | null = null;
  
  // Layer reference for proper integration
  private layer: Container | null = null;
  
  /**
   * Initialize the interactions manager
   */
  initialize(engine: BattlemapEngine): void {
    this.engine = engine;
    
    // Get the UI layer for interaction overlay
    this.layer = engine.getLayer('ui');
    
    // Create hit area for event handling
    this.createHitArea();
    
    console.log('[InteractionsManager] Initialized with UI layer');
  }
  
  /**
   * Create a transparent hit area that covers the entire canvas
   * This captures all mouse/touch events for the battlemap
   */
  private createHitArea(): void {
    if (!this.engine?.app || !this.layer) return;
    
    // Create a transparent graphics object that covers the entire canvas
    this.hitArea = new Graphics();
    
    // Set initial size
    this.updateHitAreaSize();
    
    // Enable interactions
    this.hitArea.eventMode = 'static';
    this.hitArea.cursor = 'crosshair';
    
    // Set up event listeners
    this.hitArea.on('pointermove', this.handlePointerMove.bind(this));
    this.hitArea.on('pointerdown', this.handlePointerDown.bind(this));
    
    // Add to UI layer
    this.layer.addChild(this.hitArea);
    
    console.log('[InteractionsManager] Hit area created and added to UI layer');
  }
  
  /**
   * Update hit area size to match container
   */
  private updateHitAreaSize(): void {
    if (!this.hitArea || !this.engine) return;
    
    const { width, height } = this.engine.containerSize;
    
    this.hitArea.clear();
    this.hitArea
      .rect(0, 0, width, height)
      .fill({ color: 0xFFFFFF, alpha: 0.001 }); // Nearly transparent
  }
  
  /**
   * Calculate grid offset with proper centering
   * This matches the calculation used in renderers for consistency
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
   * Handle pointer movement for hover effects
   */
  private handlePointerMove(event: FederatedPointerEvent): void {
    const snap = battlemapStore;
    
    // Skip handling during WASD movement for better performance
    if (snap.view.wasd_moving) return;
    
    // Convert to grid coordinates
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY } = this.pixelToGrid(mouseX, mouseY);
    
    // Always update hovered cell position
    battlemapActions.setHoveredCell(gridX, gridY);
  }
  
  /**
   * Handle pointer down (click) events
   */
  private handlePointerDown(event: FederatedPointerEvent): void {
    const snap = battlemapStore;
    
    // Skip handling during WASD movement
    if (snap.view.wasd_moving) return;
    
    // Convert to grid coordinates
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY, inBounds } = this.pixelToGrid(mouseX, mouseY);
    
    if (!inBounds) return;
    
    // Handle tile editing if enabled and not locked
    if (snap.controls.isEditing && !snap.controls.isLocked) {
      this.handleTileEdit(gridX, gridY);
    }
    
    // TODO: Handle entity selection here when entity system is implemented
    // if (!snap.controls.isEditing) {
    //   this.handleEntitySelection(gridX, gridY);
    // }
  }
  
  /**
   * Handle tile editing operations
   */
  private async handleTileEdit(x: number, y: number): Promise<void> {
    const snap = battlemapStore;
    const selectedTile = snap.controls.selectedTileType;
    
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
    this.updateHitAreaSize();
    console.log('[InteractionsManager] Hit area resized');
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
    this.layer = null;
    
    console.log('[InteractionsManager] Destroyed');
  }
} 