"""Backend spell catalog construction for design-time clients."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import inspect
import re
from typing import Any, Dict, List, Optional, Tuple, Type, cast
from uuid import uuid4

from dnd.actions import SpellAction
from dnd.core.aoe import Cone, Cube, Cylinder, Line, Sphere
from dnd.core.base_actions import TargetType
from dnd.core.events import RangeType
from dnd.core.naming import normalize_spell_id
from dnd.spells import ALL_SPELLS

from server.api_models import (
    AoeCatalogShapeType,
    ProjectileCatalogType,
    SpellCatalogEntry,
    SpellCatalogMultiTarget,
    SpellCatalogRangeType,
    SpellCatalogResponse,
    SpellCatalogRouteHint,
    SpellCatalogSavingThrow,
    SpellCatalogVfx,
)

CATALOG_VERSION = "2026-05-03.1"

PROJECTILE_TYPES = {"bolt", "ray", "orb", "beam", "dart", "spray", "radiance", "touch", "rain"}
AOE_SHAPE_TYPES = {"sphere", "cone", "line", "cube", "cylinder"}

SPELL_CATALOG_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "fire_bolt": {
        "aliases": ["Firebolt"],
        "classes": ["wizard", "sorcerer", "warlock"],
        "recommended_asset_tags": ["fire", "bolt"],
    },
    "magic_missile": {
        "classes": ["wizard", "sorcerer"],
        "recommended_asset_tags": ["force", "dart"],
    },
    "fireball": {
        "classes": ["wizard", "sorcerer"],
        "recommended_asset_tags": ["fire", "orb", "explosion"],
    },
    "ice_storm": {
        "damage_types": ["Bludgeoning", "Cold"],
        "recommended_asset_tags": ["ice", "hail", "storm"],
    },
    "flame_strike": {
        "damage_types": ["Fire", "Radiant"],
        "recommended_asset_tags": ["fire", "radiant", "cylinder"],
    },
    "mass_heal": {
        "healing": True,
        "recommended_asset_tags": ["healing", "radiance"],
    },
}

HEALING_SPELL_IDS = {
    "cure_wounds",
    "healing_word",
    "prayer_of_healing",
    "mass_healing_word",
    "mass_cure_wounds",
    "heal",
    "mass_heal",
    "regenerate",
}


@lru_cache(maxsize=1)
def build_spell_catalog() -> SpellCatalogResponse:
    """Build the complete spell catalog from registered spell classes."""
    spells = [
        build_spell_catalog_entry(display_name, spell_cls)
        for display_name, spell_cls in ALL_SPELLS.items()
    ]
    return SpellCatalogResponse(
        version=CATALOG_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        spells=spells,
    )


def build_spell_catalog_entry(display_name: str, spell_cls: Type[SpellAction]) -> SpellCatalogEntry:
    """Build a catalog entry for one spell class."""
    spell_id = normalize_spell_id(display_name)
    override = SPELL_CATALOG_OVERRIDES.get(spell_id, {})
    spell = _instantiate_spell(spell_cls, display_name)
    source = _get_source(spell_cls)

    projectile_type = _projectile_type(spell.projectile_type)
    aoe_shape_type = _aoe_shape_type(spell)
    aoe_radius_ft, aoe_length_ft, aoe_width_ft = _aoe_dimensions(spell)
    range_type = _range_type(spell)
    damage_types = override.get("damage_types", _damage_types(spell))
    saving_throw = _saving_throw(source)
    multi_target = _multi_target(spell)
    route_hint = _route_hint(spell, projectile_type, aoe_shape_type, multi_target)
    healing = bool(override.get("healing", spell_id in HEALING_SPELL_IDS))
    recommended_asset_tags = override.get(
        "recommended_asset_tags",
        _recommended_asset_tags(spell, projectile_type, aoe_shape_type, damage_types),
    )

    return SpellCatalogEntry(
        id=spell_id,
        name=display_name,
        aliases=list(override.get("aliases", [])),
        level=spell.spell_level,
        school=spell.spell_school,
        description=spell.description or None,
        target_type=spell.effective_target_type.value,
        range_type=range_type,
        range_ft=spell.spell_range.normal if spell.spell_range else None,
        projectile_type=projectile_type,
        aoe_shape_type=aoe_shape_type,
        aoe_radius_ft=aoe_radius_ft,
        aoe_length_ft=aoe_length_ft,
        aoe_width_ft=aoe_width_ft,
        damage_types=damage_types,
        healing=healing,
        attack_roll=_uses_attack_roll(source),
        saving_throw=saving_throw,
        concentration=spell.concentration,
        ritual=bool(override.get("ritual", False)),
        verbal=spell.verbal,
        somatic=override.get("somatic"),
        material=override.get("material"),
        classes=list(override.get("classes", [])),
        subclasses=list(override.get("subclasses", [])),
        source=override.get("source", "backend_catalog"),
        multi_target=multi_target,
        vfx=SpellCatalogVfx(
            projectile_type=projectile_type,
            aoe_shape_type=aoe_shape_type,
            route_hint=route_hint,
            recommended_asset_tags=recommended_asset_tags,
        ),
    )


def _instantiate_spell(spell_cls: Type[SpellAction], display_name: str) -> SpellAction:
    source_uuid = uuid4()
    spell = spell_cls(source_entity_uuid=source_uuid, use_register=False)
    if spell.name is None:
        spell.name = display_name
    return spell


def _get_source(spell_cls: Type[SpellAction]) -> str:
    try:
        return inspect.getsource(spell_cls)
    except (OSError, TypeError):
        return ""


def _projectile_type(value: Optional[str]) -> Optional[ProjectileCatalogType]:
    if value is None:
        return None
    normalized = value.lower()
    return cast(ProjectileCatalogType, normalized) if normalized in PROJECTILE_TYPES else None


def _aoe_shape_type(spell: SpellAction) -> Optional[AoeCatalogShapeType]:
    shape = spell.aoe_shape
    if shape is None or not shape.name:
        return None
    normalized = shape.name.lower()
    return cast(AoeCatalogShapeType, normalized) if normalized in AOE_SHAPE_TYPES else None


def _aoe_dimensions(spell: SpellAction) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    shape = spell.aoe_shape
    if shape is None:
        return None, None, None

    radius = spell._get_aoe_radius_ft()
    length: Optional[int] = None
    width: Optional[int] = None
    if isinstance(shape, Cone):
        length = shape.length_feet
    elif isinstance(shape, Line):
        length = shape.length_feet
        width = shape.width_feet
    elif isinstance(shape, Cube):
        length = shape.size_feet
        width = shape.size_feet
    elif isinstance(shape, (Sphere, Cylinder)):
        radius = shape.radius_feet
    return radius, length, width


def _range_type(spell: SpellAction) -> Optional[SpellCatalogRangeType]:
    if spell.spell_range.type == RangeType.SELF:
        return "self"
    if spell.spell_range.type == RangeType.REACH:
        return "touch"
    if spell.spell_range.type == RangeType.RANGE:
        return "ranged"
    return None


def _damage_types(spell: SpellAction) -> List[str]:
    if spell.spell_damage_type:
        return [spell.spell_damage_type.value]
    return []


def _uses_attack_roll(source: str) -> bool:
    return "spell_attack_bonus" in source or "determine_attack_outcome" in source


def _saving_throw(source: str) -> Optional[SpellCatalogSavingThrow]:
    if "create_saving_throw_request" not in source and "saving_throw(" not in source:
        return None
    match = re.search(r"(?:ability_name|save_ability)\s*=\s*[\"']([a-zA-Z_]+)[\"']", source)
    if not match:
        return SpellCatalogSavingThrow(ability="unknown", dc_source="caster_spell_save_dc")
    return SpellCatalogSavingThrow(ability=match.group(1).upper()[:3], dc_source="caster_spell_save_dc")


def _multi_target(spell: SpellAction) -> Optional[SpellCatalogMultiTarget]:
    if spell.effective_target_type != TargetType.MULTI_ENTITY:
        return None
    count = spell.get_multi_target_count()
    return SpellCatalogMultiTarget(
        min_targets=1,
        max_targets=count,
        allow_same_target=spell.allow_same_target,
        projectiles_per_cast=count,
    )


def _route_hint(
    spell: SpellAction,
    projectile_type: Optional[ProjectileCatalogType],
    aoe_shape_type: Optional[AoeCatalogShapeType],
    multi_target: Optional[SpellCatalogMultiTarget],
) -> SpellCatalogRouteHint:
    if spell.spell_range.type == RangeType.SELF and aoe_shape_type is None:
        return "self"
    if projectile_type == "beam":
        return "beam"
    if projectile_type == "ray":
        return "ray"
    if multi_target and projectile_type:
        return "missile_volley"
    if aoe_shape_type and projectile_type:
        return "aoe_projectile"
    if aoe_shape_type:
        return "aoe"
    if spell.spell_range.type == RangeType.REACH or projectile_type == "touch":
        return "touch"
    if projectile_type:
        return "single_projectile"
    return "none"


def _recommended_asset_tags(
    spell: SpellAction,
    projectile_type: Optional[ProjectileCatalogType],
    aoe_shape_type: Optional[AoeCatalogShapeType],
    damage_types: List[str],
) -> List[str]:
    tags: List[str] = []
    tags.extend(damage_type.lower() for damage_type in damage_types)
    if projectile_type:
        tags.append(projectile_type)
    if aoe_shape_type:
        tags.append(aoe_shape_type)
    if spell.concentration:
        tags.append("concentration")
    return list(dict.fromkeys(tags))
