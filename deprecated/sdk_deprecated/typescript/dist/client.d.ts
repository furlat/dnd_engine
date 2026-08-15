import type { ActionResult, AdvanceEncounterResult, APIAvailableActions, APIEntityHandlersResponse, APIEquippableItems, CreateSessionRequest, CreateSessionResponse, ExecuteByIndexRequest, EquipmentMutationResult, EquipRequest, GameCreationActivateRequest, GameCreationActivateResponse, GameCreationCatalogResponse, GameCreationComposeRequest, GameCreationComposeResponse, GameCreationEncounterVisualPreviewResponse, GameCreationPreviewRequest, GameCreationStartRequest, GameCreationStartResponse, ContentCatalogResponse, ContentManifestResponse, JoinGameRequest, JoinGameResponse, JsonValue, SessionPingResponse, ServerCapabilitiesResponse, SimpleActionRequest, SpellCatalogResponse, StandaloneGameStatusResponse, ToggleHandlerRequest, ToggleHandlerResponse, UnequipRequest, WorkerSummaryEvidence } from "./generated/contracts.generated.js";
export declare class DndHttpError extends Error {
    readonly status: number;
    readonly payload: JsonValue;
    constructor(status: number, payload: JsonValue);
}
export interface DndEngineClientOptions {
    readonly fetchImplementation?: typeof fetch;
    readonly headers?: Readonly<Record<string, string>>;
}
export declare class DndEngineClient {
    readonly baseUrl: string;
    private readonly fetchImplementation;
    private readonly defaultHeaders;
    constructor(baseUrl: string, options?: DndEngineClientOptions);
    getServerCapabilities(signal?: AbortSignal): Promise<ServerCapabilitiesResponse>;
    getContentManifest(signal?: AbortSignal): Promise<ContentManifestResponse>;
    getContentCatalog(signal?: AbortSignal): Promise<ContentCatalogResponse>;
    getStandaloneGameStatus(signal?: AbortSignal): Promise<StandaloneGameStatusResponse>;
    createSession(request: CreateSessionRequest, signal?: AbortSignal): Promise<CreateSessionResponse>;
    getGameCreationCatalog(signal?: AbortSignal): Promise<GameCreationCatalogResponse>;
    composeGameCreation(request: GameCreationComposeRequest, signal?: AbortSignal): Promise<GameCreationComposeResponse>;
    previewGameCreation(request: GameCreationPreviewRequest, signal?: AbortSignal): Promise<GameCreationEncounterVisualPreviewResponse>;
    startGameCreation(request: GameCreationStartRequest, signal?: AbortSignal): Promise<GameCreationStartResponse>;
    activateGameCreation(request: GameCreationActivateRequest, signal?: AbortSignal): Promise<GameCreationActivateResponse>;
    joinGame(request: JoinGameRequest, signal?: AbortSignal): Promise<JoinGameResponse>;
    pingSession(sessionId: string, signal?: AbortSignal): Promise<SessionPingResponse>;
    getSpellCatalog(signal?: AbortSignal): Promise<SpellCatalogResponse>;
    getTerminalSummary(signal?: AbortSignal): Promise<WorkerSummaryEvidence>;
    getAvailableActions(entityUuid: string, sessionId: string, signal?: AbortSignal): Promise<APIAvailableActions>;
    getEquippableItems(entityUuid: string, sessionId: string, signal?: AbortSignal): Promise<APIEquippableItems>;
    getEntityHandlers(entityUuid: string, sessionId: string, signal?: AbortSignal): Promise<APIEntityHandlersResponse>;
    toggleEntityHandler(entityUuid: string, handlerUuid: string, request: ToggleHandlerRequest, signal?: AbortSignal): Promise<ToggleHandlerResponse>;
    equip(entityUuid: string, request: EquipRequest, signal?: AbortSignal): Promise<EquipmentMutationResult>;
    unequip(entityUuid: string, request: UnequipRequest, signal?: AbortSignal): Promise<EquipmentMutationResult>;
    execute(request: ExecuteByIndexRequest, signal?: AbortSignal): Promise<ActionResult>;
    endTurn(request: SimpleActionRequest, signal?: AbortSignal): Promise<AdvanceEncounterResult>;
    private getModel;
    private postModel;
    private decodeResponse;
    private headers;
}
//# sourceMappingURL=client.d.ts.map