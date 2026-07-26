import type {
  ActionResult,
  AdvanceEncounterResult,
  APIAvailableActions,
  APIEntityHandlersResponse,
  APIEquippableItems,
  CreateSessionRequest,
  CreateSessionResponse,
  ExecuteByIndexRequest,
  EquipmentMutationResult,
  EquipRequest,
  GameCreationActivateRequest,
  GameCreationActivateResponse,
  GameCreationCatalogResponse,
  GameCreationPreflightRequest,
  GameCreationStartRequest,
  GameCreationStartResponse,
  CompatibilityReport,
  ContentCatalogResponse,
  ContentManifestResponse,
  JoinGameRequest,
  JoinGameResponse,
  JsonValue,
  SessionPingResponse,
  ServerCapabilitiesResponse,
  SimpleActionRequest,
  SdkModelByName,
  SdkModelName,
  SpellCatalogResponse,
  StandaloneGameStatusResponse,
  ToggleHandlerRequest,
  ToggleHandlerResponse,
  UnequipRequest,
  WorkerSummaryEvidence,
} from "./generated/contracts.generated.js";
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

export interface DndEngineClientOptions {
  readonly fetchImplementation?: typeof fetch;
  readonly headers?: Readonly<Record<string, string>>;
}

export class DndEngineClient {
  readonly baseUrl: string;
  private readonly fetchImplementation: typeof fetch;
  private readonly defaultHeaders: Readonly<Record<string, string>>;

  constructor(
    baseUrl: string,
    options: DndEngineClientOptions = {},
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImplementation = (options.fetchImplementation ?? globalThis.fetch).bind(globalThis);
    this.defaultHeaders = Object.freeze({ ...(options.headers ?? {}) });
  }

  async getServerCapabilities(signal?: AbortSignal): Promise<ServerCapabilitiesResponse> {
    return this.getModel("ServerCapabilitiesResponse", "/server/capabilities", signal);
  }

  async getContentManifest(signal?: AbortSignal): Promise<ContentManifestResponse> {
    return this.getModel("ContentManifestResponse", "/content/manifest", signal);
  }

  async getContentCatalog(signal?: AbortSignal): Promise<ContentCatalogResponse> {
    return this.getModel("ContentCatalogResponse", "/content/catalog", signal);
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

  async activateGameCreation(
    request: GameCreationActivateRequest,
    signal?: AbortSignal,
  ): Promise<GameCreationActivateResponse> {
    return this.postModel(
      "GameCreationActivateResponse",
      "/game-creation/activate",
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

  async getSpellCatalog(signal?: AbortSignal): Promise<SpellCatalogResponse> {
    return this.getModel("SpellCatalogResponse", "/catalog/spells", signal);
  }

  async getTerminalSummary(signal?: AbortSignal): Promise<WorkerSummaryEvidence> {
    return this.getModel("WorkerSummaryEvidence", "/game/evidence/summary", signal);
  }

  async getAvailableActions(
    entityUuid: string,
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<APIAvailableActions> {
    const query = new URLSearchParams({ session_id: sessionId });
    return this.getModel(
      "APIAvailableActions",
      `/entity/${encodeURIComponent(entityUuid)}/available-actions?${query.toString()}`,
      signal,
    );
  }

  async getEquippableItems(
    entityUuid: string,
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<APIEquippableItems> {
    const query = new URLSearchParams({ session_id: sessionId });
    return this.getModel(
      "APIEquippableItems",
      `/entity/${encodeURIComponent(entityUuid)}/equippable-items?${query.toString()}`,
      signal,
    );
  }

  async getEntityHandlers(
    entityUuid: string,
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<APIEntityHandlersResponse> {
    const query = new URLSearchParams({ session_id: sessionId });
    return this.getModel(
      "APIEntityHandlersResponse",
      `/entity/${encodeURIComponent(entityUuid)}/handlers?${query.toString()}`,
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

  private headers(additional: Readonly<Record<string, string>> = {}): Record<string, string> {
    return { ...this.defaultHeaders, ...additional };
  }
}
