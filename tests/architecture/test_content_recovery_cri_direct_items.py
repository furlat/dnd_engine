"""Current registration and direct-item contracts after the recovery cut.

The CR-0 ledger remains historical documentation. Source bytes, old row counts
and a census of test names do not define current ownership or visible behavior.
These checks use the content system already initialized by tests/conftest.py.
Actual gameplay and rendered results have their own event/replay tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from dnd.content.items.authored_item_builders import DIRECT_ITEM_BUILDERS, build_authored_item
from dnd.content.items.authored_item_definitions import (
    ACOLYTE_GEAR_DEFINITIONS,
    AUTHORED_WEAPON_DEFINITIONS,
    AUTHORED_WEARABLE_DEFINITIONS,
    STATIC_BLOCKER_DEFINITIONS,
)
from dnd.content.items.door_profiles import DOOR_PROFILES
from dnd.content.items.environment_item_builders import LIQUID_BARREL_PROFILES
from dnd.content.items.ground_hardware_builders import GROUND_HARDWARE_PROFILES
from dnd.content.items.world_prop_builders import WORLD_PROP_PROFILES
from dnd.content.items.trap_hardware_builders import TRAP_HARDWARE_PROFILES
from dnd.content_system.builtin_inventory import BUILT_IN_DECLARATION_INVENTORY
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import ContentDeclarationMode, get_content_declaration
from dnd.spells.conjuration import build_guardian_of_faith_object


_PRIVATE_GUARDIAN_ID = "environment.spell_object.guardian_of_faith"
_BEHAVIOR_ITEM_IDS = frozenset({
    "weapon.arcane_staff",
    "weapon.assassin_dagger",
    "apparel.spellblade_crown",
    "armor.padded",
    "armor.scale_mail",
    "armor.half_plate",
    "armor.ring_mail",
    "armor.chain_mail",
    "armor.splint",
    "armor.plate",
    "consumable.healing_potion",
    "consumable.potion_haste",
    "consumable.potion_greater_invisibility",
    "consumable.potion_true_seeing",
    "consumable.weapon_coat.fire",
    "consumable.weapon_coat.lightning",
    "consumable.weapon_coat.concentration_fire",
    "consumable.weapon_coat.timed_fire",
    "consumable.acid_flask",
    "spell_item.scroll_fireball",
    "spell_item.scroll_magic_missile",
    "spell_item.scroll_hold_person",
    "spell_item.scroll_mage_armor",
    "spell_item.scroll_spike_growth",
    "spell_item.scroll_invisibility",
    "spell_item.scroll_fire_bolt",
    "spell_item.wand_magic_missiles",
    "spell_item.wand_fire",
    "equipment.portable_torch",
    "environment.directional_door",
    "environment.campfire",
    "environment.arcane_device",
    "environment.arcane_machine_gun",
    "environment.wall_torch",
    "environment.trap_lever",
    "environment.storage_chest",
    "environment.chest.fantasy_a1",
    "environment.chest.fantasy_a3",
    "environment.chest.fantasy_b1",
    "environment.fireball_cannon",
    "environment.spell_object.heroes_feast",
    "gear.field_kit",
})

_FIXED_ACTIVE_VISUALS = {
    "apparel.spellblade_crown": ("Crown", None),
    "apparel.armored_boots": ("Armored Boots", None),
    "apparel.bracers": ("Bracers", None),
    "apparel.chain_coif": ("Chain Coif", None),
    "apparel.cloth_hood": ("Cloth Hood", None),
    "apparel.cloth_shoes": ("Cloth Shoes", None),
    "apparel.common_clothes": ("Common Clothes", None),
    "apparel.costume": ("Costume", None),
    "apparel.fine_clothes": ("Fine Clothes", None),
    "apparel.gauntlets": ("Gauntlets", None),
    "apparel.great_helm": ("Great Helm", None),
    "apparel.horned_helmet": ("Horned Helmet", None),
    "apparel.leather_boots": ("Leather Boots", None),
    "apparel.leather_gloves": ("Leather Gloves", None),
    "apparel.leather_hood": ("Leather Hood", None),
    "apparel.leather_shoes": ("Leather Shoes", None),
    "apparel.monster_hands": ("Monster Hands", None),
    "apparel.monster_helm": ("Monster Helm", None),
    "apparel.robes": ("Robes", None),
    "apparel.sandals": ("Sandals", None),
    "apparel.travelers_clothes": ("Traveler's Clothes", None),
    "consumable.acid_flask": ("Acid Flask", "acid_flask"),
    "spell_item.scroll_fire_bolt": ("Scroll of Fire Bolt", "scroll_fire_bolt_cl5"),
    "spell_item.scroll_fireball": ("Scroll of Fireball", "scroll_fireball_l3"),
    "spell_item.scroll_hold_person": (
        "Scroll of Hold Person",
        "scroll_hold_person_l2",
    ),
    "spell_item.scroll_invisibility": (
        "Scroll of Invisibility",
        "scroll_invisibility_l2",
    ),
    "spell_item.scroll_mage_armor": (
        "Scroll of Mage Armor",
        "scroll_mage_armor_l1",
    ),
    "spell_item.scroll_magic_missile": (
        "Scroll of Magic Missile",
        "scroll_magic_missile_l1",
    ),
    "spell_item.scroll_spike_growth": (
        "Scroll of Spike Growth",
        "scroll_spike_growth_l2",
    ),
    "spell_item.wand_fire": ("Wand of Fire", "fire"),
    "spell_item.wand_magic_missiles": (
        "Wand of Magic Missiles",
        "magic_missiles",
    ),
    "weapon.circus.flaming_scimitar": ("Scimitar", "30000017"),
    "weapon.arcane_staff": ("Quarterstaff", "1000000f"),
    "weapon.assassin_dagger": ("Dagger", "10000004"),
    "weapon.creature.bandit_captain_thrown_dagger": ("Dagger", None),
    "weapon.creature.bugbear_morningstar": ("Morningstar", None),
    "weapon.creature.kobold_sling": ("Sling", None),
    "weapon.creature.ogre_greatclub": ("Club", None),
    "weapon.creature.ogre_thrown_javelin": ("Javelin", None),
    "weapon.creature.ogre_zombie_morningstar": ("Morningstar", None),
    "weapon.creature.spy_hand_crossbow": ("Light Crossbow", None),
    "weapon.creature.thrown_javelin": ("Javelin", None),
}

# Explicit visible variants retained from the former test, without ledger/source audits.
_VARIANT_VISUALS = {'apparel.cloth_shoes.blue': ('Blue Cloth Shoes', 'Cloth Shoes', 'b0000005'),
 'apparel.cloth_shoes.dark': ('Dark Cloth Shoes', 'Cloth Shoes', 'b0000003'),
 'apparel.cloth_shoes.red': ('Red Cloth Shoes', 'Cloth Shoes', 'b0000004'),
 'apparel.common_clothes.farmhand_tunic': ("Farmhand's Tunic",
                                           'Common Clothes',
                                           '82000001'),
 'apparel.common_clothes.peasant_rags': ("Peasant's Rags",
                                         'Common Clothes',
                                         '82000009'),
 'apparel.costume.pit_fighter_wrap': ("Pit Fighter's Wrap",
                                      'Costume',
                                      '85000004'),
 'apparel.iron_helmet.steel': ('Steel Helmet', 'Iron Helmet', 'h0000008'),
 'apparel.leather_boots.brown': ('Brown Boots', 'Leather Boots', 'b0000009'),
 'apparel.leather_boots.dark': ('Dark Boots', 'Leather Boots', 'b0000008'),
 'apparel.leather_shoes.brown': ('Brown Leather Shoes',
                                 'Leather Shoes',
                                 'b0000007'),
 'apparel.robes.acolyte_vestments': ("Acolyte's Vestments",
                                     'Robes',
                                     '81000007'),
 'apparel.robes.dark_cultist': ('Dark Cultist Robes', 'Robes', '81000008'),
 'apparel.robes.hedge_wizard': ("Hedge Wizard's Robe", 'Robes', '8100000b'),
 'apparel.robes.necromancer': ("Necromancer's Robe", 'Robes', '81000004'),
 'apparel.robes.priest_vestments': ("Priest's Vestments", 'Robes', '81000003'),
 'apparel.robes.red_mage': ('Red Mage Robe', 'Robes', '81000005'),
 'apparel.robes.wizard': ("Wizard's Robe", 'Robes', '81000001'),
 'apparel.sandals.rope': ('Rope Sandals', 'Sandals', 'b0000002'),
 'apparel.travelers_clothes.thief_garb': ("Thief's Garb",
                                          "Traveler's Clothes",
                                          '84000006'),
 'apparel.wizard_hat.red': ('Red Wizard Hat', "Wizard's Hat", 'h0000011')}


def test_cri_initialized_registry_preserves_current_authored_owners() -> None:
    """Every built-in declaration resolves to its actual owner and presentation."""
    registry = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry
    declarations = BUILT_IN_DECLARATION_INVENTORY
    assert declarations
    assert len({row.ref.identity_key for row in declarations}) == len(declarations)
    for authored in declarations:
        installed = registry.resolve_definition(authored.ref)
        assert installed.mode is authored.mode
        assert installed.descriptor == authored.descriptor
        assert installed.construction == authored.construction
        assert installed.definition_payload == authored.definition_payload


def test_cri_direct_item_visual_values_preserve_authored_appearance() -> None:
    """Known gear keeps its visible values; new records follow their data owner."""
    for item_id, expected in _FIXED_ACTIVE_VISUALS.items():
        item = build_authored_item(item_id, uuid4())
        assert (item.visual_item_name, item.visual_variant_id) == expected, item_id
    for item_id, expected in _VARIANT_VISUALS.items():
        item = build_authored_item(item_id, uuid4())
        assert (item.name, item.visual_item_name, item.visual_variant_id) == expected, item_id

    for definitions in (
        ACOLYTE_GEAR_DEFINITIONS,
        AUTHORED_WEAPON_DEFINITIONS,
        AUTHORED_WEARABLE_DEFINITIONS,
        STATIC_BLOCKER_DEFINITIONS,
    ):
        for item_id, definition in definitions.items():
            item = build_authored_item(item_id, uuid4())
            assert item.name == definition.name, item_id
            assert item.visual_item_name == definition.visual_item_name, item_id
            assert item.visual_variant_id == definition.visual_variant_id, item_id


def test_cri_public_item_inventory_is_complete_and_direct() -> None:
    """All authored families and behavior items are fresh public constructions."""
    public_ids = set(DIRECT_ITEM_BUILDERS)
    expected = (
        set(ACOLYTE_GEAR_DEFINITIONS)
        | set(AUTHORED_WEAPON_DEFINITIONS)
        | set(AUTHORED_WEARABLE_DEFINITIONS)
        | set(STATIC_BLOCKER_DEFINITIONS)
        | set(DOOR_PROFILES)
        | set(TRAP_HARDWARE_PROFILES)
        | set(GROUND_HARDWARE_PROFILES)
        | set(WORLD_PROP_PROFILES)
        | set(LIQUID_BARREL_PROFILES)
        | _BEHAVIOR_ITEM_IDS
        | {"environment.directional_wall", "environment.cliff_face"}
    )
    assert public_ids == expected
    assert "environment.door" not in public_ids
    assert "environment.directional_door" in public_ids
    assert _PRIVATE_GUARDIAN_ID not in public_ids

    first = {item_id: build_authored_item(item_id, uuid4()) for item_id in public_ids}
    second = {item_id: build_authored_item(item_id, uuid4()) for item_id in public_ids}
    assert {item.item_id for item in first.values()} == public_ids
    assert {item.item_id for item in second.values()} == public_ids
    assert all(first[item_id].uuid != second[item_id].uuid for item_id in public_ids)
    guardian = build_guardian_of_faith_object(uuid4())
    assert guardian.item_id == _PRIVATE_GUARDIAN_ID
    with pytest.raises(KeyError):
        build_authored_item(_PRIVATE_GUARDIAN_ID, uuid4())


def test_cri_creature_factories_have_exact_owners_and_items_stay_direct() -> None:
    """Actual callable registration owns factories; item roots use no presets."""
    registry = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry
    factories = [
        row for row in registry.declarations.values()
        if row.mode is ContentDeclarationMode.FACTORY
    ]
    assert factories
    factory_owners = []
    for declaration in factories:
        assert declaration.ref.definition_kind is ContentDefinitionKind.CREATURE
        assert registry.resolve_factory(declaration.ref) is declaration
        assert declaration.construction is not None
        factory = declaration.construction.factory
        assert get_content_declaration(factory).ref == declaration.ref
        factory_owners.append(factory)
    assert len(set(factory_owners)) == len(factories)
    assert not any(
        row.ref.definition_kind in {
            ContentDefinitionKind.ITEM, ContentDefinitionKind.ENVIRONMENT_OBJECT,
        }
        for row in registry.declarations.values()
    )
    assert not registry.recipe_presets


def test_cri_runtime_behavior_owners_cover_current_declarations() -> None:
    """Class and provider-only admissions cover real identities without aliases."""
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    behavior_ids = {
        row.ref.content_id for row in loaded.registry.declarations.values()
        if row.mode is ContentDeclarationMode.BEHAVIOR_IDENTITY
    }
    class_ids = {
        row.ref.content_id for row in loaded.behavior_declarations_by_class.values()
    }
    assert behavior_ids
    assert len(class_ids) == len(loaded.behavior_declarations_by_class)
    assert not class_ids & loaded.provider_only_behavior_ids
    assert class_ids | loaded.provider_only_behavior_ids == behavior_ids
    for behavior_type, declaration in loaded.behavior_declarations_by_class.items():
        assert declaration.mode is ContentDeclarationMode.BEHAVIOR_IDENTITY
        assert get_content_declaration(behavior_type).ref == declaration.ref
        assert loaded.registry.resolve_definition(declaration.ref) is declaration

    legacy_ids = {row.ref.content_id for row in loaded.registry.declarations.values()}
    assert not set(DIRECT_ITEM_BUILDERS) & legacy_ids
