import { UUID, SensesType, Position, DeepReadonly, EntitySummary } from './common';

// Tile related types
export interface TileSummary {
  readonly uuid: string;
  readonly name: string;
  readonly position: Position;
  readonly walkable: boolean;
  readonly visible: boolean;
  readonly sprite_name: string | null;
}

// Response types
export interface GridSnapshot {
  readonly width: number;
  readonly height: number;
  readonly tiles: Readonly<Record<string, TileSummary>>;
}

// Senses interfaces
export interface SensesSnapshot {
  readonly entities: Readonly<Record<UUID, Position>>;
  readonly visible: Readonly<Record<string, boolean>>;
  readonly walkable: Readonly<Record<string, boolean>>;
  readonly paths: Readonly<Record<string, readonly Position[]>>;
  readonly extra_senses: readonly SensesType[];
  readonly position: Position;
  readonly seen: readonly Position[];
}

// Attack results
export interface AttackResult {
  readonly event: { // TODO: Define proper event type instead of any
    readonly type: string;
    readonly source_entity_uuid: string;
    readonly target_entity_uuid: string;
    readonly roll_results: any; // TODO: Define proper roll results type
  };
  readonly attacker: EntitySummary;
}

/**
 * Helper function to make a position mutable if needed for API calls
 * Only use when specifically required for API calls that need mutable arrays
 */
export function toMutablePosition(position: Position): [number, number] {
  return [...position];
}

/**
 * Helper function to make a readonly record mutable if needed for API calls
 * Only use when specifically required for API calls that need mutable data
 */
export function toMutableRecord<K extends string | number | symbol, V>(
  record: Readonly<Record<K, V>>
): Record<K, V> {
  return { ...record };
} 