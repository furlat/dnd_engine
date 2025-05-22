// Type alias for UUID
export type UUID = string;

// Position type (always readonly)
export type Position = readonly [number, number];

// SensesType enum
export enum SensesType {
    BLINDSIGHT = "Blindsight",
    DARKVISION = "Darkvision",
    TREMORSENSE = "Tremorsense",
    TRUESIGHT = "Truesight"
}

// TypeScript utility to make all properties and nested arrays readonly recursively
type Primitive = string | number | boolean | undefined | null;
type DeepReadonlyArray<T> = ReadonlyArray<DeepReadonly<T>>;
type DeepReadonlyObject<T> = {
  readonly [P in keyof T]: DeepReadonly<T[P]>;
};

export type DeepReadonly<T> = T extends Primitive
  ? T
  : T extends Array<infer U>
  ? DeepReadonlyArray<U>
  : T extends Map<infer K, infer V>
  ? ReadonlyMap<DeepReadonly<K>, DeepReadonly<V>>
  : T extends Set<infer U>
  ? ReadonlySet<DeepReadonly<U>>
  : DeepReadonlyObject<T>;

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

// Entity summary for battlemap and character sheet
export interface EntitySummary {
  readonly uuid: UUID;
  readonly name: string;
  readonly current_hp: number;
  readonly max_hp: number;
  readonly armor_class?: number;
  readonly target_entity_uuid?: UUID;
  readonly position: Position;
  readonly sprite_name?: string;
  readonly senses: SensesSnapshot;
}
