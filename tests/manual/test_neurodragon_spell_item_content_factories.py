"""Canonical identity and behavior coverage for spell-bearing possessions."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.items as item_exports
import dnd.items.spell_items as spell_items
import dnd.items.environment_interactables as fixture_items
from dnd.actions.standard import (
    SpellAction,
)
from dnd.blocks.base_item import (
    UsableItem,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.provenance import ContentReviewStatus
from dnd.core.content.registration import get_content_declaration
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import (
    MageArmor,
)
from dnd.spells.enchantment import HoldPerson
from dnd.spells.evocation import (
    BurningHands,
    Fireball,
    FireBolt,
    MagicMissile,
)
from dnd.spells.illusion import Invisibility
from dnd.spells.transmutation import SpikeGrowth


_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_SYMBOLS = frozenset({
    "AcidFlaskSpell",
    "SpellScroll",
    "create_acid_flask",
    "create_scroll_of_fire_bolt",
    "create_scroll_of_fireball",
    "create_scroll_of_hold_person",
    "create_scroll_of_invisibility",
    "create_scroll_of_mage_armor",
    "create_scroll_of_magic_missile",
    "create_scroll_of_spike_growth",
    "create_wand_of_fire",
    "create_wand_of_magic_missiles",
})


def test_spell_item_declarations_and_recipes_are_exact() -> None:
    """Ten possession roots own reviewed descriptors and canonical recipes."""
    declarations = spell_items.NEURODRAGON_SPELL_ITEM_DECLARATIONS
    recipes = (
        spell_items.FIREBALL_SCROLL_RECIPE,
        spell_items.MAGIC_MISSILE_SCROLL_RECIPE,
        spell_items.HOLD_PERSON_SCROLL_RECIPE,
        spell_items.MAGE_ARMOR_SCROLL_RECIPE,
        spell_items.SPIKE_GROWTH_SCROLL_RECIPE,
        spell_items.FIRE_BOLT_SCROLL_RECIPE,
        spell_items.WAND_OF_MAGIC_MISSILES_RECIPE,
        spell_items.WAND_OF_FIRE_RECIPE,
        spell_items.ACID_FLASK_RECIPE,
        spell_items.INVISIBILITY_SCROLL_RECIPE,
    )
    assert tuple(row.ref.content_id for row in declarations) == (
        "spell_item.scroll_fireball",
        "spell_item.scroll_magic_missile",
        "spell_item.scroll_hold_person",
        "spell_item.scroll_mage_armor",
        "spell_item.scroll_spike_growth",
        "spell_item.scroll_fire_bolt",
        "spell_item.wand_magic_missiles",
        "spell_item.wand_fire",
        "consumable.acid_flask",
        "spell_item.scroll_invisibility",
    )
    assert tuple(recipe.ref for recipe in recipes) == tuple(
        declaration.ref for declaration in declarations
    )
    for declaration, recipe in zip(declarations, recipes, strict=True):
        assert declaration.ref.pack_id == "content.neurodragon"
        assert declaration.descriptor.visibility.value == "public"
        assert declaration.descriptor.presentation.icon_key is not None
        assert (
            declaration.provenance.review_status
            is ContentReviewStatus.REVIEWED
        )
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )
        assert recipe.ref == declaration.ref


def test_spell_item_dependency_closure_targets_exact_metadata_identities() -> None:
    """Every granted spell is an exact runtime-reference dependency."""
    expected = {
        "spell_item.scroll_fireball": (Fireball,),
        "spell_item.scroll_magic_missile": (MagicMissile,),
        "spell_item.scroll_hold_person": (HoldPerson,),
        "spell_item.scroll_mage_armor": (MageArmor,),
        "spell_item.scroll_spike_growth": (SpikeGrowth,),
        "spell_item.scroll_fire_bolt": (FireBolt,),
        "spell_item.wand_magic_missiles": (MagicMissile,),
        "spell_item.wand_fire": (BurningHands, Fireball),
        "consumable.acid_flask": (spell_items._AcidFlaskSpell,),
        "spell_item.scroll_invisibility": (Invisibility,),
    }
    declarations = {
        row.ref.content_id: row
        for row in spell_items.NEURODRAGON_SPELL_ITEM_DECLARATIONS
    }
    expected_dependency_declaration_keys = {
        get_content_declaration(definition).ref.identity_key
        for definitions in expected.values()
        for definition in definitions
    }
    assert {
        declaration.ref.identity_key
        for declaration in spell_items.SPELL_ITEM_DEPENDENCY_DECLARATIONS
    } == (
        expected_dependency_declaration_keys
    )

    for content_id, definitions in expected.items():
        declaration = declarations[content_id]
        assert tuple(
            dependency.relation
            for dependency in declaration.dependencies
        ) == tuple(
            ContentDependencyRelation.GRANTS_SPELL
            for _ in definitions
        )
        assert tuple(
            dependency.target_ref
            for dependency in declaration.dependencies
        ) == tuple(
            get_content_declaration(definition).ref
            for definition in definitions
        )


def test_spell_item_recipe_parameters_are_closed_and_durable() -> None:
    """Cast level, caster level, and charges are the only supported variants."""
    cast_level = spell_items.FIREBALL_SCROLL_DECLARATION
    caster_level = spell_items.FIRE_BOLT_SCROLL_DECLARATION
    charges = spell_items.WAND_OF_FIRE_DECLARATION
    empty = spell_items.ACID_FLASK_DECLARATION
    assert cast_level.construction is not None
    assert caster_level.construction is not None
    assert charges.construction is not None
    assert empty.construction is not None

    assert cast_level.construction.parameter_model.model_validate(
        {},
    ).model_dump() == {"cast_level": 3}
    assert caster_level.construction.parameter_model.model_validate(
        {},
    ).model_dump() == {"caster_level": 5}
    assert charges.construction.parameter_model.model_validate(
        {},
    ).model_dump() == {"charges": 7}
    assert empty.construction.parameter_model.model_validate({}).model_dump() == {}
    with pytest.raises(ValidationError):
        cast_level.construction.parameter_model.model_validate(
            {"cast_level": 3, "spell_name": "Meteor Swarm"},
        )

    level_three = spell_items.fireball_scroll_recipe(cast_level=3)
    level_five = spell_items.fireball_scroll_recipe(cast_level=5)
    four_charge_wand = spell_items.wand_of_fire_recipe(charges=4)
    assert level_three.parameters == {"cast_level": 3}
    assert level_five.parameters == {"cast_level": 5}
    assert level_three.recipe_digest != level_five.recipe_digest
    assert four_charge_wand.parameters == {"charges": 4}


def test_scroll_materialization_preserves_stack_and_cast_variants() -> None:
    """Recipe identity owns stack compatibility and scroll cast level."""
    reset_engine_runtime(grid_size=(5, 4))
    owner = Entity.create(source_entity_uuid=uuid4(), name="Scroll bearer")
    level_three_recipe = spell_items.fireball_scroll_recipe(cast_level=3)
    level_five_recipe = spell_items.fireball_scroll_recipe(cast_level=5)
    first = materialize_item(
        level_three_recipe,
        owner.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=spell_items.SpellGrantingItem,
    )
    second = materialize_item(
        level_three_recipe,
        owner.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=spell_items.SpellGrantingItem,
    )
    higher = materialize_item(
        level_five_recipe,
        owner.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=spell_items.SpellGrantingItem,
    )

    assert first.content_ref == spell_items.FIREBALL_SCROLL_REF
    assert first.stack_id == second.stack_id == level_three_recipe.recipe_digest
    assert higher.stack_id == level_five_recipe.recipe_digest
    assert higher.stack_id != first.stack_id
    first_action = first.get_use_actions(owner.uuid)[0]
    higher_action = higher.get_use_actions(owner.uuid)[0]
    assert isinstance(first_action, Fireball)
    assert isinstance(higher_action, Fireball)
    assert first_action.cast_at_level == 3
    assert higher_action.cast_at_level == 5
    assert first_action.source_item_uuid == first.uuid


def test_wands_and_acid_flask_preserve_action_and_charge_behavior() -> None:
    """Wands retain their charge menu and Acid Flask remains item-private."""
    reset_engine_runtime(grid_size=(5, 4))
    owner = Entity.create(source_entity_uuid=uuid4(), name="Item bearer")
    wand = materialize_item(
        spell_items.wand_of_fire_recipe(charges=4),
        owner.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=spell_items.SpellGrantingItem,
    )
    actions = wand.get_use_actions(owner.uuid)
    assert all(isinstance(row, SpellAction) for row in actions)
    spell_actions = tuple(
        row
        for row in actions
        if isinstance(row, SpellAction)
    )
    assert tuple(
        (type(row), row.charge_cost, row.cast_at_level)
        for row in spell_actions
    ) == (
        (BurningHands, 1, 1),
        (Fireball, 3, 3),
        (Fireball, 4, 4),
    )
    assert wand.charges == wand.max_charges == 4
    assert wand.is_consumable is False

    acid = materialize_item(
        spell_items.ACID_FLASK_RECIPE,
        owner.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=spell_items.SpellGrantingItem,
    )
    acid_actions = acid.get_use_actions(owner.uuid)
    assert len(acid_actions) == 1
    assert isinstance(acid_actions[0], SpellAction)
    assert type(acid_actions[0]) is spell_items._AcidFlaskSpell
    assert acid_actions[0].get_semantic_key() == (
        spell_items.ACID_FLASK_SPELL_REF.identity_key
    )
    assert acid.is_consumable is True
    assert acid.charges == acid.max_charges == 1
    assert acid.max_stack == 20


def test_all_spell_item_templates_are_bound_to_their_exact_item_root() -> None:
    """Every declared granted template remains item-rooted through cloning."""
    reset_engine_runtime(grid_size=(5, 4))
    owner = Entity.create(source_entity_uuid=uuid4(), name="Spell item bearer")
    expected_templates_by_recipe = (
        (spell_items.FIREBALL_SCROLL_RECIPE, (
            (spell_items.FIREBALL_DECLARATION.ref, 1, 3, 5),
        )),
        (spell_items.MAGIC_MISSILE_SCROLL_RECIPE, (
            (spell_items.MAGIC_MISSILE_DECLARATION.ref, 1, 1, 1),
        )),
        (spell_items.HOLD_PERSON_SCROLL_RECIPE, (
            (spell_items.HOLD_PERSON_DECLARATION.ref, 1, 2, 3),
        )),
        (spell_items.MAGE_ARMOR_SCROLL_RECIPE, (
            (spell_items.MAGE_ARMOR_DECLARATION.ref, 1, 1, 1),
        )),
        (spell_items.SPIKE_GROWTH_SCROLL_RECIPE, (
            (spell_items.SPIKE_GROWTH_DECLARATION.ref, 1, 2, 3),
        )),
        (spell_items.FIRE_BOLT_SCROLL_RECIPE, (
            (spell_items.FIRE_BOLT_DECLARATION.ref, 1, 0, 5),
        )),
        (spell_items.WAND_OF_MAGIC_MISSILES_RECIPE, (
            (spell_items.MAGIC_MISSILE_DECLARATION.ref, 1, 1, 1),
        )),
        (spell_items.WAND_OF_FIRE_RECIPE, (
            (spell_items.BURNING_HANDS_DECLARATION.ref, 1, 1, 1),
            (spell_items.FIREBALL_DECLARATION.ref, 3, 3, 5),
            (spell_items.FIREBALL_DECLARATION.ref, 4, 4, 7),
        )),
        (spell_items.ACID_FLASK_RECIPE, (
            (spell_items.ACID_FLASK_SPELL_DECLARATION.ref, 1, 0, 1),
        )),
        (spell_items.INVISIBILITY_SCROLL_RECIPE, (
            (spell_items.INVISIBILITY_DECLARATION.ref, 1, 2, 3),
        )),
    )

    for recipe, expected_templates in expected_templates_by_recipe:
        item = materialize_item(
            recipe,
            owner.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=spell_items.SpellGrantingItem,
        )
        assert item.content_ref == recipe.ref
        actual_templates = tuple(
            (
                get_content_declaration(type(template)).ref,
                template.charge_cost,
                template.cast_at_level,
                template.caster_level,
            )
            for template in item.use_action_templates
            if isinstance(template, SpellAction)
        )
        assert len(actual_templates) == len(item.use_action_templates)
        assert actual_templates == expected_templates
        for template in item.use_action_templates:
            declaration = get_content_declaration(type(template))
            expected = BehaviorBinding(
                definition_ref=declaration.ref,
                provided_by_ref=recipe.ref,
                origin_root_ref=recipe.ref,
                runtime_owner_uuid=item.uuid,
            )
            assert template.behavior_binding == expected

        clones = item.get_use_actions(owner.uuid)
        assert len(clones) == len(item.use_action_templates)
        for template, clone in zip(
            item.use_action_templates,
            clones,
            strict=True,
        ):
            assert clone.behavior_binding == template.behavior_binding
            assert clone.source_item_uuid == item.uuid
        actual_clones = tuple(
            (
                clone.behavior_binding.definition_ref,
                clone.charge_cost,
                clone.cast_at_level,
                clone.caster_level,
            )
            for clone in clones
            if isinstance(clone, SpellAction)
            and clone.behavior_binding is not None
        )
        assert len(actual_clones) == len(clones)
        assert actual_clones == expected_templates


def test_spell_granting_item_is_a_mechanism_not_a_content_root() -> None:
    """The shared runtime mechanism cannot enter recipes or the catalog."""
    assert issubclass(spell_items.SpellGrantingItem, UsableItem)
    with pytest.raises(ValueError, match="no content declaration"):
        get_content_declaration(spell_items.SpellGrantingItem)
    assert all(
        declaration.construction is None
        or declaration.construction.factory is not spell_items.SpellGrantingItem
        for declaration in spell_items.NEURODRAGON_SPELL_ITEM_DECLARATIONS
    )


def test_legacy_spell_item_surface_is_absent_from_active_python() -> None:
    """No old constructor or class remains available to active callers."""
    for symbol in _LEGACY_SYMBOLS:
        assert not hasattr(fixture_items, symbol)
        assert not hasattr(item_exports, symbol)

    for path in (
        _ROOT / "dnd",
        _ROOT / "tests",
    ):
        for source_path in path.rglob("*.py"):
            if "to_archive" in source_path.parts:
                continue
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert not (
                        node.module == "dnd.items.environment_interactables"
                        and any(
                            alias.name in _LEGACY_SYMBOLS
                            for alias in node.names
                        )
                    ), f"{source_path} imports a retired spell-item symbol"
