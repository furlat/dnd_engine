"""Native content descriptors for the client, without SDL/media loading."""

from dnd.content.characters.class_definitions import FIGHTER_DEFINITION, BARBARIAN_DEFINITION, SORCERER_DEFINITION
from dnd.content.items.authored_item_builders import DIRECT_ITEM_BUILDERS
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from game.ui.content_types import UIContentManifest


def ui_content_manifest() -> UIContentManifest:
    loaded=SERVER_CONTENT_SYSTEM_RUNTIME.require()
    levels=(*FIGHTER_DEFINITION.levels,*FIGHTER_DEFINITION.champion_levels,
        *BARBARIAN_DEFINITION.levels,*BARBARIAN_DEFINITION.berserker_levels,
        *SORCERER_DEFINITION.levels,*SORCERER_DEFINITION.draconic_levels)
    features=frozenset(value for level in levels
        for value in (*level.feature_ids,*(value for choice in level.choices for value in choice.allowed_values))
        if value.startswith(('class_feature.','feat.','metamagic.')))
    return UIContentManifest(content=tuple((d.ref,d.descriptor) for d in loaded.registry.declarations.values()),
        feature_ids=features,item_ids=frozenset(DIRECT_ITEM_BUILDERS))

