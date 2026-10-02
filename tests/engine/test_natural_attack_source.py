"""Natural attack source facts never rewrite the actor's equipped or unarmed stats."""

from uuid import uuid4

from dnd.actions import AttackEvent
from dnd.blocks.base_item import BaseItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import NaturalAttack
from dnd.runtime_reset import reset_engine_runtime


def test_natural_profile_and_hit_keep_held_weapon_and_unarmed_stats_unchanged():
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    try:
        source = Entity.create(uuid4(), "Biter", config=EntityConfig(position=(2, 3)))
        sword = build_authored_item("weapon.longsword", source.uuid)
        source.install_initial_items(((sword, WeaponSlot.MELEE_MAIN),))
        source.compose_entity()
        game.deploy_entity(source, (2, 3))
        target = build_authored_item("environment.furniture.clay_stove", source.uuid)
        assert isinstance(target, BaseItem)
        target.place_on_grid((3, 3))
        Entity.update_all_entities_senses()

        def equipment_values():
            return (source.equipment.get_weapon(WeaponSlot.MELEE_MAIN),
                source.equipment.unarmed_damage_dice, source.equipment.unarmed_dice_numbers,
                source.equipment.unarmed_damage_type)

        before = equipment_values()
        observed = []

        def observe_attack(event, _source):
            observed.append(equipment_values())
            return event

        EventQueue.add_event_handler(EventHandler(name="Observe natural attack source",
            source_entity_uuid=source.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=phase)
                for phase in (EventPhase.EXECUTION, EventPhase.EFFECT)],
            event_processor=observe_attack))
        attack = NaturalAttack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
            name="Bite", natural_damage_dice=6, natural_dice_numbers=1,
            natural_damage_type=DamageType.PIERCING)
        profile = attack.get_outcome_profile(source)
        assert profile is not None
        assert profile.damage_rolls[0].die_size == 6
        assert profile.damage_rolls[0].damage_type == DamageType.PIERCING.value
        assert equipment_values() == before
        hp = target.get_hp()
        with fixed_dice_faces(18, 2):
            result = attack.apply()
        assert isinstance(result, AttackEvent) and not result.canceled
        assert result.attack_source_kind == "natural" and result.weapon_name == "Bite"
        assert result.source_item_uuid is None and result.source_item_presentation is None
        assert result.damages and result.damages[0].damage_dice == 6
        assert result.damages[0].damage_type is DamageType.PIERCING
        assert target.get_hp() < hp
        assert observed and all(values == before for values in observed)
        assert equipment_values() == before
    finally:
        game.close()
        reset_engine_runtime()
