"""Runtime receipts shared by structural character grant appliers."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from dnd.core.content.durable_characters import ProficiencySubject
from dnd.core.content.identities import ContentRef


class ModifierHandleChannel(str, Enum):
    """Closed ModifiableValue channel used by a reversible grant handle."""

    SELF_STATIC = "self_static"
    SELF_CONTEXTUAL = "self_contextual"


class ModifierHandleKind(str, Enum):
    """Closed modifier collection addressed by a reversible grant handle."""

    VALUE = "value"
    MIN_CONSTRAINT = "min_constraint"
    MAX_CONSTRAINT = "max_constraint"
    ADVANTAGE = "advantage"
    CRITICAL = "critical"
    AUTO_HIT = "auto_hit"


@dataclass(frozen=True, slots=True)
class ModifierHandle:
    """Exact value/modifier pair owned by one structural grant."""

    value_uuid: UUID
    modifier_uuid: UUID
    channel: ModifierHandleChannel = ModifierHandleChannel.SELF_STATIC
    kind: ModifierHandleKind = ModifierHandleKind.VALUE


@dataclass(frozen=True, slots=True)
class ProficiencyHandle:
    """Exact source-owned proficiency installed on one engine surface."""

    subject: ProficiencySubject
    source_id: UUID


@dataclass(frozen=True, slots=True)
class ConditionImmunityHandle:
    """Exact block/condition/source tuple owned by one structural grant."""

    block_uuid: UUID
    condition_name: str
    source_id: UUID


@dataclass(frozen=True, slots=True)
class LearnedReactionSpellHandle:
    """One casting-source contribution to a shared learned-spell handler."""

    spell_ref: ContentRef
    spellcasting_source_id: UUID
    handler_uuid: UUID


@dataclass(frozen=True, slots=True)
class CharacterGrantReceipt:
    """Runtime handles installed by one deterministic structural grant."""

    grant_id: UUID
    grant_token: str | None = None
    definition_ref: ContentRef | None = None
    modifier_handles: tuple[ModifierHandle, ...] = ()
    proficiency_handles: tuple[ProficiencyHandle, ...] = ()
    hit_die_uuids: tuple[UUID, ...] = ()
    spellcasting_source_ids: tuple[UUID, ...] = ()
    normal_spell_slot_capacity_source_ids: tuple[UUID, ...] = ()
    spell_damage_affinity_contribution_ids: tuple[UUID, ...] = ()
    action_uuids: tuple[UUID, ...] = ()
    handler_uuids: tuple[UUID, ...] = ()
    learned_reaction_spell_handles: tuple[
        LearnedReactionSpellHandle,
        ...,
    ] = ()
    condition_handles: tuple[tuple[UUID, UUID], ...] = ()
    resource_contribution_ids: tuple[tuple[str, UUID], ...] = ()
    resource_recovery_contribution_ids: tuple[tuple[str, UUID], ...] = ()
    armor_class_formula_ids: tuple[UUID, ...] = ()
    attack_multiplicity_grant_ids: tuple[UUID, ...] = ()
    condition_immunity_handles: tuple[ConditionImmunityHandle, ...] = ()
    transient_condition_refs_to_remove: tuple[ContentRef, ...] = ()


__all__ = [
    "CharacterGrantReceipt",
    "ConditionImmunityHandle",
    "LearnedReactionSpellHandle",
    "ModifierHandle",
    "ModifierHandleChannel",
    "ModifierHandleKind",
    "ProficiencyHandle",
]
