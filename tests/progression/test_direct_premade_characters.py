"""Premade characters are ordinary in-process entity compositions."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from dnd.content.characters.character_builds import create_premade_character
from dnd.content.characters.premade_builds import PREMADE_CHARACTER_DEFINITIONS
from dnd.core.events.events_registry import EventQueue, EventType
from dnd.types.abilities import AbilityName


@dataclass(frozen=True, slots=True)
class PremadeCase:
    premade_id: str
    class_levels: tuple[tuple[str, int], ...]
    inventory_count: int
    equipped_ids: frozenset[str]
    charisma: int


CASES = (
    PremadeCase(
        "hero.barbarian_l5_berserker_torch",
        tuple(("barbarian", level) for level in range(1, 6)),
        8,
        frozenset({
            "apparel.costume.pit_fighter_wrap",
            "apparel.leather_boots",
            "weapon.greataxe",
        }),
        10,
    ),
    PremadeCase(
        "hero.fighter_l5_shield_torch",
        tuple(("fighter", level) for level in range(1, 6)),
        8,
        frozenset({
            "apparel.iron_helmet.steel",
            "apparel.leather_boots.brown",
            "armor.chain_mail",
            "shield.shield",
            "weapon.longbow",
            "weapon.longsword",
        }),
        8,
    ),
    PremadeCase(
        "hero.sorcerer_l5_standard_torch",
        tuple(("sorcerer", level) for level in range(1, 6)),
        6,
        frozenset({
            "apparel.cloth_shoes.red",
            "apparel.robes.red_mage",
            "apparel.wizard_hat.red",
            "weapon.dagger",
        }),
        19,
    ),
    PremadeCase(
        "hero.fighter_2_sorcerer_3_spellblade",
        (
            ("fighter", 1),
            ("fighter", 2),
            ("sorcerer", 1),
            ("sorcerer", 2),
            ("sorcerer", 3),
        ),
        9,
        frozenset({
            "apparel.leather_boots.brown",
            "apparel.spellblade_crown",
            "armor.chain_mail",
            "shield.shield",
            "weapon.longsword",
        }),
        18,
    ),
)


@pytest.fixture(autouse=True)
def _reset_event_history() -> None:
    EventQueue.reset()


def _check_premade(case: PremadeCase) -> None:
    entity = create_premade_character(case.premade_id, uuid4())
    try:
        assert entity.creation_committed
        assert not entity.is_deployed
        assert tuple(
            (row.class_id.value, row.resulting_class_level)
            for row in entity.applied_class_levels
        ) == case.class_levels
        assert len(entity.inventory.items) == case.inventory_count
        assert {
            item.get_semantic_key()
            for item in entity.equipment.get_all_equipped_items()
        } == case.equipped_ids
        assert entity.ability_scores.get_ability(
            AbilityName.CHARISMA,
        ).ability_score.score == case.charisma
        assert entity.appearance.semantic_properties

        events = EventQueue.get_events_chronological()
        assert [event.event_type for event in events] == [EventType.ENTITY_CREATED]
        birth = events[0]
        assert birth.applied_class_levels == tuple(entity.applied_class_levels)
        assert dict(birth.body_semantics) == entity.appearance.semantic_properties
        assert {item.semantic_key for item in birth.items} == {
            item.get_semantic_key()
            for item in (
                *entity.inventory.items.values(),
                *entity.equipment.get_all_equipped_items(),
            )
        }
    finally:
        entity.discard_unpublished_runtime()


def test_all_four_premades_use_the_direct_character_boundary() -> None:
    assert set(PREMADE_CHARACTER_DEFINITIONS) == {
        case.premade_id for case in CASES
    }
    for case in CASES:
        EventQueue.reset()
        _check_premade(case)
