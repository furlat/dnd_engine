"""Monster creation through direct authored data and one entity transaction."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from dnd.content.characters.class_definitions import ClassLevelRequest
from dnd.content.characters.class_level_content import add_class_level
from dnd.content.monsters.monster_builders import create_monster
from dnd.content.monsters.monster_definitions import (
    MONSTER_DEFINITIONS,
    MONSTER_WARDROBE_LOADOUTS,
)
from dnd.content.monsters.srd_monster_definitions import (
    SRD_CONFIGURED_WARDROBE_LOADOUTS,
    SRD_MONSTER_DEFINITIONS,
)
from dnd.core.events.entity_events import EntityCreatedEvent
from dnd.core.events.events_registry import EventQueue, EventType
from dnd.entities.entity_progression import remove_last_level
from dnd.types.progression import (
    CharacterClass,
    ClassChoiceSelection,
)
from dnd.types.damage import DamageType, ResistanceStatus


@dataclass(frozen=True, slots=True)
class MonsterCase:
    monster_id: str
    equipped: frozenset[str]
    inventory: frozenset[str]
    features: frozenset[str] = frozenset()


CASES = (
    MonsterCase(
        "monster.goblin",
        frozenset({
            "armor.leather", "weapon.scimitar", "weapon.shortbow",
            "shield.shield", "apparel.leather_boots.dark",
        }),
        frozenset(),
        frozenset({"trait.goblin.nimble_escape"}),
    ),
    MonsterCase(
        "monster.skeleton",
        frozenset({
            "armor.armor_scraps", "weapon.shortsword", "weapon.shortbow",
        }),
        frozenset(),
    ),
    MonsterCase(
        "monster.goblin_archer",
        frozenset({
            "armor.leather", "weapon.shortbow", "weapon.scimitar",
            "weapon.dagger", "apparel.leather_boots.dark",
        }),
        frozenset(),
    ),
    MonsterCase(
        "monster.generic_caster",
        frozenset({
            "apparel.robes.hedge_wizard", "apparel.cloth_shoes", "weapon.dagger",
        }),
        frozenset({
            "consumable.potion_greater_invisibility",
            "consumable.potion_haste",
        }),
    ),
    MonsterCase(
        "monster.goblin_caster",
        frozenset({
            "apparel.robes.hedge_wizard", "apparel.cloth_shoes.dark", "weapon.dagger",
        }),
        frozenset({
            "consumable.potion_greater_invisibility",
            "consumable.potion_haste",
        }),
        frozenset({"trait.goblin.nimble_escape"}),
    ),
    MonsterCase(
        "monster.skeleton_warrior",
        frozenset({
            "armor.armor_scraps", "weapon.longsword", "shield.shield",
        }),
        frozenset({"consumable.acid_flask"}),
    ),
    MonsterCase(
        "monster.skeleton_archer",
        frozenset({
            "armor.armor_scraps", "weapon.shortbow", "weapon.dagger",
        }),
        frozenset(),
        frozenset({"trait.skeleton.mark_target"}),
    ),
    MonsterCase(
        "monster.skeleton_warlock",
        frozenset({
            "armor.armor_scraps", "apparel.crown", "weapon.arcane_staff",
        }),
        frozenset({"spell_item.scroll_invisibility"}),
    ),
    MonsterCase(
        "monster.circus_fighter",
        frozenset({
            "armor.circus.performer_leather",
            "weapon.circus.flaming_scimitar",
            "weapon.circus.rusty_dagger",
        }),
        frozenset(),
        frozenset({
            "trait.circus.dual_wielder",
            "trait.circus.elemental_weapon_mastery",
            "trait.circus.elemental_affinity",
            "trait.circus.performer",
        }),
    ),
)


@pytest.fixture(autouse=True)
def _reset_event_history() -> None:
    EventQueue.reset()


def test_all_hand_authored_monsters_commit_one_complete_birth_fact() -> None:
    assert set(MONSTER_DEFINITIONS) == {case.monster_id for case in CASES}
    for case in CASES:
        EventQueue.reset()
        monster = create_monster(case.monster_id, uuid4(), faction="monsters")
        try:
            assert monster.creation_committed
            assert not monster.is_deployed
            assert monster.entity_kind_id == case.monster_id
            assert monster.appearance.semantic_properties
            assert {
                item.get_semantic_key()
                for item in monster.equipment.get_all_equipped_items()
            } == case.equipped
            assert {
                item.get_semantic_key()
                for item in monster.inventory.items.values()
            } == case.inventory
            assert case.features <= set(monster.feature_sources)

            events = EventQueue.get_events_chronological()
            assert [event.event_type for event in events] == [
                EventType.ENTITY_CREATED,
            ]
            birth = events[0]
            assert birth.entity_kind_id == case.monster_id
            assert dict(birth.body_semantics) == (
                monster.appearance.semantic_properties
            )
            assert {item.semantic_key for item in birth.items} == (
                case.equipped | case.inventory
            )
        finally:
            monster.discard_unpublished_runtime()


def test_monster_uses_the_ordinary_post_birth_class_level_operation() -> None:
    monster = create_monster(
        "monster.goblin",
        uuid4(),
        include_default_possessions=False,
    )
    choice = ClassChoiceSelection
    try:
        applied = add_class_level(monster, ClassLevelRequest(
            CharacterClass.FIGHTER,
            choices=(
                choice(
                    "class.fighter.first_class.starting_equipment",
                    ("starting_equipment.fighter.sword_shield",),
                ),
                choice(
                    "class.fighter.proficiencies.skills",
                    ("skill.athletics", "skill.perception"),
                ),
                choice(
                    "class.fighter.level_1.fighting_style",
                    ("class_feature.fighter.fighting_style.archery",),
                ),
            ),
        ))
        assert applied.class_id is CharacterClass.FIGHTER
        assert applied.resulting_class_level == 1
        assert monster.applied_class_levels == [applied]
        assert [event.event_type for event in EventQueue.get_events_chronological()] == [
            EventType.ENTITY_CREATED,
            EventType.ENTITY_LEVEL_ADDED,
        ]

        assert remove_last_level(monster) == applied
        assert monster.applied_class_levels == []
    finally:
        monster.discard_unpublished_runtime()


def test_all_seven_authored_bestiary_wardrobes_are_semantic_loadouts() -> None:
    assert set(MONSTER_WARDROBE_LOADOUTS) == {
        "monster.goblin",
        "monster.goblin_archer",
        "monster.generic_caster.arcane",
        "monster.generic_caster.dark",
        "monster.generic_caster.divine",
        "monster.generic_caster.necromancer",
        "monster.goblin_caster",
    }
    expected_body_items = {
        "arcane": {"apparel.robes.hedge_wizard", "apparel.cloth_shoes"},
        "dark": {"apparel.robes.dark_cultist", "apparel.cloth_shoes.dark"},
        "divine": {"apparel.robes.priest_vestments", "apparel.sandals.rope"},
        "necromancer": {"apparel.robes.necromancer", "apparel.cloth_shoes.dark"},
    }
    for wardrobe, expected in expected_body_items.items():
        EventQueue.reset()
        caster = create_monster(
            "monster.generic_caster",
            uuid4(),
            wardrobe=wardrobe,
        )
        try:
            equipped = {
                item.get_semantic_key()
                for item in caster.equipment.get_all_equipped_items()
            }
            assert expected <= equipped
            assert [event.event_type for event in EventQueue.get_events_chronological()] == [
                EventType.ENTITY_CREATED,
            ]
        finally:
            caster.discard_unpublished_runtime()


def test_circus_fighter_intrinsics_are_birth_state_not_condition_events() -> None:
    fighter = create_monster("monster.circus_fighter", uuid4())
    try:
        assert fighter.active_conditions == {}
        assert fighter.ability_scores.strength.ability_score.score == 16
        assert fighter.ability_scores.strength.modifier == 4
        assert fighter.health.temporary_hit_points.normalized_score == 10
        assert fighter.health.damage_reduction.normalized_score == 1
        assert fighter.health.get_resistance(DamageType.FIRE) is (
            ResistanceStatus.RESISTANCE
        )
        assert fighter.health.get_resistance(DamageType.COLD) is (
            ResistanceStatus.VULNERABILITY
        )
        assert fighter.action_economy.actions.normalized_score == 100
        assert fighter.action_economy.reactions.normalized_score == 3
        assert fighter.action_economy.movement.normalized_score == 25
        assert fighter.ac_bonus().normalized_score == 14
        assert any(
            handler.behavior_id == "reaction.opportunity_attack"
            for handler in fighter.event_handlers.values()
        )
        assert [event.event_type for event in EventQueue.get_events_chronological()] == [
            EventType.ENTITY_CREATED,
        ]
    finally:
        fighter.discard_unpublished_runtime()


SRD_MONSTER_IDS = {
    "creature.commoner",
    "creature.bandit",
    "creature.cultist",
    "creature.guard",
    "creature.tribal_warrior",
    "creature.kobold",
    "creature.acolyte",
    "creature.scout",
    "creature.thug",
    "creature.spy",
    "creature.berserker",
    "creature.bandit_captain",
    "creature.priest",
    "creature.cult_fanatic",
    "creature.knight",
    "creature.veteran",
    "creature.mage",
    "creature.orc",
    "creature.hobgoblin",
    "creature.bugbear",
    "creature.gnoll",
    "creature.ogre",
    "creature.wolf",
    "creature.dire_wolf",
    "creature.zombie",
    "creature.ogre_zombie",
    "creature.ghoul",
}


def test_all_27_srd_roots_build_from_cold_direct_definitions() -> None:
    assert set(SRD_MONSTER_DEFINITIONS) == SRD_MONSTER_IDS

    for monster_id, definition in SRD_MONSTER_DEFINITIONS.items():
        EventQueue.reset()
        monster = create_monster(monster_id, uuid4(), faction="monsters")
        try:
            expected_items = {
                entry.item_id
                for entry in (
                    definition.intrinsic_loadout + definition.default_loadout
                )
            }
            equipped_items = tuple(monster.equipment.get_all_equipped_items())
            inventory_items = tuple(monster.inventory.items.values())
            runtime_items = (*equipped_items, *inventory_items)

            assert monster.creation_committed
            assert not monster.is_deployed
            assert monster.entity_kind_id == monster_id
            assert monster.appearance.semantic_properties
            assert {item.get_semantic_key() for item in runtime_items} == (
                expected_items
            )
            assert all(item.content_ref is None for item in runtime_items)
            assert set(definition.trait_ids) <= set(monster.feature_sources)

            births = [
                event
                for event in EventQueue.get_events_chronological()
                if isinstance(event, EntityCreatedEvent)
            ]
            assert len(births) == 1
            birth = births[0]
            assert birth.event_type is EventType.ENTITY_CREATED
            assert birth.entity_kind_id == monster_id
            assert {item.semantic_key for item in birth.items} == expected_items
            assert set(definition.trait_ids) <= set(birth.feature_ids)
            assert {
                multiattack.action_id
                for multiattack in definition.multiattacks
            } <= set(birth.action_ids)
            assert set(definition.spell_ids) <= set(birth.action_ids)
        finally:
            monster.discard_unpublished_runtime()


@pytest.mark.parametrize(
    ("monster_id", "expected_intrinsics"),
    (
        (
            "creature.wolf",
            {"armor.creature.wolf_natural", "weapon.creature.wolf_bite"},
        ),
        (
            "creature.dire_wolf",
            {
                "armor.creature.dire_wolf_natural",
                "weapon.creature.dire_wolf_bite",
            },
        ),
        ("creature.zombie", {"weapon.creature.zombie_slam"}),
        (
            "creature.ghoul",
            {"weapon.creature.ghoul_claws", "weapon.creature.ghoul_bite"},
        ),
        ("creature.commoner", set()),
        ("creature.ogre_zombie", set()),
    ),
)
def test_srd_intrinsic_body_items_survive_possession_opt_out(
    monster_id: str,
    expected_intrinsics: set[str],
) -> None:
    monster = create_monster(
        monster_id,
        uuid4(),
        include_default_possessions=False,
    )
    try:
        assert {
            item.get_semantic_key()
            for item in monster.equipment.get_all_equipped_items()
        } == expected_intrinsics
        birth = next(
            event
            for event in EventQueue.get_events_chronological()
            if isinstance(event, EntityCreatedEvent)
        )
        assert {item.semantic_key for item in birth.items} == expected_intrinsics
    finally:
        monster.discard_unpublished_runtime()


def test_all_21_configured_srd_wardrobes_are_direct_semantic_loadouts() -> None:
    assert len(SRD_CONFIGURED_WARDROBE_LOADOUTS) == 21
    assert all(
        wardrobe_id.endswith(".configured")
        for wardrobe_id in SRD_CONFIGURED_WARDROBE_LOADOUTS
    )

    for wardrobe_id, loadout in SRD_CONFIGURED_WARDROBE_LOADOUTS.items():
        EventQueue.reset()
        monster_id = wardrobe_id.removesuffix(".configured")
        monster = create_monster(
            monster_id,
            uuid4(),
            wardrobe="configured",
        )
        try:
            expected = {entry.item_id for entry in loadout}
            equipped = {
                item.get_semantic_key()
                for item in monster.equipment.get_all_equipped_items()
            }
            assert expected <= equipped
            assert all(
                item.content_ref is None
                for item in monster.equipment.get_all_equipped_items()
            )
            assert len([
                event
                for event in EventQueue.get_events_chronological()
                if isinstance(event, EntityCreatedEvent)
            ]) == 1
        finally:
            monster.discard_unpublished_runtime()
