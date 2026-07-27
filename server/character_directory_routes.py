"""One FastAPI route family for every character-directory deployment."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Header, Request

from server.character_directory_contracts import (
    CharacterAdvancementResponse,
    CharacterBuildValidationRequest,
    CharacterBuildValidationResponse,
    CharacterCreationCatalogResponse,
    CharacterDefinitionHistoryResponse,
    CharacterLevelUpRequest,
    CharacterListResponse,
    CharacterLoadoutMutationRequest,
    CharacterRespecRequest,
    CharacterProfileResponse,
    CharacterSnapshotResponse,
    CreateCharacterRequest,
    UpdateCharacterProfileSettingsRequest,
)
from server.character_directory_service import CharacterDirectoryService
from server.game_directory.contracts import (
    CharacterDefinitionRecord,
    CharacterHoldingsRecord,
    CharacterLoadoutRecord,
    ProfileSettingsRecord,
)


CharacterDirectoryServiceResolver = Callable[
    [Request],
    CharacterDirectoryService,
]
CharacterDirectoryPrincipalAuthorizer = Callable[
    [Request, UUID, str],
    UUID,
]
CharacterDirectoryMutationCallback = Callable[[Request], None]


def create_character_directory_router(
    *,
    resolve_service: CharacterDirectoryServiceResolver,
    authorize_principal: CharacterDirectoryPrincipalAuthorizer,
    on_mutation: CharacterDirectoryMutationCallback | None = None,
) -> APIRouter:
    """Build the one canonical unversioned character route family."""

    router = APIRouter()

    def owner(
        request: Request,
        principal_id: UUID,
        principal_capability: str,
    ) -> UUID:
        return authorize_principal(
            request,
            principal_id,
            principal_capability,
        )

    def mutated(request: Request) -> None:
        if on_mutation is not None:
            on_mutation(request)

    @router.get(
        "/character-creation/catalog",
        response_model=CharacterCreationCatalogResponse,
    )
    async def get_character_creation_catalog(
        request: Request,
    ) -> CharacterCreationCatalogResponse:
        return resolve_service(request).build_creation_catalog()

    @router.get(
        "/directory/players/me",
        response_model=CharacterProfileResponse,
    )
    async def get_character_profile(
        request: Request,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterProfileResponse:
        return resolve_service(request).get_profile(
            owner(request, principal_id, principal_capability),
        )

    @router.put(
        "/directory/players/me/settings",
        response_model=ProfileSettingsRecord,
    )
    async def update_character_profile_settings(
        request: Request,
        body: UpdateCharacterProfileSettingsRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> ProfileSettingsRecord:
        result = resolve_service(request).update_profile_settings_request(
            owner(request, principal_id, principal_capability),
            body,
        )
        mutated(request)
        return result

    @router.post(
        "/character-builds/validate",
        response_model=CharacterBuildValidationResponse,
    )
    async def validate_character_build(
        request: Request,
        body: CharacterBuildValidationRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterBuildValidationResponse:
        return resolve_service(request).validate_new_character(
            owner(request, principal_id, principal_capability),
            body,
        )

    @router.post(
        "/directory/characters",
        response_model=CharacterSnapshotResponse,
    )
    async def create_character(
        request: Request,
        body: CreateCharacterRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterSnapshotResponse:
        result = resolve_service(request).create_character(
            owner(request, principal_id, principal_capability),
            body,
        )
        mutated(request)
        return result

    @router.get(
        "/directory/characters",
        response_model=CharacterListResponse,
    )
    async def list_characters(
        request: Request,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterListResponse:
        return resolve_service(request).list_characters(
            owner(request, principal_id, principal_capability),
        )

    @router.get(
        "/directory/characters/{character_id}",
        response_model=CharacterSnapshotResponse,
    )
    async def get_character(
        request: Request,
        character_id: UUID,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterSnapshotResponse:
        return resolve_service(request).get_character_snapshot(
            owner(request, principal_id, principal_capability),
            character_id,
        )

    @router.get(
        "/directory/characters/{character_id}/definition",
        response_model=CharacterDefinitionRecord,
    )
    async def get_character_definition(
        request: Request,
        character_id: UUID,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterDefinitionRecord:
        return resolve_service(request).get_character_snapshot(
            owner(request, principal_id, principal_capability),
            character_id,
        ).definition

    @router.get(
        "/directory/characters/{character_id}/definitions",
        response_model=CharacterDefinitionHistoryResponse,
    )
    async def get_character_definitions(
        request: Request,
        character_id: UUID,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterDefinitionHistoryResponse:
        return resolve_service(request).get_definition_history(
            owner(request, principal_id, principal_capability),
            character_id,
        )

    @router.get(
        "/directory/characters/{character_id}/holdings",
        response_model=CharacterHoldingsRecord,
    )
    async def get_character_holdings(
        request: Request,
        character_id: UUID,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterHoldingsRecord:
        return resolve_service(request).get_character_snapshot(
            owner(request, principal_id, principal_capability),
            character_id,
        ).holdings

    @router.get(
        "/directory/characters/{character_id}/loadout",
        response_model=CharacterLoadoutRecord,
    )
    async def get_character_loadout(
        request: Request,
        character_id: UUID,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterLoadoutRecord:
        return resolve_service(request).get_character_snapshot(
            owner(request, principal_id, principal_capability),
            character_id,
        ).loadout

    @router.get(
        "/directory/characters/{character_id}/advancement",
        response_model=CharacterAdvancementResponse,
    )
    async def get_character_advancement(
        request: Request,
        character_id: UUID,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterAdvancementResponse:
        return resolve_service(request).get_advancement(
            owner(request, principal_id, principal_capability),
            character_id,
        )

    @router.post(
        "/directory/characters/{character_id}/level-up/validate",
        response_model=CharacterBuildValidationResponse,
    )
    async def validate_character_level_up(
        request: Request,
        character_id: UUID,
        body: CharacterLevelUpRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterBuildValidationResponse:
        return resolve_service(request).validate_level_up(
            owner(request, principal_id, principal_capability),
            character_id,
            body,
        )

    @router.post(
        "/directory/characters/{character_id}/level-up",
        response_model=CharacterSnapshotResponse,
    )
    async def level_up_character(
        request: Request,
        character_id: UUID,
        body: CharacterLevelUpRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterSnapshotResponse:
        result = resolve_service(request).level_up(
            owner(request, principal_id, principal_capability),
            character_id,
            body,
        )
        mutated(request)
        return result

    @router.post(
        "/directory/characters/{character_id}/respec/validate",
        response_model=CharacterBuildValidationResponse,
    )
    async def validate_character_respec(
        request: Request,
        character_id: UUID,
        body: CharacterRespecRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterBuildValidationResponse:
        return resolve_service(request).validate_respec(
            owner(request, principal_id, principal_capability),
            character_id,
            body,
        )

    @router.post(
        "/directory/characters/{character_id}/respec",
        response_model=CharacterSnapshotResponse,
    )
    async def respec_character(
        request: Request,
        character_id: UUID,
        body: CharacterRespecRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterSnapshotResponse:
        result = resolve_service(request).respec(
            owner(request, principal_id, principal_capability),
            character_id,
            body,
        )
        mutated(request)
        return result

    @router.post(
        "/directory/characters/{character_id}/loadout/validate",
        response_model=CharacterBuildValidationResponse,
    )
    async def validate_character_loadout(
        request: Request,
        character_id: UUID,
        body: CharacterLoadoutMutationRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterBuildValidationResponse:
        return resolve_service(request).validate_loadout(
            owner(request, principal_id, principal_capability),
            character_id,
            body,
        )

    @router.put(
        "/directory/characters/{character_id}/loadout",
        response_model=CharacterSnapshotResponse,
    )
    async def update_character_loadout(
        request: Request,
        character_id: UUID,
        body: CharacterLoadoutMutationRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> CharacterSnapshotResponse:
        result = resolve_service(request).update_loadout(
            owner(request, principal_id, principal_capability),
            character_id,
            body,
        )
        mutated(request)
        return result

    return router
