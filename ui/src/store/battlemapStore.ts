import { proxy } from 'valtio';
import { TileSummary, EntitySpriteMapping, AnimationState, Direction, SpriteFolderName, MovementState, MovementAnimation, AttackMetadata, VisualPosition, toVisualPosition, isVisualPositionSynced, EffectAnimation, EffectType } from '../types/battlemap_types';
import { EntitySummary, SensesSnapshot } from '../types/common';
import type { DeepReadonly } from '../types/common';
import { fetchGridSnapshot, fetchEntitySummaries } from '../api/battlemap/battlemapApi';
import { TileType } from '../hooks/battlemap';

// Default blood settings constant - single source of truth
const DEFAULT_BLOOD_SETTINGS = {
  enabled: true,
  // Absolute positioning (world-relative)
  heightOffset: 0.25,      // North movement (positive = north, negative = south)
  eastOffset: 0.0,         // East movement (positive = east, negative = west)
  westOffset: 0.0,         // West movement (for UI convenience, combined with eastOffset)
  // Relative positioning (relative to attacker->target line)
  backDistance: 0.0,       // Distance away from attacker (positive = away, negative = toward)
  lateralOffset: 0.0,      // Lateral offset (positive = right of attacker->target line)
  // Directional conditional offsets (when defender shows front vs back)
  frontFacingHeightOffset: 0.15,    // Additional height when defender shows front (NE,E,SE,S,SW attackers)
  frontFacingBackDistance: 0.0,     // Additional back distance when defender shows front
  backFacingHeightOffset: 0.0,      // Additional height when defender shows back (W,NW,N attackers)
  backFacingBackDistance: 0.15,     // Additional back distance when defender shows back
  // Spray direction settings from your image
  sprayNorthAmount: 2.0,   // Away from attacker
  sprayEastAmount: 0.0,    // Toward east
  sprayWestAmount: 0.0,    // Toward west
  spraySouthAmount: 0.0,   // Toward attacker
  stageCount: 5,
  dropletsPerStage: [2, 10, 10, 6, 0], // S1=2, S2=10, S3=10, S4=6, S5=0 (28 total)
  maxTravelDistance: 2.0,  // Max Travel Distance: 2.0
  spreadMultiplier: 3.4,   // Spread Multiplier: 3.4
  stageDelayMs: 10,        // Stage Delay: 10ms
  dropletDelayMs: 10,      // Droplet Delay: 10ms (from screenshot)
  scale: 1.70,             // Scale: 1.70x (from screenshot)
  alpha: 0.85,             // Alpha: 85%
};

// Types for the store
export interface GridState {
  width: number;
  height: number;
  tiles: Record<string, TileSummary>;
}

export interface ViewState {
  tileSize: number;
  offset: { x: number; y: number };
  hoveredCell: { x: number; y: number };
  wasd_moving: boolean;
}

export interface ControlState {
  isLocked: boolean;
  isGridVisible: boolean;
  isVisibilityEnabled: boolean;
  isMovementHighlightEnabled: boolean;
  isMusicPlayerMinimized: boolean;
  isTilesVisible: boolean;
  // Camera mode
  isIsometric: boolean;
  // Tile editor controls
  isEditing: boolean;
  isEditorVisible: boolean;
  selectedTileType: TileType;
  // Blood/gore settings
  isBloodSettingsVisible: boolean;
  bloodSettings: {
    enabled: boolean;
    // Absolute positioning (world-relative)
    heightOffset: number;      // North movement (positive = north, negative = south)
    eastOffset: number;        // East movement (positive = east, negative = west)
    westOffset: number;        // West movement (for UI convenience, combined with eastOffset)
    // Relative positioning (relative to attacker->target line)
    backDistance: number;      // Distance away from attacker (positive = away, negative = toward)
    lateralOffset: number;     // Lateral offset (positive = right of attacker->target line)
    // Directional conditional offsets (when defender shows front vs back)
    frontFacingHeightOffset: number;    // Additional height when defender shows front (NE,E,SE,S,SW attackers)
    frontFacingBackDistance: number;    // Additional back distance when defender shows front
    backFacingHeightOffset: number;     // Additional height when defender shows back (W,NW,N attackers)
    backFacingBackDistance: number;     // Additional back distance when defender shows back
    // Spray direction controls (relative to attacker)
    sprayNorthAmount: number;   // How much to spray toward north (away from attacker)
    sprayEastAmount: number;    // How much to spray toward east
    sprayWestAmount: number;    // How much to spray toward west
    spraySouthAmount: number;   // How much to spray toward south (toward attacker)
    stageCount: number;
    dropletsPerStage: number[];
    maxTravelDistance: number;
    spreadMultiplier: number;
    stageDelayMs: number;
    dropletDelayMs: number;
    scale: number;
    alpha: number;
  };
}

export interface EntityState {
  summaries: Record<string, EntitySummary>;
  selectedEntityId: string | undefined;
  displayedEntityId: string | undefined;
  directions: Record<string, Direction>;
  // Sprite mappings for entities
  spriteMappings: Record<string, EntitySpriteMapping>;
  // Available sprite folders
  availableSpriteFolders: SpriteFolderName[];
  // Movement animations
  movementAnimations: Record<string, MovementAnimation>;
  // NEW: Attack animations with metadata
  attackAnimations: Record<string, { entityId: string; targetId: string; metadata?: AttackMetadata }>;
  // NEW: Path senses data indexed by entity UUID first, then by position
  pathSenses: Record<string, Record<string, SensesSnapshot>>; // observerEntityId -> positionKey -> SensesSnapshot
  // NEW: Z-order overrides for dynamic layering during combat/movement
  zOrderOverrides: Record<string, number>; // entityId -> zIndex (higher = on top)
  // NEW: Permanent effects attached to entities (for debugging/testing)
  permanentEffects: Record<string, EffectType[]>; // entityId -> array of effect types
}

// NEW: Effect system state
export interface EffectState {
  // Active effect animations
  activeEffects: Record<string, EffectAnimation>; // effectId -> EffectAnimation
  // Available effect types for debugging
  availableEffects: EffectType[];
}

export interface BattlemapStoreState {
  grid: GridState;
  view: ViewState;
  controls: ControlState;
  entities: EntityState;
  effects: EffectState;
  loading: boolean;
  error: string | null;
}

// Read-only type for consuming components
export type ReadonlyBattlemapStore = DeepReadonly<BattlemapStoreState>;

// Initialize the store with default values
const battlemapStore = proxy<BattlemapStoreState>({
  grid: {
    width: 30,
    height: 20,
    tiles: {},
  },
  view: {
    tileSize: 128, // 4x the previous default (32 * 4 = 128)
    offset: { x: 0, y: 0 },
    hoveredCell: { x: -1, y: -1 },
    wasd_moving: false,
  },
  controls: {
    isLocked: false,
    isGridVisible: true,
    isVisibilityEnabled: true,
    isMovementHighlightEnabled: false,
    isMusicPlayerMinimized: true,
    isTilesVisible: true,
    // Camera mode defaults
    isIsometric: true, // Default to isometric for testing
    // Tile editor defaults
    isEditing: false,
    isEditorVisible: false,
    selectedTileType: 'floor',
    // Blood/gore settings defaults
    isBloodSettingsVisible: false,
    bloodSettings: { ...DEFAULT_BLOOD_SETTINGS },
  },
  entities: {
    summaries: {},
    selectedEntityId: undefined,
    displayedEntityId: undefined,
    directions: {},
    spriteMappings: {},
    availableSpriteFolders: [],
    movementAnimations: {},
    attackAnimations: {},
    pathSenses: {},
    zOrderOverrides: {},
    permanentEffects: {},
  },
  effects: {
    activeEffects: {},
    availableEffects: Object.values(EffectType),
  },
  loading: false,
  error: null,
});

// Polling configuration
const POLLING_INTERVAL = 200; // Match previous 200ms rate for responsive updates
let pollingInterval: NodeJS.Timeout | null = null;

// Actions to mutate the store
const battlemapActions = {
  // Grid actions
  setGridDimensions: (width: number, height: number) => {
    battlemapStore.grid.width = width;
    battlemapStore.grid.height = height;
  },
  
  setTiles: (tiles: Record<string, TileSummary>) => {
    battlemapStore.grid.tiles = tiles;
  },
  
  // View actions
  setTileSize: (size: number) => {
    console.log('[battlemapStore] setTileSize called:', battlemapStore.view.tileSize, '->', size);
    battlemapStore.view.tileSize = size;
    console.log('[battlemapStore] setTileSize completed, new value:', battlemapStore.view.tileSize);
  },
  
  setOffset: (x: number, y: number) => {
    battlemapStore.view.offset.x = x;
    battlemapStore.view.offset.y = y;
  },
  
  setHoveredCell: (x: number, y: number) => {
    battlemapStore.view.hoveredCell.x = x;
    battlemapStore.view.hoveredCell.y = y;
  },
  
  setWasdMoving: (moving: boolean) => {
    battlemapStore.view.wasd_moving = moving;
  },
  
  // Controls actions
  setLocked: (locked: boolean) => {
    battlemapStore.controls.isLocked = locked;
  },
  
  setGridVisible: (visible: boolean) => {
    battlemapStore.controls.isGridVisible = visible;
  },
  
  setTilesVisible: (visible: boolean) => {
    battlemapStore.controls.isTilesVisible = visible;
  },
  
  setVisibilityEnabled: (enabled: boolean) => {
    battlemapStore.controls.isVisibilityEnabled = enabled;
  },
  
  setMovementHighlightEnabled: (enabled: boolean) => {
    battlemapStore.controls.isMovementHighlightEnabled = enabled;
  },
  
  setMusicPlayerMinimized: (minimized: boolean) => {
    battlemapStore.controls.isMusicPlayerMinimized = minimized;
  },
  
  setIsometric: (isometric: boolean) => {
    battlemapStore.controls.isIsometric = isometric;
  },
  
  // Tile editor actions
  setTileEditing: (editing: boolean) => {
    battlemapStore.controls.isEditing = editing;
    // When disabling editing, also hide the editor panel
    if (!editing) {
      battlemapStore.controls.isEditorVisible = false;
    }
  },
  
  setTileEditorVisible: (visible: boolean) => {
    battlemapStore.controls.isEditorVisible = visible;
  },
  
  setSelectedTileType: (tileType: TileType) => {
    battlemapStore.controls.selectedTileType = tileType;
  },
  
  // Blood/gore settings actions
  setBloodSettingsVisible: (visible: boolean) => {
    battlemapStore.controls.isBloodSettingsVisible = visible;
  },
  
  updateBloodSettings: (settings: Partial<typeof battlemapStore.controls.bloodSettings>) => {
    battlemapStore.controls.bloodSettings = {
      ...battlemapStore.controls.bloodSettings,
      ...settings,
    };
  },
  
  resetBloodSettings: () => {
    battlemapStore.controls.bloodSettings = { ...DEFAULT_BLOOD_SETTINGS };
  },
  
  // Entity actions
  setEntitySummaries: (summaries: Record<string, EntitySummary>) => {
    battlemapStore.entities.summaries = summaries;
  },
  
  setSelectedEntity: (entityId: string | undefined) => {
    // If selecting the currently selected entity, clear the selection
    if (battlemapStore.entities.selectedEntityId === entityId) {
      battlemapStore.entities.selectedEntityId = undefined;
    } else {
      battlemapStore.entities.selectedEntityId = entityId;
    }
  },
  
  setDisplayedEntity: (entityId: string | undefined) => {
    battlemapStore.entities.displayedEntityId = entityId;
  },
  
  setEntityDirection: (entityId: string, direction: Direction) => {
    battlemapStore.entities.directions[entityId] = direction;
  },
  
  // NEW: Sprite mapping actions
  setEntitySpriteMapping: (entityId: string, spriteFolder: string) => {
    const existing = battlemapStore.entities.spriteMappings[entityId];
    const entity = battlemapStore.entities.summaries[entityId];
    battlemapStore.entities.spriteMappings[entityId] = {
      entityId,
      spriteFolder,
      idleAnimation: existing?.idleAnimation || AnimationState.IDLE,
      currentAnimation: existing?.currentAnimation || existing?.idleAnimation || AnimationState.IDLE,
      currentDirection: existing?.currentDirection || Direction.S,
      scale: existing?.scale || 1.0, // Default to 1.0 instead of 0.6
      animationDurationSeconds: existing?.animationDurationSeconds || 1.0, // 1 second default for testing
      movementState: existing?.movementState || MovementState.IDLE,
      visualPosition: existing?.visualPosition || (entity ? toVisualPosition(entity.position) : undefined),
      isPositionSynced: existing?.isPositionSynced ?? true,
    };
  },
  
  setEntityAnimation: (entityId: string, animation: AnimationState) => {
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        currentAnimation: animation,
      };
    }
  },

  setEntityIdleAnimation: (entityId: string, animation: AnimationState) => {
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        idleAnimation: animation,
        // If currently idle, also update current animation
        currentAnimation: mapping.movementState === MovementState.IDLE ? animation : mapping.currentAnimation,
      };
    }
  },
  
  setEntityDirectionFromMapping: (entityId: string, direction: Direction) => {
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        currentDirection: direction,
      };
    }
  },
  
  // NEW: Set sprite scale
  setEntitySpriteScale: (entityId: string, scale: number) => {
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        scale: Math.max(0.1, Math.min(5.0, scale)), // Clamp between 0.1 and 5.0
      };
    }
  },
  
  // NEW: Set animation duration in seconds
  setEntityAnimationDuration: (entityId: string, durationSeconds: number) => {
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        animationDurationSeconds: Math.max(0.1, Math.min(10.0, durationSeconds)), // Clamp between 0.1 and 10 seconds
      };
    }
  },
  
  setAvailableSpriteFolders: (folders: SpriteFolderName[]) => {
    battlemapStore.entities.availableSpriteFolders = folders;
  },
  
  removeEntitySpriteMapping: (entityId: string) => {
    delete battlemapStore.entities.spriteMappings[entityId];
  },

  // Movement animation actions
  startEntityMovement: (entityId: string, movementAnimation: MovementAnimation) => {
    battlemapStore.entities.movementAnimations[entityId] = movementAnimation;
    
    // Update sprite mapping to moving state
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        movementState: MovementState.MOVING,
        currentAnimation: AnimationState.WALK, // Switch to walk animation
        isPositionSynced: false, // Visual position will diverge from server
      };
    }
  },

  // NEW: Store path senses data for an entity
  setEntityPathSenses: (entityId: string, pathSenses: Record<string, SensesSnapshot>) => {
    battlemapStore.entities.pathSenses[entityId] = pathSenses;
    console.log(`[battlemapStore] Stored path senses for entity ${entityId} with ${Object.keys(pathSenses).length} positions`);
  },

  // NEW: Get path senses data for an entity
  getEntityPathSenses: (entityId: string): Record<string, SensesSnapshot> | undefined => {
    return battlemapStore.entities.pathSenses[entityId];
  },

  // NEW: Clear path senses data for an entity
  clearEntityPathSenses: (entityId: string) => {
    delete battlemapStore.entities.pathSenses[entityId];
    console.log(`[battlemapStore] Cleared path senses for entity ${entityId}`);
  },

  updateEntityMovementAnimation: (entityId: string, updates: Partial<MovementAnimation>) => {
    const existing = battlemapStore.entities.movementAnimations[entityId];
    if (existing) {
      battlemapStore.entities.movementAnimations[entityId] = {
        ...existing,
        ...updates,
      };
    }
  },

  updateEntityVisualPosition: (entityId: string, visualPosition: VisualPosition) => {
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      const entity = battlemapStore.entities.summaries[entityId];
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        visualPosition,
        isPositionSynced: entity ? isVisualPositionSynced(visualPosition, entity.position) : false,
      };
    }
  },

  completeEntityMovement: (entityId: string, shouldResync: boolean = true) => {
    // Remove movement animation
    delete battlemapStore.entities.movementAnimations[entityId];
    
    // NEW: Clear path senses data when movement completes
    delete battlemapStore.entities.pathSenses[entityId];
    
    // Update sprite mapping
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      const entity = battlemapStore.entities.summaries[entityId];
      
      if (shouldResync && entity) {
        // If resyncing, snap back to server position and go to idle
        battlemapStore.entities.spriteMappings[entityId] = {
          ...mapping,
          movementState: MovementState.IDLE,
          currentAnimation: mapping.idleAnimation, // Return to idle animation
          visualPosition: toVisualPosition(entity.position),
          isPositionSynced: true,
        };
      } else {
        // If not resyncing (server approved), sync visual position to server position and go to idle
        battlemapStore.entities.spriteMappings[entityId] = {
          ...mapping,
          movementState: MovementState.IDLE,
          currentAnimation: mapping.idleAnimation, // Return to idle animation
          visualPosition: entity ? toVisualPosition(entity.position) : mapping.visualPosition,
          isPositionSynced: true, // Server approved, so we're synced
        };
      }
    }
  },

  // NEW: Attack animation actions
  startEntityAttack: (entityId: string, targetId: string) => {
    battlemapStore.entities.attackAnimations[entityId] = { entityId, targetId };
    
    // Update sprite mapping to attack animation
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        currentAnimation: AnimationState.ATTACK1, // Switch to attack animation
      };
    }
  },

  updateEntityAttackMetadata: (entityId: string, metadata: AttackMetadata) => {
    const existing = battlemapStore.entities.attackAnimations[entityId];
    if (existing) {
      battlemapStore.entities.attackAnimations[entityId] = {
        ...existing,
        metadata,
      };
    }
  },

  completeEntityAttack: (entityId: string) => {
    // Remove attack animation
    delete battlemapStore.entities.attackAnimations[entityId];
    
    // Update sprite mapping back to idle
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    if (mapping) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        currentAnimation: mapping.idleAnimation, // Return to idle animation
      };
    }

    // NOTE: Damage animation on target is now triggered via onFrameChange callback
    // in EntityRenderer for more precise timing during the attack animation
  },

  resyncEntityPosition: (entityId: string) => {
    const mapping = battlemapStore.entities.spriteMappings[entityId];
    const entity = battlemapStore.entities.summaries[entityId];
    if (mapping && entity) {
      battlemapStore.entities.spriteMappings[entityId] = {
        ...mapping,
        movementState: MovementState.IDLE,
        visualPosition: toVisualPosition(entity.position),
        isPositionSynced: true,
      };
    }
  },
  
  // Get the currently selected entity
  getSelectedEntity: (): EntitySummary | undefined => {
    return battlemapStore.entities.selectedEntityId 
      ? battlemapStore.entities.summaries[battlemapStore.entities.selectedEntityId] 
      : undefined;
  },
  
  // Get sprite mapping for entity
  getEntitySpriteMapping: (entityId: string): EntitySpriteMapping | undefined => {
    return battlemapStore.entities.spriteMappings[entityId];
  },
  
  // Loading/error status
  setLoading: (loading: boolean) => {
    battlemapStore.loading = loading;
  },
  
  setError: (error: string | null) => {
    battlemapStore.error = error;
  },
  
  // Fetch grid data
  fetchGridSnapshot: async () => {
    try {
      const gridData = await fetchGridSnapshot();
      battlemapStore.grid.width = gridData.width;
      battlemapStore.grid.height = gridData.height;
      battlemapStore.grid.tiles = gridData.tiles;
      return gridData;
    } catch (err) {
      console.error('Error fetching grid data:', err);
      battlemapActions.setError(err instanceof Error ? err.message : 'Failed to fetch grid data');
      return null;
    }
  },
  
  // Fetch entity summaries
  fetchEntitySummaries: async () => {
    try {
      const summariesData = await fetchEntitySummaries();
      
      // Convert array to record while preserving existing data
      const summariesRecord = summariesData.reduce((acc: Record<string, EntitySummary>, summary: EntitySummary) => {
        // Preserve existing data for smooth transitions
        const existingSummary = battlemapStore.entities.summaries[summary.uuid];
        if (existingSummary) {
          // Only update if data has changed
          if (JSON.stringify(existingSummary) !== JSON.stringify(summary)) {
            acc[summary.uuid] = summary;
          } else {
            acc[summary.uuid] = existingSummary;
          }
        } else {
          acc[summary.uuid] = summary;
        }
        return acc;
      }, {});

      battlemapStore.entities.summaries = summariesRecord;
      return summariesRecord;
    } catch (err) {
      console.error('Error fetching entity summaries:', err);
      return {};
    }
  },
  
  // NEW: Center map on entity position
  centerMapOnEntity: (entityId: string) => {
    const entity = battlemapStore.entities.summaries[entityId];
    if (!entity) return;

    const [entityX, entityY] = entity.position;
    const tileSize = battlemapStore.view.tileSize;
    const gridWidth = battlemapStore.grid.width;
    const gridHeight = battlemapStore.grid.height;

    // Calculate the center offset needed to center the entity on screen
    // We want the entity to be in the center of the visible area
    const ENTITY_PANEL_WIDTH = 250;
    
    // Assume a typical screen size for centering calculation
    // In practice, this will be adjusted by the actual container size
    const assumedScreenWidth = 1200;
    const assumedScreenHeight = 800;
    
    const availableWidth = assumedScreenWidth - ENTITY_PANEL_WIDTH;
    const gridPixelWidth = gridWidth * tileSize;
    const gridPixelHeight = gridHeight * tileSize;
    
    // Calculate where the grid would naturally be positioned (centered)
    const baseOffsetX = ENTITY_PANEL_WIDTH + (availableWidth - gridPixelWidth) / 2;
    const baseOffsetY = (assumedScreenHeight - gridPixelHeight) / 2;
    
    // Calculate where the entity currently is in screen coordinates
    const entityScreenX = baseOffsetX + (entityX * tileSize) + (tileSize / 2);
    const entityScreenY = baseOffsetY + (entityY * tileSize) + (tileSize / 2);
    
    // Calculate where we want the entity to be (center of available area)
    const targetScreenX = ENTITY_PANEL_WIDTH + (availableWidth / 2);
    const targetScreenY = assumedScreenHeight / 2;
    
    // Calculate the offset needed to move the entity to the target position
    const offsetX = targetScreenX - entityScreenX;
    const offsetY = targetScreenY - entityScreenY;
    
    console.log(`[battlemapStore] Centering map on ${entity.name} at (${entityX}, ${entityY}), offset: (${offsetX}, ${offsetY})`);
    
    battlemapStore.view.offset.x = offsetX;
    battlemapStore.view.offset.y = offsetY;
  },
  
  // Start polling for data
  startPolling: () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }

    // Immediately fetch data
    Promise.all([
      battlemapActions.fetchGridSnapshot(),
      battlemapActions.fetchEntitySummaries()
    ]).then(async () => {
      // Select the first entity by default if none is selected
      if (!battlemapStore.entities.selectedEntityId) {
        const entityIds = Object.keys(battlemapStore.entities.summaries);
        if (entityIds.length > 0) {
          const firstEntityId = entityIds[0];
          battlemapStore.entities.selectedEntityId = firstEntityId;
          battlemapStore.entities.displayedEntityId = firstEntityId;
          
          // NEW: Auto-center map on selected entity for debugging
          console.log('[battlemapStore] Auto-centering map on first selected entity for debugging');
          battlemapActions.centerMapOnEntity(firstEntityId);
          
          // NEW: Auto-assign random character sprites to all entities for debugging
          console.log('[battlemapStore] Auto-assigning random character sprites for debugging');
          await battlemapActions.autoAssignRandomCharacters();
        }
      }
    });

    // Set up polling interval
    pollingInterval = setInterval(async () => {
      await Promise.all([
        battlemapActions.fetchEntitySummaries(),
        battlemapActions.fetchGridSnapshot()
      ]);
    }, POLLING_INTERVAL);
  },

  // Stop polling
  stopPolling: () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  },

  // NEW: Z-order management actions
  setEntityZOrder: (entityId: string, zIndex: number) => {
    battlemapStore.entities.zOrderOverrides[entityId] = zIndex;
  },
  
  clearEntityZOrder: (entityId: string) => {
    delete battlemapStore.entities.zOrderOverrides[entityId];
  },
  
  clearAllZOrderOverrides: () => {
    battlemapStore.entities.zOrderOverrides = {};
  },

  // NEW: Effect system actions
  startEffect: (effectAnimation: EffectAnimation) => {
    battlemapStore.effects.activeEffects[effectAnimation.effectId] = effectAnimation;
    console.log(`[battlemapStore] Started effect ${effectAnimation.effectType} at (${effectAnimation.position.x}, ${effectAnimation.position.y})`);
  },

  updateEffect: (effectId: string, updates: Partial<EffectAnimation>) => {
    const existing = battlemapStore.effects.activeEffects[effectId];
    if (existing) {
      battlemapStore.effects.activeEffects[effectId] = {
        ...existing,
        ...updates,
      };
    }
  },

  completeEffect: (effectId: string) => {
    const effect = battlemapStore.effects.activeEffects[effectId];
    if (effect) {
      console.log(`[battlemapStore] Completed effect ${effect.effectType} (${effectId})`);
      
      // Trigger callback if provided
      if (effect.triggerCallback) {
        effect.triggerCallback();
      }
      
      // Remove from active effects
      delete battlemapStore.effects.activeEffects[effectId];
    }
  },

  clearAllEffects: () => {
    battlemapStore.effects.activeEffects = {};
    console.log(`[battlemapStore] Cleared all active effects`);
  },

  // NEW: Permanent effect management for entities (debugging)
  addPermanentEffectToEntity: (entityId: string, effectType: EffectType) => {
    const existing = battlemapStore.entities.permanentEffects[entityId] || [];
    if (!existing.includes(effectType)) {
      battlemapStore.entities.permanentEffects[entityId] = [...existing, effectType];
      console.log(`[battlemapStore] Added permanent effect ${effectType} to entity ${entityId}`);
    }
  },

  removePermanentEffectFromEntity: (entityId: string, effectType: EffectType) => {
    const existing = battlemapStore.entities.permanentEffects[entityId] || [];
    battlemapStore.entities.permanentEffects[entityId] = existing.filter(e => e !== effectType);
    if (battlemapStore.entities.permanentEffects[entityId].length === 0) {
      delete battlemapStore.entities.permanentEffects[entityId];
    }
    console.log(`[battlemapStore] Removed permanent effect ${effectType} from entity ${entityId}`);
  },

  clearAllPermanentEffectsFromEntity: (entityId: string) => {
    delete battlemapStore.entities.permanentEffects[entityId];
    console.log(`[battlemapStore] Cleared all permanent effects from entity ${entityId}`);
  },

  // NEW: Auto-assign random character sprites to all entities (debugging feature)
  autoAssignRandomCharacters: async () => {
    // First, ensure we have sprite folders loaded
    if (battlemapStore.entities.availableSpriteFolders.length === 0) {
      try {
        const { discoverAvailableSpriteFolders } = await import('../api/battlemap/battlemapApi');
        const folders = await discoverAvailableSpriteFolders();
        battlemapStore.entities.availableSpriteFolders = folders;
        console.log(`[battlemapStore] Loaded ${folders.length} sprite folders for auto-assignment`);
      } catch (error) {
        console.error('[battlemapStore] Failed to load sprite folders for auto-assignment:', error);
        return;
      }
    }

    // Filter out zombies but keep monsters
    const availableFolders = battlemapStore.entities.availableSpriteFolders;
    const characterFolders = availableFolders.filter(folder => {
      const lowerFolder = folder.toLowerCase();
      // Exclude zombies but keep everything else (including monsters)
      return !lowerFolder.includes('zombie');
    });

    if (characterFolders.length === 0) {
      console.warn('[battlemapStore] No character folders available for auto-assignment');
      return;
    }

    console.log(`[battlemapStore] Auto-assigning from ${characterFolders.length} character folders:`, characterFolders);

    // Assign random sprites to all entities that don't already have one
    const entities = Object.values(battlemapStore.entities.summaries);
    let assignedCount = 0;

    entities.forEach(entity => {
      // Skip if entity already has a sprite assigned
      if (battlemapStore.entities.spriteMappings[entity.uuid]) {
        console.log(`[battlemapStore] Skipping ${entity.name} - already has sprite assigned`);
        return;
      }

      // Pick a random character folder
      const randomIndex = Math.floor(Math.random() * characterFolders.length);
      const selectedFolder = characterFolders[randomIndex];

      // Assign the sprite
      battlemapActions.setEntitySpriteMapping(entity.uuid, selectedFolder);
      assignedCount++;

      console.log(`[battlemapStore] Auto-assigned ${selectedFolder} to ${entity.name}`);
    });

    console.log(`[battlemapStore] Auto-assigned sprites to ${assignedCount} entities`);
  },

  // Compute direction between two positions
  computeDirection: (fromPos: [number, number], toPos: [number, number]): Direction => {
    const [fromX, fromY] = fromPos;
    const [toX, toY] = toPos;
    
    const dx = toX - fromX;
    const dy = toY - fromY;
    
    if (dx > 0 && dy > 0) return Direction.SE;
    if (dx > 0 && dy < 0) return Direction.NE;
    if (dx < 0 && dy > 0) return Direction.SW;
    if (dx < 0 && dy < 0) return Direction.NW;
    if (dx === 0 && dy > 0) return Direction.S;
    if (dx === 0 && dy < 0) return Direction.N;
    if (dx > 0 && dy === 0) return Direction.E;
    if (dx < 0 && dy === 0) return Direction.W;
    
    return Direction.S; // Default
  },
};

// Export both store and actions
export { battlemapStore, battlemapActions }; 