"""Runtime Sorcerer actions remain executable through schema-2 composition."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellAction,
)
from dnd.actions.operations import get_available_actions
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BuiltinSingleClassBuild,
)
from tests.progression.materialization_support import (
    materialize_builtin_character,
)
from dnd.content_system.character_appearance import (
    SORCERER_HUMAN_APPEARANCE,
)
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.types.actions import spell_slot_cost_type
from dnd.core.base_actions import (
    ActionSelectionParameterKind,
)
from dnd.types.abilities import AbilityName
from dnd.entities.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def _runtime() -> Iterator[None]:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    reset_engine_runtime(grid_size=(12, 8))
    yield
    reset_engine_runtime()


def _sorcerer(*metamagic: str) -> Entity:
    return materialize_builtin_character(
        build=BuiltinSingleClassBuild(
            class_id="sorcerer",
            level=5,
            equipment_preset="dagger",
            appearance=SORCERER_HUMAN_APPEARANCE,
            asi_by_level=(
                (4, ((AbilityName.CHARISMA, 2),)),
            ),
            metamagic_choices=metamagic,
            spell_names=(
                "Fire Bolt",
                "Magic Missile",
                "Hold Person",
                "False Life",
            ),
        ),
        display_name="Schema-2 Sorcerer",
        faction="heroes",
        position=(1, 1),
    ).entity


def _action(entity: Entity, name: str):
    action = entity.get_action_template(name)
    assert action is not None
    return action


def _spell(entity: Entity, name: str) -> SpellAction:
    action = _action(entity, name)
    assert isinstance(action, SpellAction)
    return action


def test_quickened_cast_spends_its_source_resource_and_cleans_override() -> None:
    """The new materializer reaches the committed metamagic lifecycle."""

    sorcerer = _sorcerer("quickened", "twinned")
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Target",
        config=EntityConfig(position=(2, 1), faction="enemies"),
    )
    Entity.update_all_entities_senses()
    authored_magic_missile = _spell(sorcerer, "Magic Missile")

    activated = _action(sorcerer, "Quickened Spell").instantiate().apply()

    assert activated is not None and not activated.canceled
    assert sorcerer.action_economy.get_resource_current(
        "sorcery_points",
    ) == 3
    magic_missile = _spell(sorcerer, "Magic Missile")
    assert magic_missile is not authored_magic_missile
    assert authored_magic_missile.alt_cost_type is None
    assert magic_missile.alt_cost_type == "bonus_actions"
    cast = magic_missile.instantiate(
        target_entity_uuid=target.uuid,
    ).apply()
    assert cast is not None and not cast.canceled
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0
    assert sorcerer.action_economy.actions.normalized_score == 1
    assert "MetamagicActive" not in sorcerer.active_conditions
    assert _spell(sorcerer, "Magic Missile") is authored_magic_missile
    assert authored_magic_missile.alt_cost_type is None


def test_twinned_targets_only_eligible_entity_spells() -> None:
    """A schema-2 metamagic grant never retargets a self spell."""

    sorcerer = _sorcerer("quickened", "twinned")
    authored_hold_person = _spell(sorcerer, "Hold Person")
    authored_false_life = _spell(sorcerer, "False Life")

    activated = _action(sorcerer, "Twinned Spell").instantiate().apply()

    assert activated is not None and not activated.canceled
    hold_person = _spell(sorcerer, "Hold Person")
    false_life = _spell(sorcerer, "False Life")
    assert hold_person is not authored_hold_person
    assert authored_hold_person.alt_target_count is None
    assert hold_person.alt_target_count == 2
    assert false_life is authored_false_life
    assert false_life.alt_target_type is None
    assert false_life.alt_target_count is None
    assert false_life.alt_extra_costs == []


def test_distant_doubles_only_spell_range() -> None:
    """Distant Spell remains a spell-only temporary override."""

    sorcerer = _sorcerer("distant", "twinned")
    authored_fire_bolt = _spell(sorcerer, "Fire Bolt")
    dash = _action(sorcerer, "Dash")
    dash_before = dash.model_dump()

    activated = _action(sorcerer, "Distant Spell").instantiate().apply()

    assert activated is not None and not activated.canceled
    fire_bolt = _spell(sorcerer, "Fire Bolt")
    assert fire_bolt is not authored_fire_bolt
    assert authored_fire_bolt.alt_range is None
    assert fire_bolt.alt_range == 240
    assert dash.model_dump() == dash_before


def test_font_of_magic_conversions_preserve_slot_and_point_accounting() -> None:
    """Both conversion directions execute from schema-2 source-owned grants."""

    slot_to_points = _sorcerer("quickened", "twinned")
    assert slot_to_points.action_economy.consume_resource(
        "sorcery_points",
        5,
    )
    level_one = slot_to_points.action_economy.spell_slot_value(1)
    before = level_one.normalized_score
    converted = _action(
        slot_to_points,
        "Slot→SP L1",
    ).instantiate().apply()
    assert converted is not None and not converted.canceled
    assert level_one.normalized_score == before - 1
    assert slot_to_points.action_economy.get_resource_current(
        "sorcery_points",
    ) == 1

    points_to_slot = _sorcerer("quickened", "twinned")
    level_one = points_to_slot.action_economy.spell_slot_value(1)
    before = level_one.normalized_score
    points_to_slot.action_economy.consume(
        spell_slot_cost_type(1),
        1,
        "schema2_sorcerer_runtime",
    )
    assert level_one.normalized_score == before - 1
    converted = _action(
        points_to_slot,
        "2SP→Slot L1",
    ).instantiate().apply()
    assert converted is not None and not converted.canceled
    assert level_one.normalized_score == before
    assert points_to_slot.action_economy.get_resource_current(
        "sorcery_points",
    ) == 3


def test_font_of_magic_discovery_exposes_exact_level_selectors_both_directions() -> None:
    """Conversion menus never reverse-engineer levels from names or costs."""
    sorcerer = _sorcerer("quickened", "twinned")
    rows = get_available_actions(sorcerer).self_actions
    slot_to_points = tuple(
        row
        for row in rows
        if row.behavior_attribution.definition_ref.content_id
        == "action.class.sorcerer.convert_slot_to_sorcery_points"
    )
    points_to_slot = tuple(
        row
        for row in rows
        if row.behavior_attribution.definition_ref.content_id
        == "action.class.sorcerer.convert_sorcery_points_to_slot"
    )

    assert slot_to_points
    assert points_to_slot
    assert {
        (
            row.selection_parameter.kind,
            row.selection_parameter.value,
        )
        for row in slot_to_points
        if row.selection_parameter is not None
    } == {
        (ActionSelectionParameterKind.LEVEL, 1),
        (ActionSelectionParameterKind.LEVEL, 2),
        (ActionSelectionParameterKind.LEVEL, 3),
    }
    assert {
        (
            row.selection_parameter.kind,
            row.selection_parameter.value,
        )
        for row in points_to_slot
        if row.selection_parameter is not None
    } == {
        (ActionSelectionParameterKind.LEVEL, 1),
        (ActionSelectionParameterKind.LEVEL, 2),
        (ActionSelectionParameterKind.LEVEL, 3),
    }
