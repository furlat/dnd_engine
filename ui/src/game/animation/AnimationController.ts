import { battlemapStore, battlemapActions } from '../../store/battlemapStore';
import { animationActions, animationEventBus, AnimationLifecycleEvents } from '../../store/animationStore';
import { AnimationState, Direction } from '../../types/battlemap_types';
import { subscribe } from 'valtio';
import { CombatAnimationHandler } from './handlers/CombatAnimationHandler';
import { EffectsAnimationHandler } from './handlers/EffectsAnimationHandler';
import { SoundAnimationHandler } from './handlers/SoundAnimationHandler';
import { MovementAnimationHandler } from './handlers/MovementAnimationHandler';
import { animationStore } from '../../store/animationStore';

/**
 * Main controller that coordinates all animation handlers and bridges animationStore with battlemap
 * FIXED: Now properly uses animationStore for all animations with adoption flow
 */
export class AnimationController {
  private unsubscribers: Array<() => void> = [];
  
  // Specialized handlers
  private combatHandler: CombatAnimationHandler;
  private effectsHandler: EffectsAnimationHandler;
  private soundHandler: SoundAnimationHandler;
  private movementHandler: MovementAnimationHandler;

  constructor() {
    // Initialize handlers
    this.combatHandler = new CombatAnimationHandler();
    this.effectsHandler = new EffectsAnimationHandler();
    this.soundHandler = new SoundAnimationHandler();
    this.movementHandler = new MovementAnimationHandler();
  }

  initialize(): void {
    console.log('[AnimationController] Initializing animation system with proper event adoption flow');
    
    // Initialize all handlers
    this.combatHandler.initialize();
    this.effectsHandler.initialize();
    this.soundHandler.initialize();
    
    // NOTE: Movement handler requires renderer callbacks and will be initialized separately
    // by the IsometricEntityRenderer when it provides the necessary callbacks
    
    this.setupEventListeners();
    // REMOVED: No more battlemapStore subscriptions - we use animationStore events only
  }

  /**
   * Set up event listeners for animation coordination
   * FIXED: Only listen to animationStore events, not battlemapStore
   */
  private setupEventListeners(): void {
    // Listen for movement animations from animationStore
    const unsubMovement = animationEventBus.on(
      AnimationLifecycleEvents.MOVEMENT_STARTED,
      this.handleMovementStarted.bind(this)
    );
    this.unsubscribers.push(unsubMovement);

    // Listen for movement completion from animationStore
    const unsubMovementComplete = animationEventBus.on(
      AnimationLifecycleEvents.MOVEMENT_COMPLETED,
      this.handleMovementCompleted.bind(this)
    );
    this.unsubscribers.push(unsubMovementComplete);

    // Listen for attack animations from animationStore
    const unsubAttack = animationEventBus.on(
      AnimationLifecycleEvents.ATTACK_STARTED,
      this.handleAttackStarted.bind(this)
    );
    this.unsubscribers.push(unsubAttack);

    // Listen for attack completion from animationStore
    const unsubAttackComplete = animationEventBus.on(
      AnimationLifecycleEvents.ATTACK_COMPLETED,
      this.handleAttackCompleted.bind(this)
    );
    this.unsubscribers.push(unsubAttackComplete);

    // Listen for damage animations from animationStore
    const unsubDamage = animationEventBus.on(
      AnimationLifecycleEvents.DAMAGE_STARTED,
      this.handleDamageStarted.bind(this)
    );
    this.unsubscribers.push(unsubDamage);

    // Listen for z-order change requests from handlers
    const unsubZOrder = animationEventBus.on(
      AnimationLifecycleEvents.ZORDER_CHANGE_REQUESTED,
      this.handleZOrderChange.bind(this)
    );
    this.unsubscribers.push(unsubZOrder);

    // Listen for animation adoption events
    const unsubAdopted = animationEventBus.on(
      AnimationLifecycleEvents.ANIMATION_ADOPTED,
      this.handleAnimationAdopted.bind(this)
    );
    this.unsubscribers.push(unsubAdopted);

    // Listen for animation rejection events
    const unsubRejected = animationEventBus.on(
      AnimationLifecycleEvents.ANIMATION_REJECTED,
      this.handleAnimationRejected.bind(this)
    );
    this.unsubscribers.push(unsubRejected);
  }

  /**
   * Handle movement started from animationStore
   */
  private handleMovementStarted(animation: any): void {
    console.log('[AnimationController] Movement animation started:', animation.entityId);
    
    // Update battlemap sprite mapping to show walk animation
    const currentMapping = battlemapStore.entities.spriteMappings[animation.entityId];
    if (currentMapping) {
      battlemapActions.setEntityAnimation(animation.entityId, AnimationState.WALK);
      battlemapActions.setEntityDirectionFromMapping(animation.entityId, animation.data.direction);
      console.log(`[AnimationController] Updated sprite mapping for ${animation.entityId}: WALK, ${animation.data.direction}`);
    }
  }

  /**
   * Handle movement completed from animationStore
   */
  private handleMovementCompleted(animation: any): void {
    console.log('[AnimationController] Movement animation completed:', animation.entityId);
    
    // Return to idle animation
    const currentMapping = battlemapStore.entities.spriteMappings[animation.entityId];
    if (currentMapping) {
      battlemapActions.setEntityAnimation(animation.entityId, currentMapping.idleAnimation);
      console.log(`[AnimationController] Returned ${animation.entityId} to idle animation: ${currentMapping.idleAnimation}`);
    }
    
    // FIXED: No resync needed - server data is already flowing to store normally
    // The visual position will automatically sync to server position via normal rendering
    console.log(`[AnimationController] Movement complete - server position already in store`);
  }

  /**
   * Handle attack started from animationStore
   */
  private handleAttackStarted(animation: any): void {
    console.log('[AnimationController] Attack animation started:', animation.entityId);
    
    // Update battlemap sprite mapping to show attack animation
    const currentMapping = battlemapStore.entities.spriteMappings[animation.entityId];
    if (currentMapping) {
      battlemapActions.setEntityAnimation(animation.entityId, AnimationState.ATTACK1);
      battlemapActions.setEntityDirectionFromMapping(animation.entityId, animation.data.direction);
      console.log(`[AnimationController] Updated sprite mapping for ${animation.entityId}: ATTACK1, ${animation.data.direction}`);
    }
  }

  /**
   * Handle attack completed from animationStore
   */
  private handleAttackCompleted(animation: any): void {
    console.log('[AnimationController] Attack animation completed:', animation.entityId);
    
    // Return to idle animation
    const currentMapping = battlemapStore.entities.spriteMappings[animation.entityId];
    if (currentMapping) {
      battlemapActions.setEntityAnimation(animation.entityId, currentMapping.idleAnimation);
      console.log(`[AnimationController] Returned ${animation.entityId} to idle animation: ${currentMapping.idleAnimation}`);
    }
  }

  /**
   * Handle damage started from animationStore
   */
  private handleDamageStarted(animation: any): void {
    console.log('[AnimationController] Damage animation started:', animation.entityId);
    
    // Update battlemap sprite mapping to show damage animation
    const currentMapping = battlemapStore.entities.spriteMappings[animation.entityId];
    if (currentMapping) {
      battlemapActions.setEntityAnimation(animation.entityId, AnimationState.TAKE_DAMAGE);
      battlemapActions.setEntityDirectionFromMapping(animation.entityId, animation.data.direction);
      console.log(`[AnimationController] Updated sprite mapping for ${animation.entityId}: TAKE_DAMAGE, ${animation.data.direction}`);
    }
  }

  /**
   * Handle animation adoption (server confirmed client prediction)
   */
  private handleAnimationAdopted(animation: any): void {
    console.log('[AnimationController] Animation adopted by server:', animation.id, animation.entityId);
    // Animation can continue playing normally - server approved it
  }

  /**
   * Handle animation rejection (server rejected client prediction)
   */
  private handleAnimationRejected(animation: any): void {
    console.log('[AnimationController] Animation rejected by server:', animation.id, animation.entityId);
    
    // For movement: snap back to original position
    if (animation.type === AnimationState.WALK || animation.type === AnimationState.RUN) {
      console.log(`[AnimationController] Movement rejected, resyncing ${animation.entityId} to server position`);
      // The animation will complete normally but won't update the server position
      // The movement handler should handle the snap-back
    }
  }

  /**
   * Handle z-order change requests from handlers
   */
  private handleZOrderChange(data: any): void {
    const { type, changes, entityIds } = data;

    if (type === 'set' && changes) {
      // Set z-order for specific entities
      Object.entries(changes).forEach(([entityId, zIndex]) => {
        console.log(`[AnimationController] Setting z-order for ${entityId}: ${zIndex}`);
      });
    } else if (type === 'clear' && entityIds) {
      // Clear z-order for specific entities
      entityIds.forEach((entityId: string) => {
        console.log(`[AnimationController] Clearing z-order for ${entityId}`);
      });
    }
  }

  /**
   * Update all active animations (called from render loop)
   */
  updateAnimations(deltaTime: number): void {
    // CRITICAL: Update movement animations first (frame-by-frame interpolation)
    this.movementHandler.updateAnimations(deltaTime);
    
    // FIXED: Only update progress for entities that actually have active animations
    // Don't interfere with basic idle sprite functionality
    const activeAnimations = Object.values(animationStore.activeAnimations);
    if (activeAnimations.length > 0) {
      activeAnimations.forEach(animation => {
        // Only update if the animation is actually playing
        if (animation.status === 'playing') {
          animationActions.updateAnimationProgress(animation.entityId, deltaTime);
        }
      });
    }
  }

  destroy(): void {
    console.log('[AnimationController] Destroying animation system');
    
    // Destroy all handlers
    this.combatHandler.destroy();
    this.effectsHandler.destroy();
    this.soundHandler.destroy();
    
    // Clean up subscriptions
    this.unsubscribers.forEach(unsub => unsub());
    this.unsubscribers = [];
  }

  /**
   * Initialize movement handler with renderer callbacks
   * Called by IsometricEntityRenderer after it's ready
   */
  initializeMovementHandler(callbacks: {
    onUpdateEntityVisualPosition: (entityId: string, position: any) => void;
    onUpdateSpriteDirection: (entityId: string, direction: any) => void;
    onSetLocalZOrder: (entityId: string, zIndex: number) => void;
    onClearLocalZOrder: (entityId: string) => void;
  }): void {
    this.movementHandler.initialize(callbacks);
    console.log('[AnimationController] Movement handler initialized with renderer callbacks');
  }

  /**
   * Get movement handler for external access
   */
  getMovementHandler(): MovementAnimationHandler {
    return this.movementHandler;
  }
}

// Export singleton instance
export const animationController = new AnimationController(); 