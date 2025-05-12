import { useSnapshot } from 'valtio';
import { useCallback, useMemo } from 'react';
import { characterStore } from '../../store/characterStore';
import type { ReadonlyModifiableValueSnapshot, ReadonlyModifier } from '../../models/readonly';
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
  const snap = useSnapshot(characterStore);

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

    const baseModifier = value.base_modifier?.value ?? 0;
    const modifiers = value.channels.flatMap(channel => 
      channel.value_modifiers.map(mod => ({
        source: mod.name,
        value: mod.value
      }))
    );

    return {
      name: value.name,
      value: value.normalized_score,
      baseValue: baseModifier,
      modifiers,
      description: `${value.name} (Base: ${baseModifier})`
    };
  }, [value]);

  // Computed values
  const getModifierTotal = useCallback(() => {
    if (!value) return 0;
    return value.channels.reduce((total, channel) => 
      total + channel.value_modifiers.reduce((sum, mod) => sum + mod.value, 0)
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

    const baseModifier = resolvedValue.base_modifier?.value ?? 0;
    const modifiers = resolvedValue.channels.flatMap(channel => 
      channel.value_modifiers.map(mod => ({
        source: mod.name,
        value: mod.value
      }))
    );

    return {
      name: resolvedValue.name,
      value: resolvedValue.normalized_score,
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