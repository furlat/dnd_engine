# State Management Architecture Guide 🏗️

## 🎯 **Executive Summary**

This guide documents our proven state management architecture that successfully handles movement, attacks, effects, and rendering in a complex isometric game. The system follows the **SERVER STATE → ANIMATION STATE → LOCAL STATE → VISUAL STATE** pattern with event-driven coordination between specialized components.

**Key Achievement**: Zero state conflicts, smooth animations, and clean separation of concerns.

---

## 🌊 **Complete System Flow**

### **1. Data Flow Architecture**
```
🌐 SERVER API
    ↓ (HTTP responses)
🗄️ BATTLEMAP STORE (source of truth)
    ↓ (triggers events)
🎮 ANIMATION STORE (active animations)
    ↓ (managed by)
🎭 ANIMATION CONTROLLER (coordinator)
    ↓ (delegates to)
🎪 SPECIALIZED HANDLERS (business logic)
    ↓ (updates via callbacks)
🎨 RENDERER MANAGERS (visual state)
    ↓ (renders to)
📺 PIXI.JS DISPLAY (screen)
```

### **2. Event Flow Lifecycle**
```
🖱️ USER INPUT → InteractionsManager
    ↓ (validates & delegates)
🚀 SERVICE LAYER → EntityMovementService/EntityCombatService
    ↓ (makes API calls)
🌐 SERVER RESPONSE → Updates battlemapStore
    ↓ (triggers animations)
🎬 ANIMATION SYSTEM → Creates/updates animationStore
    ↓ (coordinates via events)
🎪 HANDLERS → Process business logic locally
    ↓ (updates visuals via callbacks)
🎨 RENDERERS → Update display immediately
    ↓ (when complete)
🔄 SYNC BACK → Clean up and sync states
```

---

## 🧩 **Component Architecture**

### **🎮 Animation Controller** (Central Coordinator)
**File**: `AnimationController.ts`  
**Role**: Event-driven coordinator between stores and handlers

```typescript
class AnimationController {
  // Coordinates 4 specialized handlers
  private combatHandler: CombatAnimationHandler;      // Attack/damage logic
  private effectsHandler: EffectsAnimationHandler;    // Blood splats, sparks
  private soundHandler: SoundAnimationHandler;        // Audio coordination  
  private movementHandler: MovementAnimationHandler;  // Movement interpolation
  
  // Listens to animationStore events and delegates to handlers
  initialize() {
    this.setupEventListeners(); // MOVEMENT_STARTED, ATTACK_IMPACT_FRAME, etc.
    this.initializeHandlers();
  }
}
```

**Responsibilities:**
- ✅ Listen to animationStore lifecycle events
- ✅ Update battlemapStore sprite animations (WALK, ATTACK1, etc.)
- ✅ Delegate complex logic to specialized handlers
- ✅ Bridge between animation system and rendering system
- ❌ No business logic - pure coordination

---

### **🎪 Specialized Animation Handlers**

#### **🏃 MovementAnimationHandler** 
**File**: `MovementAnimationHandler.ts`  
**Role**: Frame-by-frame movement interpolation with server adoption

```typescript
class MovementAnimationHandler {
  // LOCAL STATE: Complex movement data that doesn't belong in stores
  private activeMovements: Map<string, MovementAnimationData>;
  
  updateAnimations(deltaTime: number) {
    this.activeMovements.forEach((movement, entityId) => {
      // 1. Read server state (read-only)
      const entity = battlemapStore.entities.summaries[entityId];
      
      // 2. Interpolate position locally
      const currentPos = this.calculateCurrentPosition(movement, deltaTime);
      
      // 3. Update visual via callback (no store pollution)
      this.onUpdateEntityVisualPosition?.(entityId, currentPos);
      
      // 4. Handle server adoption if available
      this.adoptServerPath(movement, entity);
      
      // 5. When complete, sync back to stores
      if (movement.isComplete) {
        battlemapActions.resyncEntityPosition(entityId);
        this.activeMovements.delete(entityId);
      }
    });
  }
}
```

#### **⚔️ CombatAnimationHandler**
**File**: `CombatAnimationHandler.ts`  
**Role**: Attack coordination and damage animation timing

```typescript
class CombatAnimationHandler {
  handleAttackImpact(data: AttackImpactEvent) {
    const { entityId, targetId, metadata } = data;
    
    // 1. Trigger damage animation on target
    this.triggerDamageAnimation(targetId, metadata);
    
    // 2. Trigger effects (blood splats, sparks)
    this.triggerCombatEffects(entityId, targetId, metadata);
    
    // 3. Trigger sound effects
    this.triggerSoundEffects(metadata);
  }
}
```

#### **💥 EffectsAnimationHandler**
**File**: `EffectsAnimationHandler.ts`  
**Role**: Visual effects (blood, sparks, magic)

```typescript
class EffectsAnimationHandler {
  handleAttackImpact(data: AttackImpactEvent) {
    // Create blood splat effects with precise positioning
    const bloodConfig = battlemapStore.controls.bloodSplatConfig;
    if (bloodConfig.awayFromAttacker.enabled) {
      this.createBloodSplatEffect(data.targetId, data.entityId, 'awayFromAttacker');
    }
  }
}
```

---

### **🎨 Renderer Architecture**

#### **🖼️ IsometricEntityRenderer** (Visual Presentation)
**Role**: Sprite rendering and frame-level event detection

```typescript
class IsometricEntityRenderer {
  // Uses specialized managers for clean separation
  private visibilityManager = new VisibilityManager();  // Entity visibility logic
  private zOrderManager = new ZOrderManager();          // Layer ordering
  private positionManager = new PositionManager();      // Position updates
  
  // ONLY emits frame timing events - no business logic
  setupAnimationCallbacks(sprite: AnimatedSprite) {
    sprite.onFrameChange = (frame) => {
      if (isAttackAnimation && frameProgress >= 0.4) {
        // PURE EVENT EMISSION - handlers do the logic
        animationEventBus.emit(ATTACK_IMPACT_FRAME, { entityId, frame });
      }
    };
  }
}
```

#### **🔍 Specialized Managers**
**Purpose**: Extract complex renderer logic into focused components

- **VisibilityManager**: Entity visibility based on senses data
- **ZOrderManager**: Dynamic layer ordering during animations
- **PositionManager**: Grid-to-screen coordinate conversion

---

### **🖱️ User Input Flow**

#### **IsometricInteractionsManager** (Input Coordinator)
```typescript
class IsometricInteractionsManager {
  handleEntityMovement(gridX: number, gridY: number) {
    // 1. Cache senses data to prevent flicker
    this.cacheSensesDataForMovement();
    
    // 2. Delegate to service (no animation details here)
    const result = await EntityMovementService.moveEntityTo(entityId, [gridX, gridY]);
    
    // 3. Log result - service handles everything else
  }
}
```

---

## 🏪 **Store Architecture**

### **🗺️ BattlemapStore** (Main State)
```typescript
interface BattlemapStoreState {
  entities: {
    summaries: Record<string, EntitySummary>;        // SERVER STATE
    spriteMappings: Record<string, EntitySpriteMapping>; // Visual config
    directions: Record<string, Direction>;           // Current facing
    attackAnimations: Record<string, AttackMetadata>; // Simple metadata
    pathSenses: Record<string, SensesSnapshot>;      // Movement senses
    zOrderOverrides: Record<string, number>;         // Global layering
  };
  // ... other state
}
```

**Rules:**
- ✅ Always let server data flow in (never block)
- ✅ Simple metadata only (no complex animation data)
- ✅ Triggers for animation system
- ❌ No frame-by-frame animation progress

### **🎬 AnimationStore** (Animation Registry)
```typescript
interface AnimationStoreState {
  activeAnimations: Record<string, Animation>; // entityId -> Animation
  events: AnimationEvent[];                    // Event queue
}

interface Animation {
  id: string;
  entityId: string;
  type: AnimationState;                 // WALK, ATTACK1, etc.
  status: 'playing' | 'completed';
  startTime: number;
  duration: number;
  clientInitiated: boolean;             // Client prediction vs server
  data: any;                           // Animation-specific data
}
```

**Rules:**
- ✅ Registry of what's currently animating
- ✅ Event bus for coordination
- ✅ Client prediction tracking
- ❌ No visual position interpolation (that's in handlers)

---

## 🚀 **Adding New Systems: Complete Examples**

### **Example 1: Ranged Attacks** 🏹

#### **Step 1: Extend Types**
```typescript
// In battlemap_types.ts
export enum AnimationState {
  // ... existing
  RANGED_ATTACK = 'RangedAttack',
  DODGE = 'Dodge',
}

export interface RangedAttackMetadata extends AttackMetadata {
  projectileType: 'arrow' | 'bolt' | 'throwing_knife';
  targetPosition: Position;
  flightTime: number; // milliseconds
}
```

#### **Step 2: Add to BattlemapStore**
```typescript
// In battlemapStore.ts
interface EntityState {
  // ... existing
  rangedAttackAnimations: Record<string, RangedAttackMetadata>; // entityId -> metadata
}

const battlemapActions = {
  // ... existing
  startEntityRangedAttack: (entityId: string, targetId: string, metadata: RangedAttackMetadata) => {
    battlemapStore.entities.rangedAttackAnimations[entityId] = metadata;
    battlemapActions.setEntityAnimation(entityId, AnimationState.RANGED_ATTACK);
  },
  
  completeEntityRangedAttack: (entityId: string) => {
    delete battlemapStore.entities.rangedAttackAnimations[entityId];
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapActions.setEntityAnimation(entityId, mapping.idleAnimation);
    }
  },
};
```

#### **Step 3: Create RangedCombatHandler**
```typescript
// New file: RangedCombatAnimationHandler.ts
export class RangedCombatAnimationHandler {
  private activeProjectiles: Map<string, ProjectileData> = new Map();
  
  initialize(): void {
    // Listen for ranged attack impact frames
    animationEventBus.on(RANGED_ATTACK_RELEASE_FRAME, this.handleProjectileRelease.bind(this));
  }
  
  handleProjectileRelease(data: any): void {
    const { entityId, targetId, metadata } = data;
    
    // Create projectile animation
    const projectileId = `projectile_${Date.now()}_${entityId}`;
    const projectile: ProjectileData = {
      id: projectileId,
      attackerId: entityId,
      targetId: targetId,
      startPosition: this.getEntityPosition(entityId),
      targetPosition: metadata.targetPosition,
      projectileType: metadata.projectileType,
      startTime: Date.now(),
      flightTime: metadata.flightTime,
    };
    
    this.activeProjectiles.set(projectileId, projectile);
    
    // Create visual projectile effect
    this.createProjectileEffect(projectile);
  }
  
  updateProjectiles(deltaTime: number): void {
    this.activeProjectiles.forEach((projectile, id) => {
      const elapsed = Date.now() - projectile.startTime;
      const progress = Math.min(elapsed / projectile.flightTime, 1.0);
      
      // Interpolate projectile position
      const currentPos = this.interpolateProjectilePosition(projectile, progress);
      this.updateProjectileVisualPosition(id, currentPos);
      
      // Check for impact
      if (progress >= 1.0) {
        this.handleProjectileImpact(projectile);
        this.activeProjectiles.delete(id);
      }
    });
  }
  
  private handleProjectileImpact(projectile: ProjectileData): void {
    // Trigger damage on target (same as melee)
    animationEventBus.emit(ATTACK_IMPACT_FRAME, {
      entityId: projectile.attackerId,
      targetId: projectile.targetId,
      metadata: { projectileType: projectile.projectileType }
    });
    
    // Remove projectile visual
    this.removeProjectileEffect(projectile.id);
  }
}
```

#### **Step 4: Integrate with AnimationController**
```typescript
// In AnimationController.ts
class AnimationController {
  private rangedCombatHandler: RangedCombatAnimationHandler; // Add this
  
  constructor() {
    // ... existing handlers
    this.rangedCombatHandler = new RangedCombatAnimationHandler();
  }
  
  initialize() {
    // ... existing
    this.rangedCombatHandler.initialize();
  }
  
  updateAnimations(deltaTime: number) {
    // ... existing
    this.rangedCombatHandler.updateProjectiles(deltaTime);
  }
}
```

#### **Step 5: Add Service Layer**
```typescript
// In EntityCombatService.ts (extend existing)
export class EntityCombatService {
  static async executeRangedAttack(
    attackerId: string, 
    targetId: string, 
    projectileType: 'arrow' | 'bolt' | 'throwing_knife' = 'arrow'
  ): Promise<boolean> {
    const attacker = battlemapStore.entities.summaries[attackerId];
    const target = battlemapStore.entities.summaries[targetId];
    
    if (!attacker || !target) return false;
    
    // Calculate flight time based on distance
    const distance = this.calculateDistance(attacker.position, target.position);
    const flightTime = distance * 100; // 100ms per tile
    
    const metadata: RangedAttackMetadata = {
      weapon_slot: 'MAIN_HAND',
      projectileType,
      targetPosition: target.position,
      flightTime,
    };
    
    // Start animation immediately (client prediction)
    battlemapActions.startEntityRangedAttack(attackerId, targetId, metadata);
    
    try {
      // Make API call
      const response = await executeAttack(attackerId, targetId, 'MAIN_HAND', 'Ranged Attack');
      
      // Server will adopt or reject the animation
      // Impact will be triggered when projectile reaches target
      return true;
    } catch (error) {
      // Rollback animation on error
      battlemapActions.completeEntityRangedAttack(attackerId);
      throw error;
    }
  }
}
```

#### **Step 6: Update Renderer for New Frame Events**
```typescript
// In IsometricEntityRenderer.ts
setupOptimizedAnimationCallbacks(sprite: AnimatedSprite, entity: EntitySummary, mapping: EntitySpriteMapping) {
  // ... existing code
  
  const isRangedAttack = mapping.currentAnimation === AnimationState.RANGED_ATTACK;
  
  if (isRangedAttack) {
    sprite.onFrameChange = (currentFrame: number) => {
      const frameProgress = currentFrame / Math.max(sprite.totalFrames - 1, 1);
      
      // Release projectile at 60% through animation (adjust as needed)
      if (!releaseTriggered && frameProgress >= 0.6) {
        releaseTriggered = true;
        animationEventBus.emit(RANGED_ATTACK_RELEASE_FRAME, {
          entityId: entity.uuid,
          frameProgress,
          currentFrame
        });
      }
    };
  }
}
```

---

### **Example 2: Spell System** 🧙‍♂️

#### **Step 1: Define Spell Types**
```typescript
// In battlemap_types.ts
export enum SpellType {
  FIREBALL = 'fireball',
  LIGHTNING_BOLT = 'lightning_bolt', 
  HEAL = 'heal',
  SHIELD = 'shield',
  TELEPORT = 'teleport',
}

export enum AnimationState {
  // ... existing
  CAST_SPELL = 'CastSpell',
  CHANNEL_SPELL = 'ChannelSpell',
}

export interface SpellMetadata {
  spellType: SpellType;
  targetPosition?: Position;
  targetEntityId?: string;
  castTime: number;        // milliseconds
  effectDuration?: number; // for buffs/debuffs
  damage?: number;
  healAmount?: number;
  requiresLineOfSight: boolean;
}
```

#### **Step 2: Create SpellAnimationHandler**
```typescript
// New file: SpellAnimationHandler.ts
export class SpellAnimationHandler {
  private activeSpells: Map<string, SpellData> = new Map();
  private channeledSpells: Map<string, ChannelData> = new Map();
  
  initialize(): void {
    animationEventBus.on(SPELL_CAST_FRAME, this.handleSpellCast.bind(this));
    animationEventBus.on(SPELL_CHANNEL_COMPLETE, this.handleChannelComplete.bind(this));
  }
  
  handleSpellCast(data: any): void {
    const { entityId, spellMetadata } = data;
    
    switch (spellMetadata.spellType) {
      case SpellType.FIREBALL:
        this.castFireball(entityId, spellMetadata);
        break;
      case SpellType.LIGHTNING_BOLT:
        this.castLightningBolt(entityId, spellMetadata);
        break;
      case SpellType.HEAL:
        this.castHeal(entityId, spellMetadata);
        break;
      case SpellType.TELEPORT:
        this.castTeleport(entityId, spellMetadata);
        break;
    }
  }
  
  private castFireball(casterId: string, metadata: SpellMetadata): void {
    // Create projectile (similar to ranged attacks but with magic effects)
    const fireballId = `fireball_${Date.now()}_${casterId}`;
    
    // Create fireball projectile with particle trail
    this.createMagicProjectile(fireballId, {
      type: 'fireball',
      startPosition: this.getEntityPosition(casterId),
      targetPosition: metadata.targetPosition!,
      speed: 300, // pixels per second
      trailEffect: EffectType.FIRE_AURA,
      impactEffect: EffectType.SPLASH,
    });
  }
  
  private castLightningBolt(casterId: string, metadata: SpellMetadata): void {
    // Instant effect - no projectile
    const casterPos = this.getEntityPosition(casterId);
    const targetPos = metadata.targetPosition!;
    
    // Create lightning line effect
    this.createLightningEffect(casterPos, targetPos);
    
    // Immediate damage
    setTimeout(() => {
      animationEventBus.emit(SPELL_IMPACT, {
        casterId,
        targetPosition: targetPos,
        spellType: SpellType.LIGHTNING_BOLT,
        damage: metadata.damage,
      });
    }, 100); // Small delay for visual effect
  }
  
  private castHeal(casterId: string, metadata: SpellMetadata): void {
    const targetId = metadata.targetEntityId!;
    
    // Create healing effect on target
    this.createHealingEffect(targetId, metadata.healAmount!);
    
    // Apply healing immediately
    animationEventBus.emit(SPELL_IMPACT, {
      casterId,
      targetEntityId: targetId,
      spellType: SpellType.HEAL,
      healAmount: metadata.healAmount,
    });
  }
  
  private castTeleport(casterId: string, metadata: SpellMetadata): void {
    const targetPos = metadata.targetPosition!;
    
    // 1. Fade out effect at current position
    this.createTeleportEffect(casterId, 'fadeOut');
    
    // 2. Move entity instantly (after fade)
    setTimeout(() => {
      battlemapActions.resyncEntityPosition(casterId); // Snap to server position
      
      // 3. Fade in effect at new position  
      this.createTeleportEffect(casterId, 'fadeIn');
    }, 300);
  }
}
```

#### **Step 3: Add Spell Service**
```typescript
// New file: EntitySpellService.ts
export class EntitySpellService {
  static async castSpell(
    casterId: string,
    spellType: SpellType,
    targetPosition?: Position,
    targetEntityId?: string
  ): Promise<boolean> {
    const caster = battlemapStore.entities.summaries[casterId];
    if (!caster) return false;
    
    // Validate spell requirements
    if (!this.validateSpellCast(caster, spellType, targetPosition, targetEntityId)) {
      return false;
    }
    
    const spellMetadata: SpellMetadata = {
      spellType,
      targetPosition,
      targetEntityId,
      castTime: this.getSpellCastTime(spellType),
      requiresLineOfSight: this.spellRequiresLOS(spellType),
    };
    
    // Start casting animation
    battlemapActions.startEntitySpellCast(casterId, spellMetadata);
    
    try {
      // Make API call to server
      const response = await this.callSpellAPI(casterId, spellMetadata);
      
      // Server will handle the actual spell effect
      return true;
    } catch (error) {
      // Rollback on error
      battlemapActions.completeEntitySpellCast(casterId);
      throw error;
    }
  }
  
  private static validateSpellCast(
    caster: EntitySummary,
    spellType: SpellType,
    targetPosition?: Position,
    targetEntityId?: string
  ): boolean {
    // Check mana, spell slots, etc.
    // Check line of sight for targeted spells
    // Check range requirements
    return true; // Simplified
  }
  
  private static getSpellCastTime(spellType: SpellType): number {
    const castTimes = {
      [SpellType.FIREBALL]: 1000,      // 1 second
      [SpellType.LIGHTNING_BOLT]: 500, // 0.5 seconds  
      [SpellType.HEAL]: 800,           // 0.8 seconds
      [SpellType.SHIELD]: 600,         // 0.6 seconds
      [SpellType.TELEPORT]: 1200,      // 1.2 seconds
    };
    return castTimes[spellType] || 1000;
  }
}
```

#### **Step 4: Update Interactions Manager**
```typescript
// In IsometricInteractionsManager.ts
private async handleSpellCast(gridX: number, gridY: number, spellType: SpellType): Promise<void> {
  const selectedEntityId = battlemapStore.entities.selectedEntityId;
  if (!selectedEntityId) return;
  
  // Validate entity can cast spells
  if (!EntitySpellService.canCastSpells(selectedEntityId)) {
    console.log('Entity cannot cast spells');
    return;
  }
  
  const targetPosition: Position = [gridX, gridY];
  
  try {
    const success = await EntitySpellService.castSpell(
      selectedEntityId, 
      spellType, 
      targetPosition
    );
    
    if (success) {
      console.log(`Spell ${spellType} cast successfully`);
    }
  } catch (error) {
    console.error(`Failed to cast ${spellType}:`, error);
  }
}
```

---

## 🛡️ **Error Handling Patterns**

### **1. Animation Rollback**
```typescript
// When server rejects client prediction
handleAnimationRejection(animation: Animation) {
  switch (animation.type) {
    case AnimationState.WALK:
      // Snap back to server position
      battlemapActions.resyncEntityPosition(animation.entityId);
      break;
      
    case AnimationState.ATTACK1:
      // Cancel attack, return to idle
      battlemapActions.completeEntityAttack(animation.entityId);
      break;
      
    case SpellType.FIREBALL:
      // Remove projectile, refund mana
      this.cancelSpellProjectile(animation.entityId);
      this.refundSpellCost(animation.entityId, animation.data.spellType);
      break;
  }
}
```

### **2. State Validation**
```typescript
// Always validate before processing
updateAnimation(entityId: string, deltaTime: number) {
  const entity = battlemapStore.entities.summaries[entityId];
  if (!entity) {
    console.warn(`Entity ${entityId} no longer exists, cleaning up animation`);
    this.cleanupAnimation(entityId);
    return;
  }
  
  const animation = animationActions.getActiveAnimation(entityId);
  if (!animation) {
    console.warn(`No active animation for ${entityId}, skipping update`);
    return;
  }
  
  // Safe to proceed...
}
```

### **3. Graceful Degradation**
```typescript
// Missing handlers don't crash the system
try {
  animationEventBus.emit(NEW_SPELL_EVENT, data);
} catch (error) {
  console.warn('Spell handler not available, spell will have no visual effects:', error);
  // Game continues normally, just missing visual effects
}
```

---

## 📏 **Performance Guidelines**

### **1. Local State Management**
- ✅ **Use local state** for high-frequency updates (movement interpolation)
- ✅ **Sync back** to stores only when complete
- ❌ **Don't spam stores** with intermediate animation values

### **2. Event Bus Usage**
- ✅ **Emit specific events** (ATTACK_IMPACT_FRAME, SPELL_CAST_COMPLETE)
- ✅ **Include relevant data** in event payload
- ❌ **Don't emit every frame** unless necessary

### **3. Render Optimization**  
- ✅ **Cache visibility states** to avoid redundant calculations
- ✅ **Skip updates** for off-screen or invisible entities
- ✅ **Batch position updates** when view changes

---

## 🎯 **Testing Strategy**

### **1. Unit Tests for Handlers**
```typescript
describe('SpellAnimationHandler', () => {
  it('should create fireball projectile on cast frame', () => {
    const handler = new SpellAnimationHandler();
    handler.initialize();
    
    const mockData = {
      entityId: 'caster-1',
      spellMetadata: { 
        spellType: SpellType.FIREBALL,
        targetPosition: [5, 5]
      }
    };
    
    handler.handleSpellCast(mockData);
    
    expect(handler.getActiveProjectiles()).toHaveLength(1);
  });
});
```

### **2. Integration Tests**
```typescript
describe('Spell System Integration', () => {
  it('should complete full spell cast workflow', async () => {
    // 1. User clicks to cast spell
    await interactionsManager.handleSpellCast(5, 5, SpellType.FIREBALL);
    
    // 2. Verify animation started
    expect(animationStore.activeAnimations['caster-1']).toBeDefined();
    
    // 3. Simulate frame progression
    renderer.simulateFrameProgress('caster-1', 0.8); // Cast frame
    
    // 4. Verify projectile created
    expect(effectsHandler.getActiveProjectiles()).toHaveLength(1);
    
    // 5. Simulate projectile impact
    await effectsHandler.simulateProjectileImpact();
    
    // 6. Verify damage applied
    expect(targetEntity.currentHP).toBeLessThan(targetEntity.maxHP);
  });
});
```

---

## 🚀 **Quick Start Checklist for New Systems**

### **✅ For New Animation Types:**
1. Add enum to `AnimationState` in `battlemap_types.ts`
2. Add sprite sheets to `/assets/entities/{folder}/{AnimationState}.json`
3. Update `AnimationController` event listeners if needed
4. Test frame timing in renderer callbacks

### **✅ For New Combat Mechanics:**
1. Extend `AttackMetadata` with new fields
2. Create new handler class (extend pattern from `CombatAnimationHandler`)  
3. Add handler to `AnimationController` constructor
4. Add service methods to `EntityCombatService`
5. Update `InteractionsManager` for user input

### **✅ For New Effect Types:**
1. Add to `EffectType` enum in `battlemap_types.ts`
2. Add sprite sheets to `/assets/effects/{effectType}.json`
3. Update `EffectsAnimationHandler` with new effect logic
4. Test effect positioning and timing

### **✅ For New Visual Features:**
1. Add manager to `IsometricEntityRenderer` if complex
2. Update store state in `battlemapStore.ts` if needed
3. Add to `BattlemapEngine` renderers if separate layer needed
4. Test performance with multiple entities

---

## 🏆 **Success Metrics**

Our architecture achieves:
- ✅ **Zero state conflicts** - animations never fight each other
- ✅ **Smooth 60fps rendering** - local state prevents store spam
- ✅ **Clean separation** - each component has single responsibility  
- ✅ **Easy testing** - handlers can be tested in isolation
- ✅ **Extensible design** - new features follow established patterns
- ✅ **Server synchronization** - client prediction with server adoption
- ✅ **Graceful error handling** - missing features don't crash system

**This architecture is production-ready and scales to complex game mechanics.** 🎉 