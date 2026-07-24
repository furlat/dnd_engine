import type {
  AttachHostedGameRequest,
  AttachHostedGameResponse,
  CharacterRecord,
  CreateCharacterRequest,
  CreateAgentGrantRequest,
  CreateAgentGrantResponse,
  CreateHostedGameRequest,
  CreateHostedGameResponse,
  FinalSummaryRecord,
  GameRecord,
  GuestPrincipalRequest,
  GuestPrincipalResponse,
  HostedGameConnection,
  HostedGameListResponse,
  ObserveHostedGameRequest,
  ObserveHostedGameResponse,
  ObjectiveReplayBundle,
  PlayerIdentityRequest,
  PlayerIdentityResponse,
  PlayerProfileResponse,
  ReconnectHostedGameRequest,
  ReconnectHostedGameResponse,
  SdkModelByName,
  SdkModelName,
  StopHostedGameRequest,
  StopHostedGameResponse,
  SubjectivePlayerReplayBundle,
} from "./generated/contracts.generated.js";
import { DndEngineClient, DndHttpError } from "./client.js";
import {
  SseDecoder,
  decodeDirectoryEnvelope,
  type DirectorySseEnvelope,
} from "./sse.js";
import { decodeModel, parseJson } from "./validation.js";
import { assertObjectiveReplay, assertSubjectivePlayerReplay } from "./replay.js";

export interface DirectoryPrincipalCredential {
  readonly principalId: string;
  readonly principalCapability: string;
}

export interface GameDirectoryClientOptions {
  readonly fetchImplementation?: typeof fetch;
}

export type DirectoryConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting";

export interface FollowGameDirectoryOptions {
  readonly credential?: DirectoryPrincipalCredential;
  readonly since?: number;
  readonly signal?: AbortSignal;
  readonly onEnvelope?: (envelope: DirectorySseEnvelope) => void | Promise<void>;
  readonly onConnectionState?: (
    state: DirectoryConnectionState,
  ) => void | Promise<void>;
  readonly initialReconnectDelayMs?: number;
  readonly maximumReconnectDelayMs?: number;
}

export class GameDirectoryClient {
  readonly baseUrl: string;
  private readonly fetchImplementation: typeof fetch;

  constructor(
    baseUrl: string,
    options: GameDirectoryClientOptions = {},
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImplementation = (options.fetchImplementation ?? globalThis.fetch).bind(globalThis);
  }

  async createGuest(
    request: GuestPrincipalRequest,
    signal?: AbortSignal,
  ): Promise<GuestPrincipalResponse> {
    return this.requestModel(
      "GuestPrincipalResponse",
      "/directory/principals/guest",
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async identifyPlayer(
    request: PlayerIdentityRequest,
    signal?: AbortSignal,
  ): Promise<PlayerIdentityResponse> {
    return this.requestModel(
      "PlayerIdentityResponse",
      "/directory/players/identify",
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async getPlayerProfile(
    credential: DirectoryPrincipalCredential,
    signal?: AbortSignal,
  ): Promise<PlayerProfileResponse> {
    return this.requestModel(
      "PlayerProfileResponse",
      "/directory/players/me",
      requestOptions("GET", signal, undefined, principalHeaders(credential)),
    );
  }

  async createCharacter(
    credential: DirectoryPrincipalCredential,
    request: CreateCharacterRequest,
    signal?: AbortSignal,
  ): Promise<CharacterRecord> {
    return this.requestModel(
      "CharacterRecord",
      "/directory/characters",
      requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)),
    );
  }

  async listGames(
    credential?: DirectoryPrincipalCredential,
    signal?: AbortSignal,
  ): Promise<HostedGameListResponse> {
    return this.requestModel(
      "HostedGameListResponse",
      "/games",
      requestOptions("GET", signal, undefined, principalHeaders(credential)),
    );
  }

  async getGame(
    gameId: string,
    credential?: DirectoryPrincipalCredential,
    signal?: AbortSignal,
  ): Promise<GameRecord> {
    return this.requestModel(
      "GameRecord",
      `/games/${encodeURIComponent(gameId)}`,
      requestOptions("GET", signal, undefined, principalHeaders(credential)),
    );
  }

  async createGame(
    request: CreateHostedGameRequest,
    signal?: AbortSignal,
  ): Promise<CreateHostedGameResponse> {
    return this.requestModel(
      "CreateHostedGameResponse",
      "/games",
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async attach(
    gameId: string,
    request: AttachHostedGameRequest,
    signal?: AbortSignal,
  ): Promise<AttachHostedGameResponse> {
    return this.requestModel(
      "AttachHostedGameResponse",
      `/games/${encodeURIComponent(gameId)}/attachments`,
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async reconnect(
    gameId: string,
    request: ReconnectHostedGameRequest,
    signal?: AbortSignal,
  ): Promise<ReconnectHostedGameResponse> {
    return this.requestModel(
      "ReconnectHostedGameResponse",
      `/games/${encodeURIComponent(gameId)}/reconnect`,
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async observe(
    gameId: string,
    request: ObserveHostedGameRequest,
    signal?: AbortSignal,
  ): Promise<ObserveHostedGameResponse> {
    return this.requestModel(
      "ObserveHostedGameResponse",
      `/games/${encodeURIComponent(gameId)}/observers`,
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async createAgentGrant(
    gameId: string,
    request: CreateAgentGrantRequest,
    signal?: AbortSignal,
  ): Promise<CreateAgentGrantResponse> {
    return this.requestModel(
      "CreateAgentGrantResponse",
      `/games/${encodeURIComponent(gameId)}/agent-grants`,
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async stopGame(
    gameId: string,
    request: StopHostedGameRequest,
    signal?: AbortSignal,
  ): Promise<StopHostedGameResponse> {
    return this.requestModel(
      "StopHostedGameResponse",
      `/games/${encodeURIComponent(gameId)}/stop`,
      requestOptions("POST", signal, JSON.stringify(request)),
    );
  }

  async getSummary(
    gameId: string,
    credential?: DirectoryPrincipalCredential,
    signal?: AbortSignal,
  ): Promise<FinalSummaryRecord> {
    return this.requestModel(
      "FinalSummaryRecord",
      `/games/${encodeURIComponent(gameId)}/summary`,
      requestOptions("GET", signal, undefined, principalHeaders(credential)),
    );
  }

  async getObjectiveReplay(
    gameId: string,
    credential: DirectoryPrincipalCredential,
    signal?: AbortSignal,
  ): Promise<ObjectiveReplayBundle> {
    const replay = await this.requestModel(
      "ObjectiveReplayBundle",
      `/games/${encodeURIComponent(gameId)}/diagnostics/objective-replay`,
      requestOptions("GET", signal, undefined, principalHeaders(credential)),
    );
    assertObjectiveReplay(replay);
    return replay;
  }

  async getSubjectiveReplay(
    gameId: string,
    membershipId: string,
    credential: DirectoryPrincipalCredential,
    signal?: AbortSignal,
  ): Promise<SubjectivePlayerReplayBundle> {
    const replay = await this.requestModel(
      "SubjectivePlayerReplayBundle",
      `/games/${encodeURIComponent(gameId)}/memberships/${encodeURIComponent(membershipId)}/replay`,
      requestOptions("GET", signal, undefined, principalHeaders(credential)),
    );
    assertSubjectivePlayerReplay(replay);
    return replay;
  }

  runtimeClient(connection: HostedGameConnection): DndEngineClient {
    return new DndEngineClient(connection.engine_base_url, {
      fetchImplementation: this.fetchImplementation,
      headers: {
        Authorization: `Bearer ${connection.runtime_token}`,
      },
    });
  }

  async *events(
    since: number,
    credential?: DirectoryPrincipalCredential,
    signal?: AbortSignal,
  ): AsyncGenerator<DirectorySseEnvelope> {
    if (!Number.isInteger(since) || since < 0) {
      throw new RangeError("directory event cursor must be a non-negative integer");
    }
    const headers = new Headers(principalHeaders(credential));
    headers.set("accept", "text/event-stream");
    const response = await this.fetchImplementation(
      `${this.baseUrl}/games/subscribe?since=${encodeURIComponent(String(since))}`,
      requestOptions("GET", signal, undefined, headers),
    );
    if (!response.ok) {
      const text = await response.text();
      throw new DndHttpError(
        response.status,
        text.length === 0 ? null : parseJson(text),
      );
    }
    if (response.body === null) {
      throw new Error("directory event stream response has no body");
    }

    const reader = response.body.getReader();
    const textDecoder = new TextDecoder();
    const sseDecoder = new SseDecoder();
    let completed = false;
    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) {
          completed = true;
          break;
        }
        const text = textDecoder.decode(chunk.value, { stream: true });
        for (const message of sseDecoder.feed(text)) {
          yield decodeDirectoryEnvelope(message);
        }
      }
      const trailing = textDecoder.decode();
      for (const message of [...sseDecoder.feed(trailing), ...sseDecoder.finish()]) {
        yield decodeDirectoryEnvelope(message);
      }
    } finally {
      if (!completed) await reader.cancel().catch(() => undefined);
      reader.releaseLock();
    }
  }

  async followGames(options: FollowGameDirectoryOptions = {}): Promise<void> {
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

    let cursor = options.since ?? 0;
    let reconnectDelay = initialDelay;
    while (!options.signal?.aborted) {
      await options.onConnectionState?.("connecting");
      const stream = this.events(
        cursor,
        options.credential,
        options.signal,
      );
      const iterator = stream[Symbol.asyncIterator]();
      try {
        while (true) {
          let next: IteratorResult<DirectorySseEnvelope>;
          try {
            next = await iterator.next();
          } catch (error) {
            if (options.signal?.aborted) return;
            if (!isRetryableDirectoryTransportError(error)) throw error;
            break;
          }
          if (next.done) break;

          const envelope = next.value;
          if (options.signal?.aborted) return;
          reconnectDelay = initialDelay;
          // Consumer callbacks are not transport operations. In particular, a
          // callback TypeError must propagate rather than trigger a reconnect.
          await options.onConnectionState?.("connected");
          if (envelope.event === "directory_event") {
            if (envelope.data.cursor <= cursor) continue;
            cursor = envelope.data.cursor;
          } else if (envelope.event === "heartbeat") {
            cursor = Math.max(cursor, envelope.data.cursor);
          }
          await options.onEnvelope?.(envelope);
          if (envelope.event === "evicted") break;
        }
      } finally {
        await iterator.return?.(undefined);
      }

      if (options.signal?.aborted) return;
      await options.onConnectionState?.("reconnecting");
      await waitForDirectoryReconnect(reconnectDelay, options.signal);
      reconnectDelay = Math.min(Math.max(reconnectDelay * 2, 1), maximumDelay);
    }
  }

  private async requestModel<Name extends SdkModelName>(
    modelName: Name,
    path: string,
    init: RequestInit,
  ): Promise<SdkModelByName[Name]> {
    const headers = new Headers(init.headers);
    if (init.body !== undefined && init.body !== null) {
      headers.set("content-type", "application/json");
    }
    headers.set("accept", "application/json");
    const response = await this.fetchImplementation(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });
    const payload = parseJson(await response.text());
    if (!response.ok) throw new DndHttpError(response.status, payload);
    return decodeModel(modelName, payload);
  }
}

function principalHeaders(
  credential: DirectoryPrincipalCredential | undefined,
): Readonly<Record<string, string>> | undefined {
  if (credential === undefined) return undefined;
  return {
    "X-Dnd-Principal-Id": credential.principalId,
    "X-Dnd-Principal-Capability": credential.principalCapability,
  };
}

function requestOptions(
  method: string,
  signal: AbortSignal | undefined,
  body?: string,
  headers?: HeadersInit,
): RequestInit {
  const options: RequestInit = { method };
  if (signal !== undefined) options.signal = signal;
  if (body !== undefined) options.body = body;
  if (headers !== undefined) options.headers = headers;
  return options;
}

function isRetryableDirectoryTransportError(error: unknown): boolean {
  if (error instanceof DndHttpError) {
    return error.status === 408 || error.status === 429 || error.status >= 500;
  }
  return error instanceof TypeError;
}

async function waitForDirectoryReconnect(
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
