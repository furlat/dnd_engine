"""Exact per-cast spell-damage contribution regressions."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellAction,
    SpellEvent,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.types.damage import DamageType
from dnd.entities.entity import Entity, EntityConfig
from tests.engine.support import create_test_entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import FireBolt, RayOfFrost


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _caster() -> Entity:
    return create_test_entity(
        name="Affinity Sorcerer",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                charisma=AbilityConfig(ability_score=18),
            ),
            position=(1, 1),
            faction="heroes",
        ),
        entity_kind_id="test.affinity_caster",
        source_id=uuid4(),
    )


def _target(*, position: tuple[int, int] = (2, 1)) -> Entity:
    return create_test_entity(
        name="Target",
        config=EntityConfig(
            position=position,
            faction="enemies",
        ),
        entity_kind_id="test.affinity_target",
        source_id=uuid4(),
    )


def _cast(spell: SpellAction, target: Entity):
    executable = spell.instantiate(target_entity_uuid=target.uuid)
    return executable.apply()


def test_matching_affinity_adds_charisma_once_per_cast_without_persisting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "dnd.core.dice._randint",
        lambda _low, high: high,
    )
    caster = _caster()
    first_target = _target()
    second_target = _target(position=(3, 1))
    contribution_id = uuid4()
    caster.spellcasting.add_spell_damage_affinity_contribution(
        contribution_id,
        damage_type=DamageType.FIRE,
        ability_name="charisma",
    )
    Entity.materialize_all_navigation(max_distance=30)

    first = _cast(
        FireBolt(source_entity_uuid=caster.uuid, template=True),
        first_target,
    )
    caster.action_economy.reset_all_costs()
    second = _cast(
        FireBolt(source_entity_uuid=caster.uuid, template=True),
        second_target,
    )

    assert isinstance(first, SpellEvent) and first.damages
    assert isinstance(second, SpellEvent) and second.damages
    assert first.damages[0].damage_bonus is not None
    assert second.damages[0].damage_bonus is not None
    assert first.damages[0].damage_bonus.normalized_score == 4
    assert second.damages[0].damage_bonus.normalized_score == 4
    assert caster.spellcasting.spell_damage_bonus.normalized_score == 0

    assert caster.spellcasting.remove_spell_damage_affinity_contribution(
        contribution_id,
    )
    caster.action_economy.reset_all_costs()
    third = _cast(
        FireBolt(source_entity_uuid=caster.uuid, template=True),
        _target(position=(4, 1)),
    )
    assert isinstance(third, SpellEvent) and third.damages
    assert third.damages[0].damage_bonus is not None
    assert third.damages[0].damage_bonus.normalized_score == 0


def test_affinity_does_not_apply_to_a_different_spell_damage_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "dnd.core.dice._randint",
        lambda _low, high: high,
    )
    caster = _caster()
    caster.spellcasting.add_spell_damage_affinity_contribution(
        uuid4(),
        damage_type=DamageType.FIRE,
        ability_name="charisma",
    )
    Entity.materialize_all_navigation(max_distance=30)

    result = _cast(
        RayOfFrost(source_entity_uuid=caster.uuid, template=True),
        _target(),
    )

    assert isinstance(result, SpellEvent) and result.damages
    assert result.damages[0].damage_bonus is not None
    assert result.damages[0].damage_bonus.normalized_score == 0


def test_one_cast_context_can_claim_a_matching_affinity_only_once() -> None:
    caster = _caster()
    caster.spellcasting.add_spell_damage_affinity_contribution(
        uuid4(),
        damage_type=DamageType.FIRE,
        ability_name="charisma",
    )
    spell = FireBolt(source_entity_uuid=caster.uuid, template=False)

    with spell.spell_execution_scope():
        spell.bind_spell_execution_lineage(uuid4())
        first = caster.get_spell_damage_bonus()
        second = caster.get_spell_damage_bonus()

    assert first.normalized_score == 4
    assert second.normalized_score == 0
