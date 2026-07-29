"""Built-in structural feature appliers keyed by exact authored identity.

These appliers install cold, source-owned engine structure.  They deliberately
do not create permanent conditions: temporary conditions remain evented
gameplay state, while character composition is removed through its receipt.
"""

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid5

from dnd.classes.structural_feature_definitions import (
    REMARKABLE_ATHLETE_DECLARATION,
)
from dnd.classes.barbarian_progression_definitions import (
    BERSERKER_SUBCLASS_REF,
)
from dnd.classes.progression_definitions import CHAMPION_SUBCLASS_REF
from dnd.classes.sorcerer_progression_definitions import (
    DRACONIC_BLOODLINE_SUBCLASS_REF,
)
from dnd.content_system.barbarian_character_grant_appliers import (
    BARBARIAN_CHARACTER_GRANT_APPLIERS,
)
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
    CharacterGrantScheduleKind,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ModifierHandle,
    ModifierHandleChannel,
    ProficiencyHandle,
)
from dnd.content_system.dragonborn_character_grant_appliers import (
    install_dragonborn_ancestry_feature,
)
from dnd.content_system.dragonborn_origin_definitions import (
    DRAGONBORN_ANCESTRY_DECLARATIONS,
)
from dnd.content_system.extra_attack_character_grant_appliers import (
    EXTRA_ATTACK_CHARACTER_GRANT_APPLIERS,
)
from dnd.content_system.fighter_character_grant_appliers import (
    FIGHTER_CHARACTER_GRANT_APPLIERS,
)
from dnd.content_system.sorcerer_character_grant_appliers import (
    SORCERER_CHARACTER_GRANT_APPLIERS,
)
from dnd.content_system.origin_runtime_character_grant_appliers import (
    ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS,
)
from dnd.core.content.durable_characters import (
    ProficiencySubject,
    ProficiencySubjectKind,
)
from dnd.core.content.dragonborn import DragonbornAncestryFeatureDefinition
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.events import AbilityName
from dnd.core.modifiers import (
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.core.proficiency_types import ProficiencyMode
from dnd.entity import Entity


CharacterGrantApplier = Callable[
    [BuiltinCharacterGrantContext, CharacterGrantScheduleEntry],
    CharacterGrantReceipt,
]


_DRAGONBORN_ANCESTRY_REFS = {
    declaration.ref.identity_key: declaration
    for declaration in DRAGONBORN_ANCESTRY_DECLARATIONS
}
_NON_STRUCTURAL_CONTENT_KINDS = frozenset({
    ContentDefinitionKind.SPELL,
    ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
})
_METADATA_ONLY_CONTENT_REFS = frozenset({
    BERSERKER_SUBCLASS_REF.identity_key,
    CHAMPION_SUBCLASS_REF.identity_key,
    DRACONIC_BLOODLINE_SUBCLASS_REF.identity_key,
})


def _apply_dragonborn_ancestry(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    """Install one validated Dragonborn ancestry choice."""
    content_ref = entry.content_ref
    if content_ref is None:
        raise ValueError("Dragonborn ancestry grant requires exact content")
    declaration = _DRAGONBORN_ANCESTRY_REFS.get(content_ref.identity_key)
    if declaration is None or declaration.ref != content_ref:
        raise ValueError("Dragonborn ancestry applier received another ref")
    definition = declaration.definition_payload
    if not isinstance(definition, DragonbornAncestryFeatureDefinition):
        raise TypeError("Dragonborn ancestry definition has the wrong payload")
    return install_dragonborn_ancestry_feature(
        entity=context.entity,
        character_id=context.character_id,
        grant_token=entry.grant_token,
        definition_ref=content_ref,
        character_level=sum(
            class_level
            for _, class_level in context.preview.class_level_counts
        ),
        definition=definition,
        runtime=context.runtime,
    )


def _remarkable_athlete_jump_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: UUID | None = None,
    context: dict[str, object] | None = None,
) -> NumericalModifier | None:
    """Return the owner's current Strength modifier as a jump contribution."""
    _ = target_entity_uuid
    _ = context
    entity = Entity.get(source_entity_uuid)
    if entity is None:
        return None
    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Remarkable Athlete",
        value=entity.ability_scores.strength.modifier,
    )


def _apply_remarkable_athlete(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    """Install Champion's structural check and jump contributions."""
    entity = context.entity
    if entry.content_ref != REMARKABLE_ATHLETE_DECLARATION.ref:
        raise ValueError(
            "Remarkable Athlete applier received a different content ref",
        )
    source_id = uuid5(context.character_id, entry.grant_token)
    proficiency_handles: list[ProficiencyHandle] = []
    modifier_handles: list[ModifierHandle] = []
    try:
        for ability_name in ("strength", "dexterity", "constitution"):
            subject = ProficiencySubject(
                subject_kind=ProficiencySubjectKind.ABILITY_CHECK,
                subject_id=f"ability_check.{ability_name}",
            )
            entity.ability_scores.get_ability(
                ability_name,
            ).add_check_proficiency_source(
                source_id,
                ProficiencyMode.HALF_ROUND_UP,
            )
            proficiency_handles.append(
                ProficiencyHandle(
                    subject=subject,
                    source_id=source_id,
                ),
            )

        modifier = ContextualNumericalModifier(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Remarkable Athlete",
            callable=_remarkable_athlete_jump_bonus,
        )
        entity.jump_distance_additive.self_contextual.add_value_modifier(
            modifier,
        )
        modifier_handles.append(
            ModifierHandle(
                value_uuid=entity.jump_distance_additive.uuid,
                modifier_uuid=modifier.uuid,
                channel=ModifierHandleChannel.SELF_CONTEXTUAL,
            ),
        )
    except Exception:
        for handle in reversed(proficiency_handles):
            subject_id = handle.subject.subject_id
            if subject_id is None:
                continue
            entity.ability_scores.get_ability(
                cast(
                    AbilityName,
                    subject_id.removeprefix("ability_check."),
                ),
            ).remove_check_proficiency_source(handle.source_id)
        for modifier_handle in reversed(modifier_handles):
            entity.jump_distance_additive.self_contextual.remove_value_modifier(
                modifier_handle.modifier_uuid,
            )
        raise

    return CharacterGrantReceipt(
        grant_id=source_id,
        grant_token=entry.grant_token,
        definition_ref=entry.content_ref,
        modifier_handles=tuple(modifier_handles),
        proficiency_handles=tuple(proficiency_handles),
    )


_BUILTIN_CHARACTER_GRANT_APPLIERS: dict[str, CharacterGrantApplier] = {
    REMARKABLE_ATHLETE_DECLARATION.ref.identity_key: (
        _apply_remarkable_athlete
    ),
    **{
        identity_key: _apply_dragonborn_ancestry
        for identity_key in _DRAGONBORN_ANCESTRY_REFS
    },
    **EXTRA_ATTACK_CHARACTER_GRANT_APPLIERS,
    **FIGHTER_CHARACTER_GRANT_APPLIERS,
    **BARBARIAN_CHARACTER_GRANT_APPLIERS,
    **SORCERER_CHARACTER_GRANT_APPLIERS,
    **ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS,
}


def apply_builtin_character_grant(
    *,
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt | None:
    """Apply a recognized built-in content grant, or decline metadata-only rows."""
    if entry.kind not in {
        CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
        CharacterGrantScheduleKind.SELECTED_CONTENT,
    }:
        return None
    content_ref = entry.content_ref
    if content_ref is None:
        raise ValueError("content grant schedule row has no content reference")
    applier = _BUILTIN_CHARACTER_GRANT_APPLIERS.get(content_ref.identity_key)
    if applier is None:
        if (
            content_ref.definition_kind in _NON_STRUCTURAL_CONTENT_KINDS
            or content_ref.identity_key in _METADATA_ONLY_CONTENT_REFS
        ):
            return None
        raise RuntimeError(
            "No structural character applier is installed for "
            f"{content_ref.identity_key}",
        )
    return applier(context, entry)


__all__ = [
    "BuiltinCharacterGrantContext",
    "CharacterGrantApplier",
    "apply_builtin_character_grant",
]
