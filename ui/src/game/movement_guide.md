1. Missing Position Decoupling
Your entities jump directly to server positions. We need:

Visual position (for smooth animation)
Server position (authoritative)
Interpolation layer between them

2. No Path-Based Movement
The moveEntityTo hook sets position directly without:

Walking animation trigger
Path following
Direction updates during movement

Surgical Movement Implementation Plan
Phase 1: Add Position Tracking to EntityRenderer
typescript// In EntityRenderer, add position management
private visualPositions: Map<string, { x: number; y: number }> = new Map();
private targetPositions: Map<string, { x: number; y: number }> = new Map();
private movementPaths: Map<string, { path: Position[]; currentIndex: number }> = new Map();

// Add this to the needsTickerUpdate
protected needsTickerUpdate: boolean = true;

// Implement update method for smooth movement
update(ticker: Ticker): void {
  this.updateEntityMovement(ticker.deltaTime);
}
Phase 2: Movement Interpolation System
typescriptprivate updateEntityMovement(deltaTime: number): void {
  this.movementPaths.forEach((movement, entityId) => {
    const entity = battlemapStore.entities.summaries[entityId];
    if (!entity) return;
    
    const visualPos = this.visualPositions.get(entityId);
    if (!visualPos) return;
    
    // Get current and next path positions
    const currentTarget = movement.path[movement.currentIndex];
    const nextTarget = movement.path[movement.currentIndex + 1];
    
    if (!nextTarget) {
      // Reached end of path
      this.completeMovement(entityId);
      return;
    }
    
    // Calculate direction and update sprite
    this.updateMovementDirection(entityId, currentTarget, nextTarget);
    
    // Interpolate position
    const speed = 5; // tiles per second
    const step = speed * deltaTime;
    
    // Move towards next target
    const dx = nextTarget[0] - visualPos.x;
    const dy = nextTarget[1] - visualPos.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    
    if (distance <= step) {
      // Reached waypoint
      visualPos.x = nextTarget[0];
      visualPos.y = nextTarget[1];
      movement.currentIndex++;
    } else {
      // Move towards target
      const ratio = step / distance;
      visualPos.x += dx * ratio;
      visualPos.y += dy * ratio;
    }
    
    // Update sprite position
    this.updateEntityVisualPosition(entityId, visualPos);
  });
}
Phase 3: Hook into Movement System
typescript// Add to EntityRenderer
public startEntityMovement(entityId: string, targetPosition: Position): void {
  const entity = battlemapStore.entities.summaries[entityId];
  if (!entity) return;
  
  // Get path from entity senses
  const pathKey = `${targetPosition[0]},${targetPosition[1]}`;
  const path = entity.senses.paths[pathKey];
  
  if (!path || path.length === 0) {
    // No valid path, just teleport
    this.visualPositions.set(entityId, { 
      x: targetPosition[0], 
      y: targetPosition[1] 
    });
    return;
  }
  
  // Start movement along path
  this.movementPaths.set(entityId, {
    path: [entity.position, ...path], // Include current position
    currentIndex: 0
  });
  
  // Change to walk animation
  const mapping = battlemapStore.entities.spriteMappings[entityId];
  if (mapping) {
    battlemapActions.setEntityAnimation(entityId, AnimationState.WALK);
  }
}
Phase 4: Modified Movement Hook
typescript// In InteractionsManager, handle entity click for movement
private async handleEntityMovement(gridX: number, gridY: number): Promise<void> {
  const selectedEntityId = battlemapStore.entities.selectedEntityId;
  if (!selectedEntityId) return;
  
  // Check if can move to position
  if (!this.canEntityMoveTo(selectedEntityId, gridX, gridY)) return;
  
  // Get the entity renderer
  const entityRenderer = this.engine?.getRenderer<EntityRenderer>('entities');
  if (!entityRenderer) return;
  
  // Start visual movement immediately
  entityRenderer.startEntityMovement(selectedEntityId, [gridX, gridY]);
  
  // Send to server
  await moveEntity(selectedEntityId, [gridX, gridY]);
}
Phase 5: Direction Updates During Movement
typescriptprivate updateMovementDirection(
  entityId: string, 
  from: Position, 
  to: Position
): void {
  const direction = this.computeDirection(from, to);
  const currentDirection = battlemapStore.entities.directions[entityId];
  
  if (direction !== currentDirection) {
    // Update direction in store
    battlemapActions.setEntityDirection(entityId, direction);
    
    // Update sprite textures for new direction
    const sprite = this.animatedSprites.get(entityId);
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    
    if (sprite && mapping) {
      const spritesheet = this.loadedSpritesheets.get(
        `${mapping.spriteFolder}_${mapping.currentAnimation}`
      );
      
      if (spritesheet) {
        const directionTextures = this.getDirectionTextures(spritesheet, direction);
        sprite.textures = directionTextures;
        // Don't restart animation, just update textures
      }
    }
  }
}
Key Points:

Decoupled Positions: Visual position (for rendering) vs server position (authoritative)
Path Following: Uses existing entity.senses.paths data
Smooth Interpolation: Ticker-based movement between waypoints
Direction Updates: Changes sprite direction as entity moves along path
Animation Coordination: Walk animation during movement, idle when stopped

This approach:

Keeps your existing architecture intact
Adds minimal complexity
Uses the path data you already have
Provides smooth, interpolated movement
Updates directions naturally during movement

Would you like me to create a complete code artifact for any of these components?