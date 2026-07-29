"""Explicit historical character-content migrations.

Rows in this module are authored migrations between two exact contracts.  A
pack/kind/content-ID resemblance is never enough to migrate a durable
character: the complete historical source ref must match one row.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from dnd.content_system.character_origin_definitions import (
    ADVENTURER_BACKGROUND_REF,
    HUMAN_SPECIES_REF,
)
from dnd.core.content.durable_characters import (
    BuildChoiceSelection,
    ProficiencySubject,
    ProficiencySubjectKind,
    StartingProficiencyChoice,
)
from dnd.core.content.identities import ContentRef
from dnd.core.language_types import SrdLanguageId


def exact_content_ref_key(ref: ContentRef) -> str:
    """Return the full contract-authenticated migration lookup key."""

    return f"{ref.identity_key}#{ref.definition_contract_hash}"


@dataclass(frozen=True, slots=True)
class CharacterContentRefMigration:
    """One exact historical ref replacement and its required origin choices."""

    source_ref: ContentRef
    target_ref: ContentRef
    added_origin_choices: tuple[BuildChoiceSelection, ...] = ()

    def __post_init__(self) -> None:
        if self.source_ref == self.target_ref:
            raise ValueError("content migration requires distinct refs")
        if (
            self.source_ref.pack_id != self.target_ref.pack_id
            or self.source_ref.definition_kind
            is not self.target_ref.definition_kind
            or self.source_ref.content_id != self.target_ref.content_id
        ):
            raise ValueError(
                "content migration cannot change the authored content root",
            )
        choice_ids = tuple(
            choice.choice_id for choice in self.added_origin_choices
        )
        if len(set(choice_ids)) != len(choice_ids):
            raise ValueError(
                "content migration origin choices must have unique IDs",
            )


_HISTORICAL_HUMAN_V1_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=HUMAN_SPECIES_REF.definition_kind,
    content_id="species.human",
    content_version=1,
    definition_contract_hash=(
        "4c1110dce3e2ab688603db91ba767cde7d564c1cc3b4a734b3b33811a6176545"
    ),
)
_HISTORICAL_ADVENTURER_V1_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ADVENTURER_BACKGROUND_REF.definition_kind,
    content_id="background.adventurer",
    content_version=1,
    definition_contract_hash=(
        "a6c220e89812efc6bcc9d0f9efb316803bfdc9b1c6a78144538425215ed1dc79"
    ),
)

CHARACTER_CONTENT_REF_MIGRATIONS = (
    CharacterContentRefMigration(
        source_ref=_HISTORICAL_HUMAN_V1_REF,
        target_ref=HUMAN_SPECIES_REF,
        added_origin_choices=(
            StartingProficiencyChoice(
                choice_id="species.human.additional_language",
                proficiencies=(
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.LANGUAGE,
                        subject_id=SrdLanguageId.DRACONIC.value,
                    ),
                ),
            ),
        ),
    ),
    CharacterContentRefMigration(
        source_ref=_HISTORICAL_ADVENTURER_V1_REF,
        target_ref=ADVENTURER_BACKGROUND_REF,
    ),
)

CHARACTER_CONTENT_REF_MIGRATIONS_BY_SOURCE = MappingProxyType({
    exact_content_ref_key(row.source_ref): row
    for row in CHARACTER_CONTENT_REF_MIGRATIONS
})


__all__ = [
    "CHARACTER_CONTENT_REF_MIGRATIONS",
    "CHARACTER_CONTENT_REF_MIGRATIONS_BY_SOURCE",
    "CharacterContentRefMigration",
    "exact_content_ref_key",
]
