# PixiJS Entity Animation System Design

## Design Philosophy & Background

### The Problem Space

In a real-time multiplayer battlemap system, we face several fundamental challenges:

1. **State Synchronization**: Server state updates arrive asynchronously and may be delayed
2. **Visual Continuity**: Animations must appear smooth despite network latency
3. **Event Ordering**: Actions must be displayed in correct sequence even when events arrive out of order
4. **Performance**: Hundreds of entities may need simultaneous animation
5. **Complexity**: Each entity has multiple animation states, directions, and transition rules

### The Traditional Approach (and its limitations)

Many web-based games use React components for rendering game entities, leveraging React's declarative model. However, this approach has significant drawbacks:

- **Render Cycle Coupling**: React's reconciliation process is optimized for UI, not 60fps game rendering
- **State Management Overhead**: Every frame potentially triggers React re-renders
- **Mixed Paradigms**: Game logic becomes entangled with React lifecycle methods
- **Performance Bottlenecks**: React's virtual DOM adds unnecessary overhead for sprite rendering

### The PixiJS-Native Approach

PixiJS v8's architecture is built around several core principles that align perfectly with game development needs:

1. **Ticker-Based Updates**: Deterministic frame-based updates instead of event-driven renders
2. **Scene Graph Optimization**: Efficient hierarchical rendering with automatic batching
3. **Extension-Based Architecture**: Modular systems that can be composed as needed
4. **GPU Acceleration**: Direct GPU communication for transforms and effects

### Our Design Objective

Create a **pure PixiJS entity animation system** that:

- Completely decouples game rendering from React (React only handles UI overlays)
- Implements a deterministic animation state machine for each entity
- Maintains smooth visual interpolation between server state updates
- Handles event queuing and replay for proper sequencing
- Optimizes rendering through proper use of PixiJS features

## Architecture Overview

### Core Components

1. **EntityRenderer**: A dedicated PixiJS renderer that manages all entity sprites
2. **AnimationStateMachine**: Per-entity state machines that control animation transitions
3. **EventProcessor**: Queues and processes animation events in correct temporal order
4. **PositionInterpolator**: Smoothly transitions entities between positions
5. **EffectsCoordinator**: Manages visual effects triggered by entity animations

### Data Flow

```
Server Event → Event Queue → Event Processor → Animation State Machine → Sprite Update
                    ↓                                      ↓
              Position Update                    Effect Triggers
                    ↓                                      ↓
            Position Interpolator                  Effects Layer
```

## PixiJS Implementation Guide

### Why AnimatedSprite Over Sprite

**AnimatedSprite** is the cornerstone of our entity system because it provides:

- **Built-in frame sequencing**: No manual frame management needed
- **Timing control**: Per-frame duration support for variable animation speeds
- **Event callbacks**: `onComplete`, `onFrameChange`, and `onLoop` for state transitions
- **Performance optimization**: Efficient texture swapping and update cycles

```javascript
// Key properties we'll leverage:
animatedSprite.animationSpeed // Global speed multiplier
animatedSprite.loop          // Whether to repeat
animatedSprite.onComplete    // State transition hook
animatedSprite.onFrameChange // Mid-animation effect triggers
```

### Ticker System: The Game Loop

Instead of React's render cycle, we use PixiJS's **Ticker** system:

**Why Ticker?**
- **Predictable timing**: Based on `requestAnimationFrame` with delta time
- **Multiple tickers**: Separate tickers for different systems (animation, physics, effects)
- **Performance control**: Built-in FPS limiting and frame skipping

```javascript
app.ticker        // Main render ticker
new Ticker()      // Custom ticker for animation state updates
ticker.deltaTime  // Scaled time for smooth animations regardless of framerate
```

### Container Hierarchy & RenderGroups

**Container organization** is crucial for performance:

```
Stage
├── TileLayer (RenderGroup - static)
├── EntityLayer
│   ├── EntityContainer (per entity)
│   │   ├── AnimatedSprite (character)
│   │   ├── HealthBar
│   │   └── StatusEffects
└── EffectsLayer (for temporary effects)
```

**Why use RenderGroups?**
- Static content (tiles) can be GPU-optimized
- Reduces CPU overhead for non-changing elements
- Allows batch rendering of similar objects

### Texture Management with Assets

**Assets.load()** provides several advantages over manual texture loading:

- **Automatic caching**: Textures are reused across sprites
- **Batch loading**: Multiple assets loaded in parallel
- **Resolution handling**: Automatic @2x texture selection
- **Memory management**: Built-in reference counting

For our sprite sheets:
```javascript
// Each direction/state combination is a separate sprite sheet
'Knight_idle_1.json'   // Southwest facing idle animation
'Knight_attack_3.json' // North facing attack animation
```

### Event Handling Without React

PixiJS provides a complete event system that we'll use for entity interactions:

**eventMode types:**
- `'static'`: For clickable entities
- `'dynamic'`: For entities that need hover states
- `'none'`: For pure visual elements (effects)

**Why not use React event handlers?**
- Direct hit testing on GPU-transformed sprites
- No DOM event bubbling overhead
- Built-in interaction culling

### Transform Interpolation

**Why manual position interpolation?**

Server updates arrive at ~200ms intervals, but we render at 60fps. Without interpolation:
- Movement appears "jumpy"
- Players perceive lag even when there isn't any
- Combat feels unresponsive

PixiJS provides the tools:
- `ticker.deltaTime`: For frame-independent movement
- `Point.lerp()` (with math-extras): For smooth interpolation
- Transform matrix caching: Efficient position updates

### State Machine Integration

**AnimatedSprite callbacks** map perfectly to state machine transitions:

1. **onComplete**: Transition to next state
   - Attack → Idle
   - Death → (terminal state)
   
2. **onFrameChange**: Trigger frame-specific events
   - Frame 5 of attack: Spawn damage effect
   - Frame 3 of cast: Show spell projectile
   
3. **loop property**: Control state behavior
   - true for Idle, Walk
   - false for Attack, Hit, Death

### Effect Coordination

Effects use a separate rendering layer because:

- **Temporary existence**: Effects have short lifespans
- **No entity coupling**: Effects can exist between entities
- **Pooling potential**: Reuse effect sprites for performance

### Performance Optimizations

1. **Sprite Pooling**: Reuse AnimatedSprite instances
2. **Texture Atlases**: Combine frames into single textures
3. **Culling**: Only update visible entities
4. **Batch Rendering**: Let PixiJS batch similar draw calls
5. **Manual Updates**: Disable autoUpdate on AnimatedSprites

### Memory Management

Key considerations:
- **Destroy sprites** when entities are removed
- **Unload textures** for unused animation states
- **Clear event queues** for destroyed entities
- **Remove ticker callbacks** to prevent memory leaks

## Integration Points

### With Valtio Store

The Valtio store remains the source of truth, but the PixiJS system:
- Subscribes to specific state changes
- Maintains its own interpolated positions
- Queues events for ordered playback

### With React UI

React components handle:
- Character sheets
- UI overlays
- Settings panels
- Non-game visualizations

PixiJS handles:
- All entity rendering
- Animation states
- Visual effects
- Movement interpolation

### With Server Events

Server events are transformed into animation events:
- Attack action → Attack animation + effect
- Movement update → Path interpolation
- Status change → Visual indicator update

## Summary

This architecture leverages PixiJS's strengths while avoiding common pitfalls of mixing game rendering with React's UI paradigm. By embracing PixiJS's ticker-based update cycle, built-in animation support, and efficient scene graph, we achieve smooth, deterministic animations that gracefully handle network latency and maintain visual continuity.