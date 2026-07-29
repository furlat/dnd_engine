"""Canonical registry and behavior coverage for Neurodragon consumables."""

from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.items as item_exports
import dnd.items.consumables as consumable_definitions
import dnd.items.environment_interactables as fixture_items
from dnd.actions_functional import execute_use_action
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import Weapon
from dnd.content_system.icon_bindings import (
    BUILT_IN_CONTENT_ICON_BINDING_LEDGER,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    get_content_declaration,
    scan_module_content_declarations,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.creature_types import DamageType
from dnd.entity import Entity
from dnd.items.weapons import SHORTSWORD_RECIPE
from dnd.runtime_reset import reset_engine_runtime


_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_SYMBOLS = frozenset({
    "ApplyCoatAction",
    "DrinkGreaterInvisibilityPotionAction",
    "DrinkHastePotionAction",
    "DrinkPotionAction",
    "FlamingCoatCondition",
    "HealingPotion",
    "PotionDrinkAction",
    "PotionOfGreaterInvisibility",
    "PotionOfHaste",
    "WeaponCoat",
    "WeaponCoatCondition",
    "create_flaming_weapon_spell_coat",
    "create_healing_potion",
    "create_lightning_weapon_coat",
    "create_potion_of_greater_invisibility",
    "create_potion_of_haste",
    "create_timed_weapon_coat",
    "create_weapon_coat",
})


def test_consumable_declarations_are_exact_reviewed_original_content() -> None:
    """All seven roots own stable public metadata and durable possession."""
    declarations = consumable_definitions.NEURODRAGON_CONSUMABLE_DECLARATIONS
    recipes = (
        consumable_definitions
        .NEURODRAGON_CONSUMABLE_RECIPES_BY_LEGACY_ID
    )

    assert isinstance(recipes, MappingProxyType)
    assert tuple(recipes) == (
        "healing_potion",
        "weapon_coat",
        "lightning_weapon_coat",
        "flaming_weapon_spell_coat",
        "timed_weapon_coat",
        "potion_of_greater_invisibility",
        "potion_of_haste",
    )
    assert tuple(declaration.ref.content_id for declaration in declarations) == (
        "consumable.healing_potion",
        "consumable.weapon_coat.fire",
        "consumable.weapon_coat.lightning",
        "consumable.weapon_coat.concentration_fire",
        "consumable.weapon_coat.timed_fire",
        "consumable.potion_greater_invisibility",
        "consumable.potion_haste",
    )

    discovered = scan_module_content_declarations(consumable_definitions)
    assert set(declarations).issubset(set(discovered))
    icon_rows = {
        row.content_ref.identity_key: row
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
    }
    for declaration in declarations:
        assert declaration.ref.pack_id == "content.neurodragon"
        assert declaration.ref.content_version == 1
        assert declaration.descriptor.ref == declaration.ref
        assert declaration.descriptor.visibility.value == "public"
        assert declaration.descriptor.presentation.icon_key == (
            icon_rows[declaration.ref.identity_key].icon_key
        )
        assert declaration.provenance.primary_source_id == (
            "neurodragon.original_b2b3930"
        )
        assert (
            declaration.provenance.relation
            is ContentProvenanceRelation.ORIGINAL_CONTENT
        )
        assert declaration.provenance.fidelity is ContentFidelity.COMPLETE
        assert (
            declaration.provenance.review_status
            is ContentReviewStatus.REVIEWED
        )
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )

    with pytest.raises(TypeError):
        recipes["weapon_coat"] = recipes["healing_potion"]  # type: ignore[index]


def test_consumable_recipe_parameters_are_closed_and_stack_exactly() -> None:
    """Only heal amount and timed rounds vary, and both enter the recipe hash."""
    healing_construction = (
        consumable_definitions.HEALING_POTION_DECLARATION.construction
    )
    timed_construction = (
        consumable_definitions
        .TIMED_FIRE_WEAPON_COAT_DECLARATION
        .construction
    )
    assert healing_construction is not None
    assert timed_construction is not None
    healing_model = healing_construction.parameter_model
    timed_model = timed_construction.parameter_model
    assert healing_model.model_validate({}).model_dump() == {"heal_amount": 7}
    assert healing_model.model_validate(
        {"heal_amount": 12},
    ).model_dump() == {"heal_amount": 12}
    assert timed_model.model_validate({}).model_dump() == {"rounds": 3}
    assert timed_model.model_validate({"rounds": 5}).model_dump() == {
        "rounds": 5,
    }
    with pytest.raises(ValidationError):
        healing_model.model_validate({"heal_amount": 7, "color": "red"})
    with pytest.raises(ValidationError):
        timed_model.model_validate({"rounds": 3, "damage": "cold"})

    default_healing = consumable_definitions.HEALING_POTION_RECIPE
    strong_healing = consumable_definitions.healing_potion_recipe(
        heal_amount=12,
    )
    timed_three = consumable_definitions.TIMED_FIRE_WEAPON_COAT_RECIPE
    timed_five = consumable_definitions.timed_fire_weapon_coat_recipe(
        rounds=5,
    )
    assert default_healing.parameters == {"heal_amount": 7}
    assert strong_healing.parameters == {"heal_amount": 12}
    assert default_healing.recipe_digest != strong_healing.recipe_digest
    assert timed_three.parameters == {"rounds": 3}
    assert timed_five.parameters == {"rounds": 5}
    assert timed_three.recipe_digest != timed_five.recipe_digest

    reset_engine_runtime(grid_size=(4, 3))
    owner = uuid4()
    default_item = materialize_item(
        default_healing,
        owner,
        origin=ItemRuntimeOrigin.STARTER,
    )
    same_item = materialize_item(
        default_healing,
        owner,
        origin=ItemRuntimeOrigin.STARTER,
    )
    strong_item = materialize_item(
        strong_healing,
        owner,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert default_item.stack_id == same_item.stack_id
    assert default_item.stack_id == default_healing.recipe_digest
    assert strong_item.stack_id == strong_healing.recipe_digest
    assert strong_item.stack_id != default_item.stack_id


def test_weapon_coat_condition_variants_own_exact_closed_identities() -> None:
    """Each authored coat effect is a declared child of the apply action."""
    expected = {
        consumable_definitions.FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY:
            consumable_definitions._FireWeaponCoatCondition,
        consumable_definitions.LIGHTNING_WEAPON_COAT_CONDITION_SEMANTIC_KEY:
            consumable_definitions._LightningWeaponCoatCondition,
        (
            consumable_definitions
            .CONCENTRATION_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY
        ): consumable_definitions._ConcentrationFireWeaponCoatCondition,
        consumable_definitions.TIMED_FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY:
            consumable_definitions._TimedFireWeaponCoatCondition,
    }
    assert dict(
        consumable_definitions
        ._WEAPON_COAT_CONDITION_TYPES_BY_SEMANTIC_KEY
    ) == expected
    declarations = {
        condition_type: get_content_declaration(condition_type)
        for condition_type in expected.values()
    }
    assert {
        declaration.ref.identity_key
        for declaration in declarations.values()
    } == set(expected)
    with pytest.raises(ValueError):
        get_content_declaration(consumable_definitions._WeaponCoatCondition)

    action_declaration = get_content_declaration(
        consumable_definitions._ApplyWeaponCoatAction,
    )
    assert {
        dependency.target_ref.identity_key
        for dependency in action_declaration.dependencies
    } == {
        declaration.ref.identity_key
        for declaration in declarations.values()
    } | {
        get_content_declaration(
            consumable_definitions.Concentrating,
        ).ref.identity_key,
    }
    assert all(
        dependency.relation
        is ContentDependencyRelation.APPLIES_CONDITION
        for dependency in action_declaration.dependencies
    )


def test_healing_potion_keeps_healing_cost_and_consumption_behavior() -> None:
    """The canonical item still heals, spends a bonus action, and is consumed."""
    reset_engine_runtime(grid_size=(4, 3))
    actor = Entity.create(source_entity_uuid=uuid4(), name="Potion tester")
    potion = materialize_item(
        consumable_definitions.healing_potion_recipe(heal_amount=4),
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=UsableItem,
    )
    assert actor.loot_item(potion)
    assert actor.receive_damage(
        4,
        DamageType.SLASHING,
        actor.uuid,
    ) == 4
    before_bonus_actions = actor.action_economy.bonus_actions.normalized_score

    action = potion.get_use_actions(actor.uuid)[0]
    assert action.get_semantic_key() == (
        consumable_definitions.HEALING_POTION_DRINK_SEMANTIC_KEY
    )
    assert action.get_fixed_healing(actor) == 4
    assert tuple(
        (cost.cost_type, cost.cost)
        for cost in action.costs
    ) == (("bonus_actions", 1),)

    completion = execute_use_action(actor, potion.uuid, "Drink Potion")

    assert completion is not None and not completion.canceled
    assert actor.get_hp() == actor.get_max_hp()
    assert (
        actor.action_economy.bonus_actions.normalized_score
        == before_bonus_actions - 1
    )
    assert potion.uuid not in actor.inventory.items


def test_weapon_coat_variants_keep_exact_actions_conditions_and_cleanup() -> None:
    """Variant recipes preserve slot, element, lifetime, and removal hooks."""
    reset_engine_runtime(grid_size=(4, 3))
    actor = Entity.create(source_entity_uuid=uuid4(), name="Coat tester")
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert actor.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    fire = materialize_item(
        consumable_definitions.FIRE_WEAPON_COAT_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=UsableItem,
    )
    lightning = materialize_item(
        consumable_definitions.LIGHTNING_WEAPON_COAT_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=UsableItem,
    )
    concentration = materialize_item(
        consumable_definitions.CONCENTRATION_FIRE_WEAPON_COAT_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=UsableItem,
    )
    timed = materialize_item(
        consumable_definitions.timed_fire_weapon_coat_recipe(rounds=5),
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=UsableItem,
    )

    fire_actions = fire.get_use_actions(actor.uuid)
    lightning_actions = lightning.get_use_actions(actor.uuid)
    concentration_action = concentration.get_use_actions(actor.uuid)[0]
    timed_action = timed.get_use_actions(actor.uuid)[0]
    fire_action_data = tuple(action.model_dump() for action in fire_actions)
    lightning_action_data = tuple(
        action.model_dump() for action in lightning_actions
    )
    concentration_action_data = concentration_action.model_dump()
    timed_action_data = timed_action.model_dump()
    assert tuple(action.name for action in fire_actions) == (
        "Coat Main Hand",
        "Coat Off Hand",
    )
    assert tuple(row["coat_damage_type"] for row in fire_action_data) == (
        DamageType.FIRE,
        DamageType.FIRE,
    )
    assert tuple(
        row["coat_damage_type"] for row in lightning_action_data
    ) == (DamageType.LIGHTNING, DamageType.LIGHTNING)
    assert concentration_action_data["use_concentration"] is True
    assert concentration_action_data["coat_duration"] is None
    assert timed_action_data["use_concentration"] is False
    assert timed_action_data["coat_duration"] == 5

    assert actor.loot_item(fire)
    completion = execute_use_action(actor, fire.uuid, "Coat Main Hand")
    assert completion is not None and not completion.canceled
    coat = actor.active_conditions["Flaming Coat"]
    assert coat.get_semantic_key() == (
        consumable_definitions.FIRE_WEAPON_COAT_CONDITION_SEMANTIC_KEY
    )
    assert coat.behavior_binding is not None
    assert coat.behavior_binding.definition_ref == get_content_declaration(
        consumable_definitions._FireWeaponCoatCondition,
    ).ref
    assert coat.behavior_binding.provided_by_ref == get_content_declaration(
        consumable_definitions._ApplyWeaponCoatAction,
    ).ref
    assert (
        coat.behavior_binding.origin_root_ref
        == consumable_definitions.FIRE_WEAPON_COAT_REF
    )
    assert coat.behavior_binding.runtime_owner_uuid == actor.uuid
    assert sword.extra_damage_dices == [6]
    assert sword.extra_damage_dices_numbers == [1]
    assert sword.extra_damage_type == [DamageType.FIRE]
    coat_events = [
        event
        for event in EventQueue.get_events_by_type(
            EventType.CONDITION_APPLICATION,
        )
            if getattr(getattr(event, "condition", None), "uuid", None)
            == coat.uuid
            and event.phase is EventPhase.DECLARATION
    ]
    assert len(coat_events) == 1
    coat_parent_uuid = coat_events[0].parent_event
    assert coat_parent_uuid is not None
    coat_parent = EventQueue.get_event_by_uuid(coat_parent_uuid)
    assert coat_parent is not None
    assert coat_parent.lineage_uuid == completion.lineage_uuid

    actor.remove_condition("Flaming Coat")

    assert sword.extra_damage_dices == []
    assert sword.extra_damage_dices_numbers == []
    assert sword.extra_damage_bonus == []
    assert sword.extra_damage_type == []


def test_legacy_consumable_constructor_and_class_surface_is_absent() -> None:
    """No maintained Python module can import or define the deleted surface."""
    for symbol in _LEGACY_SYMBOLS:
        assert not hasattr(fixture_items, symbol)
        assert not hasattr(item_exports, symbol)

    violations: list[str] = []
    roots = ("ai", "custom_ai", "devtools", "dnd", "server", "tests")
    for root_name in roots:
        for path in (_ROOT / root_name).rglob("*.py"):
            if "to_archive" in path.parts or path == Path(__file__):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    if node.name in _LEGACY_SYMBOLS:
                        violations.append(
                            f"{path.relative_to(_ROOT)}:{node.lineno}:"
                            f"definition:{node.name}"
                        )
                if isinstance(node, ast.ImportFrom):
                    imported = _LEGACY_SYMBOLS.intersection(
                        alias.name for alias in node.names
                    )
                    if imported:
                        violations.append(
                            f"{path.relative_to(_ROOT)}:{node.lineno}:"
                            f"import:{','.join(sorted(imported))}"
                        )

    assert violations == []
