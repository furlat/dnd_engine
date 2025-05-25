import { Graphics, FederatedPointerEvent, Container } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../store';
import { createTile, deleteTile, moveEntity, getEntitiesAtPosition, executeAttack } from '../api/battlemap/battlemapApi';
import { BattlemapEngine, LayerName } from './BattlemapEngine';
import { TileSummary, Direction, MovementAnimation, toVisualPosition, AnimationState } from '../types/battlemap_types';
import { Position } from '../types/common';

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
  
  // Context menu event handler reference for cleanup
  private contextMenuHandler: ((event: Event) => boolean) | null = null;
  
  // Click throttling to prevent rapid inputs
  private lastClickTime: number = 0;
  private readonly CLICK_THROTTLE_MS = 300;
  
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
    
    // Prevent browser context menu on right-click
    this.hitArea.on('rightclick', (event: FederatedPointerEvent) => {
      event.preventDefault();
      event.stopPropagation();
    });
    
    // Also prevent context menu at the DOM level
    if (this.engine?.app?.canvas) {
      this.contextMenuHandler = (event: Event) => {
        event.preventDefault();
        event.stopPropagation();
        return false;
      };
      this.engine.app.canvas.addEventListener('contextmenu', this.contextMenuHandler);
    }
    
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
    
    // Throttle clicks to prevent rapid inputs
    const currentTime = Date.now();
    if (currentTime - this.lastClickTime < this.CLICK_THROTTLE_MS) {
      console.log(`[InteractionsManager] Click throttled (${currentTime - this.lastClickTime}ms since last click)`);
      return;
    }
    this.lastClickTime = currentTime;
    
    // Convert to grid coordinates
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY, inBounds } = this.pixelToGrid(mouseX, mouseY);
    
    if (!inBounds) return;
    
    // Handle tile editing if enabled and not locked
    if (snap.controls.isEditing && !snap.controls.isLocked) {
      this.handleTileEdit(gridX, gridY);
      return;
    }
    
    // Handle entity interactions if not editing
    if (!snap.controls.isEditing) {
      // Check if this is a right-click (button 2)
      if (event.button === 2) {
        // Right-click: try attack first, fallback to movement
        this.handleRightClick(gridX, gridY);
      } else {
        // Left-click for movement
        this.handleEntityMovement(gridX, gridY);
      }
    }
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
   * Handle right-click: try attack first, fallback to movement
   */
  private async handleRightClick(gridX: number, gridY: number): Promise<void> {
    try {
      // First, check if there are entities at the target position
      const entitiesAtPosition = await getEntitiesAtPosition(gridX, gridY);
      
      if (entitiesAtPosition.length > 0) {
        // There are entities at this position, try to attack
        console.log(`[InteractionsManager] Right-click on position with entities, attempting attack`);
        await this.handleEntityAttack(gridX, gridY);
      } else {
        // No entities at this position, fallback to movement
        console.log(`[InteractionsManager] Right-click on empty position, fallback to movement`);
        await this.handleEntityMovement(gridX, gridY);
      }
    } catch (error) {
      console.error(`[InteractionsManager] Error handling right-click:`, error);
      // On error, fallback to movement
      await this.handleEntityMovement(gridX, gridY);
    }
  }
  
  /**
   * Handle entity attack operations (right-click)
   */
  private async handleEntityAttack(gridX: number, gridY: number): Promise<void> {
    const snap = battlemapStore;
    const selectedEntityId = snap.entities.selectedEntityId;
    
    if (!selectedEntityId) {
      console.log('[InteractionsManager] No entity selected for attack');
      return;
    }
    
    const attacker = snap.entities.summaries[selectedEntityId];
    if (!attacker) {
      console.warn('[InteractionsManager] Selected entity not found');
      return;
    }
    
    // Check if entity is ready for input
    if (!this.isEntityReadyForInput(selectedEntityId)) {
      console.log(`[InteractionsManager] Entity ${attacker.name} is not ready for input, ignoring attack command`);
      return;
    }
    
    try {
      // Get entities at the target position
      const entitiesAtPosition = await getEntitiesAtPosition(gridX, gridY);
      
      if (entitiesAtPosition.length === 0) {
        console.log(`[InteractionsManager] No entities at position ${gridX},${gridY} to attack`);
        return;
      }
      
      // Find the first entity that is not the attacker
      const target = entitiesAtPosition.find(entity => entity.uuid !== selectedEntityId);
      
      if (!target) {
        console.log(`[InteractionsManager] No valid target found at position ${gridX},${gridY}`);
        return;
      }
      
      console.log(`[InteractionsManager] ${attacker.name} attempting to attack ${target.name} at position ${gridX},${gridY}`);
      
      // Check if attacker is adjacent to target
      if (this.isAdjacentToTarget(attacker.position, target.position)) {
        // Direct attack
        console.log(`[InteractionsManager] ${attacker.name} is adjacent to ${target.name}, attacking directly`);
        await this.executeDirectAttack(selectedEntityId, target.uuid);
      } else {
        // Move and attack - start movement first
        console.log(`[InteractionsManager] ${attacker.name} needs to move to attack ${target.name}`);
        await this.executeMoveAndAttack(selectedEntityId, target.uuid, target.position);
      }
      
    } catch (error) {
      console.error(`[InteractionsManager] Error handling attack:`, error);
    }
  }
  
  /**
   * Check if an entity is adjacent to a target position
   */
  private isAdjacentToTarget(entityPosition: Position, targetPosition: Position): boolean {
    const [entityX, entityY] = entityPosition;
    const [targetX, targetY] = targetPosition;
    
    const dx = Math.abs(entityX - targetX);
    const dy = Math.abs(entityY - targetY);
    
    // Adjacent means within 1 tile in any direction (including diagonals)
    return dx <= 1 && dy <= 1 && (dx > 0 || dy > 0);
  }
  
  /**
   * Execute a direct attack (entities are adjacent)
   */
  private async executeDirectAttack(attackerId: string, targetId: string): Promise<void> {
    const attacker = battlemapStore.entities.summaries[attackerId];
    const target = battlemapStore.entities.summaries[targetId];
    
    if (!attacker || !target) return;
    
    try {
      console.log(`[InteractionsManager] ${attacker.name} attacking ${target.name} directly`);
      
      // FIRST: Set direction to face the target BEFORE marking as out-of-sync
      const direction = this.computeDirection(attacker.position, target.position);
      
      // Clear any local direction state that might interfere with attack direction
      const entityRenderer = this.engine?.getRenderer('EntityRenderer');
      if (entityRenderer && 'clearLocalDirectionState' in entityRenderer) {
        (entityRenderer as any).clearLocalDirectionState(attackerId);
      }
      
      battlemapActions.setEntityDirectionFromMapping(attackerId, direction);
      console.log(`[InteractionsManager] Set attack direction for ${attacker.name}: ${direction}`);
      
      // THEN: Mark entity as out-of-sync to block further inputs
      const spriteMapping = battlemapStore.entities.spriteMappings[attackerId];
      if (spriteMapping) {
        battlemapActions.updateEntityVisualPosition(attackerId, spriteMapping.visualPosition || { x: attacker.position[0], y: attacker.position[1] });
      }
      
      // FINALLY: Trigger attack animation (should use the direction we just set)
      battlemapActions.setEntityAnimation(attackerId, AnimationState.ATTACK1);
      
      // Execute the attack
      const attackResult = await executeAttack(attackerId, targetId, 'MAIN_HAND');
      
      console.log(`[InteractionsManager] Attack successful:`, attackResult);
      
      // Refresh entity summaries to get updated health/status
      await battlemapActions.fetchEntitySummaries();
      
    } catch (error) {
      console.error(`[InteractionsManager] Attack failed:`, error);
      
      // Return to idle animation on failure
      const spriteMapping = battlemapStore.entities.spriteMappings[attackerId];
      if (spriteMapping) {
        battlemapActions.setEntityAnimation(attackerId, spriteMapping.idleAnimation);
      }
    }
  }
  
  /**
   * Execute move-and-attack sequence
   */
  private async executeMoveAndAttack(attackerId: string, targetId: string, targetPosition: Position): Promise<void> {
    const attacker = battlemapStore.entities.summaries[attackerId];
    const target = battlemapStore.entities.summaries[targetId];
    
    if (!attacker || !target) return;
    
    // Find the nearest adjacent position to the target
    const attackPosition = this.findNearestAttackPosition(attackerId, targetPosition);
    if (!attackPosition) {
      console.warn(`[InteractionsManager] No valid attack position found for ${attacker.name} to reach ${target.name}`);
      return;
    }
    
    console.log(`[InteractionsManager] ${attacker.name} moving to attack position ${attackPosition} to reach ${target.name}`);
    
    try {
      // Start movement to attack position using the same logic as handleEntityMovement
      const success = await this.startEntityMovementToPosition(attackerId, attackPosition);
      if (!success) {
        console.warn(`[InteractionsManager] Failed to start movement for ${attacker.name}`);
        return;
      }
      
      // Set up a listener for when movement completes to execute the attack
      const checkMovementComplete = () => {
        const currentMovement = battlemapStore.entities.movementAnimations[attackerId];
        const spriteMapping = battlemapStore.entities.spriteMappings[attackerId];
        
        // Check if movement is complete (no active movement and back to idle)
        if (!currentMovement && spriteMapping?.movementState === 'idle') {
          console.log(`[InteractionsManager] Movement completed for ${attacker.name}, executing attack on ${target.name}`);
          
          // Execute the attack after movement completes
          this.executeDirectAttack(attackerId, targetId);
          
          // Stop checking
          clearInterval(movementCheckInterval);
        }
      };
      
      // Check every 100ms for movement completion
      const movementCheckInterval = setInterval(checkMovementComplete, 100);
      
      // Safety timeout - stop checking after 10 seconds
      setTimeout(() => {
        clearInterval(movementCheckInterval);
        console.warn(`[InteractionsManager] Movement timeout for ${attacker.name}, attack cancelled`);
      }, 10000);
      
    } catch (error) {
      console.error(`[InteractionsManager] Move-and-attack failed:`, error);
    }
  }
  
  /**
   * Find the nearest adjacent cell to a target that the entity can move to
   */
  private findNearestAttackPosition(entityId: string, targetPosition: Position): Position | null {
    const entity = battlemapStore.entities.summaries[entityId];
    if (!entity) return null;
    
    const [targetX, targetY] = targetPosition;
    
    // Check all 8 adjacent positions around the target
    const adjacentPositions: Position[] = [
      [targetX - 1, targetY - 1], // NW
      [targetX, targetY - 1],     // N
      [targetX + 1, targetY - 1], // NE
      [targetX + 1, targetY],     // E
      [targetX + 1, targetY + 1], // SE
      [targetX, targetY + 1],     // S
      [targetX - 1, targetY + 1], // SW
      [targetX - 1, targetY]      // W
    ];
    
    // Filter positions that the entity can move to (has path in senses)
    const validPositions = adjacentPositions.filter(pos => {
      const posKey = `${pos[0]},${pos[1]}`;
      return !!entity.senses.paths[posKey];
    });
    
    if (validPositions.length === 0) return null;
    
    // Find the position with the shortest path
    let bestPosition: Position | null = null;
    let shortestPathLength = Infinity;
    
    for (const position of validPositions) {
      const posKey = `${position[0]},${position[1]}`;
      const path = entity.senses.paths[posKey];
      if (path && path.length < shortestPathLength) {
        shortestPathLength = path.length;
        bestPosition = position;
      }
    }
    
    return bestPosition;
  }
  
  /**
   * Start entity movement to a specific position (used for move-and-attack)
   */
  private async startEntityMovementToPosition(entityId: string, targetPosition: Position): Promise<boolean> {
    const entity = battlemapStore.entities.summaries[entityId];
    if (!entity) {
      console.warn('[InteractionsManager] Entity not found for movement');
      return false;
    }
    
    const [gridX, gridY] = targetPosition;
    
    // Check if entity can move to this position (requires path in senses)
    const posKey = `${gridX},${gridY}`;
    const path = entity.senses.paths[posKey];
    
    if (!path) {
      console.log(`[InteractionsManager] No path available for ${entity.name} to position ${targetPosition}`);
      return false;
    }
    
    console.log(`[InteractionsManager] Moving entity ${entity.name} to position ${targetPosition}`);
    
    // NEW: Cache senses data for the selected entity BEFORE starting movement
    // This prevents visibility flickering when changing perspectives during movement
    this.cacheSensesDataForMovement();
    
    // IMMEDIATELY mark entity as out-of-sync to block further inputs
    const spriteMapping = battlemapStore.entities.spriteMappings[entityId];
    if (spriteMapping) {
      battlemapActions.updateEntityVisualPosition(entityId, spriteMapping.visualPosition || { x: entity.position[0], y: entity.position[1] });
    }
    
    // Get movement speed from sprite mapping (use animation duration as movement speed)
    const movementSpeed = spriteMapping?.animationDurationSeconds ? (1.0 / spriteMapping.animationDurationSeconds) : 1.0; // tiles per second
    
    // Create movement animation with full path including current position
    const fullPath = [entity.position, ...path];
    const movementAnimation: MovementAnimation = {
      entityId: entityId,
      path: fullPath,
      currentPathIndex: 0,
      startTime: Date.now(),
      movementSpeed,
      targetPosition,
      isServerApproved: undefined, // Will be set when server responds
    };
    
    // Start movement animation immediately
    battlemapActions.startEntityMovement(entityId, movementAnimation);
    
    // OPTIMIZED: Set initial direction immediately (EntityRenderer will handle direction changes during movement locally)
    if (fullPath.length > 1) {
      const initialDirection = this.computeDirection(fullPath[0], fullPath[1]);
      battlemapActions.setEntityDirectionFromMapping(entityId, initialDirection);
    }
    
    try {
      // Send movement to server (don't wait for response to start animation)
      const updatedEntity = await moveEntity(entityId, targetPosition);
      
      // Mark movement as server-approved
      battlemapActions.updateEntityMovementAnimation(entityId, { isServerApproved: true });
      
      // Refresh entities to get updated server state
      await battlemapActions.fetchEntitySummaries();
      
      console.log(`[InteractionsManager] Server approved movement for ${entity.name}`);
      return true;
    } catch (error) {
      console.error(`[InteractionsManager] Server rejected movement for ${entity.name}:`, error);
      
      // Mark movement as server-rejected
      battlemapActions.updateEntityMovementAnimation(entityId, { isServerApproved: false });
      
      // Movement animation will continue and then snap back on completion
      return false;
    }
  }
  
  /**
   * Check if an entity is ready for input (in sync and not animating)
   */
  private isEntityReadyForInput(entityId: string): boolean {
    const snap = battlemapStore;
    const spriteMapping = snap.entities.spriteMappings[entityId];
    const movementAnimation = snap.entities.movementAnimations[entityId];
    
    // Block input if entity is moving
    if (movementAnimation) {
      console.log(`[InteractionsManager] Entity ${entityId} is currently moving, blocking input`);
      return false;
    }
    
    // Block input if entity is not position-synced (e.g., during attack animations)
    if (spriteMapping && !spriteMapping.isPositionSynced) {
      console.log(`[InteractionsManager] Entity ${entityId} is not position-synced, blocking input`);
      return false;
    }
    
    return true;
  }
  
  /**
   * NEW: Cache senses data for the selected entity before movement starts
   * This prevents visibility flickering when changing perspectives during movement
   */
  private cacheSensesDataForMovement(): void {
    const snap = battlemapStore;
    const selectedEntity = snap.entities.selectedEntityId ? snap.entities.summaries[snap.entities.selectedEntityId] : null;
    
    if (!selectedEntity || !snap.controls.isVisibilityEnabled) {
      return;
    }
    
    // Get the EntityRenderer to cache the senses data
    const entityRenderer = this.engine?.getRenderer('EntityRenderer');
    if (entityRenderer && 'cacheSensesDataForEntity' in entityRenderer) {
      (entityRenderer as any).cacheSensesDataForEntity(selectedEntity.uuid, {
        visible: selectedEntity.senses.visible,
        seen: selectedEntity.senses.seen
      });
      console.log(`[InteractionsManager] Cached senses data for ${selectedEntity.name} before movement`);
    }
    
    // Also cache for TileRenderer
    const tileRenderer = this.engine?.getRenderer('TileRenderer');
    if (tileRenderer && 'cacheSensesDataForEntity' in tileRenderer) {
      (tileRenderer as any).cacheSensesDataForEntity(selectedEntity.uuid, {
        visible: selectedEntity.senses.visible,
        seen: selectedEntity.senses.seen
      });
    }
  }
  
  /**
   * Handle entity movement operations
   */
  private async handleEntityMovement(gridX: number, gridY: number): Promise<void> {
    const snap = battlemapStore;
    const selectedEntityId = snap.entities.selectedEntityId;
    
    if (!selectedEntityId) {
      console.log('[InteractionsManager] No entity selected for movement');
      return;
    }
    
    const entity = snap.entities.summaries[selectedEntityId];
    if (!entity) {
      console.warn('[InteractionsManager] Selected entity not found');
      return;
    }
    
    // Check if entity is ready for input
    if (!this.isEntityReadyForInput(selectedEntityId)) {
      console.log(`[InteractionsManager] Entity ${entity.name} is not ready for input, ignoring movement command`);
      return;
    }
    
    const targetPosition: Position = [gridX, gridY];
    
    // Check if entity can move to this position (requires path in senses)
    const posKey = `${gridX},${gridY}`;
    const path = entity.senses.paths[posKey];
    
    if (!path) {
      console.log(`[InteractionsManager] No path available for ${entity.name} to position ${targetPosition}`);
      return;
    }
    
    console.log(`[InteractionsManager] Moving entity ${entity.name} to position ${targetPosition}`);
    
    // NEW: Cache senses data for the selected entity BEFORE starting movement
    // This prevents visibility flickering when changing perspectives during movement
    this.cacheSensesDataForMovement();
    
    // IMMEDIATELY mark entity as out-of-sync to block further inputs
    const spriteMapping = snap.entities.spriteMappings[selectedEntityId];
    if (spriteMapping) {
      battlemapActions.updateEntityVisualPosition(selectedEntityId, spriteMapping.visualPosition || { x: entity.position[0], y: entity.position[1] });
    }
    
    // Get movement speed from sprite mapping (use animation duration as movement speed)
    const movementSpeed = spriteMapping?.animationDurationSeconds ? (1.0 / spriteMapping.animationDurationSeconds) : 1.0; // tiles per second
    
    // Create movement animation with full path including current position
    const fullPath = [entity.position, ...path];
    const movementAnimation: MovementAnimation = {
      entityId: selectedEntityId,
      path: fullPath,
      currentPathIndex: 0,
      startTime: Date.now(),
      movementSpeed,
      targetPosition,
      isServerApproved: undefined, // Will be set when server responds
    };
    
    // Start movement animation immediately
    battlemapActions.startEntityMovement(selectedEntityId, movementAnimation);
    
    // OPTIMIZED: Set initial direction immediately (EntityRenderer will handle direction changes during movement locally)
    if (fullPath.length > 1) {
      const initialDirection = this.computeDirection(fullPath[0], fullPath[1]);
      battlemapActions.setEntityDirectionFromMapping(selectedEntityId, initialDirection);
    }
    
    try {
      // Send movement to server (don't wait for response to start animation)
      const updatedEntity = await moveEntity(selectedEntityId, targetPosition);
      
      // Mark movement as server-approved
      battlemapActions.updateEntityMovementAnimation(selectedEntityId, { isServerApproved: true });
      
      // Refresh entities to get updated server state
      await battlemapActions.fetchEntitySummaries();
      
      console.log(`[InteractionsManager] Server approved movement for ${entity.name}`);
    } catch (error) {
      console.error(`[InteractionsManager] Server rejected movement for ${entity.name}:`, error);
      
      // Mark movement as server-rejected
      battlemapActions.updateEntityMovementAnimation(selectedEntityId, { isServerApproved: false });
      
      // Movement animation will continue and then snap back on completion
    }
  }
  
  /**
   * Compute direction from one position to another
   */
  private computeDirection(fromPos: Position, toPos: Position): Direction {
    return battlemapActions.computeDirection([fromPos[0], fromPos[1]], [toPos[0], toPos[1]]);
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
    
    // Remove context menu event listener
    if (this.contextMenuHandler && this.engine?.app?.canvas) {
      this.engine.app.canvas.removeEventListener('contextmenu', this.contextMenuHandler);
      this.contextMenuHandler = null;
    }
    
    this.engine = null;
    this.layer = null;
    
    console.log('[InteractionsManager] Destroyed');
  }
} 