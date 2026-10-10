import assert from 'node:assert/strict';
import test, {type TestContext} from 'node:test';
import identity from '../protocol-identity.json' with {type: 'json'};
import * as sdk from '../index.js';
const uuid = '00000000-0000-4000-8000-000000000001';
const scope = {game_id: 'test', game_epoch: uuid, audience_id: uuid};
const boundary: sdk.BoundaryState = {lifecycle: 'waiting_for_human', input_actor_uuid: uuid, state_revision: 'r'};
const encoder = new TextEncoder();
const cursor = (sequence: number): sdk.PlayerCursor => ({...scope, sequence});
const status = (final?: number): sdk.StatusSnapshot => ({...scope, boundary: {...boundary, lifecycle: final === undefined ? 'waiting_for_human' : 'terminal'},
  published_cursor: cursor(final ?? 0), final_cursor: final === undefined ? null : cursor(final), attachment_epoch: uuid, catch_up_cursor: cursor(0), acknowledged_cursor: null,
  next_command_number: 1, pending_command_numbers: []});
const protocol = identity as sdk.ProtocolIdentity;
const initial = (sequence = 0): sdk.InitializationResponse => ({kind: 'initialization', protocol, cursor: cursor(sequence), content_revision: 'r', content_additions: [],
  initialization: {generation: uuid, observer_uuid: uuid, world: {battlefield_id: 'test', battlefield_name: 'é', bounds: [-1, -1, 1, 1], width: 3, height: 3},
    nodes: [], version_rows: [], end_cursor: 0, observations: [], world_updates: []}});
const operation = (sequence: number): sdk.PlayerOperation => ({kind: 'operation', protocol, cursor: cursor(sequence), state_revision: 'r', command_number: null, boundary,
  audience: {controlled: [uuid], observers: [uuid]}, lineages: [], hud: null, combat_log_appends: [], content_additions: []});
const event = (name: string, value: unknown, sequence?: number) => `event: ${name}\n${sequence === undefined ? '' : `id: ${sequence}\n`}data: ${JSON.stringify(value)}\n\n`;
const ready = (final?: number, after = 0) => event('ready', {kind: 'ready', protocol, after: cursor(after), head: cursor(final ?? 0), status: status(final)});
function deferred() {let resolve!: () => void; const promise = new Promise<void>(r => {resolve = r;}); return {promise, resolve};}
function peer(t: TestContext, streams: (string | Uint8Array)[], init = initial(), ackFailure?: (sequence: number, count: number) => Response | undefined, eof = false) {
  const acks: number[] = []; const resumes: number[] = []; let cancelled = 0;
  t.mock.method(globalThis, 'fetch', async (input: string, options: RequestInit) => {
    const url = new URL(input);
    if (url.pathname.endsWith('/initialization')) return Response.json(init);
    if (url.pathname.endsWith('/ack')) {const value = JSON.parse(options.body as string).cursor as sdk.PlayerCursor; acks.push(value.sequence);
      return ackFailure?.(value.sequence, acks.length) ?? Response.json({kind: 'ack', cursor: value, catch_up_cursor: cursor(0)});}
    if (url.pathname.endsWith('/events')) {
      resumes.push(Number(url.searchParams.get('after'))); const value = streams.shift(); assert.notEqual(value, undefined);
      return new Response(new ReadableStream<Uint8Array>({start(controller) {controller.enqueue(typeof value === 'string' ? encoder.encode(value) : value); if (eof) controller.close();}, cancel() {cancelled++;}}),
        {headers: {'content-type': 'text/event-stream'}});}
    throw new Error('Unexpected route ' + url.pathname);
  });
  const connection: sdk.Connection = {baseUrl: 'https://peer.invalid', credential: 'test', bootstrap: {kind: 'bootstrap', protocol, status: status(), audience: null, encounter_name: 'test', content_revision: 'r'}};
  return {connection, acks, resumes, cancelled: () => cancelled};
}
test('SSE split UTF-8/CRLF, comments, multiline and incomplete EOF', async () => {
  async function* chunks() {for (const byte of encoder.encode(': comment\r\nevent: operation\r\nid: 1\r\ndata: {"name":\r\ndata: "é"}\r\n\r\ndata: unfinished')) yield Uint8Array.of(byte);}
  const records = []; for await (const record of sdk.sseRecords(chunks())) records.push(record);
  assert.deepEqual(records, [{event: 'operation', id: '1', raw: encoder.encode('{"name":\n"é"}')}]);
});
test('CR-only blank line terminates at EOF', async () => {
  async function* chunks() {yield encoder.encode('event: operation\rid: 1\rdata: {}\r\r');}
  const records = []; for await (const record of sdk.sseRecords(chunks())) records.push(record);
  assert.deepEqual(records, [{event: 'operation', id: '1', raw: encoder.encode('{}')}]);
});
test('duplicate and final prefix consumed once', async t => {
  const server = peer(t, [ready(2) + event('operation', operation(1), 1).repeat(2) + event('operation', operation(2), 2)]); const seen: number[] = [];
  const follower = sdk.createFollower(server.connection, async (packet, raw) => {seen.push(packet.cursor.sequence); assert.deepEqual(JSON.parse(new TextDecoder().decode(raw)), packet);});
  await sdk.follow(follower); await sdk.waitForCursor(follower, cursor(1)); await assert.rejects(sdk.waitForCursor(follower, cursor(3)), sdk.ProtocolError);
  assert.deepEqual(seen, [0, 1, 2]); assert.deepEqual(server.acks, [0, 1, 2]); assert.equal(server.cancelled(), 1);
});
for (const [name, packet, id] of [['gap', operation(2), 2], ['ID', operation(1), 2], ['identity', {...operation(1), cursor: {...cursor(1), game_id: 'other'}}, 1]] as const) {
  test(`${name} failure does not ACK`, async t => {
    const server = peer(t, [ready() + event('operation', packet, id)]); const seen: number[] = [];
    const follower = sdk.createFollower(server.connection, async packet => {seen.push(packet.cursor.sequence);});
    await assert.rejects(sdk.follow(follower), sdk.ProtocolError); assert.deepEqual(seen, [0]); assert.deepEqual(server.acks, [0]); assert.equal(server.cancelled(), 1);
  });
}
test('blocked consumer failure leaves previous cursor and ACK', async t => {
  const server = peer(t, [ready() + event('operation', operation(1), 1)]); const entered = deferred(); const release = deferred();
  const follower = sdk.createFollower(server.connection, async packet => {if (packet.cursor.sequence) {entered.resolve(); await release.promise; throw new Error('consumer failed');}});
  const rejected = assert.rejects(sdk.follow(follower), /consumer failed/);
  await entered.promise; assert.deepEqual(follower.consumed, cursor(0)); assert.deepEqual(server.acks, [0]); release.resolve(); await rejected;
  await assert.rejects(sdk.waitForCursor(follower, cursor(1)), /consumer failed/); assert.deepEqual(server.acks, [0]); assert.equal(server.cancelled(), 1);
});
test('nonzero initialization rejected before consumption', async t => {
  const server = peer(t, [ready(1, 1)], initial(1)); const seen: unknown[] = [];
  await assert.rejects(sdk.follow(sdk.createFollower(server.connection, async packet => {seen.push(packet);})), sdk.ProtocolError);
  assert.deepEqual(seen, []); assert.deepEqual(server.acks, []);
});
test('final ACK replacement is not suppressed', async t => {
  const server = peer(t, [ready(1) + event('operation', operation(1), 1)], initial(), sequence => sequence === 1 ? Response.json({kind: 'error', code: 'attachment_replaced', http_status: 409, retryable: false}, {status: 409}) : undefined);
  const follower = sdk.createFollower(server.connection, async () => {});
  await assert.rejects(sdk.follow(follower), sdk.PlayerApiError); assert.equal(follower.completed, false); assert.equal(server.cancelled(), 1);
});
test('nested final cursor identity is validated', async t => {
  const state = status(0); state.final_cursor!.game_id = 'other';
  const server = peer(t, [event('ready', {kind: 'ready', protocol, after: cursor(0), head: cursor(0), status: state})]);
  await assert.rejects(sdk.follow(sdk.createFollower(server.connection, async () => {})), sdk.ProtocolError);
});
test('fully delimited invalid UTF-8 is fatal, not a reconnect', async t => {
  const server = peer(t, [new Uint8Array([...encoder.encode('data: '), 255, ...encoder.encode('\n\n')])]);
  await assert.rejects(sdk.follow(sdk.createFollower(server.connection, async () => {})), sdk.ProtocolError); assert.equal(server.resumes.length, 1);
});
test('cancellation interrupts a blocked consumer and removes waits', async t => {
  const server = peer(t, [ready() + event('operation', operation(1), 1)]); const entered = deferred(); const release = deferred(); const abort = new AbortController();
  const follower = sdk.createFollower(server.connection, async packet => {if (packet.cursor.sequence) {entered.resolve(); await release.promise;}});
  const rejected = assert.rejects(sdk.follow(follower, {signal: abort.signal}), /cancelled/);
  const waiting = assert.rejects(sdk.waitForCursor(follower, cursor(1), {signal: abort.signal}), /cancelled/);
  await entered.promise; abort.abort(new Error('cancelled')); await Promise.all([rejected, waiting]); release.resolve();
  assert.deepEqual(follower.consumed, cursor(0)); assert.deepEqual(server.acks, [0]); assert.equal(server.cancelled(), 1); assert.equal(follower.waiters.size, 0);
});
test('lost final ACK reply resends consumed cursor without another consumer call', async t => {
  const server = peer(t, [ready(1) + event('operation', operation(1), 1), ready(1, 1)], initial(), (sequence, count) => {if (sequence === 1 && count === 2) throw new TypeError('reply lost'); return undefined;});
  const seen: number[] = []; await sdk.follow(sdk.createFollower(server.connection, async packet => {seen.push(packet.cursor.sequence);}));
  assert.deepEqual(seen, [0, 1]); assert.deepEqual(server.acks, [0, 1, 1]); assert.deepEqual(server.resumes, [0, 1]); assert.equal(server.cancelled(), 2);
});
test('failed final prefix drains before typed error', async t => {
  const state = status(1); state.boundary.lifecycle = 'failed';
  const server = peer(t, [event('ready', {kind: 'ready', protocol, after: cursor(0), head: cursor(1), status: state}) + event('operation', operation(1), 1)]);
  const seen: number[] = []; const follower = sdk.createFollower(server.connection, async packet => {seen.push(packet.cursor.sequence);});
  await assert.rejects(sdk.follow(follower), (error: sdk.PlayerApiError) => error.value.code === 'game_failed');
  await sdk.waitForCursor(follower, cursor(1)); await assert.rejects(sdk.waitForCursor(follower, cursor(2)), sdk.PlayerApiError); assert.deepEqual(seen, [0, 1]);
});
test('waiters are bounded and cancellation frees every registration', async t => {
  const server = peer(t, []); const follower = sdk.createFollower(server.connection, async () => {}); const abort = new AbortController();
  const waits = Array.from({length: 64}, () => assert.rejects(sdk.waitForCursor(follower, cursor(1), {signal: abort.signal}), /cancelled/));
  await assert.rejects(sdk.waitForCursor(follower, cursor(1)), /Too many/); abort.abort(new Error('cancelled')); await Promise.all(waits); assert.equal(follower.waiters.size, 0);
});
test('oversized unfinished SSE line is rejected before JSON decoding', async () => {
  async function* chunks() {for (let i = 0; i < 65; i++) yield new Uint8Array(1024 * 1024).fill(97);}
  await assert.rejects(async () => {for await (const _ of sdk.sseRecords(chunks())) assert.fail('unfinished event dispatched');}, sdk.ProtocolError);
});
test('overflowing JSON number is rejected', () => {
  assert.throws(() => sdk.decode('ResidueEllipse', encoder.encode('{"center":[0,0],"radius_x":1e999,"radius_y":1}')), sdk.ProtocolError);
});
test('preview correlation also checks actor and ordered selection', async t => {
  const body: sdk.PreviewRequest = {actor_uuid: uuid, state_revision: 'r', discovery_generation: 1, correlation_id: uuid, selection: {action_index: 0, target_indices: [1, 1, 2]}};
  const server = peer(t, []);
  t.mock.method(globalThis, 'fetch', async () => Response.json({...scope, kind: 'preview', state_revision: 'r', request: {...body, selection: {...body.selection, target_indices: [1, 2, 1]}}, preview: {can_confirm: true}}));
  await assert.rejects(sdk.preview(server.connection, body), sdk.ProtocolError);
});
for (const [requested, echoed] of [[undefined, true], [true, true], [false, false], [false, true], [true, false], [undefined, false]] as const) {
  test(`preview route preference ${requested} echoed as ${echoed}`, async t => {
    const selection: sdk.ActionSelection = {action_index: 0, target_indices: [0]};
    if (requested !== undefined) selection.prefer_safe = requested;
    const body: sdk.PreviewRequest = {actor_uuid: uuid, state_revision: 'r', discovery_generation: 1, correlation_id: uuid, selection};
    const server = peer(t, []);
    t.mock.method(globalThis, 'fetch', async (_input: string, options: RequestInit) => {
      assert.deepEqual(JSON.parse(options.body as string), body);
      return Response.json({...scope, kind: 'preview', state_revision: 'r',
        request: {...body, selection: {...selection, prefer_safe: echoed}}, preview: {can_confirm: true}});
    });
    if (echoed === (requested ?? true)) {
      const result = await sdk.preview(server.connection, body);
      assert.equal(result.request.selection.prefer_safe, echoed);
    } else {
      await assert.rejects(sdk.preview(server.connection, body), /Preview correlation mismatch/);
    }
  });
}

test('choices for a different actor are rejected', async t => {
  const body: sdk.ChoicesRequest = {actor_uuid: uuid, state_revision: 'r', force_attack: false, correlation_id: uuid}; const server = peer(t, []);
  t.mock.method(globalThis, 'fetch', async () => Response.json({...scope, kind: 'choices', state_revision: 'r', force_attack: false, correlation_id: uuid, choices: {entity_uuid: '00000000-0000-4000-8000-000000000002'}}));
  await assert.rejects(sdk.choices(server.connection, body), sdk.ProtocolError);
});
test('incomplete EOF reconnects from consumed cursor', async t => {
  const server = peer(t, [ready(1) + event('operation', operation(1), 1).slice(0, -1), ready(1) + event('operation', operation(1), 1)], initial(), undefined, true);
  const seen: number[] = []; await sdk.follow(sdk.createFollower(server.connection, async packet => {seen.push(packet.cursor.sequence);}));
  assert.deepEqual(seen, [0, 1]); assert.deepEqual(server.acks, [0, 0, 1]); assert.deepEqual(server.resumes, [0, 0]);
});
test('a command reply loss is surfaced without an automatic command retry', async t => {
  const server = peer(t, []); const sent: unknown[] = [];
  t.mock.method(globalThis, 'fetch', async (input: string, options: RequestInit) => {
    if (options.method === 'POST') {sent.push(JSON.parse(options.body as string)); throw new TypeError('reply lost');}
    assert.ok(input.endsWith('/commands/1')); return Response.json({kind: 'receipt', receipt: {...scope, kind: 'committed', command_number: 1, cursor: cursor(1)}});
  });
  const body: sdk.CommandRequest = {command_number: 1, actor_uuid: uuid, state_revision: 'r', intent: {kind: 'end_turn'}};
  await assert.rejects(sdk.submitCommand(server.connection, body), /reply lost/); const result = await sdk.receipt(server.connection, 1);
  assert.deepEqual(sent, [body]); assert.equal(result.receipt.kind, 'committed');
});
test('authenticated redirects stop visibly without a retry or body read', async t => {
  let calls = 0; let cancelled = 0;
  t.mock.method(globalThis, 'fetch', async (_input: string, options: RequestInit) => {
    calls++; assert.equal(options.redirect, 'manual'); assert.equal(options.credentials, 'omit');
    return new Response(new ReadableStream({cancel() {cancelled++;}}), {status: 302, headers: {location: 'https://other.invalid/'}});
  });
  await assert.rejects(sdk.connect('https://peer.invalid', 'credential'), /redirects are forbidden/);
  assert.equal(calls, 1); assert.equal(cancelled, 1);
});
test('safe integer limits, signed coordinates, Unicode and unknown versions/tags', () => {
  assert.deepEqual(sdk.decode('PlayerCursor', encoder.encode(JSON.stringify(cursor(Number.MAX_SAFE_INTEGER)))), cursor(Number.MAX_SAFE_INTEGER));
  assert.deepEqual(sdk.decode('InitializationResponse', encoder.encode(JSON.stringify(initial()))), initial());
  for (const sequence of [Number.MAX_SAFE_INTEGER + 1, -1, '1', true]) assert.throws(() => sdk.decode('PlayerCursor', encoder.encode(JSON.stringify({...cursor(0), sequence}))), sdk.ProtocolError);
  for (const packet of [{...operation(1), protocol: {...protocol, protocol_version: 2}}, {...operation(1), kind: 'objective'}]) assert.throws(() => sdk.decode('PlayerOperation', encoder.encode(JSON.stringify(packet))), sdk.ProtocolError);
});
test('cursor wait deadline releases its registration', async t => {
  const server = peer(t, []); const follower = sdk.createFollower(server.connection, async () => {});
  await assert.rejects(sdk.waitForCursor(follower, cursor(1), {timeout: 0}), /timed out/); assert.equal(follower.waiters.size, 0);
});
