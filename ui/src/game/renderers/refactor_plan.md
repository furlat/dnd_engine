# PixiJS Game Engine Refactor Plan for Entity Animation

## Current Architecture Analysis

### What's Working Well
1. **Renderer Pattern**: Clean separation between different visual layers
2. **Valtio Integration**: Reactive updates from store changes
3. **Resource Management**: Proper cleanup in destroy methods
4. **Offset Calculations**: Consistent handling of entity panel space

### What Needs Enhancement
1. **Update Loop**: Currently using manual `renderAll()` instead of ticker-based updates
2. **Animation Support**: No infrastructure for AnimatedSprite or state machines
3. **Event Processing**: No system for queuing and processing animation events
4. **Position Interpolation**: Direct position updates without smoothing
5. **Layer Management**: Need explicit layer ordering for entities

## Refactor Plan

### Phase 1: Core Engine Enhancements

#### 1.1 BattlemapEngine Updates
```typescript
class BattlemapEngine {
  // ADD: Ticker management
  private animationTicker: Ticker | null = null;
  private renderTicker: Ticker | null = null;
  
  // ADD: Layer containers for proper ordering
  private layers: {
    tiles: Container;
    grid: Container;
    entities: Container;
    effects: Container;
    ui: Container;
  } | null = null;
  
  // ADD: Render groups for optimization
  private tileRenderGroup: Container | null = null;
  
  // MODIFY: Initialize to set up layers and tickers
  async initialize(element: HTMLElement): Promise<boolean> {
    // ... existing initialization ...
    
    // Set up layer hierarchy
    this.setupLayers();
    
    // Initialize tickers
    this.setupTickers();
    
    // Enable render groups for static content
    this.enableRenderGroups();
  }
  
  // ADD: Layer management
  private setupLayers(): void {
    const stage = this.app.stage;
    
    this.layers = {
      tiles: new Container(),
      grid: new Container(),
      entities: new Container(),
      effects: new Container(),
      ui: new Container()
    };
    
    // Add layers in rendering order
    stage.addChild(this.layers.tiles);
    stage.addChild(this.layers.grid);
    stage.addChild(this.layers.entities);
    stage.addChild(this.layers.effects);
    stage.addChild(this.layers.ui);
  }
  
  // ADD: Get specific layer for renderers
  getLayer(layerName: keyof typeof this.layers): Container | null {
    return this.layers?.[layerName] || null;
  }
}
```

#### 1.2 Ticker System Integration
```typescript
// New TickerManager to coordinate updates
class TickerManager {
  private tickers: Map<string, Ticker> = new Map();
  
  createTicker(name: string, autoStart = true): Ticker {
    const ticker = new Ticker();
    this.tickers.set(name, ticker);
    if (autoStart) ticker.start();
    return ticker;
  }
  
  getTicker(name: string): Ticker | undefined {
    return this.tickers.get(name);
  }
  
  destroy(): void {
    this.tickers.forEach(ticker => ticker.destroy());
    this.tickers.clear();
  }
}
```

### Phase 2: Renderer Base Class Enhancement

#### 2.1 AbstractRenderer Updates
```typescript
abstract class AbstractRenderer implements BaseRenderer {
  container: Container = new Container();
  protected engine: BattlemapEngine | null = null;
  protected layer: Container | null = null;
  
  // ADD: Layer name for this renderer
  abstract get layerName(): keyof typeof BattlemapEngine.prototype.layers;
  
  // ADD: Whether this renderer needs ticker updates
  protected needsTickerUpdate: boolean = false;
  
  // MODIFY: Initialize to use proper layer
  initialize(engine: BattlemapEngine): void {
    this.engine = engine;
    
    // Get the appropriate layer
    this.layer = engine.getLayer(this.layerName);
    
    // Add container to layer instead of stage
    if (this.layer) {
      this.layer.addChild(this.container);
    }
    
    // Register for ticker updates if needed
    if (this.needsTickerUpdate) {
      this.registerTickerUpdate();
    }
  }
  
  // ADD: Optional ticker update method
  update?(ticker: Ticker): void;
  
  // ADD: Register for ticker updates
  private registerTickerUpdate(): void {
    const ticker = this.engine?.tickerManager?.getTicker('render');
    if (ticker && this.update) {
      ticker.add(this.update, this);
    }
  }
}
```

### Phase 3: Entity Renderer Implementation

#### 3.1 Core EntityRenderer Structure
```typescript
class EntityRenderer extends AbstractRenderer {
  get layerName() { return 'entities' as const; }
  protected needsTickerUpdate = true;
  
  // Entity management
  private entityContainers: Map<string, Container> = new Map();
  private animatedSprites: Map<string, AnimatedSprite> = new Map();
  private animationStates: Map<string, AnimationStateMachine> = new Map();
  
  // Position interpolation
  private targetPositions: Map<string, Point> = new Map();
  private currentPositions: Map<string, Point> = new Map();
  
  // Event processing
  private eventQueue: AnimationEvent[] = [];
  private eventProcessor: EventProcessor;
  
  // Texture management
  private textureLoader: EntityTextureLoader;
  
  initialize(engine: BattlemapEngine): void {
    super.initialize(engine);
    
    // Initialize subsystems
    this.eventProcessor = new EventProcessor(this);
    this.textureLoader = new EntityTextureLoader();
    
    // Preload common animations
    this.preloadAnimations();
    
    // Subscribe to store changes
    this.setupSubscriptions();
  }
  
  // Ticker update - called every frame
  update(ticker: Ticker): void {
    // Process queued events
    this.eventProcessor.processEvents(ticker.deltaTime);
    
    // Update entity positions and animations
    this.updateEntities(ticker.deltaTime);
    
    // Clean up removed entities
    this.cleanupRemovedEntities();
  }
  
  // Main render method (called on store changes)
  render(): void {
    const entities = Object.values(battlemapStore.entities.summaries);
    
    entities.forEach(entity => {
      // Ensure entity has a container
      if (!this.entityContainers.has(entity.uuid)) {
        this.createEntityContainer(entity);
      }
      
      // Update entity state (position, direction, etc.)
      this.updateEntityState(entity);
    });
  }
}
```

#### 3.2 Animation State Machine
```typescript
class AnimationStateMachine {
  private currentState: AnimationState = AnimationState.IDLE;
  private sprite: AnimatedSprite;
  private entityId: string;
  private transitions: Map<string, TransitionConfig> = new Map();
  
  constructor(entityId: string, sprite: AnimatedSprite) {
    this.entityId = entityId;
    this.sprite = sprite;
    this.setupDefaultTransitions();
  }
  
  transition(newState: AnimationState, options?: TransitionOptions): void {
    // Check if transition is allowed
    if (!this.canTransition(this.currentState, newState)) {
      if (options?.queue) {
        this.queueTransition(newState, options);
      }
      return;
    }
    
    // Stop current animation
    this.sprite.stop();
    
    // Load new animation textures
    const direction = this.getCurrentDirection();
    const textures = this.loadStateTextures(newState, direction);
    
    // Configure sprite for new state
    this.sprite.textures = textures;
    this.configureSprite(newState);
    
    // Set up callbacks
    this.setupStateCallbacks(newState, options);
    
    // Start playing
    this.sprite.play();
    this.currentState = newState;
  }
  
  private setupStateCallbacks(state: AnimationState, options?: TransitionOptions): void {
    // Clear previous callbacks
    this.sprite.onComplete = null;
    this.sprite.onFrameChange = null;
    
    switch (state) {
      case AnimationState.ATTACK:
        this.sprite.onFrameChange = (frame) => {
          if (frame === 5) { // Mid-attack frame
            options?.onMidAnimation?.();
          }
        };
        this.sprite.onComplete = () => {
          this.transition(AnimationState.IDLE);
          options?.onComplete?.();
        };
        break;
        
      case AnimationState.WALK:
        this.sprite.onLoop = () => {
          // Check if we should continue walking
          if (!this.shouldContinueWalking()) {
            this.transition(AnimationState.IDLE);
          }
        };
        break;
        
      case AnimationState.DEATH:
        this.sprite.onComplete = () => {
          // Death is terminal - no automatic transition
          options?.onComplete?.();
        };
        break;
    }
  }
}
```

#### 3.3 Position Interpolation System
```typescript
class PositionInterpolator {
  private static INTERPOLATION_SPEED = 5; // Units per second
  
  static interpolate(
    current: Point,
    target: Point,
    deltaTime: number
  ): Point {
    const dx = target.x - current.x;
    const dy = target.y - current.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    
    if (distance < 0.1) {
      // Close enough, snap to target
      return target.clone();
    }
    
    // Calculate movement for this frame
    const moveDistance = this.INTERPOLATION_SPEED * deltaTime;
    const t = Math.min(moveDistance / distance, 1);
    
    return new Point(
      current.x + dx * t,
      current.y + dy * t
    );
  }
  
  static interpolateAlongPath(
    current: Point,
    path: Position[],
    speed: number,
    deltaTime: number
  ): { position: Point; segmentIndex: number; complete: boolean } {
    // Implementation for smooth path following
    // Returns current position, which path segment we're on, and if complete
  }
}
```

### Phase 4: Event Processing System

#### 4.1 Event Queue and Processor
```typescript
interface AnimationEvent {
  id: string;
  timestamp: number;
  entityId: string;
  type: 'move' | 'attack' | 'hit' | 'status' | 'death';
  data: any;
  priority: number;
}

class EventProcessor {
  private eventQueue: AnimationEvent[] = [];
  private processing: Set<string> = new Set();
  private eventHandlers: Map<string, EventHandler> = new Map();
  
  constructor(private entityRenderer: EntityRenderer) {
    this.registerDefaultHandlers();
  }
  
  queueEvent(event: AnimationEvent): void {
    // Insert event in priority order
    const index = this.eventQueue.findIndex(e => 
      e.timestamp > event.timestamp || 
      (e.timestamp === event.timestamp && e.priority < event.priority)
    );
    
    if (index === -1) {
      this.eventQueue.push(event);
    } else {
      this.eventQueue.splice(index, 0, event);
    }
  }
  
  processEvents(currentTime: number): void {
    // Process all events that should have occurred by now
    while (this.eventQueue.length > 0) {
      const event = this.eventQueue[0];
      
      if (event.timestamp > currentTime) {
        break; // Wait for future events
      }
      
      // Remove from queue
      this.eventQueue.shift();
      
      // Skip if entity is already processing an event
      if (this.processing.has(event.entityId)) {
        // Re-queue with slight delay
        event.timestamp = currentTime + 100;
        this.queueEvent(event);
        continue;
      }
      
      // Process the event
      this.processEvent(event);
    }
  }
  
  private processEvent(event: AnimationEvent): void {
    const handler = this.eventHandlers.get(event.type);
    if (handler) {
      this.processing.add(event.entityId);
      
      handler.handle(event, () => {
        this.processing.delete(event.entityId);
      });
    }
  }
}
```

### Phase 5: Integration Updates

#### 5.1 GameManager Updates
```typescript
class GameManager {
  // ADD: Entity renderer
  private entityRenderer: EntityRenderer = new EntityRenderer();
  
  // ADD: Ticker manager
  private tickerManager: TickerManager = new TickerManager();
  
  // ADD: Event coordinator
  private eventCoordinator: EventCoordinator = new EventCoordinator();
  
  private initializeComponents(): void {
    // ... existing tile and grid initialization ...
    
    // Initialize entity renderer
    this.entityRenderer.initialize(battlemapEngine);
    battlemapEngine.registerRenderer('entities', this.entityRenderer);
    
    // Set up event flow from API to renderer
    this.eventCoordinator.initialize(this.entityRenderer);
    
    // Start animation ticker
    const animationTicker = this.tickerManager.createTicker('animation');
    animationTicker.add(() => {
      // Update all animation states
      this.entityRenderer.update(animationTicker);
    });
  }
}
```

#### 5.2 Store Integration
```typescript
// Add to battlemapStore
export interface EntityState {
  // ... existing properties ...
  
  // ADD: Animation states
  animationStates: Record<string, AnimationState>;
  
  // ADD: Movement paths
  movementPaths: Record<string, Position[]>;
  
  // ADD: Pending actions
  pendingActions: Record<string, ActionType[]>;
}

// Add to battlemapActions
const battlemapActions = {
  // ... existing actions ...
  
  // ADD: Queue entity action
  queueEntityAction: (entityId: string, action: ActionType) => {
    if (!battlemapStore.entities.pendingActions[entityId]) {
      battlemapStore.entities.pendingActions[entityId] = [];
    }
    battlemapStore.entities.pendingActions[entityId].push(action);
  },
  
  // ADD: Set entity animation state
  setEntityAnimationState: (entityId: string, state: AnimationState) => {
    battlemapStore.entities.animationStates[entityId] = state;
  }
};
```

### Phase 6: Optimization Strategies

#### 6.1 Texture Preloading
```typescript
class EntityTextureLoader {
  private loadedSheets: Map<string, Spritesheet> = new Map();
  
  async preloadEntityType(
    entityType: string,
    states: AnimationState[],
    directions: Direction[]
  ): Promise<void> {
    const loadPromises: Promise<void>[] = [];
    
    for (const state of states) {
      for (const direction of directions) {
        const key = `${entityType}_${state}_${direction}`;
        const promise = this.loadSpritesheet(key);
        loadPromises.push(promise);
      }
    }
    
    await Promise.all(loadPromises);
  }
  
  private async loadSpritesheet(key: string): Promise<void> {
    if (this.loadedSheets.has(key)) return;
    
    const sheet = await Assets.load(`/assets/entities/${key}.json`);
    this.loadedSheets.set(key, sheet);
  }
}
```

#### 6.2 Object Pooling
```typescript
class EntityObjectPool {
  private pools: Map<string, any[]> = new Map();
  
  getAnimatedSprite(): AnimatedSprite {
    const pool = this.pools.get('AnimatedSprite') || [];
    
    if (pool.length > 0) {
      return pool.pop();
    }
    
    return new AnimatedSprite([]);
  }
  
  returnAnimatedSprite(sprite: AnimatedSprite): void {
    sprite.stop();
    sprite.textures = [];
    sprite.onComplete = null;
    sprite.onFrameChange = null;
    sprite.onLoop = null;
    
    const pool = this.pools.get('AnimatedSprite') || [];
    pool.push(sprite);
    this.pools.set('AnimatedSprite', pool);
  }
}
```

## Implementation Order

1. **Core Engine Updates** 
   - Update BattlemapEngine with layers and tickers
   - Implement TickerManager
   - Update AbstractRenderer base class

2. **Entity Renderer Foundation** 
   - Create EntityRenderer class
   - Implement basic entity container management
   - Set up store subscriptions

3. **Animation System** 
   - Implement AnimationStateMachine
   - Create texture loading system
   - Add AnimatedSprite management

4. **Position & Movement** 
   - Implement PositionInterpolator
   - Add path following logic
   - Integrate with movement animations

5. **Event Processing** 
   - Create EventProcessor
   - Implement event handlers
   - Connect to API responses

6. **Integration & Testing** 
   - Update GameManager
   - Test with real entity data
   - Performance optimization

## Key Benefits

1. **Decoupled Architecture**: Complete separation from React rendering
2. **Smooth Animations**: Ticker-based updates with interpolation
3. **Event Coordination**: Proper sequencing of actions and effects
4. **Performance**: Optimized with render groups, pooling, and culling
5. **Extensibility**: Easy to add new animation states and effects

## Next Steps After Implementation

1. **Effects Layer**: Add projectiles, spell effects, damage numbers
2. **Advanced States**: Implement combo attacks, channeling, interrupts
3. **Performance Monitoring**: Add FPS counter and profiling
4. **Entity Variations**: Support different sprite sheets per entity type
5. **Animation Editor**: Tool for adjusting timing and transitions