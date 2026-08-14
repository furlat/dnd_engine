import { decodeModel, parseJson } from "./validation.js";
export class DndHttpError extends Error {
    status;
    payload;
    constructor(status, payload) {
        super(`D&D engine request failed with HTTP ${status}`);
        this.name = "DndHttpError";
        this.status = status;
        this.payload = payload;
    }
}
export class DndEngineClient {
    baseUrl;
    fetchImplementation;
    defaultHeaders;
    constructor(baseUrl, options = {}) {
        this.baseUrl = baseUrl.replace(/\/$/, "");
        this.fetchImplementation = (options.fetchImplementation ?? globalThis.fetch).bind(globalThis);
        this.defaultHeaders = Object.freeze({ ...(options.headers ?? {}) });
    }
    async getServerCapabilities(signal) {
        return this.getModel("ServerCapabilitiesResponse", "/server/capabilities", signal);
    }
    async getContentManifest(signal) {
        return this.getModel("ContentManifestResponse", "/content/manifest", signal);
    }
    async getContentCatalog(signal) {
        return this.getModel("ContentCatalogResponse", "/content/catalog", signal);
    }
    async getStandaloneGameStatus(signal) {
        return this.getModel("StandaloneGameStatusResponse", "/game/status", signal);
    }
    async createSession(request, signal) {
        return this.postModel("CreateSessionResponse", "/session/create", request, signal);
    }
    async getGameCreationCatalog(signal) {
        return this.getModel("GameCreationCatalogResponse", "/game-creation/catalog", signal);
    }
    async composeGameCreation(request, signal) {
        return this.postModel("GameCreationComposeResponse", "/game-creation/compose", request, signal);
    }
    async previewGameCreation(request, signal) {
        return this.postModel("GameCreationEncounterVisualPreviewResponse", "/game-creation/preview", request, signal);
    }
    async startGameCreation(request, signal) {
        return this.postModel("GameCreationStartResponse", "/game-creation/start", request, signal);
    }
    async activateGameCreation(request, signal) {
        return this.postModel("GameCreationActivateResponse", "/game-creation/activate", request, signal);
    }
    async joinGame(request, signal) {
        return this.postModel("JoinGameResponse", "/game/join", request, signal);
    }
    async pingSession(sessionId, signal) {
        return this.postModel("SessionPingResponse", `/session/${encodeURIComponent(sessionId)}/ping`, null, signal);
    }
    async getSpellCatalog(signal) {
        return this.getModel("SpellCatalogResponse", "/catalog/spells", signal);
    }
    async getTerminalSummary(signal) {
        return this.getModel("WorkerSummaryEvidence", "/game/evidence/summary", signal);
    }
    async getAvailableActions(entityUuid, sessionId, signal) {
        const query = new URLSearchParams({ session_id: sessionId });
        return this.getModel("APIAvailableActions", `/entity/${encodeURIComponent(entityUuid)}/available-actions?${query.toString()}`, signal);
    }
    async getEquippableItems(entityUuid, sessionId, signal) {
        const query = new URLSearchParams({ session_id: sessionId });
        return this.getModel("APIEquippableItems", `/entity/${encodeURIComponent(entityUuid)}/equippable-items?${query.toString()}`, signal);
    }
    async getEntityHandlers(entityUuid, sessionId, signal) {
        const query = new URLSearchParams({ session_id: sessionId });
        return this.getModel("APIEntityHandlersResponse", `/entity/${encodeURIComponent(entityUuid)}/handlers?${query.toString()}`, signal);
    }
    async toggleEntityHandler(entityUuid, handlerUuid, request, signal) {
        return this.postModel("ToggleHandlerResponse", `/entity/${encodeURIComponent(entityUuid)}/handlers/${encodeURIComponent(handlerUuid)}/toggle`, request, signal);
    }
    async equip(entityUuid, request, signal) {
        return this.postModel("EquipmentMutationResult", `/entity/${encodeURIComponent(entityUuid)}/equip`, request, signal);
    }
    async unequip(entityUuid, request, signal) {
        return this.postModel("EquipmentMutationResult", `/entity/${encodeURIComponent(entityUuid)}/unequip`, request, signal);
    }
    async execute(request, signal) {
        return this.postModel("ActionResult", "/action/execute", request, signal);
    }
    async endTurn(request, signal) {
        return this.postModel("AdvanceEncounterResult", "/action/end-turn", request, signal);
    }
    async getModel(name, path, signal) {
        const response = await this.fetchImplementation(`${this.baseUrl}${path}`, signal === undefined
            ? { headers: this.headers() }
            : { headers: this.headers(), signal });
        return this.decodeResponse(name, response);
    }
    async postModel(name, path, body, signal) {
        const request = {
            method: "POST",
            headers: this.headers({ "Content-Type": "application/json" }),
            body: JSON.stringify(body),
            ...(signal === undefined ? {} : { signal }),
        };
        const response = await this.fetchImplementation(`${this.baseUrl}${path}`, request);
        return this.decodeResponse(name, response);
    }
    async decodeResponse(name, response) {
        const payload = parseJson(await response.text());
        if (!response.ok) {
            throw new DndHttpError(response.status, payload);
        }
        return decodeModel(name, payload);
    }
    headers(additional = {}) {
        return { ...this.defaultHeaders, ...additional };
    }
}
//# sourceMappingURL=client.js.map