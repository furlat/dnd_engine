import { useSnapshot } from 'valtio';
import { useState, useCallback } from 'react';
import { characterSheetStore } from '../../store/characterSheetStore';
import type { 
  SkillSetSnapshot, 
  SkillBonusCalculationSnapshot,
  Skill
} from '../../types/characterSheet_types';

interface SkillsData {
  // Store data
  skillSet: SkillSetSnapshot | null;
  calculations: Readonly<Record<string, SkillBonusCalculationSnapshot>> | null;
  // UI State
  selectedSkill: Skill | null;
  // Actions
  handleSelectSkill: (skill: Skill | null) => void;
  // Computed values
  getOrderedSkills: () => Skill[];
  getSkillBonus: (skill: Skill) => number;
  isSkillProficient: (skill: Skill) => boolean;
  hasSkillExpertise: (skill: Skill) => boolean;
}

const ABILITY_ORDER = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'];

export function useSkills(): SkillsData {
  const snap = useSnapshot(characterSheetStore);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);

  // Handlers
  const handleSelectSkill = useCallback((skill: Skill | null) => {
    setSelectedSkill(skill);
  }, []);

  // Computed values
  const getOrderedSkills = useCallback(() => {
    const skills = snap.character?.skill_set?.skills;
    if (!skills) return [];
    
    const list: Skill[] = [];
    ABILITY_ORDER.forEach((ability) => {
      Object.values(skills)
        .filter((skill) => skill.ability === ability)
        .forEach((skill) => list.push(skill));
    });
    return list;
  }, [snap.character?.skill_set?.skills]);

  const getSkillBonus = useCallback((skill: Skill) => {
    return skill.bonus ?? 0;
  }, []);

  const isSkillProficient = useCallback((skill: Skill) => {
    return skill.proficient ?? false;
  }, []);

  const hasSkillExpertise = useCallback((skill: Skill) => {
    // Typescript will warn about this property not existing on Skill,
    // but it might be available at runtime for some skill objects
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