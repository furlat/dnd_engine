"""Exact handler-toggle coverage for reactions and low-level ownership."""

from dataclasses import dataclass
from typing import Literal

from dnd.actions import Attack, Move
from dnd.actions_functional import setup_standard_actions
from dnd.classes.fighter import FightingStyleProtection
from dnd.conditions import InvisibilityEffect
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.modifiers import AdvantageStatus
from dnd.entity import Entity
from dnd.items.armors import create_shield
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.reactions import add_opportunity_attack_handler
from dnd.utils import force_attack_miss, get_hp, remove_attack_modifier
from tests.engine_book.test_chapter_10_core_actions_combat import (
    reset_core_action_state,
)


CoverageStatus = Literal["active", "strengthened"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived handler-toggle case's reviewed replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_144_handler_toggle_legacy_contract.py"
OA_SELECTOR = (
    f"{THIS_FILE}::"
    "test_opportunity_attack_toggle_preserves_registration_and_invisibility"
)
PROTECTION_SELECTOR = (
    f"{THIS_FILE}::test_protection_reaction_respects_disable_and_reenable"
)
ENABLED_OA_SELECTOR = (
    "tests/engine_book/test_chapter_10_core_actions_combat.py::"
    "test_eb_10_005_opportunity_attack_uses_reaction_on_step_movement"
)
LOW_LEVEL_SELECTOR = (
    "tests/engine_book/test_chapter_05_blocks_context.py::"
    "test_eb_05_011_handler_toggles_only_affect_player_toggleable_handlers"
)


HANDLER_TOGGLE_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_oa_enabled_fires_normally": LegacyCoverage(
        "strengthened",
        ENABLED_OA_SELECTOR,
        "Maintained coverage proves a real step spends the reaction and deals damage.",
    ),
    "test_oa_disabled_prevents_attack": LegacyCoverage(
        "active",
        OA_SELECTOR,
        "A real provoking Move remains harmless while the handler is disabled.",
    ),
    "test_toggle_on_off_cycle": LegacyCoverage(
        "active",
        OA_SELECTOR,
        "The same handler instance supports repeated name/UUID toggles.",
    ),
    "test_disabled_handler_stays_registered": LegacyCoverage(
        "active",
        OA_SELECTOR,
        "Disabled reactions remain owned by both Entity and EventQueue.",
    ),
    "test_set_handler_enabled_missing_name": LegacyCoverage(
        "strengthened",
        LOW_LEVEL_SELECTOR,
        "Maintained coverage rejects missing and non-toggleable handler names.",
    ),
    "test_set_handler_enabled_by_uuid": LegacyCoverage(
        "active",
        OA_SELECTOR,
        "The concrete reaction is re-enabled by its stable UUID.",
    ),
    "test_get_event_handlers_by_name": LegacyCoverage(
        "active",
        OA_SELECTOR,
        "Both matching and missing name lookups are asserted.",
    ),
    "test_invisible_creature_oa_opt_out": LegacyCoverage(
        "active",
        OA_SELECTOR,
        "Opting out prevents the attack and therefore preserves invisibility.",
    ),
    "test_protection_handler_toggle": LegacyCoverage(
        "active",
        PROTECTION_SELECTOR,
        "Disabled Protection neither imposes disadvantage nor spends a reaction.",
    ),
    "test_protection_re_enabled": LegacyCoverage(
        "active",
        PROTECTION_SELECTOR,
        "Re-enabled Protection modifies the attack and consumes its reaction.",
    ),
}


def test_handler_toggle_manifest_accounts_for_all_10_cases() -> None:
    """Every archived handler-toggle case has a reviewed live disposition."""
    assert len(HANDLER_TOGGLE_LEGACY_CASES) == 10
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for case, row in HANDLER_TOGGLE_LEGACY_CASES.items()
    )


def test_opportunity_attack_toggle_preserves_registration_and_invisibility() -> None:
    """Disabling an OA is an opt-out, not handler deletion or execution."""
    reset_core_action_state()
    attacker = create_skeleton(
        name="Invisible Watcher",
        position=(5, 5),
        faction="monsters",
    )
    mover = create_goblin(name="Mover", position=(5, 6), faction="heroes")
    setup_standard_actions(mover)
    add_opportunity_attack_handler(attacker)
    invisible = InvisibilityEffect(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid,
    )
    attacker.add_condition(invisible)
    Entity.update_all_entities_senses(max_distance=20)

    handler = attacker.get_event_handler_by_name("Opportunity Attack Handler")
    assert handler is not None
    assert handler.enabled is True
    assert attacker.get_event_handlers_by_name("Opportunity Attack Handler") == [
        handler
    ]
    assert attacker.get_event_handlers_by_name("Missing Handler") == []
    assert attacker.set_handler_enabled("Missing Handler", False) is False
    assert attacker.set_handler_enabled("Opportunity Attack Handler", False)
    assert handler.enabled is False
    assert handler.uuid in attacker.event_handlers
    assert handler.uuid in EventQueue._event_handlers

    hp_before = get_hp(mover)
    move_event = Move(
        source_entity_uuid=mover.uuid,
        end_position=(5, 10),
    ).apply()

    assert move_event is not None
    assert get_hp(mover) == hp_before
    assert attacker.action_economy.reactions.normalized_score == 1
    assert invisible.uuid in attacker.active_conditions_by_uuid

    assert attacker.set_handler_enabled_by_uuid(handler.uuid, True)
    assert handler.enabled is True
    assert attacker.set_handler_enabled("Opportunity Attack Handler", False)
    assert attacker.set_handler_enabled("Opportunity Attack Handler", True)
    assert handler.enabled is True


def test_protection_reaction_respects_disable_and_reenable() -> None:
    """Protection toggle controls both attack pressure and reaction spending."""
    reset_core_action_state()
    protector = create_skeleton(
        name="Protector",
        position=(5, 5),
        faction="heroes",
    )
    protector.equipment.equip(
        create_shield(protector.uuid),
        WeaponSlot.MELEE_OFF,
    )
    protection = FightingStyleProtection(
        source_entity_uuid=protector.uuid,
        target_entity_uuid=protector.uuid,
    )
    protector.add_condition(protection)
    ally = create_goblin(name="Ally", position=(5, 6), faction="heroes")
    enemy = create_skeleton(
        name="Enemy",
        position=(5, 7),
        faction="monsters",
    )
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses(max_distance=20)

    handler = protector.get_event_handler_by_name("Protection")
    assert handler is not None
    assert handler.player_toggleable is True
    assert protector.set_handler_enabled("Protection", False)
    miss_modifier = force_attack_miss(enemy)

    disabled_event = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=ally.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        costs=[],
        template=False,
    ).apply()

    assert disabled_event is not None
    assert disabled_event.attack_bonus is not None
    assert disabled_event.attack_bonus.advantage is AdvantageStatus.NONE
    assert protector.action_economy.reactions.normalized_score == 1

    assert protector.set_handler_enabled("Protection", True)
    enabled_event = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=ally.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        costs=[],
        template=False,
    ).apply()
    remove_attack_modifier(enemy, miss_modifier)

    assert enabled_event is not None
    assert enabled_event.attack_bonus is not None
    assert enabled_event.attack_bonus.advantage is AdvantageStatus.DISADVANTAGE
    assert protector.action_economy.reactions.normalized_score == 0
