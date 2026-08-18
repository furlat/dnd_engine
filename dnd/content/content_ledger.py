"""Optional cold listing of directly authored gameplay content."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from dnd.content.characters.character_definitions import (
    BACKGROUND_DEFINITIONS,
    SPECIES_DEFINITIONS,
    SPECIES_VARIANT_DEFINITIONS,
)
from dnd.content.characters.class_definitions import (
    CLASS_DEFINITIONS,
    SUBCLASS_DEFINITIONS,
)
from dnd.content.characters.premade_builds import PREMADE_CHARACTER_DEFINITIONS
from dnd.content.items.item_catalog import DIRECT_ITEM_CATALOG
from dnd.content.monsters.monster_definitions import MONSTER_DEFINITIONS
from dnd.content.monsters.srd_monster_definitions import SRD_MONSTER_DEFINITIONS
from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTERS,
    AUTHORED_ROSTERS,
)


class ContentLedgerKind(str, Enum):
    """Direct authored families exposed by the cold ledger."""

    SPECIES = "species"
    SPECIES_VARIANT = "species_variant"
    BACKGROUND = "background"
    CLASS = "class"
    SUBCLASS = "subclass"
    PREMADE = "premade"
    MONSTER = "monster"
    ITEM = "item"
    BATTLEFIELD = "battlefield"
    ROSTER = "roster"
    DEPLOYMENT = "deployment"
    ENCOUNTER = "encounter"


@dataclass(frozen=True, slots=True)
class ContentLedgerRow:
    """Renderer-neutral selection row; never a construction dispatch entry."""

    content_id: str
    kind: ContentLedgerKind
    display_name: str
    description: str


def _rows() -> tuple[ContentLedgerRow, ...]:
    rows = [
        *(
            ContentLedgerRow(
                f"species.{identity.value}",
                ContentLedgerKind.SPECIES,
                definition.display_name,
                definition.description,
            )
            for identity, definition in SPECIES_DEFINITIONS.items()
        ),
        *(
            ContentLedgerRow(
                f"species_variant.{identity.value}",
                ContentLedgerKind.SPECIES_VARIANT,
                definition.display_name,
                definition.description,
            )
            for identity, definition in SPECIES_VARIANT_DEFINITIONS.items()
        ),
        *(
            ContentLedgerRow(
                f"background.{identity.value}",
                ContentLedgerKind.BACKGROUND,
                definition.display_name,
                definition.description,
            )
            for identity, definition in BACKGROUND_DEFINITIONS.items()
        ),
        *(
            ContentLedgerRow(
                f"class.{identity.value}",
                ContentLedgerKind.CLASS,
                definition.display_name,
                definition.description,
            )
            for identity, definition in CLASS_DEFINITIONS.items()
        ),
        *(
            ContentLedgerRow(
                f"subclass.{identity.value}",
                ContentLedgerKind.SUBCLASS,
                definition.display_name,
                definition.description,
            )
            for identity, definition in SUBCLASS_DEFINITIONS.items()
        ),
        *(
            ContentLedgerRow(
                identity,
                ContentLedgerKind.PREMADE,
                definition.display_name,
                f"Authored {definition.display_name} character build.",
            )
            for identity, definition in PREMADE_CHARACTER_DEFINITIONS.items()
        ),
        *(
            ContentLedgerRow(
                identity,
                ContentLedgerKind.MONSTER,
                definition.name,
                definition.description,
            )
            for identity, definition in {
                **MONSTER_DEFINITIONS,
                **SRD_MONSTER_DEFINITIONS,
            }.items()
        ),
        *(
            ContentLedgerRow(
                entry.item_id,
                ContentLedgerKind.ITEM,
                entry.display_name,
                entry.description,
            )
            for entry in DIRECT_ITEM_CATALOG
        ),
        *(
            ContentLedgerRow(
                identity,
                ContentLedgerKind.BATTLEFIELD,
                identity.removeprefix("battlefield.").replace("_", " ").title(),
                "Authored renderer-independent battlefield.",
            )
            for identity in sorted({
                deployment.battlefield_id for deployment in AUTHORED_DEPLOYMENTS
            })
        ),
        *(
            ContentLedgerRow(
                roster.roster_id,
                ContentLedgerKind.ROSTER,
                roster.title,
                f"Authored roster containing {len(roster.members)} entities.",
            )
            for roster in AUTHORED_ROSTERS
        ),
        *(
            ContentLedgerRow(
                deployment.deployment_id,
                ContentLedgerKind.DEPLOYMENT,
                deployment.title,
                f"Authored deployment for {deployment.battlefield_id}.",
            )
            for deployment in AUTHORED_DEPLOYMENTS
        ),
        *(
            ContentLedgerRow(
                encounter.encounter_id,
                ContentLedgerKind.ENCOUNTER,
                encounter.title,
                f"Authored encounter on {encounter.battlefield_id}.",
            )
            for encounter in AUTHORED_ENCOUNTERS
        ),
    ]
    return tuple(rows)


CONTENT_LEDGER = _rows()
CONTENT_LEDGER_BY_KEY: Mapping[
    tuple[ContentLedgerKind, str],
    ContentLedgerRow,
] = MappingProxyType({
    (row.kind, row.content_id): row for row in CONTENT_LEDGER
})

if len(CONTENT_LEDGER_BY_KEY) != len(CONTENT_LEDGER):
    raise ValueError("content ledger contains duplicate kind/identity pairs")


__all__ = [
    "CONTENT_LEDGER",
    "CONTENT_LEDGER_BY_KEY",
    "ContentLedgerKind",
    "ContentLedgerRow",
]
