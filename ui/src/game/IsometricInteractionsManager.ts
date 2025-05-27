import { Graphics, FederatedPointerEvent, Container } from 'pixi.js';
import { battlemapStore, battlemapActions } from '../store';
import { createTile, deleteTile, moveEntity, getEntitiesAtPosition, executeAttack } from '../api/battlemap/battlemapApi';
import { BattlemapEngine, LayerName } from './BattlemapEngine';
import { TileSummary, Direction, MovementAnimation, toVisualPosition, AnimationState } from '../types/battlemap_types';
import { Position } from '../types/common';
import { IsometricGridRenderer } from './renderers/IsometricGridRenderer';
import { screenToGrid } from '../utils/isometricUtils';

// Define minimum width of entity panel
const ENTITY_PANEL_WIDTH = 250;

/**
 * IsometricInteractionsManager handles user input and interactions with the isometric battlemap
 * It manages mouse/touch events for tile editing and entity selection using isometric coordinate conversion
 */
export class IsometricInteractionsManager {
  // Engine reference
  private engine: BattlemapEngine | null = null;
  
  // Hit area for capturing events (transparent overlay)
  private hitArea: Graphics | null = null;
  
  // Layer reference for proper integration
  private layer: Container | null = null;
  
  // Reference to the isometric grid renderer for coordinate conversion
  private isometricGridRenderer: IsometricGridRenderer | null = null;
  
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
    
    // Get reference to the isometric grid renderer for coordinate conversion
    this.isometricGridRenderer = engine.getRenderer<IsometricGridRenderer>('isometric_grid') || null;
    
    if (!this.isometricGridRenderer) {
      console.error('[IsometricInteractionsManager] Could not find IsometricGridRenderer - coordinate conversion will not work');
    }
    
    // Create hit area for event handling
    this.createHitArea();
    
    console.log('[IsometricInteractionsManager] Initialized with UI layer and isometric coordinate conversion');
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
    
    console.log('[IsometricInteractionsManager] Hit area created and added to UI layer');
  }
  
  /**
   * Update hit area size to match canvas
   */
  private updateHitAreaSize(): void {
    if (!this.hitArea || !this.engine?.containerSize) return;
    
    const { width, height } = this.engine.containerSize;
    
    this.hitArea.clear();
    this.hitArea.rect(0, 0, width, height);
    this.hitArea.fill({ color: 0x000000, alpha: 0 }); // Transparent
  }
  
  /**
   * Convert pixel coordinates to grid coordinates using isometric transformation
   */
  private pixelToGrid(pixelX: number, pixelY: number): { 
    gridX: number; 
    gridY: number; 
    inBounds: boolean 
  } {
    if (!this.isometricGridRenderer) {
      console.warn('[IsometricInteractionsManager] No isometric grid renderer available for coordinate conversion');
      return { gridX: -1, gridY: -1, inBounds: false };
    }
    
    // Use the isometric grid renderer's coordinate conversion
    return this.isometricGridRenderer.screenToGrid(pixelX, pixelY);
  }
  
  /**
   * Handle pointer movement for hover effects
   */
  private handlePointerMove(event: FederatedPointerEvent): void {
    const snap = battlemapStore;
    
    // Skip handling during WASD movement for better performance
    if (snap.view.wasd_moving) return;
    
    // Convert to grid coordinates using isometric transformation
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
      console.log(`[IsometricInteractionsManager] Click throttled (${currentTime - this.lastClickTime}ms since last click)`);
      return;
    }
    this.lastClickTime = currentTime;
    
    // Convert to grid coordinates using isometric transformation
    const mouseX = event.global.x;
    const mouseY = event.global.y;
    
    const { gridX, gridY, inBounds } = this.pixelToGrid(mouseX, mouseY);
    
    if (!inBounds) return;
    
    console.log(`[IsometricInteractionsManager] Click at screen (${mouseX}, ${mouseY}) -> grid (${gridX}, ${gridY})`);
    
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
   * Handle tile editing
   */
  private async handleTileEdit(gridX: number, gridY: number): Promise<void> {
    const snap = battlemapStore;
    const selectedTileType = snap.controls.selectedTileType;
    
    console.log(`[IsometricInteractionsManager] Tile edit at (${gridX}, ${gridY}) with type: ${selectedTileType}`);
    
    try {
      if (selectedTileType === 'erase') {
        // Delete tile
        await deleteTile(gridX, gridY);
        console.log(`[IsometricInteractionsManager] Deleted tile at (${gridX}, ${gridY})`);
      } else {
        // Create/update tile
        const position: Position = [gridX, gridY];
        await createTile(position, selectedTileType);
        console.log(`[IsometricInteractionsManager] Created ${selectedTileType} tile at (${gridX}, ${gridY})`);
      }
    } catch (error) {
      console.error(`[IsometricInteractionsManager] Error editing tile at (${gridX}, ${gridY}):`, error);
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
      console.log(`[IsometricInteractionsManager] Entity ${entityId} is currently moving, blocking input`);
      return false;
    }
    
    // Block input if entity is not position-synced (e.g., during attack animations)
    if (spriteMapping && !spriteMapping.isPositionSynced) {
      console.log(`[IsometricInteractionsManager] Entity ${entityId} is not position-synced, blocking input`);
      return false;
    }
    
    return true;
  }
  
  /**
   * Cache senses data for the selected entity before movement starts
   * This prevents visibility flickering when changing perspectives during movement
   */
  private cacheSensesDataForMovement(): void {
    const snap = battlemapStore;
    const selectedEntity = snap.entities.selectedEntityId ? snap.entities.summaries[snap.entities.selectedEntityId] : null;
    
    if (!selectedEntity || !snap.controls.isVisibilityEnabled) {
      return;
    }
    
    // Get the IsometricEntityRenderer to cache the senses data
    const entityRenderer = this.engine?.getRenderer('isometric_entity');
    if (entityRenderer && 'cacheSensesDataForEntity' in entityRenderer) {
      (entityRenderer as any).cacheSensesDataForEntity(selectedEntity.uuid, {
        visible: selectedEntity.senses.visible,
        seen: selectedEntity.senses.seen
      });
      console.log(`[IsometricInteractionsManager] Cached senses data for ${selectedEntity.name} before movement`);
    }
    
    // Also cache for IsometricTileRenderer
    const tileRenderer = this.engine?.getRenderer('isometric_tile');
    if (tileRenderer && 'cacheSensesDataForEntity' in tileRenderer) {
      (tileRenderer as any).cacheSensesDataForEntity(selectedEntity.uuid, {
        visible: selectedEntity.senses.visible,
        seen: selectedEntity.senses.seen
      });
    }
  }

  /**
   * Handle entity movement
   */
  private async handleEntityMovement(gridX: number, gridY: number): Promise<void> {
    const snap = battlemapStore;
    const selectedEntityId = snap.entities.selectedEntityId;
    
    if (!selectedEntityId) {
      console.log('[IsometricInteractionsManager] No entity selected for movement');
      return;
    }

    const entity = snap.entities.summaries[selectedEntityId];
    if (!entity) {
      console.warn('[IsometricInteractionsManager] Selected entity not found');
      return;
    }

    // Check if entity is ready for input
    if (!this.isEntityReadyForInput(selectedEntityId)) {
      console.log(`[IsometricInteractionsManager] Entity ${entity.name} is not ready for input, ignoring movement command`);
      return;
    }

    const targetPosition: Position = [gridX, gridY];
    
    // Check if entity can move to this position (requires path in senses)
    const posKey = `${gridX},${gridY}`;
    const path = entity.senses.paths[posKey];
    
    if (!path) {
      console.log(`[IsometricInteractionsManager] No path available for ${entity.name} to position ${targetPosition}`);
      return;
    }

    console.log(`[IsometricInteractionsManager] Moving entity ${entity.name} to position ${targetPosition}`);
    
    // Cache senses data for the selected entity BEFORE starting movement
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
    
    // Set initial direction immediately (IsometricEntityRenderer will handle direction changes during movement locally)
    if (fullPath.length > 1) {
      const initialDirection = this.computeDirection(fullPath[0], fullPath[1]);
      battlemapActions.setEntityDirectionFromMapping(selectedEntityId, initialDirection);
    }

    try {
      // Send movement to server (don't wait for response to start animation)
      // Use the updated moveEntity API that returns MovementResponse with path senses
      const updatedEntity = await moveEntity(selectedEntityId, targetPosition, true); // Default to true for debugging
      
      // Mark movement as server-approved
      battlemapActions.updateEntityMovementAnimation(selectedEntityId, { isServerApproved: true });
      
      // Refresh entities to get updated server state
      await battlemapActions.fetchEntitySummaries();
      
      console.log(`[IsometricInteractionsManager] Server approved movement for ${entity.name}`);
    } catch (error) {
      console.error(`[IsometricInteractionsManager] Server rejected movement for ${entity.name}:`, error);
      
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
   * Handle right-click (attack or fallback to movement)
   */
  private async handleRightClick(gridX: number, gridY: number): Promise<void> {
    try {
      // First, check if there are entities at the target position
      const entitiesAtPosition = await getEntitiesAtPosition(gridX, gridY);
      
      if (entitiesAtPosition.length > 0) {
        // There are entities at this position, try to attack
        console.log(`[IsometricInteractionsManager] Right-click on position with entities, attempting attack`);
        await this.handleEntityAttack(gridX, gridY);
      } else {
        // No entities at this position, fallback to movement
        console.log(`[IsometricInteractionsManager] Right-click on empty position, fallback to movement`);
        await this.handleEntityMovement(gridX, gridY);
      }
    } catch (error) {
      console.error(`[IsometricInteractionsManager] Error handling right-click:`, error);
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
      console.log('[IsometricInteractionsManager] No entity selected for attack');
      return;
    }
    
    const attacker = snap.entities.summaries[selectedEntityId];
    if (!attacker) {
      console.warn('[IsometricInteractionsManager] Selected entity not found');
      return;
    }
    
    // Check if entity is ready for input
    if (!this.isEntityReadyForInput(selectedEntityId)) {
      console.log(`[IsometricInteractionsManager] Entity ${attacker.name} is not ready for input, ignoring attack command`);
      return;
    }
    
    try {
      // Get entities at the target position
      const entitiesAtPosition = await getEntitiesAtPosition(gridX, gridY);
      
      if (entitiesAtPosition.length === 0) {
        console.log(`[IsometricInteractionsManager] No entities at position ${gridX},${gridY} to attack`);
        return;
      }
      
      // Find the first entity that is not the attacker
      const target = entitiesAtPosition.find(entity => entity.uuid !== selectedEntityId);
      
      if (!target) {
        console.log(`[IsometricInteractionsManager] No valid target found at position ${gridX},${gridY}`);
        return;
      }
      
      console.log(`[IsometricInteractionsManager] ${attacker.name} attempting to attack ${target.name} at position ${gridX},${gridY}`);
      
      // Check if attacker is adjacent to target
      if (this.isAdjacentToTarget(attacker.position, target.position)) {
        // Direct attack
        console.log(`[IsometricInteractionsManager] ${attacker.name} is adjacent to ${target.name}, attacking directly`);
        await this.executeDirectAttack(selectedEntityId, target.uuid);
      } else {
        // Move and attack - start movement first
        console.log(`[IsometricInteractionsManager] ${attacker.name} needs to move to attack ${target.name}`);
        await this.executeMoveAndAttack(selectedEntityId, target.uuid, target.position);
      }
      
    } catch (error) {
      console.error(`[IsometricInteractionsManager] Error handling attack:`, error);
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
   * Execute a direct attack (entities are adjacent) using optimistic pattern
   */
  private async executeDirectAttack(attackerId: string, targetId: string): Promise<void> {
    const attacker = battlemapStore.entities.summaries[attackerId];
    const target = battlemapStore.entities.summaries[targetId];
    
    if (!attacker || !target) return;
    
    console.log(`[IsometricInteractionsManager] ${attacker.name} attacking ${target.name} directly (optimistic)`);
      
    // STEP 1: Set direction to face the target BEFORE starting attack
    const direction = this.computeDirection(attacker.position, target.position);
    
    // Clear any local direction state that might interfere with attack direction
    const entityRenderer = this.engine?.getRenderer('isometric_entity');
    if (entityRenderer && 'clearLocalDirectionState' in entityRenderer) {
      (entityRenderer as any).clearLocalDirectionState(attackerId);
    }
    
    battlemapActions.setEntityDirectionFromMapping(attackerId, direction);
    console.log(`[IsometricInteractionsManager] Set attack direction for ${attacker.name}: ${direction}`);
    
    // STEP 2: Mark entity as out-of-sync to block further inputs
    const spriteMapping = battlemapStore.entities.spriteMappings[attackerId];
    if (spriteMapping) {
      battlemapActions.updateEntityVisualPosition(attackerId, spriteMapping.visualPosition || { x: attacker.position[0], y: attacker.position[1] });
    }
    
    // STEP 3: Start optimistic attack animation immediately
    battlemapActions.startEntityAttack(attackerId, targetId);
    console.log(`[IsometricInteractionsManager] Started optimistic attack animation for ${attacker.name}`);
      
    try {
      // STEP 4: Execute the attack API call
      const attackResponse = await executeAttack(attackerId, targetId, 'MAIN_HAND');
      
      console.log(`[IsometricInteractionsManager] Attack response received:`, {
        event: attackResponse.event,
        metadata: attackResponse.metadata
      });
      
      // STEP 5: Update attack metadata from server response
      battlemapActions.updateEntityAttackMetadata(attackerId, attackResponse.metadata);
      
      // STEP 6: Refresh entity summaries to get updated health/status
      await battlemapActions.fetchEntitySummaries();
      
      console.log(`[IsometricInteractionsManager] Attack successful - outcome: ${attackResponse.metadata.attack_outcome}, damage: ${attackResponse.metadata.total_damage}`);
      
    } catch (error) {
      console.error(`[IsometricInteractionsManager] Attack failed:`, error);
      
      // ROLLBACK: Complete attack immediately on failure (returns to idle)
      battlemapActions.completeEntityAttack(attackerId);
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
      console.warn(`[IsometricInteractionsManager] No valid attack position found for ${attacker.name} to reach ${target.name}`);
      return;
    }
    
    console.log(`[IsometricInteractionsManager] ${attacker.name} moving to attack position ${attackPosition} to reach ${target.name}`);
    
    try {
      // Start movement to attack position using the same logic as handleEntityMovement
      const success = await this.startEntityMovementToPosition(attackerId, attackPosition);
      if (!success) {
        console.warn(`[IsometricInteractionsManager] Failed to start movement for ${attacker.name}`);
        return;
      }
      
      // Set up a listener for when movement completes to execute the attack
      const checkMovementComplete = () => {
        const currentMovement = battlemapStore.entities.movementAnimations[attackerId];
        const spriteMapping = battlemapStore.entities.spriteMappings[attackerId];
        
        // Check if movement is complete (no active movement and back to idle)
        if (!currentMovement && spriteMapping?.movementState === 'idle') {
          console.log(`[IsometricInteractionsManager] Movement completed for ${attacker.name}, executing attack on ${target.name}`);
          
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
        console.warn(`[IsometricInteractionsManager] Movement timeout for ${attacker.name} move-and-attack sequence`);
      }, 10000);
      
    } catch (error) {
      console.error(`[IsometricInteractionsManager] Error in move-and-attack sequence:`, error);
    }
  }

  /**
   * Find the nearest attack position adjacent to a target
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
      console.warn('[IsometricInteractionsManager] Entity not found for movement');
      return false;
    }
    
    const [gridX, gridY] = targetPosition;
    
    // Check if entity can move to this position (requires path in senses)
    const posKey = `${gridX},${gridY}`;
    const path = entity.senses.paths[posKey];
    
    if (!path) {
      console.log(`[IsometricInteractionsManager] No path available for ${entity.name} to position ${targetPosition}`);
      return false;
    }
    
    console.log(`[IsometricInteractionsManager] Moving entity ${entity.name} to position ${targetPosition}`);
    
    // Cache senses data for the selected entity BEFORE starting movement
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
    
    // Set initial direction immediately (IsometricEntityRenderer will handle direction changes during movement locally)
    if (fullPath.length > 1) {
      const initialDirection = this.computeDirection(fullPath[0], fullPath[1]);
      battlemapActions.setEntityDirectionFromMapping(entityId, initialDirection);
    }
    
    try {
      // Send movement to server (don't wait for response to start animation)
      // Use the updated moveEntity API that returns MovementResponse with path senses
      const updatedEntity = await moveEntity(entityId, targetPosition, true); // Default to true for debugging
      
      // Mark movement as server-approved
      battlemapActions.updateEntityMovementAnimation(entityId, { isServerApproved: true });
      
      // Refresh entities to get updated server state
      await battlemapActions.fetchEntitySummaries();
      
      console.log(`[IsometricInteractionsManager] Server approved movement for ${entity.name}`);
      return true;
    } catch (error) {
      console.error(`[IsometricInteractionsManager] Server rejected movement for ${entity.name}:`, error);
      
      // Mark movement as server-rejected
      battlemapActions.updateEntityMovementAnimation(entityId, { isServerApproved: false });
      
      // Movement animation will continue and then snap back on completion
      return false;
    }
  }
  
  /**
   * Resize handler
   */
  resize(width: number, height: number): void {
    this.updateHitAreaSize();
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    console.log('[IsometricInteractionsManager] Destroying interactions manager');
    
    // Remove context menu handler
    if (this.contextMenuHandler && this.engine?.app?.canvas) {
      this.engine.app.canvas.removeEventListener('contextmenu', this.contextMenuHandler);
      this.contextMenuHandler = null;
    }
    
    // Clean up hit area
    if (this.hitArea) {
      this.hitArea.removeAllListeners();
      if (this.layer && this.hitArea.parent === this.layer) {
        this.layer.removeChild(this.hitArea);
      }
      this.hitArea.destroy();
      this.hitArea = null;
    }
    
    // Clear references
    this.engine = null;
    this.layer = null;
    this.isometricGridRenderer = null;
  }
} 