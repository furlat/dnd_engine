import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterStore } from '../../store/characterStore';
import type { 
  ReadonlySkillSetSnapshot, 
  ReadonlySkillBonusCalculation,
  ReadonlySkill
} from '../../models/readonly';

interface SkillsData {
  // Store data
  skillSet: ReadonlySkillSetSnapshot | null;
  calculations: Readonly<Record<string, ReadonlySkillBonusCalculation>> | null;
  // UI State
  selectedSkill: ReadonlySkill | null;
  // Actions
  handleSelectSkill: (skill: ReadonlySkill | null) => void;
  // Computed values
  getOrderedSkills: () => ReadonlySkill[];
  getSkillBonus: (skill: ReadonlySkill) => number;
  isSkillProficient: (skill: ReadonlySkill) => boolean;
  hasSkillExpertise: (skill: ReadonlySkill) => boolean;
}

const ABILITY_ORDER = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'];

export function useSkills(): SkillsData {
  const snap = useSnapshot(characterStore);
  const [selectedSkill, setSelectedSkill] = useState<ReadonlySkill | null>(null);

  // Handlers
  const handleSelectSkill = useCallback((skill: ReadonlySkill | null) => {
    setSelectedSkill(skill);
  }, []);

  // Computed values
  const getOrderedSkills = useCallback(() => {
    const skills = snap.character?.skill_set?.skills;
    if (!skills) return [];
    
    const list: ReadonlySkill[] = [];
    ABILITY_ORDER.forEach((ability) => {
      Object.values(skills)
        .filter((skill) => skill.ability === ability)
        .forEach((skill) => list.push(skill));
    });
    return list;
  }, [snap.character?.skill_set?.skills]);

  const getSkillBonus = useCallback((skill: ReadonlySkill) => {
    return (skill as any).bonus ?? (skill as any).effective_bonus ?? 0;
  }, []);

  const isSkillProficient = useCallback((skill: ReadonlySkill) => {
    return (skill as any).proficient ?? false;
  }, []);

  const hasSkillExpertise = useCallback((skill: ReadonlySkill) => {
    return (skill as any).expertise ?? false;
  }, []);

  return {
    skillSet: snap.character?.skill_set ?? null,
    calculations: snap.character?.skill_calculations ?? null,
    selectedSkill,
    handleSelectSkill,
    getOrderedSkills,
    getSkillBonus,
    isSkillProficient,
    hasSkillExpertise
  };
} 