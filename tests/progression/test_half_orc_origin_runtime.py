"""Deterministic direct Half-Orc Relentless Endurance regressions."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.characters.origin_content import resolve_origin_transforms
from dnd.content.characters.player_body import create_player_body
from dnd.entities.creature_transforms import apply_entity_transforms, rollback_entity_transforms
from dnd.entities.entity import EntityConfig
from dnd.origins.half_orc import HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.abilities import AbilityName
from dnd.types.creatures import Background, Species
from dnd.types.damage import DamageType
from dnd.types.life import LifeState
from dnd.types.progression import AppliedOriginState
from tests.engine.support import create_test_entity


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _state() -> AppliedOriginState:
    return AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.CONSTITUTION, 1),
        ),
    )


def _half_orc():
    entity = create_test_entity(
        name="Half-Orc",
        config=EntityConfig(
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10,
                hit_dice_count=1,
                mode="maximums",
            )]),
            position=(0, 0),
            faction="heroes",
        ),
    )
    apply_entity_transforms(
        entity,
        resolve_origin_transforms(
            species=Species.HALF_ORC,
            species_variant=None,
            background=Background.ADVENTURER,
            state=_state(),
        ),
    )
    return entity


def _attacker():
    return create_test_entity(
        name="Attacker",
        config=EntityConfig(
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10,
                hit_dice_count=1,
                mode="maximums",
            )]),
            position=(1, 0),
            faction="monsters",
        ),
    )


def test_relentless_endurance_survives_once_and_recovers_on_long_rest() -> None:
    half_orc = _half_orc()
    attacker = _attacker()
    starting_hp = half_orc.get_normal_hp()

    first_damage = half_orc.receive_damage(
        starting_hp,
        DamageType.SLASHING,
        attacker.uuid,
    )

    assert first_damage == starting_hp - 1
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
    half_orc = _half_orc()
    attacker = _attacker()
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
    half_orc = _half_orc()
    attacker = _attacker()
    half_orc.receive_damage(
        half_orc.get_normal_hp(),
        DamageType.SLASHING,
        attacker.uuid,
    )
    half_orc.receive_damage(1, DamageType.SLASHING, attacker.uuid)
    assert half_orc.health.life_state is LifeState.DEAD


def test_relentless_endurance_transform_removes_handler_and_resource() -> None:
    half_orc = create_player_body(uuid4(), name="Half-Orc")
    receipts = apply_entity_transforms(
        half_orc,
        resolve_origin_transforms(
            species=Species.HALF_ORC,
            species_variant=None,
            background=Background.ADVENTURER,
            state=_state(),
        ),
    )
    assert half_orc.action_economy.has_resource(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    )

    rollback_entity_transforms(receipts)

    assert not half_orc.action_economy.has_resource(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    )
    half_orc.discard_unpublished_runtime()
