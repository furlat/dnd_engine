import assert from 'node:assert/strict';
import test from 'node:test';
import * as sdk from '../index.js';

const uuid = '00000000-0000-4000-8000-000000000001';
const other = '00000000-0000-4000-8000-000000000002';
const encoder = new TextEncoder();
function action(index: number, targetSet: number, targetType: sdk.PlayerAction['target_type'] = 'multi_entity',
  changes: Partial<sdk.PlayerAction> = {}): sdk.PlayerAction {
  return {template_name: 'Rule', behavior_id: 'spell.rule', provided_by_id: 'spell.rule',
    target_type: targetType, availability_status: 'available', can_afford: true,
    display_name: 'Rule', cost_type: 'actions', discovery_index: index, discovery_generation: 1, target_set: targetSet, ...changes};
}
function discovery(): sdk.PlayerChoices {
  return {discovery_generation: 1, entity_uuid: uuid,
    subjects: [{uuid, kind: 'creature', name: 'Hero'}, {uuid: other, kind: 'object', name: 'Wall'}],
    positions: [[-2, 3], [4, 5]], target_sets: [
      [{kind: 'subject', index: 0, subject: 0, position: 0, secondary_set: 1},
       {kind: 'subject', index: 1, subject: 1, position: 1, secondary_set: 2},
       {kind: 'subject', index: 2, subject: 0, secondary_set: 3}],
      [{kind: 'subject', index: 3, subject: 1}], [{kind: 'subject', index: 3, subject: 0}], [],
      [{kind: 'self', index: 0}], [{kind: 'subject', index: 0, subject: 0}, {kind: 'subject', index: 1, subject: 1}]],
    entity_actions: [action(0, 0), action(1, 5)], self_actions: [action(2, 4, 'self')],
    object_actions: [action(3, 3, 'object', {availability_status: 'source_unaffordable', can_afford: false})]};
}
function decoded<T>(value: unknown, root = 'PlayerChoices'): T {return sdk.decode<T>(root, encoder.encode(JSON.stringify(value)));}

function lazyChoicesResponse(): sdk.ChoicesResponse {
  return {kind: 'choices', game_id: 'test', game_epoch: uuid, audience_id: uuid,
    correlation_id: other, state_revision: 'r', force_attack: false,
    choices: {discovery_generation: 1, entity_uuid: uuid, target_sets: [[]],
      position_actions: [action(0, 0, 'position', {template_name: 'Drop', display_name: 'Drop (Potion of Haste)',
        position_region: {range_feet: 5, candidate_source: 'visible', requires_unoccupied: false,
          requires_walkable: false, requires_axis_or_diagonal_alignment: false, exclude_source_position: true}})]}};
}

for (const [status, canAfford] of [['available', true], ['no_valid_targets', true], ['source_unaffordable', false]] as const)
  for (const defaultRegion of [false, true]) test(`lazy region: ${status}, defaults ${defaultRegion}`, () => {
    const value = lazyChoicesResponse(); const row = value.choices.position_actions![0];
    row.availability_status = status; row.can_afford = canAfford;
    if (defaultRegion) row.position_region = {};
    const before = structuredClone(value);
    assert.equal(sdk.validate('ChoicesResponse', value), value);
    const result = decoded<sdk.ChoicesResponse>(value, 'ChoicesResponse');
    assert.deepEqual(result, before); assert.deepEqual(value, before);
    assert.deepEqual(sdk.actionOptions(result.choices, sdk.allActions(result.choices)[0]), []);
    assert.equal(result.choices.positions?.length ?? 0, 0);
  });

const badLazyRelations: [string, (row: sdk.PlayerAction, choices: sdk.PlayerChoices) => void][] = [
  ['missing region', row => {delete row.position_region;}],
  ['null region', row => {row.position_region = null;}],
  ['invalid region', row => {(row.position_region as unknown as {candidate_source: string}).candidate_source = 'invented';}],
  ['unavailable nonempty', (row, choices) => {row.availability_status = 'no_valid_targets';
    choices.positions = [[1, 0]]; choices.target_sets![0].push({kind: 'position', index: 0, position: 0});}],
  ['source affordable', row => {row.availability_status = 'source_unaffordable';}],
  ['other unaffordable', row => {row.can_afford = false;}],
  ['target set', row => {row.target_set = 999;}],
  ['wrong generation', row => {row.discovery_generation = 2;}],
  ['wrong ordinal', row => {row.discovery_index = 1;}],
];
for (const [name, mutate] of badLazyRelations) test(`lazy region does not bypass admission: ${name}`, () => {
  const value = lazyChoicesResponse(); mutate(value.choices.position_actions![0], value.choices);
  assert.throws(() => decoded(value, 'ChoicesResponse'), sdk.ProtocolError);
});

test('shared options retain branch indices, inheritance, self and ordered repeated selections', () => {
  const value = decoded<sdk.PlayerChoices>(discovery()); const before = JSON.stringify(value);
  const [chain, repeated, dash, unavailable] = sdk.allActions(value);
  const [first, second, empty] = sdk.actionOptions(value, chain);
  assert.equal(sdk.secondaryOptions(value, chain, first)[0].index, 3);
  assert.equal(sdk.secondaryOptions(value, chain, second)[0].index, 3);
  assert.equal(sdk.bindingSubject(value, sdk.secondaryOptions(value, chain, first)[0])?.uuid, other);
  assert.equal(sdk.bindingSubject(value, sdk.secondaryOptions(value, chain, second)[0])?.uuid, uuid);
  assert.deepEqual(sdk.secondaryOptions(value, chain, empty), []);
  const inherited = sdk.actionOptions(value, repeated);
  assert.equal(sdk.secondaryOptions(value, repeated, inherited[0]), inherited);
  assert.deepEqual(sdk.selectionFor(repeated, [inherited[0], inherited[1], inherited[0]]).target_indices, [0, 1, 0]);
  const self = sdk.actionOptions(value, dash)[0];
  assert.equal(sdk.bindingSubject(value, self), undefined); assert.equal(sdk.bindingPosition(value, self), undefined);
  assert.deepEqual(sdk.selectionFor(dash, [self]).target_indices, [0]);
  assert.deepEqual(sdk.actionOptions(value, unavailable), []);
  assert.equal(sdk.bindingValue(first, 'is_path_hazardous'), false);
  assert.equal(sdk.bindingValue(first, 'path'), null);
  assert.deepEqual(sdk.bindingValue(first, 'opportunity_attack_exposures'), []);
  assert.equal(sdk.positionEligibility(value).get('-2,3')?.[0].binding, first);
  assert.equal(JSON.stringify(value), before); assert.equal(sdk.actionOptions(value, chain), value.target_sets![0]);
});

const badRelations: [string, (value: sdk.PlayerChoices) => void][] = [
  ['subject', value => {const binding = value.target_sets![0][0] as sdk.SubjectBinding; binding.subject = 999;}],
  ['position', value => {(value.target_sets![0][0] as sdk.SubjectBinding).position = 999;}],
  ['path', value => {value.target_sets![0][0].path = [999];}],
  ['exposure', value => {value.target_sets![0][0].opportunity_attack_exposures = [{reactor_uuid: uuid, reactor_name: 'Hero', from_position: 0, to_position: 999}];}],
  ['secondary', value => {value.target_sets![0][0].secondary_set = 999;}],
  ['target set', value => {value.entity_actions![0].target_set = 999;}],
  ['duplicate', value => {value.target_sets![0].push({...value.target_sets![0][0]});}],
  ['nested', value => {value.target_sets![1][0].secondary_set = 3;}],
  ['collision', value => {value.target_sets![1][0].index = 0;}],
  ['available empty', value => {value.entity_actions![0].target_set = 3;}],
  ['unavailable nonempty', value => {value.entity_actions![0].availability_status = 'no_valid_targets';}],
  ['source affordable', value => {value.object_actions![0].can_afford = true;}],
  ['other unaffordable', value => {value.entity_actions![0].can_afford = false;}],
  ['duplicate action', value => {value.self_actions![0].discovery_index = 0;}],
  ['wrong generation', value => {value.entity_actions![0].discovery_generation = 2;}],
  ['wrong ordinal', value => {value.entity_actions![0].discovery_index = 5;}],
];
for (const [name, mutate] of badRelations) test(`malformed compact relation: ${name}`, () => {
  const value = discovery(); mutate(value); assert.throws(() => decoded(value), sdk.ProtocolError);
});
for (const invalid of [true, '0', -1, 0.5]) test(`references do not coerce ${JSON.stringify(invalid)}`, () => {
  const value = discovery(); (value.target_sets![0][0] as unknown as {subject: unknown}).subject = invalid;
  assert.throws(() => decoded(value), sdk.ProtocolError);
});
test('preview local offset zero resolves only within its reply, including new coordinates', () => {
  const choices = decoded<sdk.PlayerChoices>(discovery());
  const value: sdk.PlayerSelectionPreview = {can_confirm: true,
    subjects: [{uuid: other, kind: 'object'}], positions: [[99, -7]],
    target_sets: [[{kind: 'subject', index: 3, subject: 0, position: 0}]], next_target_set: 0,
    next_positions: [0], area_preview: 'computed'};
  const result = decoded<sdk.PlayerSelectionPreview>(value, 'PlayerSelectionPreview');
  const binding = sdk.nextOptions(result)[0];
  assert.deepEqual(sdk.bindingPosition(result, binding), [99, -7]);
  assert.equal(sdk.bindingSubject(result, binding)?.uuid, other);
  assert.deepEqual(sdk.previewPositions(result), [[99, -7]]);
  assert.deepEqual(sdk.previewPositions(result, true), []);
  assert.notDeepEqual(choices.positions![0], sdk.bindingPosition(result, binding));
  assert.equal(result.area_preview, 'computed'); assert.equal('affected_positions' in result, false);
  assert.equal(decoded<sdk.PlayerSelectionPreview>({...value, area_preview: 'deferred'}, 'PlayerSelectionPreview').area_preview, 'deferred');
  for (const field of ['next_target_set', 'next_positions', 'affected_positions'])
    assert.throws(() => decoded({...value, [field]: field === 'next_target_set' ? 999 : [999]}, 'PlayerSelectionPreview'), sdk.ProtocolError);
});
test('selected paths resolve shared positions and preserve explicit empty paths', () => {
  const value = discovery(); value.target_sets![0][0].path = [0, 1]; value.target_sets![0][0].safe_path = [];
  const result = decoded<sdk.PlayerChoices>(value); const target = sdk.actionOptions(result, sdk.allActions(result)[0])[0];
  assert.deepEqual(sdk.bindingPath(result, target), [[-2, 3], [4, 5]]);
  assert.deepEqual(sdk.bindingPath(result, target, true), []);
  assert.equal(sdk.bindingPath(result, target)![0], result.positions![0]);
});
