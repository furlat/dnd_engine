import type {
  JsonValue,
  SubjectiveCombatLogFramesResponse,
  SubjectiveFramesResponse,
  SubjectiveReplicationBootstrap,
} from "./generated/contracts.generated.js";
import {
  SubjectiveReplicationJournal,
  assertCombatLogWindow,
  assertSubjectiveReplicationBootstrap,
  assertSubjectiveFramesPage,
  type SubjectiveJournalIngestResult,
  type SubjectiveReplicationJournalState,
  type SubjectiveResyncReason,
} from "./subjectiveJournal.js";
import {
  SubjectiveSseDecoder,
  SubjectiveStreamFollower,
  type SubjectiveSseEnvelope,
  type SubjectiveStreamPosition,
} from "./subjectiveSse.js";
import { ContractValidationError, decodeModel, parseJson } from "./validation.js";

export const SUBJECTIVE_REPLICATION_ROUTES = Object.freeze({
  bootstrap: "/replication/bootstrap",
  frames: "/replication/frames",
  combatLog: "/replication/combat-log",
  subscribe: "/replication/subscribe",
});

export class SubjectiveReplicationHttpError extends Error {
  readonly status: number;
  readonly payload: JsonValue;

  constructor(status: number, payload: JsonValue) {
    super(`Subjective replication request failed with HTTP ${status}`);
    this.name = "SubjectiveReplicationHttpError";
    this.status = status;
    this.payload = payload;
  }
}

export interface SubjectiveReplicationClientOptions {
  readonly fetchImplementation?: typeof fetch;
  readonly headers?: Readonly<Record<string, string>>;
}

export interface SubjectiveReplicationIdentity {
  readonly sourceStreamId: string;
  readonly generationId: string;
  readonly perspectiveEpochId: string;
}

export interface SubjectiveFramesQuery extends SubjectiveReplicationIdentity {
  readonly fromObservationCursor?: number;
  readonly limit?: number;
}

export interface SubjectiveCombatLogQuery extends SubjectiveReplicationIdentity {
  readonly fromCombatLogCursor?: number;
  readonly limit?: number;
}

export interface SubjectiveSubscribeOptions extends SubjectiveReplicationIdentity {
  readonly sessionId: string;
  readonly sourceEventCursor: number;
  readonly fromObservationCursor: number;
  readonly presentationCursor: number;
  readonly fromCombatLogCursor: number;
  readonly signal?: AbortSignal;
}

export interface SubjectiveReplicationUpdate {
  readonly envelope: SubjectiveSseEnvelope;
  readonly result: SubjectiveJournalIngestResult;
}

export interface SubjectiveReplicaReset {
  readonly reason: "initial_bootstrap" | SubjectiveResyncReason;
  readonly bootstrap: SubjectiveReplicationBootstrap;
  readonly state: SubjectiveReplicationJournalState;
}

export interface FollowSubjectiveReplicationOptions {
  readonly sessionId: string;
  readonly initialBootstrap?: SubjectiveReplicationBootstrap;
  readonly signal?: AbortSignal;
  readonly onUpdate?: (update: SubjectiveReplicationUpdate) => void | Promise<void>;
  readonly onReplicaReset?: (reset: SubjectiveReplicaReset) => void | Promise<void>;
  readonly initialReconnectDelayMs?: number;
  readonly maximumReconnectDelayMs?: number;
}

/** HTTP/SSE client for the one canonical player replication surface. */
export class SubjectiveReplicationClient {
  readonly baseUrl: string;
  private readonly fetchImplementation: typeof fetch;
  private readonly defaultHeaders: Readonly<Record<string, string>>;

  constructor(baseUrl: string, options: SubjectiveReplicationClientOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImplementation = (options.fetchImplementation ?? globalThis.fetch).bind(globalThis);
    this.defaultHeaders = Object.freeze({ ...(options.headers ?? {}) });
  }

  async bootstrap(sessionId: string, signal?: AbortSignal): Promise<SubjectiveReplicationBootstrap> {
    const parameters = new URLSearchParams({ session_id: requireNonEmpty(sessionId, "sessionId") });
    const seed = decodeModel(
      "SubjectiveReplicationBootstrap",
      await this.getJson(`${SUBJECTIVE_REPLICATION_ROUTES.bootstrap}?${parameters.toString()}`, signal),
    );
    assertSubjectiveReplicationBootstrap(seed);
    return seed;
  }

  async frames(
    sessionId: string,
    query: SubjectiveFramesQuery,
    signal?: AbortSignal,
  ): Promise<SubjectiveFramesResponse> {
    const parameters = identityParameters(sessionId, query);
    const fromObservationCursor = requireCursor(
      query.fromObservationCursor ?? 0,
      "fromObservationCursor",
    );
    parameters.set("from_observation_cursor", String(fromObservationCursor));
    appendLimit(parameters, query.limit);
    const response = decodeModel(
      "SubjectiveFramesResponse",
      await this.getJson(`${SUBJECTIVE_REPLICATION_ROUTES.frames}?${parameters.toString()}`, signal),
    );
    assertResponseIdentity(response, query, "$subjective.frames");
    assertSubjectiveFramesPage(response);
    if (response.from_watermarks.observation_cursor !== fromObservationCursor) {
      throw new ContractValidationError(
        "$subjective.frames.from_watermarks.observation_cursor",
        "response page does not start at the requested observation cursor",
      );
    }
    return response;
  }

  async combatLog(
    sessionId: string,
    query: SubjectiveCombatLogQuery,
    signal?: AbortSignal,
  ): Promise<SubjectiveCombatLogFramesResponse> {
    const parameters = identityParameters(sessionId, query);
    const fromCombatLogCursor = requireCursor(
      query.fromCombatLogCursor ?? 0,
      "fromCombatLogCursor",
    );
    parameters.set("from_combat_log_cursor", String(fromCombatLogCursor));
    appendLimit(parameters, query.limit);
    const response = decodeModel(
      "SubjectiveCombatLogFramesResponse",
      await this.getJson(`${SUBJECTIVE_REPLICATION_ROUTES.combatLog}?${parameters.toString()}`, signal),
    );
    assertResponseIdentity(response, query, "$subjective.combat_log");
    assertCombatLogWindow(response);
    if (response.from_cursor !== fromCombatLogCursor) {
      throw new ContractValidationError(
        "$subjective.combat_log.from_cursor",
        "response page does not start at the requested combat-log cursor",
      );
    }
    return response;
  }

  async *subscribe(options: SubjectiveSubscribeOptions): AsyncGenerator<SubjectiveSseEnvelope> {
    const parameters = identityParameters(options.sessionId, options);
    parameters.set(
      "from_observation_cursor",
      String(requireCursor(options.fromObservationCursor, "fromObservationCursor")),
    );
    parameters.set(
      "from_combat_log_cursor",
      String(requireCursor(options.fromCombatLogCursor, "fromCombatLogCursor")),
    );
    const response = await this.fetchImplementation(
      `${this.baseUrl}${SUBJECTIVE_REPLICATION_ROUTES.subscribe}?${parameters.toString()}`,
      {
        headers: this.headers({ Accept: "text/event-stream" }),
        ...(options.signal === undefined ? {} : { signal: options.signal }),
      },
    );
    if (!response.ok) throw await this.httpError(response);
    if (response.body === null) throw new Error("subjective replication stream has no body");

    const follower = new SubjectiveStreamFollower({
      sourceStreamId: options.sourceStreamId,
      generationId: options.generationId,
      perspectiveEpochId: options.perspectiveEpochId,
      sourceEventCursor: requireCursor(options.sourceEventCursor, "sourceEventCursor"),
      observationCursor: requireCursor(options.fromObservationCursor, "fromObservationCursor"),
      presentationCursor: requireCursor(options.presentationCursor, "presentationCursor"),
      combatLogCursor: requireCursor(options.fromCombatLogCursor, "fromCombatLogCursor"),
    });
    const reader = response.body.getReader();
    const text = new TextDecoder();
    const decoder = new SubjectiveSseDecoder();
    let completed = false;
    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) {
          completed = true;
          break;
        }
        for (const envelope of decoder.feed(text.decode(chunk.value, { stream: true }))) {
          follower.ingest(envelope);
          yield envelope;
        }
      }
      for (const envelope of decoder.feed(text.decode())) {
        follower.ingest(envelope);
        yield envelope;
      }
      for (const envelope of decoder.finish()) {
        follower.ingest(envelope);
        yield envelope;
      }
    } finally {
      if (!completed) await reader.cancel().catch(() => undefined);
      reader.releaseLock();
    }
  }

  async follow(
    journal: SubjectiveReplicationJournal,
    options: FollowSubjectiveReplicationOptions,
  ): Promise<void> {
    const initialDelay = options.initialReconnectDelayMs ?? 250;
    const maximumDelay = options.maximumReconnectDelayMs ?? 5_000;
    if (!Number.isFinite(initialDelay) || initialDelay < 0) throw new RangeError("invalid reconnect delay");
    if (!Number.isFinite(maximumDelay) || maximumDelay < initialDelay) {
      throw new RangeError("maximum reconnect delay is below the initial delay");
    }
    let delay = initialDelay;
    let state = journal.state();
    let initialBootstrap = options.initialBootstrap;
    if (initialBootstrap !== undefined) {
      assertSubjectiveReplicationBootstrap(initialBootstrap);
      if (state.health === "ready") {
        throw new ContractValidationError(
          "$subjective.follow.initial_bootstrap",
          "an initial bootstrap cannot replace an already-ready journal",
        );
      }
    }
    let pendingResetReason: "initial_bootstrap" | SubjectiveResyncReason | null =
      state.health === "ready"
        ? null
        : state.health === "uninitialized"
          ? "initial_bootstrap"
          : state.resyncReason ?? "contract_mismatch";
    replication: while (!options.signal?.aborted) {
      if (state.health !== "ready") {
        let seed: SubjectiveReplicationBootstrap;
        try {
          if (initialBootstrap !== undefined) {
            seed = initialBootstrap;
            initialBootstrap = undefined;
          } else {
            seed = await this.bootstrap(options.sessionId, options.signal);
          }
        } catch (error) {
          if (options.signal?.aborted) return;
          if (!isRetryable(error) && resyncReason(error) === null) throw error;
          await wait(delay, options.signal);
          delay = Math.min(Math.max(delay * 2, 1), maximumDelay);
          continue;
        }
        state = journal.bootstrap(seed);
        if (state.health !== "ready") {
          throw new ContractValidationError(
            "$subjective.follow.bootstrap",
            "journal rejected a bootstrap validated by the client",
          );
        }
        await options.onReplicaReset?.({
          reason: pendingResetReason ?? "contract_mismatch",
          bootstrap: seed,
          state,
        });
        if (options.signal?.aborted) return;
        pendingResetReason = null;
        delay = initialDelay;
      }

      const position = journal.streamPosition();
      const stream = this.subscribe({
        sessionId: options.sessionId,
        ...identityFromPosition(position),
        sourceEventCursor: position.sourceEventCursor,
        fromObservationCursor: position.observationCursor,
        presentationCursor: position.presentationCursor,
        fromCombatLogCursor: position.combatLogCursor,
        ...(options.signal === undefined ? {} : { signal: options.signal }),
      });
      const iterator = stream[Symbol.asyncIterator]();
      try {
        while (true) {
          let next: IteratorResult<SubjectiveSseEnvelope>;
          try {
            next = await iterator.next();
          } catch (error) {
            if (options.signal?.aborted) return;
            const reason = resyncReason(error);
            if (reason !== null) {
              pendingResetReason = reason;
              state = journal.invalidate(reason);
              continue replication;
            }
            if (!isRetryable(error)) throw error;
            break;
          }
          if (next.done) break;

          const envelope = next.value;
          delay = initialDelay;
          const result = journal.ingest(envelope);
          // Consumer callbacks are not transport or decoder operations. Their
          // failures must escape rather than reconnect from an advanced cursor.
          await options.onUpdate?.({ envelope, result });
          if (options.signal?.aborted) return;
          if (result.state.health === "resync_required") {
            pendingResetReason = result.state.resyncReason ?? "contract_mismatch";
            state = result.state;
            continue replication;
          }
        }
      } finally {
        await iterator.return?.(undefined);
      }
      if (options.signal?.aborted) return;
      await wait(delay, options.signal);
      delay = Math.min(Math.max(delay * 2, 1), maximumDelay);
    }
  }

  private async getJson(path: string, signal?: AbortSignal): Promise<JsonValue> {
    const response = await this.fetchImplementation(
      `${this.baseUrl}${path}`,
      signal === undefined ? { headers: this.headers() } : { headers: this.headers(), signal },
    );
    const payload = parseJson(await response.text());
    if (!response.ok) throw new SubjectiveReplicationHttpError(response.status, payload);
    return payload;
  }

  private async httpError(response: Response): Promise<SubjectiveReplicationHttpError> {
    const body = await response.text();
    return new SubjectiveReplicationHttpError(response.status, body === "" ? null : parseJson(body));
  }

  private headers(additional: Readonly<Record<string, string>> = {}): Record<string, string> {
    return { ...this.defaultHeaders, ...additional };
  }
}

function identityParameters(
  sessionId: string,
  identity: SubjectiveReplicationIdentity,
): URLSearchParams {
  return new URLSearchParams({
    session_id: requireNonEmpty(sessionId, "sessionId"),
    expected_source_stream_id: requireNonEmpty(identity.sourceStreamId, "sourceStreamId"),
    expected_generation_id: requireNonEmpty(identity.generationId, "generationId"),
    expected_perspective_epoch_id: requireNonEmpty(identity.perspectiveEpochId, "perspectiveEpochId"),
  });
}

function assertResponseIdentity(
  response: { readonly source_stream_id: string; readonly generation_id: string; readonly perspective_epoch_id: string },
  expected: SubjectiveReplicationIdentity,
  path: string,
): void {
  if (
    response.source_stream_id !== expected.sourceStreamId
    || response.generation_id !== expected.generationId
    || response.perspective_epoch_id !== expected.perspectiveEpochId
  ) {
    throw new ContractValidationError(path, "response identity differs from request");
  }
}

function appendLimit(parameters: URLSearchParams, limit: number | undefined): void {
  if (limit === undefined) return;
  if (!Number.isSafeInteger(limit) || limit < 1) throw new RangeError("limit must be a positive integer");
  parameters.set("limit", String(limit));
}

function identityFromPosition(position: SubjectiveStreamPosition): SubjectiveReplicationIdentity {
  return {
    sourceStreamId: position.sourceStreamId,
    generationId: position.generationId,
    perspectiveEpochId: position.perspectiveEpochId,
  };
}

function requireCursor(value: number, name: string): number {
  if (!Number.isSafeInteger(value) || value < 0) throw new RangeError(`${name} must be a non-negative cursor`);
  return value;
}

function requireNonEmpty(value: string, name: string): string {
  if (value.trim() === "") throw new TypeError(`${name} must be non-empty`);
  return value;
}

function isRetryable(error: unknown): boolean {
  return error instanceof TypeError
    || (error instanceof SubjectiveReplicationHttpError
      && (error.status === 408 || error.status === 429 || error.status >= 500));
}

function resyncReason(error: unknown): SubjectiveResyncReason | null {
  if (error instanceof ContractValidationError || error instanceof SyntaxError) return "contract_mismatch";
  if (!(error instanceof SubjectiveReplicationHttpError) || error.status !== 409) return null;
  const code = errorCode(error.payload);
  if (code === "replication_identity_changed") return "source_stream_changed";
  if (code === "replication_resync_required") return "observation_cursor_gap";
  if (code === "replication_source_unavailable" || code === "replication_partition_unavailable") {
    return "source_stream_changed";
  }
  return null;
}

function errorCode(payload: JsonValue): string | null {
  if (!isJsonObject(payload)) return null;
  const detail = payload.detail;
  if (!isJsonObject(detail)) return null;
  return typeof detail.code === "string" ? detail.code : null;
}

function isJsonObject(value: unknown): value is { readonly [key: string]: JsonValue } {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function wait(delay: number, signal?: AbortSignal): Promise<void> {
  if (delay <= 0) return;
  await new Promise<void>((resolve) => {
    const timeout = setTimeout(done, delay);
    signal?.addEventListener("abort", done, { once: true });
    function done(): void {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", done);
      resolve();
    }
  });
}
