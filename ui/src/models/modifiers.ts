export enum AdvantageStatus {
  NONE = "None",
  ADVANTAGE = "Advantage",
  DISADVANTAGE = "Disadvantage"
}

export enum AutoHitStatus {
  NONE = "None",
  AUTOHIT = "Autohit",
  AUTOMISS = "Automiss"
}

export enum CriticalStatus {
  NONE = "None",
  AUTOCRIT = "Autocrit",
  NOCRIT = "Critical Immune"
}

export interface Modifier {
  uuid: string;
  name: string;
  value: number;
  source_entity_name?: string;
}

export interface ModifierChannel {
  name: string;
  score: number;
  normalized_score: number;
  value_modifiers: Array<{
    name: string;
    value: number;
    source_entity_name?: string;
  }>;
  advantage_modifiers: Array<{
    name: string;
    value: AdvantageStatus;
    source_entity_name?: string;
  }>;
  advantage_status: AdvantageStatus;
  critical_modifiers: Array<{
    name: string;
    value: CriticalStatus;
    source_entity_name?: string;
  }>;
  critical_status: CriticalStatus;
  auto_hit_modifiers: Array<{
    name: string;
    value: AutoHitStatus;
    source_entity_name?: string;
  }>;
  auto_hit_status: AutoHitStatus;
}

export interface ModifiableValueSnapshot {
  name: string;
  uuid: string;
  score: number;
  normalized_score: number;
  base_modifier?: Modifier;
  channels: ModifierChannel[];
  advantage: AdvantageStatus;
  critical: CriticalStatus;
  auto_hit: AutoHitStatus;
  outgoing_advantage: AdvantageStatus;
  outgoing_critical: CriticalStatus;
  outgoing_auto_hit: AutoHitStatus;
} 