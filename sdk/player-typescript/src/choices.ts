/** Response-local lookups. Shared values are read-only by consumer contract. */
import type * as C from './contracts.generated.js';

export class ProtocolError extends Error {}
export type ChoiceOption = Readonly<C.SubjectBinding | C.PositionBinding | C.SelfBinding>;
type Domains = C.PlayerChoices | C.PlayerSelectionPreview;
type Position = NonNullable<C.PlayerChoices['positions']>[number];
type PairField = 'distance' | 'path_cost' | 'extra_target_uuids' | 'secondary_set' |
  'is_path_hazardous' | 'safe_path_cost' | 'path' | 'safe_path' |
  'opportunity_attack_exposures' | 'safe_path_opportunity_attack_exposures';

export function allActions(choices: C.PlayerChoices): readonly Readonly<C.PlayerAction>[] {
  return [...choices.entity_actions ?? [], ...choices.position_actions ?? [],
    ...choices.self_actions ?? [], ...choices.object_actions ?? []];
}
function at<T>(values: readonly T[], index: number, field: string): T {
  if (!Number.isSafeInteger(index) || index < 0 || index >= values.length)
    throw new ProtocolError(`${field}: reference ${index} is out of range`);
  return values[index];
}
export function actionOptions(choices: C.PlayerChoices, action: Readonly<C.PlayerAction>): readonly ChoiceOption[] {
  return at(choices.target_sets ?? [], action.target_set, 'target_set');
}
export function bindingSubject(domains: Domains, binding: ChoiceOption): Readonly<C.ChoiceSubject> | undefined {
  return binding.kind === 'subject' ? at(domains.subjects ?? [], binding.subject, 'subject') : undefined;
}
export function bindingPosition(domains: Domains, binding: ChoiceOption): Readonly<Position> | undefined {
  return binding.kind === 'self' || binding.position == null ? undefined :
    at(domains.positions ?? [], binding.position, 'position');
}
export function bindingValue<K extends PairField>(binding: ChoiceOption, field: K): ChoiceOption[K] {
  if (binding[field] !== undefined) return binding[field];
  if (field === 'is_path_hazardous') return false as ChoiceOption[K];
  if (field === 'opportunity_attack_exposures' || field === 'safe_path_opportunity_attack_exposures')
    return [] as unknown as ChoiceOption[K];
  return null as ChoiceOption[K];
}
export function bindingPath(domains: Domains, binding: ChoiceOption, safe = false): readonly Readonly<Position>[] | null {
  const references = bindingValue(binding, safe ? 'safe_path' : 'path');
  return references == null ? null : references.map(index => at(domains.positions ?? [], index, 'path'));
}
export function secondaryOptions(choices: C.PlayerChoices, action: Readonly<C.PlayerAction>, primary: ChoiceOption): readonly ChoiceOption[] {
  return primary.secondary_set == null ? actionOptions(choices, action) :
    at(choices.target_sets ?? [], primary.secondary_set, 'secondary_set');
}
export function nextOptions(preview: C.PlayerSelectionPreview): readonly ChoiceOption[] {
  return at(preview.target_sets ?? [], preview.next_target_set, 'next_target_set');
}
export function previewPositions(preview: C.PlayerSelectionPreview, affected = false): readonly Readonly<Position>[] {
  const field = affected ? 'affected_positions' : 'next_positions';
  return (preview[field] ?? []).map(index => at(preview.positions ?? [], index, field));
}
export function selectionFor(action: Readonly<C.PlayerAction>, targets: readonly ChoiceOption[],
  extraPositions: readonly Readonly<Position>[] = [], preferSafe = true): C.ActionSelection {
  return {action_index: action.discovery_index ?? 0, target_indices: targets.map(target => target.index),
    extra_target_positions: extraPositions.map(position => [...position]), prefer_safe: preferSafe};
}
export interface PositionEligibility {readonly action: Readonly<C.PlayerAction>; readonly binding: ChoiceOption}
export function positionEligibility(choices: C.PlayerChoices): ReadonlyMap<string, readonly PositionEligibility[]> {
  const result = new Map<string, PositionEligibility[]>();
  for (const action of allActions(choices)) for (const binding of actionOptions(choices, action)) {
    const position = bindingPosition(choices, binding);
    if (position) {const key = `${position[0]},${position[1]}`; const entries = result.get(key) ?? [];
      entries.push({action, binding}); result.set(key, entries);}
  }
  return result;
}
function checkDomains(domains: Domains): void {
  const positions = domains.positions ?? []; const subjects = domains.subjects ?? [];
  const sets = domains.target_sets ?? []; const indices: Set<number>[] = []; const secondarySets = new Set<number>();
  for (const targets of sets) {
    const seen = new Set<number>();
    for (const binding of targets) {
      if (!Number.isSafeInteger(binding.index) || seen.has(binding.index)) throw new ProtocolError('Invalid or duplicate target index within a target set');
      seen.add(binding.index);
      if (binding.kind === 'subject') at(subjects, binding.subject, 'subject');
      if (binding.kind !== 'self' && binding.position != null) at(positions, binding.position, 'position');
      for (const field of ['path', 'safe_path'] as const) for (const reference of binding[field] ?? []) at(positions, reference, field);
      for (const field of ['opportunity_attack_exposures', 'safe_path_opportunity_attack_exposures'] as const)
        for (const exposure of binding[field] ?? []) {at(positions, exposure.from_position, field); at(positions, exposure.to_position, field);}
      if (binding.secondary_set != null) {at(sets, binding.secondary_set, 'secondary_set'); secondarySets.add(binding.secondary_set);}
    }
    indices.push(seen);
  }
  for (const reference of secondarySets)
    if (sets[reference].some(binding => binding.secondary_set != null)) throw new ProtocolError('Secondary options cannot contain secondary overrides');
  for (const targets of sets) for (const primary of targets)
    if (primary.secondary_set != null && indices[primary.secondary_set].has(primary.index))
      throw new ProtocolError('Secondary target index collides with its primary');
}
export function checkChoices(choices: C.PlayerChoices): void {
  checkDomains(choices); const sets = choices.target_sets ?? []; let ordinal = 0;
  for (const action of allActions(choices)) {
    const index = action.discovery_index ?? 0;
    if (!Number.isSafeInteger(index) || index !== ordinal++) throw new ProtocolError('Discovery action index does not match its ordinal');
    if ((action.discovery_generation ?? 0) !== choices.discovery_generation) throw new ProtocolError('Action belongs to a different discovery generation');
    const targets = at(sets, action.target_set, 'target_set');
    if ((action.availability_status === 'source_unaffordable') === action.can_afford) throw new ProtocolError('Contradictory source affordability');
    if ((action.availability_status === 'available') !== (targets.length > 0)) throw new ProtocolError('Contradictory action availability and target set');
  }
}
export function checkPreview(preview: C.PlayerSelectionPreview): void {
  checkDomains(preview); nextOptions(preview);
  for (const field of ['next_positions', 'affected_positions'] as const)
    for (const reference of preview[field] ?? []) at(preview.positions ?? [], reference, field);
}
