import assert from 'node:assert/strict';
import test from 'node:test';
import {decode, ProtocolError, type AudienceFact, type BoundaryState} from '../index.js';

const caster = '00000000-0000-4000-8000-000000000001';
const summon = '00000000-0000-4000-8000-000000000002';
const encoder = new TextEncoder();
const grant: AudienceFact = {kind: 'audience', audience: {
  controlled: [caster, summon], observers: [caster, summon], revision: 1}, sensory: null};
const revoke: AudienceFact = {kind: 'audience', audience: {
  controlled: [caster], observers: [caster], revision: 2}, sensory: null};

test('audience transitions preserve order and Codex input remains external', () => {
  assert.deepEqual([grant, revoke].map(row => decode('AudienceFact', encoder.encode(JSON.stringify(row)))), [grant, revoke]);
  const boundary: BoundaryState = {lifecycle: 'waiting_for_codex', input_actor_uuid: summon, state_revision: 'summon-turn'};
  assert.deepEqual(decode('BoundaryState', encoder.encode(JSON.stringify(boundary))), boundary);
});
for (const changes of [{revision: -1}, {revision: 1.5}, {controlled: ['not-a-uuid']}]) {
  test(`invalid audience change ${JSON.stringify(changes)} is rejected`, () => {
    assert.throws(() => decode('AudienceFact', encoder.encode(JSON.stringify({
      ...grant, audience: {...grant.audience, ...changes}}))), ProtocolError);
  });
}
