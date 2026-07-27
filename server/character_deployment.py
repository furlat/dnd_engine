"""Projection from persistent directory heads to one engine deployment."""

from __future__ import annotations

from uuid import UUID

from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.content.durable_characters import CharacterDefinitionRevisionV2
from server.character_directory_service import CharacterDirectoryService
from server.game_directory.errors import ConflictError


def build_character_deployment_snapshot(
    service: CharacterDirectoryService,
    principal_id: UUID,
    character_id: UUID,
) -> CharacterDeploymentSnapshot:
    """Bind the exact current revision triplet and profile rules once."""

    snapshot = service.get_character_snapshot(principal_id, character_id)
    definition = snapshot.definition.definition
    if not isinstance(definition, CharacterDefinitionRevisionV2):
        raise ConflictError(
            "Character must be migrated to schema 2 before deployment",
        )
    settings = service.ensure_profile_settings(principal_id)
    if definition.ruleset_digest != settings.ruleset_digest:
        raise ConflictError(
            "Character ruleset differs from the selected profile settings",
        )
    return CharacterDeploymentSnapshot(
        character_id=character_id,
        character_row_version=snapshot.character.row_version,
        display_name=snapshot.character.display_name,
        definition=definition,
        holdings=snapshot.holdings.holdings,
        loadout=snapshot.loadout.loadout,
        expected_ruleset_digest=settings.ruleset_digest,
        multiclass_slot_rounding_policy=(
            settings.multiclass_slot_rounding_policy
        ),
        permissive_multiclass_prerequisites=(
            settings.permissive_multiclass_prerequisites
        ),
    )


__all__ = ["build_character_deployment_snapshot"]
