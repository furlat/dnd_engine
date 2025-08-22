import { useSnapshot } from 'valtio';
import { useCallback, useMemo } from 'react';
import { characterSheetStore } from '../../store/characterSheetStore';
import { ModifiableValueSnapshot as ReadonlyModifiableValueSnapshot } from '../../types/characterSheet_types';
import { get } from 'lodash';

interface ModifiableValueDetails {
  name: string;
  value: number;
  baseValue: number;
  modifiers: Array<{ source: string; value: number }>;
  description?: string;
}

interface ModifiableValueState {
  // Data
  value: ReadonlyModifiableValueSnapshot | null;
  details: ModifiableValueDetails | null;
  // Computed
  getModifierTotal: () => number;
  getBaseValue: () => number;
  // Path resolution
  resolveValueAtPath: (path: string) => ReadonlyModifiableValueSnapshot | null;
  // Compatibility methods
  getValueDetails: (path: string) => ModifiableValueDetails;
}

export function useModifiableValue(valuePath: string | null): ModifiableValueState {
  const snap = useSnapshot(characterSheetStore);

  // Path resolution
  const resolveValueAtPath = useCallback((path: string): ReadonlyModifiableValueSnapshot | null => {
    if (!snap.character) return null;
    return get(snap.character, path) as ReadonlyModifiableValueSnapshot || null;
  }, [snap.character]);

  // Get the value at the current path
  const value = useMemo(() => 
    valuePath ? resolveValueAtPath(valuePath) : null
  , [valuePath, resolveValueAtPath]);

  // Compute details
  const details = useMemo(() => {
    if (!value) return null;

    type Channel = {
      readonly name: string;
      readonly normalized_value: number;
      readonly value_modifiers: ReadonlyArray<{
        readonly name: string;
        readonly value: number;
        readonly source_entity_name?: string;
      }>;
    }

    type Modifier = {
      readonly name: string;
      readonly value: number;
      readonly source_entity_name?: string;
    }

    const baseModifier = value.base_modifier?.value ?? 0;
    const modifiers = value.channels?.flatMap((channel: Channel) => 
      channel.value_modifiers.map((mod: Modifier) => ({
        source: mod.name,
        value: mod.value
      }))
    ) || [];

    return {
      name: value.name,
      value: value.normalized_value,
      baseValue: baseModifier,
      modifiers,
      description: `${value.name} (Base: ${baseModifier})`
    };
  }, [value]);

  // Computed values
  const getModifierTotal = useCallback(() => {
    if (!value || !value.channels) return 0;
    
    type Channel = {
      readonly value_modifiers: ReadonlyArray<{
        readonly value: number;
      }>;
    }
    
    return value.channels.reduce((total: number, channel: Channel) => 
      total + channel.value_modifiers.reduce((sum: number, mod: { value: number }) => sum + mod.value, 0)
    , 0);
  }, [value]);

  const getBaseValue = useCallback(() => {
    if (!value) return 0;
    return value.base_modifier?.value ?? 0;
  }, [value]);

  // Compatibility method for existing components
  const getValueDetails = useCallback((path: string): ModifiableValueDetails => {
    const resolvedValue = resolveValueAtPath(path);
    if (!resolvedValue) {
      // Return stub data for compatibility
      return {
        name: path.split('.').pop() || path,
        value: 0,
        baseValue: 0,
        modifiers: [],
        description: path
      };
    }

    type Channel = {
      readonly value_modifiers: ReadonlyArray<{
        readonly name: string;
        readonly value: number;
      }>;
    }

    type Modifier = {
      readonly name: string;
      readonly value: number;
    }

    const baseModifier = resolvedValue.base_modifier?.value ?? 0;
    const modifiers = resolvedValue.channels?.flatMap((channel: Channel) => 
      channel.value_modifiers.map((mod: Modifier) => ({
        source: mod.name,
        value: mod.value
      }))
    ) || [];

    return {
      name: resolvedValue.name,
      value: resolvedValue.normalized_value,
      baseValue: baseModifier,
      modifiers,
      description: `${resolvedValue.name} (Base: ${baseModifier})`
    };
  }, [resolveValueAtPath]);

  return {
    value,
    details,
    getModifierTotal,
    getBaseValue,
    resolveValueAtPath,
    getValueDetails
  };
} 