"""Sneak Attack uses the resolved attack circumstance before applying damage."""

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.blocks.equipment import Weapon
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_block import LightLevel
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageRollResultEvent, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.entity import Entity, EntityConfig
from dnd.monsters.traits import register_sneak_attack
from tests.engine.support import create_test_entity, reset_combat_state


@pytest.mark.parametrize(
    ("circumstance", "adjacent_ally", "expected_damage", "packet_totals"),
    [
        pytest.param(AdvantageStatus.ADVANTAGE, False, 12, [3, 9], id="advantage-alone"),
        pytest.param(AdvantageStatus.DISADVANTAGE, True, 3, [3], id="disadvantage-with-ally"),
    ],
)
def test_sneak_attack_uses_queued_attack_circumstance(
    circumstance: AdvantageStatus,
    adjacent_ally: bool,
    expected_damage: int,
    packet_totals: list[int],
) -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 4, 4, default_light=LightLevel.BRIGHT_LIGHT)
    health = HealthConfig(
        hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=3, mode="maximums")]
    )
    attacker = create_test_entity(
        name="Spy",
        config=EntityConfig(position=(1, 1), faction="heroes", health=health),
    )
    target = create_test_entity(
        name="Guard",
        config=EntityConfig(position=(2, 1), faction="enemies", health=health),
    )
    if adjacent_ally:
        create_test_entity(
            name="Ally",
            config=EntityConfig(position=(2, 2), faction="heroes", health=health),
        )
    sword = build_authored_item("weapon.shortsword", attacker.uuid)
    assert isinstance(sword, Weapon)
    assert attacker.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    register_sneak_attack(attacker)
    attacker.equipment.melee_attack_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=attacker.uuid,
            name="Attack circumstance",
            value=circumstance,
        )
    )
    Entity.update_all_entities_senses()
    hp_before = target.get_hp()

    with fixed_dice_faces(18, 17, 3, 4, 5):
        result = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert isinstance(result, AttackEvent)
    assert not result.canceled
    assert result.attack_outcome is AttackOutcome.HIT
    assert hp_before - target.get_hp() == expected_damage
    assert ("Sneak Attack Used" in attacker.active_conditions) is (len(packet_totals) == 2)
    damage_events = [
        event
        for event in EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        if isinstance(event, DamageRollResultEvent) and event.phase is EventPhase.COMPLETION
    ]
    assert len(damage_events) == 1
    damage_event = damage_events[0]
    assert [packet.final_roll.total for packet in damage_event.damage_packets] == packet_totals
    assert damage_event.parent_event is not None
    parent = EventQueue.get_event_by_uuid(damage_event.parent_event)
    assert isinstance(parent, AttackEvent)
    assert parent.phase is EventPhase.EFFECT
    assert parent.dice_roll is not None
    assert parent.dice_roll.advantage_status is circumstance
