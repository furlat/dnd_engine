import { animationEventBus, AnimationLifecycleEvents } from '../../../store/animationStore';
import { battlemapStore, battlemapActions } from '../../../store/battlemapStore';
import { soundActions } from '../../../store/soundStore';
import { Direction, AnimationState } from '../../../types/battlemap_types';
import { AttackAnimationEvent, DamageAnimationEvent } from '../../../types/animation_types';
// NEW: Import centralized combat utilities
import { getAdjacentPosition, getOppositeDirection, computeDirection } from '../../../utils/combatUtils';

/**
 * Local state for dodge animations to prevent store pollution during execution
 */
interface DodgeAnimationState {
  entityId: string;
  originalPosition: readonly [number, number];
  currentPhase: 'dodging_back' | 'returning' | 'completed';
  originalDirection: Direction;
  startTime: number;
  phaseStartTime: number;
  totalDuration: number;
  backDuration: number;
  returnDuration: number;
}

/**
 * Handles all combat animation events and logic using LOCAL STATE principles
 * - Read initial data from stores
 * - Maintain local state during execution
 * - Only sync back to animation store at completion/transition points
 */
export class CombatAnimationHandler {
  private unsubscribers: Array<() => void> = [];
  
  // LOCAL STATE: Track active dodge animations without polluting stores
  private activeDodgeAnimations: Map<string, DodgeAnimationState> = new Map();
  
  // LOCAL STATE: Track active attack impact data
  private activeAttackImpacts: Map<string, {
    attackerId: string;
    targetId: string;
    metadata: any;
    impactTriggered: boolean;
  }> = new Map();

  initialize(): void {
    console.log('[CombatAnimationHandler] Initializing combat animation handler with LOCAL STATE architecture');
    this.setupEventListeners();
    this.startLocalStateUpdateLoop();
  }

  private setupEventListeners(): void {
    // Listen for attack start events from EntityCombatService
    const unsubAttackStart = animationEventBus.on(
      'ATTACK_STARTED',
      (animation) => this.handleAttackStart(animation)
    );
    this.unsubscribers.push(unsubAttackStart);

    // Listen for attack adoption events from EntityCombatService
    const unsubAttackAdopted = animationEventBus.on(
      'ATTACK_ADOPTED',
      (animation) => this.handleAttackAdopted(animation)
    );
    this.unsubscribers.push(unsubAttackAdopted);

    // Listen for attack rejection events from EntityCombatService
    const unsubAttackRejected = animationEventBus.on(
      'ATTACK_REJECTED',
      (animation) => this.handleAttackRejected(animation)
    );
    this.unsubscribers.push(unsubAttackRejected);

    // Listen for attack impact events (40% frame timing) from renderer
    const unsubAttackImpact = animationEventBus.on(
      AnimationLifecycleEvents.ATTACK_IMPACT_FRAME,
      (animation) => this.handleAttackImpact(animation as AttackAnimationEvent)
    );
    this.unsubscribers.push(unsubAttackImpact);

    // Listen for attack completion events from renderer
    const unsubAttackComplete = animationEventBus.on(
      AnimationLifecycleEvents.ATTACK_COMPLETED,
      (animation) => this.handleAttackComplete(animation as AttackAnimationEvent)
    );
    this.unsubscribers.push(unsubAttackComplete);

    // Listen for damage start events
    const unsubDamageStart = animationEventBus.on(
      AnimationLifecycleEvents.DAMAGE_STARTED,
      (animation) => this.handleDamageStart(animation as DamageAnimationEvent)
    );
    this.unsubscribers.push(unsubDamageStart);
  }

  /**
   * LOCAL STATE UPDATE LOOP: Updates local animation states without touching stores
   */
  private startLocalStateUpdateLoop(): void {
    const updateLocalStates = () => {
      const currentTime = Date.now();
      
      // Update active dodge animations using LOCAL STATE ONLY
      this.activeDodgeAnimations.forEach((dodgeState, entityId) => {
        this.updateDodgeLocalState(dodgeState, currentTime);
      });
      
      // Continue loop
      requestAnimationFrame(updateLocalStates);
    };
    
    requestAnimationFrame(updateLocalStates);
  }

  /**
   * LOCAL STATE: Update dodge animation using only local state
   */
  private updateDodgeLocalState(dodgeState: DodgeAnimationState, currentTime: number): void {
    const phaseElapsed = currentTime - dodgeState.phaseStartTime;
    const entity = battlemapStore.entities.summaries[dodgeState.entityId];
    
    if (!entity) {
      // Entity no longer exists - clean up local state
      this.activeDodgeAnimations.delete(dodgeState.entityId);
      return;
    }

    switch (dodgeState.currentPhase) {
      case 'dodging_back':
        if (phaseElapsed >= dodgeState.backDuration) {
          // PHASE TRANSITION: Start return phase (LOCAL STATE ONLY)
          dodgeState.currentPhase = 'returning';
          dodgeState.phaseStartTime = currentTime;
          console.log(`[CombatAnimationHandler] LOCAL: ${entity.name} entering return phase`);
        } else {
          // UPDATE LOCAL VISUAL POSITION: No store updates during animation
          const progress = phaseElapsed / dodgeState.backDuration;
          const easedProgress = 1 - Math.pow(1 - progress, 3); // Ease-out
          
          // Calculate current position (LOCAL CALCULATION)
          const backwardDirection = getOppositeDirection(dodgeState.originalDirection);
          const backwardPosition = getAdjacentPosition(dodgeState.originalPosition, backwardDirection);
          
          const currentX = dodgeState.originalPosition[0] + (backwardPosition[0] - dodgeState.originalPosition[0]) * easedProgress;
          const currentY = dodgeState.originalPosition[1] + (backwardPosition[1] - dodgeState.originalPosition[1]) * easedProgress;
          
          // ONLY update visual position - no other store pollution
          battlemapActions.updateEntityVisualPosition(dodgeState.entityId, { x: currentX, y: currentY });
        }
        break;

      case 'returning':
        if (phaseElapsed >= dodgeState.returnDuration) {
          // PHASE TRANSITION: Complete dodge (SYNC BACK TO STORES)
          dodgeState.currentPhase = 'completed';
          this.completeDodgeAnimation(dodgeState);
        } else {
          // UPDATE LOCAL VISUAL POSITION: Return to original
          const progress = phaseElapsed / dodgeState.returnDuration;
          const easedProgress = 1 - Math.pow(1 - progress, 3); // Ease-out
          
          const backwardDirection = getOppositeDirection(dodgeState.originalDirection);
          const backwardPosition = getAdjacentPosition(dodgeState.originalPosition, backwardDirection);
          
          const currentX = backwardPosition[0] + (dodgeState.originalPosition[0] - backwardPosition[0]) * easedProgress;
          const currentY = backwardPosition[1] + (dodgeState.originalPosition[1] - backwardPosition[1]) * easedProgress;
          
          // ONLY update visual position - no other store pollution
          battlemapActions.updateEntityVisualPosition(dodgeState.entityId, { x: currentX, y: currentY });
        }
        break;

      case 'completed':
        // Animation completed - cleanup handled by completeDodgeAnimation
        break;
    }
  }

  /**
   * SYNC BACK TO STORES: Complete dodge animation and sync final state
   */
  private completeDodgeAnimation(dodgeState: DodgeAnimationState): void {
    const entity = battlemapStore.entities.summaries[dodgeState.entityId];
    if (!entity) return;

    console.log(`[CombatAnimationHandler] SYNC: Completing dodge for ${entity.name} - syncing back to stores`);

    // SYNC: Update animation store with final state for next animation to read
    battlemapActions.setEntityAnimation(dodgeState.entityId, AnimationState.IDLE);
    
    // SYNC: Force position sync to server position (not visual position)
    battlemapActions.resyncEntityPosition(dodgeState.entityId);
    
    // SYNC: Update direction back to store
    battlemapActions.setEntityDirectionFromMapping(dodgeState.entityId, dodgeState.originalDirection);

    // VISUAL: Clear z-order override (return to normal layering)
    battlemapActions.clearEntityZOrder(dodgeState.entityId);
    console.log(`[CombatAnimationHandler] Cleared z-order for ${entity.name} - returned to normal layering`);

    // CLEANUP: Remove from local state
    this.activeDodgeAnimations.delete(dodgeState.entityId);
    
    // COORDINATION: Emit completion event for other systems
    animationEventBus.emit(AnimationLifecycleEvents.ANIMATION_COMPLETED, {
      id: `dodge_${dodgeState.entityId}_${Date.now()}`,
      entityId: dodgeState.entityId,
      type: 'dodge' as any,
      status: 'completed' as any,
      startTime: dodgeState.startTime,
      duration: Date.now() - dodgeState.startTime,
      progress: 1.0,
      clientInitiated: false,
      data: { originalPosition: dodgeState.originalPosition }
    });
  }

  private handleAttackStart(animation: any): void {
    console.log('[CombatAnimationHandler] Attack animation started:', animation);
    
    // READ: Get initial data from stores (read-only)
    const attacker = battlemapStore.entities.summaries[animation.entityId];
    if (!attacker) return;

    // COORDINATE: Trigger sound via sound handler
    // No local state needed - just coordination
    console.log(`[CombatAnimationHandler] Attack started by ${attacker.name}`);
  }

  private handleAttackAdopted(animation: any): void {
    console.log('[CombatAnimationHandler] Attack adopted by server:', animation);
    
    const { entityId, targetId, attackResponse, adoptionTime } = animation;
    const attacker = battlemapStore.entities.summaries[entityId];
    
    if (!attacker) return;

    console.log(`[CombatAnimationHandler] Server processed attack from ${attacker.name}: ${attackResponse.metadata.attack_outcome}`);
    
    // The attack metadata is already updated in the store by EntityCombatService
    // Just log the adoption - combat logic will happen on impact frame
  }

  private handleAttackRejected(animation: any): void {
    console.log('[CombatAnimationHandler] Attack rejected by server:', animation);
    
    const { entityId, targetId, error, rejectionTime } = animation;
    const attacker = battlemapStore.entities.summaries[entityId];
    
    if (!attacker) return;

    console.log(`[CombatAnimationHandler] Server rejected attack from ${attacker.name}: ${error}`);
    
    // The attack is already completed/cancelled by EntityCombatService
    // Just log the rejection
  }

  private handleAttackImpact(animation: any): void {
    console.log('[CombatAnimationHandler] Attack impact detected:', animation);
    
    // READ: Get current attack data from battlemap store
    const attackAnimation = battlemapStore.entities.attackAnimations[animation.entityId];
    if (!attackAnimation?.metadata) {
      console.warn('[CombatAnimationHandler] No attack metadata found for impact');
      return;
    }

    // PREVENT DUPLICATE: Check if already processed
    const impactKey = `${animation.entityId}_${attackAnimation.targetId}`;
    if (this.activeAttackImpacts.has(impactKey)) {
      console.log('[CombatAnimationHandler] Impact already processed, skipping');
      return;
    }

    // LOCAL STATE: Track this impact
    this.activeAttackImpacts.set(impactKey, {
      attackerId: animation.entityId,
      targetId: attackAnimation.targetId,
      metadata: attackAnimation.metadata,
      impactTriggered: true
    });

    const isHit = attackAnimation.metadata.attack_outcome === 'Hit' || 
                 attackAnimation.metadata.attack_outcome === 'Crit';

    if (isHit) {
      this.handleSuccessfulAttack(animation.entityId, attackAnimation.targetId, animation, attackAnimation.metadata);
    } else {
      this.handleMissedAttack(animation.entityId, attackAnimation.targetId, animation);
    }
  }

  private handleSuccessfulAttack(
    attackerId: string, 
    targetId: string, 
    animation: AttackAnimationEvent, 
    metadata: any
  ): void {
    // READ: Get entities from store (read-only)
    const attacker = battlemapStore.entities.summaries[attackerId];
    const target = battlemapStore.entities.summaries[targetId];
    
    if (!attacker || !target) return;

    console.log(`[CombatAnimationHandler] Successful attack: ${attacker.name} hits ${target.name}`);

    // COORDINATE: Trigger damage animation (sync to animation store)
    battlemapActions.setEntityAnimation(targetId, AnimationState.TAKE_DAMAGE);
    
    // COORDINATE: Face target toward attacker (sync direction)
    const targetDirection = computeDirection(target.position, attacker.position);
    battlemapActions.setEntityDirectionFromMapping(targetId, targetDirection);

    // COORDINATE: Trigger sound
    soundActions.playAttackSound(metadata.attack_outcome as 'Hit' | 'Crit');

    // COORDINATE: Trigger effects handler via event system
    animationEventBus.emit(AnimationLifecycleEvents.EFFECT_TRIGGERED, {
      type: 'blood_splat',
      attackerId: attackerId,
      targetId: targetId,
      attackerPosition: attacker.position,
      targetPosition: target.position,
      metadata: metadata
    });
  }

  private handleMissedAttack(attackerId: string, targetId: string, animation: AttackAnimationEvent): void {
    // READ: Get entities from store (read-only)
    const attacker = battlemapStore.entities.summaries[attackerId];
    const target = battlemapStore.entities.summaries[targetId];
    
    if (!attacker || !target) return;

    console.log(`[CombatAnimationHandler] Missed attack: ${attacker.name} misses ${target.name} - starting LOCAL dodge`);

    // COORDINATE: Play miss sound
    soundActions.playAttackSound('Miss');

    // LOCAL STATE: Start dodge animation using local state only
    this.startLocalDodgeAnimation(targetId, attackerId, animation);
  }

  /**
   * LOCAL STATE: Start dodge animation with local state management
   * FIXED: Use frame-based timing like the original renderer
   */
  private startLocalDodgeAnimation(targetId: string, attackerId: string, animation: any): void {
    // READ: Get initial data from stores (read-only)
    const target = battlemapStore.entities.summaries[targetId];
    const attacker = battlemapStore.entities.summaries[attackerId];
    
    if (!target || !attacker) return;

    // Calculate direction from target to attacker
    const targetDirection = computeDirection(
      target.position as readonly [number, number], 
      attacker.position as readonly [number, number]
    );

    // Use RUN_BACKWARDS for clean, consistent dodge animation
    const selectedDodgeAnimation = AnimationState.RUN_BACKWARDS;

    console.log(`[CombatAnimationHandler] Starting ${selectedDodgeAnimation} dodge for ${target.name}`);

    // CRITICAL: Must calculate timing based on remaining attack animation frame progress
    let remainingTime = 500; // Default fallback (0.5 seconds)

    // COORDINATE: Set dodge animation in store for visual feedback
    battlemapActions.setEntityAnimation(targetId, selectedDodgeAnimation);
    
    // COORDINATE: Face target toward attacker
    battlemapActions.setEntityDirectionFromMapping(targetId, targetDirection);

    // VISUAL: Set z-order for dodging entity (above attacker during dodge)
    battlemapActions.setEntityZOrder(targetId, 200); // Higher than attack z-order (150)
    console.log(`[CombatAnimationHandler] Set z-order 200 for dodging entity ${target.name}`);

    // FIXED: Calculate frame-based timing like the original renderer
    // Assume attack animation has standard frame count and speed
    const attackerMapping = battlemapStore.entities.spriteMappings[attackerId];
    
    if (attackerMapping && animation.data?.frameProgress) {
      // Calculate remaining animation time based on frame progress (impact at 40%)
      const frameProgress = animation.data.frameProgress; // Should be 0.4 when dodge starts
      const remainingProgress = 1.0 - frameProgress; // 0.6 remaining
      
      // Use the animation duration from mapping or default to 1 second
      const animationDuration = (attackerMapping.animationDurationSeconds || 1.0) * 1000; // Convert to ms
      remainingTime = Math.floor(animationDuration * remainingProgress);
      
      console.log(`[CombatAnimationHandler] FRAME-BASED: Attack at ${Math.round(frameProgress * 100)}% progress, ${remainingTime}ms remaining in attack`);
    } else {
      console.log(`[CombatAnimationHandler] FALLBACK: Using default timing - no frame data available`);
    }

    // PRECISE: Dodge timing calculated like original
    // Phase 1: Dodge back in 40% of remaining attack time
    // Phase 2: Return in remaining 60%
    const dodgeBackTime = Math.floor(remainingTime * 0.4);
    const returnTime = remainingTime - dodgeBackTime;

    const dodgeState: DodgeAnimationState = {
      entityId: targetId,
      originalPosition: target.position,
      currentPhase: 'dodging_back',
      originalDirection: targetDirection,
      startTime: Date.now(),
      phaseStartTime: Date.now(),
      totalDuration: remainingTime,
      backDuration: dodgeBackTime,
      returnDuration: returnTime
    };

    // STORE IN LOCAL STATE: No store updates during execution
    this.activeDodgeAnimations.set(targetId, dodgeState);

    console.log(`[CombatAnimationHandler] FRAME-BASED: Started dodge for ${target.name} - back:${dodgeBackTime}ms, return:${returnTime}ms, total:${remainingTime}ms`);
  }

  private handleAttackComplete(animation: AttackAnimationEvent): void {
    console.log('[CombatAnimationHandler] Attack animation completed:', animation);
    
    // CLEANUP: Remove impact tracking
    const attackAnimation = battlemapStore.entities.attackAnimations[animation.entityId];
    if (attackAnimation) {
      const impactKey = `${animation.entityId}_${attackAnimation.targetId}`;
      this.activeAttackImpacts.delete(impactKey);
    }

    // SYNC: Complete attack in store for next animation to read
    battlemapActions.completeEntityAttack(animation.entityId);
  }

  private handleDamageStart(animation: DamageAnimationEvent): void {
    console.log('[CombatAnimationHandler] Damage animation started:', animation);
    // Damage animations are handled by their own completion callbacks
    // No additional logic needed here
  }

  destroy(): void {
    console.log('[CombatAnimationHandler] Destroying combat animation handler');
    
    // CLEANUP: All local state
    this.activeDodgeAnimations.clear();
    this.activeAttackImpacts.clear();
    
    // Unsubscribe from events
    this.unsubscribers.forEach(unsubscriber => unsubscriber());
    this.unsubscribers = [];
  }
}

export const combatAnimationHandler = new CombatAnimationHandler(); 