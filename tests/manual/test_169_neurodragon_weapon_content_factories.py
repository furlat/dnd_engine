"""Canonical registry coverage for NeuroDragon's custom weapon roots."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.items as item_exports
import dnd.items.weapons as weapon_definitions
from dnd.blocks.equipment import Weapon
from dnd.content_system.icon_bindings import (
    BUILT_IN_CONTENT_ICON_BINDING_LEDGER,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import scan_module_content_declarations
from dnd.core.equipment_types import WeaponProperty, WeaponSlot
from dnd.core.events import EventHandler, EventQueue, RangeType
from dnd.core.creature_types import DamageType
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime


_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_FACTORIES = frozenset(
    {
        "create_arcane_staff",
        "create_assassin_dagger",
        "create_double_bladed_sword",
    },
)


def test_neurodragon_weapon_declarations_are_exact_original_content() -> None:
    """All roots own exact stable identity, presentation, and provenance."""
    declarations = weapon_definitions.NEURODRAGON_WEAPON_DECLARATIONS

    assert declarations == (
        weapon_definitions.DOUBLE_BLADED_SWORD_DECLARATION,
        weapon_definitions.ASSASSIN_DAGGER_DECLARATION,
        weapon_definitions.ARCANE_STAFF_DECLARATION,
    )
    assert tuple(
        declaration.ref.content_id for declaration in declarations
    ) == (
        "weapon.double_bladed_sword",
        "weapon.assassin_dagger",
        "weapon.arcane_staff",
    )

    discovered = scan_module_content_declarations(weapon_definitions)
    icon_rows = {
        row.content_ref.identity_key: row
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
    }
    for declaration in declarations:
        assert declaration in discovered
        assert declaration.ref.pack_id == "content.neurodragon"
        assert declaration.ref.content_version == 1
        assert declaration.descriptor.ref == declaration.ref
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
    recipes = (
        weapon_definitions.DOUBLE_BLADED_SWORD_RECIPE,
        weapon_definitions.ASSASSIN_DAGGER_RECIPE,
        weapon_definitions.ARCANE_STAFF_RECIPE,
    )
    assert tuple(recipe.ref for recipe in recipes) == tuple(
        declaration.ref for declaration in declarations
    )
    assert all(recipe.parameters == {} for recipe in recipes)


@pytest.mark.parametrize(
    ("declaration", "extra"),
    (
        (weapon_definitions.ASSASSIN_DAGGER_DECLARATION, {"unseen_die": 8}),
        (weapon_definitions.ARCANE_STAFF_DECLARATION, {"spell_bonus": 2}),
    ),
)
def test_neurodragon_weapon_parameters_forbid_sideways_variants(
    declaration,
    extra: dict[str, int],
) -> None:
    """Custom mechanics remain definition-owned rather than recipe overrides."""
    assert declaration.construction is not None
    parameter_model = declaration.construction.parameter_model
    assert parameter_model.model_validate({}).model_dump() == {}
    with pytest.raises(ValidationError):
        parameter_model.model_validate(extra)


def test_assassin_dagger_materialization_and_handler_lifecycle_are_exact() -> None:
    """The recipe preserves weapon mechanics and equip-scoped unseen handler."""
    reset_engine_runtime(grid_size=(4, 3))
    attacker = Entity.create(source_entity_uuid=uuid4(), name="Assassin")
    dagger = materialize_item(
        weapon_definitions.ASSASSIN_DAGGER_RECIPE,
        attacker.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )

    assert dagger.content_ref == weapon_definitions.ASSASSIN_DAGGER_REF
    assert dagger.name == "Assassin's Dagger"
    assert dagger.visual_item_name == "Dagger"
    assert dagger.visual_variant_id == "10000004"
    assert dagger.damage_dice == 4
    assert dagger.dice_numbers == 1
    assert dagger.damage_type is DamageType.PIERCING
    assert tuple(dagger.properties) == (
        WeaponProperty.FINESSE,
        WeaponProperty.LIGHT,
    )
    assert dagger.range.type is RangeType.REACH
    assert dagger.range.normal == 5

    assert attacker.equipment.equip(dagger, WeaponSlot.MELEE_MAIN)
    handler_uuid = getattr(dagger, "_handler_uuid")
    assert handler_uuid is not None
    assert attacker.get_event_handler_by_name("Unseen Strike") is not None
    assert EventHandler.get(handler_uuid) is not None

    assert attacker.equipment.unequip(WeaponSlot.MELEE_MAIN) is dagger
    assert getattr(dagger, "_handler_uuid") is None
    assert attacker.get_event_handler_by_name("Unseen Strike") is None
    assert handler_uuid not in EventQueue._event_handlers


def test_double_bladed_sword_materializes_one_shared_custom_mechanic() -> None:
    """Named double-blade colors remain recipes over one two-handed weapon."""
    sword = materialize_item(
        weapon_definitions.DOUBLE_BLADED_SWORD_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )

    assert sword.content_ref == weapon_definitions.DOUBLE_BLADED_SWORD_REF
    assert sword.name == "Double-Bladed Sword"
    assert sword.damage_dice == 4
    assert sword.dice_numbers == 2
    assert sword.damage_type is DamageType.SLASHING
    assert tuple(sword.properties) == (
        WeaponProperty.TWO_HANDED,
        WeaponProperty.MARTIAL,
    )
    assert sword.range.type is RangeType.REACH
    assert sword.range.normal == 5


def test_arcane_staff_materialization_modifier_is_exactly_equip_scoped() -> None:
    """The canonical staff adds exactly +1 spell attack only while equipped."""
    reset_engine_runtime(grid_size=(4, 3))
    caster = Entity.create(source_entity_uuid=uuid4(), name="Arcane wielder")
    staff = materialize_item(
        weapon_definitions.ARCANE_STAFF_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    base_spell_attack = caster.spellcasting.spell_attack_bonus.normalized_score

    assert staff.content_ref == weapon_definitions.ARCANE_STAFF_REF
    assert staff.name == "Arcane Staff"
    assert staff.visual_item_name == "Quarterstaff"
    assert staff.visual_variant_id == "1000000f"
    assert staff.damage_dice == 6
    assert staff.dice_numbers == 1
    assert staff.damage_type is DamageType.BLUDGEONING
    assert tuple(staff.properties) == (WeaponProperty.VERSATILE,)
    assert staff.range.type is RangeType.REACH
    assert staff.range.normal == 5

    assert caster.equipment.equip(staff, WeaponSlot.MELEE_MAIN)
    assert (
        caster.spellcasting.spell_attack_bonus.normalized_score
        == base_spell_attack + 1
    )
    assert caster.equipment.unequip(WeaponSlot.MELEE_MAIN) is staff
    assert (
        caster.spellcasting.spell_attack_bonus.normalized_score
        == base_spell_attack
    )


def test_neurodragon_weapon_legacy_constructor_surface_is_absent() -> None:
    """No public constructor alias remains in engine or maintained tests."""
    for name in _LEGACY_FACTORIES:
        assert not hasattr(weapon_definitions, name)
        assert not hasattr(item_exports, name)

    violations: list[str] = []
    for path in (*(_ROOT / "dnd").rglob("*.py"), *(_ROOT / "tests").rglob("*.py")):
        if "to_archive" in path.parts or path == Path(__file__):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module not in {"dnd.items", "dnd.items.weapons"}:
                continue
            imported = _LEGACY_FACTORIES.intersection(
                alias.name for alias in node.names
            )
            if imported:
                violations.append(
                    f"{path.relative_to(_ROOT)}:{node.lineno}:"
                    f"{','.join(sorted(imported))}"
                )

    assert violations == []
