/** Subjective transport. Consumers own reduction and durable recording. */
import {Ajv2020} from 'ajv/dist/2020.js';
import {fullFormats} from 'ajv-formats/dist/formats.js';
import schema from './player-api-v1.schema.json' with {type: 'json'};
import identity from './protocol-identity.json' with {type: 'json'};
import type * as C from './contracts.generated.js';
export type * from './contracts.generated.js';
const MAX_BYTES = 64 * 1024 * 1024;
const ajv = new Ajv2020({strict: false, strictNumbers: true, coerceTypes: false, useDefaults: false, removeAdditional: false, inlineRefs: false, formats: fullFormats});
ajv.addSchema(schema);
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', {fatal: true});
export class ProtocolError extends Error {}
export class PlayerApiError extends Error { constructor(readonly value: C.ApiError, readonly retryAfter = 0) { super(value.code); } }
export function validate<T>(root: string, value: unknown): T {
  const validator = ajv.getSchema(schema.$id + '#/$defs/' + root);
  if (!validator) throw new ProtocolError('Unknown contract: ' + root);
  if (!validator(value)) throw new ProtocolError(root + ': ' + ajv.errorsText(validator.errors));
  if (root === 'InitializationResponse' && (value as C.InitializationResponse).cursor.sequence !== 0) throw new ProtocolError('Initialization sequence must be zero');
  if (root === 'PlayerOperation' && (value as C.PlayerOperation).cursor.sequence < 1) throw new ProtocolError('Operation sequence must be positive');
  return value as T;
}
export function decode<T>(root: string, raw: Uint8Array): T {
  if (raw.byteLength > MAX_BYTES) throw new ProtocolError('Record exceeds 64 MiB');
  let value: unknown;
  try { value = JSON.parse(decoder.decode(raw)); } catch { throw new ProtocolError('Invalid JSON record'); }
  return validate<T>(root, value);
}
function checkProtocol(value: C.ProtocolIdentity): void {
  if (value.protocol_version !== identity.protocol_version || value.player_schema_version !== identity.player_schema_version || value.schema_digest !== identity.schema_digest)
    throw new ProtocolError('Protocol/schema identity mismatch');
}
function checkScope(scope: C.StatusSnapshot, value: Pick<C.PlayerCursor, 'game_id' | 'game_epoch' | 'audience_id'>): void {
  if (scope.game_id !== value.game_id || scope.game_epoch !== value.game_epoch || scope.audience_id !== value.audience_id) throw new ProtocolError('Game/epoch/audience mismatch');
}
function checkStatus(scope: C.StatusSnapshot, value: C.StatusSnapshot): void {
  checkScope(scope, value);
  for (const cursor of [value.published_cursor, value.final_cursor, value.catch_up_cursor, value.acknowledged_cursor]) if (cursor) checkScope(scope, cursor);
}
export interface Connection {baseUrl: string; credential: string; bootstrap: C.BootstrapResponse; attachment?: C.AttachmentResponse}
function headers(connection: Connection): Record<string, string> {
  const result: Record<string, string> = {Authorization: 'Bearer ' + connection.credential};
  Object.assign(result, {'X-Game-Epoch': connection.bootstrap.status.game_epoch, 'X-Audience-Id': connection.bootstrap.status.audience_id});
  if (connection.attachment) result['X-Attachment-Epoch'] = connection.attachment.attachment_epoch;
  return result;
}
function route(connection: Connection, suffix: string): string { return '/api/v1/games/' + encodeURIComponent(connection.bootstrap.status.game_id) + '/' + suffix; }
async function rejectRedirect(response: Response): Promise<void> {
  if (response.type === 'opaqueredirect' || (response.status >= 300 && response.status < 400)) {
    await response.body?.cancel(); throw new ProtocolError('Authenticated redirects are forbidden');
  }
}
async function bytes(response: Response): Promise<Uint8Array> {
  if (!response.body) throw new ProtocolError('Response has no body');
  const reader = response.body.getReader(); const chunks: Uint8Array[] = []; let size = 0;
  try { while (true) { const next = await reader.read(); if (next.done) break; size += next.value.byteLength;
    if (size > MAX_BYTES) throw new ProtocolError('HTTP response exceeds 64 MiB'); chunks.push(next.value); } }
  finally { try { await reader.cancel(); } finally { reader.releaseLock(); } }
  const result = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; } return result;
}
function apiError(response: Response, raw: Uint8Array): PlayerApiError {
  const value = decode<C.ApiError>('ApiError', raw);
  if (value.http_status !== response.status) throw new ProtocolError('HTTP error status mismatch');
  const header = response.headers.get('retry-after');
  const after = header === null ? 0 : /^\d+$/.test(header) ? Number(header) * 1000 : Date.parse(header) - Date.now();
  return new PlayerApiError(value, Number.isNaN(after) ? 0 : Math.min(5000, Math.max(0, after)));
}
async function request<T>(connection: Connection, method: string, path: string, root: string, body?: unknown, signal?: AbortSignal): Promise<[T, Uint8Array]> {
  const response = await fetch(connection.baseUrl + path, {method, headers: {...headers(connection), ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
    credentials: 'omit', redirect: 'manual', body: body === undefined ? undefined : JSON.stringify(body), signal});
  await rejectRedirect(response);
  const raw = await bytes(response); if (!response.ok) throw apiError(response, raw);
  return [decode<T>(root, raw), raw];
}
export async function connect(baseUrl: string, credential: string, signal?: AbortSignal): Promise<Connection> {
  const response = await fetch(baseUrl.replace(/\/$/, '') + '/api/v1/bootstrap', {headers: {Authorization: 'Bearer ' + credential}, credentials: 'omit', redirect: 'manual', signal});
  await rejectRedirect(response);
  const raw = await bytes(response); if (!response.ok) throw apiError(response, raw);
  const bootstrap = decode<C.BootstrapResponse>('BootstrapResponse', raw); checkProtocol(bootstrap.protocol);
  checkStatus(bootstrap.status, bootstrap.status);
  return {baseUrl: baseUrl.replace(/\/$/, ''), credential, bootstrap};
}
export async function attach(connection: Connection, body: C.AttachmentRequest, signal?: AbortSignal): Promise<C.AttachmentResponse> {
  validate('AttachmentRequest', body);
  const [result] = await request<C.AttachmentResponse>(connection, 'POST', route(connection, 'attachment'), 'AttachmentResponse', body, signal);
  checkStatus(connection.bootstrap.status, result.status);
  if (result.acquisition_id !== body.acquisition_id) throw new ProtocolError('Attachment acquisition mismatch');
  connection.attachment = result; return result;
}
export async function status(connection: Connection, signal?: AbortSignal): Promise<C.StatusSnapshot> {
  const [result] = await request<C.StatusResponse>(connection, 'GET', route(connection, 'status'), 'StatusResponse', undefined, signal);
  checkStatus(connection.bootstrap.status, result.status); return result.status;
}
export async function choices(connection: Connection, body: C.ChoicesRequest, signal?: AbortSignal): Promise<C.ChoicesResponse> {
  validate('ChoicesRequest', body);
  const [result] = await request<C.ChoicesResponse>(connection, 'POST', route(connection, 'choices'), 'ChoicesResponse', body, signal);
  checkScope(connection.bootstrap.status, result);
  if (result.correlation_id !== body.correlation_id || result.state_revision !== body.state_revision || result.force_attack !== body.force_attack) throw new ProtocolError('Choices correlation mismatch');
  if (result.choices.entity_uuid !== body.actor_uuid) throw new ProtocolError('Choices actor mismatch');
  return result;
}
export async function preview(connection: Connection, body: C.PreviewRequest, signal?: AbortSignal): Promise<C.PreviewResponse> {
  validate('PreviewRequest', body);
  const [result] = await request<C.PreviewResponse>(connection, 'POST', route(connection, 'preview'), 'PreviewResponse', body, signal);
  checkScope(connection.bootstrap.status, result);
  const echoed = result.request;
  if (result.state_revision !== body.state_revision || echoed.state_revision !== body.state_revision || echoed.correlation_id !== body.correlation_id ||
      echoed.actor_uuid !== body.actor_uuid || echoed.discovery_generation !== body.discovery_generation || echoed.selection.action_index !== body.selection.action_index ||
      JSON.stringify(echoed.selection.target_indices) !== JSON.stringify(body.selection.target_indices) ||
      JSON.stringify(echoed.selection.extra_target_positions ?? []) !== JSON.stringify(body.selection.extra_target_positions ?? [])) throw new ProtocolError('Preview correlation mismatch');
  return result;
}
export async function submitCommand(connection: Connection, body: C.CommandRequest, signal?: AbortSignal): Promise<C.ReceiptResponse> {
  validate('CommandRequest', body);
  const [result] = await request<C.ReceiptResponse>(connection, 'POST', route(connection, 'commands'), 'ReceiptResponse', body, signal);
  checkScope(connection.bootstrap.status, result.receipt);
  if (result.receipt.kind === 'committed') checkScope(connection.bootstrap.status, result.receipt.cursor);
  if (result.receipt.command_number !== body.command_number) throw new ProtocolError('Command receipt mismatch'); return result;
}
export async function receipt(connection: Connection, number: number, signal?: AbortSignal): Promise<C.ReceiptResponse> {
  const [result] = await request<C.ReceiptResponse>(connection, 'GET', route(connection, 'commands/' + number), 'ReceiptResponse', undefined, signal);
  checkScope(connection.bootstrap.status, result.receipt);
  if (result.receipt.kind === 'committed') checkScope(connection.bootstrap.status, result.receipt.cursor);
  if (result.receipt.command_number !== number) throw new ProtocolError('Command receipt mismatch'); return result;
}
async function acknowledge(connection: Connection, cursor: C.PlayerCursor, signal?: AbortSignal): Promise<void> {
  const [result] = await request<C.AckResponse>(connection, 'POST', route(connection, 'ack'), 'AckResponse', {cursor}, signal);
  checkScope(connection.bootstrap.status, result.cursor); checkScope(connection.bootstrap.status, result.catch_up_cursor);
  if (result.cursor.sequence !== cursor.sequence) throw new ProtocolError('ACK mismatch');
}
export async function content(connection: Connection, revision: string, signal?: AbortSignal): Promise<C.ContentResponse> {
  const [result] = await request<C.ContentResponse>(connection, 'GET', '/api/v1/content/' + encodeURIComponent(revision), 'ContentResponse', undefined, signal);
  if (result.revision !== revision) throw new ProtocolError('Content revision mismatch'); return result;
}
export interface SseRecord {event: string; id?: string; raw: Uint8Array}
export async function* sseRecords(chunks: AsyncIterable<Uint8Array>): AsyncGenerator<SseRecord> {
  let pending = ''; let size = 0; let data: string[] = []; let event = 'message'; let id: string | undefined;
  let skipLf = false;
  const utf8 = new TextDecoder('utf-8', {fatal: true});
  for await (const chunk of chunks) {
    try { pending += utf8.decode(chunk, {stream: true}); } catch { throw new ProtocolError('Invalid SSE UTF-8'); }
    if (skipLf && pending.length) { if (pending[0] === '\n') pending = pending.slice(1); skipLf = false; }
    while (true) {
      const match = /[\r\n]/.exec(pending);
      if (!match) { if (encoder.encode(pending).byteLength + size > MAX_BYTES + 1024) throw new ProtocolError('Oversized SSE record'); break; }
      const end = match.index; skipLf = pending[end] === '\r' && end + 1 === pending.length;
      const width = pending.slice(end, end + 2) === '\r\n' ? 2 : 1;
      const line = pending.slice(0, end); pending = pending.slice(end + width);
      if (!line) { if (data.length) yield {event, id, raw: encoder.encode(data.join('\n'))}; data = []; size = 0; event = 'message'; id = undefined; continue; }
      size += encoder.encode(line).byteLength + width;
      if (size > MAX_BYTES + 1024) throw new ProtocolError('Oversized SSE record');
      const colon = line.indexOf(':'); const field = colon < 0 ? line : line.slice(0, colon);
      let value = colon < 0 ? '' : line.slice(colon + 1); if (value.startsWith(' ')) value = value.slice(1);
      if (field === 'data') data.push(value); else if (field === 'event') event = value; else if (field === 'id' && !value.includes('\0')) id = value;
    }
  }
}
async function* chunks(body: ReadableStream<Uint8Array>): AsyncGenerator<Uint8Array> {
  const reader = body.getReader();
  try { while (true) { const next = await reader.read(); if (next.done) return; yield next.value; } }
  finally { try { await reader.cancel(); } finally { reader.releaseLock(); } }
}
async function* stream(connection: Connection, after: number, signal?: AbortSignal): AsyncGenerator<SseRecord> {
  const response = await fetch(connection.baseUrl + route(connection, 'events') + '?after=' + after, {headers: headers(connection), credentials: 'omit', redirect: 'manual', signal});
  await rejectRedirect(response);
  if (!response.ok) throw apiError(response, await bytes(response));
  if (!response.body || response.headers.get('content-type')?.split(';')[0] !== 'text/event-stream') { await response.body?.cancel(); throw new ProtocolError('Expected event stream'); }
  yield* sseRecords(chunks(response.body));
}
export type Consumer = (packet: C.InitializationResponse | C.PlayerOperation, raw: Uint8Array) => Promise<void>;
export interface Follower {connection: Connection; consumer: Consumer; consumed?: C.PlayerCursor; status?: C.StatusSnapshot;
  running: boolean; completed: boolean; failure?: unknown; waiters: Set<() => void>}
export function createFollower(connection: Connection, consumer: Consumer): Follower { return {connection, consumer, running: false, completed: false, waiters: new Set()}; }
function notify(follower: Follower): void { for (const wake of [...follower.waiters]) wake(); }
export async function waitForCursor(follower: Follower, cursor: C.PlayerCursor, options: {timeout?: number; signal?: AbortSignal} = {}): Promise<void> {
  validate('PlayerCursor', cursor); checkScope(follower.connection.bootstrap.status, cursor);
  if (follower.consumed && follower.consumed.sequence >= cursor.sequence) return;
  if (follower.waiters.size >= 64) throw new ProtocolError('Too many cursor waits');
  return new Promise<void>((resolve, reject) => {
    const finish = (error?: unknown) => { clearTimeout(timer); follower.waiters.delete(check); options.signal?.removeEventListener('abort', abort); error === undefined ? resolve() : reject(error); };
    const abort = () => finish(options.signal?.reason ?? new ProtocolError('Cancelled'));
    const check = () => {
      if (follower.consumed && follower.consumed.sequence >= cursor.sequence) finish(); else if (follower.failure !== undefined) finish(follower.failure);
      else if (follower.completed || (follower.status?.final_cursor && cursor.sequence > follower.status.final_cursor.sequence)) finish(new ProtocolError('Final cursor precedes requested cursor'));
    };
    const timer = setTimeout(() => finish(new ProtocolError('Cursor wait timed out')), options.timeout ?? 30000);
    follower.waiters.add(check); options.signal?.addEventListener('abort', abort, {once: true}); if (options.signal?.aborted) abort(); else check();
  });
}
async function delay(ms: number, signal?: AbortSignal): Promise<void> {
  signal?.throwIfAborted(); await new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal?.reason); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, ms); signal?.addEventListener('abort', abort, {once: true});
  });
}
function retryable(error: unknown): boolean { return error instanceof PlayerApiError ? error.value.retryable === true : error instanceof TypeError; }
async function consume(follower: Follower, packet: C.InitializationResponse | C.PlayerOperation, raw: Uint8Array, signal?: AbortSignal): Promise<void> {
  signal?.throwIfAborted();
  if (!signal) { await follower.consumer(packet, raw); return; }
  await new Promise<void>((resolve, reject) => {
    const abort = () => reject(signal.reason);
    signal.addEventListener('abort', abort, {once: true});
    Promise.resolve().then(() => { signal.throwIfAborted(); return follower.consumer(packet, raw); }).then(resolve, reject)
      .finally(() => signal.removeEventListener('abort', abort));
    if (signal.aborted) abort();
  });
  signal.throwIfAborted();
}
export async function follow(follower: Follower, options: {signal?: AbortSignal; reconnectTimeout?: number} = {}): Promise<void> {
  if (follower.running || follower.completed || follower.failure !== undefined) throw new ProtocolError('Follower already started or completed');
  follower.running = true; const connection = follower.connection; let retrySince: number | undefined; let attempt = 0; let iterator: AsyncGenerator<SseRecord> | undefined;
  try {
    const [initial, raw] = await request<C.InitializationResponse>(connection, 'GET', route(connection, 'initialization'), 'InitializationResponse', undefined, options.signal);
    checkProtocol(initial.protocol); checkScope(connection.bootstrap.status, initial.cursor);
    await consume(follower, initial, raw, options.signal); follower.consumed = initial.cursor; notify(follower);
    while (true) {
      let interruption: unknown;
      try { await acknowledge(connection, follower.consumed!, options.signal); iterator = stream(connection, follower.consumed!.sequence, options.signal); } catch (error) { interruption = error; }
      while (iterator && interruption === undefined) {
        let next: IteratorResult<SseRecord>;
        try { next = await iterator.next(); } catch (error) { interruption = error; break; }
        if (next.done) { interruption = new TypeError('Stream ended before final cursor'); break; }
        const {event, id, raw} = next.value;
        if (event === 'error') throw new PlayerApiError(decode<C.ApiError>('ApiError', raw));
        if (event === 'ready' || event === 'status') {
          if (event === 'ready') { const packet = decode<C.StreamReady>('StreamReady', raw); checkProtocol(packet.protocol); checkScope(connection.bootstrap.status, packet.after); checkScope(connection.bootstrap.status, packet.head);
            if (packet.after.sequence !== follower.consumed!.sequence) throw new ProtocolError('Resume cursor mismatch'); follower.status = packet.status;
          } else follower.status = decode<C.StreamStatus>('StreamStatus', raw).status;
          checkStatus(connection.bootstrap.status, follower.status); notify(follower);
        } else if (event === 'operation') {
          const packet = decode<C.PlayerOperation>('PlayerOperation', raw); checkProtocol(packet.protocol); checkScope(connection.bootstrap.status, packet.cursor);
          if (id !== String(packet.cursor.sequence)) throw new ProtocolError('SSE ID/body mismatch'); if (packet.cursor.sequence <= follower.consumed!.sequence) continue;
          if (packet.cursor.sequence !== follower.consumed!.sequence + 1) throw new ProtocolError('Non-contiguous operation');
          await consume(follower, packet, raw, options.signal); follower.consumed = packet.cursor; notify(follower);
          try { await acknowledge(connection, follower.consumed, options.signal); } catch (error) { interruption = error; }
        } else throw new ProtocolError('Unknown SSE event');
        retrySince = undefined; attempt = 0;
        if (interruption === undefined && follower.status?.final_cursor && follower.consumed!.sequence >= follower.status.final_cursor.sequence) {
          if (follower.status.boundary.lifecycle !== 'terminal') throw new PlayerApiError({kind: 'error', code: follower.status.boundary.lifecycle === 'failed' ? 'game_failed' : 'game_closed',
            http_status: follower.status.boundary.lifecycle === 'failed' ? 503 : 410, retryable: false, incident_id: follower.status.boundary.incident_id} as C.ApiError);
          follower.completed = true; return;
        }
      }
      await iterator?.return(undefined); iterator = undefined; options.signal?.throwIfAborted(); if (!retryable(interruption)) throw interruption;
      retrySince ??= performance.now(); if (performance.now() - retrySince >= (options.reconnectTimeout ?? 60000)) throw new ProtocolError('Reconnect deadline exceeded');
      let backoff = Math.min(5000, 250 * 2 ** Math.min(attempt++, 5) * (.8 + Math.random() * .4));
      if (interruption instanceof PlayerApiError && 'retry_after_ms' in interruption.value) backoff = Math.max(backoff, interruption.retryAfter, Math.min(5000, interruption.value.retry_after_ms ?? 0));
      await delay(Math.min(backoff, Math.max(0, (options.reconnectTimeout ?? 60000) - (performance.now() - retrySince))), options.signal);
    }
  } catch (error) { follower.failure = error === undefined ? new ProtocolError('Follower failed without a reason') : error; throw follower.failure; }
  finally { try { await iterator?.return(undefined); } finally { follower.running = false; notify(follower); } }
}
