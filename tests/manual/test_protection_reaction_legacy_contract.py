"""Behavioral coverage for the archived Protection fighting-style matrix."""

from dataclasses import dataclass

import pytest

from dnd.actions.standard import (
    Attack,
    AttackEvent,
)
from dnd.actions.operations import setup_standard_actions
from dnd.blocks.equipment import (
    Shield,
)
from dnd.classes.fighter import create_protection_handler
from dnd.conditions import Invisible
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.types.equipment import WeaponSlot
from dnd.types.rolls import AdvantageStatus
from dnd.entities.entity import Entity
from dnd.items.armors import SHIELD_RECIPE
from tests.engine.support import create_test_monster
from tests.engine.support import reset_combat_state
from dnd.core.gridmap import get_map


@dataclass(frozen=True)
class ProtectionScene:
    protector: Entity
    ally: Entity
    enemy: Entity


def _protection_scene(*, shield: bool = True) -> ProtectionScene:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 14, 10)
    protector = create_test_monster("monster.skeleton", 
        name="Protection Fighter",
        position=(4, 4),
        faction="heroes",
    )
    if shield:
        protector.equipment.equip(
            materialize_item(
                SHIELD_RECIPE,
                protector.uuid,
                origin=ItemRuntimeOrigin.STARTER,
                expected_type=Shield,
            ),
            WeaponSlot.MELEE_OFF,
        )
    protector.add_event_handler(create_protection_handler(protector.uuid))
    ally = create_test_monster("monster.goblin", 
        name="Protection Ally",
        position=(4, 5),
        faction="heroes",
    )
    enemy = create_test_monster("monster.skeleton", 
        name="Protection Enemy",
        position=(4, 6),
        faction="monsters",
    )
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses(max_distance=50)
    return ProtectionScene(protector=protector, ally=ally, enemy=enemy)


def _attack(scene: ProtectionScene, target: Entity | None = None) -> AttackEvent:
    event = Attack(
        source_entity_uuid=scene.enemy.uuid,
        target_entity_uuid=(target or scene.ally).uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()
    assert isinstance(event, AttackEvent)
    assert event.attack_bonus is not None
    return event


def _has_protection_modifier(event: AttackEvent) -> bool:
    attack_bonus = event.attack_bonus
    assert attack_bonus is not None
    return any(
        modifier.name == "Protection"
        for modifier in attack_bonus.self_static.advantage_modifiers.values()
    )


def test_protection_imposes_disadvantage_once_and_consumes_reaction() -> None:
    """The first eligible attack is protected and a second attack is not."""
    scene = _protection_scene()

    first = _attack(scene)

    assert _has_protection_modifier(first)
    assert first.attack_bonus is not None
    assert first.attack_bonus.advantage is AdvantageStatus.DISADVANTAGE
    assert scene.protector.action_economy.reactions.normalized_score == 0

    scene.enemy.action_economy.reset_all_costs()
    second = _attack(scene)

    assert not _has_protection_modifier(second)
    assert scene.protector.action_economy.reactions.normalized_score == 0


@pytest.mark.parametrize(
    "gate",
    ["no_shield", "target_too_far", "protect_self", "no_reaction", "unseen_attacker"],
)
def test_protection_rejects_each_ineligible_reaction_gate(gate: str) -> None:
    """Every archived eligibility gate leaves the attack unmodified."""
    scene = _protection_scene(shield=gate != "no_shield")
    target = scene.ally

    if gate == "target_too_far":
        Entity.update_entity_position(scene.ally, (4, 8))
        Entity.update_entity_position(scene.enemy, (4, 9))
    elif gate == "protect_self":
        target = scene.protector
        Entity.update_entity_position(scene.enemy, (4, 3))
    elif gate == "no_reaction":
        scene.protector.action_economy.consume("reactions", 1)
    elif gate == "unseen_attacker":
        scene.enemy.add_condition(
            Invisible(
                source_entity_uuid=scene.enemy.uuid,
                target_entity_uuid=scene.enemy.uuid,
            )
        )
    Entity.update_all_entities_senses(max_distance=50)
    reactions_before = scene.protector.action_economy.reactions.normalized_score

    event = _attack(scene, target)

    assert not _has_protection_modifier(event)
    assert scene.protector.action_economy.reactions.normalized_score == reactions_before
