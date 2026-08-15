"""Exact learned-spell roots backed by independently authored reactions.

Shield and Counterspell are learned spells, but their playable runtime surface
is an event handler rather than a clickable ``SpellAction``.  This module keeps
those two identities distinct and joins them only through explicit
``INSTALLS_HANDLER`` dependency edges.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
)
from dnd.core.events.events_registry import (
    EventHandler,
)
from dnd.spells.abjuration import (
    COUNTERSPELL_REACTION_DECLARATION,
    SHIELD_REACTION_DECLARATION,
    CounterspellReactionHandler,
    ShieldReactionHandler,
    create_counterspell_reaction_handler,
    create_shield_reaction_handler,
)
from dnd.spells.content_metadata import (
    SpellCatalogMetadata,
    srd_spell_identity,
)


LearnedReactionHandlerFactory = Callable[[UUID], EventHandler]


@dataclass(frozen=True, slots=True)
class LearnedReactionSpellSpec:
    """One exact spell root and the reaction behavior it installs."""

    display_name: str
    definition_source: type[object]
    declaration: ContentDeclaration
    metadata: SpellCatalogMetadata
    school: str
    level: int
    catalog_order: int
    handler_type: type[EventHandler]
    handler_factory: LearnedReactionHandlerFactory


def _installs_handler(
    declaration: ContentDeclaration,
) -> tuple[ContentDependency, ...]:
    return (
        ContentDependency(
            relation=ContentDependencyRelation.INSTALLS_HANDLER,
            target_ref=declaration.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes=(
                "Knowing this exact spell installs its independently "
                "attributed reaction handler."
            ),
        ),
    )


@srd_spell_identity(
    content_id="spell.shield",
    display_name="Shield",
    description=(
        "Use a reaction to gain +5 Armor Class and block Magic Missile until "
        "the start of your next turn."
    ),
    school="abjuration",
    level=1,
    source_page=180,
    sort_order=205,
    icon_key="reaction.shield",
    dependencies=_installs_handler(SHIELD_REACTION_DECLARATION),
)
class ShieldLearnedSpell:
    """Non-clickable learned spell root for the Shield reaction."""


@srd_spell_identity(
    content_id="spell.counterspell",
    display_name="Counterspell",
    description=(
        "Use a reaction to interrupt a visible creature casting a spell "
        "within 60 feet."
    ),
    school="abjuration",
    level=3,
    source_page=131,
    sort_order=705,
    dependencies=_installs_handler(COUNTERSPELL_REACTION_DECLARATION),
)
class CounterspellLearnedSpell:
    """Non-clickable learned spell root for the Counterspell reaction."""


SHIELD_SPELL_DECLARATION = get_content_declaration(ShieldLearnedSpell)
COUNTERSPELL_SPELL_DECLARATION = get_content_declaration(
    CounterspellLearnedSpell,
)


def _create_learned_counterspell_handler(
    source_entity_uuid: UUID,
) -> EventHandler:
    """Create Counterspell bound to its exact learned-spell source set."""
    return create_counterspell_reaction_handler(
        source_entity_uuid,
        learned_spell_ref=COUNTERSPELL_SPELL_DECLARATION.ref,
    )


_SHIELD_METADATA = SpellCatalogMetadata(
    catalog_id="shield",
    description=(
        "Reaction: gain +5 AC and block Magic Missile until your next turn."
    ),
    target_type="self",
    range_type="self",
    range_ft=0,
    delivery="self",
    projectile_type=None,
    aoe=None,
    damage_types=(),
    healing=False,
    attack_roll=False,
    saving_throws=(),
    concentration=False,
    ritual=False,
    verbal=True,
    somatic=True,
    material=False,
    classes=("sorcerer", "wizard"),
    subclasses=(),
    multi_target=None,
    recommended_asset_tags=("abjuration", "shield", "reaction"),
)
_COUNTERSPELL_METADATA = SpellCatalogMetadata(
    catalog_id="counterspell",
    description=(
        "Reaction: interrupt a visible creature casting a spell within 60 "
        "feet."
    ),
    target_type="entity",
    range_type="ranged",
    range_ft=60,
    delivery="none",
    projectile_type=None,
    aoe=None,
    damage_types=(),
    healing=False,
    attack_roll=False,
    saving_throws=(),
    concentration=False,
    ritual=False,
    verbal=False,
    somatic=True,
    material=False,
    classes=("sorcerer", "warlock", "wizard"),
    subclasses=(),
    multi_target=None,
    recommended_asset_tags=("abjuration", "counterspell", "reaction"),
)


LEARNED_REACTION_SPELL_SPECS: tuple[LearnedReactionSpellSpec, ...] = (
    LearnedReactionSpellSpec(
        display_name="Shield",
        definition_source=ShieldLearnedSpell,
        declaration=SHIELD_SPELL_DECLARATION,
        metadata=_SHIELD_METADATA,
        school="abjuration",
        level=1,
        catalog_order=205,
        handler_type=ShieldReactionHandler,
        handler_factory=create_shield_reaction_handler,
    ),
    LearnedReactionSpellSpec(
        display_name="Counterspell",
        definition_source=CounterspellLearnedSpell,
        declaration=COUNTERSPELL_SPELL_DECLARATION,
        metadata=_COUNTERSPELL_METADATA,
        school="abjuration",
        level=3,
        catalog_order=705,
        handler_type=CounterspellReactionHandler,
        handler_factory=_create_learned_counterspell_handler,
    ),
)
LEARNED_REACTION_SPELL_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    spec.declaration for spec in LEARNED_REACTION_SPELL_SPECS
)

for _spec in LEARNED_REACTION_SPELL_SPECS:
    _dependencies = tuple(
        dependency
        for dependency in _spec.declaration.dependencies
        if dependency.relation is ContentDependencyRelation.INSTALLS_HANDLER
    )
    if (
        len(_dependencies) != 1
        or _dependencies[0].target_ref
        != get_content_declaration(_spec.handler_type).ref
    ):
        raise RuntimeError(
            "Learned reaction spell does not install its exact handler: "
            f"{_spec.declaration.ref.identity_key}",
        )


__all__ = [
    "COUNTERSPELL_SPELL_DECLARATION",
    "CounterspellLearnedSpell",
    "LEARNED_REACTION_SPELL_DECLARATIONS",
    "LEARNED_REACTION_SPELL_SPECS",
    "LearnedReactionHandlerFactory",
    "LearnedReactionSpellSpec",
    "SHIELD_SPELL_DECLARATION",
    "ShieldLearnedSpell",
]
