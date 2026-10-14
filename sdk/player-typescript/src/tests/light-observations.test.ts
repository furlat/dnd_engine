import assert from 'node:assert/strict';
import test from 'node:test';
import {decode, ProtocolError, type PerceivedLightSource} from '../index.js';

const encoder = new TextEncoder();
const source: PerceivedLightSource = {
  source_uuid: '00000000-0000-4000-8000-000000000001', revision: 3,
  position: [-2, 6], base_height_steps: 2, very_bright_radius_feet: 10,
  bright_radius_feet: 20, dim_radius_feet: 20, appearance: 'torch',
  actor_anchored: true, anchor_entity_uuid: null, anchor_item_uuid: null,
  affected_tiles: {'-2,6': 4, '1,6': 3, '4,6': 2},
};
test('optical source preserves anonymous anchor, footprint and sparse defaults', () => {
  assert.deepEqual(decode('PerceivedLightSource', encoder.encode(JSON.stringify(source))), source);
  const {appearance, actor_anchored, anchor_entity_uuid, anchor_item_uuid, affected_tiles, ...sparse} = source;
  assert.deepEqual(decode('PerceivedLightSource', encoder.encode(JSON.stringify(sparse))), sparse);
});
for (const [field, value] of [
  ['revision', -1], ['position', [1]], ['position', [1.5, 2]],
  ['appearance', 'private_inventory'], ['actor_anchored', 1],
  ['affected_tiles', {'1,2': 99}], ['anchor_item_uuid', 'not-a-uuid'],
] as const) {
  test(`invalid optical source ${field}=${JSON.stringify(value)} is rejected`, () => {
    assert.throws(() => decode('PerceivedLightSource', encoder.encode(JSON.stringify({...source, [field]: value}))), ProtocolError);
  });
}
