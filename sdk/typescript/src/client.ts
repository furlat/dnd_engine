import type {
  ActionResult,
  AdvanceEncounterResult,
  APIAvailableActions,
  APIEntityHandlersResponse,
  APIEquipmentOverview,
  APIEquippableItems,
  APIGameState,
  APIItemSummary,
  APIVisibilityResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  ExecuteByIndexRequest,
  EquipmentMutationResult,
  EquipRequest,
  GameCreationCatalogResponse,
  GameCreationPreflightRequest,
  GameCreationStartRequest,
  GameCreationStartResponse,
  CompatibilityReport,
  EventHistoryResponse,
  GameEventHistoryResponse,
  JoinGameRequest,
  JoinGameResponse,
  JsonValue,
  ReplicationBootstrapResponse,
  SessionPingResponse,
  ServerCapabilitiesResponse,
  SimpleActionRequest,
  SdkModelByName,
  SdkModelName,
  SpellCatalogResponse,
  StandaloneGameStatusResponse,
  StartHumanSimulationResponse,
  ToggleHandlerRequest,
  ToggleHandlerResponse,
  UnequipRequest,
  WorkerSummaryEvidence,
} from "./generated/contracts.generated.js";
import {
  ReplicationJournal,
  type IngestResult,
  type ReplicationJournalState,
  type ResyncReason,
} from "./journal.js";
import {
  SseDecoder,
  decodeReplicationEnvelope,
  type ReplicationSseEnvelope,
} from "./sse.js";
import { decodeModel, parseJson } from "./validation.js";

export class DndHttpError extends Error {
  readonly status: number;
  readonly payload: JsonValue;

  constructor(status: number, payload: JsonValue) {
    super(`D&D engine request failed with HTTP ${status}`);
    this.name = "DndHttpError";
    this.status = status;
    this.payload = payload;
  }
}

export interface ReplicationUpdate {
  readonly envelope: ReplicationSseEnvelope;
  readonly result: IngestResult;
}

export type ReplicationConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "resyncing";

export interface ReplicationReset {
  readonly reason: "initial_bootstrap" | ResyncReason;
  readonly state: ReplicationJournalState;
}

export interface FollowReplicationOptions {
  readonly sessionId?: string;
  readonly signal?: AbortSignal;
  readonly onUpdate?: (update: ReplicationUpdate) => void | Promise<void>;
  readonly onReplicaReset?: (reset: ReplicationReset) => void | Promise<void>;
  readonly onConnectionState?: (
    state: ReplicationConnectionState,
  ) => void | Promise<void>;
  readonly initialReconnectDelayMs?: number;
  readonly maximumReconnectDelayMs?: number;
}

export interface DndEngineClientOptions {
  readonly fetchImplementation?: typeof fetch;
  readonly headers?: Readonly<Record<string, string>>;
}

export interface GameEventHistoryQuery {
  readonly fromCursor?: number;
  readonly throughCursor?: number;
  readonly eventType?: string;
  readonly phase?: string;
}

export interface EventHistoryQuery {
  readonly since?: number;
  readonly limit?: number;
  readonly eventType?: string;
  readonly phase?: string;
}

export class DndEngineClient {
  readonly baseUrl: string;
  private readonly fetchImplementation: typeof fetch;
  private readonly defaultHeaders: Readonly<Record<string, string>>;

  constructor(
    baseUrl: string,
    fetchOrOptions: typeof fetch | DndEngineClientOptions = globalThis.fetch,
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    const options = typeof fetchOrOptions === "function"
      ? { fetchImplementation: fetchOrOptions }
      : fetchOrOptions;
    this.fetchImplementation = (options.fetchImplementation ?? globalThis.fetch).bind(globalThis);
    this.defaultHeaders = Object.freeze({ ...(options.headers ?? {}) });
  }

  async bootstrap(sessionId?: string, signal?: AbortSignal): Promise<ReplicationBootstrapResponse> {
    const query = sessionId === undefined
      ? ""
      : `?session_id=${encodeURIComponent(sessionId)}`;
    return this.getModel("ReplicationBootstrapResponse", `/replication/bootstrap${query}`, signal);
  }

  async getServerCapabilities(signal?: AbortSignal): Promise<ServerCapabilitiesResponse> {
    return this.getModel("ServerCapabilitiesResponse", "/server/capabilities", signal);
  }

  async getStandaloneGameStatus(
    signal?: AbortSignal,
  ): Promise<StandaloneGameStatusResponse> {
    return this.getModel("StandaloneGameStatusResponse", "/game/status", signal);
  }

  async createSession(
    request: CreateSessionRequest,
    signal?: AbortSignal,
  ): Promise<CreateSessionResponse> {
    return this.postModel("CreateSessionResponse", "/session/create", request, signal);
  }

  async startHuman(
    characterClass: string,
    signal?: AbortSignal,
  ): Promise<StartHumanSimulationResponse> {
    const query = new URLSearchParams({ character_class: characterClass });
    return this.postModel(
      "StartHumanSimulationResponse",
      `/simulation/start-human?${query.toString()}`,
      null,
      signal,
    );
  }

  async getGameCreationCatalog(
    signal?: AbortSignal,
  ): Promise<GameCreationCatalogResponse> {
    return this.getModel("GameCreationCatalogResponse", "/game-creation/catalog", signal);
  }

  async preflightGameCreation(
    request: GameCreationPreflightRequest,
    signal?: AbortSignal,
  ): Promise<CompatibilityReport> {
    return this.postModel(
      "CompatibilityReport",
      "/game-creation/preflight",
      request,
      signal,
    );
  }

  async startGameCreation(
    request: GameCreationStartRequest,
    signal?: AbortSignal,
  ): Promise<GameCreationStartResponse> {
    return this.postModel(
      "GameCreationStartResponse",
      "/game-creation/start",
      request,
      signal,
    );
  }

  async joinGame(request: JoinGameRequest, signal?: AbortSignal): Promise<JoinGameResponse> {
    return this.postModel("JoinGameResponse", "/game/join", request, signal);
  }

  async pingSession(sessionId: string, signal?: AbortSignal): Promise<SessionPingResponse> {
    return this.postModel(
      "SessionPingResponse",
      `/session/${encodeURIComponent(sessionId)}/ping`,
      null,
      signal,
    );
  }

  async getState(signal?: AbortSignal): Promise<APIGameState> {
    return this.getModel("APIGameState", "/state", signal);
  }

  async getGameEventHistory(
    query: GameEventHistoryQuery = {},
    signal?: AbortSignal,
  ): Promise<GameEventHistoryResponse> {
    const parameters = new URLSearchParams();
    if (query.fromCursor !== undefined) parameters.set("from_cursor", String(query.fromCursor));
    if (query.throughCursor !== undefined) parameters.set("through_cursor", String(query.throughCursor));
    if (query.eventType !== undefined) parameters.set("event_type", query.eventType);
    if (query.phase !== undefined) parameters.set("phase", query.phase);
    const suffix = parameters.size === 0 ? "" : `?${parameters.toString()}`;
    return this.getModel("GameEventHistoryResponse", `/events/history${suffix}`, signal);
  }

  async getEventHistory(
    query: EventHistoryQuery = {},
    signal?: AbortSignal,
  ): Promise<EventHistoryResponse> {
    const parameters = new URLSearchParams();
    if (query.since !== undefined) parameters.set("since", String(query.since));
    if (query.limit !== undefined) parameters.set("limit", String(query.limit));
    if (query.eventType !== undefined) parameters.set("event_type", query.eventType);
    if (query.phase !== undefined) parameters.set("phase", query.phase);
    const suffix = parameters.size === 0 ? "" : `?${parameters.toString()}`;
    return this.getModel("EventHistoryResponse", `/events${suffix}`, signal);
  }

  async getVisibility(signal?: AbortSignal): Promise<APIVisibilityResponse> {
    return this.getModel("APIVisibilityResponse", "/visibility", signal);
  }

  async getSpellCatalog(signal?: AbortSignal): Promise<SpellCatalogResponse> {
    return this.getModel("SpellCatalogResponse", "/catalog/spells", signal);
  }

  async getTerminalSummary(signal?: AbortSignal): Promise<WorkerSummaryEvidence> {
    return this.getModel("WorkerSummaryEvidence", "/game/evidence/summary", signal);
  }

  async getAvailableActions(entityUuid: string, signal?: AbortSignal): Promise<APIAvailableActions> {
    return this.getModel(
      "APIAvailableActions",
      `/entity/${encodeURIComponent(entityUuid)}/available-actions`,
      signal,
    );
  }

  async getEquipment(entityUuid: string, signal?: AbortSignal): Promise<APIEquipmentOverview> {
    return this.getModel(
      "APIEquipmentOverview",
      `/entity/${encodeURIComponent(entityUuid)}/equipment`,
      signal,
    );
  }

  async getItem(
    entityUuid: string,
    itemUuid: string,
    signal?: AbortSignal,
  ): Promise<APIItemSummary> {
    return this.getModel(
      "APIItemSummary",
      `/entity/${encodeURIComponent(entityUuid)}/equipment/item/${encodeURIComponent(itemUuid)}`,
      signal,
    );
  }

  async getEquippableItems(
    entityUuid: string,
    signal?: AbortSignal,
  ): Promise<APIEquippableItems> {
    return this.getModel(
      "APIEquippableItems",
      `/entity/${encodeURIComponent(entityUuid)}/equippable-items`,
      signal,
    );
  }

  async getEntityHandlers(
    entityUuid: string,
    signal?: AbortSignal,
  ): Promise<APIEntityHandlersResponse> {
    return this.getModel(
      "APIEntityHandlersResponse",
      `/entity/${encodeURIComponent(entityUuid)}/handlers`,
      signal,
    );
  }

  async toggleEntityHandler(
    entityUuid: string,
    handlerName: string,
    request: ToggleHandlerRequest,
    signal?: AbortSignal,
  ): Promise<ToggleHandlerResponse> {
    return this.postModel(
      "ToggleHandlerResponse",
      `/entity/${encodeURIComponent(entityUuid)}/handlers/${encodeURIComponent(handlerName)}/toggle`,
      request,
      signal,
    );
  }

  async equip(
    entityUuid: string,
    request: EquipRequest,
    signal?: AbortSignal,
  ): Promise<EquipmentMutationResult> {
    return this.postModel(
      "EquipmentMutationResult",
      `/entity/${encodeURIComponent(entityUuid)}/equip`,
      request,
      signal,
    );
  }

  async unequip(
    entityUuid: string,
    request: UnequipRequest,
    signal?: AbortSignal,
  ): Promise<EquipmentMutationResult> {
    return this.postModel(
      "EquipmentMutationResult",
      `/entity/${encodeURIComponent(entityUuid)}/unequip`,
      request,
      signal,
    );
  }

  async execute(request: ExecuteByIndexRequest, signal?: AbortSignal): Promise<ActionResult> {
    return this.postModel("ActionResult", "/action/execute", request, signal);
  }

  async endTurn(request: SimpleActionRequest, signal?: AbortSignal): Promise<AdvanceEncounterResult> {
    return this.postModel("AdvanceEncounterResult", "/action/end-turn", request, signal);
  }

  async *events(
    eventCursor: number,
    combatLogCursor: number,
    sessionId?: string,
    signal?: AbortSignal,
  ): AsyncGenerator<ReplicationSseEnvelope> {
    const parameters = new URLSearchParams({
      since_event: String(eventCursor),
      since_log: String(combatLogCursor),
    });
    if (sessionId !== undefined) {
      parameters.set("session_id", sessionId);
    }
    const response = await this.fetchImplementation(
      `${this.baseUrl}/events/subscribe?${parameters.toString()}`,
      signal === undefined
        ? { headers: this.headers({ Accept: "text/event-stream" }) }
        : { headers: this.headers({ Accept: "text/event-stream" }), signal },
    );
    if (!response.ok) {
      throw await this.httpError(response);
    }
    if (response.body === null) {
      throw new Error("event stream response has no body");
    }

    const reader = response.body.getReader();
    const textDecoder = new TextDecoder();
    const sseDecoder = new SseDecoder();
    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) {
          break;
        }
        const text = textDecoder.decode(chunk.value, { stream: true });
        for (const message of sseDecoder.feed(text)) {
          yield decodeReplicationEnvelope(message);
        }
      }
      const trailing = textDecoder.decode();
      for (const message of [...sseDecoder.feed(trailing), ...sseDecoder.finish()]) {
        yield decodeReplicationEnvelope(message);
      }
    } finally {
      reader.releaseLock();
    }
  }

  async followReplication(
    journal: ReplicationJournal,
    options: FollowReplicationOptions = {},
  ): Promise<void> {
    const initialDelay = options.initialReconnectDelayMs ?? 250;
    const maximumDelay = options.maximumReconnectDelayMs ?? 5_000;
    if (!Number.isFinite(initialDelay) || initialDelay < 0) {
      throw new RangeError("initialReconnectDelayMs must be a non-negative number");
    }
    if (!Number.isFinite(maximumDelay) || maximumDelay < initialDelay) {
      throw new RangeError(
        "maximumReconnectDelayMs must be greater than or equal to initialReconnectDelayMs",
      );
    }

    let reconnectDelay = initialDelay;
    let state = journal.state();
    if (state.health !== "ready") {
      await options.onConnectionState?.("resyncing");
      state = await this.resetReplica(journal, options, "initial_bootstrap");
    }

    while (!options.signal?.aborted) {
      const authoritative = state.authoritative;
      if (authoritative === null) {
        throw new Error("replication journal failed to bootstrap");
      }
      await options.onConnectionState?.("connecting");
      let resynced = false;
      try {
        for await (const envelope of this.events(
          authoritative.eventCursor,
          authoritative.combatLogCursor,
          options.sessionId,
          options.signal,
        )) {
          if (options.signal?.aborted) return;
          reconnectDelay = initialDelay;
          await options.onConnectionState?.("connected");
          const result = journal.ingest(envelope);
          await options.onUpdate?.({ envelope, result });
          if (result.health !== "resync_required") continue;

          const reason = result.resyncReason;
          if (reason === null) {
            throw new Error("replication requested resync without a reason");
          }
          await options.onConnectionState?.("resyncing");
          state = await this.resetReplica(journal, options, reason);
          resynced = true;
          break;
        }
      } catch (error) {
        if (options.signal?.aborted) return;
        if (!isRetryableTransportError(error)) throw error;
      }

      if (options.signal?.aborted) return;
      if (resynced) continue;
      await options.onConnectionState?.("reconnecting");
      await waitForReconnect(reconnectDelay, options.signal);
      reconnectDelay = Math.min(Math.max(reconnectDelay * 2, 1), maximumDelay);
      state = journal.state();
    }
  }

  private async resetReplica(
    journal: ReplicationJournal,
    options: FollowReplicationOptions,
    reason: ReplicationReset["reason"],
  ): Promise<ReplicationJournalState> {
    const state = journal.bootstrap(
      await this.bootstrap(options.sessionId, options.signal),
    );
    if (state.health !== "ready" || state.authoritative === null) {
      throw new Error(
        `replication bootstrap failed: ${state.resyncReason ?? "unknown"}`,
      );
    }
    await options.onReplicaReset?.({ reason, state });
    return state;
  }

  private async getModel<Name extends SdkModelName>(
    name: Name,
    path: string,
    signal?: AbortSignal,
  ): Promise<SdkModelByName[Name]> {
    const response = await this.fetchImplementation(
      `${this.baseUrl}${path}`,
      signal === undefined
        ? { headers: this.headers() }
        : { headers: this.headers(), signal },
    );
    return this.decodeResponse(name, response);
  }

  private async postModel<Name extends SdkModelName, Body>(
    name: Name,
    path: string,
    body: Body,
    signal?: AbortSignal,
  ): Promise<SdkModelByName[Name]> {
    const request: RequestInit = {
      method: "POST",
      headers: this.headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
      ...(signal === undefined ? {} : { signal }),
    };
    const response = await this.fetchImplementation(`${this.baseUrl}${path}`, request);
    return this.decodeResponse(name, response);
  }

  private async decodeResponse<Name extends SdkModelName>(
    name: Name,
    response: Response,
  ): Promise<SdkModelByName[Name]> {
    const payload = parseJson(await response.text());
    if (!response.ok) {
      throw new DndHttpError(response.status, payload);
    }
    return decodeModel(name, payload);
  }

  private async httpError(response: Response): Promise<DndHttpError> {
    const text = await response.text();
    const payload: JsonValue = text.length === 0 ? null : parseJson(text);
    return new DndHttpError(response.status, payload);
  }

  private headers(additional: Readonly<Record<string, string>> = {}): Record<string, string> {
    return { ...this.defaultHeaders, ...additional };
  }
}

function isRetryableTransportError(error: unknown): boolean {
  if (error instanceof DndHttpError) {
    return error.status === 408 || error.status === 429 || error.status >= 500;
  }
  return error instanceof TypeError;
}

async function waitForReconnect(
  delayMs: number,
  signal?: AbortSignal,
): Promise<void> {
  if (delayMs <= 0) return;
  await new Promise<void>((resolve) => {
    const timeout = setTimeout(finish, delayMs);
    signal?.addEventListener("abort", finish, { once: true });

    function finish(): void {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", finish);
      resolve();
    }
  });
}
