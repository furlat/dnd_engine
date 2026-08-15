"""Import NeuroClient's authored sub-item map into a backend-owned ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_SOURCE_SHA256 = (
    "3adaea5f6717fd8fc19198176ebe2cd32211681d6c522163a998697aca83a27a"
)
EXPECTED_SOURCE_CATEGORY_COUNT = 77
EXPECTED_AUTHORED_CATEGORY_COUNT = 77
EXPECTED_AUTHORED_VARIANT_COUNT = 205

_CATEGORY_TARGETS = {
    "Armored Boots": "content.neurodragon:item:apparel.armored_boots@1",
    "Battleaxe": "content.srd_5_1_cc:item:weapon.battleaxe@1",
    "Breastplate": "content.srd_5_1_cc:item:armor.breastplate@1",
    "Chain Mail": "content.srd_5_1_cc:item:armor.chain_mail@1",
    "Chain Shirt": "content.srd_5_1_cc:item:armor.chain_shirt@1",
    "Cloth Shoes": "content.neurodragon:item:apparel.cloth_shoes@1",
    "Cloth Hood": "content.neurodragon:item:apparel.cloth_hood@1",
    "Club": "content.srd_5_1_cc:item:weapon.club@1",
    "Common Clothes": "content.neurodragon:item:apparel.common_clothes@1",
    "Costume": "content.neurodragon:item:apparel.costume@1",
    "Crown": "content.neurodragon:item:apparel.crown@1",
    "Dagger": "content.srd_5_1_cc:item:weapon.dagger@1",
    "Double-Bladed Sword": (
        "content.neurodragon:item:weapon.double_bladed_sword@1"
    ),
    "Fine Clothes": "content.neurodragon:item:apparel.fine_clothes@1",
    "Greataxe": "content.srd_5_1_cc:item:weapon.greataxe@1",
    "Greatsword": "content.srd_5_1_cc:item:weapon.greatsword@1",
    "Half Plate": "content.srd_5_1_cc:item:armor.half_plate@1",
    "Handaxe": "content.srd_5_1_cc:item:weapon.handaxe@1",
    "Hide Armor": "content.srd_5_1_cc:item:armor.hide@1",
    "Iron Helmet": "content.neurodragon:item:apparel.iron_helmet@1",
    "Javelin": "content.srd_5_1_cc:item:weapon.javelin@1",
    "Leather Armor": "content.srd_5_1_cc:item:armor.leather@1",
    "Leather Boots": "content.neurodragon:item:apparel.leather_boots@1",
    "Leather Gloves": "content.neurodragon:item:apparel.leather_gloves@1",
    "Leather Hood": "content.neurodragon:item:apparel.leather_hood@1",
    "Leather Shoes": "content.neurodragon:item:apparel.leather_shoes@1",
    "Longbow": "content.srd_5_1_cc:item:weapon.longbow@1",
    "Longsword": "content.srd_5_1_cc:item:weapon.longsword@1",
    "Mace": "content.srd_5_1_cc:item:weapon.mace@1",
    "Morningstar": "content.srd_5_1_cc:item:weapon.morningstar@1",
    "Off-hand Dagger": "content.srd_5_1_cc:item:weapon.dagger@1",
    "Off-hand Handaxe": "content.srd_5_1_cc:item:weapon.handaxe@1",
    "Off-hand Sickle": "content.srd_5_1_cc:item:weapon.sickle@1",
    "Off-hand Scimitar": "content.srd_5_1_cc:item:weapon.scimitar@1",
    "Off-hand Shortsword": "content.srd_5_1_cc:item:weapon.shortsword@1",
    "Padded Armor": "content.srd_5_1_cc:item:armor.padded@1",
    "Plate Armor": "content.srd_5_1_cc:item:armor.plate@1",
    "Quarterstaff": "content.srd_5_1_cc:item:weapon.quarterstaff@1",
    "Rapier": "content.srd_5_1_cc:item:weapon.rapier@1",
    "Ring Mail": "content.srd_5_1_cc:item:armor.ring_mail@1",
    "Robes": "content.neurodragon:item:apparel.robes@1",
    "Sandals": "content.neurodragon:item:apparel.sandals@1",
    "Scale Mail": "content.srd_5_1_cc:item:armor.scale_mail@1",
    "Scimitar": "content.srd_5_1_cc:item:weapon.scimitar@1",
    "Shield": "content.srd_5_1_cc:item:shield.shield@1",
    "Shortbow": "content.srd_5_1_cc:item:weapon.shortbow@1",
    "Shortsword": "content.srd_5_1_cc:item:weapon.shortsword@1",
    "Sickle": "content.srd_5_1_cc:item:weapon.sickle@1",
    "Sling": "content.srd_5_1_cc:item:weapon.sling@1",
    "Spear": "content.srd_5_1_cc:item:weapon.spear@1",
    "Splint Armor": "content.srd_5_1_cc:item:armor.splint@1",
    "Studded Leather": (
        "content.srd_5_1_cc:item:armor.studded_leather@1"
    ),
    "Traveler's Clothes": (
        "content.neurodragon:item:apparel.travelers_clothes@1"
    ),
    "Trident": "content.srd_5_1_cc:item:weapon.trident@1",
    "Warhammer": "content.srd_5_1_cc:item:weapon.warhammer@1",
    "Wizard's Hat": "content.neurodragon:item:apparel.wizard_hat@1",
    "Wooden Shield": "content.neurodragon:item:shield.wooden@1",
    "Bracers": "content.neurodragon:item:apparel.bracers@1",
    "Chain Coif": "content.neurodragon:item:apparel.chain_coif@1",
    "Gauntlets": "content.neurodragon:item:apparel.gauntlets@1",
    "Great Helm": "content.neurodragon:item:apparel.great_helm@1",
    "Horned Helmet": "content.neurodragon:item:apparel.horned_helmet@1",
    "Monster Hands": "content.neurodragon:item:apparel.monster_hands@1",
    "Monster Helm": "content.neurodragon:item:apparel.monster_helm@1",
    "Cloth Armor": "content.neurodragon:item:armor.cloth@1",
    "Off-hand Club": "content.srd_5_1_cc:item:weapon.club@1",
    "Assassin's Dagger": (
        "content.neurodragon:item:weapon.assassin_dagger@1"
    ),
    "Arcane Staff": "content.neurodragon:item:weapon.arcane_staff@1",
    "Light Crossbow": (
        "content.srd_5_1_cc:item:weapon.light_crossbow@1"
    ),
    "Heavy Crossbow": (
        "content.srd_5_1_cc:item:weapon.heavy_crossbow@1"
    ),
    "Armor Scraps": "content.neurodragon:item:armor.armor_scraps@1",
    "Performer's Leather Armor": (
        "content.neurodragon:item:armor.circus.performer_leather@1"
    ),
    "Rusty Dagger": (
        "content.neurodragon:item:weapon.circus.rusty_dagger@1"
    ),
    "Flaming Scimitar": (
        "content.neurodragon:item:weapon.circus.flaming_scimitar@1"
    ),
    "Longsword +1": (
        "content.neurodragon:item:weapon.circus.longsword_plus_one@1"
    ),
    "Soul-Draining Morningstar": (
        "content.neurodragon:item:weapon.circus.soul_draining_morningstar@1"
    ),
}

_CATEGORY_EQUIPMENT_SLOTS = {
    "Armored Boots": "boots",
    "Armor Scraps": "body_armor",
    "Arcane Staff": "weapon_melee_main",
    "Assassin's Dagger": "weapon_melee_main",
    "Battleaxe": "weapon_melee_main",
    "Bracers": "gauntlets",
    "Breastplate": "body_armor",
    "Chain Coif": "helmet",
    "Chain Mail": "body_armor",
    "Chain Shirt": "body_armor",
    "Cloth Armor": "body_armor",
    "Cloth Hood": "helmet",
    "Cloth Shoes": "boots",
    "Club": "weapon_melee_main",
    "Common Clothes": "body_armor",
    "Costume": "body_armor",
    "Crown": "helmet",
    "Dagger": "weapon_melee_main",
    "Double-Bladed Sword": "weapon_melee_main",
    "Fine Clothes": "body_armor",
    "Flaming Scimitar": "weapon_melee_main",
    "Gauntlets": "gauntlets",
    "Greataxe": "weapon_melee_main",
    "Great Helm": "helmet",
    "Greatsword": "weapon_melee_main",
    "Half Plate": "body_armor",
    "Handaxe": "weapon_melee_main",
    "Heavy Crossbow": "weapon_ranged_main",
    "Hide Armor": "body_armor",
    "Horned Helmet": "helmet",
    "Iron Helmet": "helmet",
    "Javelin": "weapon_melee_main",
    "Leather Armor": "body_armor",
    "Leather Boots": "boots",
    "Leather Gloves": "gauntlets",
    "Leather Hood": "helmet",
    "Leather Shoes": "boots",
    "Light Crossbow": "weapon_ranged_main",
    "Longbow": "weapon_ranged_main",
    "Longsword": "weapon_melee_main",
    "Longsword +1": "weapon_melee_main",
    "Mace": "weapon_melee_main",
    "Monster Hands": "gauntlets",
    "Monster Helm": "helmet",
    "Morningstar": "weapon_melee_main",
    "Off-hand Club": "weapon_melee_off",
    "Off-hand Dagger": "weapon_melee_off",
    "Off-hand Handaxe": "weapon_melee_off",
    "Off-hand Scimitar": "weapon_melee_off",
    "Off-hand Shortsword": "weapon_melee_off",
    "Off-hand Sickle": "weapon_melee_off",
    "Padded Armor": "body_armor",
    "Performer's Leather Armor": "body_armor",
    "Plate Armor": "body_armor",
    "Quarterstaff": "weapon_melee_main",
    "Rapier": "weapon_melee_main",
    "Ring Mail": "body_armor",
    "Robes": "body_armor",
    "Rusty Blade": "weapon_melee_main",
    "Rusty Dagger": "weapon_melee_main",
    "Sandals": "boots",
    "Scale Mail": "body_armor",
    "Scimitar": "weapon_melee_main",
    "Shield": "weapon_melee_off",
    "Shortbow": "weapon_ranged_main",
    "Shortsword": "weapon_melee_main",
    "Sickle": "weapon_melee_main",
    "Sling": "weapon_ranged_main",
    "Soul-Draining Morningstar": "weapon_melee_main",
    "Spear": "weapon_melee_main",
    "Splint Armor": "body_armor",
    "Studded Leather": "body_armor",
    "Traveler's Clothes": "body_armor",
    "Trident": "weapon_melee_main",
    "Warhammer": "weapon_melee_main",
    "Wizard's Hat": "helmet",
    "Wooden Shield": "weapon_melee_off",
}

_PRIMARY_RENDER_LAYER_BY_EQUIPMENT_SLOT = {
    "body_armor": "chest",
    "boots": "shoes",
    "gauntlets": "hands",
    "helmet": "helmet",
    "weapon_melee_main": "weapon",
    "weapon_melee_off": "offhand",
    "weapon_ranged_main": "weapon",
    "weapon_ranged_off": "offhand",
}

_NON_ROOT_PRESENTATION_CATEGORIES = frozenset({
    "Off-hand Club",
    "Off-hand Dagger",
    "Off-hand Handaxe",
    "Off-hand Scimitar",
    "Off-hand Shortsword",
    "Off-hand Sickle",
})

_ADDITIONAL_FACTORY_PRESENTATION_BINDINGS = {
    "Club": (
        (
            "content.srd_5_1_cc:item:weapon.creature.ogre_greatclub@1",
            "weapon_melee_main",
            True,
        ),
    ),
    "Dagger": (
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.bandit_captain_thrown_dagger@1",
            "weapon_ranged_main",
            True,
        ),
    ),
    "Javelin": (
        (
            "content.srd_5_1_cc:item:weapon.creature.thrown_javelin@1",
            "weapon_ranged_main",
            True,
        ),
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.ogre_thrown_javelin@1",
            "weapon_ranged_main",
            True,
        ),
    ),
    "Light Crossbow": (
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.spy_hand_crossbow@1",
            "weapon_ranged_main",
            True,
        ),
    ),
    "Morningstar": (
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.bugbear_morningstar@1",
            "weapon_melee_main",
            True,
        ),
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.ogre_zombie_morningstar@1",
            "weapon_melee_main",
            True,
        ),
    ),
    "Off-hand Dagger": (
        (
            "content.neurodragon:item:weapon.assassin_dagger@1",
            "weapon_melee_off",
            False,
        ),
        (
            "content.neurodragon:item:weapon.circus.rusty_dagger@1",
            "weapon_melee_off",
            False,
        ),
    ),
    "Off-hand Scimitar": (
        (
            "content.neurodragon:item:"
            "weapon.circus.flaming_scimitar@1",
            "weapon_melee_off",
            False,
        ),
    ),
    "Sling": (
        (
            "content.srd_5_1_cc:item:weapon.creature.kobold_sling@1",
            "weapon_ranged_main",
            True,
        ),
    ),
}

_VARIANT_TARGET_OVERRIDES = {
    "10000004": "content.neurodragon:item:weapon.assassin_dagger@1",
    "1000000f": "content.neurodragon:item:weapon.arcane_staff@1",
}

_EXISTING_PRESET_IDS = {
    "81000001": "apparel.robes.wizard",
    "81000003": "apparel.robes.priest_vestments",
    "81000004": "apparel.robes.necromancer",
    "81000005": "apparel.robes.red_mage",
    "81000007": "apparel.robes.acolyte_vestments",
    "81000008": "apparel.robes.dark_cultist",
    "8100000b": "apparel.robes.hedge_wizard",
    "82000001": "apparel.common_clothes.farmhand_tunic",
    "82000009": "apparel.common_clothes.peasant_rags",
    "84000006": "apparel.travelers_clothes.thief_garb",
    "85000004": "apparel.costume.pit_fighter_wrap",
    "b0000002": "apparel.sandals.rope",
    "b0000003": "apparel.cloth_shoes.dark",
    "b0000004": "apparel.cloth_shoes.red",
    "b0000005": "apparel.cloth_shoes.blue",
    "b0000007": "apparel.leather_shoes.brown",
    "b0000008": "apparel.leather_boots.dark",
    "b0000009": "apparel.leather_boots.brown",
    "h0000008": "apparel.iron_helmet.steel",
    "h0000011": "apparel.wizard_hat.red",
}


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"id_{normalized}"
    return normalized


def _generic_preset_id(base_category: str, display_name: str) -> str:
    return f"item_variant.{_slug(base_category)}.{_slug(display_name)}"


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolved_equipment_layers(
    *,
    base_row: dict[str, Any],
    primary_render_layer: str,
    variant_row: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Resolve exact source inheritance into renderer-native layer rows."""
    override = variant_row or {}
    primary_tint = int(override.get("tint", base_row["tint"]))
    layers = [{
        "render_layer": primary_render_layer,
        "sprite_key": str(
            override.get("spriteCategory", base_row["spriteCategory"]),
        ),
        "tint_rgb": primary_tint,
    }]
    for render_layer, category_key, tint_key in (
        ("legs", "legsCategory", "legsTint"),
        ("belt", "beltCategory", "beltTint"),
    ):
        sprite_key = override.get(category_key, base_row.get(category_key))
        if sprite_key is None:
            continue
        tint_rgb = override.get(tint_key, base_row.get(tint_key))
        layers.append({
            "render_layer": render_layer,
            "sprite_key": str(sprite_key),
            "tint_rgb": (
                primary_tint
                if tint_rgb is None
                else int(tint_rgb)
            ),
        })
    return sorted(layers, key=lambda row: str(row["render_layer"]))


def build_inventory(source_path: Path) -> dict[str, Any]:
    """Normalize and authenticate the exact reviewed source inventory."""
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            "NeuroClient item visual inventory source digest changed: "
            f"{source_sha256}",
        )
    source = json.loads(source_bytes)
    if not isinstance(source, dict):
        raise TypeError("NeuroClient item visual inventory must be an object")
    if len(source) != EXPECTED_SOURCE_CATEGORY_COUNT:
        raise ValueError("unexpected NeuroClient base-category count")

    categories: list[dict[str, Any]] = []
    raw_ids: dict[str, list[str]] = {}
    preset_ids: set[str] = set()
    for category_order, (base_category, base_row) in enumerate(source.items()):
        variants = base_row.get("subItems", [])
        target = _CATEGORY_TARGETS.get(base_category)
        supported = target is not None
        equipment_slot = _CATEGORY_EQUIPMENT_SLOTS.get(base_category)
        if equipment_slot is None:
            raise ValueError(
                f"missing equipment-slot classification for {base_category!r}",
            )
        primary_render_layer = _PRIMARY_RENDER_LAYER_BY_EQUIPMENT_SLOT.get(
            equipment_slot,
        )
        if primary_render_layer is None:
            raise ValueError(
                "missing primary render-layer classification for equipment "
                f"slot {equipment_slot!r}",
            )
        factory_presentation_bindings = []
        if supported:
            factory_presentation_bindings.append({
                "equipment_slot": equipment_slot,
                "factory_identity": target,
                "root_presentation_owner": (
                    base_category
                    not in _NON_ROOT_PRESENTATION_CATEGORIES
                ),
            })
        factory_presentation_bindings.extend(
            {
                "equipment_slot": slot,
                "factory_identity": identity,
                "root_presentation_owner": owner,
            }
            for identity, slot, owner in (
                _ADDITIONAL_FACTORY_PRESENTATION_BINDINGS.get(
                    base_category,
                    (),
                )
            )
        )
        normalized_variants: list[dict[str, Any]] = []
        for variant_order, row in enumerate(variants):
            raw_id = str(row["id"])
            inventory_id = (
                f"item_visual.{_slug(base_category)}.{_slug(raw_id)}"
            )
            raw_ids.setdefault(raw_id, []).append(inventory_id)
            preset_id = None
            variant_target = None
            visual_variant_id = None
            if supported:
                variant_target = _VARIANT_TARGET_OVERRIDES.get(raw_id, target)
                preset_id = _EXISTING_PRESET_IDS.get(
                    raw_id,
                    _generic_preset_id(base_category, str(row["name"])),
                )
                if preset_id in preset_ids:
                    raise ValueError(f"duplicate preset identity {preset_id}")
                preset_ids.add(preset_id)
                visual_variant_id = raw_id
            normalized_variants.append({
                "display_name": str(row["name"]),
                "inventory_id": inventory_id,
                "mechanical_factory_identity": variant_target,
                "notes": str(row.get("notes", "")),
                "preset_id": preset_id,
                "source_order": variant_order,
                "source_visual_variant_id": raw_id,
                "equipment_layers": _resolved_equipment_layers(
                    base_row=base_row,
                    primary_render_layer=primary_render_layer,
                    variant_row=row,
                ),
                "tags": sorted(set(str(tag) for tag in row.get("tags", []))),
                "visual_variant_id": visual_variant_id,
            })
        categories.append({
            "base_category": base_category,
            "base_presentation": {
                "equipment_layers": _resolved_equipment_layers(
                    base_row=base_row,
                    primary_render_layer=primary_render_layer,
                ),
                "notes": str(base_row.get("notes", "")),
                "tags": sorted(
                    set(str(tag) for tag in base_row.get("tags", [])),
                ),
            },
            "classification": (
                "supported_existing_factory"
                if supported
                else "unsupported_missing_factory"
            ),
            "equipment_slot": equipment_slot,
            "factory_presentation_bindings": (
                factory_presentation_bindings
            ),
            "mechanical_factory_identity": target,
            "primary_render_layer": primary_render_layer,
            "source_order": category_order,
            "unsupported_reason": (
                None
                if supported
                else (
                    "No canonical item factory currently exists for the "
                    f"{base_category!r} mechanical base."
                )
            ),
            "variants": normalized_variants,
        })

    variant_count = sum(len(row["variants"]) for row in categories)
    if len(categories) != EXPECTED_AUTHORED_CATEGORY_COUNT:
        raise ValueError("unexpected authored base-category count")
    if variant_count != EXPECTED_AUTHORED_VARIANT_COUNT:
        raise ValueError("unexpected authored sub-item count")
    collisions = {
        raw_id: inventory_ids
        for raw_id, inventory_ids in sorted(raw_ids.items())
        if len(inventory_ids) > 1
    }
    inventory_payload = {
        "categories": categories,
        "source_visual_variant_id_collisions": collisions,
    }
    return {
        "authored_category_count": len(categories),
        "authored_variant_count": variant_count,
        "inventory_digest": _canonical_digest(inventory_payload),
        "inventory": inventory_payload,
        "schema_version": 3,
        "source": {
            "captured_date": "2026-07-25",
            "license_scope": (
                "NeuroDragon project-authored renderer metadata; not SRD text."
            ),
            "provenance": (
                "Normalized from the NeuroClient renderer map so backend "
                "content packs own durable item presentation identities."
            ),
            "repository": "NeuroClient",
            "repository_relative_path": (
                "app/src/render/data/defaultItemVisualMap.json"
            ),
            "sha256": source_sha256,
            "source_base_category_count": len(source),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "content_data"
            / "ledgers"
            / "neuroclient_authored_item_visuals.json"
        ),
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    output = (
        json.dumps(
            build_inventory(arguments.source),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if arguments.check:
        if not arguments.output.exists():
            raise SystemExit(f"missing generated ledger {arguments.output}")
        if arguments.output.read_text(encoding="utf-8") != output:
            raise SystemExit(
                f"generated ledger is stale: {arguments.output}",
            )
        return
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
