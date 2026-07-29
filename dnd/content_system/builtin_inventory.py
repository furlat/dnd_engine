"""Exact declaration and preset inventory for trusted built-in content."""

from __future__ import annotations

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
from dnd.classes.barbarian_progression_definitions import (
    BARBARIAN_PROGRESSION_DECLARATIONS,
)
from dnd.classes.content_factories import PLAYER_CLASS_CREATURE_DECLARATIONS
from dnd.classes.progression_definitions import (
    FIGHTER_PROGRESSION_DECLARATIONS,
)
from dnd.classes.sorcerer_progression_definitions import (
    SORCERER_PROGRESSION_DECLARATIONS,
)
from dnd.classes.sorcerer_structural_feature_definitions import (
    SORCERER_STRUCTURAL_FEATURE_DECLARATIONS,
)
from dnd.classes.structural_feature_definitions import (
    STRUCTURAL_CLASS_FEATURE_DECLARATIONS,
)
from dnd.conditions import CORE_STANDARD_CONDITION_DECLARATIONS
from dnd.content_system.action_definitions import ACTION_BEHAVIOR_DECLARATIONS
from dnd.content_system.character_origin_definitions import (
    NEURODRAGON_CHARACTER_ORIGIN_DECLARATIONS,
    SRD_CHARACTER_ORIGIN_DECLARATIONS,
)
from dnd.content_system.origin_feature_definitions import (
    SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS,
)
from dnd.content_system.condition_effect_population import (
    populate_builtin_condition_effects,
)
from dnd.content_system.dragonborn_origin_definitions import (
    DRAGONBORN_ANCESTRY_DECLARATIONS,
)
from dnd.content_system.reaction_definitions import (
    REACTION_BEHAVIOR_DECLARATIONS,
)
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS,
)
from dnd.content_system.starting_apparel_definitions import (
    STARTING_APPAREL_PACKAGE_DECLARATIONS,
)
from dnd.content_system.acolyte_starting_holdings import (
    ACOLYTE_STARTING_HOLDINGS_DECLARATION,
)
from dnd.core.content.recipe_presets import ContentRecipePreset
from dnd.core.content.registration import ContentDeclaration
from dnd.extensions.field_focus import (
    NEURODRAGON_FIELD_FOCUS_ITEM_DECLARATIONS,
)
from dnd.items.armors import (
    NEURODRAGON_ARMOR_DECLARATIONS,
    SRD_ARMOR_DECLARATIONS,
)
from dnd.items.acolyte_gear import SRD_ACOLYTE_GEAR_DECLARATIONS
from dnd.items.authored_variant_presets import (
    NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS,
)
from dnd.items.consumables import NEURODRAGON_CONSUMABLE_DECLARATIONS
from dnd.items.environment_content import (
    NEURODRAGON_ENVIRONMENT_OBJECT_DECLARATIONS,
)
from dnd.items.spell_items import (
    ACID_FLASK_SPELL_DECLARATION,
    NEURODRAGON_SPELL_ITEM_DECLARATIONS,
)
from dnd.items.torches import NEURODRAGON_TORCH_DECLARATIONS
from dnd.items.weapons import (
    NEURODRAGON_WEAPON_DECLARATIONS,
    SRD_WEAPON_DECLARATIONS,
)
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_DECLARATIONS
from dnd.monsters.bestiary_items import (
    NEURODRAGON_BESTIARY_ITEM_DECLARATIONS,
)
from dnd.monsters.circus_fighter_items import (
    NEURODRAGON_CIRCUS_ITEM_DECLARATIONS,
)
from dnd.monsters.multiattack_definitions import (
    SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS,
)
from dnd.monsters.configured_srd_creatures import (
    CONFIGURED_SRD_CREATURE_DECLARATIONS,
)
from dnd.monsters.srd_roster import SRD_CREATURE_DECLARATIONS
from dnd.monsters.srd_roster_items import (
    SRD_CREATURE_POSSESSION_ITEM_DECLARATIONS,
)
from dnd.origins.dragonborn import (
    DRAGONBORN_BREATH_WEAPON_DECLARATION,
)
from dnd.origins.halfling import HALFLING_LUCKY_DECLARATION
from dnd.origins.half_orc import (
    HALF_ORC_RELENTLESS_ENDURANCE_DECLARATION,
)
from dnd.premade_characters import NEURODRAGON_PREMADE_CREATURE_DECLARATIONS
from dnd.player_character_body import PLAYER_CHARACTER_BODY_DECLARATION
from dnd.spells.abjuration import (
    COUNTERSPELL_REACTION_DECLARATION,
    SHIELD_REACTION_DECLARATION,
)
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS
from dnd.spells.conjuration import (
    SRD_SPELL_ENVIRONMENT_OBJECT_DECLARATIONS,
)
from dnd.spells.reaction_spell_content import (
    LEARNED_REACTION_SPELL_DECLARATIONS,
)
from dnd.spells.infernal import (
    HELLISH_REBUKE_REACTION_DECLARATION,
    HELLISH_REBUKE_SPELL_DECLARATION,
    THAUMATURGY_SPELL_DECLARATION,
)


_UNPOPULATED_BUILT_IN_DECLARATION_INVENTORY: tuple[
    ContentDeclaration,
    ...,
] = (
    *CORE_STANDARD_ACTION_DECLARATIONS,
    *CORE_STANDARD_CONDITION_DECLARATIONS,
    *ACTION_BEHAVIOR_DECLARATIONS,
    *CONDITION_BEHAVIOR_DECLARATIONS,
    *REACTION_BEHAVIOR_DECLARATIONS,
    *STRUCTURAL_CLASS_FEATURE_DECLARATIONS,
    *SORCERER_STRUCTURAL_FEATURE_DECLARATIONS,
    *SRD_CHARACTER_ORIGIN_DECLARATIONS,
    *NEURODRAGON_CHARACTER_ORIGIN_DECLARATIONS,
    *SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS,
    *DRAGONBORN_ANCESTRY_DECLARATIONS,
    DRAGONBORN_BREATH_WEAPON_DECLARATION,
    HALF_ORC_RELENTLESS_ENDURANCE_DECLARATION,
    HALFLING_LUCKY_DECLARATION,
    *STARTING_EQUIPMENT_PACKAGE_DECLARATIONS,
    *STARTING_APPAREL_PACKAGE_DECLARATIONS,
    ACOLYTE_STARTING_HOLDINGS_DECLARATION,
    *BARBARIAN_PROGRESSION_DECLARATIONS,
    *FIGHTER_PROGRESSION_DECLARATIONS,
    *SORCERER_PROGRESSION_DECLARATIONS,
    COUNTERSPELL_REACTION_DECLARATION,
    SHIELD_REACTION_DECLARATION,
    *LEARNED_REACTION_SPELL_DECLARATIONS,
    HELLISH_REBUKE_REACTION_DECLARATION,
    HELLISH_REBUKE_SPELL_DECLARATION,
    THAUMATURGY_SPELL_DECLARATION,
    *NEURODRAGON_ARMOR_DECLARATIONS,
    *NEURODRAGON_BESTIARY_ITEM_DECLARATIONS,
    *NEURODRAGON_CIRCUS_ITEM_DECLARATIONS,
    *CONFIGURED_SRD_CREATURE_DECLARATIONS,
    *BESTIARY_CREATURE_DECLARATIONS,
    *NEURODRAGON_CONSUMABLE_DECLARATIONS,
    *NEURODRAGON_ENVIRONMENT_OBJECT_DECLARATIONS,
    *NEURODRAGON_FIELD_FOCUS_ITEM_DECLARATIONS,
    *NEURODRAGON_PREMADE_CREATURE_DECLARATIONS,
    PLAYER_CHARACTER_BODY_DECLARATION,
    *NEURODRAGON_SPELL_ITEM_DECLARATIONS,
    *NEURODRAGON_TORCH_DECLARATIONS,
    *NEURODRAGON_WEAPON_DECLARATIONS,
    *PLAYER_CLASS_CREATURE_DECLARATIONS,
    ACID_FLASK_SPELL_DECLARATION,
    *SPELL_CONTENT_DECLARATIONS,
    *SRD_SPELL_ENVIRONMENT_OBJECT_DECLARATIONS,
    *SRD_ARMOR_DECLARATIONS,
    *SRD_ACOLYTE_GEAR_DECLARATIONS,
    *SRD_CREATURE_POSSESSION_ITEM_DECLARATIONS,
    *SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS,
    *SRD_CREATURE_DECLARATIONS,
    *SRD_WEAPON_DECLARATIONS,
)
BUILT_IN_DECLARATION_INVENTORY = populate_builtin_condition_effects(
    _UNPOPULATED_BUILT_IN_DECLARATION_INVENTORY,
)
BUILT_IN_RECIPE_PRESET_INVENTORY: tuple[ContentRecipePreset, ...] = (
    *NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS,
)


__all__ = [
    "BUILT_IN_DECLARATION_INVENTORY",
    "BUILT_IN_RECIPE_PRESET_INVENTORY",
]
