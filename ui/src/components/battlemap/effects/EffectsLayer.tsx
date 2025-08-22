import React from 'react';
import { useEffects } from '../../../hooks/battlemap';
import AttackEffect from './AttackEffect';

/**
 * Layer for rendering visual effects (attacks, spells, etc.)
 */
const EffectsLayer: React.FC = () => {
  const { attackEffect, clearAttackEffect } = useEffects();
  
  if (!attackEffect) return null;
  
  return (
    <div 
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none'
      }}
    >
      <AttackEffect
        {...attackEffect}
        onComplete={clearAttackEffect}
      />
    </div>
  );
};

export default EffectsLayer; 