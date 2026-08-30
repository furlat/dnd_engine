"""Active parity coverage for the fourteen archived Antimagic Field groups.

This is the maintained replacement for
``to_archive/examples/test_antimagic_field.py``. The archived fixture used a
level-5 caster for an eighth-level spell, so every rule assertion ran after a
pre-cost ``None`` result. These actors declare the eighth-level slot directly.
"""

from dnd.actions import SpellEvent
from dnd.conditions import Blinded, Frightened, Poisoned
from dnd.core.condition_types import ConditionTag
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.abjuration import AntimagicField, AntimagicFieldZone
from dnd.spells.enchantment import BlessEffect
from dnd.spells.evocation import FireBolt
from dnd.spells.transmutation import Haste
from tests.engine.support import has_condition
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    reset_spell_regression_arena,
)


def _amf_caster(
    name: str = "AMF Caster",
    position: tuple[int, int] = (5, 4),
) -> Entity:
    """Create an actor with exactly the slot needed by Antimagic Field."""
    return create_spell_regression_actor(
        name,
        position,
        "heroes",
        spell_slots={8: 1},
    )


def _cast_antimagic_field(caster: Entity) -> SpellEvent:
    """Cast and assert the canonical AMF completion event."""
    result = AntimagicField(
        source_entity_uuid=caster.uuid,
        cast_at_level=8,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return result


def _add_magical_blinded(source: Entity, target: Entity) -> None:
    """Apply the representative magical condition used by suppression tests."""
    event = target.add_condition(
        Blinded(
            source_entity_uuid=source.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    assert event is not None
    assert has_condition(target, "Blinded")


def test_zone_creation() -> None:
    """Archived group 1: the ten-foot zone is centered on its caster."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    Entity.update_all_entities_senses(max_distance=100)

    _cast_antimagic_field(caster)

    assert has_condition(caster, "Concentrating")
    zone = next(
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, AntimagicFieldZone)
    )
    assert caster.position in zone.affected_positions
    assert (6, 4) in zone.affected_positions
    assert (7, 4) in zone.affected_positions
    assert (8, 4) not in zone.affected_positions


def test_spell_blocked_targeting_inside_zone() -> None:
    """Archived group 2: a spell from outside cannot target inside the field."""
    reset_spell_regression_arena(16, 9)
    amf_caster = _amf_caster()
    outside_caster = create_spell_regression_actor(
        "Outside Caster",
        (11, 4),
        "monsters",
    )
    target = create_spell_regression_actor("Inside Target", (6, 4), "heroes")
    Entity.update_all_entities_senses(max_distance=100)
    _cast_antimagic_field(amf_caster)

    result = FireBolt(
        source_entity_uuid=outside_caster.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.canceled
    assert result.status_message is not None
    assert "antimagic field" in result.status_message.lower()


def test_spell_blocked_from_inside_zone() -> None:
    """Archived group 3: a caster inside the field cannot cast outward."""
    reset_spell_regression_arena(16, 9)
    amf_caster = _amf_caster()
    inside_caster = create_spell_regression_actor(
        "Inside Caster",
        (6, 4),
        "monsters",
    )
    target = create_spell_regression_actor("Outside Target", (11, 4), "heroes")
    Entity.update_all_entities_senses(max_distance=100)
    _cast_antimagic_field(amf_caster)

    result = FireBolt(
        source_entity_uuid=inside_caster.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.canceled
    assert result.status_message is not None
    assert "antimagic field" in result.status_message.lower()


def test_suppress_existing_conditions_on_cast() -> None:
    """Archived group 4: existing magical conditions become markers on cast."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    target = create_spell_regression_actor("Inside Target", (6, 4), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    _add_magical_blinded(caster, target)

    _cast_antimagic_field(caster)

    assert not has_condition(target, "Blinded")
    assert has_condition(target, "Antimagic Suppression: Blinded")


def test_restore_conditions_on_amf_end() -> None:
    """Archived group 5: ending AMF restores its suppressed conditions."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    target = create_spell_regression_actor("Inside Target", (6, 4), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    _add_magical_blinded(caster, target)
    _cast_antimagic_field(caster)
    assert not has_condition(target, "Blinded")

    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Concentrating")
    assert not any(
        isinstance(condition, AntimagicFieldZone)
        for condition in get_map().get_spatial_conditions()
    )
    assert has_condition(target, "Blinded")
    assert not has_condition(target, "Antimagic Suppression: Blinded")


def test_suppress_on_entry_restore_on_exit() -> None:
    """Archived group 6: entity entry suppresses and exit restores."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    target = create_spell_regression_actor("Mobile Target", (11, 4), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    _add_magical_blinded(caster, target)
    _cast_antimagic_field(caster)
    assert has_condition(target, "Blinded")

    Entity.update_entity_position(target, (6, 4))
    assert not has_condition(target, "Blinded")

    Entity.update_entity_position(target, (11, 4))
    assert has_condition(target, "Blinded")


def test_caster_magical_conditions_suppressed() -> None:
    """Archived group 7: the field also suppresses magic on its caster."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    ally = create_spell_regression_actor("Blessing Ally", (11, 4), "heroes")
    Entity.update_all_entities_senses(max_distance=100)
    caster.add_condition(
        BlessEffect(
            source_entity_uuid=ally.uuid,
            target_entity_uuid=caster.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    assert has_condition(caster, "Bless")

    _cast_antimagic_field(caster)

    assert not has_condition(caster, "Bless")
    assert has_condition(caster, "Antimagic Suppression: Bless")


def test_zone_follows_caster() -> None:
    """Archived group 8: moving the caster moves the zone and restores leavers."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    target = create_spell_regression_actor("Old-zone Target", (6, 4), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    _add_magical_blinded(caster, target)
    _cast_antimagic_field(caster)
    assert not has_condition(target, "Blinded")

    Entity.update_entity_position(caster, (12, 4))

    zone = next(
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, AntimagicFieldZone)
    )
    assert zone.position == (12, 4)
    assert target.position not in zone.affected_positions
    assert has_condition(target, "Blinded")


def test_concentration_spell_suppressed_and_restored() -> None:
    """Archived group 9: suppression preserves and reconnects parent lineage."""
    reset_spell_regression_arena(16, 9)
    amf_caster = _amf_caster()
    haste_caster = create_spell_regression_actor(
        "Haste Caster",
        (10, 4),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor("Haste Target", (6, 4), "heroes")
    Entity.update_all_entities_senses(max_distance=100)
    haste_result = Haste(
        source_entity_uuid=haste_caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=3,
    ).apply()
    assert isinstance(haste_result, SpellEvent)
    assert has_condition(target, "Haste")
    assert has_condition(haste_caster, "Concentrating")

    _cast_antimagic_field(amf_caster)
    assert not has_condition(target, "Haste")
    assert has_condition(haste_caster, "Concentrating")

    amf_caster.remove_condition("Concentrating")

    assert has_condition(target, "Haste")
    concentration = haste_caster.active_conditions.get("Concentrating")
    haste_effect = target.active_conditions.get("Haste")
    assert concentration is not None
    assert haste_effect is not None
    assert (target.uuid, haste_effect.uuid) in concentration.linked_conditions


def test_haste_no_lethargy_on_suppression() -> None:
    """Archived group 10: AMF suppression does not trigger Haste lethargy."""
    reset_spell_regression_arena(16, 9)
    amf_caster = _amf_caster()
    haste_caster = create_spell_regression_actor(
        "Haste Caster",
        (10, 4),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor("Haste Target", (6, 4), "heroes")
    Entity.update_all_entities_senses(max_distance=100)
    haste_result = Haste(
        source_entity_uuid=haste_caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=3,
    ).apply()
    assert isinstance(haste_result, SpellEvent)
    assert has_condition(target, "Haste")

    _cast_antimagic_field(amf_caster)

    assert not has_condition(target, "Haste")
    assert not has_condition(target, "Haste Lethargy")
    assert target.can_take_actions()


def test_nonmagical_conditions_untouched() -> None:
    """Archived group 11: conditions without magical origin remain active."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    target = create_spell_regression_actor("Inside Target", (6, 4), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    target.add_condition(
        Poisoned(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
    )
    assert has_condition(target, "Poisoned")

    _cast_antimagic_field(caster)

    assert has_condition(target, "Poisoned")
    assert not has_condition(target, "Antimagic Suppression: Poisoned")


def test_concentrating_not_suppressed() -> None:
    """Archived group 12: AMF never suppresses the concentration owner record."""
    reset_spell_regression_arena(16, 9)
    amf_caster = _amf_caster()
    haste_caster = create_spell_regression_actor(
        "Haste Caster",
        (6, 4),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor("Haste Target", (10, 4), "heroes")
    Entity.update_all_entities_senses(max_distance=100)
    haste_result = Haste(
        source_entity_uuid=haste_caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=3,
    ).apply()
    assert isinstance(haste_result, SpellEvent)
    assert has_condition(haste_caster, "Concentrating")

    _cast_antimagic_field(amf_caster)

    assert has_condition(haste_caster, "Concentrating")
    assert not has_condition(
        haste_caster,
        "Antimagic Suppression: Concentrating",
    )


def test_multiple_conditions_suppressed() -> None:
    """Archived group 13: every magical condition is suppressed and restored."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster()
    target = create_spell_regression_actor("Inside Target", (6, 4), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    target.add_condition(
        Blinded(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    target.add_condition(
        Frightened(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    assert has_condition(target, "Blinded")
    assert has_condition(target, "Frightened")

    _cast_antimagic_field(caster)
    assert not has_condition(target, "Blinded")
    assert not has_condition(target, "Frightened")

    caster.remove_condition("Concentrating")
    assert has_condition(target, "Blinded")
    assert has_condition(target, "Frightened")


def test_zone_movement_suppress_new_entity() -> None:
    """Archived group 14: a following field suppresses newly covered entities."""
    reset_spell_regression_arena(16, 9)
    caster = _amf_caster(position=(3, 4))
    target = create_spell_regression_actor("New-zone Target", (12, 4), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    _add_magical_blinded(caster, target)
    _cast_antimagic_field(caster)
    assert has_condition(target, "Blinded")

    Entity.update_entity_position(caster, (12, 5))

    zone = next(
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, AntimagicFieldZone)
    )
    assert target.position in zone.affected_positions
    assert not has_condition(target, "Blinded")
