"""Sensory spell durations and ownership through real casts."""

import pytest

from dnd.core.base_block import SenseMode, SensesType
from dnd.entity import Entity
from dnd.spells.divination import SeeInvisibility, TrueSeeing
from dnd.spells.transmutation import Barkskin, DarkvisionSpell
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, reset_spell_regression_arena,
)


@pytest.mark.parametrize("spell_type,name,rounds", (
    (DarkvisionSpell, "Darkvision", 4800),
    (SeeInvisibility, "See Invisibility", 600),
    (TrueSeeing, "True Seeing", 600),
))
def test_sensory_cast_has_full_duration_and_preserves_concentration(spell_type, name, rounds):
    reset_spell_regression_arena(8, 8)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={2: 3, 6: 1})
    Entity.update_all_entities_senses()
    bark = Barkskin(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid).apply()
    assert bark is not None and not bark.canceled
    concentration = caster.active_conditions["Concentrating"].uuid
    caster.action_economy.reset_all_costs()
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid).apply()
    assert result is not None and not result.canceled
    assert caster.active_conditions[name].duration.duration == rounds
    assert caster.active_conditions["Concentrating"].uuid == concentration
    caster.remove_condition("Concentrating")
    assert name in caster.active_conditions
    assert "Barkskin" not in caster.active_conditions


def test_darkvision_removal_preserves_innate_longer_vision():
    reset_spell_regression_arena(8, 8)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={2: 1})
    innate = SenseMode(sense_type=SensesType.DARKVISION, range_feet=120)
    caster.senses.sense_modes.append(innate)
    Entity.update_all_entities_senses()
    result = DarkvisionSpell(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid).apply()
    assert result is not None and not result.canceled
    caster.remove_condition("Darkvision")
    assert innate in caster.senses.sense_modes
    assert not any(mode.sense_type == SensesType.DARKVISION and mode.range_feet == 60
                   for mode in caster.senses.sense_modes)
