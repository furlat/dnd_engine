import { Ticker } from 'pixi.js';
import { battlemapActions, battlemapStore } from '../store/battlemapStore';

/**
 * MovementController handles smooth camera movement using PixiJS's ticker system
 * This replaces the discrete WASD movement with smooth, frame-based movement
 */
export class MovementController {
  private isActive: boolean = false;
  private keys: Set<string> = new Set();
  private ticker: Ticker | null = null;
  
  // Movement parameters
  private readonly BASE_SPEED = 300; // pixels per second
  private readonly ACCELERATION = 2; // speed multiplier when holding key
  private readonly MAX_SPEED_MULTIPLIER = 3;
  
  // Current movement state
  private velocity: { x: number; y: number } = { x: 0, y: 0 };
  private speedMultiplier: number = 1;
  
  /**
   * Initialize the movement controller
   */
  initialize(ticker: Ticker): void {
    this.ticker = ticker;
    this.setupKeyboardListeners();
    this.setupTickerUpdate();
    console.log('[MovementController] Initialized with PixiJS ticker');
  }
  
  /**
   * Set up keyboard event listeners
   */
  private setupKeyboardListeners(): void {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if modifier keys are pressed or movement is locked
      if (e.ctrlKey || e.altKey || e.metaKey || battlemapStore.controls.isLocked) return;
      
      const key = e.key.toLowerCase();
      if (['w', 'a', 's', 'd'].includes(key)) {
        e.preventDefault();
        
        if (!this.keys.has(key)) {
          this.keys.add(key);
          this.updateMovementState();
        }
      }
    };
    
    const handleKeyUp = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      if (['w', 'a', 's', 'd'].includes(key)) {
        this.keys.delete(key);
        this.updateMovementState();
      }
    };
    
    const handleBlur = () => {
      // Stop all movement when window loses focus
      this.keys.clear();
      this.updateMovementState();
    };
    
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);
    
    // Store cleanup functions
    this.cleanup = () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }
  
  /**
   * Set up ticker-based movement updates
   */
  private setupTickerUpdate(): void {
    if (!this.ticker) return;
    
    this.ticker.add(this.updateMovement, this);
  }
  
  /**
   * Update movement state based on currently pressed keys
   */
  private updateMovementState(): void {
    const wasActive = this.isActive;
    this.isActive = this.keys.size > 0;
    
    // Calculate target velocity based on pressed keys
    let targetVelocityX = 0;
    let targetVelocityY = 0;
    
    if (this.keys.has('a')) targetVelocityX -= 1; // Left
    if (this.keys.has('d')) targetVelocityX += 1; // Right
    if (this.keys.has('w')) targetVelocityY -= 1; // Up
    if (this.keys.has('s')) targetVelocityY += 1; // Down
    
    // Normalize diagonal movement
    if (targetVelocityX !== 0 && targetVelocityY !== 0) {
      const length = Math.sqrt(targetVelocityX * targetVelocityX + targetVelocityY * targetVelocityY);
      targetVelocityX /= length;
      targetVelocityY /= length;
    }
    
    this.velocity.x = targetVelocityX;
    this.velocity.y = targetVelocityY;
    
    // Update store movement state
    if (this.isActive !== wasActive) {
      battlemapActions.setWasdMoving(this.isActive);
    }
    
    // Reset speed multiplier when stopping
    if (!this.isActive) {
      this.speedMultiplier = 1;
    }
  }
  
  /**
   * Update movement every frame (called by ticker)
   */
  private updateMovement = (ticker: Ticker): void => {
    if (!this.isActive || battlemapStore.controls.isLocked) {
      return;
    }
    
    // Increase speed multiplier over time for acceleration
    if (this.keys.size > 0) {
      this.speedMultiplier = Math.min(
        this.speedMultiplier + (this.ACCELERATION * ticker.deltaTime * 0.01),
        this.MAX_SPEED_MULTIPLIER
      );
    }
    
    // Calculate movement delta based on frame time
    const deltaTime = ticker.deltaTime / 60; // Convert to seconds (assuming 60 FPS base)
    const speed = this.BASE_SPEED * this.speedMultiplier;
    
    const deltaX = this.velocity.x * speed * deltaTime;
    const deltaY = this.velocity.y * speed * deltaTime;
    
    // Apply movement if there's any
    if (Math.abs(deltaX) > 0.1 || Math.abs(deltaY) > 0.1) {
      const currentOffset = battlemapStore.view.offset;
      battlemapActions.setOffset(
        currentOffset.x + deltaX,
        currentOffset.y + deltaY
      );
    }
  };
  
  /**
   * Get current movement state
   */
  getMovementState(): { isActive: boolean; velocity: { x: number; y: number }; speed: number } {
    return {
      isActive: this.isActive,
      velocity: { ...this.velocity },
      speed: this.speedMultiplier
    };
  }
  
  /**
   * Force stop all movement
   */
  stop(): void {
    this.keys.clear();
    this.updateMovementState();
  }
  
  /**
   * Cleanup function
   */
  private cleanup: (() => void) | null = null;
  
  /**
   * Destroy the movement controller
   */
  destroy(): void {
    if (this.ticker) {
      this.ticker.remove(this.updateMovement, this);
    }
    
    if (this.cleanup) {
      this.cleanup();
    }
    
    this.keys.clear();
    this.ticker = null;
    this.isActive = false;
  }
} 