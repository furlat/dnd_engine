import { useCallback } from 'react';
import {
  refreshActionEconomy,
  addCondition,
  removeCondition,
  modifyHealth,
  applyTemporaryHP
} from '../../api/character_sheet/characterSheetApi';
import { ConditionType, DurationType, Character } from '../../types/characterSheet_types';
import { characterSheetActions } from '../../store/characterSheetStore';

/**
 * Hook for character control actions
 */
export const useCharacterControls = () => {
  /**
   * Apply the specified condition to the character
   */
  const applyCondition = useCallback(async (
    entityId: string,
    condition: ConditionType,
    duration: DurationType = DurationType.ROUNDS,
    sourceEntityId?: string, // If omitted, applies to self
    durationRounds?: number
  ): Promise<Character | undefined> => {
    try {
      const source = sourceEntityId || entityId;
      
      const response = await addCondition(entityId, {
        condition_type: condition,
        source_entity_uuid: source,
        duration_type: duration,
        duration_rounds: durationRounds
      });
      
      characterSheetActions.setCharacter(response);
      return response;
    } catch (error) {
      console.error('Error applying condition:', error);
      return undefined;
    }
  }, []);
  
  /**
   * Remove the specified condition from the character
   */
  const removeConditionFromEntity = useCallback(async (
    entityId: string,
    condition: string
  ): Promise<Character | undefined> => {
    try {
      const response = await removeCondition(entityId, condition);
      
      characterSheetActions.setCharacter(response);
      return response;
    } catch (error) {
      console.error('Error removing condition:', error);
      return undefined;
    }
  }, []);
  
  /**
   * Refresh action economy for the character
   */
  const refreshEntityActionEconomy = useCallback(async (
    entityId: string
  ): Promise<Character | undefined> => {
    try {
      const response = await refreshActionEconomy(entityId);
      
      characterSheetActions.setCharacter(response);
      return response;
    } catch (error) {
      console.error('Error refreshing action economy:', error);
      return undefined;
    }
  }, []);
  
  /**
   * Apply damage or healing to the character
   */
  const applyHealthChange = useCallback(async (
    entityId: string,
    amount: number, // Positive for healing, negative for damage
    isTemporary: boolean = false
  ): Promise<Character | undefined> => {
    try {
      let response;
      
      if (isTemporary && amount > 0) {
        response = await applyTemporaryHP(entityId, amount);
      } else {
        response = await modifyHealth(entityId, amount);
      }
      
      characterSheetActions.setCharacter(response);
      return response;
    } catch (error) {
      console.error('Error modifying health:', error);
      return undefined;
    }
  }, []);
  
  return {
    applyCondition,
    removeConditionFromEntity,
    refreshEntityActionEconomy,
    applyHealthChange
  };
}; 