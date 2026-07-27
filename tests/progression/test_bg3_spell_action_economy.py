"""BG3-style spell casting composes every independently granted turn budget."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions_functional import execute_by_index, get_available_actions
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import BUILTIN_PREMADE_BUILDS
from dnd.content_system.builtin_character_materialization import (
    materialize_builtin_character,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.events import Event
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import HasteEffect


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


@pytest.fixture(scope="module")
def runtime() -> ContentSystemRuntime:
    installed = ContentSystemRuntime()
    installed.install(bootstrap_content_system())
    return installed


def _execute(
    actor: Entity,
    template_name: str,
    *,
    target_uuid: str | None = None,
) -> Event:
    available = get_available_actions(actor, legal_only=True)
    rows = [
        row
        for row in available.all_actions
        if row.template_name == template_name
    ]
    assert len(rows) == 1
    row = rows[0]
    target = (
        row.valid_targets[0]
        if target_uuid is None
        else next(
            option
            for option in row.valid_targets
            if str(option.target_uuid) == target_uuid
        )
    )
    extra_targets = (
        [target_uuid, target_uuid]
        if row.num_projectiles == 3 and target_uuid is not None
        else None
    )
    event = execute_by_index(
        actor,
        row.template_name,
        target.index,
        extra_target_uuids=extra_targets,
        available=available,
    )
    assert event is not None
    assert not event.canceled
    return event


def test_hasted_spellblade_casts_with_action_haste_surge_and_bonus_action(
    runtime: ContentSystemRuntime,
) -> None:
    """Four leveled casts consume four independent BG3-style turn budgets."""
    spellblade = materialize_builtin_character(
        build=BUILTIN_PREMADE_BUILDS[
            "hero.fighter_2_sorcerer_3_spellblade"
        ],
        display_name="Hasted Spellblade",
        faction="heroes",
        position=(2, 2),
        runtime=runtime,
    ).entity
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Durable Target",
        config=EntityConfig(
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=50,
                        mode="maximums",
                    )
                ],
            ),
            position=(3, 2),
            faction="enemies",
        ),
    )
    spellblade.add_condition(
        HasteEffect(
            source_entity_uuid=spellblade.uuid,
            target_entity_uuid=spellblade.uuid,
            caster_uuid=spellblade.uuid,
            apply_lethargy=False,
        ),
    )
    spellblade.on_turn_start()
    Entity.update_all_entities_senses()

    assert spellblade.action_economy.spell_slot_1.normalized_score == 4
    assert spellblade.action_economy.actions.normalized_score == 1
    assert spellblade.action_economy.bonus_actions.normalized_score == 1
    assert spellblade.action_economy.resources["haste_action"].current == 1
    assert spellblade.action_economy.resources["action_surge"].current == 1

    target_uuid = str(target.uuid)
    _execute(
        spellblade,
        "Magic Missile__slot_1",
        target_uuid=target_uuid,
    )
    assert spellblade.action_economy.spell_slot_1.normalized_score == 3
    assert spellblade.action_economy.actions.normalized_score == 0
    assert spellblade.action_economy.resources["haste_action"].current == 1
    _execute(
        spellblade,
        "Magic Missile__slot_1__grant_haste",
        target_uuid=target_uuid,
    )
    assert spellblade.action_economy.spell_slot_1.normalized_score == 2
    assert spellblade.action_economy.actions.normalized_score == 0
    assert spellblade.action_economy.resources["haste_action"].current == 0
    _execute(spellblade, "Action Surge")
    assert spellblade.action_economy.actions.normalized_score == 1
    assert spellblade.action_economy.resources["action_surge"].current == 0
    _execute(
        spellblade,
        "Magic Missile__slot_1",
        target_uuid=target_uuid,
    )
    assert spellblade.action_economy.spell_slot_1.normalized_score == 1
    assert spellblade.action_economy.actions.normalized_score == 0
    _execute(spellblade, "Quickened Spell")
    assert spellblade.action_economy.get_resource_current(
        "sorcery_points",
    ) == 1
    _execute(
        spellblade,
        "Magic Missile__slot_1",
        target_uuid=target_uuid,
    )

    assert spellblade.action_economy.spell_slot_1.normalized_score == 0
    assert spellblade.action_economy.actions.normalized_score == 0
    assert spellblade.action_economy.bonus_actions.normalized_score == 0
    assert spellblade.action_economy.resources["haste_action"].current == 0
    assert spellblade.action_economy.resources["action_surge"].current == 0
    assert spellblade.action_economy.get_resource_current(
        "sorcery_points",
    ) == 1
