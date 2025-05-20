import React, { useEffect, useState } from 'react';
import { Assets, Texture, Rectangle } from 'pixi.js';
import { useTick } from '@pixi/react';
import { AttackEffectProps } from '../../../hooks/battlemap/useEffects';

// Cache for attack effect textures
const textureCache: Record<string, Texture> = {};

interface AnimationFrame {
  x: number;
  y: number;
  w: number;
  h: number;
  duration: number;
}

interface FrameData {
  frames: AnimationFrame[];
  totalDuration: number;
}

const AttackEffect: React.FC<AttackEffectProps & { onComplete: () => void }> = ({ 
  x, 
  y, 
  scale, 
  angle = 0, 
  flipX = false,
  isHit,
  onComplete
}) => {
  const [currentFrame, setCurrentFrame] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [frameData, setFrameData] = useState<FrameData | null>(null);
  const [texture, setTexture] = useState<Texture | null>(null);

  // Load animation data
  useEffect(() => {
    const loadAnimationData = async () => {
      try {
        const hitOrMiss = isHit ? 'hit' : 'miss';
        const assetPath = `/assets/effects/attack_${hitOrMiss}.png`;
        const jsonPath = `/assets/effects/attack_${hitOrMiss}.json`;
        
        // Check if we already have the texture in cache
        if (textureCache[assetPath]) {
          setTexture(textureCache[assetPath]);
        } else {
          // Load the spritesheet
          const loadedTexture = await Assets.load(assetPath);
          textureCache[assetPath] = loadedTexture;
          setTexture(loadedTexture);
        }
        
        // Load the animation data
        const response = await fetch(jsonPath);
        const data = await response.json();
        
        // Process the frame data
        const frames = data.frames.map((frame: any) => ({
          x: frame.frame.x,
          y: frame.frame.y,
          w: frame.frame.w,
          h: frame.frame.h,
          duration: frame.duration
        }));
        
        // Calculate total duration
        const totalDuration = frames.reduce((sum: number, frame: AnimationFrame) => sum + frame.duration, 0);
        
        setFrameData({ frames, totalDuration });
      } catch (err) {
        console.error('Error loading attack effect:', err);
      }
    };
    
    loadAnimationData();
  }, [isHit]);

  // Animation loop - using the same pattern as in AttackEventAnimation
  useTick(() => {
    if (!frameData || !texture) return;
    
    // Increment elapsed time based on a fixed delta
    const frameDelta = 1; // Fixed delta time increment
    const newElapsed = elapsed + (frameDelta * 16.67);
    
    if (newElapsed >= frameData.frames[currentFrame].duration) {
      // Move to next frame
      const nextFrame = currentFrame + 1;
      
      if (nextFrame >= frameData.frames.length) {
        // Animation completed
        onComplete();
        return;
      }
      
      setCurrentFrame(nextFrame);
      setElapsed(0);
    } else {
      setElapsed(newElapsed);
    }
  });

  // No rendering until resources are loaded
  if (!frameData || !texture) return null;

  // Get current frame data
  const frame = frameData.frames[currentFrame];
  
  // Create a texture for the current frame
  const frameTexture = new Texture({
    source: texture.baseTexture,
    frame: new Rectangle(frame.x, frame.y, frame.w, frame.h)
  });

  return (
    <pixiContainer x={x} y={y} rotation={angle}>
      <pixiSprite
        texture={frameTexture}
        anchor={0.5}
        scale={{ x: flipX ? -scale : scale, y: scale }}
      />
    </pixiContainer>
  );
};

export default AttackEffect; 