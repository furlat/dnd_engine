"""Admit the settled palette/partial-outfit/cloak selections from the frozen bible.

Authoring only: the game never reads the private handoff. Original pixels stay
in their preserved ZIP; registrations and palette recipes use existing owners.
"""

import argparse
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import zipfile

from PIL import Image

from dnd.items.authored_variant_inventory import AuthoredItemVariantCategory, AuthoredItemVariantLedger
from game.item_appearance import ItemAppearanceDocument


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_SHA = "fb25c343932523a684e2ea03db9aa287dfd73fc311cfb685867f6b5f9e5e9b8c"
OFFHAND_LONGSWORD = "recommendation.724760f143086fc2"
MAUL_RECORD = "recommendation.95d553b995244dc5"
CLOAK_RECORDS = {"recommendation.22852dc18f7bc2cd", "recommendation.24e94ba86ac133ff"}
# Vendor only supplies two offhand silhouettes. These category-qualified
# substitutions are approximations, never altered mechanics or new geometry.
TALENT_HAND_SHEETS = {
    "Wand": "Offhand2", "Crowbar": "Offhand2",
    "Javelin": "Offhand1", "Spear": "Offhand1", "Quarterstaff": "Offhand1",
    "Arcane Staff": "Offhand1", "Rapier": "Offhand1", "Longsword": "Offhand1",
    "Longsword +1": "Offhand1", "Trident": "Offhand1",
    "Mace": "Offhand2", "Morningstar": "Offhand2", "Warhammer": "Offhand2",
    "Battleaxe": "Offhand2", "Soul-Draining Morningstar": "Offhand2",
    "Assassin's Dagger": "Offhand2", "Rusty Dagger": "Offhand2",
    "Flaming Scimitar": "Offhand1",
}
# Reviewed authoring reconciliation only; none of these study keys is a runtime ID.
ORDINARY_GAP_ITEMS = {
    "gap.0492850d8b9c03cd": ("tool.banner", "Banner"),
    "gap.7e8c70e1f6af7897": ("focus.wand", "Wand"),
    "gap.8c45e56e7e13957e": ("gear.canister", "Back Canister"),
    "gap.af17f53160bc0118": ("weapon.musket", "Musket"),
    "gap.c2733a274e9ddcb6": ("gear.saddle", "Saddle and Tack"),
    "gap.cbf14e096242e487": ("tool.crowbar", "Crowbar"),
}
ENCHANTED_POSSESSION_ITEMS = {
    "48d4b74b08c1.p5": "weapon.roster.ember_longsword",
    "b59e73b6cc44.p4": "weapon.roster.ember_longsword",
    "9f74ed954ba8.p4": "weapon.roster.ember_greatsword",
    "1c51ab737db3.p1": "weapon.roster.psychic_scimitar",
    "1c51ab737db3.p2": "weapon.roster.psychic_scimitar",
    "8fdb756ad9a1.p3": "weapon.roster.psychic_greataxe",
    "3d7a7ff0e102.p2": "weapon.roster.psychic_trident",
    "7c436df99411.p2": "weapon.roster.psychic_longsword",
    "ad8defebd1f2.p4": "weapon.roster.psychic_longsword_greater",
}
SOURCE_PREFIX = "Fantasy Character Creator_Data/StreamingAssets/Spritesheets"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def author(handoff: Path, archive: Path, receipt: Path) -> None:
    if receipt.exists():
        raise FileExistsError("Preserve the first admission/media delta receipt; use a new receipt path for a later run")
    payload = handoff.read_bytes()
    if hashlib.sha256(payload).hexdigest() != HANDOFF_SHA:
        raise ValueError("roster handoff differs from the reviewed frozen snapshot")
    intake = json.loads(payload)
    ledger_path = ROOT / "content_data/ledgers/neuroclient_authored_item_visuals.json"
    ledger = json.loads(ledger_path.read_text())
    appearances_path = ROOT / "game/data/item_appearances.json"
    appearances = json.loads(appearances_path.read_text())
    categories: dict = {row["base_category"]: row for row in ledger["inventory"]["categories"]}
    if "Cloak" not in categories:
        categories["Cloak"] = dict(
            base_category="Cloak",
            base_presentation=dict(equipment_layers=[dict(render_layer="cloak", sprite_key="Bag1", tint_rgb=0x343436)],
                                   notes="Ordinary cloth cloak; original vendor back layer.", tags=["apparel", "cloth", "cloak"]),
            classification="supported_existing_factory", equipment_slot="cloak",
            factory_presentation_bindings=[dict(equipment_slot="cloak", factory_identity="content.neurodragon:item:apparel.cloak@1", root_presentation_owner=True)],
            mechanical_factory_identity="content.neurodragon:item:apparel.cloak@1",
            primary_render_layer="cloak", source_order=len(categories), unsupported_reason=None, variants=[])
        ledger["inventory"]["categories"].append(categories["Cloak"])
    cloak_category: dict = categories["Cloak"]
    cloak_category["primary_render_layer"] = "cloak"
    for recipe in (cloak_category["base_presentation"], *cloak_category["variants"]):
        for layer in recipe["equipment_layers"]:
            layer["render_layer"] = "cloak"
    for row in appearances["ground"]:
        if row["category"] == "Cloak":
            for layer in row["layers"]:
                layer["render_layer"] = "cloak"
    categories["Common Clothes"]["allowed_registration_layers"] = ["chest", "legs"]
    ordinary = (
        ("Maul", "weapon.maul", "weapon_melee_main", "weapon", "Melee11", 12039858),
        ("Wand", "focus.wand", "weapon_melee_main", "weapon", "Melee19", 8952234),
        ("Crowbar", "tool.crowbar", "weapon_melee_main", "weapon", "Melee10", 8952234),
        ("Banner", "tool.banner", "weapon_melee_main", "weapon", "Melee25", 5974125),
        ("Musket", "weapon.musket", "weapon_ranged_main", "weapon", "Ranged3", 8952234),
        ("Quiver", "gear.quiver", "backpack", "backpack", "Bag2", 6637363),
        ("Back Canister", "gear.canister", "backpack", "backpack", "Bag2", 8952234),
    )
    for name, item_id, slot, layer, key, tint in ordinary:
        if name not in categories:
            factory = f"content.neurodragon:item:{item_id}@1"
            category = dict(base_category=name, base_presentation=dict(
                equipment_layers=[dict(render_layer=layer, sprite_key=key, tint_rgb=tint)],
                notes="Existing vendor silhouette approximation; does not promise exact wand length, crowbar hook, banner flag, firearm, canister or larger maul-head geometry.", tags=["ordinary", "approximation"]),
                classification="supported_existing_factory", equipment_slot=slot,
                factory_presentation_bindings=[dict(equipment_slot=slot, factory_identity=factory, root_presentation_owner=True)],
                mechanical_factory_identity=factory, primary_render_layer=layer,
                source_order=len(categories), unsupported_reason=None, variants=[])
            ledger["inventory"]["categories"].append(category)
            categories[name] = category
    rig = json.loads((ROOT / "game/data/neuroclient/rig-tables.json").read_text())
    layer_order = {layer: i for i, layer in enumerate(rig["SLOT_RENDER_ORDER"])}
    decisions, admitted, selected_keys = [], [], set()
    ground_keys = {(r["category"], r["variant"]) for r in appearances["ground"]}
    hand_keys = {(r["category"], r["variant"], r["slot"]) for r in appearances["hands"]}
    with zipfile.ZipFile(archive) as original:
        for row in intake["deduplicated_items"]:
            selected = row["selected"]
            identity = row["id"]
            if selected is None or selected["appearance_outcome"] != "new_palette_or_layer_recipe":
                decisions.append(dict(id=identity, state="existing_selection" if selected else "ordinary_gear_admitted" if identity in ORDINARY_GAP_ITEMS else "unsettled", consumers=row["consumers"]))
                continue
            cloak = identity in CLOAK_RECORDS
            maul = identity == MAUL_RECORD
            quiver = identity == "recommendation.18ec8cf1d3121b12"
            category = categories["Maul" if maul else "Quiver" if quiver else "Cloak" if cloak else selected["category"]]
            layers = sorted(selected["selected_layers"], key=lambda r: layer_order[r["render_layer"]])
            if quiver:
                layers = deepcopy(category["base_presentation"]["equipment_layers"])
            if cloak:
                layers = deepcopy(layers)
                for layer in layers:
                    layer["render_layer"] = "cloak"
            anchor = category["primary_render_layer"]
            offhand_sword = identity == OFFHAND_LONGSWORD
            # One physical sword keeps its main-hand recipe; the explicit hand
            # binding supplies the reviewed vendor approximation in the left hand.
            if offhand_sword:
                layers = deepcopy(selected["source_category_layers"])
                for layer in layers:
                    layer["tint_rgb"] = selected["selected_layers"][0]["tint_rgb"]
            if category["base_category"] == "Common Clothes" and all(r["render_layer"] != "chest" for r in layers) and any(r["render_layer"] == "legs" for r in layers):
                anchor = "legs"
            if (not maul and not cloak and not quiver and (row["mechanical_base"] != selected["base_factory"] or (row["native_slot"] != category["equipment_slot"] and not offhand_sword))) or sum(r["render_layer"] == anchor for r in layers) != 1:
                decisions.append(dict(id=identity, state="unsettled_base_slot_or_anchor", consumers=row["consumers"]))
                continue
            variant = selected["proposed_variant_key"]
            note = f"Roster-derived appearance, 2026-10-02; {identity}; handoff SHA256 {HANDOFF_SHA}. {selected['fit_note']} Cosmetic only; unchanged native base rules."
            if not any(r["visual_variant_id"] == variant for r in category["variants"]):
                category["variants"].append(dict(
                    display_name=row["label"], equipment_layers=layers,
                    inventory_id=f"item_visual.{variant}", mechanical_factory_identity=category["mechanical_factory_identity"],
                    notes=note, preset_id=f"item_variant.{variant}", source_order=len(category["variants"]),
                    source_visual_variant_id=f"roster-derived:{identity}", tags=["roster-derived", "palette", "cosmetic"],
                    visual_variant_id=variant, **({"registration_render_layer": anchor} if anchor != category["primary_render_layer"] else {})))
            primary = next(r for r in layers if r["render_layer"] == anchor)
            if (category["base_category"], variant) not in ground_keys:
                pivots = []
                for camera_row in (2, 4, 6, 0):
                    merged = Image.new("RGBA", (128, 128))
                    for layer in layers:
                        sheet = Image.open(BytesIO(original.read(f"{SOURCE_PREFIX}/{layer['sprite_key']}/Idle.png"))).convert("RGBA")
                        merged.alpha_composite(sheet.crop((0, camera_row*128, 128, (camera_row+1)*128)))
                    box = merged.getchannel("A").getbbox()
                    if box is None:
                        raise ValueError(f"empty selected ground frame: {identity}/{camera_row}")
                    pivots.append([(box[0]+box[2])/2, (box[1]+box[3])/2])
                appearances["ground"].append(dict(category=category["base_category"], variant=variant, sprite_key=primary["sprite_key"], layers=layers,
                    clip="Idle", frame=0, rows_by_camera=[2,4,6,0], cell=[128,128], pivots_by_camera=pivots,
                    scale=.75, reference_tile_width=64, tint=primary["tint_rgb"], rotation=0,
                    shadow_sprite_key="Shadow", shadow_scale=.18, notes=note+" Isolated held/outfit frame is a deliberate floor approximation, centered at contact."))
                ground_keys.add((category["base_category"], variant))
            if offhand_sword:
                key = (category["base_category"], variant, row["native_slot"])
                if key not in hand_keys:
                    appearances["hands"].append(dict(category=category["base_category"], variant=variant,
                        slot=row["native_slot"], layers=selected["selected_layers"],
                        notes=note+" Reviewed straight Offhand1 approximation; eligibility belongs to the actor's non-light offhand talent."))
                    hand_keys.add(key)
                    selected_keys.update(r["sprite_key"] for r in selected["selected_layers"])
            # Existing accepted opposite-hand geometry only; no new eligibility.
            templates = [r for r in appearances["hands"] if r["category"] == category["base_category"] and r["variant"] is None]
            for template in templates:
                key = (category["base_category"], variant, template["slot"])
                if key not in hand_keys:
                    counterpart = deepcopy(template)
                    counterpart["variant"] = variant
                    counterpart["notes"] = note+" Existing accepted opposite-hand substitution."
                    for layer in counterpart["layers"]:
                        layer["tint_rgb"] = primary["tint_rgb"]
                    appearances["hands"].append(counterpart)
                    hand_keys.add(key)
                    selected_keys.update(r["sprite_key"] for r in counterpart["layers"])
            selected_keys.update(r["sprite_key"] for r in layers)
            admitted.append(dict(id=identity, category=category["base_category"], variant=variant,
                                 base=category["mechanical_factory_identity"], consumers=row["consumers"]))
        # Default cloak needs a ground appearance too, retaining the same recipe.
        if ("Cloak", None) not in ground_keys:
            default = deepcopy(next(r for r in appearances["ground"] if r["category"] == "Cloak"))
            base_cloak = AuthoredItemVariantCategory.model_validate(categories["Cloak"]).base_presentation
            default.update(variant=None, layers=[layer.model_dump(mode="json") for layer in base_cloak.equipment_layers], tint=0x343436,
                           notes="Ordinary base cloak; original Bag1 and isolated ground registration. No magical or armor bonus.")
            appearances["ground"].append(default)
        ground_ordinary = (*ordinary, ("Saddle and Tack", "gear.saddle", None, "backpack", "Bag2", 9136404))
        for name, _, _, layer, key, tint in ground_ordinary:
            selected_keys.add(key)
            if (name, None) in ground_keys:
                continue
            image = Image.open(BytesIO(original.read(f"{SOURCE_PREFIX}/{key}/Idle.png"))).convert("RGBA")
            pivots = []
            for camera_row in (2, 4, 6, 0):
                box = image.crop((0, camera_row*128, 128, (camera_row+1)*128)).getchannel("A").getbbox()
                if box is None:
                    raise ValueError(f"empty ordinary gear frame: {name}/{camera_row}")
                pivots.append([(box[0]+box[2])/2, (box[1]+box[3])/2])
            appearances["ground"].append(dict(category=name, variant=None, sprite_key=key,
                layers=[dict(render_layer=layer, sprite_key=key, tint_rgb=tint)], clip="Idle", frame=0,
                rows_by_camera=[2,4,6,0], cell=[128,128], pivots_by_camera=pivots, scale=.75,
                reference_tile_width=64, tint=tint, rotation=0, shadow_sprite_key="Shadow", shadow_scale=.18,
                notes="Isolated original vendor frame; disclosed approximate silhouette, centered at contact."))
            ground_keys.add((name, None))
        for category_name, sprite_key in TALENT_HAND_SHEETS.items():
            category = categories[category_name]
            recipes = [(None, category["base_presentation"]["equipment_layers"])]
            recipes.extend((row["visual_variant_id"], row["equipment_layers"])
                           for row in category["variants"])
            for variant, recipe_layers in recipes:
                key = (category_name, variant, "weapon_melee_off")
                if key in hand_keys:
                    continue
                primary = next(row for row in recipe_layers if row["render_layer"] == "weapon")
                appearances["hands"].append(dict(category=category_name, variant=variant,
                    slot="weapon_melee_off", layers=[dict(render_layer="offhand",
                    sprite_key=sprite_key, tint_rgb=primary["tint_rgb"])],
                    notes="Vendor offhand silhouette approximation using existing original sheets and palette replacement; pole length, axe/hammer head and trident tines are not exact. Actor-owned eligibility and native weapon rules remain unchanged."))
                hand_keys.add(key)
                selected_keys.add(sprite_key)
        bindings_path = ROOT / "game/data/neuroclient/bindings.json"
        bindings = json.loads(bindings_path.read_text())
        sources_path = ROOT / "game/data/item_media_sources.json"
        sources = json.loads(sources_path.read_text())
        if archive.name != sources["archive"]:
            raise ValueError("wrong equipment archive")
        files = {r["path"]: r for r in sources["files"]}
        previous_files = set(files)
        clips = sorted({Path(url).stem for url in bindings["resources"] if url.startswith("/spritesheets/NakedBody/")})
        for key in sorted(selected_keys):
            for clip in clips:
                url = f"/spritesheets/{key}/{clip}.png"
                relative = f"game/assets/neuroclient/spritesheets/{key}/{clip}.png"
                member = f"{SOURCE_PREFIX}/{key}/{clip}.png"
                if url not in bindings["resources"]:
                    original.getinfo(member)  # No Idle fallback for a missing action.
                    bindings["resources"][url] = relative
                    files[relative] = dict(member=member, path=relative)
        sources["files"] = sorted(files.values(), key=lambda r: r["path"])
    ledger["authored_category_count"] = len(categories)
    ledger["authored_variant_count"] = sum(len(r["variants"]) for r in categories.values())
    ledger["inventory_digest"] = hashlib.sha256(json.dumps(ledger["inventory"], allow_nan=False, ensure_ascii=False, separators=(",",":"), sort_keys=True).encode()).hexdigest()
    AuthoredItemVariantLedger.model_validate(ledger)
    ItemAppearanceDocument.model_validate(appearances)
    for path, value in ((ledger_path, ledger), (appearances_path, appearances), (bindings_path, bindings), (sources_path, sources)):
        write_json(path, value)
    # Cover every frozen record, including reuse and the later ordinary gear correction.
    # Keep per-possession power overrides separate from shared cosmetic deduplication.
    admitted_by_id = {row["id"]: row for row in admitted}
    production_records = []
    for row in intake["deduplicated_items"]:
        selected = row["selected"]
        admitted_row = admitted_by_id.get(row["id"])
        if admitted_row:
            category_name, variant, base = admitted_row["category"], admitted_row["variant"], admitted_row["base"]
        elif row["id"] in ORDINARY_GAP_ITEMS:
            item_id, category_name = ORDINARY_GAP_ITEMS[row["id"]]
            variant, base = None, f"content.neurodragon:item:{item_id}@1"
        elif selected:
            category_name, variant, base = selected["category"], selected["variant_id"], selected["base_factory"]
        else:
            raise ValueError(f"unaccounted roster item: {row['id']}")
        if category_name != "Saddle and Tack":
            category = categories[category_name]
            if category["mechanical_factory_identity"] != base:
                raise ValueError(f"incompatible roster mechanical base: {row['id']}")
            if variant is not None and not any(r["visual_variant_id"] == variant for r in category["variants"]):
                raise ValueError(f"missing roster variant: {row['id']}")
        if (category_name, variant) not in ground_keys:
            raise ValueError(f"missing roster ground binding: {row['id']}")
        native_slot = (None if category_name == "Saddle and Tack" else
                       categories[category_name]["equipment_slot"] if row["id"] in ORDINARY_GAP_ITEMS
                       or row["id"] in CLOAK_RECORDS or row["id"] in (MAUL_RECORD, "recommendation.18ec8cf1d3121b12")
                       else row["native_slot"])
        consumers = []
        for consumer in row["consumer_possessions"]:
            item_id = ENCHANTED_POSSESSION_ITEMS.get(consumer["possession"])
            consumers.append(dict(consumer, native_reference=base if item_id is None else f"content.neurodragon:item:{item_id}@1",
                                  category=category_name, variant=variant, native_slot=native_slot))
        for consumer in consumers:
            if consumer["possession"] == "6bbb248c8804.p4":
                consumer["coating_reference"] = "content.neurodragon:item:consumable.weapon_coat.basic_poison@1"
        production_records.append(dict(id=row["id"], label=row["label"], native_reference=base,
            category=category_name, variant=variant, native_slot=native_slot, consumers=consumers,
            fixed_holder_removal="deferred_by_human", effect_media="received_item_material"))
    if len({row["id"] for row in production_records}) != len(intake["deduplicated_items"]):
        raise ValueError("duplicate roster item reconciliation")
    character_records = []
    for character in intake["characters"]:
        possessions = [dict(consumer, record_id=row["id"]) for row in production_records
                       for consumer in row["consumers"] if consumer["character"] == character["key"]]
        if not possessions and character["possessions"]:
            raise ValueError(f"character possessions omitted: {character['key']}")
        character_records.append(dict(character=character["key"], identity=character["identity"],
            possessions=possessions, item_status="mapped" if possessions else "explicit_no_possessions"))
    write_json(receipt, dict(handoff_sha256=HANDOFF_SHA, production_records=production_records,
                            character_records=character_records,
                            admitted=admitted, remaining=decisions,
                            selected_keys=sorted(selected_keys), required_clips=clips,
                            new_media_paths=sorted(set(files)-previous_files)))
    print(f"Authored {len(admitted)} selections; added {len(set(files)-previous_files)} original media registrations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    author(args.handoff, args.archive, args.receipt)
