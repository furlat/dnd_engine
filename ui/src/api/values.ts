// ModifiableValue channel types
export interface ValueModifier {
  name: string;
  value: number;
  source_entity_name?: string;
}

export interface AdvantageModifier {
  name: string;
  value: 'ADVANTAGE' | 'DISADVANTAGE' | 'NONE';
  source_entity_name?: string;
}

export interface Channel {
  name: string;
  normalized_score: number;
  value_modifiers: ValueModifier[];
  advantage_modifiers: AdvantageModifier[];
}

// ModifiableValue snapshot
export interface ModifiableValueSnapshot {
  uuid: string;
  name: string;
  score: number;
  normalized_score: number;
  channels: Channel[];
  advantage?: 'ADVANTAGE' | 'DISADVANTAGE' | 'NONE';
} 