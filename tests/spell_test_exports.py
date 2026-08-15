"""Test-only conveniences for the native spell inventory.

Production code imports spell implementations or canonical catalog rows
directly.  Tests that exercise broad spell families may use this module
without turning ``dnd.spells`` into an eager re-export façade.
"""

from dnd.spells.abjuration import (
    MageArmor,
)
from dnd.spells.catalog_content import (
    SPELL_CATALOG_METADATA_BY_CLASS,
    SPELL_CATALOG_METADATA_BY_ID,
    SPELL_CATALOG_METADATA_BY_NAME,
    SPELL_CATALOG_METADATA_SPECS,
    SPELL_CONTENT_DECLARATIONS,
    SPELL_CONTENT_DECLARATIONS_BY_CLASS,
    SPELL_CONTENT_DECLARATIONS_BY_NAME,
    SPELL_CONTENT_IDENTITY_SPECS,
)
from dnd.spells.enchantment import PowerWordKill
from dnd.spells.evocation import (
    BurningHands,
    EldritchBlast,
    Fireball,
    FireBolt,
    GuidingBolt,
    MagicMissile,
    SacredFlame,
    ScorchingRay,
    Thunderwave,
)
from dnd.spells.necromancy import ChillTouch, FingerOfDeath, NecroticBless
from dnd.spells.transmutation import Haste


def _spell_map_for_level(level: int | None):
    return {
        spec.display_name: spec.spell_type
        for spec in SPELL_CONTENT_IDENTITY_SPECS
        if level is None or spec.level == level
    }


CANTRIPS = _spell_map_for_level(0)
LEVEL_1_SPELLS = _spell_map_for_level(1)
LEVEL_2_SPELLS = _spell_map_for_level(2)
LEVEL_3_SPELLS = _spell_map_for_level(3)
LEVEL_4_SPELLS = _spell_map_for_level(4)
LEVEL_5_SPELLS = _spell_map_for_level(5)
LEVEL_6_SPELLS = _spell_map_for_level(6)
LEVEL_7_SPELLS = _spell_map_for_level(7)
LEVEL_8_SPELLS = _spell_map_for_level(8)
LEVEL_9_SPELLS = _spell_map_for_level(9)
ALL_SPELLS = _spell_map_for_level(None)
