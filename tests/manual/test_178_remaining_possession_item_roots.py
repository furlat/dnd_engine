"""Canonical coverage for the final six inventoried possession roots."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.extensions.field_focus as field_focus
import dnd.monsters.circus_fighter as circus_fighter
import dnd.monsters.circus_fighter_items as circus_items
from dnd.blocks.base_item import (
    UsableItem,
)
from dnd.blocks.equipment import (
    BodyArmor,
    Weapon,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.types.equipment import (
    ArmorType,
    BodyPart,
    WeaponProperty,
    WeaponSlot,
)
from dnd.core.events.resolution_events import (
    RangeType,
)
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus
from dnd.runtime_reset import reset_engine_runtime


_CIRCUS_RECIPES = (
    circus_items.RUSTY_DAGGER_RECIPE,
    circus_items.FLAMING_SCIMITAR_RECIPE,
    circus_items.PERFORMER_LEATHER_RECIPE,
    circus_items.LONGSWORD_PLUS_ONE_RECIPE,
    circus_items.SOUL_DRAINING_MORNINGSTAR_RECIPE,
)


def test_six_possession_roots_are_exact_public_registry_definitions() -> None:
    """All six definitions are constructible possessions in the frozen set."""
    loaded = bootstrap_content_system()
    declarations = (
        field_focus.FIELD_KIT_DECLARATION,
        *circus_items.NEURODRAGON_CIRCUS_ITEM_DECLARATIONS,
    )
    assert tuple(
        declaration.ref.content_id for declaration in declarations
    ) == (
        "gear.field_kit",
        "weapon.circus.rusty_dagger",
        "weapon.circus.flaming_scimitar",
        "armor.circus.performer_leather",
        "weapon.circus.longsword_plus_one",
        "weapon.circus.soul_draining_morningstar",
    )

    assert field_focus.FIELD_KIT_DECLARATION in declarations
    assert set(circus_items.NEURODRAGON_CIRCUS_ITEM_DECLARATIONS) <= set(
        declarations,
    )
    for declaration in declarations:
        assert (
            loaded.registry.resolve_factory(declaration.ref)
            is declaration
        )
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )


def test_field_kit_materialization_preserves_charges_action_and_visuals() -> None:
    """The parameterized recipe retains the exact usable-item behavior."""
    reset_engine_runtime(grid_size=(4, 3))
    owner_uuid = uuid4()
    recipe = field_focus.field_kit_recipe(charges=3)
    kit = materialize_item(
        recipe,
        owner_uuid,
        origin=ItemRuntimeOrigin.LOOT,
        expected_type=UsableItem,
    )

    assert kit.content_ref == field_focus.FIELD_KIT_REF
    assert kit.source_entity_uuid == owner_uuid
    assert kit.name == "Field Kit"
    assert kit.description == (
        "A compact kit that deploys tactical focus gear."
    )
    assert kit.map_char == "kit"
    assert kit.visual_item_name is None
    assert kit.visual_variant_id is None
    assert kit.charges == 3
    assert kit.max_charges == 3
    assert len(kit.use_action_templates) == 1
    action = kit.use_action_templates[0]
    assert isinstance(action, field_focus.DeployFieldFocus)
    assert action.source_entity_uuid == owner_uuid
    assert action.template
    assert action.charge_cost == 1
    assert action.costs[0].cost_type == "bonus_actions"
    assert action.costs[0].cost == 1

    state = kit.to_item_presentation_state()
    assert state.content_ref is not None
    assert state.content_ref.model_dump(mode="json") == (
        field_focus.FIELD_KIT_REF.model_dump(mode="json")
    )
    assert state.visual_item_name == "Field Kit"
    assert state.visual_variant_id is None
    binding = ITEM_RUNTIME_BINDINGS.require(kit.uuid)
    assert binding.recipe == recipe
    assert binding.origin is ItemRuntimeOrigin.LOOT

    parameter_model = (
        field_focus.FIELD_KIT_DECLARATION.construction.parameter_model
        if field_focus.FIELD_KIT_DECLARATION.construction is not None
        else None
    )
    assert parameter_model is not None
    assert parameter_model is field_focus.FieldKitParameters
    assert field_focus.FieldKitParameters.model_validate({}).charges == 1
    with pytest.raises(ValidationError):
        parameter_model.model_validate({"charges": 1, "alias": "kit"})


def test_circus_weapon_materialization_preserves_all_mechanical_profiles() -> None:
    """All four weapons retain their exact dice, modifiers, and visuals."""
    reset_engine_runtime(grid_size=(4, 3))
    owner_uuid = uuid4()
    rusty, flaming, longsword, morningstar = (
        materialize_item(
            recipe,
            owner_uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        )
        for recipe in (
            circus_items.RUSTY_DAGGER_RECIPE,
            circus_items.FLAMING_SCIMITAR_RECIPE,
            circus_items.LONGSWORD_PLUS_ONE_RECIPE,
            circus_items.SOUL_DRAINING_MORNINGSTAR_RECIPE,
        )
    )

    assert rusty.content_ref == circus_items.RUSTY_DAGGER_REF
    assert rusty.name == "Rusty Dagger"
    assert rusty.damage_dice == 4
    assert rusty.dice_numbers == 1
    assert rusty.damage_type is DamageType.PIERCING
    assert tuple(rusty.properties) == (
        WeaponProperty.FINESSE,
        WeaponProperty.LIGHT,
        WeaponProperty.THROWN,
    )
    assert rusty.range.type is RangeType.REACH
    assert rusty.range.normal == 5
    assert rusty.attack_bonus.advantage is AdvantageStatus.DISADVANTAGE
    assert rusty.visual_item_name is None
    assert rusty.visual_variant_id is None

    assert flaming.content_ref == circus_items.FLAMING_SCIMITAR_REF
    assert flaming.name == "Flaming Scimitar"
    assert flaming.visual_item_name == "Scimitar"
    assert flaming.visual_variant_id == "30000017"
    assert flaming.damage_dice == 6
    assert flaming.dice_numbers == 1
    assert flaming.damage_type is DamageType.SLASHING
    assert tuple(flaming.properties) == (
        WeaponProperty.FINESSE,
        WeaponProperty.LIGHT,
    )
    assert flaming.extra_damage_dices == [6]
    assert flaming.extra_damage_dices_numbers == [1]
    assert tuple(flaming.extra_damage_type) == (DamageType.FIRE,)
    assert flaming.extra_damage_bonus[0].normalized_score == 0

    assert longsword.content_ref == circus_items.LONGSWORD_PLUS_ONE_REF
    assert longsword.name == "Longsword +1"
    assert longsword.damage_dice == 8
    assert longsword.dice_numbers == 1
    assert longsword.damage_type is DamageType.SLASHING
    assert tuple(longsword.properties) == (WeaponProperty.VERSATILE,)
    assert longsword.attack_bonus.normalized_score == 1
    assert longsword.damage_bonus is not None
    assert longsword.damage_bonus.normalized_score == 1
    assert longsword.extra_damage_dices == []
    assert longsword.visual_item_name is None
    assert longsword.visual_variant_id is None

    assert (
        morningstar.content_ref
        == circus_items.SOUL_DRAINING_MORNINGSTAR_REF
    )
    assert morningstar.name == "Soul-Draining Morningstar"
    assert morningstar.damage_dice == 8
    assert morningstar.dice_numbers == 1
    assert morningstar.damage_type is DamageType.PIERCING
    assert morningstar.properties == []
    assert morningstar.extra_damage_dices == [4]
    assert morningstar.extra_damage_dices_numbers == [1]
    assert tuple(morningstar.extra_damage_type) == (DamageType.NECROTIC,)
    assert morningstar.extra_damage_bonus[0].normalized_score == 0
    assert morningstar.visual_item_name is None
    assert morningstar.visual_variant_id is None

    for item, recipe in zip(
        (rusty, flaming, longsword, morningstar),
        (
            circus_items.RUSTY_DAGGER_RECIPE,
            circus_items.FLAMING_SCIMITAR_RECIPE,
            circus_items.LONGSWORD_PLUS_ONE_RECIPE,
            circus_items.SOUL_DRAINING_MORNINGSTAR_RECIPE,
        ),
        strict=True,
    ):
        assert ITEM_RUNTIME_BINDINGS.require(item.uuid).recipe == recipe


def test_performer_armor_materialization_preserves_exact_ac_policy() -> None:
    """The circus armor retains its light/body and Dexterity-cap facts."""
    reset_engine_runtime(grid_size=(4, 3))
    armor = materialize_item(
        circus_items.PERFORMER_LEATHER_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )

    assert armor.content_ref == circus_items.PERFORMER_LEATHER_REF
    assert armor.name == "Performer's Leather Armor"
    assert armor.type is ArmorType.LIGHT
    assert armor.body_part is BodyPart.BODY
    assert armor.ac.normalized_score == 11
    assert armor.max_dex_bonus.normalized_score == 5
    assert armor.visual_item_name is None
    assert armor.visual_variant_id is None


def test_circus_actor_uses_only_canonical_bound_possessions() -> None:
    """The retained actor composition no longer calls legacy constructors."""
    reset_engine_runtime(grid_size=(6, 4))
    actor = circus_fighter.create_warrior(
        source_id=uuid4(),
        proficiency_bonus=2,
        name="Registry Performer",
        position=(1, 1),
    )
    main = actor.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN)
    off = actor.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF)
    armor = actor.equipment.get_item_by_slot(BodyPart.BODY)

    assert isinstance(main, Weapon)
    assert isinstance(off, Weapon)
    assert isinstance(armor, BodyArmor)
    assert main.content_ref == circus_items.FLAMING_SCIMITAR_REF
    assert off.content_ref == circus_items.RUSTY_DAGGER_REF
    assert armor.content_ref == circus_items.PERFORMER_LEATHER_REF
    assert ITEM_RUNTIME_BINDINGS.require(main.uuid).recipe == (
        circus_items.FLAMING_SCIMITAR_RECIPE
    )
    assert ITEM_RUNTIME_BINDINGS.require(off.uuid).recipe == (
        circus_items.RUSTY_DAGGER_RECIPE
    )
    assert ITEM_RUNTIME_BINDINGS.require(armor.uuid).recipe == (
        circus_items.PERFORMER_LEATHER_RECIPE
    )


def test_no_legacy_possession_constructor_surface_remains() -> None:
    """The six old construction functions cannot coexist with recipes."""
    assert not hasattr(field_focus, "create_field_kit")
    for name in (
        "create_dagger",
        "create_flaming_scimitar",
        "create_light_armor",
        "create_longsword_plus_one",
        "create_morningstar",
    ):
        assert not hasattr(circus_fighter, name)

    assert tuple(recipe.ref for recipe in _CIRCUS_RECIPES) == tuple(
        declaration.ref
        for declaration in circus_items.NEURODRAGON_CIRCUS_ITEM_DECLARATIONS
    )
