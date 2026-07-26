"""Server composition of approved premades into durable character revisions."""

from __future__ import annotations

from uuid import UUID, uuid5

from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevision,
    CharacterHoldingsRevision,
    CharacterItemV1,
)
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.premade_characters import PREMADE_CHARACTER_TEMPLATES
from server.game_directory.contracts import CharacterBootstrapCreate


class PremadeCharacterNotFoundError(KeyError):
    """Raised when a public request names no installed approved premade."""


def _starter_item_id(
    *,
    character_id: UUID,
    template_digest: str,
    holding_index: int,
) -> UUID:
    """Derive one retry-stable possession identity from the character template."""

    return uuid5(
        character_id,
        (
            "dnd-engine:starter-holding:v1:"
            f"{template_digest}:{holding_index}"
        ),
    )


def compose_premade_character_bootstrap(
    *,
    character_id: UUID,
    owner_principal_id: UUID,
    display_name: str,
    premade_id: str,
    content_system: LoadedContentSystem,
) -> CharacterBootstrapCreate:
    """Resolve one approved premade into exact immutable revision-one records."""

    template = PREMADE_CHARACTER_TEMPLATES.get(premade_id)
    if template is None:
        raise PremadeCharacterNotFoundError(premade_id)
    template.verify_integrity()

    creature_declaration = content_system.registry.resolve_factory(
        template.creature_recipe.ref,
    )
    if "player_capable" not in creature_declaration.descriptor.tags:
        raise ValueError(
            f"Premade {premade_id} does not resolve to a player-capable creature",
        )

    items: list[CharacterItemV1] = []
    for holding_index, holding in enumerate(template.starter_holdings):
        item_declaration = content_system.registry.resolve_factory(
            holding.recipe.ref,
        )
        item_definition = item_declaration.item_definition
        if item_definition is None:
            raise TypeError(
                f"Starter holding {holding.recipe.ref.identity_key} has no "
                "item definition",
            )
        if (
            item_definition.persistence_policy
            is not ItemPersistencePolicy.POSSESSION
        ):
            raise ValueError(
                f"Starter holding {holding.recipe.ref.identity_key} is not a "
                "durable possession",
            )
        items.append(
            CharacterItemV1.create(
                character_item_id=_starter_item_id(
                    character_id=character_id,
                    template_digest=template.template_digest,
                    holding_index=holding_index,
                ),
                recipe=holding.recipe,
                quantity=holding.quantity,
                equipped_slot=holding.equipped_slot,
            ),
        )

    definition = CharacterDefinitionRevision.create(
        character_id=character_id,
        definition_revision=1,
        creature_recipe=template.creature_recipe,
        premade_id=template.premade_id,
        content_set_digest=content_system.content_set_digest,
    )
    holdings = CharacterHoldingsRevision.create(
        character_id=character_id,
        holdings_revision=1,
        items=tuple(
            sorted(
                items,
                key=lambda item: item.character_item_id.hex,
            ),
        ),
    )
    return CharacterBootstrapCreate(
        character_id=character_id,
        owner_principal_id=owner_principal_id,
        display_name=display_name,
        definition=definition,
        starter_holdings=holdings,
    )


__all__ = [
    "PremadeCharacterNotFoundError",
    "compose_premade_character_bootstrap",
]
