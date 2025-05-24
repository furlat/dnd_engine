# Animation State Machine Architecture - Detailed Implementation

## Core Architecture Overview

### Three-Layer State System

1. **Server State** (Source of Truth)
   - Authoritative position from API
   - Discrete updates every ~200ms
   - Contains action results (damage, status effects)

2. **Animation State** (Visual Representation)
   - Interpolated positions for smooth movement
   - Frame-by-frame animation progression
   - Predictive states for immediate feedback

3. **Reconciliation Layer** (Synchronization)
   - Manages discrepancies between server and client
   - Smooth corrections without visual jarring
   - Event queue for proper sequencing

## Deterministic FSM Implementation

### State Definitions
```typescript
enum AnimationState {
  IDLE = 'idle',      // Default, looping
  WALK = 'walk',      // Looping, directional
  ATTACK = 'attack',  // One-shot, has hit frame
  HIT = 'hit',        // One-shot, interrupts others
  CAST = 'cast',      // One-shot, channeled
  DEATH = 'death'     // One-shot, terminal
}

interface StateTransition {
  from: AnimationState;
  to: AnimationState;
  priority: number;      // Higher priority can interrupt
  canInterrupt: boolean; // Can this transition interrupt current?
  queueable: boolean;    // Can queue if can't interrupt?
}
```

### State Machine with PixiJS AnimatedSprite
```typescript
class AnimationStateMachine {
  private sprite: AnimatedSprite;
  private currentState: AnimationState = AnimationState.IDLE;
  private stateStartTime: number = 0;
  private queuedStates: QueuedState[] = [];
  
  constructor(entityId: string) {
    // Initialize with empty sprite
    this.sprite = new AnimatedSprite([]);
    this.sprite.autoUpdate = false; // Manual control
    
    // Configure default callbacks
    this.setupCallbacks();
  }
  
  private setupCallbacks(): void {
    // Universal completion handler
    this.sprite.onComplete = () => {
      this.handleStateComplete();
    };
    
    // Frame change for mid-animation events
    this.sprite.onFrameChange = (frame: number) => {
      this.handleFrameChange(frame);
    };
    
    // Loop handler for continuous states
    this.sprite.onLoop = () => {
      this.handleLoop();
    };
  }
}
```

## Sprite Sheet Organization

### File Structure
```
/assets/entities/
  Knight_idle_1.json    // SW facing idle
  Knight_idle_2.json    // W facing idle
  ...
  Knight_idle_8.json    // S facing idle
  Knight_attack_1.json  // SW facing attack
  ...
```

### Direction Mapping
```typescript
enum Direction {
  SW = 0,  // File: _1
  W = 1,   // File: _2
  NW = 2,  // File: _3
  N = 3,   // File: _4
  NE = 4,  // File: _5
  E = 5,   // File: _6
  SE = 6,  // File: _7
  S = 7    // File: _8
}

// Convert direction to file suffix
const getFileSuffix = (direction: Direction): number => direction + 1;
```

## Event Processing Pipeline

### 1. Event Queue Architecture
```typescript
interface AnimationEvent {
  id: string;
  timestamp: number;        // When event should play
  entityId: string;
  type: EventType;
  priority: number;         // For same-timestamp ordering
  data: EventData;
  source: 'server' | 'prediction' | 'local';
}

class EventProcessor {
  private eventQueue: PriorityQueue<AnimationEvent>;
  private currentTime: number = 0;
  private processingDelay: Map<string, number> = new Map();
  
  // Called every frame by ticker
  update(deltaTime: number): void {
    this.currentTime += deltaTime * 1000; // Convert to ms
    
    while (!this.eventQueue.isEmpty()) {
      const event = this.eventQueue.peek();
      
      // Check if event is ready to process
      if (event.timestamp > this.currentTime) break;
      
      // Check if entity is still busy
      const entityDelay = this.processingDelay.get(event.entityId) || 0;
      if (entityDelay > this.currentTime) {
        // Requeue with delay
        event.timestamp = entityDelay + 16; // Next frame
        this.eventQueue.update(event);
        continue;
      }
      
      // Process the event
      this.processEvent(this.eventQueue.dequeue());
    }
  }
}
```

### 2. Event to Animation Mapping
```typescript
class EventToAnimationMapper {
  static mapEventToState(event: AnimationEvent): StateTransition {
    switch (event.type) {
      case 'attack':
        return {
          state: AnimationState.ATTACK,
          priority: 5,
          config: {
            speed: 1.5,
            onFrame: {
              5: () => this.spawnAttackEffect(event.data),
              8: () => this.applyDamage(event.data)
            }
          }
        };
        
      case 'move':
        return {
          state: AnimationState.WALK,
          priority: 2,
          config: {
            loop: true,
            path: event.data.path,
            speed: this.calculateWalkSpeed(event.data.distance)
          }
        };
    }
  }
}
```

## Position Interpolation System

### 1. Multi-Layer Position Tracking
```typescript
class PositionManager {
  // Server authoritative position
  private serverPosition: Point;
  
  // Current visual position (what's rendered)
  private visualPosition: Point;
  
  // Target position for interpolation
  private targetPosition: Point;
  
  // Path for complex movement
  private movementPath: Position[] = [];
  private pathIndex: number = 0;
  
  // Interpolation settings
  private interpolationSpeed: number = 5; // tiles per second
  private reconciliationSpeed: number = 10; // faster for corrections
  
  update(deltaTime: number): void {
    if (this.isReconciling()) {
      this.reconcile(deltaTime);
    } else if (this.isMovingAlongPath()) {
      this.followPath(deltaTime);
    } else {
      this.interpolateToTarget(deltaTime);
    }
  }
}
```

### 2. Path Following with Direction Updates
```typescript
class PathAnimator {
  private currentSegment: number = 0;
  private segmentProgress: number = 0;
  
  animateAlongPath(
    entity: AnimatedEntity,
    path: Position[],
    ticker: Ticker
  ): void {
    const updatePath = (delta: number) => {
      if (this.currentSegment >= path.length - 1) {
        ticker.remove(updatePath);
        entity.stateMachine.transition(AnimationState.IDLE);
        return;
      }
      
      const from = path[this.currentSegment];
      const to = path[this.currentSegment + 1];
      
      // Update direction if needed
      const newDirection = this.calculateDirection(from, to);
      if (newDirection !== entity.currentDirection) {
        this.updateSpriteDirection(entity, newDirection);
      }
      
      // Interpolate position
      this.segmentProgress += delta * this.speed;
      
      if (this.segmentProgress >= 1) {
        this.currentSegment++;
        this.segmentProgress = 0;
        
        // Trigger segment completion callback
        this.onSegmentComplete?.(from, to);
      }
      
      // Update visual position
      const t = this.easeInOut(this.segmentProgress);
      entity.container.x = lerp(from[0], to[0], t) * TILE_SIZE;
      entity.container.y = lerp(from[1], to[1], t) * TILE_SIZE;
    };
    
    ticker.add(updatePath);
  }
}
```

## Animation Callback System

### 1. Frame-Specific Callbacks
```typescript
interface FrameCallback {
  frame: number;
  callback: () => void;
  hasTriggered: boolean;
}

class AnimationCallbackManager {
  private frameCallbacks: Map<AnimationState, FrameCallback[]> = new Map();
  
  registerFrameCallback(
    state: AnimationState,
    frame: number,
    callback: () => void
  ): void {
    const callbacks = this.frameCallbacks.get(state) || [];
    callbacks.push({ frame, callback, hasTriggered: false });
    this.frameCallbacks.set(state, callbacks);
  }
  
  // Called by AnimatedSprite.onFrameChange
  handleFrameChange(state: AnimationState, frame: number): void {
    const callbacks = this.frameCallbacks.get(state) || [];
    
    callbacks.forEach(cb => {
      if (cb.frame === frame && !cb.hasTriggered) {
        cb.callback();
        cb.hasTriggered = true;
      }
    });
  }
  
  // Reset when animation starts
  resetCallbacks(state: AnimationState): void {
    const callbacks = this.frameCallbacks.get(state) || [];
    callbacks.forEach(cb => cb.hasTriggered = false);
  }
}
```

### 2. State Transition Callbacks
```typescript
interface StateCallbacks {
  onEnter?: (prevState: AnimationState) => void;
  onExit?: (nextState: AnimationState) => void;
  onComplete?: () => void;
  onInterrupt?: (byState: AnimationState) => void;
}

// Example: Attack animation with full callbacks
const attackCallbacks: StateCallbacks = {
  onEnter: (prev) => {
    sound.play('sword_swing');
    this.lockMovement();
  },
  onComplete: () => {
    this.unlockMovement();
    this.checkComboWindow();
  },
  onInterrupt: (by) => {
    if (by === AnimationState.HIT) {
      this.cancelAttack();
    }
  }
};
```

## State Priority & Interruption Rules

### Priority System
```typescript
const STATE_PRIORITIES = {
  [AnimationState.DEATH]: 10,    // Highest - cannot be interrupted
  [AnimationState.HIT]: 8,       // High - interrupts most
  [AnimationState.ATTACK]: 5,    // Medium - interrupts movement
  [AnimationState.CAST]: 5,      // Medium - same as attack
  [AnimationState.WALK]: 2,      // Low - easily interrupted
  [AnimationState.IDLE]: 0       // Lowest - always interruptible
};

class StateTransitionValidator {
  canTransition(
    from: AnimationState,
    to: AnimationState,
    force: boolean = false
  ): boolean {
    // Death is terminal
    if (from === AnimationState.DEATH) return false;
    
    // Forced transitions always work (except from death)
    if (force) return true;
    
    // Check priority
    const fromPriority = STATE_PRIORITIES[from];
    const toPriority = STATE_PRIORITIES[to];
    
    // Higher or equal priority can interrupt
    return toPriority >= fromPriority;
  }
}
```

## Predictive Animation System

### 1. Client Prediction
```typescript
class PredictiveAnimator {
  // Start animation immediately on user input
  predictMovement(targetPos: Position): void {
    // Calculate predicted path
    const predictedPath = this.pathfinder.findPath(
      this.entity.position,
      targetPos
    );
    
    // Start animation immediately
    this.animator.startWalkAnimation(predictedPath);
    
    // Mark as predicted
    this.entity.isPredicting = true;
    
    // Send to server
    this.sendMoveRequest(targetPos);
  }
  
  // Handle server response
  handleServerResponse(actualPath: Position[]): void {
    if (this.pathsMatch(this.predictedPath, actualPath)) {
      // Prediction was correct, just continue
      this.entity.isPredicting = false;
    } else {
      // Reconcile smoothly
      this.reconcilePath(actualPath);
    }
  }
  
  private reconcilePath(serverPath: Position[]): void {
    // Calculate blend factor based on how far we've moved
    const progress = this.animator.getPathProgress();
    
    // Blend current position with where we should be
    const targetPos = this.getPositionAlongPath(serverPath, progress);
    
    // Smooth correction over next few frames
    this.positionCorrector.smoothCorrect(
      this.entity.visualPosition,
      targetPos,
      300 // ms to correct
    );
  }
}
```

### 2. Rollback and Replay
```typescript
class AnimationHistory {
  private history: AnimationSnapshot[] = [];
  private maxHistory: number = 60; // 1 second at 60fps
  
  recordFrame(snapshot: AnimationSnapshot): void {
    this.history.push(snapshot);
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    }
  }
  
  rollbackTo(timestamp: number): void {
    const index = this.history.findIndex(s => s.timestamp >= timestamp);
    if (index !== -1) {
      // Restore state
      const snapshot = this.history[index];
      this.restoreSnapshot(snapshot);
      
      // Replay events from that point
      this.replayFrom(index);
    }
  }
}
```

## Performance Optimizations

### 1. Texture and Animation Pooling
```typescript
class AnimationPool {
  private pools: Map<string, AnimatedSprite[]> = new Map();
  private textureCache: Map<string, Texture[]> = new Map();
  
  getAnimatedSprite(state: AnimationState, direction: Direction): AnimatedSprite {
    const key = `${state}_${direction}`;
    let pool = this.pools.get(key);
    
    if (!pool || pool.length === 0) {
      // Create new sprite with cached textures
      const textures = this.getTextures(state, direction);
      return new AnimatedSprite(textures, false);
    }
    
    return pool.pop()!;
  }
  
  returnSprite(sprite: AnimatedSprite, state: AnimationState, direction: Direction): void {
    // Reset sprite state
    sprite.stop();
    sprite.currentFrame = 0;
    sprite.onComplete = null;
    sprite.onFrameChange = null;
    sprite.onLoop = null;
    
    // Return to pool
    const key = `${state}_${direction}`;
    const pool = this.pools.get(key) || [];
    pool.push(sprite);
    this.pools.set(key, pool);
  }
}
```

### 2. Update Culling
```typescript
class EntityUpdateCuller {
  private viewport: Rectangle;
  private margin: number = 2; // Tile margin around viewport
  
  shouldUpdate(entity: AnimatedEntity): boolean {
    // Always update if in combat or transitioning
    if (entity.isInCombat || entity.isTransitioning) return true;
    
    // Check viewport bounds with margin
    const bounds = this.getEntityBounds(entity);
    return this.viewport.intersects(bounds, this.margin * TILE_SIZE);
  }
  
  getUpdateFrequency(entity: AnimatedEntity): number {
    const distance = this.getDistanceFromViewportCenter(entity);
    
    if (distance < 5) return 1;        // Every frame
    if (distance < 10) return 2;       // Every 2 frames
    if (distance < 20) return 4;       // Every 4 frames
    return 8;                          // Every 8 frames
  }
}
```

## Memory Management

### 1. Texture Lifecycle
```typescript
class TextureLifecycleManager {
  private usageCount: Map<string, number> = new Map();
  private lastUsed: Map<string, number> = new Map();
  private maxUnusedTime: number = 30000; // 30 seconds
  
  incrementUsage(textureKey: string): void {
    const count = this.usageCount.get(textureKey) || 0;
    this.usageCount.set(textureKey, count + 1);
    this.lastUsed.set(textureKey, Date.now());
  }
  
  decrementUsage(textureKey: string): void {
    const count = this.usageCount.get(textureKey) || 0;
    if (count > 0) {
      this.usageCount.set(textureKey, count - 1);
    }
  }
  
  cleanup(): void {
    const now = Date.now();
    
    for (const [key, count] of this.usageCount) {
      if (count === 0) {
        const lastUsedTime = this.lastUsed.get(key) || 0;
        if (now - lastUsedTime > this.maxUnusedTime) {
          this.unloadTexture(key);
        }
      }
    }
  }
}
```

### 2. Event Cleanup
```typescript
class EventCleanupManager {
  private activeEvents: Map<string, Set<string>> = new Map();
  
  registerEvent(entityId: string, eventId: string): void {
    const events = this.activeEvents.get(entityId) || new Set();
    events.add(eventId);
    this.activeEvents.set(entityId, events);
  }
  
  cleanupEntity(entityId: string): void {
    const events = this.activeEvents.get(entityId);
    if (events) {
      events.forEach(eventId => {
        this.eventQueue.remove(eventId);
      });
      this.activeEvents.delete(entityId);
    }
  }
}
```

## Integration with PixiJS Features

### 1. Custom Ticker Usage
```typescript
// Separate tickers for different update rates
const tickers = {
  animation: new Ticker(),  // 60 FPS - Sprite updates
  movement: new Ticker(),   // 30 FPS - Position interpolation
  effects: new Ticker(),    // 60 FPS - Particle effects
  network: new Ticker()     // 5 FPS - Server reconciliation
};

// Configure update rates
tickers.movement.maxFPS = 30;
tickers.network.maxFPS = 5;
```

### 2. RenderGroup Optimization
```typescript
// Entities are NOT in a RenderGroup as they change frequently
// But we can use Container pooling for better performance
class EntityContainer extends Container {
  constructor() {
    super();
    
    // Pre-allocate common children
    this.shadowSprite = new Sprite();
    this.mainSprite = new AnimatedSprite([]);
    this.healthBar = new Graphics();
    this.effectsContainer = new Container();
    
    // Add in render order
    this.addChild(this.shadowSprite);
    this.addChild(this.mainSprite);
    this.addChild(this.healthBar);
    this.addChild(this.effectsContainer);
  }
}
```

## Debug Tools

### 1. State Visualizer
```typescript
class AnimationStateDebugger {
  private debugContainer: Container;
  private stateTexts: Map<string, Text> = new Map();
  
  visualizeState(entity: AnimatedEntity): void {
    const text = this.stateTexts.get(entity.id) || new Text('', {
      fontSize: 12,
      fill: 0x00FF00
    });
    
    text.text = `
      State: ${entity.currentState}
      Frame: ${entity.sprite.currentFrame}
      Queued: ${entity.queuedStates.length}
      Pos: ${entity.position.x.toFixed(1)}, ${entity.position.y.toFixed(1)}
    `;
    
    text.position.set(entity.container.x, entity.container.y - 50);
  }
}
```

### 2. Network Delay Simulator
```typescript
class NetworkDelaySimulator {
  private delay: number = 100; // ms
  private jitter: number = 20;  // ms variance
  
  simulateDelay<T>(callback: () => T): Promise<T> {
    const actualDelay = this.delay + (Math.random() - 0.5) * this.jitter * 2;
    
    return new Promise(resolve => {
      setTimeout(() => {
        resolve(callback());
      }, actualDelay);
    });
  }
}
```

## Complete Architecture Benefits

1. **Frame-Perfect Animations**: Ticker-based updates ensure smooth 60fps
2. **Network Resilience**: Predictive animations hide latency
3. **Rich Interactions**: Complex callback system for game events
4. **Performance**: Pooling, culling, and selective updates
5. **Debuggability**: Built-in tools for development
6. **Extensibility**: Easy to add new states and effects

The architecture fully leverages PixiJS v8's capabilities while maintaining clean separation between server state and visual representation.