import { animationEventBus, AnimationLifecycleEvents } from '../../../store/animationStore';
import { soundActions } from '../../../store/soundStore';

/**
 * Handles all sound animation events and coordination
 * Extracted from IsometricEntityRenderer sound trigger logic
 */
export class SoundAnimationHandler {
  private unsubscribers: Array<() => void> = [];
  
  initialize(): void {
    console.log('[SoundAnimationHandler] Initializing sound animation handler');
    this.setupEventListeners();
  }
  
  private setupEventListeners(): void {
    // Listen for sound trigger events
    const unsubSoundTrigger = animationEventBus.on(
      AnimationLifecycleEvents.SOUND_TRIGGERED,
      this.handleSoundTrigger.bind(this)
    );
    this.unsubscribers.push(unsubSoundTrigger);

    // Listen for specific animation events that should trigger sounds
    const unsubAttackStart = animationEventBus.on(
      AnimationLifecycleEvents.ATTACK_STARTED,
      (animation) => {
        // Attack start sound could be added here
        console.log('[SoundAnimationHandler] Attack started - could trigger weapon swing sound');
      }
    );
    this.unsubscribers.push(unsubAttackStart);
  }
  
  /**
   * Handle sound trigger events
   */
  private handleSoundTrigger(data: any): void {
    const { soundType, outcome, volume, delay } = data;
    
    switch (soundType) {
      case 'attack':
        this.playAttackSound(outcome, volume, delay);
        break;
      
      case 'movement':
        this.playMovementSound(data.type, volume, delay);
        break;
        
      case 'damage':
        this.playDamageSound(data.type, volume, delay);
        break;
        
      case 'ambient':
        this.playAmbientSound(data.type, volume, delay);
        break;
        
      default:
        console.warn('[SoundAnimationHandler] Unknown sound type:', soundType);
    }
  }
  
  /**
   * Play attack sound based on outcome
   */
  private playAttackSound(outcome: string, volume?: number, delay?: number): void {
    const playSound = () => {
      switch (outcome) {
        case 'Hit':
          soundActions.playAttackSound('Hit');
          console.log('[SoundAnimationHandler] Playing attack hit sound');
          break;
          
        case 'Crit':
          soundActions.playAttackSound('Crit');
          console.log('[SoundAnimationHandler] Playing attack crit sound');
          break;
          
        case 'Miss':
          soundActions.playAttackSound('Miss');
          console.log('[SoundAnimationHandler] Playing attack miss sound');
          break;
          
        default:
          console.warn('[SoundAnimationHandler] Unknown attack outcome:', outcome);
      }
    };
    
    if (delay && delay > 0) {
      setTimeout(playSound, delay);
    } else {
      playSound();
    }
  }
  
  /**
   * Play movement sound
   */
  private playMovementSound(type: string, volume?: number, delay?: number): void {
    const playSound = () => {
      switch (type) {
        case 'footstep':
          // soundActions.playMovementSound('footstep', volume);
          console.log('[SoundAnimationHandler] Playing footstep sound');
          break;
          
        case 'running':
          // soundActions.playMovementSound('running', volume);
          console.log('[SoundAnimationHandler] Playing running sound');
          break;
          
        case 'dodge':
          // soundActions.playMovementSound('dodge', volume);
          console.log('[SoundAnimationHandler] Playing dodge sound');
          break;
          
        default:
          console.warn('[SoundAnimationHandler] Unknown movement sound type:', type);
      }
    };
    
    if (delay && delay > 0) {
      setTimeout(playSound, delay);
    } else {
      playSound();
    }
  }
  
  /**
   * Play damage sound
   */
  private playDamageSound(type: string, volume?: number, delay?: number): void {
    const playSound = () => {
      switch (type) {
        case 'hit':
          // soundActions.playDamageSound('hit', volume);
          console.log('[SoundAnimationHandler] Playing damage hit sound');
          break;
          
        case 'blocked':
          // soundActions.playDamageSound('blocked', volume);
          console.log('[SoundAnimationHandler] Playing damage blocked sound');
          break;
          
        case 'death':
          // soundActions.playDamageSound('death', volume);
          console.log('[SoundAnimationHandler] Playing death sound');
          break;
          
        default:
          console.warn('[SoundAnimationHandler] Unknown damage sound type:', type);
      }
    };
    
    if (delay && delay > 0) {
      setTimeout(playSound, delay);
    } else {
      playSound();
    }
  }
  
  /**
   * Play ambient sound
   */
  private playAmbientSound(type: string, volume?: number, delay?: number): void {
    const playSound = () => {
      switch (type) {
        case 'wind':
          // soundActions.playAmbientSound('wind', volume);
          console.log('[SoundAnimationHandler] Playing wind ambient sound');
          break;
          
        case 'fire':
          // soundActions.playAmbientSound('fire', volume);
          console.log('[SoundAnimationHandler] Playing fire ambient sound');
          break;
          
        case 'water':
          // soundActions.playAmbientSound('water', volume);
          console.log('[SoundAnimationHandler] Playing water ambient sound');
          break;
          
        default:
          console.warn('[SoundAnimationHandler] Unknown ambient sound type:', type);
      }
    };
    
    if (delay && delay > 0) {
      setTimeout(playSound, delay);
    } else {
      playSound();
    }
  }
  
  destroy(): void {
    console.log('[SoundAnimationHandler] Destroying');
    this.unsubscribers.forEach(unsub => unsub());
    this.unsubscribers = [];
  }
}

export const soundAnimationHandler = new SoundAnimationHandler(); 