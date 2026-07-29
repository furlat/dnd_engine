"""Runtime deployment of built-in character fixtures for progression tests."""

from __future__ import annotations

from uuid import UUID, uuid4

from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
    BuiltinCharacterBuild,
    BuiltinSingleClassBuild,
    compose_builtin_character_revisions,
)
from dnd.content_system.character_materialization import (
    MaterializedCharacter,
    materialize_character,
)
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.core.content.materialization import CreatureDeploymentRole


def materialize_builtin_character(
    *,
    build: BuiltinCharacterBuild,
    display_name: str,
    faction: str | None,
    position: tuple[int, int],
    runtime_entity_uuid: UUID | None = None,
    deployment_role: CreatureDeploymentRole | None = None,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> MaterializedCharacter:
    """Materialize a built-in fixture through the sole schema-2 runtime path."""
    entity_uuid = runtime_entity_uuid or uuid4()
    revisions = compose_builtin_character_revisions(
        character_id=entity_uuid,
        build=build,
        content_system=runtime.require(),
    )
    return materialize_character(
        definition=revisions.definition,
        holdings=revisions.holdings,
        loadout=revisions.loadout,
        runtime_entity_uuid=entity_uuid,
        display_name=display_name,
        faction=faction,
        position=position,
        deployment_role=deployment_role or CreatureDeploymentRole(
            role_id=(
                f"builtin.{build.class_id}"
                if isinstance(build, BuiltinSingleClassBuild)
                else f"builtin.{build.premade_id or 'multiclass'}"
            ),
        ),
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
        runtime=runtime,
    )


__all__ = ["materialize_builtin_character"]
