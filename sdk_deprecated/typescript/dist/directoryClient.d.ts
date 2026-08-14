import type { AdminCharacterAdvancementAwardRequest, AttachHostedGameRequest, AttachHostedGameResponse, CharacterAdvancementResponse, CharacterBuildValidationResponse, CharacterBuildVisualPreviewResponse, CharacterCreationCatalogResponse, CharacterCreationValidationRequest, CharacterDefinitionHistoryResponse, CharacterDefinitionRecord, CharacterHoldingsRecord, CharacterLevelUpRequest, CharacterListResponse, CharacterLoadoutMutationRequest, CharacterLoadoutRecord, CharacterPresentationPreferencesResponse, CharacterProfileResponse, CharacterRespecRequest, CharacterRespecSeedResponse, CharacterSnapshotResponse, CreateCharacterRequest, CreateAgentGrantRequest, CreateAgentGrantResponse, CreateHostedGameRequest, CreateHostedGameResponse, ContentCatalogResponse, ContentManifestResponse, FinalSummaryRecord, GameCreationCatalogResponse, GameCreationComposeRequest, GameCreationComposeResponse, GameCreationEncounterVisualPreviewResponse, GameCreationPreviewRequest, GameRecord, GuestPrincipalRequest, GuestPrincipalResponse, HostedGameConnection, GameHistoryListResponse, ObserveHostedGameRequest, ObserveHostedGameResponse, ObjectiveReplayBundle, PlayerIdentityRequest, PlayerIdentityResponse, ProfileSettingsRecord, ReconnectHostedGameRequest, ReconnectHostedGameResponse, ReplaceSavedEncounterRequest, ReplaceSavedEncounterRosterRequest, SaveEncounterRequest, SaveEncounterRosterRequest, SavedEncounterListResponse, SavedEncounterRecord, SavedEncounterRosterListResponse, SavedEncounterRosterRecord, StandaloneLocalProfileResponse, StopHostedGameRequest, StopHostedGameResponse, SubjectivePlayerReplayBundle, UpdateCharacterProfileSettingsRequest, UpdateCharacterPresentationPreferencesRequest } from "./generated/contracts.generated.js";
import { DndEngineClient } from "./client.js";
import { type DirectorySseEnvelope } from "./sse.js";
export interface DirectoryPrincipalCredential {
    readonly principalId: string;
    readonly principalCapability: string;
}
export interface GameDirectoryClientOptions {
    readonly fetchImplementation?: typeof fetch;
}
export type DirectoryConnectionState = "connecting" | "connected" | "reconnecting";
export interface FollowGameDirectoryOptions {
    readonly credential?: DirectoryPrincipalCredential;
    readonly since?: number;
    readonly signal?: AbortSignal;
    readonly onEnvelope?: (envelope: DirectorySseEnvelope) => void | Promise<void>;
    readonly onConnectionState?: (state: DirectoryConnectionState) => void | Promise<void>;
    readonly initialReconnectDelayMs?: number;
    readonly maximumReconnectDelayMs?: number;
}
export declare class GameDirectoryClient {
    readonly baseUrl: string;
    private readonly fetchImplementation;
    constructor(baseUrl: string, options?: GameDirectoryClientOptions);
    getContentManifest(signal?: AbortSignal): Promise<ContentManifestResponse>;
    getContentCatalog(signal?: AbortSignal): Promise<ContentCatalogResponse>;
    getCharacterCreationCatalog(signal?: AbortSignal): Promise<CharacterCreationCatalogResponse>;
    getGameCreationCatalog(signal?: AbortSignal): Promise<GameCreationCatalogResponse>;
    composeGameCreation(credential: DirectoryPrincipalCredential, request: GameCreationComposeRequest, signal?: AbortSignal): Promise<GameCreationComposeResponse>;
    previewGameCreation(credential: DirectoryPrincipalCredential, request: GameCreationPreviewRequest, signal?: AbortSignal): Promise<GameCreationEncounterVisualPreviewResponse>;
    getStandaloneLocalProfile(signal?: AbortSignal): Promise<StandaloneLocalProfileResponse>;
    createGuest(request: GuestPrincipalRequest, signal?: AbortSignal): Promise<GuestPrincipalResponse>;
    identifyPlayer(request: PlayerIdentityRequest, signal?: AbortSignal): Promise<PlayerIdentityResponse>;
    getCharacterProfile(credential: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<CharacterProfileResponse>;
    updateCharacterProfileSettings(credential: DirectoryPrincipalCredential, request: UpdateCharacterProfileSettingsRequest, signal?: AbortSignal): Promise<ProfileSettingsRecord>;
    validateCharacterBuild(credential: DirectoryPrincipalCredential, request: CharacterCreationValidationRequest, signal?: AbortSignal): Promise<CharacterBuildValidationResponse>;
    previewCharacterBuild(credential: DirectoryPrincipalCredential, request: CharacterCreationValidationRequest, signal?: AbortSignal): Promise<CharacterBuildVisualPreviewResponse>;
    createCharacter(credential: DirectoryPrincipalCredential, request: CreateCharacterRequest, signal?: AbortSignal): Promise<CharacterSnapshotResponse>;
    listCharacters(credential: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<CharacterListResponse>;
    createSavedEncounterRoster(credential: DirectoryPrincipalCredential, request: SaveEncounterRosterRequest, signal?: AbortSignal): Promise<SavedEncounterRosterRecord>;
    listSavedEncounterRosters(credential: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<SavedEncounterRosterListResponse>;
    getSavedEncounterRoster(credential: DirectoryPrincipalCredential, savedRosterId: string, signal?: AbortSignal): Promise<SavedEncounterRosterRecord>;
    replaceSavedEncounterRoster(credential: DirectoryPrincipalCredential, savedRosterId: string, request: ReplaceSavedEncounterRosterRequest, signal?: AbortSignal): Promise<SavedEncounterRosterRecord>;
    deleteSavedEncounterRoster(credential: DirectoryPrincipalCredential, savedRosterId: string, expectedRevision: number, expectedRecipeDigest: string, signal?: AbortSignal): Promise<SavedEncounterRosterRecord>;
    createSavedEncounter(credential: DirectoryPrincipalCredential, request: SaveEncounterRequest, signal?: AbortSignal): Promise<SavedEncounterRecord>;
    listSavedEncounters(credential: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<SavedEncounterListResponse>;
    getSavedEncounter(credential: DirectoryPrincipalCredential, savedEncounterId: string, signal?: AbortSignal): Promise<SavedEncounterRecord>;
    replaceSavedEncounter(credential: DirectoryPrincipalCredential, savedEncounterId: string, request: ReplaceSavedEncounterRequest, signal?: AbortSignal): Promise<SavedEncounterRecord>;
    deleteSavedEncounter(credential: DirectoryPrincipalCredential, savedEncounterId: string, expectedRevision: number, expectedRecipeDigest: string, signal?: AbortSignal): Promise<SavedEncounterRecord>;
    getCharacter(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterSnapshotResponse>;
    getCharacterDefinition(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterDefinitionRecord>;
    getCharacterDefinitionHistory(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterDefinitionHistoryResponse>;
    getCharacterHoldings(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterHoldingsRecord>;
    getCharacterLoadout(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterLoadoutRecord>;
    getCharacterPresentationPreferences(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterPresentationPreferencesResponse>;
    updateCharacterPresentationPreferences(credential: DirectoryPrincipalCredential, characterId: string, request: UpdateCharacterPresentationPreferencesRequest, signal?: AbortSignal): Promise<CharacterPresentationPreferencesResponse>;
    getCharacterAdvancement(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterAdvancementResponse>;
    grantAdminCharacterAdvancementAward(credential: DirectoryPrincipalCredential, characterId: string, request: AdminCharacterAdvancementAwardRequest, signal?: AbortSignal): Promise<CharacterAdvancementResponse>;
    validateCharacterLevelUp(credential: DirectoryPrincipalCredential, characterId: string, request: CharacterLevelUpRequest, signal?: AbortSignal): Promise<CharacterBuildValidationResponse>;
    levelUpCharacter(credential: DirectoryPrincipalCredential, characterId: string, request: CharacterLevelUpRequest, signal?: AbortSignal): Promise<CharacterSnapshotResponse>;
    validateCharacterRespec(credential: DirectoryPrincipalCredential, characterId: string, request: CharacterRespecRequest, signal?: AbortSignal): Promise<CharacterBuildValidationResponse>;
    getCharacterRespecSeed(credential: DirectoryPrincipalCredential, characterId: string, signal?: AbortSignal): Promise<CharacterRespecSeedResponse>;
    respecCharacter(credential: DirectoryPrincipalCredential, characterId: string, request: CharacterRespecRequest, signal?: AbortSignal): Promise<CharacterSnapshotResponse>;
    validateCharacterLoadout(credential: DirectoryPrincipalCredential, characterId: string, request: CharacterLoadoutMutationRequest, signal?: AbortSignal): Promise<CharacterBuildValidationResponse>;
    updateCharacterLoadout(credential: DirectoryPrincipalCredential, characterId: string, request: CharacterLoadoutMutationRequest, signal?: AbortSignal): Promise<CharacterSnapshotResponse>;
    listGames(credential?: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<GameHistoryListResponse>;
    getGame(gameId: string, credential?: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<GameRecord>;
    createGame(request: CreateHostedGameRequest, signal?: AbortSignal): Promise<CreateHostedGameResponse>;
    attach(gameId: string, request: AttachHostedGameRequest, signal?: AbortSignal): Promise<AttachHostedGameResponse>;
    reconnect(gameId: string, request: ReconnectHostedGameRequest, signal?: AbortSignal): Promise<ReconnectHostedGameResponse>;
    observe(gameId: string, request: ObserveHostedGameRequest, signal?: AbortSignal): Promise<ObserveHostedGameResponse>;
    createAgentGrant(gameId: string, request: CreateAgentGrantRequest, signal?: AbortSignal): Promise<CreateAgentGrantResponse>;
    stopGame(gameId: string, request: StopHostedGameRequest, signal?: AbortSignal): Promise<StopHostedGameResponse>;
    getSummary(gameId: string, credential?: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<FinalSummaryRecord>;
    getObjectiveReplay(gameId: string, credential: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<ObjectiveReplayBundle>;
    getSubjectiveReplay(gameId: string, membershipId: string, credential: DirectoryPrincipalCredential, signal?: AbortSignal): Promise<SubjectivePlayerReplayBundle>;
    runtimeClient(connection: HostedGameConnection): DndEngineClient;
    events(since: number, credential?: DirectoryPrincipalCredential, signal?: AbortSignal): AsyncGenerator<DirectorySseEnvelope>;
    followGames(options?: FollowGameDirectoryOptions): Promise<void>;
    private requestModel;
}
//# sourceMappingURL=directoryClient.d.ts.map