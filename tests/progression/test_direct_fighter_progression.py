"""Public direct Fighter/Champion progression proofs."""

from collections.abc import Iterator
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from dnd.blocks.action_economy import RechargeType
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.equipment import Weapon
from dnd.blocks.health import HealthConfig
from dnd.classes import fighter
from dnd.content.characters.class_definitions import (
    FIGHTER_ASI_LEVELS,
    FIGHTER_ASI_VALUES,
    FIGHTER_CLASS_SKILLS,
    FIGHTER_DEFINITION,
    FIGHTER_FIGHTING_STYLES,
    FIGHTER_STARTING_EQUIPMENT,
    resolve_fighter_level,
)
from dnd.content.characters.fighter_grants import (
    apply_fighter_level,
    remove_last_fighter_level,
)
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import (
    ArmorType,
    BodyPart,
    WeaponProperty,
    WeaponSlot,
)
from dnd.core.events import Range, RangeType
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.values import BaseValue, ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.core.proficiency_types import ProficiencyMode
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import (
    AppliedClassLevel,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
)


_ROOT = Path(__file__).resolve().parents[2]
_ASI_ABILITIES = {
    4: "strength",
    6: "dexterity",
    8: "constitution",
    12: "intelligence",
    14: "wisdom",
    16: "charisma",
    19: "strength",
}


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _entity(*, strength: int = 10, dexterity: int = 10) -> Entity:
    return Entity.create(
        uuid4(),
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                dexterity=AbilityConfig(ability_score=dexterity),
            ),
            health=HealthConfig(),
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_armor_types=(),
                base_shields=False,
            ),
        ),
    )


def _fighter_level(
    level: int,
    *,
    character_level: int | None = None,
    first_style: str = "class_feature.fighter.fighting_style.archery",
    second_style: str = "class_feature.fighter.fighting_style.dueling",
    lucky_level: int | None = None,
) -> AppliedClassLevel:
    choices: list[ClassChoiceSelection] = []
    resolved_character_level = character_level or level
    if level == 1:
        if resolved_character_level == 1:
            choices.extend((
                ClassChoiceSelection(
                    choice_id="class.fighter.first_class.starting_equipment",
                    values=("starting_equipment.fighter.sword_shield",),
                ),
                ClassChoiceSelection(
                    choice_id="class.fighter.proficiencies.skills",
                    values=("athletics", "perception"),
                ),
            ))
        choices.append(ClassChoiceSelection(
            choice_id="class.fighter.level_1.fighting_style",
            values=(first_style,),
        ))
    elif level == 3:
        choices.append(ClassChoiceSelection(
            choice_id="class.fighter.level_3.subclass",
            values=(CharacterSubclass.CHAMPION.value,),
        ))
    elif level in FIGHTER_ASI_LEVELS:
        values = (
            ("feat.lucky",)
            if level == lucky_level
            else (f"ability_score.{_ASI_ABILITIES[level]}.2",)
        )
        choices.append(ClassChoiceSelection(
            choice_id=f"class.fighter.level_{level}.asi_or_feat",
            values=values,
        ))
    elif level == 10:
        choices.append(ClassChoiceSelection(
            choice_id="subclass.fighter.champion.level_10.fighting_style",
            values=(second_style,),
        ))
    return AppliedClassLevel(
        step_id=f"class.fighter.level_{level}",
        character_level=resolved_character_level,
        class_id=CharacterClass.FIGHTER,
        resulting_class_level=level,
        subclass_id=(CharacterSubclass.CHAMPION if level >= 3 else None),
        choices=tuple(choices),
    )


def test_fighter_definition_is_cold_complete_and_exact() -> None:
    marker = "__DIRECT_FIGHTER_IMPORTS__="
    script = (
        "import json, sys\n"
        "import dnd.content.characters.class_definitions\n"
        "forbidden = ('dnd.entity', 'dnd.actions', 'dnd.conditions', "
        "'dnd.classes.fighter', 'dnd.content_system')\n"
        "loaded = sorted(name for name in sys.modules if any("
        "name == prefix or name.startswith(prefix + '.') for prefix in forbidden))\n"
        f"print({marker!r} + json.dumps(loaded))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    line = next(
        row for row in completed.stdout.splitlines() if row.startswith(marker)
    )
    assert json.loads(line[len(marker):]) == []

    assert FIGHTER_DEFINITION.hit_die == 10
    assert FIGHTER_DEFINITION.class_skills == FIGHTER_CLASS_SKILLS
    assert FIGHTER_DEFINITION.starting_equipment == FIGHTER_STARTING_EQUIPMENT
    assert tuple(row.class_level for row in FIGHTER_DEFINITION.levels) == tuple(
        range(1, 21)
    )
    assert tuple(
        row.class_level for row in FIGHTER_DEFINITION.champion_levels
    ) == tuple(range(1, 21))
    assert len(FIGHTER_FIGHTING_STYLES) == 6
    assert len(FIGHTER_ASI_VALUES) == 13
    assert {
        row.class_level: row.feature_ids
        for row in FIGHTER_DEFINITION.levels
        if row.feature_ids
    } == {
        1: ("class_feature.fighter.second_wind",),
        2: ("class_feature.fighter.action_surge",),
        5: ("class_feature.extra_attack",),
        9: ("class_feature.fighter.indomitable",),
        11: ("class_feature.extra_attack",),
        13: ("class_feature.fighter.indomitable",),
        17: (
            "class_feature.fighter.action_surge",
            "class_feature.fighter.indomitable",
        ),
        20: ("class_feature.extra_attack",),
    }
    assert {
        row.class_level: row.feature_ids
        for row in FIGHTER_DEFINITION.champion_levels
        if row.feature_ids
    } == {
        3: ("class_feature.fighter.improved_critical",),
        7: ("class_feature.fighter.remarkable_athlete",),
        15: ("class_feature.fighter.superior_critical",),
        18: ("class_feature.fighter.survivor",),
    }


@pytest.mark.parametrize("style", FIGHTER_FIGHTING_STYLES)
def test_each_fighting_style_has_direct_exact_reversible_ownership(
    style: str,
) -> None:
    entity = _entity(strength=14, dexterity=16)
    if style.endswith(".defense"):
        armor = build_authored_item("armor.leather", entity.uuid)
        assert entity.equipment.equip(armor, BodyPart.BODY)
    elif style.endswith(".dueling"):
        weapon = build_authored_item("weapon.longsword", entity.uuid)
        assert entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    elif style.endswith(".two_weapon_fighting"):
        melee = build_authored_item("weapon.dagger", entity.uuid)
        ranged = Weapon(
            source_entity_uuid=entity.uuid,
            item_id="test.fighter.light_ranged_off_hand",
            name="Light Ranged Off Hand",
            damage_dice=4,
            dice_numbers=1,
            damage_type=DamageType.PIERCING,
            properties=[WeaponProperty.RANGED, WeaponProperty.LIGHT],
            range=Range(type=RangeType.RANGE, normal=30, long=120),
            attack_bonus=ModifiableValue.create(
                source_entity_uuid=entity.uuid,
                value_name="Light Ranged Off Hand Attack Bonus",
            ),
        )
        assert entity.equipment.equip(melee, WeaponSlot.MELEE_OFF)
        assert entity.equipment.equip(ranged, WeaponSlot.RANGED_OFF)

    baseline_handlers = set(entity.event_handlers)
    baseline_blocks = set(BaseBlock._registry)
    baseline_values = set(BaseValue._registry)
    baseline_objects = set(BaseObject._registry)
    receipt = apply_fighter_level(entity, _fighter_level(1, first_style=style))
    applied_objects = set(BaseObject._registry)

    assert not entity.active_conditions
    assert style in {
        feature_id for feature_id, _ in receipt.feature_sources
    }
    if style.endswith(".archery"):
        assert entity.equipment.ranged_attack_bonus.normalized_score == 2
    elif style.endswith(".defense"):
        for _ in range(3):
            assert entity.equipment.ac_bonus.normalized_score == 1
    elif style.endswith(".dueling"):
        for _ in range(3):
            assert entity.equipment.melee_damage_bonus.normalized_score == 2
    elif style.endswith(".two_weapon_fighting"):
        for _ in range(3):
            assert (
                entity.equipment.off_hand_melee_ability_bonus.normalized_score
                == 3
            )
            assert (
                entity.equipment.off_hand_ranged_ability_bonus.normalized_score
                == 3
            )
    elif style.endswith(".great_weapon_fighting"):
        assert entity.get_event_handler_by_name("Great Weapon Fighting") is not None
    elif style.endswith(".protection"):
        handler = entity.get_event_handler_by_name("Protection")
        assert handler is not None
        assert handler.behavior_binding is not None
        assert handler.behavior_binding.behavior_id == (
            "reaction.class_feature.fighter.protection"
        )
    assert set(BaseObject._registry) == applied_objects

    remove_last_fighter_level(entity)
    assert set(entity.event_handlers) == baseline_handlers
    assert entity.equipment.ranged_attack_bonus.normalized_score == 0
    assert not entity.feature_sources
    assert set(BaseBlock._registry) == baseline_blocks
    assert set(BaseValue._registry) == baseline_values
    assert set(BaseObject._registry) == baseline_objects


def test_fighter_champion_applies_1_to_20_and_removes_20_to_1_exactly() -> None:
    entity = _entity()
    sibling_source = uuid4()
    sibling_modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        name="Sibling ranged bonus",
        value=1,
    )
    entity.equipment.ranged_attack_bonus.self_static.add_value_modifier(
        sibling_modifier,
    )
    entity.skill_set.athletics.add_proficiency_source(
        sibling_source,
        ProficiencyMode.FULL,
    )
    entity.add_feature_source("class_feature.fighter.second_wind", sibling_source)
    baseline_blocks = set(BaseBlock._registry)
    baseline_values = set(BaseValue._registry)
    baseline_objects = set(BaseObject._registry)

    receipts = tuple(
        apply_fighter_level(
            entity,
            _fighter_level(level, lucky_level=4),
        )
        for level in range(1, 21)
    )

    assert len(receipts) == 20
    assert len(entity.applied_class_levels) == 20
    assert entity.health.total_hit_dices_number == 20
    assert entity.health.hit_dices_total_hit_points == 124
    assert entity.action_economy.resolve_attacks_per_attack_action() == 4
    assert entity.get_crit_threshold() == 18
    assert entity.get_spell_crit_threshold() == 20
    assert entity.equipment.ranged_attack_bonus.normalized_score == 3
    assert entity.ability_scores.strength.check_proficiency_sources.has_mode(
        ProficiencyMode.HALF_ROUND_UP,
    )
    applied_objects = set(BaseObject._registry)
    for _ in range(3):
        assert entity.jump_distance_additive.normalized_score == (
            entity.ability_scores.strength.modifier
        )
    assert set(BaseObject._registry) == applied_objects
    assert {
        name: (resource.current, resource.maximum)
        for name, resource in entity.action_economy.resources.items()
    } == {
        "action_surge": (2, 2),
        "extra_attacks": (3, 3),
        "indomitable": (3, 3),
        "luck_points": (3, 3),
        "second_wind": (1, 1),
    }
    assert {
        type(action)
        for action in entity.registered_actions
    } == {fighter.SecondWind, fighter.ActionSurge, fighter.ExtraAttack}
    assert {
        handler.name for handler in entity.event_handlers.values()
    } == {"Extra Attack Resource", "Indomitable", "Lucky", "Survivor"}
    assert all(
        action.behavior_binding is not None
        and action.behavior_binding.origin_root_id == CharacterClass.FIGHTER.value
        for action in entity.registered_actions
    )
    second_wind = entity.get_action_template("Second Wind")
    assert isinstance(second_wind, fighter.SecondWind)
    assert second_wind.fighter_level == 20

    removed = tuple(remove_last_fighter_level(entity) for _ in range(20))
    assert tuple(row.resulting_class_level for row in removed) == tuple(
        range(20, 0, -1)
    )
    assert entity.applied_class_levels == ()
    assert entity.health.hit_dices == []
    assert not entity.registered_actions
    assert not entity.event_handlers
    assert not entity.action_economy.resources
    assert entity.action_economy.resolve_attacks_per_attack_action() == 1
    assert entity.get_crit_threshold() == 20
    assert entity.get_spell_crit_threshold() == 20
    assert entity.equipment.ranged_attack_bonus.normalized_score == 1
    assert entity.skill_set.athletics.proficiency_sources.sources == {
        sibling_source: ProficiencyMode.FULL,
    }
    assert entity.feature_sources == {
        "class_feature.fighter.second_wind": {sibling_source},
    }
    assert set(BaseBlock._registry) == baseline_blocks
    assert set(BaseValue._registry) == baseline_values
    assert set(BaseObject._registry) == baseline_objects


def test_second_wind_scaling_uses_its_receipt_owned_action_uuid() -> None:
    entity = _entity()
    sibling = fighter.SecondWind(
        source_entity_uuid=entity.uuid,
        fighter_level=99,
        template=True,
        semantic_key="fixture.sibling.second_wind",
        behavior_binding=BehaviorBinding(
            behavior_id="action.class.fighter.second_wind",
            provided_by_id="fixture.sibling.second_wind",
            origin_root_id="fixture.sibling",
            runtime_owner_uuid=entity.uuid,
        ),
    )
    entity.register_action(sibling)

    level_one = apply_fighter_level(entity, _fighter_level(1))
    owned_uuid = level_one.action_uuids[0]
    owned = next(
        action for action in entity.registered_actions if action.uuid == owned_uuid
    )
    assert owned.fighter_level == 1
    assert sibling.fighter_level == 99

    apply_fighter_level(entity, _fighter_level(2))
    assert owned.fighter_level == 2
    assert sibling.fighter_level == 99

    remove_last_fighter_level(entity)
    assert owned.fighter_level == 1
    assert sibling.fighter_level == 99
    remove_last_fighter_level(entity)
    assert entity.registered_actions == [sibling]
    assert sibling.fighter_level == 99


def test_first_class_and_multiclass_fighter_packages_are_distinct() -> None:
    first = _entity()
    apply_fighter_level(first, _fighter_level(1))
    assert first.creature_proficiencies.is_armor_proficient(ArmorType.HEAVY)
    assert first.saving_throws.strength_saving_throw.proficiency
    assert first.saving_throws.constitution_saving_throw.proficiency
    assert first.skill_set.athletics.proficiency
    assert first.skill_set.perception.proficiency

    multiclass = _entity()
    multiclass.applied_class_levels = (AppliedClassLevel(
        step_id="class.sorcerer.level_1",
        character_level=1,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=1,
    ),)
    apply_fighter_level(multiclass, _fighter_level(1, character_level=2))
    assert not multiclass.creature_proficiencies.is_armor_proficient(
        ArmorType.HEAVY,
    )
    assert multiclass.creature_proficiencies.is_armor_proficient(
        ArmorType.LIGHT,
    )
    assert multiclass.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
    )
    assert not multiclass.saving_throws.strength_saving_throw.proficiency
    assert not multiclass.saving_throws.constitution_saving_throw.proficiency
    assert not multiclass.skill_set.athletics.proficiency


def test_fighter_resolution_rejects_invalid_choices_before_mutation() -> None:
    entity = _entity()
    invalid = _fighter_level(1)
    invalid = AppliedClassLevel(
        step_id=invalid.step_id,
        character_level=invalid.character_level,
        class_id=invalid.class_id,
        resulting_class_level=invalid.resulting_class_level,
        choices=invalid.choices[:-1],
    )
    with pytest.raises(ValueError, match="exact authored order"):
        apply_fighter_level(entity, invalid)
    assert entity.applied_class_levels == ()
    assert entity.health.hit_dices == []
    assert not entity.feature_sources

    first = _fighter_level(1)
    resolved = resolve_fighter_level(first, ())
    assert resolved.starting_equipment_id == (
        "starting_equipment.fighter.sword_shield"
    )

    with pytest.raises(ValueError, match="values must be unique"):
        ClassChoiceSelection(
            choice_id="class.fighter.proficiencies.skills",
            values=("athletics", "athletics"),
        )
    assert entity.applied_class_levels == ()


def test_fighter_owner_failure_rolls_back_only_the_partial_level() -> None:
    entity = _entity()
    entity.action_economy.add_resource(
        "second_wind",
        maximum=7,
        recharge_type=RechargeType.LONG_REST,
    )
    existing = entity.action_economy.resources["second_wind"]
    block_registry_before = set(BaseBlock._registry)
    object_registry_before = set(BaseObject._registry)
    value_registry_before = set(BaseValue._registry)

    with pytest.raises(ValueError, match="already uses long_rest recharge"):
        apply_fighter_level(entity, _fighter_level(1))

    assert entity.applied_class_levels == ()
    with pytest.raises(KeyError):
        entity.character_grant_receipt("class.fighter.level_1")
    assert entity.health.hit_dices == []
    assert not entity.registered_actions
    assert not entity.event_handlers
    assert not entity.feature_sources
    assert entity.equipment.ranged_attack_bonus.normalized_score == 0
    assert entity.action_economy.resources["second_wind"] is existing
    assert (existing.current, existing.maximum) == (7, 7)
    assert set(BaseBlock._registry) == block_registry_before
    assert set(BaseObject._registry) == object_registry_before
    assert set(BaseValue._registry) == value_registry_before


def test_asi_shapes_and_cap_are_validated_before_owner_mutation() -> None:
    first = _fighter_level(1)
    second = _fighter_level(2)
    third = _fighter_level(3)
    split = AppliedClassLevel(
        step_id="class.fighter.level_4",
        character_level=4,
        class_id=CharacterClass.FIGHTER,
        resulting_class_level=4,
        subclass_id=CharacterSubclass.CHAMPION,
        choices=(ClassChoiceSelection(
            choice_id="class.fighter.level_4.asi_or_feat",
            values=("ability_score.strength.1", "ability_score.dexterity.1"),
        ),),
    )
    assert resolve_fighter_level(
        split,
        (first, second, third),
    ).ability_increases == (("strength", 1), ("dexterity", 1))

    entity = _entity(strength=20)
    for level in (first, second, third):
        apply_fighter_level(entity, level)
    before_hit_dice = tuple(entity.health.hit_dices)
    with pytest.raises(ValueError, match="above 20"):
        apply_fighter_level(entity, _fighter_level(4))
    assert tuple(entity.health.hit_dices) == before_hit_dice
    assert len(entity.applied_class_levels) == 3


def test_fighter_removal_rejects_a_modifier_moved_to_a_foreign_channel() -> None:
    entity = _entity()
    level = _fighter_level(1)
    receipt = apply_fighter_level(entity, level)
    modifier_uuid = receipt.ranged_attack_bonus_modifier_ids[0]
    modifier = entity.equipment.ranged_attack_bonus.self_static.value_modifiers.pop(
        modifier_uuid,
    )
    entity.equipment.crit_threshold_melee.self_static.value_modifiers[
        modifier_uuid
    ] = modifier
    action_order = tuple(action.uuid for action in entity.registered_actions)

    with pytest.raises(RuntimeError, match="modifier ownership changed"):
        remove_last_fighter_level(entity)

    assert entity.applied_class_levels == (level,)
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert tuple(action.uuid for action in entity.registered_actions) == action_order
    assert NumericalModifier.get(modifier_uuid) is modifier


def test_fighter_removal_rejects_a_resource_source_moved_to_another_pool() -> None:
    entity = _entity()
    apply_fighter_level(entity, _fighter_level(1))
    level = _fighter_level(2)
    receipt = apply_fighter_level(entity, level)
    resource_name, source_uuid = next(
        row
        for row in receipt.resource_contributions
        if row[0] == "action_surge"
    )
    source_key = str(source_uuid)
    amount = entity.action_economy.resources[
        resource_name
    ].capacity_contributions.pop(source_key)
    entity.action_economy.resources["second_wind"].capacity_contributions[
        source_key
    ] = amount
    action_order = tuple(action.uuid for action in entity.registered_actions)

    with pytest.raises(RuntimeError, match="resource contribution ownership changed"):
        remove_last_fighter_level(entity)

    assert entity.applied_class_levels[-1] == level
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert tuple(action.uuid for action in entity.registered_actions) == action_order
