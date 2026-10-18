import assert from 'node:assert/strict';
import test from 'node:test';
import {decode, ProtocolError, type LightRow} from '../index.js';

const encoder = new TextEncoder();
// A light source row of its group: identities are rows of the group's uuids; the footprint is a level per cell.
const source: LightRow = {
  source: 0, revision: 3, position: [-2, 6], base_height_steps: 2, very_bright_radius_feet: 10,
  bright_radius_feet: 20, dim_radius_feet: 20, appearance: 'torch', actor_anchored: true,
  anchor_entity: null, anchor_item: 1,
  affected_tiles: {cells: {x0: -2, y0: 6, width: 7, height: 1, bits: 'SQ=='}, values: 'BAMC'},
};
test('light row preserves its anchors, footprint and sparse defaults', () => {
  assert.deepEqual(decode('LightRow', encoder.encode(JSON.stringify(source))), source);
  const {base_height_steps, appearance, actor_anchored, anchor_entity, anchor_item, affected_tiles, ...sparse} = source;
  assert.deepEqual(decode('LightRow', encoder.encode(JSON.stringify(sparse))), sparse);
});
for (const [field, value] of [
  ['revision', -1], ['source', -1], ['position', [1]], ['position', [1.5, 2]],
  ['appearance', 'private_inventory'], ['actor_anchored', 1],
  ['affected_tiles', {'1,2': 4}], ['anchor_item', 'not-an-index'],
] as const) {
  test(`invalid light row ${field}=${JSON.stringify(value)} is rejected`, () => {
    assert.throws(() => decode('LightRow', encoder.encode(JSON.stringify({...source, [field]: value}))), ProtocolError);
  });
}
