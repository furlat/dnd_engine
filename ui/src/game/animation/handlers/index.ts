// Animation handlers for different types of animations and effects
// Each handler follows LOCAL STATE architecture:
// - Read initial data from stores (read-only)
// - Maintain local state during execution  
// - Only sync back to animation store at completion/transition points

export { CombatAnimationHandler } from './CombatAnimationHandler';
export { EffectsAnimationHandler } from './EffectsAnimationHandler';
export { SoundAnimationHandler } from './SoundAnimationHandler'; 