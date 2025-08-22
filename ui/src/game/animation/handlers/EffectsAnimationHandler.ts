import { animationEventBus, AnimationLifecycleEvents } from '../../../store/animationStore';
import { battlemapStore, battlemapActions } from '../../../store/battlemapStore';
import { Direction, EffectType, EffectCategory, BloodSplatConfig, BloodSplatSettings } from '../../../types/battlemap_types';
import { isDefenderShowingFront, computeDirection, getOppositeDirection } from '../../../utils/combatUtils';

/**
 * Handles all visual effects animation events and logic
 * Extracted from IsometricEntityRenderer blood splat and effects logic
 */
export class EffectsAnimationHandler {
  private unsubscribers: Array<() => void> = [];
  
  initialize(): void {
    console.log('[EffectsAnimationHandler] Initializing effects animation handler');
    this.setupEventListeners();
  }
  
  private setupEventListeners(): void {
    // Listen for effect trigger events
    const unsubEffectTrigger = animationEventBus.on(
      AnimationLifecycleEvents.EFFECT_TRIGGERED,
      this.handleEffectTrigger.bind(this)
    );
    this.unsubscribers.push(unsubEffectTrigger);
  }
  
  /**
   * Handle effect trigger events
   */
  private handleEffectTrigger(data: any): void {
    const { type } = data;
    
    switch (type) {
      case 'blood_splat':
        this.createBloodSplatEffects(
          data.targetPosition,
          data.attackerPosition,
          data.metadata
        );
        break;
      
      case 'sparks':
        this.createSparksEffect(data.position);
        break;
      
      case 'smoke':
        this.createSmokeEffect(data.position, data.smokeType || EffectType.SMOKE_SIMPLE_1);
        break;
      
      case 'dodge_movement':
        // Handle dodge movement phases - this would coordinate with movement system
        console.log('[EffectsAnimationHandler] Dodge movement requested:', data);
        break;
      
      default:
        console.warn('[EffectsAnimationHandler] Unknown effect type:', type);
    }
  }
  
  /**
   * Create blood splat effects using the complex multi-stage system
   * Extracted from IsometricEntityRenderer blood splat logic
   */
  private createBloodSplatEffects(
    targetPosition: readonly [number, number], 
    attackerPosition: readonly [number, number], 
    config: any
  ): void {
    const bloodSplatConfig = battlemapStore.controls.bloodSplatConfig;
    
    // Early exit if both blood effects are disabled
    if (!bloodSplatConfig.towardAttacker.enabled && !bloodSplatConfig.awayFromAttacker.enabled) {
      console.log('[EffectsAnimationHandler] Both blood splat directions disabled - skipping blood effects');
      return;
    }

    console.log('[EffectsAnimationHandler] Creating blood splat effects');

    // Determine if defender shows front or back for conditional offsets
    const defenderShowsFront = isDefenderShowingFront(attackerPosition, targetPosition);

    // Calculate direction FROM attacker TO target (this is the impact direction)
    const impactDirection = computeDirection(attackerPosition, targetPosition);

    // Get the "away from attacker" direction vector (opposite of impact)
    const awayDirection = getOppositeDirection(impactDirection);

    // Direction vectors for each of the 8 directions in GRID SPACE
    const gridDirectionVectors = {
      [Direction.N]:  { x:  0, y: -1 }, // North = negative Y
      [Direction.NE]: { x:  1, y: -1 }, // Northeast
      [Direction.E]:  { x:  1, y:  0 }, // East = positive X
      [Direction.SE]: { x:  1, y:  1 }, // Southeast
      [Direction.S]:  { x:  0, y:  1 }, // South = positive Y
      [Direction.SW]: { x: -1, y:  1 }, // Southwest
      [Direction.W]:  { x: -1, y:  0 }, // West = negative X
      [Direction.NW]: { x: -1, y: -1 }  // Northwest
    };

    // Get direction vectors
    const awayVector = gridDirectionVectors[awayDirection];
    const impactVector = gridDirectionVectors[impactDirection]; // Direction FROM attacker TO target

    console.log(`[EffectsAnimationHandler] Blood spray setup: impact=${impactDirection}, away=${awayDirection}, defender shows ${defenderShowsFront ? 'FRONT' : 'BACK'}`);

    // Create blood splats for each enabled direction
    // Correct direction assignments and layering
    const awayBloodLayer = defenderShowsFront ? 'below' : 'above';
    const towardBloodLayer = defenderShowsFront ? 'above' : 'below'; // Opposite of away blood

    this.createBloodSplatsForDirection(
      'towardAttacker', 
      bloodSplatConfig.towardAttacker, 
      awayVector, 
      towardBloodLayer,
      targetPosition,
      attackerPosition,
      defenderShowsFront
    );
    
    this.createBloodSplatsForDirection(
      'awayFromAttacker', 
      bloodSplatConfig.awayFromAttacker, 
      impactVector, 
      awayBloodLayer,
      targetPosition,
      attackerPosition,
      defenderShowsFront
    );
  }
  
  /**
   * Create blood splats for a specific direction
   */
  private createBloodSplatsForDirection(
    direction: string,
    settings: any,
    directionVector: { x: number; y: number },
    layerHint: 'below' | 'above',
    targetPosition: readonly [number, number],
    attackerPosition: readonly [number, number],
    defenderShowsFront: boolean
  ): void {
    if (!settings.enabled) return;

    // Apply conditional offsets based on camera perspective
    const conditionalUpDownOffset = defenderShowsFront 
      ? settings.frontFacingUpDownOffset 
      : settings.backFacingUpDownOffset;
    const conditionalForwardBackwardOffset = defenderShowsFront 
      ? settings.frontFacingForwardBackwardOffset 
      : settings.backFacingForwardBackwardOffset;

    // Blood base position is ALWAYS the diamond center (target position)
    const basePosition = {
      x: targetPosition[0],
      y: targetPosition[1]
    };

    // Apply up/down offset in SCREEN SPACE (not grid space)
    const totalUpDownOffset = settings.upDownOffset + conditionalUpDownOffset;
    if (Math.abs(totalUpDownOffset) > 0.001) {
      // In isometric view:
      // Screen UP = Map NE direction = (-1, -1) in grid coordinates
      // Screen DOWN = Map SW direction = (+1, +1) in grid coordinates
      // Positive upDownOffset = screen up = move NE in grid space
      basePosition.x -= totalUpDownOffset; // Screen up (+) = grid west (-)
      basePosition.y -= totalUpDownOffset; // Screen up (+) = grid north (-)
    }

    // Apply forward/backward offset if user explicitly sets it
    const forwardBackwardTotal = settings.forwardBackwardOffset + conditionalForwardBackwardOffset;
    if (Math.abs(forwardBackwardTotal) > 0.001) {
      // Apply offset in the direction vector (which is constant for this attack)
      basePosition.x += directionVector.x * forwardBackwardTotal;
      basePosition.y += directionVector.y * forwardBackwardTotal;
    }

    console.log(`[EffectsAnimationHandler] Creating ${direction} blood: ${settings.dropletsPerStage.reduce((sum: number, count: number) => sum + count, 0)} droplets, layer: ${layerHint}`);
    console.log(`[EffectsAnimationHandler] Target position: (${targetPosition[0]}, ${targetPosition[1]})`);
    console.log(`[EffectsAnimationHandler] Blood base position: (${basePosition.x}, ${basePosition.y})`);
    console.log(`[EffectsAnimationHandler] Settings: upDown=${settings.upDownOffset}, forwardBack=${settings.forwardBackwardOffset}, randomness=${settings.sprayRandomness}`);

    // Multi-stage expanding spray pattern using store settings
    settings.dropletsPerStage.forEach((dropletCount: number, stageIndex: number) => {
      const stageDelay = stageIndex * settings.stageDelayMs;
      const stageDistance = (settings.maxTravelDistance / settings.stageCount) * (stageIndex + 1); // Progressive distance
      const spreadFactor = 1 + (stageIndex * (settings.spreadMultiplier - 1) / (settings.stageCount - 1)); // Progressive spread

      this.createBloodStage(
        stageIndex, 
        dropletCount, 
        stageDelay, 
        stageDistance, 
        spreadFactor,
        basePosition,
        directionVector,
        settings,
        layerHint,
        attackerPosition,
        targetPosition,
        direction
      );
    });
  }
  
  /**
   * Create a blood stage with multiple droplets
   */
  private createBloodStage(
    stageIndex: number,
    stageDroplets: number,
    stageDelay: number,
    stageDistance: number,
    spreadFactor: number,
    basePosition: { x: number; y: number },
    directionVector: { x: number; y: number },
    settings: any,
    layerHint: 'below' | 'above',
    attackerPosition: readonly [number, number],
    targetPosition: readonly [number, number],
    direction: string
  ): void {
    for (let i = 0; i < stageDroplets; i++) {
      // Start position is ALWAYS exact - no randomness applied to start
      const startPosition = {
        x: basePosition.x,
        y: basePosition.y
      };

      console.log(`[EffectsAnimationHandler] Blood droplet ${i}: target=(${targetPosition[0]}, ${targetPosition[1]}), base=(${basePosition.x}, ${basePosition.y}), start=(${startPosition.x}, ${startPosition.y})`);

      // Calculate end position using spray intensity and direction
      const sprayDistance = stageDistance * settings.sprayIntensity;

      // Randomness only applies to END position and only PERPENDICULAR to spray direction
      const perpX = -directionVector.y; // Perpendicular X
      const perpY = directionVector.x;  // Perpendicular Y

      // Apply randomness only perpendicular to spray direction (never against it)
      const perpRandomness = settings.sprayRandomness > 0.001 ? ((Math.random() - 0.5) * 0.6 * spreadFactor) : 0;
      const perpOffsetX = perpX * perpRandomness;
      const perpOffsetY = perpY * perpRandomness;

      // Calculate final end position in GRID SPACE
      const endX = startPosition.x + (directionVector.x * sprayDistance) + perpOffsetX;
      const endY = startPosition.y + (directionVector.y * sprayDistance) + perpOffsetY;

      // Frame delay using store settings
      const frameDelay = settings.dropletDelayMs + Math.floor(Math.random() * (settings.dropletDelayMs * 0.5)); // Base + up to 50% variation

      const bloodSplatEffectId = `blood_splat_${direction}_${Date.now()}_s${stageIndex}_${i}_${Math.random().toString(36).substr(2, 9)}`;
      const bloodSplatEffect = {
        effectId: bloodSplatEffectId,
        effectType: EffectType.BLOOD_SPLAT,
        category: EffectCategory.TEMPORARY,
        position: startPosition,
        startTime: Date.now() + stageDelay + (i * frameDelay), // Stage delay + frame delay
        duration: 700 + Math.random() * 400, // 0.7-1.1 seconds
        scale: (0.7 + Math.random() * 0.8) * settings.scale, // Use store scale setting
        alpha: (0.7 + Math.random() * 0.3) * settings.alpha, // Use store alpha setting
        // Store end position for movement animation
        offsetX: endX - startPosition.x,
        offsetY: endY - startPosition.y,
        // Add attacker and defender positions for isometric layer determination
        attackerPosition: attackerPosition as readonly [number, number],
        defenderPosition: targetPosition as readonly [number, number],
        // Add layer hint for proper rendering order
        layerHint: layerHint,
        triggerCallback: (direction === 'awayFromAttacker' && stageIndex === 0 && i === 0) ? () => {
          console.log(`[EffectsAnimationHandler] Blood splat effects completed`);
        } : undefined // Only log on first droplet of main direction
      };

      battlemapActions.startEffect(bloodSplatEffect);
    }
  }
  
  /**
   * Create sparks effect
   */
  private createSparksEffect(position: readonly [number, number]): void {
    const sparksEffectId = `sparks_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const sparksEffect = {
      effectId: sparksEffectId,
      effectType: EffectType.SPARKS,
      category: EffectCategory.TEMPORARY,
      position: { x: position[0], y: position[1] },
      startTime: Date.now(),
      duration: 600, // 0.6 seconds
      scale: 1.0,
      alpha: 0.9
    };

    battlemapActions.startEffect(sparksEffect);
    console.log(`[EffectsAnimationHandler] Created sparks effect at (${position[0]}, ${position[1]})`);
  }
  
  /**
   * Create smoke effect
   */
  private createSmokeEffect(position: readonly [number, number], smokeType: EffectType): void {
    const smokeEffectId = `smoke_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const smokeEffect = {
      effectId: smokeEffectId,
      effectType: smokeType,
      category: EffectCategory.TEMPORARY,
      position: { x: position[0], y: position[1] },
      startTime: Date.now(),
      duration: 1000, // 1 second
      scale: 1.2,
      alpha: 0.8
    };

    battlemapActions.startEffect(smokeEffect);
    console.log(`[EffectsAnimationHandler] Created ${smokeType} effect at (${position[0]}, ${position[1]})`);
  }
  
  destroy(): void {
    console.log('[EffectsAnimationHandler] Destroying');
    this.unsubscribers.forEach(unsub => unsub());
    this.unsubscribers = [];
  }
}

export const effectsAnimationHandler = new EffectsAnimationHandler(); 