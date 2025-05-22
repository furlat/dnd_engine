Animation State Machine Architecture
Core Concepts

State Decoupling

Server Position: The authoritative position from API
Animation Position: Interpolated/predicted position for smooth visuals
Reconciliation: Gracefully sync when server updates arrive


Deterministic FSM for Animations
idle → attack → idle
idle → walk → idle  
idle → hit → idle
idle → death (terminal)

Indexed Sprite System
Knight_{state}_{direction}
- state: idle, walk, attack, hit, death
- direction: 1-8 (SW clockwise to S)


Key Design Considerations
1. Event-Driven Architecture

API Events → Update Valtio state → Trigger animation transitions
Animation Events → Callbacks → Trigger effects or next animations
Effect Events → Visual feedback independent of entity state

2. Temporal Coordination
Server says "move A to B" at T0
↓
Client starts walk animation at T0+latency
↓
Animation interpolates position over frames
↓
Server says "arrived at B" at T1
↓
Client reconciles if needed
3. Callback System

onAnimationStart: Setup effects, sounds, UI updates
onAnimationEnd: Cleanup, state transitions, trigger next action
onFrame: Direction changes during path movement, effect spawning

4. Path-Based Movement
During walking animations:

Interpolate along path segments
Calculate direction for each segment
Smooth direction transitions at corners
Handle interruptions (new path, combat)

5. Effects Coordination
Entity Attack Animation
    ├─ Frame 5: onFrame callback
    │     └─ Spawn attack effect at midpoint
    ├─ Frame 8: Hit connects
    │     └─ Damage numbers, hit effect
    └─ Frame 12: onEnd callback
          └─ Return to idle
6. State Priority & Interruption

Death overrides everything
Hit/damage interrupts most actions
Attack might interrupt movement
Movement queues after current animation

7. Predictive Animation
typescript// Example flow
1. User clicks to move → Start walk animation immediately
2. Send move request to server
3. Animate along predicted path
4. Server responds with actual path
5. Smoothly adjust if different
8. Effect Geometry

Projectile arcs (quadratic bezier)
Rotation to face target
Scale based on distance
Particle systems for impacts

9. Performance Optimizations

Pool animation states and sprites
Preload all direction variants
Cache calculated paths
Batch effect updates

10. Debug/Development Tools

Animation state visualizer
Frame-by-frame stepping
Network delay simulation
State machine graph viewer

This architecture gives you:

Smooth client experience despite network latency
Rich animation coordination
Clean separation between logic and rendering
Extensible effect system

The key insight is treating animations as first-class state machines that can be influenced by both server events and local predictions, with a reconciliation layer to keep everything synchronized.