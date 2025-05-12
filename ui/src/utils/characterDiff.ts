import * as React from 'react';
import { Character } from '../models/character';

export interface CharacterChanges {
  abilityScores: boolean;
  skills: boolean;
  savingThrows: boolean;
  health: boolean;
  equipment: boolean;
  actionEconomy: boolean;
  conditions: boolean;
}

export const detectChanges = (prev: Character | null, next: Character | null): CharacterChanges => {
  const changes: CharacterChanges = {
    abilityScores: false,
    skills: false,
    savingThrows: false,
    health: false,
    equipment: false,
    actionEconomy: false,
    conditions: false,
  };

  // If either is null, mark all as changed
  if (!prev || !next) {
    return Object.keys(changes).reduce((acc, key) => ({ ...acc, [key]: true }), {} as CharacterChanges);
  }

  // Check ability scores
  changes.abilityScores = JSON.stringify(prev.ability_scores) !== JSON.stringify(next.ability_scores);

  // Check skills
  changes.skills = JSON.stringify(prev.skill_set) !== JSON.stringify(next.skill_set) ||
    JSON.stringify(prev.skill_calculations) !== JSON.stringify(next.skill_calculations);

  // Check saving throws
  changes.savingThrows = JSON.stringify(prev.saving_throws) !== JSON.stringify(next.saving_throws) ||
    JSON.stringify(prev.saving_throw_calculations) !== JSON.stringify(next.saving_throw_calculations);

  // Check health
  changes.health = JSON.stringify(prev.health) !== JSON.stringify(next.health);

  // Check equipment and related calculations
  changes.equipment = JSON.stringify(prev.equipment) !== JSON.stringify(next.equipment) ||
    JSON.stringify(prev.ac_calculation) !== JSON.stringify(next.ac_calculation) ||
    JSON.stringify(prev.attack_calculations) !== JSON.stringify(next.attack_calculations);

  // Check action economy
  changes.actionEconomy = JSON.stringify(prev.action_economy) !== JSON.stringify(next.action_economy);

  // Check conditions
  changes.conditions = JSON.stringify(prev.active_conditions) !== JSON.stringify(next.active_conditions);

  return changes;
};

// Helper hook to track changes
export const useCharacterChanges = (character: Character | null) => {
  const prevCharRef = React.useRef<Character | null>(null);
  const [changes, setChanges] = React.useState<CharacterChanges>({
    abilityScores: true,
    skills: true,
    savingThrows: true,
    health: true,
    equipment: true,
    actionEconomy: true,
    conditions: true,
  });

  React.useEffect(() => {
    const newChanges = detectChanges(prevCharRef.current, character);
    setChanges(newChanges);
    prevCharRef.current = character;
  }, [character]);

  return changes;
}; 