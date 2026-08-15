import { DndEngineClient, DndHttpError } from "./client.js";
import { SseDecoder, decodeDirectoryEnvelope, } from "./sse.js";
import { decodeModel, parseJson } from "./validation.js";
import { assertObjectiveReplay, assertSubjectivePlayerReplay } from "./replay.js";
export class GameDirectoryClient {
    baseUrl;
    fetchImplementation;
    constructor(baseUrl, options = {}) {
        this.baseUrl = baseUrl.replace(/\/$/, "");
        this.fetchImplementation = (options.fetchImplementation ?? globalThis.fetch).bind(globalThis);
    }
    async getContentManifest(signal) {
        return this.requestModel("ContentManifestResponse", "/content/manifest", requestOptions("GET", signal));
    }
    async getContentCatalog(signal) {
        return this.requestModel("ContentCatalogResponse", "/content/catalog", requestOptions("GET", signal));
    }
    async getCharacterCreationCatalog(signal) {
        return this.requestModel("CharacterCreationCatalogResponse", "/character-creation/catalog", requestOptions("GET", signal));
    }
    async getGameCreationCatalog(signal) {
        return this.requestModel("GameCreationCatalogResponse", "/game-creation/catalog", requestOptions("GET", signal));
    }
    async composeGameCreation(credential, request, signal) {
        return this.requestModel("GameCreationComposeResponse", "/game-creation/compose", requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async previewGameCreation(credential, request, signal) {
        return this.requestModel("GameCreationEncounterVisualPreviewResponse", "/game-creation/preview", requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async getStandaloneLocalProfile(signal) {
        return this.requestModel("StandaloneLocalProfileResponse", "/directory/local-profile", requestOptions("GET", signal));
    }
    async createGuest(request, signal) {
        return this.requestModel("GuestPrincipalResponse", "/directory/principals/guest", requestOptions("POST", signal, JSON.stringify(request)));
    }
    async identifyPlayer(request, signal) {
        return this.requestModel("PlayerIdentityResponse", "/directory/players/identify", requestOptions("POST", signal, JSON.stringify(request)));
    }
    async getCharacterProfile(credential, signal) {
        return this.requestModel("CharacterProfileResponse", "/directory/players/me", requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async updateCharacterProfileSettings(credential, request, signal) {
        return this.requestModel("ProfileSettingsRecord", "/directory/players/me/settings", requestOptions("PUT", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async validateCharacterBuild(credential, request, signal) {
        return this.requestModel("CharacterBuildValidationResponse", "/character-builds/validate", requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async previewCharacterBuild(credential, request, signal) {
        return this.requestModel("CharacterBuildVisualPreviewResponse", "/character-builds/visual-preview", requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async createCharacter(credential, request, signal) {
        return this.requestModel("CharacterSnapshotResponse", "/directory/characters", requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async listCharacters(credential, signal) {
        return this.requestModel("CharacterListResponse", "/directory/characters", requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async createSavedEncounterRoster(credential, request, signal) {
        return this.requestModel("SavedEncounterRosterRecord", "/directory/encounter-rosters", requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async listSavedEncounterRosters(credential, signal) {
        return this.requestModel("SavedEncounterRosterListResponse", "/directory/encounter-rosters", requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getSavedEncounterRoster(credential, savedRosterId, signal) {
        return this.requestModel("SavedEncounterRosterRecord", `/directory/encounter-rosters/${encodeURIComponent(savedRosterId)}`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async replaceSavedEncounterRoster(credential, savedRosterId, request, signal) {
        return this.requestModel("SavedEncounterRosterRecord", `/directory/encounter-rosters/${encodeURIComponent(savedRosterId)}`, requestOptions("PUT", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async deleteSavedEncounterRoster(credential, savedRosterId, expectedRevision, expectedRecipeDigest, signal) {
        const query = new URLSearchParams({
            expected_revision: String(expectedRevision),
            expected_recipe_digest: expectedRecipeDigest,
        });
        return this.requestModel("SavedEncounterRosterRecord", `/directory/encounter-rosters/${encodeURIComponent(savedRosterId)}?${query.toString()}`, requestOptions("DELETE", signal, undefined, principalHeaders(credential)));
    }
    async createSavedEncounter(credential, request, signal) {
        return this.requestModel("SavedEncounterRecord", "/directory/encounters", requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async listSavedEncounters(credential, signal) {
        return this.requestModel("SavedEncounterListResponse", "/directory/encounters", requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getSavedEncounter(credential, savedEncounterId, signal) {
        return this.requestModel("SavedEncounterRecord", `/directory/encounters/${encodeURIComponent(savedEncounterId)}`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async replaceSavedEncounter(credential, savedEncounterId, request, signal) {
        return this.requestModel("SavedEncounterRecord", `/directory/encounters/${encodeURIComponent(savedEncounterId)}`, requestOptions("PUT", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async deleteSavedEncounter(credential, savedEncounterId, expectedRevision, expectedRecipeDigest, signal) {
        const query = new URLSearchParams({
            expected_revision: String(expectedRevision),
            expected_recipe_digest: expectedRecipeDigest,
        });
        return this.requestModel("SavedEncounterRecord", `/directory/encounters/${encodeURIComponent(savedEncounterId)}?${query.toString()}`, requestOptions("DELETE", signal, undefined, principalHeaders(credential)));
    }
    async getCharacter(credential, characterId, signal) {
        return this.requestModel("CharacterSnapshotResponse", `/directory/characters/${encodeURIComponent(characterId)}`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getCharacterDefinition(credential, characterId, signal) {
        return this.requestModel("CharacterDefinitionRecord", `/directory/characters/${encodeURIComponent(characterId)}/definition`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getCharacterDefinitionHistory(credential, characterId, signal) {
        return this.requestModel("CharacterDefinitionHistoryResponse", `/directory/characters/${encodeURIComponent(characterId)}/definitions`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getCharacterHoldings(credential, characterId, signal) {
        return this.requestModel("CharacterHoldingsRecord", `/directory/characters/${encodeURIComponent(characterId)}/holdings`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getCharacterLoadout(credential, characterId, signal) {
        return this.requestModel("CharacterLoadoutRecord", `/directory/characters/${encodeURIComponent(characterId)}/loadout`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getCharacterPresentationPreferences(credential, characterId, signal) {
        return this.requestModel("CharacterPresentationPreferencesResponse", `/directory/characters/${encodeURIComponent(characterId)}/presentation-preferences`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async updateCharacterPresentationPreferences(credential, characterId, request, signal) {
        return this.requestModel("CharacterPresentationPreferencesResponse", `/directory/characters/${encodeURIComponent(characterId)}/presentation-preferences`, requestOptions("PUT", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async getCharacterAdvancement(credential, characterId, signal) {
        return this.requestModel("CharacterAdvancementResponse", `/directory/characters/${encodeURIComponent(characterId)}/advancement`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async grantAdminCharacterAdvancementAward(credential, characterId, request, signal) {
        return this.requestModel("CharacterAdvancementResponse", `/admin/characters/${encodeURIComponent(characterId)}/advancement-awards`, requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async validateCharacterLevelUp(credential, characterId, request, signal) {
        return this.requestModel("CharacterBuildValidationResponse", `/directory/characters/${encodeURIComponent(characterId)}/level-up/validate`, requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async levelUpCharacter(credential, characterId, request, signal) {
        return this.requestModel("CharacterSnapshotResponse", `/directory/characters/${encodeURIComponent(characterId)}/level-up`, requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async validateCharacterRespec(credential, characterId, request, signal) {
        return this.requestModel("CharacterBuildValidationResponse", `/directory/characters/${encodeURIComponent(characterId)}/respec/validate`, requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async getCharacterRespecSeed(credential, characterId, signal) {
        return this.requestModel("CharacterRespecSeedResponse", `/directory/characters/${encodeURIComponent(characterId)}/respec/seed`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async respecCharacter(credential, characterId, request, signal) {
        return this.requestModel("CharacterSnapshotResponse", `/directory/characters/${encodeURIComponent(characterId)}/respec`, requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async validateCharacterLoadout(credential, characterId, request, signal) {
        return this.requestModel("CharacterBuildValidationResponse", `/directory/characters/${encodeURIComponent(characterId)}/loadout/validate`, requestOptions("POST", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async updateCharacterLoadout(credential, characterId, request, signal) {
        return this.requestModel("CharacterSnapshotResponse", `/directory/characters/${encodeURIComponent(characterId)}/loadout`, requestOptions("PUT", signal, JSON.stringify(request), principalHeaders(credential)));
    }
    async listGames(credential, signal) {
        return this.requestModel("GameHistoryListResponse", "/games", requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getGame(gameId, credential, signal) {
        return this.requestModel("GameRecord", `/games/${encodeURIComponent(gameId)}`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async createGame(request, signal) {
        return this.requestModel("CreateHostedGameResponse", "/games", requestOptions("POST", signal, JSON.stringify(request)));
    }
    async attach(gameId, request, signal) {
        return this.requestModel("AttachHostedGameResponse", `/games/${encodeURIComponent(gameId)}/attachments`, requestOptions("POST", signal, JSON.stringify(request)));
    }
    async reconnect(gameId, request, signal) {
        return this.requestModel("ReconnectHostedGameResponse", `/games/${encodeURIComponent(gameId)}/reconnect`, requestOptions("POST", signal, JSON.stringify(request)));
    }
    async observe(gameId, request, signal) {
        return this.requestModel("ObserveHostedGameResponse", `/games/${encodeURIComponent(gameId)}/observers`, requestOptions("POST", signal, JSON.stringify(request)));
    }
    async createAgentGrant(gameId, request, signal) {
        return this.requestModel("CreateAgentGrantResponse", `/games/${encodeURIComponent(gameId)}/agent-grants`, requestOptions("POST", signal, JSON.stringify(request)));
    }
    async stopGame(gameId, request, signal) {
        return this.requestModel("StopHostedGameResponse", `/games/${encodeURIComponent(gameId)}/stop`, requestOptions("POST", signal, JSON.stringify(request)));
    }
    async getSummary(gameId, credential, signal) {
        return this.requestModel("FinalSummaryRecord", `/games/${encodeURIComponent(gameId)}/summary`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
    }
    async getObjectiveReplay(gameId, credential, signal) {
        const replay = await this.requestModel("ObjectiveReplayBundle", `/games/${encodeURIComponent(gameId)}/diagnostics/objective-replay`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
        assertObjectiveReplay(replay);
        return replay;
    }
    async getSubjectiveReplay(gameId, membershipId, credential, signal) {
        const replay = await this.requestModel("SubjectivePlayerReplayBundle", `/games/${encodeURIComponent(gameId)}/memberships/${encodeURIComponent(membershipId)}/replay`, requestOptions("GET", signal, undefined, principalHeaders(credential)));
        assertSubjectivePlayerReplay(replay);
        return replay;
    }
    runtimeClient(connection) {
        return new DndEngineClient(connection.engine_base_url, {
            fetchImplementation: this.fetchImplementation,
            headers: {
                Authorization: `Bearer ${connection.runtime_token}`,
            },
        });
    }
    async *events(since, credential, signal) {
        if (!Number.isInteger(since) || since < 0) {
            throw new RangeError("directory event cursor must be a non-negative integer");
        }
        const headers = new Headers(principalHeaders(credential));
        headers.set("accept", "text/event-stream");
        const response = await this.fetchImplementation(`${this.baseUrl}/games/subscribe?since=${encodeURIComponent(String(since))}`, requestOptions("GET", signal, undefined, headers));
        if (!response.ok) {
            const text = await response.text();
            throw new DndHttpError(response.status, text.length === 0 ? null : parseJson(text));
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
        }
        finally {
            if (!completed)
                await reader.cancel().catch(() => undefined);
            reader.releaseLock();
        }
    }
    async followGames(options = {}) {
        const initialDelay = options.initialReconnectDelayMs ?? 250;
        const maximumDelay = options.maximumReconnectDelayMs ?? 5_000;
        if (!Number.isFinite(initialDelay) || initialDelay < 0) {
            throw new RangeError("initialReconnectDelayMs must be a non-negative number");
        }
        if (!Number.isFinite(maximumDelay) || maximumDelay < initialDelay) {
            throw new RangeError("maximumReconnectDelayMs must be greater than or equal to initialReconnectDelayMs");
        }
        let cursor = options.since ?? 0;
        let reconnectDelay = initialDelay;
        while (!options.signal?.aborted) {
            await options.onConnectionState?.("connecting");
            const stream = this.events(cursor, options.credential, options.signal);
            const iterator = stream[Symbol.asyncIterator]();
            try {
                while (true) {
                    let next;
                    try {
                        next = await iterator.next();
                    }
                    catch (error) {
                        if (options.signal?.aborted)
                            return;
                        if (!isRetryableDirectoryTransportError(error))
                            throw error;
                        break;
                    }
                    if (next.done)
                        break;
                    const envelope = next.value;
                    if (options.signal?.aborted)
                        return;
                    reconnectDelay = initialDelay;
                    // Consumer callbacks are not transport operations. In particular, a
                    // callback TypeError must propagate rather than trigger a reconnect.
                    await options.onConnectionState?.("connected");
                    if (envelope.event === "directory_event") {
                        if (envelope.data.cursor <= cursor)
                            continue;
                        cursor = envelope.data.cursor;
                    }
                    else if (envelope.event === "heartbeat") {
                        cursor = Math.max(cursor, envelope.data.cursor);
                    }
                    await options.onEnvelope?.(envelope);
                    if (envelope.event === "evicted")
                        break;
                }
            }
            finally {
                await iterator.return?.(undefined);
            }
            if (options.signal?.aborted)
                return;
            await options.onConnectionState?.("reconnecting");
            await waitForDirectoryReconnect(reconnectDelay, options.signal);
            reconnectDelay = Math.min(Math.max(reconnectDelay * 2, 1), maximumDelay);
        }
    }
    async requestModel(modelName, path, init) {
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
        if (!response.ok)
            throw new DndHttpError(response.status, payload);
        return decodeModel(modelName, payload);
    }
}
function principalHeaders(credential) {
    if (credential === undefined)
        return undefined;
    return {
        "X-Dnd-Principal-Id": credential.principalId,
        "X-Dnd-Principal-Capability": credential.principalCapability,
    };
}
function requestOptions(method, signal, body, headers) {
    const options = { method };
    if (signal !== undefined)
        options.signal = signal;
    if (body !== undefined)
        options.body = body;
    if (headers !== undefined)
        options.headers = headers;
    return options;
}
function isRetryableDirectoryTransportError(error) {
    if (error instanceof DndHttpError) {
        return error.status === 408 || error.status === 429 || error.status >= 500;
    }
    return error instanceof TypeError;
}
async function waitForDirectoryReconnect(delayMs, signal) {
    if (delayMs <= 0)
        return;
    await new Promise((resolve) => {
        const timeout = setTimeout(finish, delayMs);
        signal?.addEventListener("abort", finish, { once: true });
        function finish() {
            clearTimeout(timeout);
            signal?.removeEventListener("abort", finish);
            resolve();
        }
    });
}
//# sourceMappingURL=directoryClient.js.map