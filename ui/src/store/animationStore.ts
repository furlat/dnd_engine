import { proxy, subscribe } from 'valtio';
import { AnimationStoreState, AnimationEvent, AnimationStatus, AnimationEventType } from '../types/animation_types';
import { animationEventBus } from '../game/animation/AnimationEventBus';
import { AnimationLifecycleEvents } from '../types/animation_types';
import { AnimationState } from '../types/battlemap_types';

// Create the store
const animationStore = proxy<AnimationStoreState>({
  activeAnimations: {},
  animationQueue: [],
  animationHistory: [],
  config: {
    maxHistorySize: 50,
    allowClientPrediction: true,
    animationSpeed: 1.0
  }
});

// Animation actions
export const animationActions = {
  /**
   * Create a new animation (can be orphan/client-predicted)
   */
  createAnimation(
    entityId: string,
    type: AnimationState,
    duration: number,
    data: Record<string, any>,
    clientInitiated: boolean = false
  ): string {
    const id = `anim_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const animation: AnimationEvent = {
      id,
      entityId,
      type,
      status: clientInitiated ? AnimationStatus.ORPHAN : AnimationStatus.PENDING,
      startTime: Date.now(),
      duration,
      progress: 0,
      clientInitiated,
      data
    };
    
    // Add to queue
    animationStore.animationQueue.push(animation);
    
    // Emit event
    animationEventBus.emit(AnimationLifecycleEvents.ANIMATION_QUEUED, animation);
    
    // Try to start if no active animation for this entity
    this.processQueue(entityId);
    
    return id;
  },
  
  /**
   * Process animation queue for an entity
   */
  processQueue(entityId: string): void {
    // Check if entity has active animation
    if (animationStore.activeAnimations[entityId]) {
      return; // Already animating
    }
    
    // Find next animation for this entity
    const nextIndex = animationStore.animationQueue.findIndex(
      anim => anim.entityId === entityId
    );
    
    if (nextIndex === -1) return; // No animations queued
    
    // Remove from queue and start
    const [animation] = animationStore.animationQueue.splice(nextIndex, 1);
    this.startAnimation(animation);
  },
  
  /**
   * Start an animation
   */
  startAnimation(animation: AnimationEvent): void {
    animation.status = AnimationStatus.PLAYING;
    animation.startTime = Date.now();
    
    animationStore.activeAnimations[animation.entityId] = animation;
    
    animationEventBus.emit(AnimationLifecycleEvents.ANIMATION_STARTED, animation);
    
    // Emit specific event based on type
    if (animation.type.startsWith('Attack')) {
      animationEventBus.emit(AnimationLifecycleEvents.ATTACK_STARTED, animation);
    } else if (animation.type === AnimationState.WALK || animation.type === AnimationState.RUN) {
      animationEventBus.emit(AnimationLifecycleEvents.MOVEMENT_STARTED, animation);
    } else if (animation.type === AnimationState.TAKE_DAMAGE) {
      animationEventBus.emit(AnimationLifecycleEvents.DAMAGE_STARTED, animation);
    }
  },
  
  /**
   * Update animation progress (called from render loop)
   */
  updateAnimationProgress(entityId: string, deltaTime: number): void {
    const animation = animationStore.activeAnimations[entityId];
    if (!animation || animation.status !== AnimationStatus.PLAYING) return;
    
    const elapsed = Date.now() - animation.startTime;
    const progress = Math.min(elapsed / animation.duration, 1.0);
    
    animation.progress = progress;
    
    // Emit progress event
    animationEventBus.emit(AnimationLifecycleEvents.ANIMATION_PROGRESS, {
      animation,
      deltaTime
    });
    
    // Check for completion
    if (progress >= 1.0) {
      this.completeAnimation(entityId);
    }
  },
  
  /**
   * Complete an animation
   */
  completeAnimation(entityId: string): void {
    const animation = animationStore.activeAnimations[entityId];
    if (!animation) return;
    
    animation.status = AnimationStatus.COMPLETED;
    animation.progress = 1.0;
    
    // Move to history
    delete animationStore.activeAnimations[entityId];
    this.addToHistory(animation);
    
    // Emit completion events
    animationEventBus.emit(AnimationLifecycleEvents.ANIMATION_COMPLETED, animation);
    
    // Emit specific completion event
    if (animation.type.startsWith('Attack')) {
      animationEventBus.emit(AnimationLifecycleEvents.ATTACK_COMPLETED, animation);
    } else if (animation.type === AnimationState.WALK || animation.type === AnimationState.RUN) {
      animationEventBus.emit(AnimationLifecycleEvents.MOVEMENT_COMPLETED, animation);
    } else if (animation.type === AnimationState.TAKE_DAMAGE) {
      animationEventBus.emit(AnimationLifecycleEvents.DAMAGE_COMPLETED, animation);
    }
    
    // Process next in queue
    this.processQueue(entityId);
  },
  
  /**
   * Adopt an orphan animation when server responds
   */
  adoptAnimation(animationId: string, serverEventId: string, serverData?: any): void {
    // Check active animations
    let animation: AnimationEvent | undefined;
    
    for (const anim of Object.values(animationStore.activeAnimations)) {
      if (anim.id === animationId) {
        animation = anim;
        break;
      }
    }
    
    // Check queue if not active
    if (!animation) {
      animation = animationStore.animationQueue.find(a => a.id === animationId);
    }
    
    if (!animation) return;
    
    // Update animation
    animation.status = AnimationStatus.ADOPTED;
    animation.serverEventId = serverEventId;
    
    // Merge server data
    if (serverData) {
      animation.data = { ...animation.data, ...serverData };
    }
    
    animationEventBus.emit(AnimationLifecycleEvents.ANIMATION_ADOPTED, animation);
  },
  
  /**
   * Reject an orphan animation
   */
  rejectAnimation(animationId: string): void {
    // Find and cancel the animation
    for (const [entityId, anim] of Object.entries(animationStore.activeAnimations)) {
      if (anim.id === animationId) {
        this.cancelAnimation(entityId);
        return;
      }
    }
  },
  
  /**
   * Cancel an active animation
   */
  cancelAnimation(entityId: string): void {
    const animation = animationStore.activeAnimations[entityId];
    if (!animation) return;
    
    animation.status = AnimationStatus.CANCELLED;
    
    delete animationStore.activeAnimations[entityId];
    this.addToHistory(animation);
    
    animationEventBus.emit(AnimationLifecycleEvents.ANIMATION_CANCELLED, animation);
    
    // Process next in queue
    this.processQueue(entityId);
  },
  
  /**
   * Add to history with size limit
   */
  addToHistory(animation: AnimationEvent): void {
    animationStore.animationHistory.unshift(animation);
    
    // Trim history
    if (animationStore.animationHistory.length > animationStore.config.maxHistorySize) {
      animationStore.animationHistory.pop();
    }
  },
  
  /**
   * Get active animation for entity
   */
  getActiveAnimation(entityId: string): AnimationEvent | undefined {
    return animationStore.activeAnimations[entityId];
  },
  
  /**
   * Clear all animations
   */
  clearAll(): void {
    animationStore.activeAnimations = {};
    animationStore.animationQueue = [];
  }
};

// Export store and actions
export { animationStore };

// Re-export for convenience
export { animationEventBus } from '../game/animation/AnimationEventBus';
export { AnimationLifecycleEvents } from '../types/animation_types'; 