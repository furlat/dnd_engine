import assert from 'node:assert/strict';
import test from 'node:test';
import {decode, ProtocolError, type LightRow} from '../index.js';

const encoder = new TextEncoder();
// A light source entering perception, as a row of its group: identities are rows of the group's uuids. It carries
// no native revision and no footprint (the cells' light is their own value).
const source: LightRow = {
  source: 0, position: [-2, 6], base_height_steps: 2, very_bright_radius_feet: 10,
  bright_radius_feet: 20, dim_radius_feet: 20, appearance: 'torch', actor_anchored: true,
  anchor_entity: null, anchor_item: 1,
};
test('light row preserves its anchors and sparse defaults', () => {
  assert.deepEqual(decode('LightRow', encoder.encode(JSON.stringify(source))), source);
  const {base_height_steps, appearance, actor_anchored, anchor_entity, anchor_item, ...sparse} = source;
  assert.deepEqual(decode('LightRow', encoder.encode(JSON.stringify(sparse))), sparse);
});
for (const [field, value] of [
  ['revision', 3], ['source', -1], ['position', [1]], ['position', [1.5, 2]],
  ['appearance', 'private_inventory'], ['actor_anchored', 1],
  ['affected_tiles', {'1,2': 4}], ['anchor_item', 'not-an-index'],
] as const) {
  test(`invalid light row ${field}=${JSON.stringify(value)} is rejected`, () => {
    assert.throws(() => decode('LightRow', encoder.encode(JSON.stringify({...source, [field]: value}))), ProtocolError);
  });
}
