import { EntitySummary } from '../../../types/common';
import { EntitySpriteMapping, MovementState } from '../../../types/battlemap_types';

/**
 * Store change detection utilities for efficient memoization
 * Provides reusable patterns for any component that needs to detect store changes
 * without triggering unnecessary re-renders
 */
export class StoreChangeDetectionUtils {
  
  /**
   * Check if entities have actually changed by comparing JSON hashes
   * Prevents unnecessary re-renders when polling creates new objects with same data
   */
  static hasEntitiesChanged(
    currentEntities: Record<string, EntitySummary>,
    lastEntityData: Map<string, string>
  ): { hasChanges: boolean; changedEntityIds: string[] } {
    const changedEntityIds: string[] = [];
    let hasChanges = false;
    
    // Check entity summaries for changes
    for (const [entityId, entity] of Object.entries(currentEntities)) {
      const entityHash = JSON.stringify({
        uuid: entity.uuid,
        name: entity.name,
        position: entity.position,
        // Add other important fields that should trigger re-renders
      });
      
      const lastHash = lastEntityData.get(entityId);
      if (lastHash !== entityHash) {
        lastEntityData.set(entityId, entityHash);
        changedEntityIds.push(entityId);
        hasChanges = true;
      }
    }
    
    // Check for removed entities
    const currentEntityIds = new Set(Object.keys(currentEntities));
    for (const entityId of Array.from(lastEntityData.keys())) {
      if (!currentEntityIds.has(entityId)) {
        lastEntityData.delete(entityId);
        changedEntityIds.push(entityId);
        hasChanges = true;
      }
    }
    
    return { hasChanges, changedEntityIds };
  }
  
  /**
   * Check if sprite mappings have actually changed
   * Excludes direction changes during movement to prevent feedback loops
   */
  static hasSpriteMappingsChanged(
    currentMappings: Record<string, EntitySpriteMapping>,
    lastMappingData: Map<string, string>
  ): { hasChanges: boolean; changedMappingIds: string[] } {
    const changedMappingIds: string[] = [];
    let hasChanges = false;
    
    // Check sprite mappings for changes
    for (const [entityId, mapping] of Object.entries(currentMappings)) {
      const isMoving = mapping.movementState === MovementState.MOVING;
      
      const mappingHash = JSON.stringify({
        spriteFolder: mapping.spriteFolder,
        currentAnimation: mapping.currentAnimation,
        // Only include direction when NOT moving to prevent feedback loops
        currentDirection: isMoving ? 'MOVING' : mapping.currentDirection,
        scale: mapping.scale,
        animationDurationSeconds: mapping.animationDurationSeconds,
        movementState: mapping.movementState, // Include movement state changes
      });
      
      const lastMappingHash = lastMappingData.get(entityId);
      if (lastMappingHash !== mappingHash) {
        lastMappingData.set(entityId, mappingHash);
        changedMappingIds.push(entityId);
        hasChanges = true;
      }
    }
    
    // Check for removed mappings
    const currentMappingIds = new Set(Object.keys(currentMappings));
    for (const entityId of Array.from(lastMappingData.keys())) {
      if (!currentMappingIds.has(entityId)) {
        lastMappingData.delete(entityId);
        changedMappingIds.push(entityId);
        hasChanges = true;
      }
    }
    
    return { hasChanges, changedMappingIds };
  }
  
  /**
   * Generic memoization helper for any data structure
   * Compares JSON strings to detect changes
   */
  static hasDataChanged<T>(
    currentData: T,
    lastDataHash: Map<string, string>,
    dataKey: string,
    hashSelector?: (data: T) => any // Optional function to select what to hash
  ): boolean {
    const dataToHash = hashSelector ? hashSelector(currentData) : currentData;
    const currentHash = JSON.stringify(dataToHash);
    const lastHash = lastDataHash.get(dataKey);
    
    if (lastHash !== currentHash) {
      lastDataHash.set(dataKey, currentHash);
      return true;
    }
    
    return false;
  }
  
  /**
   * Track specific field changes for an entity
   * Useful for tracking position, health, or other specific changes
   */
  static hasEntityFieldChanged<K extends keyof EntitySummary>(
    entity: EntitySummary,
    field: K,
    lastFieldData: Map<string, string>
  ): boolean {
    const fieldKey = `${entity.uuid}_${field}`;
    const currentValue = JSON.stringify(entity[field]);
    const lastValue = lastFieldData.get(fieldKey);
    
    if (lastValue !== currentValue) {
      lastFieldData.set(fieldKey, currentValue);
      return true;
    }
    
    return false;
  }
  
  /**
   * Batch check multiple entities for specific field changes
   * Returns array of entity IDs that had the field change
   */
  static getEntitiesWithFieldChanges<K extends keyof EntitySummary>(
    entities: EntitySummary[],
    field: K,
    lastFieldData: Map<string, string>
  ): string[] {
    const changedEntityIds: string[] = [];
    
    entities.forEach(entity => {
      if (this.hasEntityFieldChanged(entity, field, lastFieldData)) {
        changedEntityIds.push(entity.uuid);
      }
    });
    
    return changedEntityIds;
  }
  
  /**
   * Create a throttled change detector
   * Only reports changes after a minimum time interval
   */
  static createThrottledDetector(
    minIntervalMs: number = 100
  ): {
    hasChanged: (data: any, key: string) => boolean;
    forceNext: () => void;
  } {
    const lastDataHash = new Map<string, string>();
    const lastCheckTime = new Map<string, number>();
    let forceNextCheck = false;
    
    return {
      hasChanged: (data: any, key: string): boolean => {
        const now = Date.now();
        const lastTime = lastCheckTime.get(key) || 0;
        
        // Check if enough time has passed or if forced
        if (!forceNextCheck && (now - lastTime) < minIntervalMs) {
          return false;
        }
        
        // Reset force flag
        if (forceNextCheck) {
          forceNextCheck = false;
        }
        
        // Check for actual data change
        const hasChanged = StoreChangeDetectionUtils.hasDataChanged(data, lastDataHash, key);
        
        if (hasChanged) {
          lastCheckTime.set(key, now);
        }
        
        return hasChanged;
      },
      
      forceNext: (): void => {
        forceNextCheck = true;
      }
    };
  }
  
  /**
   * Create a debounced change detector
   * Only reports changes after data has been stable for a minimum time
   */
  static createDebouncedDetector(
    debounceMs: number = 200
  ): {
    hasChanged: (data: any, key: string) => Promise<boolean>;
    clear: () => void;
  } {
    const lastDataHash = new Map<string, string>();
    const timeouts = new Map<string, NodeJS.Timeout>();
    
    return {
      hasChanged: (data: any, key: string): Promise<boolean> => {
        return new Promise((resolve) => {
          // Clear existing timeout for this key
          const existingTimeout = timeouts.get(key);
          if (existingTimeout) {
            clearTimeout(existingTimeout);
          }
          
          // Set new timeout
          const timeout = setTimeout(() => {
            const hasChanged = StoreChangeDetectionUtils.hasDataChanged(data, lastDataHash, key);
            timeouts.delete(key);
            resolve(hasChanged);
          }, debounceMs);
          
          timeouts.set(key, timeout);
        });
      },
      
      clear: (): void => {
        // Clear all timeouts
        timeouts.forEach(timeout => clearTimeout(timeout));
        timeouts.clear();
        lastDataHash.clear();
      }
    };
  }
  
  /**
   * Cleanup utility to remove old entries from memoization maps
   * Call periodically to prevent memory leaks
   */
  static cleanupOldEntries(
    dataMap: Map<string, string>,
    validKeys: Set<string>
  ): number {
    let removedCount = 0;
    
    for (const key of Array.from(dataMap.keys())) {
      if (!validKeys.has(key)) {
        dataMap.delete(key);
        removedCount++;
      }
    }
    
    return removedCount;
  }
} 