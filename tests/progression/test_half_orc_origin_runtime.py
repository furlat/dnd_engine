"""Deterministic Half-Orc Relentless Endurance regressions."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content_system.character_build_validation import (
    CharacterBuildPreview,
    CharacterGrantProvenance,
    CharacterGrantScheduleEntry,
    CharacterGrantScheduleKind,
    CharacterGrantSourceKind,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    remove_character_composition,
)
from dnd.content_system.origin_runtime_character_grant_appliers import (
    ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS,
)
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.life_types import LifeState
from dnd.core.creature_types import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.origins.half_orc import (
    HALF_ORC_RELENTLESS_ENDURANCE_DECLARATION,
    HALF_ORC_RELENTLESS_ENDURANCE_REF,
    HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
)
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _runtime() -> ContentSystemRuntime:
    runtime = ContentSystemRuntime()
    runtime.install(
        LoadedContentSystem(
            registry=FrozenContentRegistry(
                declarations={
                    HALF_ORC_RELENTLESS_ENDURANCE_REF.identity_key: (
                        HALF_ORC_RELENTLESS_ENDURANCE_DECLARATION
                    ),
                },
                recipe_presets={},
                sources={},
            ),
            packs=(),
            built_in_artifact_digest="a" * 64,
            content_set_digest="b" * 64,
            provider_only_behavior_ids=frozenset({
                HALF_ORC_RELENTLESS_ENDURANCE_REF.content_id,
            }),
        ),
    )
    return runtime


def _entity(name: str) -> Entity:
    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=1,
                        mode="maximums",
                    ),
                ],
            ),
        ),
    )


def _install(entity: Entity):
    entry = CharacterGrantScheduleEntry(
        kind=CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
        provenance=CharacterGrantProvenance(
            source_kind=CharacterGrantSourceKind.SPECIES,
            source_ref=HALF_ORC_RELENTLESS_ENDURANCE_REF,
            character_level=1,
            class_level_id=None,
            class_level=None,
            choice_id=None,
            ordinal_path=(0,),
        ),
        grant_token="species.half_orc.relentless_endurance",
        content_ref=HALF_ORC_RELENTLESS_ENDURANCE_REF,
    )
    context = BuiltinCharacterGrantContext(
        entity=entity,
        character_id=uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=(),
            automatic_grant_refs=(
                HALF_ORC_RELENTLESS_ENDURANCE_REF,
            ),
            grant_schedule=(entry,),
            final_known_spell_refs=(),
            caster_contributions=(),
            effective_spellcaster_level=0,
            normal_spell_slots=(),
        ),
        runtime=_runtime(),
    )
    return (
        context,
        ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS[
            HALF_ORC_RELENTLESS_ENDURANCE_REF.identity_key
        ](context, entry),
    )


def test_relentless_endurance_survives_once_and_recovers_on_long_rest() -> None:
    half_orc = _entity("Half-Orc")
    attacker = _entity("Attacker")
    _install(half_orc)

    first_damage = half_orc.receive_damage(
        half_orc.get_normal_hp(),
        DamageType.SLASHING,
        attacker.uuid,
    )

    assert first_damage == 9
    assert half_orc.get_normal_hp() == 1
    assert half_orc.health.life_state is LifeState.ALIVE
    assert half_orc.action_economy.get_resource_current(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    ) == 0

    half_orc.on_long_rest()
    assert half_orc.action_economy.get_resource_current(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    ) == 1


def test_relentless_endurance_does_not_prevent_massive_damage() -> None:
    half_orc = _entity("Half-Orc")
    attacker = _entity("Attacker")
    _install(half_orc)

    half_orc.receive_damage(
        half_orc.get_normal_hp() + half_orc.get_max_hp(),
        DamageType.FORCE,
        attacker.uuid,
    )

    assert half_orc.health.life_state is LifeState.DEAD
    assert half_orc.action_economy.get_resource_current(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    ) == 1


def test_relentless_endurance_cannot_prevent_a_second_lethal_packet() -> None:
    half_orc = _entity("Half-Orc")
    attacker = _entity("Attacker")
    _install(half_orc)

    half_orc.receive_damage(
        half_orc.get_normal_hp(),
        DamageType.SLASHING,
        attacker.uuid,
    )
    half_orc.receive_damage(
        1,
        DamageType.SLASHING,
        attacker.uuid,
    )

    assert half_orc.health.life_state is LifeState.DEAD


def test_relentless_endurance_receipt_removes_handler_and_resource() -> None:
    half_orc = _entity("Half-Orc")
    attacker = _entity("Attacker")
    context, receipt = _install(half_orc)

    remove_character_composition(
        half_orc,
        CharacterCompositionReceipt(
            runtime_entity_uuid=half_orc.uuid,
            character_id=context.character_id,
            grants=(receipt,),
            automatic_grant_refs=(
                HALF_ORC_RELENTLESS_ENDURANCE_REF,
            ),
        ),
    )

    assert HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE not in (
        half_orc.action_economy.resources
    )
    half_orc.receive_damage(
        half_orc.get_normal_hp(),
        DamageType.SLASHING,
        attacker.uuid,
    )
    assert half_orc.health.life_state is LifeState.DEAD
